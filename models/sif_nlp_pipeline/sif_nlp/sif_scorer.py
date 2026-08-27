"""Continuous SIF score engine using weighted-sum formulation."""

from typing import Dict, List, Optional

from .config import (
    SIF_PRECURSORS,
    DEFAULT_SIF_SCORE_WEIGHTS,
    SIF_SCORE_COMPONENTS,
    LSRStatus,
    PRECURSOR_ENCODING,
)


class SIFScorer:
    """Calculates a continuous SIF score [0, 1] using weighted-sum methodology."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        weight_source: str = "fallback_project_weights",
    ):
        if weights is not None:
            self.weights = weights
            self.weight_source = "configured_domain_weights"
        else:
            self.weights = dict(DEFAULT_SIF_SCORE_WEIGHTS)
            self.weight_source = weight_source

    def _compute_severity_or_potential_consequence(
        self,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
    ) -> float:
        hazards = extracted_evidence.get("hazards", [])
        hazard_count = len(hazards)
        high_energy_hazards = {"electrical_hazard", "fall_hazard", "stored_energy_hazard"}
        high_energy_count = sum(
            1 for h in hazards if h.get("hazard_type", "") in high_energy_hazards
        )

        precursor_scores = []
        for prec in SIF_PRECURSORS:
            data = mapped_precursors.get(prec, {})
            status = data.get("status", 0)
            conf = data.get("confidence", 0.0)
            if status == 3:
                precursor_scores.append(conf)

        base = 0.0
        if hazard_count > 0:
            base += min(hazard_count * 0.15, 0.40)
        if high_energy_count > 0:
            base += min(high_energy_count * 0.15, 0.30)
        if precursor_scores:
            avg_precursor_conf = sum(precursor_scores) / len(precursor_scores)
            base += min(avg_precursor_conf * 0.30, 0.30)

        return min(base, 1.0)

    def _compute_hazard_energy_exposure(
        self,
        extracted_evidence: Dict,
    ) -> float:
        hazards = extracted_evidence.get("hazards", [])
        if not hazards:
            return 0.0

        high_energy_keywords = {
            "electrical_hazard",
            "stored_energy_hazard",
            "fall_hazard",
        }
        score = 0.0
        for h in hazards:
            htype = h.get("hazard_type", "")
            if htype in high_energy_keywords:
                score += 0.25
            else:
                score += 0.10

        controls = extracted_evidence.get("controls", {})
        control_failed = controls.get("control_failed", [])
        if control_failed:
            score += 0.15

        return min(score, 1.0)

    def _compute_barrier_or_control_failure(
        self,
        extracted_evidence: Dict,
    ) -> float:
        controls = extracted_evidence.get("controls", {})
        present = controls.get("control_present", [])
        missing = controls.get("control_missing", [])
        failed = controls.get("control_failed", [])

        if not present and not missing and not failed:
            return 0.0

        total = len(present) + len(missing) + len(failed)
        if total == 0:
            return 0.0

        failure_score = (len(missing) * 0.4 + len(failed) * 0.6) / total
        return min(failure_score, 1.0)

    def _compute_critical_rule_violation(
        self,
        lsr_result: Optional[Dict],
    ) -> float:
        if lsr_result is None:
            return 0.0

        analysis = lsr_result.get("analysis", [])
        broken_count = sum(
            1 for a in analysis if a.get("status") == LSRStatus.BROKEN
        )
        uncertain_count = sum(
            1 for a in analysis if a.get("status") == LSRStatus.UNCERTAIN
        )

        score = broken_count * 0.20 + uncertain_count * 0.05
        return min(score, 1.0)

    def _compute_sif_precursor_signal(
        self,
        mapped_precursors: Dict,
    ) -> float:
        present_scores = []
        for prec in SIF_PRECURSORS:
            data = mapped_precursors.get(prec, {})
            status = data.get("status", 0)
            conf = data.get("confidence", 0.0)
            evidence_count = data.get("evidence_count", 0)

            if status == 3:
                weight_factor = 1.0 + min(evidence_count * 0.05, 0.20)
                present_scores.append(conf * weight_factor)
            elif status == 2:
                present_scores.append(conf * 0.4)

        if not present_scores:
            return 0.0

        aggregated = sum(present_scores) / len(SIF_PRECURSORS)
        return min(aggregated, 1.0)

    def _compute_evidence_strength(
        self,
        extracted_evidence: Dict,
        preprocessed_data: Dict,
    ) -> float:
        total_sentences = preprocessed_data.get("sentence_count", 0)
        if total_sentences == 0:
            return 0.0

        relevant_count = 0
        for p_data in extracted_evidence.get("precursor_evidence", {}).values():
            for status in ["present", "absent"]:
                relevant_count += len(p_data.get(status, []))

        ratio = relevant_count / total_sentences if total_sentences > 0 else 0.0
        return min(ratio, 1.0)

    def _compute_extraction_confidence(
        self,
        mapped_precursors: Dict,
    ) -> float:
        confidences = []
        for prec in SIF_PRECURSORS:
            data = mapped_precursors.get(prec, {})
            status = data.get("status", 0)
            if status != 0:
                confidences.append(data.get("confidence", 0.0))

        if not confidences:
            return 0.0

        return sum(confidences) / len(confidences)

    def compute_score(
        self,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        lsr_result: Optional[Dict] = None,
    ) -> Dict:
        raw_components = {
            "severity_or_potential_consequence": self._compute_severity_or_potential_consequence(
                extracted_evidence, mapped_precursors
            ),
            "hazard_energy_exposure": self._compute_hazard_energy_exposure(
                extracted_evidence
            ),
            "barrier_or_control_failure": self._compute_barrier_or_control_failure(
                extracted_evidence
            ),
            "critical_rule_violation": self._compute_critical_rule_violation(
                lsr_result
            ),
            "sif_precursor_signal": self._compute_sif_precursor_signal(
                mapped_precursors
            ),
            "evidence_strength": self._compute_evidence_strength(
                extracted_evidence, preprocessed_data
            ),
            "extraction_confidence": self._compute_extraction_confidence(
                mapped_precursors
            ),
        }

        missing_components = []
        available_components = {}
        for comp_name, comp_value in raw_components.items():
            if comp_name in self.weights:
                available_components[comp_name] = {
                    "value": comp_value,
                    "weight": self.weights[comp_name],
                }
            else:
                missing_components.append(comp_name)

        total_available_weight = sum(
            c["weight"] for c in available_components.values()
        )

        if total_available_weight == 0:
            score = 0.0
        else:
            contributions = []
            for comp_name, comp_data in available_components.items():
                normalized_weight = comp_data["weight"] / total_available_weight
                contribution = comp_data["value"] * normalized_weight
                contributions.append(contribution)
            score = sum(contributions)

        score = max(0.0, min(1.0, score))

        component_details = []
        for comp_name, comp_data in available_components.items():
            normalized_weight = comp_data["weight"] / total_available_weight
            contribution = comp_data["value"] * normalized_weight
            component_details.append({
                "name": comp_name,
                "value": round(comp_data["value"], 4),
                "weight": round(normalized_weight, 4),
                "contribution": round(contribution, 4),
            })

        limitations = []
        if missing_components:
            limitations.append(
                f"Missing components excluded: {', '.join(missing_components)}"
            )

        score_explanation = {
            "value": round(score, 4),
            "range": [0.0, 1.0],
            "method": "weighted_sum",
            "weight_source": self.weight_source,
            "components": component_details,
            "missing_components": missing_components,
            "limitations": limitations,
        }

        return score_explanation

    def validate(self, score_obj: Dict) -> List[str]:
        errors = []
        value = score_obj.get("value", -1.0)
        if not (0.0 <= value <= 1.0):
            errors.append(f"SIF score value out of range: {value}")

        components = score_obj.get("components", [])
        for comp in components:
            comp_value = comp.get("value", -1.0)
            comp_weight = comp.get("weight", -1.0)
            if not (0.0 <= comp_value <= 1.0):
                errors.append(
                    f"Component {comp['name']} value out of range: {comp_value}"
                )
            if comp_weight < 0:
                errors.append(
                    f"Component {comp['name']} weight is negative: {comp_weight}"
                )

        total_weight = sum(c.get("weight", 0) for c in components)
        if components and abs(total_weight - 1.0) > 0.01:
            errors.append(f"Active weights do not sum to 1.0: {total_weight}")

        total_contribution = sum(c.get("contribution", 0) for c in components)
        if components and abs(total_contribution - value) > 0.01:
            errors.append(
                f"Sum of contributions ({total_contribution:.4f}) "
                f"does not equal score ({value:.4f})"
            )

        if score_obj.get("weight_source", "") == "":
            errors.append("weight_source is not recorded")

        return errors
