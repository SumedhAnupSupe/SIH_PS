"""Precursor mapping module - maps extracted evidence to SIF precursors.

Extended from 13 EEI precursors to 22 total (13 EEI + 9 oil-and-gas).
Includes cluster aggregation, density calculations, and evidence-strength scoring.
"""

from typing import Dict, List, Tuple

from .config import (
    SIF_PRECURSORS,
    EEI_PRECURSORS,
    OG_PRECURSORS,
    PrecursorStatus,
    SIF_PRECURSOR_LABELS,
    PRECURSOR_ENCODING,
    PRECURSOR_CLUSTERS,
    DEFAULT_PRECURSOR_SEVERITY_WEIGHTS,
    PRECURSOR_INTERACTIONS,
    CLUSTER_LABELS,
)


class PrecursorMapper:
    """Maps extracted evidence to the 22 SIF precursor categories."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS
        self.clusters = PRECURSOR_CLUSTERS
        self.severity_weights = DEFAULT_PRECURSOR_SEVERITY_WEIGHTS

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

    def _compute_evidence_strength(
        self, present_evidence: List[Dict], absent_evidence: List[Dict]
    ) -> float:
        """Compute evidence strength as ratio of evidence to total sentences.

        Returns a value in [0, 1] reflecting how much evidence was found.
        """
        total = len(present_evidence) + len(absent_evidence)
        if total == 0:
            return 0.0
        # More evidence relative to a typical report -> stronger
        return min(total / 10.0, 1.0)

    def map_precursors(self, extracted_evidence: Dict) -> Dict[str, Dict]:
        precursor_evidence = extracted_evidence["precursor_evidence"]
        equipment_evidence = extracted_evidence.get("equipment_evidence", [])

        # Merge equipment evidence into relevant precursors
        enhanced_evidence = dict(precursor_evidence)
        for prec in OG_PRECURSORS:
            if prec not in enhanced_evidence:
                enhanced_evidence[prec] = {"present": [], "absent": []}

        # Map equipment evidence to equipment-cluster precursors
        for eq in equipment_evidence:
            eq_type = eq.get("evidence_type", "")
            if eq_type in ("equipment_malfunction", "mechanical_electrical_failure", "guarding_failure",
                           "instrumentation_alarm_failure"):
                for ev in eq.get("evidence", []):
                    evidence_item = {"text": ev, "source_sentence_id": -1, "matched_pattern": f"equipment_{eq_type}"}
                    if "critical_control_failure" in enhanced_evidence:
                        enhanced_evidence["critical_control_failure"]["present"].append(evidence_item)

        results = {}
        for precursor in self.precursors:
            evidence_data = enhanced_evidence.get(
                precursor, {"present": [], "absent": []}
            )
            present = evidence_data.get("present", [])
            absent = evidence_data.get("absent", [])
            status, confidence, evidence_count = self._compute_status(present, absent)
            evidence_strength = self._compute_evidence_strength(present, absent)
            results[precursor] = {
                "precursor": SIF_PRECURSOR_LABELS[precursor],
                "status": status,
                "status_label": PRECURSOR_ENCODING[status],
                "confidence": round(confidence, 3),
                "evidence_count": evidence_count,
                "present_evidence": present,
                "absent_evidence": absent,
                "evidence_strength": round(evidence_strength, 3),
            }
        return results

    def compute_clusters(self, mapped_precursors: Dict) -> Dict[str, Dict]:
        """Compute cluster scores, density, and evidence coverage."""
        cluster_results = {}
        for cluster_name, cluster_precursors in self.clusters.items():
            cluster_data = {
                "label": CLUSTER_LABELS[cluster_name],
                "contribution_score": 0.0,
                "density": 0.0,
                "evidence_coverage": 0.0,
                "present_count": 0,
                "applicable_count": 0,
                "members": [],
            }

            scores = []
            present_in_cluster = 0
            applicable_in_cluster = 0
            total_evidence_in_cluster = 0

            for prec in cluster_precursors:
                data = mapped_precursors.get(prec, {})
                status = data.get("status", 0)
                confidence = data.get("confidence", 0.0)
                evidence_strength = data.get("evidence_strength", 0.0)
                severity = self.severity_weights.get(prec, 1.0)

                member = {
                    "precursor": prec,
                    "label": SIF_PRECURSOR_LABELS.get(prec, prec),
                    "status": status,
                    "status_label": PRECURSOR_ENCODING.get(status, "UNKNOWN"),
                    "confidence": confidence,
                    "evidence_strength": evidence_strength,
                }
                cluster_data["members"].append(member)

                if status == PrecursorStatus.NOT_APPLICABLE:
                    continue

                applicable_in_cluster += 1

                if status == PrecursorStatus.PRESENT:
                    present_in_cluster += 1
                    score = severity * confidence * (1.0 + evidence_strength)
                    scores.append(score)
                elif status == PrecursorStatus.AMBIGUOUS:
                    scores.append(severity * confidence * 0.4 * (1.0 + evidence_strength))

                total_evidence_in_cluster += evidence_strength

            cluster_data["present_count"] = present_in_cluster
            cluster_data["applicable_count"] = applicable_in_cluster

            if applicable_in_cluster > 0:
                cluster_data["contribution_score"] = round(
                    sum(scores) / applicable_in_cluster, 4
                )
                cluster_data["density"] = round(
                    present_in_cluster / applicable_in_cluster, 4
                )
            else:
                cluster_data["contribution_score"] = 0.0
                cluster_data["density"] = 0.0

            if applicable_in_cluster > 0:
                cluster_data["evidence_coverage"] = round(
                    total_evidence_in_cluster / applicable_in_cluster, 4
                )
            else:
                cluster_data["evidence_coverage"] = 0.0

            cluster_results[cluster_name] = cluster_data

        return cluster_results

    def compute_density(self, mapped_precursors: Dict) -> Dict:
        """Compute precursor density metrics."""
        present_count = 0
        applicable_count = 0
        weighted_strength_sum = 0.0
        weighted_applicable_sum = 0.0

        for prec in self.precursors:
            data = mapped_precursors.get(prec, {})
            status = data.get("status", 0)
            confidence = data.get("confidence", 0.0)
            evidence_strength = data.get("evidence_strength", 0.0)
            severity = self.severity_weights.get(prec, 1.0)

            if status == PrecursorStatus.NOT_APPLICABLE:
                continue

            applicable_count += 1

            if status == PrecursorStatus.PRESENT:
                present_count += 1
                precursor_strength = severity * confidence * evidence_strength
                weighted_strength_sum += precursor_strength
            elif status == PrecursorStatus.AMBIGUOUS:
                precursor_strength = severity * confidence * 0.4 * evidence_strength
                weighted_strength_sum += precursor_strength

            weighted_applicable_sum += severity

        raw_density = present_count / applicable_count if applicable_count > 0 else 0.0
        evidence_weighted_density = (
            weighted_strength_sum / weighted_applicable_sum if weighted_applicable_sum > 0 else 0.0
        )

        return {
            "raw": round(min(raw_density, 1.0), 4),
            "evidence_weighted": round(min(evidence_weighted_density, 1.0), 4),
            "applicable_precursor_count": applicable_count,
            "present_precursor_count": present_count,
            "evidence_strength": round(
                sum(d.get("evidence_strength", 0) for d in mapped_precursors.values()) / max(len(mapped_precursors), 1),
                4,
            ),
        }

    def compute_high_energy_density(
        self,
        mapped_precursors: Dict,
        high_energy_data: Dict,
        cluster_results: Dict,
    ) -> float:
        """Compute high-energy conditional density.

        high_energy_density = evidence_weighted_density * high_energy_factor * barrier_degradation_factor
        """
        density = self.compute_density(mapped_precursors)
        ewd = density["evidence_weighted"]

        high_energy_present = high_energy_data.get("high_energy_present", False)
        high_energy_factor = 1.2 if high_energy_present else 0.8

        barrier_data = cluster_results.get("barrier", {})
        barrier_density = barrier_data.get("density", 0.0)
        barrier_degradation_factor = 1.0 + barrier_density * 0.5

        conditional_density = ewd * high_energy_factor * barrier_degradation_factor
        return round(min(conditional_density, 1.0), 4)

    def compute_interactions(self, mapped_precursors: Dict) -> Dict[str, float]:
        """Compute precursor interaction features."""
        interactions = {}
        for inter_name, left_prec, right_prec in PRECURSOR_INTERACTIONS:
            left_status = mapped_precursors.get(left_prec, {}).get("status", 0)
            right_status = mapped_precursors.get(right_prec, {}).get("status", 0)

            left_present = 1.0 if left_status == PrecursorStatus.PRESENT else (
                0.5 if left_status == PrecursorStatus.AMBIGUOUS else 0.0
            )
            right_present = 1.0 if right_status == PrecursorStatus.PRESENT else (
                0.5 if right_status == PrecursorStatus.AMBIGUOUS else 0.0
            )

            interactions[inter_name] = round(left_present * right_present, 4)

        return interactions

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
