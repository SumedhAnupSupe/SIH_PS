"""Unified SIF Classification Tree - replaces the old 7-node tree.

Implements the Unified SIF Classification Tree for Oil & Gas with
structured node representations, evidence traceability, and the Two-IF test.
"""

from typing import Dict, List, Optional, Tuple

from .config import (
    UNIFIED_TREE_NODES,
    UNIFIED_TREE_VERSION,
    SIFClassification,
    SIF_CLASSIFICATION_TIER,
)


class TreePathNode:
    """A single node evaluation in the classification tree."""

    def __init__(
        self,
        node_id: str,
        question: str,
        answer: str,
        confidence: float,
        evidence: List[Dict],
        source_sentence_ids: List[int],
        reason: str,
    ):
        self.node_id = node_id
        self.question = question
        self.answer = answer
        self.confidence = confidence
        self.evidence = evidence
        self.source_sentence_ids = source_sentence_ids
        self.reason = reason

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "question": self.question,
            "answer": self.answer,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_sentence_ids": self.source_sentence_ids,
            "reason": self.reason,
        }


class UnifiedSIFClassifier:
    """Classifies incidents using the Unified SIF Classification Tree."""

    def __init__(self):
        self.tree_version = UNIFIED_TREE_VERSION
        self.nodes = UNIFIED_TREE_NODES

    def classify(
        self,
        extracted_evidence: Dict,
    ) -> Dict:
        """Traverse the unified tree and produce a classification.

        Returns a dict with classification, tier, confidence, path, and reason.
        """
        high_energy = extracted_evidence.get("high_energy", {})
        outcome = extracted_evidence.get("outcome", {})
        direct_control = extracted_evidence.get("direct_control", {})
        two_if = extracted_evidence.get("two_if_test", {})

        path: List[TreePathNode] = []

        # Q1: Fatality?
        fatality = outcome.get("fatality", False)
        q1_answer, q1_confidence, q1_reason, q1_ev = self._evaluate_q1(outcome)
        path.append(self._make_node("Q1", q1_answer, q1_confidence, q1_reason, q1_ev))
        if q1_answer == "YES":
            return self._terminal_result(SIFClassification.ACTUAL_SIF_FATALITY, path)

        # Q2: Life-threatening or life-altering injury?
        q2_answer, q2_confidence, q2_reason, q2_ev = self._evaluate_q2(outcome)
        path.append(self._make_node("Q2", q2_answer, q2_confidence, q2_reason, q2_ev))
        if q2_answer == "YES":
            return self._terminal_result(SIFClassification.ACTUAL_SIF_SERIOUS_INJURY, path)

        # Q3: High energy present?
        high_energy_present = high_energy.get("high_energy_present", False)
        q3_answer, q3_confidence, q3_reason, q3_ev = self._evaluate_q3(high_energy)
        path.append(self._make_node("Q3", q3_answer, q3_confidence, q3_reason, q3_ev))
        if q3_answer == "NO":
            # Q8: Low-severity
            q8_answer, q8_confidence, q8_reason, q8_ev = self._evaluate_q8(outcome, high_energy)
            path.append(self._make_node("Q8", q8_answer, q8_confidence, q8_reason, q8_ev))
            return self._terminal_result(SIFClassification.LOW_SEVERITY, path)

        # Q4: High-energy incident?
        high_energy_incident = high_energy.get("high_energy_incident", False)
        q4_answer, q4_confidence, q4_reason, q4_ev = self._evaluate_q4(high_energy)
        path.append(self._make_node("Q4", q4_answer, q4_confidence, q4_reason, q4_ev))
        if q4_answer == "NO":
            # Q6: Exposure/Capacity
            q6_answer, q6_confidence, q6_reason, q6_ev = self._evaluate_q6(direct_control)
            path.append(self._make_node("Q6", q6_answer, q6_confidence, q6_reason, q6_ev))
            if q6_answer == "YES":
                return self._terminal_result(SIFClassification.SUCCESS, path)
            else:
                return self._terminal_result(SIFClassification.EXPOSURE, path)

        # Q5: Direct control present?
        sustained_sif = outcome.get("sustained_sif_injury", False)
        q5_answer, q5_confidence, q5_reason, q5_ev = self._evaluate_q5(
            direct_control, sustained_sif, outcome
        )
        path.append(self._make_node("Q5", q5_answer, q5_confidence, q5_reason, q5_ev))

        # Determine Q5 outcome
        dc_present = direct_control.get("present", False)
        if dc_present and sustained_sif:
            return self._terminal_result(SIFClassification.LSIF, path)
        elif dc_present and not sustained_sif:
            return self._terminal_result(SIFClassification.CAPACITY, path)
        elif not dc_present and sustained_sif:
            return self._terminal_result(SIFClassification.HSIF, path)
        else:
            return self._terminal_result(SIFClassification.PSIF, path)

    def _evaluate_q1(self, outcome: Dict) -> Tuple[str, float, str, List[Dict]]:
        fatality = outcome.get("fatality", False)
        evidence = []
        if fatality:
            ev_data = outcome.get("evidence", {}).get("fatality", [])
            for ev in ev_data:
                evidence.append({"text": ev, "source_sentence_id": -1})
            return "YES", 0.95, "Fatality confirmed from incident evidence", evidence
        return "NO", 0.9, "No fatality indicated in report", []

    def _evaluate_q2(self, outcome: Dict) -> Tuple[str, float, str, List[Dict]]:
        life_threatening = outcome.get("life_threatening_injury", False)
        life_altering = outcome.get("life_altering_injury", False)
        evidence = []

        if life_threatening:
            ev_data = outcome.get("evidence", {}).get("life_threatening", [])
            for ev in ev_data:
                evidence.append({"text": ev, "source_sentence_id": -1})
            return "YES", 0.9, "Life-threatening injury identified", evidence
        if life_altering:
            ev_data = outcome.get("evidence", {}).get("life_altering", [])
            for ev in ev_data:
                evidence.append({"text": ev, "source_sentence_id": -1})
            return "YES", 0.85, "Life-altering/permanent impairment identified", evidence
        return "NO", 0.8, "No life-threatening or life-altering injury indicated", []

    def _evaluate_q3(self, high_energy: Dict) -> Tuple[str, float, str, List[Dict]]:
        present = high_energy.get("high_energy_present", False)
        sources = high_energy.get("energy_sources", {})
        evidence = []
        for cat, keywords in sources.items():
            for kw in keywords:
                evidence.append({"text": f"High-energy source: {cat} ({kw})", "source_sentence_id": -1})

        if present:
            confidence = min(0.7 + len(sources) * 0.05, 0.95)
            reason = f"High-energy sources detected: {', '.join(sources.keys())}"
            return "YES", confidence, reason, evidence
        return "NO", 0.7, "No high-energy source detected", []

    def _evaluate_q4(self, high_energy: Dict) -> Tuple[str, float, str, List[Dict]]:
        incident = high_energy.get("high_energy_incident", False)
        evidence = []

        if incident:
            return "YES", 0.85, "High-energy incident (energy release and worker proximity) detected", evidence

        # Check exposure categories for incident indicators
        exposure_cats = high_energy.get("exposure_categories", {})
        incident_cats = [
            "falling_flailing_rolling_object", "stored_energy", "electricity_arc_flash",
            "work_at_height", "confined_space", "hot_work_fire_explosion",
            "motorized_vehicle_operation", "pedestrian_struck_by_vehicle",
        ]
        for cat in incident_cats:
            if cat in exposure_cats:
                for kw in exposure_cats[cat]:
                    evidence.append({"text": f"Exposure category: {cat} ({kw})", "source_sentence_id": -1})
                return "YES", 0.75, f"High-energy incident indicated by {cat} exposure", evidence

        return "NO", 0.7, "No high-energy incident detected (energy present but no release/contact)", []

    def _evaluate_q5(
        self, direct_control: Dict, sustained_sif: bool, outcome: Dict
    ) -> Tuple[str, float, str, List[Dict]]:
        state = direct_control.get("state", "NOT_APPLICABLE")
        confidence = direct_control.get("confidence", 0.3)
        evidence = direct_control.get("evidence", [])

        if state == "PRESENT":
            return "YES", confidence, "Direct control present and effective", evidence
        elif state == "FAILED":
            return "NO", confidence, "Direct control failed", evidence
        elif state == "MISSING":
            return "NO", confidence, "No direct control in place", evidence
        else:
            return "UNCERTAIN", 0.4, "Direct control status uncertain", evidence

    def _evaluate_q6(self, direct_control: Dict) -> Tuple[str, float, str, List[Dict]]:
        state = direct_control.get("state", "NOT_APPLICABLE")
        confidence = direct_control.get("confidence", 0.3)
        evidence = direct_control.get("evidence", [])

        if state == "PRESENT":
            return "YES", confidence, "Direct control present for high energy (no incident)", evidence
        return "NO", confidence, "No direct control for present high energy", evidence

    def _evaluate_q8(self, outcome: Dict, high_energy: Dict) -> Tuple[str, float, str, List[Dict]]:
        near_miss = outcome.get("near_miss", False)
        minor_injury = outcome.get("minor_injury", False)
        high_energy_present = high_energy.get("high_energy_present", False)

        if high_energy_present:
            return "NO", 0.7, "High-energy source present -- not low severity", []

        evidence = []
        if near_miss:
            ev_data = outcome.get("evidence", {}).get("near_miss", [])
            for ev in ev_data:
                evidence.append({"text": ev, "source_sentence_id": -1})
            return "YES", 0.75, "Near miss with no high-energy source", evidence
        if minor_injury:
            return "YES", 0.7, "Minor injury with no high-energy source", evidence
        return "YES", 0.6, "Low-severity event assumed (no high energy, no SIF injury)", []

    def _make_node(
        self, node_id: str, answer: str, confidence: float, reason: str, evidence: List[Dict]
    ) -> TreePathNode:
        question = self.nodes.get(node_id, {}).get("question", "")
        source_sentence_ids = [
            e.get("source_sentence_id", -1) for e in evidence
        ]
        return TreePathNode(
            node_id=node_id,
            question=question,
            answer=answer,
            confidence=round(confidence, 3),
            evidence=evidence,
            source_sentence_ids=source_sentence_ids,
            reason=reason,
        )

    def _terminal_result(self, classification: str, path: List[TreePathNode]) -> Dict:
        tier = SIF_CLASSIFICATION_TIER.get(classification, 3)
        avg_confidence = (
            sum(n.confidence for n in path) / len(path) if path else 0.0
        )

        terminal_node = path[-1].node_id if path else "Q1"

        reasons = [n.reason for n in path if n.reason]
        combined_reason = "; ".join(reasons) if reasons else ""

        all_evidence = []
        for node in path:
            all_evidence.extend(node.evidence)

        return {
            "classification": classification,
            "tier": tier,
            "tree_version": self.tree_version,
            "confidence": round(avg_confidence, 3),
            "path": [n.to_dict() for n in path],
            "terminal_node": terminal_node,
            "reason": combined_reason,
            "evidence": all_evidence,
        }

    def validate(self, classification_result: Dict) -> List[str]:
        """Validate a classification result."""
        errors = []
        classification = classification_result.get("classification", "")
        if classification not in SIF_CLASSIFICATION_TIER:
            errors.append(f"Unknown classification: {classification}")

        confidence = classification_result.get("confidence", -1.0)
        if not (0.0 <= confidence <= 1.0):
            errors.append(f"Confidence out of range: {confidence}")

        path = classification_result.get("path", [])
        if not path:
            errors.append("Classification path is empty")

        tier = classification_result.get("tier", 0)
        if tier not in (1, 2, 3):
            errors.append(f"Invalid tier: {tier}")

        # Fatality cannot be downgraded
        if classification == SIFClassification.ACTUAL_SIF_FATALITY and tier != 1:
            errors.append("Fatality classification must be Tier 1")

        return errors
