"""Evidence extraction module using keyword and pattern matching."""

import re
from typing import Dict, List, Tuple

from .config import (
    PRECURSOR_KEYWORDS,
    TASK_TYPE_KEYWORDS,
    HAZARD_KEYWORDS,
    CONTROL_KEYWORDS,
    WORKER_KEYWORDS,
    ENVIRONMENT_KEYWORDS,
)


class EvidenceExtractor:
    """Extracts SIF-relevant evidence from preprocessed report sentences."""

    def __init__(self):
        self.precursor_keywords = PRECURSOR_KEYWORDS
        self.task_keywords = TASK_TYPE_KEYWORDS
        self.hazard_keywords = HAZARD_KEYWORDS
        self.control_keywords = CONTROL_KEYWORDS
        self.worker_keywords = WORKER_KEYWORDS
        self.env_keywords = ENVIRONMENT_KEYWORDS

    def _match_keywords(
        self, text: str, keyword_groups: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        matches = {}
        for category, patterns in keyword_groups.items():
            found = []
            for pattern in patterns:
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    found.append(m.group())
            if found:
                matches[category] = list(set(found))
        return matches

    def _match_precursor_evidence(
        self, sentences: List[Dict]
    ) -> Dict[str, Dict[str, List[Dict]]]:
        precursor_evidence = {}
        for precursor, keyword_groups in self.precursor_keywords.items():
            precursor_evidence[precursor] = {"present": [], "absent": []}
            for sent in sentences:
                for status in ["present", "absent"]:
                    for pattern in keyword_groups.get(status, []):
                        if re.search(pattern, sent["text"], re.IGNORECASE):
                            evidence_item = {
                                "text": sent["text"],
                                "source_sentence_id": sent["sentence_id"],
                                "matched_pattern": pattern,
                            }
                            existing_ids = {
                                e["source_sentence_id"]
                                for e in precursor_evidence[precursor][status]
                            }
                            if sent["sentence_id"] not in existing_ids:
                                precursor_evidence[precursor][status].append(
                                    evidence_item
                                )
                            break
        return precursor_evidence

    def _extract_task_type(self, sentences: List[Dict]) -> List[Dict]:
        full_text = " ".join(s["text"] for s in sentences)
        task_matches = self._match_keywords(full_text, self.task_keywords)
        results = []
        for task_type, keywords in task_matches.items():
            results.append({
                "task_type": task_type,
                "evidence": keywords,
            })
        return results

    def _extract_hazards(self, sentences: List[Dict]) -> List[Dict]:
        full_text = " ".join(s["text"] for s in sentences)
        hazard_matches = self._match_keywords(full_text, self.hazard_keywords)
        results = []
        for hazard_type, keywords in hazard_matches.items():
            results.append({
                "hazard_type": hazard_type,
                "evidence": keywords,
            })
        return results

    def _extract_controls(self, sentences: List[Dict]) -> Dict[str, List[Dict]]:
        full_text = " ".join(s["text"] for s in sentences)
        control_matches = self._match_keywords(full_text, self.control_keywords)
        return control_matches

    def _extract_worker_info(self, sentences: List[Dict]) -> Dict[str, List[Dict]]:
        full_text = " ".join(s["text"] for s in sentences)
        worker_matches = self._match_keywords(full_text, self.worker_keywords)
        return worker_matches

    def _extract_environment(self, sentences: List[Dict]) -> Dict[str, List[Dict]]:
        full_text = " ".join(s["text"] for s in sentences)
        env_matches = self._match_keywords(full_text, self.env_keywords)
        return env_matches

    def _extract_work_changes(self, sentences: List[Dict]) -> Dict[str, bool]:
        full_text = " ".join(s["text"] for s in sentences)
        change_indicators = {
            "work_plan_changed": [
                r"(?:plan|approach)\s*(?:was\s+)?(?:changed|modified|revised|updated|adjusted)",
                r"change[d]?\s*(?:the\s+)?(?:plan|approach|method)",
                r"revised?\s*(?:the\s+)?(?:plan|approach|method)",
            ],
            "unexpected_condition": [
                r"unexpected",
                r"unanticipated",
                r"not\s*(?:expected|anticipated|planned)",
                r"surprising",
            ],
            "task_changed": [
                r"task\s*(?:was\s+)?(?:changed|modified|switched)",
                r"changed\s*(?:the\s+)?task",
                r"different\s*task",
            ],
            "equipment_changed": [
                r"equipment\s*(?:was\s+)?(?:changed|modified|replaced|switched|different)",
                r"changed\s*(?:the\s+)?equipment",
                r"different\s*equipment",
            ],
            "procedure_changed": [
                r"procedure\s*(?:was\s+)?(?:changed|modified|revised|different)",
                r"changed\s*(?:the\s+)?procedure",
                r"new\s*procedure",
            ],
            "work_sequence_changed": [
                r"(?:sequence|order|step)\s*(?:was\s+)?(?:changed|modified|rearranged|reordered)",
                r"changed\s*(?:the\s+)?(?:sequence|order|step)",
                r"reordered",
            ],
            "reassessment_performed": [
                r"reassess",
                r"re[-\s]?evaluated?",
                r"reviewed?\s*(?:the\s+)?(?:conditions?|situation|plan|hazards?)",
                r"updated?\s*(?:the\s+)?(?:assessment|plan|analysis)",
            ],
            "reassessment_missing": [
                r"(?:no|did\s*not|failed?\s*to)\s*(?:reassess|re[-\s]?evaluate|reassess)",
                r"(?:no|did\s*not|failed?\s*to)\s*review(?:ed)?\s*(?:the\s+)?(?:conditions?|situation|plan|hazards?)",
                r"(?:no|did\s*not|failed?\s*to)\s*update(?:d)?\s*(?:the\s+)?(?:assessment|plan|analysis)",
                r"without\s*(?:a\s+)?(?:reassessment|reevaluation|re[-\s]?review)",
            ],
        }
        results = {}
        for change_type, patterns in change_indicators.items():
            for pattern in patterns:
                if re.search(pattern, full_text, re.IGNORECASE):
                    results[change_type] = True
                    break
            else:
                results[change_type] = False
        return results

    def extract_all(self, preprocessed_data: Dict) -> Dict:
        sentences = preprocessed_data["sentences"]
        precursor_evidence = self._match_precursor_evidence(sentences)
        task_types = self._extract_task_type(sentences)
        hazards = self._extract_hazards(sentences)
        controls = self._extract_controls(sentences)
        worker_info = self._extract_worker_info(sentences)
        environment = self._extract_environment(sentences)
        work_changes = self._extract_work_changes(sentences)
        return {
            "precursor_evidence": precursor_evidence,
            "task_types": task_types,
            "hazards": hazards,
            "controls": controls,
            "worker_info": worker_info,
            "environment": environment,
            "work_changes": work_changes,
        }
