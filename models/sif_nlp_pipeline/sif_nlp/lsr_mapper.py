"""IOGP Report 459 Life-Saving Rule mapping module."""

import re
from typing import Dict, List, Tuple

from .config import (
    IOGP_LSR_RULES,
    IOGP_LSR_RULE_LABELS,
    LSR_RULE_KEYWORDS,
    LSRStatus,
)


class LSRMapper:
    """Maps structured evidence to IOGP Report 459 Life-Saving Rules."""

    def __init__(self):
        self.rules = IOGP_LSR_RULES

    def _extract_lsr_evidence(
        self, sentences: List[Dict]
    ) -> Dict[str, Dict[str, List[Dict]]]:
        rule_evidence = {}
        for rule in self.rules:
            rule_evidence[rule] = {"activity": [], "violation": []}
            rule_kw = LSR_RULE_KEYWORDS.get(rule, {})
            activity_patterns = rule_kw.get("activity", [])
            violation_patterns = rule_kw.get("violation", [])
            for sent in sentences:
                text = sent["text"]
                for pattern in violation_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        existing_ids = {
                            e["source_sentence_id"]
                            for e in rule_evidence[rule]["violation"]
                        }
                        if sent["sentence_id"] not in existing_ids:
                            rule_evidence[rule]["violation"].append({
                                "text": text,
                                "source_sentence_id": sent["sentence_id"],
                                "matched_pattern": pattern,
                            })
                        break
                for pattern in activity_patterns:
                    if re.search(pattern, text, re.IGNORECASE):
                        existing_ids = {
                            e["source_sentence_id"]
                            for e in rule_evidence[rule]["activity"]
                        }
                        if sent["sentence_id"] not in existing_ids:
                            rule_evidence[rule]["activity"].append({
                                "text": text,
                                "source_sentence_id": sent["sentence_id"],
                                "matched_pattern": pattern,
                            })
                        break
        return rule_evidence

    def _compute_rule_status(
        self,
        activity_evidence: List[Dict],
        violation_evidence: List[Dict],
    ) -> Tuple[str, float]:
        has_activity = len(activity_evidence) > 0
        has_violation = len(violation_evidence) > 0

        if not has_activity:
            return LSRStatus.NOT_APPLICABLE, 0.99

        if has_violation:
            violation_count = len(violation_evidence)
            if violation_count >= 3:
                confidence = min(0.90 + (violation_count * 0.02), 0.99)
            elif violation_count >= 2:
                confidence = 0.85
            else:
                confidence = 0.70
            return LSRStatus.BROKEN, round(confidence, 3)

        if has_activity and not has_violation:
            activity_count = len(activity_evidence)
            if activity_count >= 3:
                confidence = min(0.80 + (activity_count * 0.02), 0.95)
            elif activity_count >= 2:
                confidence = 0.75
            else:
                confidence = 0.60
            return LSRStatus.NOT_BROKEN, round(confidence, 3)

        return LSRStatus.UNCERTAIN, 0.50

    def map_rules(self, preprocessed_data: Dict) -> Dict:
        sentences = preprocessed_data.get("sentences", [])
        rule_evidence = self._extract_lsr_evidence(sentences)

        analysis = []
        for rule in self.rules:
            evidence_data = rule_evidence.get(rule, {"activity": [], "violation": []})
            activity_ev = evidence_data.get("activity", [])
            violation_ev = evidence_data.get("violation", [])
            status, confidence = self._compute_rule_status(activity_ev, violation_ev)

            reason = ""
            if status == LSRStatus.BROKEN:
                reason = (
                    f"Evidence indicates the {IOGP_LSR_RULE_LABELS[rule]} rule "
                    f"was not followed."
                )
            elif status == LSRStatus.NOT_BROKEN:
                reason = (
                    f"The activity was present but evidence indicates the "
                    f"{IOGP_LSR_RULE_LABELS[rule]} rule was followed."
                )
            elif status == LSRStatus.NOT_APPLICABLE:
                reason = (
                    f"No {IOGP_LSR_RULE_LABELS[rule]} activity was identified "
                    f"in the report."
                )
            else:
                reason = (
                    f"The rule appears potentially relevant but the report "
                    f"does not provide enough evidence to determine whether "
                    f"it was followed or broken."
                )

            evidence_for_json = [
                {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                for e in violation_ev
            ]
            if not evidence_for_json:
                evidence_for_json = [
                    {"text": e["text"], "source_sentence_id": e["source_sentence_id"]}
                    for e in activity_ev[:2]
                ]

            analysis.append({
                "rule_name": IOGP_LSR_RULE_LABELS[rule],
                "status": status,
                "confidence": confidence,
                "reason": reason,
                "evidence": evidence_for_json,
            })

        broken_rules = [
            a["rule_name"]
            for a in analysis
            if a["status"] == LSRStatus.BROKEN
        ]
        broken_rule_count = len(broken_rules)

        return {
            "analysis": analysis,
            "broken_rule_count": broken_rule_count,
            "broken_rules": broken_rules,
            "rule_evidence_raw": rule_evidence,
        }

    def validate(self, lsr_result: Dict) -> List[str]:
        errors = []
        analysis = lsr_result.get("analysis", [])
        if len(analysis) != 9:
            errors.append(
                f"Expected 9 LSR rules, got {len(analysis)}"
            )
        valid_statuses = {
            LSRStatus.BROKEN,
            LSRStatus.NOT_BROKEN,
            LSRStatus.UNCERTAIN,
            LSRStatus.NOT_APPLICABLE,
        }
        rule_names_seen = set()
        for entry in analysis:
            rule_name = entry.get("rule_name", "")
            status = entry.get("status", "")
            confidence = entry.get("confidence", 0.0)

            if rule_name in rule_names_seen:
                errors.append(f"Duplicate LSR rule: {rule_name}")
            rule_names_seen.add(rule_name)

            if status not in valid_statuses:
                errors.append(f"Invalid LSR status for {rule_name}: {status}")

            if not (0.0 <= confidence <= 1.0):
                errors.append(
                    f"LSR confidence for {rule_name} out of range: {confidence}"
                )

            if status == LSRStatus.BROKEN and not entry.get("evidence"):
                errors.append(
                    f"BROKEN rule {rule_name} has no supporting evidence"
                )

        broken_count = lsr_result.get("broken_rule_count", 0)
        actual_broken = sum(
            1 for a in analysis if a["status"] == LSRStatus.BROKEN
        )
        if broken_count != actual_broken:
            errors.append(
                f"broken_rule_count mismatch: {broken_count} vs {actual_broken}"
            )

        broken_rules_list = lsr_result.get("broken_rules", [])
        actual_broken_names = sorted(
            a["rule_name"] for a in analysis if a["status"] == LSRStatus.BROKEN
        )
        if sorted(broken_rules_list) != actual_broken_names:
            errors.append("broken_rules list does not match BROKEN status entries")

        return errors
