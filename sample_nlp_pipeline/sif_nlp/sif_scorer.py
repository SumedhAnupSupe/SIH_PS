"""SIF Scoring Module - computes SIF potential score from precursor evidence."""

from typing import Dict, List, Optional
from dataclasses import dataclass

from .config import SIF_PRECURSORS, PRECURSOR_ENCODING, SIF_PRECURSOR_LABELS


@dataclass
class PrecursorWeight:
    """Weight configuration for a precursor in SIF scoring."""
    precursor: str
    weight: float
    rationale: str


DEFAULT_WEIGHTS: List[PrecursorWeight] = [
    PrecursorWeight("energy_isolation", 0.15, "Directly prevents SIF (EEI/IOGP)"),
    PrecursorWeight("departure_from_routine", 0.12, "Strong precursor (DEKRA)"),
    PrecursorWeight("plan_to_address_work_change", 0.12, "Work-change management critical"),
    PrecursorWeight("stop_work_execution", 0.10, "Last line of defense"),
    PrecursorWeight("hazard_recognition", 0.10, "Foundation of risk awareness"),
    PrecursorWeight("pre_task_plan", 0.10, "Planning quality indicator"),
    PrecursorWeight("risk_normalization", 0.08, "Cultural precursor"),
    PrecursorWeight("productivity_pressure", 0.08, "Systemic driver"),
    PrecursorWeight("familiarity_with_task", 0.05, "Complacency factor"),
    PrecursorWeight("safe_work_procedure", 0.05, "Procedure adherence"),
    PrecursorWeight("safety_attitudes", 0.03, "Cultural indicator"),
    PrecursorWeight("rules_and_procedures", 0.02, "Compliance indicator"),
    PrecursorWeight("perceived_safety_culture", 0.02, "Climate indicator"),
    PrecursorWeight("workers_inactive_in_safety", 0.02, "Engagement indicator"),
]


def compute_sif_score(
    mapped_precursors: Dict,
    weights: Optional[List[PrecursorWeight]] = None,
    present_threshold: int = 3,
) -> Dict:
    """
    Compute SIF potential score from precursor analysis.
    
    Returns dict with:
    - value: float (0-1)
    - method: str
    - weight_source: str
    - components: list of dicts
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    
    weight_map = {w.precursor: w for w in weights}
    total_weight = sum(w.weight for w in weights)
    
    present_precursors = []
    components = []
    weighted_sum = 0.0
    
    for precursor_key in SIF_PRECURSORS:
        data = mapped_precursors.get(precursor_key, {})
        status = data.get("status", 0)
        confidence = data.get("confidence", 0.0)
        evidence_count = data.get("evidence_count", 0)
        label = SIF_PRECURSOR_LABELS.get(precursor_key, precursor_key)
        
        weight_info = weight_map.get(precursor_key)
        weight = weight_info.weight if weight_info else 0.05
        
        # Score contribution based on status and confidence
        if status == 3:  # PRESENT
            contribution = weight * confidence
            present_precursors.append(precursor_key)
        elif status == 2:  # AMBIGUOUS
            contribution = weight * confidence * 0.5
        else:  # NOT_MENTIONED or ABSENT
            contribution = 0.0
        
        weighted_sum += contribution
        
        components.append({
            "precursor": label,
            "precursor_key": precursor_key,
            "status": PRECURSOR_ENCODING.get(status, "NOT_MENTIONED"),
            "confidence": round(confidence, 3),
            "evidence_count": evidence_count,
            "weight": round(weight, 3),
            "contribution": round(contribution, 4),
        })
    
    # Normalize to 0-1 range (max possible is sum of all weights)
    max_possible = total_weight
    normalized_score = min(weighted_sum / max_possible, 1.0) if max_possible > 0 else 0.0
    
    # Classify (model-derived indicator, NOT official SIF classification)
    if normalized_score >= 0.65:
        score_class = "HIGH"
    elif normalized_score >= 0.35:
        score_class = "MEDIUM"
    else:
        score_class = "LOW"
    
    return {
        "value": round(normalized_score, 3),
        "class": score_class,
        "method": "weighted_precursor_sum",
        "weight_source": "EEI/DEKRA/IOGP literature-based defaults",
        "components": components,
        "present_precursors": present_precursors,
        "max_possible": round(max_possible, 3),
    }


def get_sif_classification_label(score: float) -> str:
    """Get human-readable label for SIF score class."""
    if score >= 0.65:
        return "HIGH (Model-derived indicator; not a final SIF classification)"
    elif score >= 0.35:
        return "MEDIUM (Model-derived indicator; not a final SIF classification)"
    else:
        return "LOW (Model-derived indicator; not a final SIF classification)"