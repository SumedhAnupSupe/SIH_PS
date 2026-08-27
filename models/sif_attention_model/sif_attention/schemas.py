"""Pydantic schemas for input/output validation.

v3.0.0: Unified SIF Classification Tree, barrier assessment, consistency.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PrecursorEvidence(BaseModel):
    text: str
    source_sentence_id: int


class PrecursorAnalysis(BaseModel):
    precursor: str
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    evidence_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    present_evidence: List[PrecursorEvidence] = []
    absent_evidence: List[PrecursorEvidence] = []


class LSRRuleAnalysis(BaseModel):
    rule_name: str
    status: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: List[PrecursorEvidence] = []


class LifeSavingRules(BaseModel):
    broken_rule_count: int = Field(ge=0)
    broken_rules: List[str] = []
    analysis: List[LSRRuleAnalysis] = []


class SIFScore(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    range: List[float] = [0.0, 1.0]
    method: str
    weight_source: str
    classification: str = ""
    classification_tier: int = 3
    tree_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    limitations: List[str] = []


class UnifiedTreePathNode(BaseModel):
    node_id: str
    question: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[PrecursorEvidence] = []
    source_sentence_ids: List[int] = []
    reason: str = ""


class UnifiedClassificationTree(BaseModel):
    classification: str
    tier: int = 3
    tree_version: str = "unified_sif_tree_v1"
    confidence: float = Field(ge=0.0, le=1.0)
    path: List[UnifiedTreePathNode] = []
    terminal_node: str = ""
    reason: str = ""
    evidence: List[PrecursorEvidence] = []


class HighEnergyAnalysis(BaseModel):
    high_energy_present: bool = False
    high_energy_incident: bool = False
    energy_sources: Dict[str, List[str]] = {}
    exposure_categories: Dict[str, List[str]] = {}


class DirectControlAssessment(BaseModel):
    state: str = "NOT_APPLICABLE"
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    evidence: List[PrecursorEvidence] = []


class OutcomeEvidence(BaseModel):
    fatality: bool = False
    life_threatening_injury: bool = False
    life_altering_injury: bool = False
    minor_injury: bool = False
    near_miss: bool = False
    sustained_sif_injury: bool = False
    evidence: Dict[str, List[str]] = {}


class TwoIFTest(BaseModel):
    first_if_absent: bool = False
    second_if_absent: bool = False
    both_absent: bool = False
    evidence: List[PrecursorEvidence] = []


class ClusterAnalysis(BaseModel):
    label: str
    contribution_score: float = 0.0
    density: float = 0.0
    evidence_coverage: float = 0.0
    present_count: int = 0
    applicable_count: int = 0


class DensityAnalysis(BaseModel):
    raw: float = 0.0
    evidence_weighted: float = 0.0
    applicable_precursor_count: int = 0
    present_precursor_count: int = 0
    evidence_strength: float = 0.0


class BarrierFailureAssessment(BaseModel):
    failure_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    direct_control_failure_contrib: float = 0.0
    barrier_cluster_contrib: float = 0.0
    critical_control_verification_contrib: float = 0.0
    energy_isolation_contrib: float = 0.0
    stop_work_contrib: float = 0.0
    calculation_method: str = "deterministic_weighted_sum"


class ReportAnalysis(BaseModel):
    incident_id: str
    summary: str = ""
    metadata: Dict[str, Any] = {}
    report_statistics: Dict[str, Any] = {}
    precursor_analysis: Dict[str, PrecursorAnalysis] = {}
    cluster_analysis: Dict[str, ClusterAnalysis] = {}
    density: DensityAnalysis = Field(default_factory=DensityAnalysis)
    interaction_features: Dict[str, float] = {}
    consistency: Dict[str, float] = {}
    high_energy: HighEnergyAnalysis = Field(default_factory=HighEnergyAnalysis)
    direct_control: DirectControlAssessment = Field(default_factory=DirectControlAssessment)
    outcome: OutcomeEvidence = Field(default_factory=OutcomeEvidence)
    two_if_test: TwoIFTest = Field(default_factory=TwoIFTest)
    hazards: List[Dict[str, Any]] = []
    task_types: List[Dict[str, Any]] = []
    controls: Dict[str, Any] = {}
    environment: Dict[str, Any] = {}
    work_changes: Dict[str, Any] = {}
    worker_info: Dict[str, Any] = {}
    life_saving_rules: LifeSavingRules = Field(default_factory=lambda: LifeSavingRules(broken_rule_count=0))
    unified_tree: UnifiedClassificationTree = Field(default_factory=lambda: UnifiedClassificationTree(classification=""))
    sif_score: SIFScore = Field(default_factory=lambda: SIFScore(value=0.0, method="unified_tree_classification", weight_source="none"))
    barrier_failure_assessment: BarrierFailureAssessment = Field(default_factory=BarrierFailureAssessment)


class UpstreamInputs(BaseModel):
    incident_id: str
    feature_row: Dict[str, Any] = Field(description="Single row from sif_features_encoded.csv")
    analysis_json: Optional[ReportAnalysis] = None
    summary_text: str = ""


class ActionRecommendation(BaseModel):
    action: str
    priority: int = Field(ge=1, le=10)
    time_horizon: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: List[Dict[str, Any]] = []


class EvidenceItem(BaseModel):
    source_sentence_id: Optional[int] = None
    text: str
    role: str = "observed"


class DriverItem(BaseModel):
    feature: str
    value: Any
    role: str
    importance: float = 0.0


class UncertaintyInfo(BaseModel):
    missing_information: List[str] = []
    contradictions: List[str] = []
    out_of_distribution: bool = False
    human_review_required: bool = False


class SimilarIncident(BaseModel):
    incident_id: str
    similarity: float = Field(ge=0.0, le=1.0)
    historical_action: str = ""
    historical_outcome: str = ""


class AttentionAssessment(BaseModel):
    level: str
    urgency_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    systemic_attention: str
    systemic_attention_score: float = Field(ge=0.0, le=1.0)


class ModelMetadata(BaseModel):
    upstream_pipeline_version: str = ""
    feature_schema_version: str = ""
    urgency_model_version: str = ""
    action_model_version: str = ""
    rule_engine_version: str = ""
    prediction_mode: str = "RULE_BASED_COLD_START"


class IncidentPrediction(BaseModel):
    incident_id: str
    prediction_mode: str = "RULE_BASED_COLD_START"

    risk_potential_score: float = Field(ge=0.0, le=1.0)
    risk_potential_source: str = "upstream_sif_score"

    attention: AttentionAssessment
    actions: List[ActionRecommendation] = []
    drivers: List[DriverItem] = []
    evidence: List[EvidenceItem] = []
    similar_incidents: List[SimilarIncident] = []
    uncertainty: UncertaintyInfo = Field(default_factory=UncertaintyInfo)
    model_metadata: ModelMetadata = Field(default_factory=ModelMetadata)

    action_flags: Dict[str, int] = {}

    upstream_sif_score: float = 0.0
    upstream_tree_classification: str = ""
    upstream_tree_tier: int = 3
    upstream_tree_confidence: float = 0.0
    upstream_tree_version: str = ""
    upstream_tree_node_answers: Dict[str, str] = {}
    upstream_tree_node_confidences: Dict[str, float] = {}

    barrier_failure_rate: float = 0.0
    barrier_failure_assessment: Optional[BarrierFailureAssessment] = None

    def to_assessment_json(self) -> Dict[str, Any]:
        return self.model_dump()
