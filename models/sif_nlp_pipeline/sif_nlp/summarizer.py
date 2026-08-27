"""Summarization module - generates human-readable SIF-focused summary.

Unified tree output with clusters, density, consistency, and direct control sections.
"""

from typing import Dict, List, Optional

from .config import (
    SIF_PRECURSORS,
    PRECURSOR_ENCODING,
    SIF_PRECURSOR_LABELS,
    IOGP_LSR_RULE_LABELS,
    IOGP_LSR_RULES,
    PRECURSOR_CLUSTERS,
    CLUSTER_LABELS,
    LSRStatus,
)


class SIFSummarizer:
    """Generates concise SIF-focused summaries from mapped precursor evidence."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS
        self.clusters = PRECURSOR_CLUSTERS

    def _format_precursor_section(self, mapped_precursors: Dict) -> str:
        lines = ["SIF Precursor Analysis", "-" * 40]
        present = []
        absent = []
        ambiguous = []
        not_mentioned = []
        not_applicable = []
        for precursor_key in self.precursors:
            data = mapped_precursors.get(precursor_key, {})
            label = SIF_PRECURSOR_LABELS[precursor_key]
            status = data.get("status", 0)
            confidence = data.get("confidence", 0.0)
            count = data.get("evidence_count", 0)
            strength = data.get("evidence_strength", 0.0)
            entry = (
                f"  {label}: {PRECURSOR_ENCODING[status]} "
                f"(confidence={confidence:.2f}, evidence_count={count}, "
                f"strength={strength:.2f})"
            )
            if status == 3:
                present.append(entry)
            elif status == 1:
                absent.append(entry)
            elif status == 2:
                ambiguous.append(entry)
            elif status == -1:
                not_applicable.append(entry)
            else:
                not_mentioned.append(entry)
        if present:
            lines.append("\n  PRESENT:")
            lines.extend(present)
        if absent:
            lines.append("\n  ABSENT:")
            lines.extend(absent)
        if ambiguous:
            lines.append("\n  AMBIGUOUS:")
            lines.extend(ambiguous)
        if not_applicable:
            lines.append("\n  NOT APPLICABLE:")
            lines.extend(not_applicable)
        if not_mentioned:
            lines.append("\n  NOT MENTIONED:")
            lines.extend(not_mentioned)
        return "\n".join(lines)

    def _format_cluster_section(self, cluster_results: Dict) -> str:
        lines = ["Precursor Cluster Analysis", "-" * 40]
        for cluster_name, cluster_data in cluster_results.items():
            label = cluster_data.get("label", cluster_name)
            contribution = cluster_data.get("contribution_score", 0.0)
            density = cluster_data.get("density", 0.0)
            coverage = cluster_data.get("evidence_coverage", 0.0)
            present = cluster_data.get("present_count", 0)
            applicable = cluster_data.get("applicable_count", 0)
            lines.append(
                f"  {label}: density={density:.2f}, "
                f"contribution={contribution:.3f}, "
                f"evidence_coverage={coverage:.2f}, "
                f"present={present}/{applicable}"
            )
        return "\n".join(lines)

    def _format_density_section(self, density_data: Dict) -> str:
        lines = ["Precursor Density", "-" * 40]
        lines.append(f"  Raw density: {density_data.get('raw', 0.0):.3f}")
        lines.append(f"  Evidence-weighted density: {density_data.get('evidence_weighted', 0.0):.3f}")
        lines.append(
            f"  Applicable precursors: {density_data.get('applicable_precursor_count', 0)}"
        )
        lines.append(
            f"  Present precursors: {density_data.get('present_precursor_count', 0)}"
        )
        return "\n".join(lines)

    def _format_high_energy_section(self, extracted_evidence: Dict) -> str:
        lines = ["High-Energy Analysis", "-" * 40]
        high_energy = extracted_evidence.get("high_energy", {})
        he_present = high_energy.get("high_energy_present", False)
        he_incident = high_energy.get("high_energy_incident", False)
        lines.append(f"  High energy present: {'YES' if he_present else 'NO'}")
        lines.append(f"  High energy incident: {'YES' if he_incident else 'NO'}")

        sources = high_energy.get("energy_sources", {})
        if sources:
            lines.append(f"  Energy sources: {', '.join(sources.keys())}")
        exposure = high_energy.get("exposure_categories", {})
        if exposure:
            lines.append(f"  Exposure categories: {', '.join(exposure.keys())}")
        return "\n".join(lines)

    def _format_direct_control_section(self, extracted_evidence: Dict) -> str:
        lines = ["Direct Control Assessment", "-" * 40]
        dc = extracted_evidence.get("direct_control", {})
        state = dc.get("state", "NOT_APPLICABLE")
        confidence = dc.get("confidence", 0.0)
        lines.append(f"  State: {state}")
        lines.append(f"  Confidence: {confidence:.2f}")
        evidence = dc.get("evidence", [])
        if evidence:
            lines.append("  Evidence:")
            for ev in evidence[:3]:
                text = ev.get("text", "")[:200]
                lines.append(f'    - "{text}"')
        return "\n".join(lines)

    def _format_classification_section(self, classification_result: Dict) -> str:
        lines = ["Unified SIF Classification Tree", "-" * 40]
        classification = classification_result.get("classification", "")
        tier = classification_result.get("tier", 3)
        confidence = classification_result.get("confidence", 0.0)
        tree_version = classification_result.get("tree_version", "")
        lines.append(f"  Classification: {classification}")
        lines.append(f"  Tier: {tier}")
        lines.append(f"  Tree confidence: {confidence:.2f}")
        lines.append(f"  Tree version: {tree_version}")

        path = classification_result.get("path", [])
        if path:
            lines.append("\n  Classification Path:")
            for node in path:
                node_id = node.get("node_id", "")
                question = node.get("question", "")
                answer = node.get("answer", "")
                node_conf = node.get("confidence", 0.0)
                reason = node.get("reason", "")
                lines.append(
                    f"    {node_id}: {question}"
                )
                lines.append(
                    f"      -> {answer} (confidence={node_conf:.2f})"
                )
                if reason:
                    lines.append(f"      Reason: {reason}")
        return "\n".join(lines)

    def _format_consistency_section(self, consistency_features: Dict) -> str:
        lines = ["Model Consistency", "-" * 40]
        hazard_c = consistency_features.get("hazard_consistency", 0.5)
        barrier_c = consistency_features.get("barrier_consistency", 0.5)
        energy_c = consistency_features.get("energy_consistency", 0.5)
        overall_c = consistency_features.get("intra_model_consistency", 0.5)
        lines.append(f"  Hazard consistency: {hazard_c:.2f}")
        lines.append(f"  Barrier consistency: {barrier_c:.2f}")
        lines.append(f"  Energy consistency: {energy_c:.2f}")
        lines.append(f"  Overall consistency: {overall_c:.2f}")
        return "\n".join(lines)

    def _format_evidence_section(self, mapped_precursors: Dict) -> str:
        lines = ["Supporting Evidence Details", "-" * 40]
        for precursor_key in self.precursors:
            data = mapped_precursors.get(precursor_key, {})
            label = SIF_PRECURSOR_LABELS[precursor_key]
            present_ev = data.get("present_evidence", [])
            absent_ev = data.get("absent_evidence", [])
            if present_ev:
                lines.append(f"\n  {label} - Evidence of presence:")
                for ev in present_ev[:3]:
                    text = ev["text"][:200]
                    lines.append(f'    - "{text}"')
            if absent_ev:
                lines.append(f"\n  {label} - Evidence of absence:")
                for ev in absent_ev[:3]:
                    text = ev["text"][:200]
                    lines.append(f'    - "{text}"')
        return "\n".join(lines)

    def _format_hazard_section(self, extracted_evidence: Dict) -> str:
        hazards = extracted_evidence.get("hazards", [])
        if not hazards:
            return "No specific hazards identified in the report."
        lines = ["Identified Hazards", "-" * 40]
        for h in hazards:
            lines.append(f'  - {h["hazard_type"]}: {", ".join(h["evidence"][:3])}')
        return "\n".join(lines)

    def _format_work_changes(self, extracted_evidence: Dict) -> str:
        changes = extracted_evidence.get("work_changes", {})
        active_changes = [k for k, v in changes.items() if v]
        if not active_changes:
            return "No notable work condition changes identified."
        lines = ["Work Condition Changes", "-" * 40]
        for change in active_changes:
            label = change.replace("_", " ").title()
            lines.append(f"  - {label}")
        return "\n".join(lines)

    def _format_lsr_section(self, lsr_result: Optional[Dict]) -> str:
        if lsr_result is None:
            return ""

        lines = ["IOGP REPORT 459 LIFE-SAVING RULES", "-" * 40]
        lines.append("")

        broken = []
        not_broken = []
        uncertain = []
        not_applicable = []

        analysis = lsr_result.get("analysis", [])
        for entry in analysis:
            rule_name = entry.get("rule_name", "")
            status = entry.get("status", "")
            if status == LSRStatus.BROKEN:
                broken.append(rule_name)
            elif status == LSRStatus.NOT_BROKEN:
                not_broken.append(rule_name)
            elif status == LSRStatus.UNCERTAIN:
                uncertain.append(rule_name)
            else:
                not_applicable.append(rule_name)

        if broken:
            lines.append("Broken / Not Followed:")
            for r in broken:
                lines.append(f"  - {r}")
            lines.append("")

        if uncertain:
            lines.append("Uncertain:")
            for r in uncertain:
                lines.append(f"  - {r}")
            lines.append("")

        if not_broken:
            lines.append("Not Broken:")
            for r in not_broken:
                lines.append(f"  - {r}")
            lines.append("")

        if not_applicable:
            lines.append("Not Applicable:")
            for r in not_applicable:
                lines.append(f"  - {r}")
            lines.append("")

        return "\n".join(lines)

    def _format_sif_score_section(self, score_obj: Optional[Dict]) -> str:
        if score_obj is None:
            return ""

        lines = ["SIF SCORE", "-" * 40]
        value = score_obj.get("value", 0.0)
        method = score_obj.get("method", "unified_tree_classification")
        weight_source = score_obj.get("weight_source", "")

        lines.append(f"Score: {value:.2f} / 1.00")
        lines.append(f"Method: {method.replace('_', ' ').title()}")
        lines.append(f"Weight Source: {weight_source}")
        lines.append("")

        limitations = score_obj.get("limitations", [])
        if limitations:
            lines.append("Score limitations:")
            for lim in limitations:
                lines.append(f"  - {lim}")
            lines.append("")

        lines.append(
            f"The derived SIF score is {value:.2f} on a 0-1 scale. "
            f"This score is an evidence-based model output and should not be "
            f"interpreted as a final SIF classification."
        )

        return "\n".join(lines)

    def generate_summary(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        cluster_results: Dict,
        density_data: Dict,
        classification_result: Dict,
        score_obj: Dict,
        consistency_features: Dict,
        lsr_result: Optional[Dict] = None,
    ) -> str:
        sections = []
        sections.append(f"SIF Analysis Report: {incident_id}")
        sections.append("=" * 50)
        sections.append("")

        sections.append("Report Overview")
        sections.append("-" * 40)
        sections.append(
            f"  Report length: {preprocessed_data.get('report_length', 0)} characters"
        )
        sections.append(
            f"  Sentences analyzed: {preprocessed_data.get('sentence_count', 0)}"
        )
        sections.append("")

        sections.append(self._format_classification_section(classification_result))
        sections.append("")
        sections.append(self._format_high_energy_section(extracted_evidence))
        sections.append("")
        sections.append(self._format_direct_control_section(extracted_evidence))
        sections.append("")
        sections.append(self._format_precursor_section(mapped_precursors))
        sections.append("")
        sections.append(self._format_cluster_section(cluster_results))
        sections.append("")
        sections.append(self._format_density_section(density_data))
        sections.append("")
        sections.append(self._format_consistency_section(consistency_features))
        sections.append("")
        sections.append(self._format_evidence_section(mapped_precursors))
        sections.append("")
        sections.append(self._format_hazard_section(extracted_evidence))
        sections.append("")
        sections.append(self._format_work_changes(extracted_evidence))

        present_count = sum(
            1
            for p in self.precursors
            if mapped_precursors.get(p, {}).get("status", 0) == 3
        )
        sections.append("")
        sections.append("Summary Assessment")
        sections.append("-" * 40)
        sections.append(
            f"  {present_count} of {len(self.precursors)} SIF precursors detected as PRESENT."
        )
        classification = classification_result.get("classification", "")
        tier = classification_result.get("tier", 3)
        sections.append(f"  Unified Tree Classification: {classification} (Tier {tier})")
        sections.append(f"  High-energy present: {'YES' if extracted_evidence.get('high_energy', {}).get('high_energy_present') else 'NO'}")

        lsr_section = self._format_lsr_section(lsr_result)
        if lsr_section:
            sections.append("")
            sections.append(lsr_section)

        score_section = self._format_sif_score_section(score_obj)
        if score_section:
            sections.append("")
            sections.append(score_section)

        return "\n".join(sections)

    def generate_analysis_json(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        cluster_results: Dict,
        density_data: Dict,
        interaction_results: Dict,
        classification_result: Dict,
        score_obj: Dict,
        consistency_features: Dict,
        summary: str,
        lsr_result: Optional[Dict] = None,
    ) -> Dict:
        analysis = {
            "incident_id": incident_id,
            "summary": summary,
            "metadata": preprocessed_data.get("metadata", {}),
            "report_statistics": {
                "report_length": preprocessed_data.get("report_length", 0),
                "sentence_count": preprocessed_data.get("sentence_count", 0),
            },
            "unified_tree": classification_result,
            "high_energy": extracted_evidence.get("high_energy", {}),
            "direct_control": extracted_evidence.get("direct_control", {}),
            "outcome": extracted_evidence.get("outcome", {}),
            "two_if_test": extracted_evidence.get("two_if_test", {}),
            "precursor_analysis": {},
            "cluster_analysis": cluster_results,
            "density": density_data,
            "interaction_features": interaction_results,
            "consistency": consistency_features,
            "hazards": extracted_evidence.get("hazards", []),
            "task_types": extracted_evidence.get("task_types", []),
            "controls": extracted_evidence.get("controls", {}),
            "environment": extracted_evidence.get("environment", {}),
            "work_changes": extracted_evidence.get("work_changes", {}),
            "worker_info": extracted_evidence.get("worker_info", {}),
        }
        for precursor_key in self.precursors:
            data = mapped_precursors.get(precursor_key, {})
            analysis["precursor_analysis"][precursor_key] = {
                "precursor": SIF_PRECURSOR_LABELS[precursor_key],
                "status": PRECURSOR_ENCODING[data.get("status", 0)],
                "confidence": data.get("confidence", 0.0),
                "evidence_count": data.get("evidence_count", 0),
                "evidence_strength": data.get("evidence_strength", 0.0),
                "present_evidence": [
                    {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                    for e in data.get("present_evidence", [])
                ],
                "absent_evidence": [
                    {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                    for e in data.get("absent_evidence", [])
                ],
            }

        if lsr_result is not None:
            analysis["life_saving_rules"] = {
                "broken_rule_count": lsr_result.get("broken_rule_count", 0),
                "broken_rules": lsr_result.get("broken_rules", []),
                "analysis": [
                    {
                        "rule_name": entry["rule_name"],
                        "status": entry["status"],
                        "confidence": entry["confidence"],
                        "reason": entry.get("reason", ""),
                        "evidence": entry.get("evidence", []),
                    }
                    for entry in lsr_result.get("analysis", [])
                ],
            }
        else:
            analysis["life_saving_rules"] = {
                "broken_rule_count": 0,
                "broken_rules": [],
                "analysis": [],
            }

        if score_obj is not None:
            analysis["sif_score"] = score_obj
        else:
            analysis["sif_score"] = {
                "value": 0.0,
                "range": [0.0, 1.0],
                "method": "unified_tree_classification",
                "weight_source": "",
                "components": [],
                "missing_components": [],
                "limitations": [],
            }

        return analysis
