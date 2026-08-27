"""Rule-based safety override engine.

v3.0.0: Unified SIF Classification Tree rules, new safety rules,
22 precursors, barrier density, and cluster-based rules.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    AttentionLevel,
    SystemicLevel,
    ActionTimeHorizon,
    ACTION_LABELS,
    URGENCY_ORDER,
    PRECURSOR_NAMES,
    LSR_RULES,
    RuleConfig,
    DEFAULT_RULE_CONFIG,
)

logger = logging.getLogger(__name__)


class RuleSignal:
    """A signal produced by a single rule."""

    def __init__(
        self,
        rule_id: str,
        rule_description: str,
        candidate_attention: Optional[str] = None,
        candidate_actions: Optional[List[str]] = None,
        candidate_systemic: Optional[str] = None,
        urgency_score_adjustment: float = 0.0,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ):
        self.rule_id = rule_id
        self.rule_description = rule_description
        self.candidate_attention = candidate_attention
        self.candidate_actions = candidate_actions or []
        self.candidate_systemic = candidate_systemic
        self.urgency_score_adjustment = urgency_score_adjustment
        self.evidence = evidence or []

    def __repr__(self) -> str:
        return (
            f"RuleSignal(id={self.rule_id}, attention={self.candidate_attention}, "
            f"actions={self.candidate_actions})"
        )


class RuleEngine:
    """Deterministic rule engine for safety override and cold-start operation."""

    def __init__(self, config: Optional[RuleConfig] = None):
        self.config = config or DEFAULT_RULE_CONFIG
        self.version = "3.0.0"

    def evaluate(self, feature_row: Dict[str, Any]) -> List[RuleSignal]:
        signals: List[RuleSignal] = []

        # Original rules
        signals.extend(self._rule_energy_isolation_broken(feature_row))
        signals.extend(self._rule_high_energy_control_failure(feature_row))
        signals.extend(self._rule_reassessment_gap(feature_row))
        signals.extend(self._rule_stop_work_not_exercised(feature_row))
        signals.extend(self._rule_productivity_pressure_systemic(feature_row))
        signals.extend(self._rule_risk_normalization_systemic(feature_row))
        signals.extend(self._rule_lsr_broken_immediate(feature_row))
        signals.extend(self._rule_multiple_precursors_elevated(feature_row))
        signals.extend(self._rule_missing_controls_systemic(feature_row))
        signals.extend(self._rule_procedure_weakness_systemic(feature_row))

        # Unified tree rules
        signals.extend(self._rule_tree_hsif_active_exposure(feature_row))
        signals.extend(self._rule_tree_tier_1(feature_row))
        signals.extend(self._rule_tree_hsif_path(feature_row))
        signals.extend(self._rule_tree_psif_path(feature_row))
        signals.extend(self._rule_tree_exposure(feature_row))

        # New v3.0.0 rules
        signals.extend(self._rule_barrier_density_high(feature_row))
        signals.extend(self._rule_high_energy_no_direct_control(feature_row))
        signals.extend(self._rule_cluster_organizational_high(feature_row))
        signals.extend(self._rule_cluster_barrier_degraded(feature_row))
        signals.extend(self._rule_consistency_low(feature_row))

        return signals

    def aggregate_signals(self, signals: List[RuleSignal]) -> Dict[str, Any]:
        if not signals:
            return {
                "rule_attention": AttentionLevel.MONITOR.value,
                "rule_urgency_score": 0.0,
                "rule_actions": [],
                "rule_systemic": SystemicLevel.NONE.value,
                "rule_adjustments": [],
                "override_applied": False,
                "signals": [],
            }

        max_attention_level = AttentionLevel.MONITOR.value
        max_attention_rank = URGENCY_ORDER[max_attention_level]
        adjustments = []
        all_actions: List[str] = []
        max_systemic_rank = 0
        all_evidence = []

        for sig in signals:
            if sig.candidate_attention:
                rank = URGENCY_ORDER.get(sig.candidate_attention, 0)
                if rank > max_attention_rank:
                    max_attention_rank = rank
                    max_attention_level = sig.candidate_attention

            if sig.candidate_systemic:
                from .config import SYSTEMIC_ORDER
                srank = SYSTEMIC_ORDER.get(sig.candidate_systemic, 0)
                if srank > max_systemic_rank:
                    max_systemic_rank = srank

            all_actions.extend(sig.candidate_actions)
            all_evidence.extend(sig.evidence)

            if sig.urgency_score_adjustment != 0:
                adjustments.append({
                    "rule_id": sig.rule_id,
                    "adjustment": sig.urgency_score_adjustment,
                })

        seen = set()
        unique_actions = []
        for a in all_actions:
            if a not in seen:
                seen.add(a)
                unique_actions.append(a)

        from .config import SYSTEMIC_DECODE
        systemic_level = SYSTEMIC_DECODE.get(max_systemic_rank, SystemicLevel.NONE.value)

        base_score = max_attention_rank / 3.0
        total_adjustment = sum(a["adjustment"] for a in adjustments)
        urgency_score = max(0.0, min(1.0, base_score + total_adjustment))

        return {
            "rule_attention": max_attention_level,
            "rule_urgency_score": urgency_score,
            "rule_actions": unique_actions,
            "rule_systemic": systemic_level,
            "rule_adjustments": adjustments,
            "override_applied": len(signals) > 0,
            "signals": [
                {
                    "rule_id": s.rule_id,
                    "description": s.rule_description,
                    "attention": s.candidate_attention,
                    "actions": s.candidate_actions,
                }
                for s in signals
            ],
        }

    # ------------------------------------------------------------------
    # Original Rules
    # ------------------------------------------------------------------

    def _rule_energy_isolation_broken(self, f: Dict[str, Any]) -> List[RuleSignal]:
        lsr_status = str(f.get("lsr_energy_isolation_status", "NOT_APPLICABLE"))
        high_energy = float(f.get("high_energy_hazard_present", 0))
        if lsr_status == "BROKEN" and high_energy > 0:
            return [RuleSignal(
                rule_id="RULE_ENERGY_ISOLATION_BROKEN",
                rule_description="Energy isolation Life-Saving Rule broken with high-energy hazard present",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "ENERGY_ISOLATION_VERIFICATION", "VERIFY_CRITICAL_CONTROLS"],
                urgency_score_adjustment=0.3,
                evidence=[{"type": "lsr_status", "rule": "energy_isolation", "status": lsr_status}],
            )]
        return []

    def _rule_high_energy_control_failure(self, f: Dict[str, Any]) -> List[RuleSignal]:
        high_energy = float(f.get("high_energy_hazard_present", 0))
        control_failure = int(f.get("control_failure_present", 0))
        missing_control = int(f.get("missing_control_present", 0))
        if high_energy > 0 and (control_failure > 0 or missing_control > 0):
            return [RuleSignal(
                rule_id="RULE_HIGH_ENERGY_CONTROL_FAILURE",
                rule_description="High-energy exposure combined with control failure",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "VERIFY_CRITICAL_CONTROLS", "BARRIER_RESTORATION"],
                urgency_score_adjustment=0.25,
            )]
        return []

    def _rule_reassessment_gap(self, f: Dict[str, Any]) -> List[RuleSignal]:
        reassessment_gap = float(f.get("reassessment_gap", 0))
        if reassessment_gap > 0:
            return [RuleSignal(
                rule_id="RULE_REASSESSMENT_GAP",
                rule_description="Work conditions changed without required reassessment",
                candidate_attention=AttentionLevel.SHORT_TERM.value,
                candidate_actions=["PAUSE_AND_REASSESS", "PRE_TASK_PLAN_REVIEW"],
                urgency_score_adjustment=0.15,
            )]
        return []

    def _rule_stop_work_not_exercised(self, f: Dict[str, Any]) -> List[RuleSignal]:
        stop_work_absent = int(f.get("stop_work_execution", 0))
        precursors_present = sum(
            1 for name in PRECURSOR_NAMES if int(f.get(name, 0)) == 3
        )
        if stop_work_absent == 1 and precursors_present >= 2:
            return [RuleSignal(
                rule_id="RULE_STOP_WORK_NOT_EXERCISED",
                rule_description="Stop-work authority not exercised with multiple present precursors",
                candidate_attention=AttentionLevel.SHORT_TERM.value,
                candidate_actions=["SUPERVISOR_REVIEW", "STOP_WORK"],
                urgency_score_adjustment=0.1,
            )]
        return []

    def _rule_productivity_pressure_systemic(self, f: Dict[str, Any]) -> List[RuleSignal]:
        prod_pressure = int(f.get("productivity_pressure", 0))
        if prod_pressure == 3:
            return [RuleSignal(
                rule_id="RULE_PRODUCTIVITY_PRESSURE",
                rule_description="Productivity pressure detected -- systemic concern",
                candidate_systemic=SystemicLevel.MODERATE.value,
                candidate_actions=["SCHEDULE_PRESSURE_REVIEW", "WORK_PLANNING_REVIEW"],
            )]
        return []

    def _rule_risk_normalization_systemic(self, f: Dict[str, Any]) -> List[RuleSignal]:
        risk_norm = int(f.get("risk_normalization", 0))
        if risk_norm == 3:
            return [RuleSignal(
                rule_id="RULE_RISK_NORMALIZATION",
                rule_description="Risk normalization detected -- systemic safety culture concern",
                candidate_systemic=SystemicLevel.MODERATE.value,
                candidate_actions=["SAFETY_CULTURE_REVIEW", "SUPERVISION_IMPROVEMENT"],
            )]
        return []

    def _rule_lsr_broken_immediate(self, f: Dict[str, Any]) -> List[RuleSignal]:
        broken_rules = []
        for rule in LSR_RULES:
            status = str(f.get(f"lsr_{rule}_status", "NOT_APPLICABLE"))
            if status == "BROKEN":
                broken_rules.append(rule)

        if not broken_rules:
            return []

        if len(broken_rules) >= 2:
            return [RuleSignal(
                rule_id="RULE_MULTIPLE_LSR_BROKEN",
                rule_description=f"Multiple Life-Saving Rules broken: {', '.join(broken_rules)}",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "VERIFY_CRITICAL_CONTROLS", "SUPERVISOR_REVIEW"],
                urgency_score_adjustment=0.2,
                evidence=[{"type": "lsr_broken", "rules": broken_rules}],
            )]

        return [RuleSignal(
            rule_id="RULE_LSR_BROKEN",
            rule_description=f"Life-Saving Rule broken: {broken_rules[0]}",
            candidate_attention=AttentionLevel.SHORT_TERM.value,
            candidate_actions=["SUPERVISOR_REVIEW", "PAUSE_AND_REASSESS"],
            urgency_score_adjustment=0.1,
            evidence=[{"type": "lsr_broken", "rules": broken_rules}],
        )]

    def _rule_multiple_precursors_elevated(self, f: Dict[str, Any]) -> List[RuleSignal]:
        present_count = sum(
            1 for name in PRECURSOR_NAMES if int(f.get(name, 0)) == 3
        )
        if present_count >= self.config.systemic_precursor_count_threshold:
            return [RuleSignal(
                rule_id="RULE_MULTIPLE_PRECURSORS",
                rule_description=f"{present_count} SIF precursors detected as PRESENT",
                candidate_systemic=SystemicLevel.HIGH.value,
                candidate_actions=["MANAGEMENT_SYSTEM_REVIEW", "LESSONS_LEARNED"],
            )]
        return []

    def _rule_missing_controls_systemic(self, f: Dict[str, Any]) -> List[RuleSignal]:
        missing_count = sum(
            1 for col in ["control_failure_present", "missing_control_present",
                          "barrier_failure_present", "control_deviation_present"]
            if int(f.get(col, 0)) > 0
        )
        if missing_count >= 2:
            return [RuleSignal(
                rule_id="RULE_MISSING_CONTROLS",
                rule_description="Multiple control types missing or failed",
                candidate_systemic=SystemicLevel.MODERATE.value,
                candidate_actions=["BARRIER_RESTORATION", "ENGINEERING_CONTROL", "PROCEDURE_REVIEW"],
            )]
        return []

    def _rule_procedure_weakness_systemic(self, f: Dict[str, Any]) -> List[RuleSignal]:
        ptp_missing = int(f.get("pre_task_plan_information_missing", 0))
        proc_missing = int(f.get("procedure_information_missing", 0))
        proc_changed = int(f.get("procedure_changed", 0))
        if (ptp_missing > 0 or proc_missing > 0) and proc_changed > 0:
            return [RuleSignal(
                rule_id="RULE_PROCEDURE_WEAKNESS",
                rule_description="Pre-task plan and/or procedure weakness detected",
                candidate_systemic=SystemicLevel.MODERATE.value,
                candidate_actions=["PROCEDURE_REVIEW", "PROCEDURE_UPDATE", "TRAINING_REVIEW"],
            )]
        return []

    # ------------------------------------------------------------------
    # Unified Tree-Based Rules
    # ------------------------------------------------------------------

    def _rule_tree_hsif_active_exposure(self, f: Dict[str, Any]) -> List[RuleSignal]:
        tree_class = str(f.get("unified_tree_classification", ""))
        control_failure = int(f.get("control_failure_present", 0))
        high_energy = float(f.get("high_energy_hazard_present", 0))

        if tree_class == "HSIF" and (control_failure > 0 or high_energy > 0):
            return [RuleSignal(
                rule_id="RULE_TREE_HSIF_ACTIVE_EXPOSURE",
                rule_description="HSIF classification with active critical exposure",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "VERIFY_CRITICAL_CONTROLS", "SUPERVISOR_REVIEW"],
                urgency_score_adjustment=0.2,
                evidence=[{"type": "tree_classification", "classification": "HSIF", "active_exposure": True}],
            )]
        return []

    def _rule_tree_tier_1(self, f: Dict[str, Any]) -> List[RuleSignal]:
        tree_tier = int(f.get("unified_tree_tier", 3))
        if tree_tier == 1:
            return [RuleSignal(
                rule_id="RULE_TREE_TIER_1",
                rule_description="Tier 1 classification (fatality or serious injury)",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "SUPERVISOR_REVIEW", "HUMAN_REVIEW_REQUIRED"],
                urgency_score_adjustment=0.3,
                evidence=[{"type": "tree_tier", "tier": 1}],
            )]
        return []

    def _rule_tree_hsif_path(self, f: Dict[str, Any]) -> List[RuleSignal]:
        tree_class = str(f.get("unified_tree_classification", ""))
        if tree_class == "HSIF":
            return [RuleSignal(
                rule_id="RULE_TREE_HSIF",
                rule_description="HSIF classification -- high severity with no direct control",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "BARRIER_RESTORATION", "ENERGY_ISOLATION_VERIFICATION"],
                urgency_score_adjustment=0.2,
                evidence=[{"type": "tree_classification", "classification": "HSIF"}],
            )]
        return []

    def _rule_tree_psif_path(self, f: Dict[str, Any]) -> List[RuleSignal]:
        tree_class = str(f.get("unified_tree_classification", ""))
        if tree_class == "PSIF":
            return [RuleSignal(
                rule_id="RULE_TREE_PSIF",
                rule_description="PSIF classification -- potential SIF without direct control",
                candidate_attention=AttentionLevel.SHORT_TERM.value,
                candidate_actions=["VERIFY_CRITICAL_CONTROLS", "PAUSE_AND_REASSESS"],
                urgency_score_adjustment=0.1,
                evidence=[{"type": "tree_classification", "classification": "PSIF"}],
            )]
        return []

    def _rule_tree_exposure(self, f: Dict[str, Any]) -> List[RuleSignal]:
        tree_class = str(f.get("unified_tree_classification", ""))
        if tree_class == "EXPOSURE":
            return [RuleSignal(
                rule_id="RULE_TREE_EXPOSURE",
                rule_description="Exposure classification -- high energy present, no incident yet",
                candidate_attention=AttentionLevel.SHORT_TERM.value,
                candidate_actions=["VERIFY_CRITICAL_CONTROLS", "ENERGY_ISOLATION_VERIFICATION"],
                urgency_score_adjustment=0.05,
                evidence=[{"type": "tree_classification", "classification": "EXPOSURE"}],
            )]
        return []

    # ------------------------------------------------------------------
    # New v3.0.0 Rules
    # ------------------------------------------------------------------

    def _rule_barrier_density_high(self, f: Dict[str, Any]) -> List[RuleSignal]:
        barrier_density = float(f.get("barrier_density", 0.0))
        if barrier_density >= 0.6:
            return [RuleSignal(
                rule_id="RULE_BARRIER_DENSITY_HIGH",
                rule_description=f"High barrier degradation density ({barrier_density:.2f})",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["BARRIER_RESTORATION", "VERIFY_CRITICAL_CONTROLS", "ENGINEERING_CONTROL"],
                urgency_score_adjustment=0.15,
            )]
        elif barrier_density >= 0.3:
            return [RuleSignal(
                rule_id="RULE_BARRIER_DENSITY_ELEVATED",
                rule_description=f"Elevated barrier degradation density ({barrier_density:.2f})",
                candidate_attention=AttentionLevel.SHORT_TERM.value,
                candidate_actions=["BARRIER_RESTORATION", "PROCEDURE_REVIEW"],
                urgency_score_adjustment=0.1,
            )]
        return []

    def _rule_high_energy_no_direct_control(self, f: Dict[str, Any]) -> List[RuleSignal]:
        he_present = float(f.get("high_energy_present", 0))
        dc_failed = float(f.get("direct_control_failed", 0))
        dc_missing = float(f.get("direct_control_missing", 0))
        if he_present > 0 and (dc_failed > 0 or dc_missing > 0):
            return [RuleSignal(
                rule_id="RULE_HIGH_ENERGY_NO_DC",
                rule_description="High energy present with failed or missing direct control",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["STOP_WORK", "VERIFY_CRITICAL_CONTROLS", "BARRIER_RESTORATION"],
                urgency_score_adjustment=0.25,
            )]
        return []

    def _rule_cluster_organizational_high(self, f: Dict[str, Any]) -> List[RuleSignal]:
        org_density = float(f.get("cluster_organizational_density", 0.0))
        if org_density >= 0.6:
            return [RuleSignal(
                rule_id="RULE_CLUSTER_ORG_HIGH",
                rule_description=f"High organizational cluster density ({org_density:.2f})",
                candidate_systemic=SystemicLevel.HIGH.value,
                candidate_actions=["MANAGEMENT_SYSTEM_REVIEW", "SAFETY_CULTURE_REVIEW", "LESSONS_LEARNED"],
            )]
        elif org_density >= 0.4:
            return [RuleSignal(
                rule_id="RULE_CLUSTER_ORG_ELEVATED",
                rule_description=f"Elevated organizational cluster density ({org_density:.2f})",
                candidate_systemic=SystemicLevel.MODERATE.value,
                candidate_actions=["SAFETY_CULTURE_REVIEW", "SUPERVISION_IMPROVEMENT"],
            )]
        return []

    def _rule_cluster_barrier_degraded(self, f: Dict[str, Any]) -> List[RuleSignal]:
        barrier_density = float(f.get("cluster_barrier_density", 0.0))
        if barrier_density >= 0.5:
            return [RuleSignal(
                rule_id="RULE_CLUSTER_BARRIER_DEGRADED",
                rule_description=f"Barrier cluster degraded ({barrier_density:.2f})",
                candidate_attention=AttentionLevel.IMMEDIATE.value,
                candidate_actions=["BARRIER_RESTORATION", "VERIFY_CRITICAL_CONTROLS"],
                urgency_score_adjustment=0.15,
            )]
        return []

    def _rule_consistency_low(self, f: Dict[str, Any]) -> List[RuleSignal]:
        consistency = float(f.get("intra_model_consistency", 0.5))
        if consistency < 0.3:
            return [RuleSignal(
                rule_id="RULE_LOW_CONSISTENCY",
                rule_description=f"Low model consistency ({consistency:.2f}) -- classification uncertain",
                candidate_actions=["HUMAN_REVIEW_REQUIRED", "SUPERVISOR_REVIEW"],
                urgency_score_adjustment=0.05,
            )]
        return []

    def apply_safety_override(
        self,
        model_attention: str,
        model_urgency_score: float,
        rule_result: Dict[str, Any],
    ) -> Tuple[str, float, bool]:
        if not rule_result["override_applied"]:
            return model_attention, model_urgency_score, False

        rule_attention = rule_result["rule_attention"]
        rule_rank = URGENCY_ORDER.get(rule_attention, 0)
        model_rank = URGENCY_ORDER.get(model_attention, 0)

        if rule_rank > model_rank:
            logger.info(
                "Safety override: rule=%s (rank=%d) overrides model=%s (rank=%d)",
                rule_attention, rule_rank, model_attention, model_rank,
            )
            return (
                rule_attention,
                max(model_urgency_score, rule_result["rule_urgency_score"]),
                True,
            )

        return model_attention, model_urgency_score, False
