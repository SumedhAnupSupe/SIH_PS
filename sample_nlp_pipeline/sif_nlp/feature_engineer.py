"""Feature engineering module - builds ML-ready DataFrame from evidence."""

import pandas as pd
from typing import Dict, List

from .config import SIF_PRECURSORS, DATAFRAME_SCHEMA


class FeatureEngineer:
    """Generates structured features from mapped precursor evidence."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS

    def _build_precursor_features(self, mapped_precursors: Dict) -> Dict:
        features = {}
        for precursor in self.precursors:
            data = mapped_precursors.get(precursor, {})
            features[precursor] = data.get("status", 0)
            features[f"{precursor}_confidence"] = data.get("confidence", 0.0)
            features[f"{precursor}_evidence_count"] = data.get("evidence_count", 0)
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

    def build_features(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
    ) -> pd.DataFrame:
        row = {}
        row["incident_id"] = incident_id
        row.update(self._build_precursor_features(mapped_precursors))
        row.update(self._build_general_features(extracted_evidence, preprocessed_data))
        row.update(self._build_environment_features(extracted_evidence))
        row.update(self._build_worker_features(extracted_evidence))
        row.update(self._build_missing_info_features(mapped_precursors, extracted_evidence))
        row.update(self._build_text_stats(preprocessed_data, extracted_evidence))
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
        ]
        for col in binary_cols:
            if col in df.columns:
                vals = df[col].dropna()
                if not vals.isin([0, 1]).all():
                    errors.append(f"Binary column {col} has non-binary values")
        if "sif_classification" in df.columns:
            errors.append("DataFrame contains sif_classification column - data leakage risk")
        return errors
