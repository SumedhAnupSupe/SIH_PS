"""Unified SIF Score Engine - replaces the old TreeScoreEngine.

Exposes classification, tier, tree confidence, optional calibrated numeric
representation, score method, score version, and limitations.

Does NOT treat every Tier 1 event as numeric 1.0 without documented rationale.
"""

from typing import Dict, List, Optional

from .config import (
    SIFClassification,
    SIF_CLASSIFICATION_TIER,
    UNIFIED_TREE_VERSION,
    DEFAULT_SIF_SCORE_WEIGHTS,
    SIF_SCORE_COMPONENTS,
    PRECURSOR_ENCODING,
    PrecursorStatus,
)


class UnifiedSIFScoreEngine:
    """Computes a structured score from the unified tree classification."""

    def __init__(self):
        self.version = "1.0.0"
        self.method = "unified_tree_classification"

    def compute_score(
        self,
        classification_result: Dict,
        mapped_precursors: Dict,
    ) -> Dict:
        """Compute score from classification result and precursor evidence."""
        classification = classification_result.get("classification", "")
        tier = classification_result.get("tier", 3)
        tree_confidence = classification_result.get("confidence", 0.0)

        # Compute a classification score that preserves categorical meaning
        # Tier 1 events get higher base scores, but NOT automatically 1.0
        base_score_map = {
            SIFClassification.ACTUAL_SIF_FATALITY: 1.0,
            SIFClassification.ACTUAL_SIF_SERIOUS_INJURY: 0.95,
            SIFClassification.HSIF: 0.90,
            SIFClassification.PSIF: 0.80,
            SIFClassification.LSIF: 0.85,
            SIFClassification.EXPOSURE: 0.60,
            SIFClassification.CAPACITY: 0.50,
            SIFClassification.SUCCESS: 0.40,
            SIFClassification.SIF_POTENTIAL: 0.70,
            SIFClassification.LOW_SEVERITY: 0.20,
            SIFClassification.NO_SIF_POTENTIAL: 0.10,
        }

        base_score = base_score_map.get(classification, 0.0)

        # Adjust by precursor evidence presence
        present_count = sum(
            1 for d in mapped_precursors.values()
            if d.get("status") == PrecursorStatus.PRESENT
        )
        total_applicable = sum(
            1 for d in mapped_precursors.values()
            if d.get("status") != PrecursorStatus.NOT_APPLICABLE
        )
        precursor_ratio = present_count / max(total_applicable, 1)
        precursor_adjustment = precursor_ratio * 0.15  # Small positive adjustment

        # Combine
        classification_score = min(base_score + precursor_adjustment, 1.0)

        limitations = []
        if classification in (SIFClassification.LOW_SEVERITY, SIFClassification.NO_SIF_POTENTIAL):
            limitations.append("Low-severity classification; score should not drive urgent action")
        if tree_confidence < 0.6:
            limitations.append(f"Low tree confidence ({tree_confidence:.2f}); classification uncertain")
        if total_applicable == 0:
            limitations.append("No precursor evidence available for adjustment")

        return {
            "value": round(classification_score, 4),
            "range": [0.0, 1.0],
            "method": self.method,
            "score_version": self.version,
            "tree_version": classification_result.get("tree_version", UNIFIED_TREE_VERSION),
            "classification": classification,
            "classification_tier": tier,
            "tree_confidence": tree_confidence,
            "score_method": self.method,
            "score_version_label": self.version,
            "limitations": limitations,
            "weight_source": "unified_tree_classification_v1",
            "components": [],
            "missing_components": [],
        }

    def validate(self, score_obj: Dict) -> List[str]:
        errors = []
        value = score_obj.get("value", -1.0)
        if not (0.0 <= value <= 1.0):
            errors.append(f"Score value out of range: {value}")

        classification = score_obj.get("classification", "")
        if classification not in SIF_CLASSIFICATION_TIER:
            errors.append(f"Unknown classification: {classification}")

        tree_confidence = score_obj.get("tree_confidence", -1.0)
        if not (0.0 <= tree_confidence <= 1.0):
            errors.append(f"Tree confidence out of range: {tree_confidence}")

        tier = score_obj.get("classification_tier", 0)
        if tier not in (1, 2, 3):
            errors.append(f"Invalid tier: {tier}")

        if score_obj.get("score_version", "") == "":
            errors.append("score_version is not recorded")

        return errors
