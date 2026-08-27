"""Feature engineering module - builds ML-ready DataFrame from evidence.

Features unified tree output, precursor clusters, density, interactions,
barrier density, and consistency features.
"""

import pandas as pd
from typing import Dict, List, Optional

from .config import (
    SIF_PRECURSORS,
    PRECURSOR_CLUSTERS,
    DATAFRAME_SCHEMA,
    IOGP_LSR_RULES,
    IOGP_LSR_RULE_LABELS,
    SIF_SCORE_COMPONENTS,
    PRECURSOR_INTERACTIONS,
    LSRStatus,
    PrecursorStatus,
)


class FeatureEngineer:
    """Generates structured features from mapped precursor evidence."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS
        self.clusters = PRECURSOR_CLUSTERS

    def _build_precursor_features(self, mapped_precursors: Dict) -> Dict:
        features = {}
        for precursor in self.precursors:
            data = mapped_precursors.get(precursor, {})
            status = data.get("status", PrecursorStatus.NOT_MENTIONED)
            features[precursor] = status
            features[f"{precursor}_confidence"] = data.get("confidence", 0.0)
            features[f"{precursor}_evidence_count"] = data.get("evidence_count", 0)
            features[f"{precursor}_evidence_strength"] = data.get("evidence_strength", 0.0)
        return features

    def _build_cluster_features(self, cluster_results: Dict) -> Dict:
        features = {}
        for cluster_name, cluster_data in cluster_results.items():
            features[f"cluster_{cluster_name}_contribution_score"] = cluster_data.get(
                "contribution_score", 0.0
            )
            features[f"cluster_{cluster_name}_density"] = cluster_data.get("density", 0.0)
            features[f"cluster_{cluster_name}_evidence_coverage"] = cluster_data.get(
                "evidence_coverage", 0.0
            )
            features[f"cluster_{cluster_name}_present_count"] = cluster_data.get(
                "present_count", 0
            )
        return features

    def _build_density_features(self, density_data: Dict) -> Dict:
        features = {}
        features["precursor_density_raw"] = density_data.get("raw", 0.0)
        features["precursor_density_evidence_weighted"] = density_data.get(
            "evidence_weighted", 0.0
        )
        features["precursor_applicable_count"] = density_data.get(
            "applicable_precursor_count", 0
        )
        features["precursor_present_count"] = density_data.get(
            "present_precursor_count", 0
        )
        features["precursor_evidence_strength"] = density_data.get(
            "evidence_strength", 0.0
        )
        return features

    def _build_interaction_features(self, interaction_results: Dict) -> Dict:
        features = {}
        for inter_name, _, _ in PRECURSOR_INTERACTIONS:
            features[f"interaction_{inter_name}"] = interaction_results.get(
                inter_name, 0.0
            )
        return features

    def _build_tree_features(self, classification_result: Dict) -> Dict:
        features = {}
        features["unified_tree_confidence"] = classification_result.get("confidence", 0.0)
        features["unified_tree_tier"] = classification_result.get("tier", 3)
        features["unified_tree_terminal_node"] = classification_result.get(
            "terminal_node", ""
        )

        path = classification_result.get("path", [])
        for node in path:
            node_id = node.get("node_id", "")
            features[f"tree_{node_id}_confidence"] = node.get("confidence", 0.0)

        return features

    def _build_general_features(
        self, extracted_evidence: Dict, preprocessed_data: Dict
    ) -> Dict:
        features = {}
        task_types = extracted_evidence.get("task_types", [])
        if task_types:
            features["task_type"] = task_types[0]["task_type"]
        else:
            features["task_type"] = "unknown"

        hazards = extracted_evidence.get("hazards", [])
        features["hazard_count"] = len(hazards)

        controls = extracted_evidence.get("controls", {})
        control_present = len(controls.get("control_present", []))
        control_missing = len(controls.get("control_missing", []))
        control_failed = len(controls.get("control_failed", []))
        features["control_failure_present"] = 1 if control_failed > 0 else 0
        features["missing_control_present"] = 1 if control_missing > 0 else 0

        features["barrier_failure_present"] = 1 if control_failed > 0 else 0
        features["control_deviation_present"] = (
            1 if control_missing > 0 or control_failed > 0 else 0
        )

        return features

    def _build_environment_features(self, extracted_evidence: Dict) -> Dict:
        features = {}
        env = extracted_evidence.get("environment", {})
        features["environmental_change"] = 1 if env.get("weather_change") else 0

        work_changes = extracted_evidence.get("work_changes", {})
        features["unexpected_condition"] = 1 if work_changes.get("unexpected_condition") else 0
        features["work_plan_changed"] = 1 if work_changes.get("work_plan_changed") else 0
        features["task_changed"] = 1 if work_changes.get("task_changed") else 0
        features["equipment_changed"] = 1 if work_changes.get("equipment_changed") else 0
        features["procedure_changed"] = 1 if work_changes.get("procedure_changed") else 0
        features["work_sequence_changed"] = 1 if work_changes.get("work_sequence_changed") else 0
        features["reassessment_performed"] = 1 if work_changes.get("reassessment_performed") else 0
        features["reassessment_missing"] = 1 if work_changes.get("reassessment_missing") else 0

        return features

    def _build_worker_features(self, extracted_evidence: Dict) -> Dict:
        features = {}
        worker = extracted_evidence.get("worker_info", {})
        features["worker_training_known"] = 1 if worker.get("training_known") else 0
        features["worker_experience_known"] = 1 if worker.get("experience_known") else 0
        features["worker_hazard_awareness"] = 0
        features["worker_safety_engagement"] = 0
        features["supervision_present"] = 1 if worker.get("supervision") else 0
        features["communication_issue"] = 1 if worker.get("communication_issue") else 0

        return features

    def _build_missing_info_features(
        self, mapped_precursors: Dict, extracted_evidence: Dict
    ) -> Dict:
        features = {}
        features["procedure_information_missing"] = (
            1
            if mapped_precursors.get("safe_work_procedure", {}).get("status", 0) == 0
            else 0
        )
        features["pre_task_plan_information_missing"] = (
            1
            if mapped_precursors.get("pre_task_plan", {}).get("status", 0) == 0
            else 0
        )
        features["worker_experience_information_missing"] = (
            1
            if not extracted_evidence.get("worker_info", {}).get("experience_known")
            else 0
        )
        features["hazard_information_missing"] = (
            1 if not extracted_evidence.get("hazards") else 0
        )
        features["stop_work_information_missing"] = (
            1
            if mapped_precursors.get("stop_work_execution", {}).get("status", 0) == 0
            else 0
        )
        return features

    def _build_text_stats(self, preprocessed_data: Dict, extracted_evidence: Dict) -> Dict:
        features = {}
        features["report_length"] = preprocessed_data.get("report_length", 0)
        features["sentence_count"] = preprocessed_data.get("sentence_count", 0)
        relevant = sum(
            1
            for p_data in extracted_evidence.get("precursor_evidence", {}).values()
            for status in ["present", "absent"]
            for e in p_data.get(status, [])
        )
        features["relevant_sentence_count"] = relevant
        total = features["sentence_count"]
        features["relevance_ratio"] = round(relevant / total, 4) if total > 0 else 0.0
        return features

    def _build_high_energy_features(self, extracted_evidence: Dict) -> Dict:
        features = {}
        high_energy = extracted_evidence.get("high_energy", {})
        features["high_energy_present"] = 1 if high_energy.get("high_energy_present") else 0
        features["high_energy_incident"] = 1 if high_energy.get("high_energy_incident") else 0

        sources = high_energy.get("energy_sources", {})
        features["high_energy_source_count"] = len(sources)
        for cat in ("mechanical", "electrical", "hydraulic", "pneumatic", "thermal",
                     "radiation", "gravity", "chemical", "biological"):
            features[f"high_energy_{cat}"] = 1 if cat in sources else 0

        return features

    def _build_direct_control_features(self, extracted_evidence: Dict) -> Dict:
        features = {}
        dc = extracted_evidence.get("direct_control", {})
        dc_state = dc.get("state", "NOT_APPLICABLE")
        features["direct_control_present"] = 1 if dc_state == "PRESENT" else 0
        features["direct_control_failed"] = 1 if dc_state == "FAILED" else 0
        features["direct_control_missing"] = 1 if dc_state == "MISSING" else 0
        features["direct_control_confidence"] = dc.get("confidence", 0.0)
        return features

    def _build_barrier_density_features(
        self, cluster_results: Dict, density_data: Dict
    ) -> Dict:
        features = {}
        barrier_cluster = cluster_results.get("barrier", {})
        features["barrier_density"] = barrier_cluster.get("density", 0.0)
        features["barrier_evidence_coverage"] = barrier_cluster.get(
            "evidence_coverage", 0.0
        )
        features["barrier_present_count"] = barrier_cluster.get("present_count", 0)
        return features

    def _build_consistency_features(
        self,
        classification_result: Dict,
        mapped_precursors: Dict,
        extracted_evidence: Dict,
        cluster_results: Optional[Dict] = None,
    ) -> Dict:
        features = {}

        classification = classification_result.get("classification", "")
        tier = classification_result.get("tier", 3)
        high_energy = extracted_evidence.get("high_energy", {})
        he_present = high_energy.get("high_energy_present", False)

        # Hazard-consistency: consistency between tree classification and precursor density
        present_count = sum(
            1 for d in mapped_precursors.values()
            if d.get("status") == PrecursorStatus.PRESENT
        )
        if classification in ("HSIF", "PSIF"):
            features["hazard_consistency"] = 1.0 if present_count >= 3 else 0.5
        elif classification in ("LSIF", "CAPACITY"):
            features["hazard_consistency"] = 1.0 if present_count >= 2 else 0.5
        elif classification in ("LOW_SEVERITY", "NO_SIF_POTENTIAL"):
            features["hazard_consistency"] = 1.0 if present_count <= 2 else 0.5
        else:
            features["hazard_consistency"] = 0.5

        # Barrier-consistency: consistency between direct control and barrier cluster
        dc = extracted_evidence.get("direct_control", {})
        dc_state = dc.get("state", "NOT_APPLICABLE")
        barrier_cluster = cluster_results.get("barrier", {})
        barrier_density = barrier_cluster.get("density", 0.0)

        if dc_state == "MISSING" and barrier_density < 0.3:
            features["barrier_consistency"] = 1.0
        elif dc_state == "PRESENT" and barrier_density > 0.5:
            features["barrier_consistency"] = 1.0
        else:
            features["barrier_consistency"] = 0.5

        # Energy-consistency: consistency between high energy and tree path
        if tier == 1 and he_present:
            features["energy_consistency"] = 1.0
        elif tier == 3 and not he_present:
            features["energy_consistency"] = 1.0
        else:
            features["energy_consistency"] = 0.5

        # Overall consistency
        features["intra_model_consistency"] = round(
            (features["hazard_consistency"] + features["barrier_consistency"] + features["energy_consistency"]) / 3,
            4,
        )

        return features

    def _build_lsr_features(self, lsr_result: Optional[Dict]) -> Dict:
        features = {}
        if lsr_result is None:
            features["life_saving_rule_broken_count"] = 0
            features["life_saving_rule_broken"] = ""
            for rule in IOGP_LSR_RULES:
                features[f"lsr_{rule}_status"] = "NOT_APPLICABLE"
                features[f"lsr_{rule}_confidence"] = 0.0
            return features

        features["life_saving_rule_broken_count"] = lsr_result.get(
            "broken_rule_count", 0
        )
        features["life_saving_rule_broken"] = ";".join(
            lsr_result.get("broken_rules", [])
        )

        analysis = lsr_result.get("analysis", [])
        for entry in analysis:
            rule_name = entry.get("rule_name", "")
            rule_key = None
            for k, v in IOGP_LSR_RULE_LABELS.items():
                if v == rule_name:
                    rule_key = k
                    break
            if rule_key:
                features[f"lsr_{rule_key}_status"] = entry.get("status", LSRStatus.NOT_APPLICABLE)
                features[f"lsr_{rule_key}_confidence"] = entry.get("confidence", 0.0)

        for rule in IOGP_LSR_RULES:
            if f"lsr_{rule}_status" not in features:
                features[f"lsr_{rule}_status"] = "NOT_APPLICABLE"
                features[f"lsr_{rule}_confidence"] = 0.0

        return features

    def _build_sif_score_features(self, score_obj: Optional[Dict]) -> Dict:
        features = {}
        if score_obj is None:
            features["sif_score"] = 0.0
            features["sif_score_method"] = ""
            features["sif_score_weight_source"] = ""
            for comp in SIF_SCORE_COMPONENTS:
                features[f"sif_component_{comp}"] = 0.0
            return features

        features["sif_score"] = score_obj.get("value", 0.0)
        features["sif_score_method"] = score_obj.get("method", "unified_tree_classification")
        features["sif_score_weight_source"] = score_obj.get("weight_source", "")

        components = score_obj.get("components", [])
        for comp in components:
            comp_name = comp.get("name", "")
            if comp_name:
                features[f"sif_component_{comp_name}"] = comp.get("value", 0.0)

        for comp in SIF_SCORE_COMPONENTS:
            key = f"sif_component_{comp}"
            if key not in features:
                features[key] = 0.0

        return features

    def build_features(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        cluster_results: Dict,
        density_data: Dict,
        interaction_results: Dict,
        classification_result: Dict,
        score_obj: Dict,
        lsr_result: Optional[Dict] = None,
    ) -> pd.DataFrame:
        row = {}
        row["incident_id"] = incident_id
        row.update(self._build_precursor_features(mapped_precursors))
        row.update(self._build_cluster_features(cluster_results))
        row.update(self._build_density_features(density_data))
        row.update(self._build_interaction_features(interaction_results))
        row.update(self._build_tree_features(classification_result))
        row.update(self._build_general_features(extracted_evidence, preprocessed_data))
        row.update(self._build_environment_features(extracted_evidence))
        row.update(self._build_worker_features(extracted_evidence))
        row.update(self._build_high_energy_features(extracted_evidence))
        row.update(self._build_direct_control_features(extracted_evidence))
        row.update(self._build_barrier_density_features(cluster_results, density_data))
        row.update(self._build_missing_info_features(mapped_precursors, extracted_evidence))
        row.update(self._build_text_stats(preprocessed_data, extracted_evidence))
        row.update(self._build_consistency_features(
            classification_result, mapped_precursors, extracted_evidence, cluster_results
        ))
        row.update(self._build_lsr_features(lsr_result))
        row.update(self._build_sif_score_features(score_obj))
        df = pd.DataFrame([row])
        return df

    def build_raw_features(self, df_encoded: pd.DataFrame) -> pd.DataFrame:
        from .config import PRECURSOR_ENCODING
        df_raw = df_encoded.copy()
        for precursor in self.precursors:
            df_raw[precursor] = df_raw[precursor].map(PRECURSOR_ENCODING)
        return df_raw

    def validate(self, df: pd.DataFrame) -> List[str]:
        errors = []
        if len(df) == 0:
            errors.append("DataFrame is empty")
            return errors
        if len(df) != 1:
            errors.append(f"Expected 1 row, got {len(df)}")
        required_cols = set(DATAFRAME_SCHEMA.keys())
        actual_cols = set(df.columns)
        missing = required_cols - actual_cols
        extra = actual_cols - required_cols - {"incident_id"}
        if missing:
            errors.append(f"Missing columns: {missing}")
        if extra:
            errors.append(f"Unexpected columns: {extra}")
        for col in df.columns:
            if col.endswith("_confidence"):
                vals = df[col].dropna()
                if not vals.between(0.0, 1.0).all():
                    errors.append(f"Confidence column {col} has values outside [0,1]")
        for col in df.columns:
            if col.endswith("_evidence_count"):
                vals = df[col].dropna()
                if (vals < 0).any():
                    errors.append(f"Evidence count column {col} has negative values")
                if not vals.apply(lambda x: x == int(x)).all():
                    errors.append(f"Evidence count column {col} has non-integer values")
        binary_cols = [
            "environmental_change",
            "unexpected_condition",
            "work_plan_changed",
            "task_changed",
            "equipment_changed",
            "procedure_changed",
            "work_sequence_changed",
            "reassessment_performed",
            "reassessment_missing",
            "control_failure_present",
            "missing_control_present",
            "barrier_failure_present",
            "control_deviation_present",
            "worker_training_known",
            "worker_experience_known",
            "worker_hazard_awareness",
            "worker_safety_engagement",
            "supervision_present",
            "communication_issue",
            "procedure_information_missing",
            "pre_task_plan_information_missing",
            "worker_experience_information_missing",
            "hazard_information_missing",
            "stop_work_information_missing",
            "high_energy_present",
            "high_energy_incident",
            "direct_control_present",
            "direct_control_failed",
            "direct_control_missing",
        ]
        for col in binary_cols:
            if col in df.columns:
                vals = df[col].dropna()
                if not vals.isin([0, 1]).all():
                    errors.append(f"Binary column {col} has non-binary values")
        if "sif_classification" in df.columns:
            errors.append("DataFrame contains sif_classification column - data leakage risk")
        valid_lsr_statuses = {"BROKEN", "NOT_BROKEN", "UNCERTAIN", "NOT_APPLICABLE"}
        for col in df.columns:
            if col.startswith("lsr_") and col.endswith("_status"):
                vals = df[col].dropna()
                if not vals.isin(valid_lsr_statuses).all():
                    errors.append(f"LSR status column {col} has invalid values")
        broken_count_col = "life_saving_rule_broken_count"
        if broken_count_col in df.columns:
            vals = df[broken_count_col].dropna()
            if (vals < 0).any():
                errors.append(f"{broken_count_col} has negative values")
            if not vals.apply(lambda x: x == int(x)).all():
                errors.append(f"{broken_count_col} has non-integer values")
        if "sif_score" in df.columns:
            vals = df["sif_score"].dropna()
            if not vals.between(0.0, 1.0).all():
                errors.append("sif_score has values outside [0,1]")
        for col in df.columns:
            if col.startswith("sif_component_"):
                vals = df[col].dropna()
                if not vals.between(0.0, 1.0).all():
                    errors.append(f"SIF component column {col} has values outside [0,1]")
        return errors
