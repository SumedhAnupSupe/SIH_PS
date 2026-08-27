"""Feature engineering for the downstream attention model.

v3.0.0: Unified SIF Classification Tree with 22 precursors, clusters,
density, high-energy, direct control, barrier density, and consistency.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .config import (
    PRECURSOR_NAMES,
    PRECURSOR_CLUSTERS,
    PRECURSOR_STATUS_COLS,
    PRECURSOR_CONFIDENCE_COLS,
    PRECURSOR_EVIDENCE_COLS,
    PRECURSOR_EVIDENCE_STRENGTH_COLS,
    WORK_CHANGE_COLS,
    WORKER_COLS,
    CONTROL_COLS,
    MISSING_INFO_COLS,
    TEXT_STAT_COLS,
    HIGH_ENERGY_COLS,
    DIRECT_CONTROL_COLS,
    DENSITY_COLS,
    CLUSTER_COLS,
    CONSISTENCY_COLS,
    LSR_RULES,
    INTERACTION_FEATURES,
)

logger = logging.getLogger(__name__)


class AttentionFeatureEngineer:
    """Builds derived features from the upstream representation."""

    HIGH_ENERGY_HAZARD_KEYWORDS = [
        "electrical_hazard",
        "fall_hazard",
        "stored_energy_hazard",
    ]

    def build_features(self, feature_row: Dict[str, Any]) -> Dict[str, float]:
        features: Dict[str, float] = {}

        # Pass-through upstream features
        pass_through_cols = (
            PRECURSOR_STATUS_COLS
            + PRECURSOR_CONFIDENCE_COLS
            + PRECURSOR_EVIDENCE_COLS
            + WORK_CHANGE_COLS
            + WORKER_COLS
            + CONTROL_COLS
            + MISSING_INFO_COLS
            + TEXT_STAT_COLS
        )
        for col in pass_through_cols:
            val = feature_row.get(col, 0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # Evidence strength columns
        for col in PRECURSOR_EVIDENCE_STRENGTH_COLS:
            val = feature_row.get(col, 0.0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # High-energy features
        for col in HIGH_ENERGY_COLS:
            val = feature_row.get(col, 0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # Direct control features
        for col in DIRECT_CONTROL_COLS:
            val = feature_row.get(col, 0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # Density features
        for col in DENSITY_COLS:
            val = feature_row.get(col, 0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # Cluster features
        for col in CLUSTER_COLS:
            val = feature_row.get(col, 0)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # Consistency features
        for col in CONSISTENCY_COLS:
            val = feature_row.get(col, 0.5)
            features[col] = float(val) if not isinstance(val, (int, float)) else val

        # task_type hash
        task_type = feature_row.get("task_type", "unknown")
        features["task_type_hash"] = float(hash(str(task_type)) % 1000) / 1000.0
        features["hazard_count"] = float(feature_row.get("hazard_count", 0))

        # LSR features
        features["broken_lsr_count"] = float(feature_row.get("life_saving_rule_broken_count", 0))
        features["broken_lsr_count_positive"] = 1.0 if features["broken_lsr_count"] > 0 else 0.0
        for rule in LSR_RULES:
            status_col = f"lsr_{rule}_status"
            conf_col = f"lsr_{rule}_confidence"
            status = str(feature_row.get(status_col, "NOT_APPLICABLE"))
            conf = float(feature_row.get(conf_col, 0.0))
            features[f"lsr_{rule}_broken"] = 1.0 if status == "BROKEN" else 0.0
            features[f"lsr_{rule}_uncertain"] = 1.0 if status == "UNCERTAIN" else 0.0
            features[f"lsr_{rule}_confidence"] = conf

        # Unified classification tree features
        tree_classification = str(feature_row.get("unified_tree_classification", ""))
        tree_confidence = float(feature_row.get("unified_tree_confidence", 0.0))

        features["tree_classification_hsif"] = 1.0 if tree_classification == "HSIF" else 0.0
        features["tree_classification_psif"] = 1.0 if tree_classification == "PSIF" else 0.0
        features["tree_classification_lsif"] = 1.0 if tree_classification == "LSIF" else 0.0
        features["tree_classification_capacity"] = 1.0 if tree_classification == "CAPACITY" else 0.0
        features["tree_classification_exposure"] = 1.0 if tree_classification == "EXPOSURE" else 0.0
        features["tree_classification_low_severity"] = 1.0 if tree_classification == "LOW_SEVERITY" else 0.0
        features["tree_classification_actual_sif"] = 1.0 if "ACTUAL_SIF" in tree_classification else 0.0
        features["tree_confidence"] = tree_confidence

        tree_tier = int(feature_row.get("unified_tree_tier", 3))
        features["tree_tier"] = float(tree_tier)
        features["tree_tier_1"] = 1.0 if tree_tier == 1 else 0.0
        features["tree_tier_2"] = 1.0 if tree_tier == 2 else 0.0
        features["tree_tier_3"] = 1.0 if tree_tier == 3 else 0.0

        # Tree node confidences
        for node_id in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]:
            conf = float(feature_row.get(f"tree_{node_id}_confidence", 0.0))
            features[f"tree_{node_id}_confidence"] = conf
            features[f"tree_{node_id}_high"] = 1.0 if conf > 0.8 else 0.0

        # SIF score features
        sif_score = float(feature_row.get("sif_score", 0.0))
        features["upstream_sif_score"] = sif_score

        # Derived aggregate features
        present_count = 0
        ambiguous_count = 0
        high_conf_present_count = 0
        not_mentioned_count = 0
        not_applicable_count = 0

        for name in PRECURSOR_NAMES:
            status = int(feature_row.get(name, 0))
            conf = float(feature_row.get(f"{name}_confidence", 0.0))
            if status == 3:
                present_count += 1
                if conf >= 0.7:
                    high_conf_present_count += 1
            elif status == 2:
                ambiguous_count += 1
            elif status == 0:
                not_mentioned_count += 1
            elif status == -1:
                not_applicable_count += 1

        features["present_precursor_count"] = float(present_count)
        features["ambiguous_precursor_count"] = float(ambiguous_count)
        features["not_mentioned_precursor_count"] = float(not_mentioned_count)
        features["not_applicable_precursor_count"] = float(not_applicable_count)
        features["high_confidence_present_precursor_count"] = float(high_conf_present_count)

        # Evidence quality
        confidences = [
            float(feature_row.get(f"{name}_confidence", 0.0))
            for name in PRECURSOR_NAMES
            if int(feature_row.get(name, 0)) != 0
        ]
        features["mean_precursor_confidence"] = float(np.mean(confidences)) if confidences else 0.0
        features["min_precursor_confidence"] = float(np.min(confidences)) if confidences else 0.0

        evidence_counts = [
            int(feature_row.get(f"{name}_evidence_count", 0))
            for name in PRECURSOR_NAMES
        ]
        features["total_evidence_count"] = float(sum(evidence_counts))

        features["evidence_strength"] = (
            features["relevant_sentence_count"] / max(features["sentence_count"], 1.0)
        )

        # Control failure density
        total_controls_mentioned = (
            features.get("control_failure_present", 0)
            + features.get("missing_control_present", 0)
            + features.get("barrier_failure_present", 0)
            + features.get("control_deviation_present", 0)
        )
        features["control_failure_density"] = float(total_controls_mentioned)

        # Work-change density
        work_change_count = sum(
            1 for col in WORK_CHANGE_COLS
            if col not in ("reassessment_performed", "reassessment_missing")
            and features.get(col, 0) > 0
        )
        features["work_change_density"] = float(work_change_count)

        # Missing information count
        missing_count = sum(
            1 for col in MISSING_INFO_COLS if features.get(col, 0) > 0
        )
        features["missing_information_count"] = float(missing_count)

        # Reassessment gap
        work_changed = any(
            features.get(col, 0) > 0
            for col in ["work_plan_changed", "task_changed", "equipment_changed",
                        "procedure_changed", "work_sequence_changed", "unexpected_condition"]
        )
        features["reassessment_gap"] = 1.0 if (work_changed and features.get("reassessment_missing", 0) > 0) else 0.0

        # High-energy hazard indicator
        high_energy = 0
        for col in self.HIGH_ENERGY_HAZARD_KEYWORDS:
            hazard_count = features.get("hazard_count", 0)
            if hazard_count > 0:
                high_energy += 1
        features["high_energy_hazard_present"] = float(min(high_energy, 1))

        # Specific precursor binary flags
        features["productivity_pressure_present"] = 1.0 if features.get("productivity_pressure", 0) == 3 else 0.0
        features["risk_normalization_present"] = 1.0 if features.get("risk_normalization", 0) == 3 else 0.0
        features["departure_from_routine_present"] = 1.0 if features.get("departure_from_routine", 0) == 3 else 0.0
        features["stop_work_ambiguous"] = 1.0 if features.get("stop_work_execution", 0) == 2 else 0.0
        features["work_continued_signal"] = 1.0 if (
            features.get("stop_work_ambiguous", 0) > 0
            and features.get("reassessment_missing", 0) > 0
        ) else 0.0

        # Cluster aggregate features
        for cluster_name, cluster_precursors in PRECURSOR_CLUSTERS.items():
            cluster_present = sum(
                1 for p in cluster_precursors if int(feature_row.get(p, 0)) == 3
            )
            cluster_applicable = sum(
                1 for p in cluster_precursors if int(feature_row.get(p, 0)) != -1
            )
            features[f"cluster_{cluster_name}_present_count"] = float(cluster_present)
            features[f"cluster_{cluster_name}_density"] = (
                float(cluster_present / cluster_applicable) if cluster_applicable > 0 else 0.0
            )

        # Barrier density (shortcut from upstream)
        barrier_density = float(feature_row.get("barrier_density", 0.0))
        features["barrier_density"] = barrier_density
        features["barrier_evidence_coverage"] = float(feature_row.get("barrier_evidence_coverage", 0.0))
        features["barrier_present_count"] = float(feature_row.get("barrier_present_count", 0))

        # Density features (shortcut)
        features["precursor_density_raw"] = float(feature_row.get("precursor_density_raw", 0.0))
        features["precursor_density_evidence_weighted"] = float(feature_row.get("precursor_density_evidence_weighted", 0.0))

        # Consistency features (shortcut)
        features["hazard_consistency"] = float(feature_row.get("hazard_consistency", 0.5))
        features["barrier_consistency"] = float(feature_row.get("barrier_consistency", 0.5))
        features["energy_consistency"] = float(feature_row.get("energy_consistency", 0.5))
        features["intra_model_consistency"] = float(feature_row.get("intra_model_consistency", 0.5))

        # Interaction features
        for inter in INTERACTION_FEATURES:
            left_val = features.get(inter.left, 0.0)
            right_val = features.get(inter.right, 0.0)
            features[inter.name] = left_val * right_val

        features["sif_score_feature"] = sif_score

        # Tree-based interaction features
        features["tree_hsif_x_high_energy"] = (
            features.get("tree_classification_hsif", 0.0)
            * features.get("high_energy_hazard_present", 0.0)
        )
        features["tree_hsif_x_control_failure"] = (
            features.get("tree_classification_hsif", 0.0)
            * features.get("control_failure_present", 0.0)
        )
        features["density_x_high_energy"] = (
            features.get("precursor_density_evidence_weighted", 0.0)
            * features.get("high_energy_present", 0.0)
        )
        features["barrier_x_direct_control"] = (
            features.get("barrier_density", 0.0)
            * features.get("direct_control_failed", 0.0)
        )

        return features

    def build_dataframe(self, inputs: List) -> pd.DataFrame:
        rows = []
        for inp in inputs:
            feats = self.build_features(inp.feature_row)
            feats["incident_id"] = inp.incident_id
            rows.append(feats)
        df = pd.DataFrame(rows)
        cols = ["incident_id"] + [c for c in df.columns if c != "incident_id"]
        return df[cols]

    def get_feature_names(self) -> List[str]:
        sample_row = {}
        for name in PRECURSOR_NAMES:
            sample_row[name] = 0
            sample_row[f"{name}_confidence"] = 0.0
            sample_row[f"{name}_evidence_count"] = 0
            sample_row[f"{name}_evidence_strength"] = 0.0
        for col in WORK_CHANGE_COLS + WORKER_COLS + CONTROL_COLS + MISSING_INFO_COLS + TEXT_STAT_COLS + HIGH_ENERGY_COLS + DIRECT_CONTROL_COLS + DENSITY_COLS + CLUSTER_COLS + CONSISTENCY_COLS:
            sample_row[col] = 0
        sample_row["task_type"] = "unknown"
        sample_row["hazard_count"] = 0
        for rule in LSR_RULES:
            sample_row[f"lsr_{rule}_status"] = "NOT_APPLICABLE"
            sample_row[f"lsr_{rule}_confidence"] = 0.0
        sample_row["life_saving_rule_broken_count"] = 0
        sample_row["sif_score"] = 0.0
        sample_row["unified_tree_confidence"] = 0.0
        sample_row["unified_tree_tier"] = 3
        for node_id in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]:
            sample_row[f"tree_{node_id}_confidence"] = 0.0
        sample_row["barrier_density"] = 0.0

        features = self.build_features(sample_row)
        return list(features.keys())
