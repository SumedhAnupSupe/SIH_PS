"""Configuration constants for the SIF Attention Prioritization Model v3.0.0.

Unified SIF Classification Tree with 22 precursors, clusters, density,
high-energy, direct control, and barrier failure rate.
"""

from enum import IntEnum, Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Attention Levels
# ---------------------------------------------------------------------------

class AttentionLevel(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    PLANNED = "PLANNED"
    MONITOR = "MONITOR"


URGENCY_ORDER: Dict[str, int] = {
    AttentionLevel.MONITOR.value: 0,
    AttentionLevel.PLANNED.value: 1,
    AttentionLevel.SHORT_TERM.value: 2,
    AttentionLevel.IMMEDIATE.value: 3,
}

URGENCY_DECODE: Dict[int, str] = {v: k for k, v in URGENCY_ORDER.items()}


# ---------------------------------------------------------------------------
# Systemic Attention Levels
# ---------------------------------------------------------------------------

class SystemicLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


SYSTEMIC_ORDER: Dict[str, int] = {
    SystemicLevel.NONE.value: 0,
    SystemicLevel.LOW.value: 1,
    SystemicLevel.MODERATE.value: 2,
    SystemicLevel.HIGH.value: 3,
}

SYSTEMIC_DECODE: Dict[int, str] = {v: k for k, v in SYSTEMIC_ORDER.items()}


# ---------------------------------------------------------------------------
# Action Taxonomy  (multi-label, not mutually exclusive)
# ---------------------------------------------------------------------------

ACTION_LABELS: List[str] = [
    "STOP_WORK",
    "PAUSE_AND_REASSESS",
    "VERIFY_CRITICAL_CONTROLS",
    "ENERGY_ISOLATION_VERIFICATION",
    "WORK_AUTHORIZATION_REVIEW",
    "PERMIT_REVIEW",
    "SUPERVISOR_REVIEW",
    "PRE_TASK_PLAN_REVIEW",
    "JOB_HAZARD_REASSESSMENT",
    "BARRIER_RESTORATION",
    "ENGINEERING_CONTROL",
    "PROCEDURE_REVIEW",
    "PROCEDURE_UPDATE",
    "TRAINING_REVIEW",
    "COMPETENCY_VERIFICATION",
    "SUPERVISION_IMPROVEMENT",
    "COMMUNICATION_REVIEW",
    "WORK_PLANNING_REVIEW",
    "SCHEDULE_PRESSURE_REVIEW",
    "SAFETY_CULTURE_REVIEW",
    "MANAGEMENT_SYSTEM_REVIEW",
    "LESSONS_LEARNED",
    "TARGETED_MONITORING",
    "NO_IMMEDIATE_ACTION",
    "HUMAN_REVIEW_REQUIRED",
]

ACTION_COLUMNS = [f"action_{a.lower()}" for a in ACTION_LABELS]


# ---------------------------------------------------------------------------
# Action Time Horizons
# ---------------------------------------------------------------------------

class ActionTimeHorizon(str, Enum):
    NOW = "NOW"
    NEXT_SHIFT_OR_HOURS = "NEXT_SHIFT_OR_HOURS"
    DAYS_TO_WEEKS = "DAYS_TO_WEEKS"
    LONGER_TERM = "LONGER_TERM"
    MONITOR = "MONITOR"


# ---------------------------------------------------------------------------
# Cost Matrix (configurable, asymmetric)
# ---------------------------------------------------------------------------

@dataclass
class CostMatrix:
    fn_immediate: float = 10.0
    fp_immediate: float = 2.0
    fn_short_term: float = 5.0
    fp_short_term: float = 1.0
    fn_planned: float = 2.0
    fp_planned: float = 1.0
    fn_monitor: float = 1.0
    fp_monitor: float = 1.0

    def weight_for(self, actual: str, predicted: str) -> float:
        if actual == predicted:
            return 0.0
        if actual == AttentionLevel.IMMEDIATE.value:
            return self.fn_immediate if URGENCY_ORDER[predicted] < URGENCY_ORDER[actual] else self.fp_immediate
        if actual == AttentionLevel.SHORT_TERM.value:
            return self.fn_short_term if URGENCY_ORDER[predicted] < URGENCY_ORDER[actual] else self.fp_short_term
        if actual == AttentionLevel.PLANNED.value:
            return self.fn_planned if URGENCY_ORDER[predicted] < URGENCY_ORDER[actual] else self.fp_planned
        return self.fn_monitor if URGENCY_ORDER[predicted] < URGENCY_ORDER[actual] else self.fp_monitor


COST_MATRIX = CostMatrix()


# ---------------------------------------------------------------------------
# Precursor Names (22 total: 13 EEI + 9 oil-and-gas)
# ---------------------------------------------------------------------------

EEI_PRECURSORS: List[str] = [
    "safe_work_procedure",
    "hazard_recognition",
    "departure_from_routine",
    "plan_to_address_work_change",
    "safety_attitudes",
    "rules_and_procedures",
    "familiarity_with_task",
    "risk_normalization",
    "productivity_pressure",
    "perceived_safety_culture",
    "stop_work_execution",
    "workers_inactive_in_safety",
    "pre_task_plan",
]

OG_PRECURSORS: List[str] = [
    "critical_control_failure",
    "high_energy_exposure",
    "energy_isolation_failure",
    "line_of_fire_exposure",
    "critical_control_verification_failure",
    "management_of_change_gap",
    "competency_supervision_gap",
    "work_authorization_gap",
    "simops_or_concurrent_operations",
]

PRECURSOR_NAMES: List[str] = EEI_PRECURSORS + OG_PRECURSORS

PRECURSOR_STATUS_COLS = PRECURSOR_NAMES
PRECURSOR_CONFIDENCE_COLS = [f"{p}_confidence" for p in PRECURSOR_NAMES]
PRECURSOR_EVIDENCE_COLS = [f"{p}_evidence_count" for p in PRECURSOR_NAMES]
PRECURSOR_EVIDENCE_STRENGTH_COLS = [f"{p}_evidence_strength" for p in PRECURSOR_NAMES]


# ---------------------------------------------------------------------------
# Precursor Clusters
# ---------------------------------------------------------------------------

PRECURSOR_CLUSTERS: Dict[str, List[str]] = {
    "personnel": [
        "hazard_recognition", "safety_attitudes", "familiarity_with_task",
        "risk_normalization", "productivity_pressure", "perceived_safety_culture",
        "workers_inactive_in_safety", "competency_supervision_gap",
    ],
    "planning": [
        "safe_work_procedure", "departure_from_routine", "plan_to_address_work_change",
        "pre_task_plan", "management_of_change_gap", "work_authorization_gap",
    ],
    "equipment": [
        "rules_and_procedures", "critical_control_failure",
        "energy_isolation_failure", "critical_control_verification_failure",
    ],
    "barrier": [
        "stop_work_execution", "critical_control_failure",
        "energy_isolation_failure", "critical_control_verification_failure",
    ],
    "organizational": [
        "perceived_safety_culture", "risk_normalization", "productivity_pressure",
        "management_of_change_gap", "competency_supervision_gap",
        "work_authorization_gap", "simops_or_concurrent_operations",
    ],
    "environment": [
        "high_energy_exposure", "line_of_fire_exposure",
        "departure_from_routine", "simops_or_concurrent_operations",
    ],
}

CLUSTER_LABELS: Dict[str, str] = {
    "personnel": "Personnel",
    "planning": "Planning",
    "equipment": "Equipment",
    "barrier": "Barrier",
    "organizational": "Organizational",
    "environment": "Environment",
}


# ---------------------------------------------------------------------------
# Precursor Interactions
# ---------------------------------------------------------------------------

PRECURSOR_INTERACTIONS: List[Tuple[str, str, str]] = [
    ("hazard_energy_x_control_failure", "high_energy_exposure", "critical_control_failure"),
    ("departure_x_reassessment_missing", "departure_from_routine", "management_of_change_gap"),
    ("productivity_x_risk_normalization", "productivity_pressure", "risk_normalization"),
    ("energy_isolation_x_broken_lsr", "energy_isolation_failure", "stop_work_execution"),
    ("stop_work_x_continued_work", "stop_work_execution", "productivity_pressure"),
]


# ---------------------------------------------------------------------------
# Unified SIF Classification Tree Configuration
# ---------------------------------------------------------------------------

UNIFIED_TREE_VERSION = "unified_sif_tree_v1"

UNIFIED_TREE_NODES = {
    "Q1": {"question": "Was there a fatality?", "next_on_no": "Q2"},
    "Q2": {"question": "Was there a life-threatening or life-altering injury?", "next_on_no": "Q3"},
    "Q3": {"question": "Was a high-energy source present?", "next_on_no": "Q8"},
    "Q4": {"question": "Was there a high-energy incident (energy release and worker proximity)?", "next_on_no": "Q6"},
    "Q5": {"question": "Was there a direct control present?", "next_on_yes": "outcome"},
    "Q6": {"question": "Was there a direct control present for the high-energy source?", "next_on_yes": "SUCCESS"},
    "Q7": {"question": "Two-IF test: Was the first IF (prevention) absent AND the second IF (protection) absent?", "next_on_yes": "HSIF"},
    "Q8": {"question": "Is this a low-severity event (near miss, minor injury, no high energy)?", "next_on_yes": "LOW_SEVERITY"},
}


# ---------------------------------------------------------------------------
# Feature Column Groups  (mirrors upstream pipeline schema)
# ---------------------------------------------------------------------------

WORK_CHANGE_COLS = [
    "environmental_change",
    "unexpected_condition",
    "work_plan_changed",
    "task_changed",
    "equipment_changed",
    "procedure_changed",
    "work_sequence_changed",
    "reassessment_performed",
    "reassessment_missing",
]

WORKER_COLS = [
    "worker_training_known",
    "worker_experience_known",
    "worker_hazard_awareness",
    "worker_safety_engagement",
    "supervision_present",
    "communication_issue",
]

CONTROL_COLS = [
    "control_failure_present",
    "missing_control_present",
    "barrier_failure_present",
    "control_deviation_present",
]

MISSING_INFO_COLS = [
    "procedure_information_missing",
    "pre_task_plan_information_missing",
    "worker_experience_information_missing",
    "hazard_information_missing",
    "stop_work_information_missing",
]

TEXT_STAT_COLS = [
    "report_length",
    "sentence_count",
    "relevant_sentence_count",
    "relevance_ratio",
]

HIGH_ENERGY_COLS = [
    "high_energy_present",
    "high_energy_incident",
    "high_energy_source_count",
    "high_energy_mechanical",
    "high_energy_electrical",
    "high_energy_hydraulic",
    "high_energy_pneumatic",
    "high_energy_thermal",
    "high_energy_radiation",
    "high_energy_gravity",
    "high_energy_chemical",
    "high_energy_biological",
]

DIRECT_CONTROL_COLS = [
    "direct_control_present",
    "direct_control_failed",
    "direct_control_missing",
    "direct_control_confidence",
]

DENSITY_COLS = [
    "precursor_density_raw",
    "precursor_density_evidence_weighted",
    "precursor_applicable_count",
    "precursor_present_count",
    "precursor_evidence_strength",
]

CLUSTER_COLS = [
    "cluster_personnel_contribution_score",
    "cluster_personnel_density",
    "cluster_personnel_evidence_coverage",
    "cluster_personnel_present_count",
    "cluster_planning_contribution_score",
    "cluster_planning_density",
    "cluster_planning_evidence_coverage",
    "cluster_planning_present_count",
    "cluster_equipment_contribution_score",
    "cluster_equipment_density",
    "cluster_equipment_evidence_coverage",
    "cluster_equipment_present_count",
    "cluster_barrier_contribution_score",
    "cluster_barrier_density",
    "cluster_barrier_evidence_coverage",
    "cluster_barrier_present_count",
    "cluster_organizational_contribution_score",
    "cluster_organizational_density",
    "cluster_organizational_evidence_coverage",
    "cluster_organizational_present_count",
    "cluster_environment_contribution_score",
    "cluster_environment_density",
    "cluster_environment_evidence_coverage",
    "cluster_environment_present_count",
]

CONSISTENCY_COLS = [
    "hazard_consistency",
    "barrier_consistency",
    "energy_consistency",
    "intra_model_consistency",
]

UNIFIED_TREE_COLS = [
    "unified_tree_confidence",
    "unified_tree_tier",
    "unified_tree_terminal_node",
    "tree_Q1_confidence",
    "tree_Q2_confidence",
    "tree_Q3_confidence",
    "tree_Q4_confidence",
    "tree_Q5_confidence",
    "tree_Q6_confidence",
    "tree_Q7_confidence",
    "tree_Q8_confidence",
]

LSR_RULES = [
    "driving",
    "bypassing_safety_controls",
    "confined_space",
    "energy_isolation",
    "hot_work",
    "line_of_fire",
    "safe_mechanical_lifting",
    "work_authorisation",
    "working_at_height",
]

LSR_STATUS_COLS = [f"lsr_{r}_status" for r in LSR_RULES]
LSR_CONFIDENCE_COLS = [f"lsr_{r}_confidence" for r in LSR_RULES]


# ---------------------------------------------------------------------------
# Barrier Failure Rate Configuration
# ---------------------------------------------------------------------------

@dataclass
class BarrierFailureRateConfig:
    """Deterministic barrier failure rate calculation weights."""
    direct_control_failure_weight: float = 0.30
    barrier_cluster_density_weight: float = 0.25
    critical_control_verification_weight: float = 0.20
    energy_isolation_failure_weight: float = 0.15
    stop_work_absence_weight: float = 0.10


BARRIER_FAILURE_RATE_CONFIG = BarrierFailureRateConfig()


# ---------------------------------------------------------------------------
# Classification Tree Feature Cols (from upstream, consumed by downstream)
# ---------------------------------------------------------------------------

TREE_FEATURE_COLS = UNIFIED_TREE_COLS

SIF_SCORE_FEATURE_COLS = [
    "sif_score",
    "sif_score_method",
    "sif_score_weight_source",
]


# ---------------------------------------------------------------------------
# Interaction Feature Definitions
# ---------------------------------------------------------------------------

@dataclass
class InteractionFeature:
    name: str
    left: str
    right: str
    op: str = "multiply"


INTERACTION_FEATURES: List[InteractionFeature] = [
    InteractionFeature("hazard_energy_x_control_failure", "high_energy_hazard_present", "control_failure_present"),
    InteractionFeature("departure_x_reassessment_missing", "departure_from_routine", "reassessment_missing"),
    InteractionFeature("productivity_x_risk_normalization", "productivity_pressure_present", "risk_normalization_present"),
    InteractionFeature("high_energy_x_broken_lsr", "high_energy_hazard_present", "broken_lsr_count_positive"),
    InteractionFeature("stop_work_x_continued_work", "stop_work_ambiguous", "work_continued_signal"),
    InteractionFeature("barrier_x_direct_control_failure", "barrier_failure_present", "direct_control_failed"),
    InteractionFeature("density_x_high_energy", "precursor_density_evidence_weighted", "high_energy_present"),
]


# ---------------------------------------------------------------------------
# Rule Engine Configuration
# ---------------------------------------------------------------------------

@dataclass
class RuleConfig:
    min_high_energy_exposure_for_immediate: int = 1
    min_broken_lsr_for_immediate: int = 1
    control_failure_plus_hazard_threshold: int = 2
    reassessment_missing_weight: float = 0.15
    systemic_precursor_count_threshold: int = 3


DEFAULT_RULE_CONFIG = RuleConfig()


# ---------------------------------------------------------------------------
# Calibration Settings
# ---------------------------------------------------------------------------

@dataclass
class CalibrationConfig:
    method: str = "isotonic"
    cv_folds: int = 5


# ---------------------------------------------------------------------------
# OOD Detection Settings
# ---------------------------------------------------------------------------

@dataclass
class OODConfig:
    enabled: bool = True
    contamination: float = 0.05
    n_neighbors: int = 5
    distance_threshold_percentile: float = 95.0


# ---------------------------------------------------------------------------
# Retrieval Settings
# ---------------------------------------------------------------------------

@dataclass
class RetrievalConfig:
    enabled: bool = False
    top_k: int = 5
    embedding_model: str = "all-MiniLM-L6-v2"
    alpha: float = 0.6
    beta: float = 0.4


# ---------------------------------------------------------------------------
# Model Versioning
# ---------------------------------------------------------------------------

MODEL_VERSION = "3.0.0"
RULE_ENGINE_VERSION = "3.0.0"
FEATURE_SCHEMA_VERSION = "2.0.0"
UPSTREAM_PIPELINE_VERSION = "3.0.0"
