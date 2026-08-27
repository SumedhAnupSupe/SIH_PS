"""Summarization module - generates human-readable SIF-focused summary."""

from typing import Dict, List

from .config import SIF_PRECURSORS, PRECURSOR_ENCODING, SIF_PRECURSOR_LABELS


class SIFSummarizer:
    """Generates concise SIF-focused summaries from mapped precursor evidence."""

    def __init__(self):
        self.precursors = SIF_PRECURSORS

    def _format_precursor_section(self, mapped_precursors: Dict) -> str:
        lines = ["SIF Precursor Analysis", "-" * 40]
        present = []
        absent = []
        ambiguous = []
        not_mentioned = []
        for precursor_key in self.precursors:
            data = mapped_precursors.get(precursor_key, {})
            label = SIF_PRECURSOR_LABELS[precursor_key]
            status = data.get("status", 0)
            confidence = data.get("confidence", 0.0)
            count = data.get("evidence_count", 0)
            entry = f"  {label}: {PRECURSOR_ENCODING[status]} (confidence={confidence:.2f}, evidence_count={count})"
            if status == 3:
                present.append(entry)
            elif status == 1:
                absent.append(entry)
            elif status == 2:
                ambiguous.append(entry)
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
        if not_mentioned:
            lines.append("\n  NOT MENTIONED:")
            lines.extend(not_mentioned)
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
                    lines.append(f"    - \"{text}\"")
            if absent_ev:
                lines.append(f"\n  {label} - Evidence of absence:")
                for ev in absent_ev[:3]:
                    text = ev["text"][:200]
                    lines.append(f"    - \"{text}\"")
        return "\n".join(lines)

    def _format_hazard_section(self, extracted_evidence: Dict) -> str:
        hazards = extracted_evidence.get("hazards", [])
        if not hazards:
            return "No specific hazards identified in the report."
        lines = ["Identified Hazards", "-" * 40]
        for h in hazards:
            lines.append(f"  - {h['hazard_type']}: {', '.join(h['evidence'][:3])}")
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

    def _format_lsr_section(self, lsr_analysis: Dict) -> str:
        if not lsr_analysis or not lsr_analysis.get("analysis"):
            return "Life-Saving Rules analysis not available."
        lines = ["Life-Saving Rules (IOGP)", "-" * 40]
        broken = lsr_analysis.get("broken_rule_count", 0)
        uncertain = lsr_analysis.get("uncertain_count", 0)
        not_broken = lsr_analysis.get("not_broken_count", 0)
        not_applicable = lsr_analysis.get("not_applicable_count", 0)
        lines.append(f"  Broken: {broken} | Uncertain: {uncertain} | Not Broken: {not_broken} | Not Applicable: {not_applicable}")
        for rule in lsr_analysis.get("analysis", []):
            if rule["status"] in ("BROKEN", "UNCERTAIN"):
                lines.append(f"  {rule['rule_id']}: {rule['rule_name']} — {rule['status']} (conf={rule['confidence']:.2f}) — {rule['reason']}")
        return "\n".join(lines)

    def generate_summary(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        lsr_analysis: Dict = None,
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

        sections.append(self._format_precursor_section(mapped_precursors))
        sections.append("")
        sections.append(self._format_evidence_section(mapped_precursors))
        sections.append("")
        sections.append(self._format_hazard_section(extracted_evidence))
        sections.append("")
        sections.append(self._format_work_changes(extracted_evidence))
        sections.append("")
        sections.append(self._format_lsr_section(lsr_analysis or {}))

        present_count = sum(
            1
            for p in self.precursors
            if mapped_precursors.get(p, {}).get("status", 0) == 3
        )
        sections.append("")
        sections.append("Summary Assessment")
        sections.append("-" * 40)
        sections.append(
            f"  {present_count} of 13 SIF precursors detected as PRESENT."
        )
        if present_count >= 5:
            sections.append(
                "  Assessment: HIGH SIF precursor density. Multiple risk indicators identified."
            )
        elif present_count >= 3:
            sections.append(
                "  Assessment: MODERATE SIF precursor density. Several risk indicators present."
            )
        elif present_count >= 1:
            sections.append(
                "  Assessment: LOW SIF precursor density. Some risk indicators present."
            )
        else:
            sections.append(
                "  Assessment: MINIMAL SIF precursor evidence detected."
            )

        return "\n".join(sections)

    def generate_analysis_json(
        self,
        incident_id: str,
        preprocessed_data: Dict,
        extracted_evidence: Dict,
        mapped_precursors: Dict,
        summary: str,
        sif_score: Dict = None,
        lsr_analysis: Dict = None,
    ) -> Dict:
        analysis = {
            "incident_id": incident_id,
            "summary": summary,
            "metadata": preprocessed_data.get("metadata", {}),
            "report_statistics": {
                "report_length": preprocessed_data.get("report_length", 0),
                "sentence_count": preprocessed_data.get("sentence_count", 0),
            },
            "sif_score": sif_score or {},
            "life_saving_rules": lsr_analysis or {},
            "precursor_analysis": {},
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
                "present_evidence": [
                    {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                    for e in data.get("present_evidence", [])
                ],
                "absent_evidence": [
                    {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                    for e in data.get("absent_evidence", [])
                ],
            }
        return analysis
