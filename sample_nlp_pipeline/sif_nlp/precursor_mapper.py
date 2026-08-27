"""Precursor mapping module - maps extracted evidence to SIF precursors."""

from typing import Dict, List, Tuple

from .config import SIF_PRECURSORS, PrecursorStatus, SIF_PRECURSOR_LABELS, PRECURSOR_ENCODING


class PrecursorMapper:
    """Maps extracted evidence to the 13 SIF precursor categories."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS

    def _compute_status(
        self, present_evidence: List[Dict], absent_evidence: List[Dict]
    ) -> Tuple[int, float, int]:
        present_count = len(present_evidence)
        absent_count = len(absent_evidence)
        total_evidence = present_count + absent_count

        if total_evidence == 0:
            return PrecursorStatus.NOT_MENTIONED, 0.0, 0

        if present_count > 0 and absent_count > 0:
            if present_count >= absent_count:
                confidence = present_count / total_evidence
                return PrecursorStatus.AMBIGUOUS, min(confidence + 0.1, 1.0), total_evidence
            else:
                confidence = absent_count / total_evidence
                return PrecursorStatus.AMBIGUOUS, min(confidence + 0.1, 1.0), total_evidence

        if present_count > 0:
            if present_count >= 2:
                confidence = min(0.7 + (present_count * 0.05), 0.95)
            else:
                confidence = 0.6
            return PrecursorStatus.PRESENT, confidence, present_count

        if absent_count > 0:
            if absent_count >= 2:
                confidence = min(0.7 + (absent_count * 0.05), 0.95)
            else:
                confidence = 0.6
            return PrecursorStatus.ABSENT, confidence, absent_count

        return PrecursorStatus.NOT_MENTIONED, 0.0, 0

    def map_precursors(self, extracted_evidence: Dict) -> Dict[str, Dict]:
        precursor_evidence = extracted_evidence["precursor_evidence"]
        results = {}
        for precursor in self.precursors:
            evidence_data = precursor_evidence.get(
                precursor, {"present": [], "absent": []}
            )
            present = evidence_data.get("present", [])
            absent = evidence_data.get("absent", [])
            status, confidence, evidence_count = self._compute_status(present, absent)
            results[precursor] = {
                "precursor": SIF_PRECURSOR_LABELS[precursor],
                "status": status,
                "status_label": PRECURSOR_ENCODING[status],
                "confidence": round(confidence, 3),
                "evidence_count": evidence_count,
                "present_evidence": present,
                "absent_evidence": absent,
            }
        return results

    def get_precursor_summary(self, mapped_precursors: Dict) -> str:
        lines = ["SIF Precursor Analysis Summary", "=" * 40]
        for precursor_key, data in mapped_precursors.items():
            label = data["precursor"]
            status = data["status_label"]
            confidence = data["confidence"]
            count = data["evidence_count"]
            lines.append(
                f"  {label}: {status} (confidence={confidence:.2f}, evidence={count})"
            )
        return "\n".join(lines)
