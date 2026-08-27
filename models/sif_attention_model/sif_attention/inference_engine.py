"""Inference engine: combines rule engine + ML models + calibration + OOD detection.

v3.0.0: Barrier assessment integration, unified tree, 22 precursors, clusters,
density, high-energy, direct control, and consistency.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import (
    AttentionLevel,
    SystemicLevel,
    ActionTimeHorizon,
    ACTION_LABELS,
    ACTION_COLUMNS,
    URGENCY_ORDER,
    URGENCY_DECODE,
    SYSTEMIC_ORDER,
    SYSTEMIC_DECODE,
    MODEL_VERSION,
    RULE_ENGINE_VERSION,
    UPSTREAM_PIPELINE_VERSION,
    FEATURE_SCHEMA_VERSION,
    OODConfig,
)
from .schemas import (
    AttentionAssessment,
    ActionRecommendation,
    IncidentPrediction,
    DriverItem,
    EvidenceItem,
    UncertaintyInfo,
    ModelMetadata,
    SimilarIncident,
    ReportAnalysis,
    BarrierFailureAssessment,
)
from .rule_engine import RuleEngine
from .barrier_assessment import BarrierAssessment
from .trainer import AttentionModelTrainer
from .feature_engineer import AttentionFeatureEngineer

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Produces final predictions by combining all system components."""

    def __init__(
        self,
        trainer: Optional[AttentionModelTrainer] = None,
        rule_engine: Optional[RuleEngine] = None,
        feature_engineer: Optional[AttentionFeatureEngineer] = None,
        barrier_assessor: Optional[BarrierAssessment] = None,
        ood_config: Optional[OODConfig] = None,
    ):
        self.trainer = trainer
        self.rule_engine = rule_engine or RuleEngine()
        self.feature_engineer = feature_engineer or AttentionFeatureEngineer()
        self.barrier_assessor = barrier_assessor or BarrierAssessment()
        self.ood_config = ood_config or OODConfig()
        self.prediction_mode = "RULE_BASED_COLD_START"

        self._ood_reference: Optional[np.ndarray] = None
        self._ood_kneighbors = None

    def set_ml_models(self, trainer: AttentionModelTrainer) -> None:
        self.trainer = trainer
        self.prediction_mode = "HYBRID_ML"

    def fit_ood_reference(self, X_reference: np.ndarray) -> None:
        if not self.ood_config.enabled:
            return
        self._ood_reference = X_reference
        try:
            from sklearn.neighbors import NearestNeighbors
            self._ood_kneighbors = NearestNeighbors(
                n_neighbors=min(self.ood_config.n_neighbors, len(X_reference)),
                metric="euclidean",
            )
            self._ood_kneighbors.fit(X_reference)
        except Exception as e:
            logger.warning("OOD reference fitting failed: %s", e)

    def _detect_ood(self, x: np.ndarray) -> Tuple[bool, float]:
        if not self.ood_config.enabled or self._ood_kneighbors is None:
            return False, 0.0

        x_reshaped = x.reshape(1, -1)
        distances, _ = self._ood_kneighbors.kneighbors(x_reshaped)
        mean_dist = float(np.mean(distances[0]))

        if self._ood_reference is not None and len(self._ood_reference) > 10:
            ref_distances, _ = self._ood_kneighbors.kneighbors(self._ood_reference)
            ref_mean_dists = np.mean(ref_distances, axis=1)
            threshold = np.percentile(ref_mean_dists, self.ood_config.distance_threshold_percentile)
            is_ood = mean_dist > threshold
        else:
            is_ood = mean_dist > 3.0

        return is_ood, mean_dist

    def predict_single(
        self,
        features: Dict[str, float],
        feature_vector: np.ndarray,
        incident_id: str,
        analysis: Optional[ReportAnalysis] = None,
        summary_text: str = "",
        similar_incidents: Optional[List[Dict[str, Any]]] = None,
    ) -> IncidentPrediction:

        # Step 1: Rule engine
        rule_result = self.rule_engine.aggregate_signals(
            self.rule_engine.evaluate(features)
        )

        # Step 2: ML predictions (if available)
        ml_attention = AttentionLevel.MONITOR.value
        ml_urgency_score = 0.0
        ml_urgency_proba = np.zeros(4)
        ml_actions_binary = np.zeros(len(ACTION_LABELS), dtype=int)
        ml_actions_proba: Dict[str, float] = {}
        ml_systemic = SystemicLevel.NONE.value
        ml_systemic_proba = np.zeros(4)

        if self.prediction_mode == "HYBRID_ML" and self.trainer is not None:
            try:
                x = feature_vector.reshape(1, -1)
                urg_pred, urg_proba = self.trainer.urgency_trainer.predict(x)
                ml_attention = urg_pred[0]
                ml_urgency_proba = urg_proba[0]
                ml_urgency_score = float(np.max(ml_urg_proba))

                act_binary, act_proba = self.trainer.action_trainer.predict(x)
                ml_actions_binary = act_binary[0]
                for action_name, proba_arr in act_proba.items():
                    ml_actions_proba[action_name] = float(proba_arr[0])

                sys_pred, sys_proba = self.trainer.systemic_trainer.predict(x)
                ml_systemic = sys_pred[0]
                ml_systemic_proba = sys_proba[0]
            except Exception as e:
                logger.warning("ML prediction failed for %s: %s", incident_id, e)

        # Step 3: Safety override
        final_attention, final_urgency_score, override_applied = self.rule_engine.apply_safety_override(
            ml_attention, ml_urgency_score, rule_result,
        )

        # Step 4: Combine rule and ML actions
        rule_actions = set(rule_result.get("rule_actions", []))
        ml_action_set = set()
        for i, action_name in enumerate(ACTION_LABELS):
            if ml_actions_binary[i] > 0:
                ml_action_set.add(action_name)

        combined_actions = rule_actions | ml_action_set

        # Step 5: Systemic attention
        rule_systemic = rule_result.get("rule_systemic", SystemicLevel.NONE.value)
        final_systemic = self._combine_systemic(ml_systemic, rule_systemic)
        systemic_score = self._systemic_to_score(final_systemic, ml_systemic_proba)

        # Step 6: OOD detection
        is_ood, ood_distance = self._detect_ood(feature_vector)

        # Step 7: Uncertainty / human review
        uncertainty = self._assess_uncertainty(
            features, ml_urgency_proba, final_attention, override_applied, is_ood
        )

        # Step 8: Barrier assessment
        barrier_result = self.barrier_assessor.compute(features)
        barrier_assessment = BarrierFailureAssessment(**barrier_result)

        # Step 9: Build drivers
        drivers = self._build_drivers(features, ml_urgency_proba, rule_result)

        # Step 10: Build evidence
        evidence = self._build_evidence(analysis)

        # Step 11: Build action recommendations
        actions = self._build_action_recommendations(
            combined_actions, features, evidence, analysis
        )

        # Step 12: Risk potential score and tree info
        risk_score = features.get("upstream_sif_score", features.get("sif_score_feature", 0.0))
        tree_classification = ""
        tree_tier = 3
        tree_confidence = 0.0
        tree_node_answers: Dict[str, str] = {}
        tree_node_confidences: Dict[str, float] = {}
        if analysis and analysis.unified_tree:
            tree_classification = analysis.unified_tree.classification
            tree_tier = analysis.unified_tree.tier
            tree_confidence = analysis.unified_tree.confidence
            for node in analysis.unified_tree.path:
                tree_node_answers[node.node_id] = node.answer
                tree_node_confidences[node.node_id] = node.confidence

        tree_version = ""
        if analysis and analysis.unified_tree:
            tree_version = analysis.unified_tree.tree_version

        # Step 13: Assemble prediction
        prediction = IncidentPrediction(
            incident_id=incident_id,
            prediction_mode=self.prediction_mode,
            risk_potential_score=float(risk_score),
            risk_potential_source="upstream_sif_score",
            attention=AttentionAssessment(
                level=final_attention,
                urgency_score=final_urgency_score,
                confidence=float(np.max(ml_urgency_proba)) if np.any(ml_urgency_proba > 0) else 0.5,
                systemic_attention=final_systemic,
                systemic_attention_score=systemic_score,
            ),
            actions=actions,
            drivers=drivers,
            evidence=evidence,
            similar_incidents=[
                SimilarIncident(**si) for si in (similar_incidents or [])
            ],
            uncertainty=uncertainty,
            model_metadata=ModelMetadata(
                upstream_pipeline_version=UPSTREAM_PIPELINE_VERSION,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                urgency_model_version=f"{MODEL_VERSION}_{self.trainer.urgency_trainer.best_model_name}" if self.trainer and self.trainer.urgency_trainer.best_model else "",
                action_model_version=f"{MODEL_VERSION}_ovr" if self.trainer and self.trainer.action_trainer.models else "",
                rule_engine_version=RULE_ENGINE_VERSION,
                prediction_mode=self.prediction_mode,
            ),
            action_flags={
                f"action_{a.lower()}": int(ml_actions_binary[ACTION_LABELS.index(a)])
                for a in ACTION_LABELS
                if a in ml_actions_proba or a in rule_actions
            },
            upstream_sif_score=float(risk_score),
            upstream_tree_classification=tree_classification,
            upstream_tree_tier=tree_tier,
            upstream_tree_confidence=tree_confidence,
            upstream_tree_version=tree_version,
            upstream_tree_node_answers=tree_node_answers,
            upstream_tree_node_confidences=tree_node_confidences,
            barrier_failure_rate=barrier_result["failure_rate"],
            barrier_failure_assessment=barrier_assessment,
        )

        return prediction

    def predict_batch(
        self, inputs: List, feature_df: "pd.DataFrame"
    ) -> List[IncidentPrediction]:
        predictions = []
        for inp in inputs:
            features = self.feature_engineer.build_features(inp.feature_row)

            feature_cols = [c for c in feature_df.columns if c != "incident_id"]
            row = feature_df[feature_df["incident_id"] == inp.incident_id]
            if row.empty:
                logger.warning("Incident %s not found in feature DataFrame", inp.incident_id)
                continue
            feature_vector = row[feature_cols].iloc[0].values.astype(float)

            pred = self.predict_single(
                features=features,
                feature_vector=feature_vector,
                incident_id=inp.incident_id,
                analysis=inp.analysis_json,
                summary_text=inp.summary_text,
            )
            predictions.append(pred)

        return predictions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _combine_systemic(self, ml_systemic: str, rule_systemic: str) -> str:
        ml_rank = SYSTEMIC_ORDER.get(ml_systemic, 0)
        rule_rank = SYSTEMIC_ORDER.get(rule_systemic, 0)
        max_rank = max(ml_rank, rule_rank)
        return SYSTEMIC_DECODE.get(max_rank, SystemicLevel.NONE.value)

    def _systemic_to_score(self, level: str, proba: np.ndarray) -> float:
        level_rank = SYSTEMIC_ORDER.get(level, 0)
        base = level_rank / 3.0
        if np.any(proba > 0):
            weighted = float(np.dot(proba, np.arange(4)) / 3.0)
            return (base + weighted) / 2.0
        return base

    def _assess_uncertainty(
        self,
        features: Dict[str, float],
        urgency_proba: np.ndarray,
        final_attention: str,
        override_applied: bool,
        is_ood: bool,
    ) -> UncertaintyInfo:
        missing_info = []
        for col in [
            "procedure_information_missing", "pre_task_plan_information_missing",
            "worker_experience_information_missing", "hazard_information_missing",
            "stop_work_information_missing",
        ]:
            if features.get(col, 0) > 0:
                missing_info.append(col.replace("_information_missing", "").replace("_", " "))

        contradictions = []
        if int(features.get("stop_work_execution", 0)) == 2:
            contradictions.append("Stop-work execution ambiguous")
        if int(features.get("plan_to_address_work_change", 0)) == 2:
            contradictions.append("Plan to address work change ambiguous")

        consistency = features.get("intra_model_consistency", 0.5)
        if consistency < 0.3:
            contradictions.append("Low model consistency between tree and precursors")

        max_proba = float(np.max(urgency_proba)) if np.any(urgency_proba > 0) else 0.0
        near_boundary = max_proba < 0.45 and max_proba > 0.0

        human_review = (
            is_ood
            or near_boundary
            or override_applied
            or len(contradictions) > 1
            or len(missing_info) >= 3
        )

        return UncertaintyInfo(
            missing_information=missing_info,
            contradictions=contradictions,
            out_of_distribution=is_ood,
            human_review_required=human_review,
        )

    def _build_drivers(
        self,
        features: Dict[str, float],
        urgency_proba: np.ndarray,
        rule_result: Dict[str, Any],
    ) -> List[DriverItem]:
        drivers = []

        # Rule-based drivers
        for sig in rule_result.get("signals", []):
            drivers.append(DriverItem(
                feature=sig["rule_id"],
                value=sig["description"],
                role="rule_signal",
                importance=0.5,
            ))

        # Top upstream features
        high_impact_features = [
            ("control_failure_present", "Control failure detected"),
            ("missing_control_present", "Missing control detected"),
            ("barrier_failure_present", "Barrier failure detected"),
            ("reassessment_missing", "Reassessment missing"),
            ("productivity_pressure", "Productivity pressure present"),
            ("risk_normalization", "Risk normalization present"),
            ("departure_from_routine", "Departure from routine"),
            ("stop_work_execution", "Stop-work not exercised"),
            ("broken_lsr_count", "Life-Saving Rule(s) broken"),
            ("tree_confidence", "Classification tree confidence"),
            ("barrier_density", "Barrier degradation density"),
            ("high_energy_present", "High-energy source present"),
            ("direct_control_failed", "Direct control failed"),
            ("direct_control_missing", "Direct control missing"),
        ]

        for feat_name, description in high_impact_features:
            val = features.get(feat_name, 0)
            if val > 0:
                if feat_name in [
                    "productivity_pressure", "risk_normalization",
                    "departure_from_routine", "stop_work_execution",
                ]:
                    display_val = {0: "NOT_MENTIONED", 1: "ABSENT", 2: "AMBIGUOUS", 3: "PRESENT"}.get(int(val), str(val))
                else:
                    display_val = val

                drivers.append(DriverItem(
                    feature=feat_name,
                    value=display_val,
                    role="observed",
                    importance=0.3 if val == 3 else 0.15,
                ))

        # Unified tree path drivers
        tree_class_val = features.get("tree_classification_hsif", 0)
        if tree_class_val > 0:
            drivers.append(DriverItem(
                feature="unified_tree_classification",
                value="HSIF",
                role="observed",
                importance=0.6,
            ))

        tree_tier_1 = features.get("tree_tier_1", 0)
        if tree_tier_1 > 0:
            drivers.append(DriverItem(
                feature="unified_tree_tier",
                value=1,
                role="observed",
                importance=0.7,
            ))

        for cls_name in ["psif", "lsif", "capacity", "exposure", "low_severity", "actual_sif"]:
            cls_val = features.get(f"tree_classification_{cls_name}", 0)
            if cls_val > 0:
                drivers.append(DriverItem(
                    feature="unified_tree_classification",
                    value=cls_name.upper(),
                    role="observed",
                    importance=0.4,
                ))

        # Cluster drivers
        for cluster_name in ["barrier", "organizational", "personnel", "equipment", "planning", "environment"]:
            density = features.get(f"cluster_{cluster_name}_density", 0.0)
            if density >= 0.5:
                drivers.append(DriverItem(
                    feature=f"cluster_{cluster_name}_density",
                    value=round(density, 3),
                    role="observed",
                    importance=0.35,
                ))

        drivers.sort(key=lambda d: d.importance, reverse=True)
        return drivers[:15]

    def _build_evidence(
        self, analysis: Optional[ReportAnalysis]
    ) -> List[EvidenceItem]:
        evidence = []
        if analysis is None:
            return evidence

        for precursor_name, pa in analysis.precursor_analysis.items():
            for ev in pa.present_evidence:
                evidence.append(EvidenceItem(
                    source_sentence_id=ev.source_sentence_id,
                    text=ev.text,
                    role="observed",
                ))
            for ev in pa.absent_evidence:
                evidence.append(EvidenceItem(
                    source_sentence_id=ev.source_sentence_id,
                    text=ev.text,
                    role="absent_evidence",
                ))

        return evidence

    def _build_action_recommendations(
        self,
        action_set: set,
        features: Dict[str, float],
        evidence: List[EvidenceItem],
        analysis: Optional[ReportAnalysis],
    ) -> List[ActionRecommendation]:
        recommendations = []

        action_time_map = {
            "STOP_WORK": ActionTimeHorizon.NOW.value,
            "PAUSE_AND_REASSESS": ActionTimeHorizon.NOW.value,
            "VERIFY_CRITICAL_CONTROLS": ActionTimeHorizon.NOW.value,
            "ENERGY_ISOLATION_VERIFICATION": ActionTimeHorizon.NOW.value,
            "SUPERVISOR_REVIEW": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
            "PRE_TASK_PLAN_REVIEW": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
            "WORK_AUTHORIZATION_REVIEW": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
            "PERMIT_REVIEW": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
            "JOB_HAZARD_REASSESSMENT": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
            "BARRIER_RESTORATION": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "ENGINEERING_CONTROL": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "PROCEDURE_REVIEW": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "PROCEDURE_UPDATE": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "TRAINING_REVIEW": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "COMPETENCY_VERIFICATION": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "SUPERVISION_IMPROVEMENT": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "COMMUNICATION_REVIEW": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "WORK_PLANNING_REVIEW": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "SCHEDULE_PRESSURE_REVIEW": ActionTimeHorizon.DAYS_TO_WEEKS.value,
            "SAFETY_CULTURE_REVIEW": ActionTimeHorizon.LONGER_TERM.value,
            "MANAGEMENT_SYSTEM_REVIEW": ActionTimeHorizon.LONGER_TERM.value,
            "LESSONS_LEARNED": ActionTimeHorizon.LONGER_TERM.value,
            "TARGETED_MONITORING": ActionTimeHorizon.MONITOR.value,
            "NO_IMMEDIATE_ACTION": ActionTimeHorizon.MONITOR.value,
            "HUMAN_REVIEW_REQUIRED": ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value,
        }

        action_reason_map = {
            "STOP_WORK": "High-energy exposure or critical control failure detected",
            "PAUSE_AND_REASSESS": "Work conditions changed without adequate reassessment",
            "VERIFY_CRITICAL_CONTROLS": "Control failure or missing barrier identified",
            "ENERGY_ISOLATION_VERIFICATION": "Energy isolation Life-Saving Rule broken or uncertain",
            "SUPERVISOR_REVIEW": "Multiple precursor signals or ambiguous stop-work execution",
            "PRE_TASK_PLAN_REVIEW": "Pre-task plan weakness or work-change without plan update",
            "WORK_AUTHORIZATION_REVIEW": "Work authorisation Life-Saving Rule concerns",
            "PERMIT_REVIEW": "Permit-related control weakness",
            "JOB_HAZARD_REASSESSMENT": "Hazard recognition present but controls unclear",
            "BARRIER_RESTORATION": "Missing or failed barriers/controls",
            "ENGINEERING_CONTROL": "Engineering control weakness identified",
            "PROCEDURE_REVIEW": "Procedure or rules precursor indicates weakness",
            "PROCEDURE_UPDATE": "Procedures do not address current conditions",
            "TRAINING_REVIEW": "Worker readiness indicators suggest training need",
            "COMPETENCY_VERIFICATION": "Task familiarity concerns",
            "SUPERVISION_IMPROVEMENT": "Risk normalization or supervision gap detected",
            "COMMUNICATION_REVIEW": "Communication issue detected",
            "WORK_PLANNING_REVIEW": "Work planning deficiency detected",
            "SCHEDULE_PRESSURE_REVIEW": "Productivity pressure contributing to risk",
            "SAFETY_CULTURE_REVIEW": "Risk normalization or safety culture signal",
            "MANAGEMENT_SYSTEM_REVIEW": "Systemic precursor pattern detected",
            "LESSONS_LEARNED": "Recurring pattern warrants organizational learning",
            "TARGETED_MONITORING": "Monitor for future developments",
            "NO_IMMEDIATE_ACTION": "Evidence does not support immediate intervention",
            "HUMAN_REVIEW_REQUIRED": "Uncertainty requires expert review",
        }

        priority_counter = 1
        for action in sorted(action_set):
            time_horizon = action_time_map.get(action, ActionTimeHorizon.DAYS_TO_WEEKS.value)
            reason = action_reason_map.get(action, "Recommended based on evidence analysis")
            confidence = 0.8 if time_horizon in [ActionTimeHorizon.NOW.value, ActionTimeHorizon.NEXT_SHIFT_OR_HOURS.value] else 0.7

            recommendations.append(ActionRecommendation(
                action=action,
                priority=priority_counter,
                time_horizon=time_horizon,
                confidence=confidence,
                reason=reason,
                evidence=[],
            ))
            priority_counter += 1

        return recommendations
