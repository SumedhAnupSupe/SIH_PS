"""Output generator: produces JSON assessments, text summaries, and ML DataFrames.

v3.0.0: Barrier failure rate output, unified tree, clusters, density, consistency.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .schemas import IncidentPrediction
from .config import (
    AttentionLevel,
    SystemicLevel,
    ACTION_LABELS,
    MODEL_VERSION,
)

logger = logging.getLogger(__name__)


class OutputGenerator:
    """Generates all downstream output artifacts."""

    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "assessments").mkdir(exist_ok=True)
        (self.output_dir / "summaries").mkdir(exist_ok=True)
        (self.output_dir / "features").mkdir(exist_ok=True)
        (self.output_dir / "similar_incidents").mkdir(exist_ok=True)

    def generate_assessment_json(self, prediction: IncidentPrediction) -> Path:
        out_path = self.output_dir / "assessments" / f"attention_assessment_{prediction.incident_id}.json"
        data = prediction.to_assessment_json()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Assessment JSON written: %s", out_path)
        return out_path

    def generate_summary_text(self, prediction: IncidentPrediction) -> Path:
        out_path = self.output_dir / "summaries" / f"attention_summary_{prediction.incident_id}.txt"
        text = self._render_summary(prediction)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info("Summary text written: %s", out_path)
        return out_path

    def generate_prediction_dataframe(
        self, predictions: List[IncidentPrediction]
    ) -> pd.DataFrame:
        rows = []
        for pred in predictions:
            row = {
                "incident_id": pred.incident_id,
                "risk_potential_score": pred.risk_potential_score,
                "urgency_score": pred.attention.urgency_score,
                "attention_level": pred.attention.level,
                "attention_confidence": pred.attention.confidence,
                "systemic_attention_score": pred.attention.systemic_attention_score,
                "systemic_attention_level": pred.attention.systemic_attention,
                "human_review_required": int(pred.uncertainty.human_review_required),
                "out_of_distribution": int(pred.uncertainty.out_of_distribution),
                "prediction_mode": pred.prediction_mode,
                "upstream_sif_score": pred.upstream_sif_score,
                "upstream_tree_classification": pred.upstream_tree_classification,
                "upstream_tree_tier": pred.upstream_tree_tier,
                "upstream_tree_confidence": pred.upstream_tree_confidence,
                "upstream_tree_version": pred.upstream_tree_version,
                "barrier_failure_rate": pred.barrier_failure_rate,
            }

            # Action counts
            immediate_count = sum(
                1 for a in pred.actions if a.time_horizon == "NOW"
            )
            short_term_count = sum(
                1 for a in pred.actions if a.time_horizon == "NEXT_SHIFT_OR_HOURS"
            )
            long_term_count = sum(
                1 for a in pred.actions
                if a.time_horizon in ("DAYS_TO_WEEKS", "LONGER_TERM")
            )
            row["immediate_action_count"] = immediate_count
            row["short_term_action_count"] = short_term_count
            row["long_term_action_count"] = long_term_count

            # Per-action binary flags
            action_set = {a.action for a in pred.actions}
            for action_name in ACTION_LABELS:
                col = f"action_{action_name.lower()}"
                row[col] = 1 if action_name in action_set else 0

            # Tree node answers and confidences
            for node_id, answer in pred.upstream_tree_node_answers.items():
                row[f"tree_node_{node_id}_answer"] = answer
            for node_id, conf in pred.upstream_tree_node_confidences.items():
                row[f"tree_node_{node_id}_confidence"] = float(conf)

            # Barrier failure rate components
            if pred.barrier_failure_assessment:
                bfr = pred.barrier_failure_assessment
                row["bfr_direct_control_contrib"] = bfr.direct_control_failure_contrib
                row["bfr_barrier_cluster_contrib"] = bfr.barrier_cluster_contrib
                row["bfr_ccv_contrib"] = bfr.critical_control_verification_contrib
                row["bfr_ei_contrib"] = bfr.energy_isolation_contrib
                row["bfr_stop_work_contrib"] = bfr.stop_work_contrib

            rows.append(row)

        df = pd.DataFrame(rows)
        return df

    def save_prediction_dataframe(
        self, predictions: List[IncidentPrediction], version: str = MODEL_VERSION
    ) -> Path:
        df = self.generate_prediction_dataframe(predictions)
        out_path = self.output_dir / "features" / f"attention_features_v{version}.csv"
        df.to_csv(out_path, index=False)
        logger.info("Prediction DataFrame written: %s (%d rows)", out_path, len(df))
        return out_path

    def generate_dashboard_data(
        self, predictions: List[IncidentPrediction]
    ) -> Dict[str, Any]:
        total = len(predictions)
        if total == 0:
            return {}

        attention_counts = {level.value: 0 for level in AttentionLevel}
        systemic_counts = {level.value: 0 for level in SystemicLevel}
        action_counts: Dict[str, int] = {}
        driver_counts: Dict[str, int] = {}
        human_review_count = 0
        ood_count = 0
        barrier_rates = []

        for pred in predictions:
            attention_counts[pred.attention.level] = attention_counts.get(pred.attention.level, 0) + 1
            systemic_counts[pred.attention.systemic_attention] = systemic_counts.get(pred.attention.systemic_attention, 0) + 1

            for action in pred.actions:
                action_counts[action.action] = action_counts.get(action.action, 0) + 1

            for driver in pred.drivers:
                driver_counts[driver.feature] = driver_counts.get(driver.feature, 0) + 1

            if pred.uncertainty.human_review_required:
                human_review_count += 1
            if pred.uncertainty.out_of_distribution:
                ood_count += 1

            barrier_rates.append(pred.barrier_failure_rate)

        dashboard = {
            "total_incidents": total,
            "attention_distribution": attention_counts,
            "systemic_distribution": systemic_counts,
            "human_review_required_count": human_review_count,
            "out_of_distribution_count": ood_count,
            "top_actions": dict(sorted(action_counts.items(), key=lambda x: -x[1])[:10]),
            "top_drivers": dict(sorted(driver_counts.items(), key=lambda x: -x[1])[:10]),
            "average_urgency_score": float(
                sum(p.attention.urgency_score for p in predictions) / total
            ),
            "average_risk_potential": float(
                sum(p.risk_potential_score for p in predictions) / total
            ),
            "average_barrier_failure_rate": float(sum(barrier_rates) / total),
            "high_barrier_failure_count": sum(1 for r in barrier_rates if r >= 0.5),
        }

        dash_path = self.output_dir / "dashboard" / "attention_dashboard.json"
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "dashboard").mkdir(exist_ok=True)
        with open(dash_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2)

        return dashboard

    def save_similar_incidents(
        self, predictions: List[IncidentPrediction]
    ) -> Path:
        data = {}
        for pred in predictions:
            if pred.similar_incidents:
                data[pred.incident_id] = [
                    si.model_dump() for si in pred.similar_incidents
                ]

        out_path = self.output_dir / "similar_incidents" / "similar_incidents.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return out_path

    def _render_summary(self, pred: IncidentPrediction) -> str:
        lines = [
            "SIF ATTENTION ASSESSMENT (v3.0.0)",
            "=" * 50,
            "",
            f"Incident: {pred.incident_id}",
            f"Prediction Mode: {pred.prediction_mode}",
            "",
            f"Attention: {pred.attention.level}",
            f"Urgency Score: {pred.attention.urgency_score:.2f}",
            f"Risk Potential Score: {pred.risk_potential_score:.2f}",
            f"Systemic Attention: {pred.attention.systemic_attention}",
            f"Systemic Attention Score: {pred.attention.systemic_attention_score:.2f}",
            "",
        ]

        # Barrier failure rate
        lines.append("Barrier Failure Rate:")
        lines.append("-" * 30)
        lines.append(f"  Rate: {pred.barrier_failure_rate:.3f}")
        if pred.barrier_failure_assessment:
            bfr = pred.barrier_failure_assessment
            lines.append(f"  Direct Control Failure: {bfr.direct_control_failure_contrib:.3f}")
            lines.append(f"  Barrier Cluster: {bfr.barrier_cluster_contrib:.3f}")
            lines.append(f"  Critical Control Verification: {bfr.critical_control_verification_contrib:.3f}")
            lines.append(f"  Energy Isolation: {bfr.energy_isolation_contrib:.3f}")
            lines.append(f"  Stop Work Absence: {bfr.stop_work_contrib:.3f}")
        lines.append("")

        # Upstream unified tree info
        if pred.upstream_tree_classification:
            lines.append("Upstream Unified Classification Tree:")
            lines.append("-" * 30)
            lines.append(f"  Classification: {pred.upstream_tree_classification}")
            lines.append(f"  Tier: {pred.upstream_tree_tier}")
            lines.append(f"  Confidence: {pred.upstream_tree_confidence:.2f}")
            if pred.upstream_tree_version:
                lines.append(f"  Version: {pred.upstream_tree_version}")
            if pred.upstream_tree_node_answers:
                lines.append("  Decisive Path:")
                for node_id, answer in pred.upstream_tree_node_answers.items():
                    conf = pred.upstream_tree_node_confidences.get(node_id, "")
                    conf_str = f" (conf={conf:.2f})" if isinstance(conf, (int, float)) else ""
                    lines.append(f"    {node_id}: {answer}{conf_str}")
            lines.append("")

        # Key drivers
        if pred.drivers:
            lines.append("Key Drivers:")
            lines.append("-" * 30)
            for driver in pred.drivers[:8]:
                role_label = {"observed": "Evidence", "rule_signal": "Rule", "model_derived": "Model"}.get(driver.role, driver.role)
                lines.append(f"  [{role_label}] {driver.feature}: {driver.value}")
            lines.append("")

        # Actions by time horizon
        immediate_actions = [a for a in pred.actions if a.time_horizon == "NOW"]
        short_term_actions = [a for a in pred.actions if a.time_horizon == "NEXT_SHIFT_OR_HOURS"]
        long_term_actions = [
            a for a in pred.actions
            if a.time_horizon in ("DAYS_TO_WEEKS", "LONGER_TERM")
        ]
        monitor_actions = [a for a in pred.actions if a.time_horizon == "MONITOR"]

        if immediate_actions:
            lines.append("Immediate Actions:")
            lines.append("-" * 30)
            for i, action in enumerate(immediate_actions, 1):
                lines.append(f"  {i}. {action.action}")
                lines.append(f"     Reason: {action.reason}")
            lines.append("")

        if short_term_actions:
            lines.append("Short-Term Actions:")
            lines.append("-" * 30)
            for i, action in enumerate(short_term_actions, 1):
                lines.append(f"  {i}. {action.action}")
                lines.append(f"     Reason: {action.reason}")
            lines.append("")

        if long_term_actions:
            lines.append("Long-Term Actions:")
            lines.append("-" * 30)
            for i, action in enumerate(long_term_actions, 1):
                lines.append(f"  {i}. {action.action}")
                lines.append(f"     Reason: {action.reason}")
            lines.append("")

        if monitor_actions:
            lines.append("Monitor:")
            lines.append("-" * 30)
            for action in monitor_actions:
                lines.append(f"  - {action.action}")
            lines.append("")

        # Evidence
        if pred.evidence:
            lines.append("Evidence:")
            lines.append("-" * 30)
            for ev in pred.evidence[:5]:
                sid = f"Sentence {ev.source_sentence_id}" if ev.source_sentence_id is not None else "Unknown"
                lines.append(f"  [{sid}] {ev.text[:120]}...")
            lines.append("")

        # Uncertainty
        lines.append("Uncertainty:")
        lines.append("-" * 30)
        if pred.uncertainty.missing_information:
            lines.append(f"  Missing information: {', '.join(pred.uncertainty.missing_information)}")
        if pred.uncertainty.contradictions:
            lines.append(f"  Contradictions: {', '.join(pred.uncertainty.contradictions)}")
        if pred.uncertainty.out_of_distribution:
            lines.append("  WARNING: Incident is out-of-distribution")
        lines.append(f"  Human review: {'RECOMMENDED' if pred.uncertainty.human_review_required else 'Not required'}")
        lines.append("")

        # Model metadata
        lines.append("Model Metadata:")
        lines.append("-" * 30)
        lines.append(f"  Urgency Model: {pred.model_metadata.urgency_model_version or 'N/A (rule-based)'}")
        lines.append(f"  Action Model: {pred.model_metadata.action_model_version or 'N/A (rule-based)'}")
        lines.append(f"  Rule Engine: {pred.model_metadata.rule_engine_version}")
        lines.append(f"  Model Version: {MODEL_VERSION}")

        return "\n".join(lines)
