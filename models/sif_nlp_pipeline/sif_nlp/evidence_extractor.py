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
    HIGH_ENERGY_KEYWORDS,
    EXPOSURE_KEYWORDS,
    EQUIPMENT_KEYWORDS,
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
        self.high_energy_keywords = HIGH_ENERGY_KEYWORDS
        self.exposure_keywords = EXPOSURE_KEYWORDS
        self.equipment_keywords = EQUIPMENT_KEYWORDS

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

    def _extract_high_energy_evidence(
        self, sentences: List[Dict]
    ) -> Dict[str, Dict]:
        """Detect high-energy sources and exposure categories with evidence."""
        full_text = " ".join(s["text"] for s in sentences)
        results = {
            "energy_sources": {},
            "exposure_categories": {},
            "high_energy_present": False,
            "high_energy_incident": False,
        }

        for category, patterns in self.high_energy_keywords.items():
            matched = []
            for pattern in patterns:
                for m in re.finditer(pattern, full_text, re.IGNORECASE):
                    matched.append(m.group())
            if matched:
                results["energy_sources"][category] = list(set(matched))
                results["high_energy_present"] = True

        for category, patterns in self.exposure_keywords.items():
            matched = []
            for pattern in patterns:
                for m in re.finditer(pattern, full_text, re.IGNORECASE):
                    matched.append(m.group())
            if matched:
                results["exposure_categories"][category] = list(set(matched))

        # Check for energy incident indicators (release, contact, proximity)
        incident_patterns = [
            r"(energy|pressure|force)\s*(release|release|discharge|rupture|burst|blow|explosion)",
            r"(struck\s*by|hit\s*by|contact\s*with)\s*(falling|moving|flying|energy|load|object)",
            r"(arc|flash|shock|electrocution|burn|crush|impact|collision)",
            r"(fell|falling)\s*(from|off|on|into)",
            r"(caught|trapped|crushed|engulfed)\s*(in|by|between)",
            r"(rupture|burst|explode|detonat)\s*(of|in|the)",
        ]
        for pattern in incident_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                results["high_energy_incident"] = True
                break

        return results

    def _extract_outcome_evidence(self, sentences: List[Dict]) -> Dict[str, Dict]:
        """Detect injury severity and outcome types."""
        full_text = " ".join(s["text"] for s in sentences)
        results = {
            "fatality": False,
            "life_threatening_injury": False,
            "life_altering_injury": False,
            "sustained_sif_injury": False,
            "minor_injury": False,
            "near_miss": False,
            "evidence": {},
        }

        fatality_patterns = [
            r"(died|death|fatal|killed|fatality|lost\s*(his|her|their)\s*life)",
            r"(dead\s*at\s*(scene|site)|deceased)",
            r"(did\s*not\s*survive)",
        ]
        for pattern in fatality_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                results["fatality"] = True
                results["sustained_sif_injury"] = True
                results["evidence"]["fatality"] = matches[:3]
                break

        life_threatening_patterns = [
            r"(life[-\s]?threatening|critical\s*injury|cardiac\s*arrest|CPR|defibrillat)",
            r"(severe\s*(bleed|hemorrhage|burn)|major\s*(arterial|vascular))",
            r"(brain\s*injury|spinal\s*(cord)?\s*injury|chest\s*trauma)",
            r"(crush\s*injury\s*(with|requiring))",
            r"(internal\s*organ\s*rupture)",
        ]
        for pattern in life_threatening_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                results["life_threatening_injury"] = True
                results["sustained_sif_injury"] = True
                results["evidence"]["life_threatening"] = matches[:3]
                break

        life_altering_patterns = [
            r"(amputation|amputat|loss\s*of\s*(body\s*part|finger|thumb|toe|limb|digit))",
            r"(permanent\s*(impairment|disability|damage|loss))",
            r"(loss\s*of\s*(vision|hearing|smell|function))",
            r"(permanent\s*(reduction|damage)\s*(of|in|to)\s*(organ|function|physiological))",
            r"(disfigurement|chronic\s*pain)",
            r"(loss\s*of\s*(thumb|index\s*finger|great\s*toe))",
        ]
        for pattern in life_altering_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                results["life_altering_injury"] = True
                results["sustained_sif_injury"] = True
                results["evidence"]["life_altering"] = matches[:3]
                break

        if not results["fatality"] and not results["life_threatening_injury"] and not results["life_altering_injury"]:
            injury_patterns = [
                r"(injur|wound|lacerat|fractur|sprain|strain|bruise|cut|gash)",
                r"(broken\s*(bone|arm|leg|rib|finger))",
                r"(first[-\s]?aid|medical\s*treatment|hospital)",
            ]
            for pattern in injury_patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    results["minor_injury"] = True
                    results["evidence"]["minor_injury"] = matches[:3]
                    break

        near_miss_patterns = [
            r"(near[-\s]?miss|close\s*call|narrowly\s*avoided)",
            r"(could\s*have|could\s*have\s*(resulted|caused|led))",
            r"(almost\s*(hit|struck|fell|fell\s*from|contact))",
            r"(fortunately|lucky|lucky\s*escape)",
        ]
        for pattern in near_miss_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                results["near_miss"] = True
                results["evidence"]["near_miss"] = matches[:3]
                break

        return results

    def _extract_direct_control_assessment(
        self, sentences: List[Dict]
    ) -> Dict:
        """Assess whether a direct control is present for the high-energy source."""
        full_text = " ".join(s["text"] for s in sentences)

        present_patterns = [
            r"(barrier|guard|guardrail|shield|baffle|barricade)\s*(was\s+)?(installed|in\s*place|present|effective|active|verified)",
            r"(interlock|safety\s*(device|system|control|instrument))\s*(was\s+)?(installed|in\s*place|present|active|effective|verified)",
            r"(fall\s*protection|harness|lanyard|guardrail|net|anchor)\s*(was\s+)?(in\s*place|installed|used|worn|active|verified)",
            r"(lockout|tagout|LOTO)\s*(was\s+)?(applied|completed|in\s*place|verified)",
            r"(emergency\s*shutdown|ESD|SIS|BOP|HIPPS)\s*(was\s+)?(active|operational|functional|in\s*place|verified)",
            r"(exclusion\s*zone|exclusion\s*area|barrier)\s*(established|maintained|in\s*place)",
        ]

        failed_patterns = [
            r"(barrier|guard|interlock|safety\s*(device|system|control))\s*(fail|failed|broke|broken|malfunction|malfunctioned|defeated|bypassed|removed|disabled|overridden)",
            r"(lockout|tagout|LOTO)\s*(fail|failed|not\s*(applied|done|verified))",
            r"(interlock)\s*(defeated|bypassed|overridden|disabled|removed)",
            r"(safety\s*system)\s*(bypassed|overridden|disabled|failed|in\s*bypass)",
        ]

        missing_patterns = [
            r"(no|absent|missing|lack\s*of)\s*(barrier|guard|guardrail|shield|interlock|safety\s*(device|system|control|instrument))",
            r"(without|no)\s*(fall\s*protection|harness|guardrail|barrier|net|barricade)",
            r"(no|without)\s*(lockout|tagout|LOTO|energy\s*isolation)",
            r"(unprotected|unguarded|unshielded)\s*(edge|opening|area|machine|equipment)",
        ]

        control_evidence = []
        failed_evidence = []
        missing_evidence = []

        for sent in sentences:
            text = sent["text"]
            for pattern in present_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    control_evidence.append({
                        "text": text,
                        "source_sentence_id": sent["sentence_id"],
                    })
                    break
            for pattern in failed_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    failed_evidence.append({
                        "text": text,
                        "source_sentence_id": sent["sentence_id"],
                    })
                    break
            for pattern in missing_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    missing_evidence.append({
                        "text": text,
                        "source_sentence_id": sent["sentence_id"],
                    })
                    break

        present_count = len(control_evidence)
        failed_count = len(failed_evidence)
        missing_count = len(missing_evidence)

        if failed_count > 0:
            state = "FAILED"
            confidence = min(0.7 + failed_count * 0.05, 0.95)
        elif missing_count > present_count:
            state = "MISSING"
            confidence = min(0.7 + missing_count * 0.05, 0.95)
        elif present_count > 0 and failed_count == 0 and missing_count == 0:
            state = "PRESENT"
            confidence = min(0.7 + present_count * 0.05, 0.95)
        elif present_count > 0 and (failed_count > 0 or missing_count > 0):
            state = "UNCERTAIN"
            confidence = 0.5
        else:
            state = "NOT_APPLICABLE"
            confidence = 0.3

        all_evidence = control_evidence + failed_evidence + missing_evidence
        source_sentence_ids = list({e["source_sentence_id"] for e in all_evidence})

        return {
            "present": state in ("PRESENT",),
            "state": state,
            "confidence": round(confidence, 3),
            "evidence": all_evidence,
            "source_sentence_ids": source_sentence_ids,
            "control_types": [],
        }

    def _extract_two_if_test(
        self, sentences: List[Dict]
    ) -> Dict:
        """Implement the IADC-style Two-IF test for near misses.

        Identify independent safeguards/conditions that would both need to
        fail for a fatal or serious outcome.
        """
        full_text = " ".join(s["text"] for s in sentences)

        if_conditions = []

        safeguard_patterns = [
            r"(IF|if)\s+(the\s+)?(exclusion\s*zone|barrier|guard|barricade|safety\s*(system|device|control|procedure))\s+(was|had\s*been|were)\s+(active|in\s*place|effective|functioning|properly\s*(installed|maintained|used))",
            r"(IF|if)\s+(the\s+)?(worker|person|personnel|operator)\s+(had\s+)?(not\s+)?(been|been\s+(inside|under|near|within|in|between))",
            r"(IF|if)\s+(the\s+)?(permit|authorization|approval|lockout|tagout|LOTO)\s+(had\s+)?(been\s+)?(in\s*place|applied|verified|obtained|valid)",
            r"(IF|if)\s+(the\s+)?(guard|barrier|shield|interlock|safety\s*(system|device))\s+(had\s+)?(been\s+)?(working|functional|active|in\s*place|not\s*(defeated|bypassed|disabled))",
            r"(IF|if)\s+(the\s+)?(training|supervision|competency)\s+(had\s+)?(been\s+)?(adequate|present|sufficient|proper|in\s*place)",
            r"(IF|if)\s+(the\s+)?(gas\s*test|atmospheric\s*test|monitoring)\s+(had\s+)?(been\s+)?(done|performed|conducted|in\s*place)",
            r"(IF|if)\s+(the\s+)?(fall\s*protection|harness|lanyard|lifeline|anchor)\s+(had\s+)?(been\s+)?(used|worn|in\s*place|properly\s*(attached|connected))",
            r"(IF|if)\s+(the\s+)?(buddy\s*system|rescue\s*(team|plan))\s+(had\s+)?(been\s+)?(in\s*place|active|available|present)",
            r"(IF|if)\s+(the\s+)?(communication|radio|signal)\s+(had\s+)?(been\s+)?(established|clear|proper|working|maintained)",
            r"(IF|if)\s+(the\s+)?(fatigue|distraction|impairment)\s+(had\s+)?(been\s+)?(absent|not\s+present|controlled|managed)",
        ]

        for pattern in safeguard_patterns:
            matches = re.finditer(pattern, full_text, re.IGNORECASE)
            for m in matches:
                context_start = max(0, m.start() - 100)
                context_end = min(len(full_text), m.end() + 100)
                context = full_text[context_start:context_end]
                if_conditions.append({
                    "condition": m.group(),
                    "evidence": [{"text": context.strip(), "source_sentence_id": -1}],
                    "confidence": 0.7,
                })

        # Remove near-duplicate conditions
        seen_conditions = set()
        unique_conditions = []
        for cond in if_conditions:
            key = cond["condition"].lower().strip()
            if key not in seen_conditions:
                seen_conditions.add(key)
                unique_conditions.append(cond)

        independent_count = len(unique_conditions)
        if independent_count >= 2:
            result = "NO_SIF_POTENTIAL"
            applicable = True
            confidence = min(0.6 + independent_count * 0.05, 0.9)
        elif independent_count == 1:
            result = "SIF_POTENTIAL"
            applicable = True
            confidence = 0.6
        else:
            result = "UNCERTAIN"
            applicable = False
            confidence = 0.3

        return {
            "applicable": applicable,
            "if_conditions": unique_conditions,
            "independent_if_count": independent_count,
            "result": result,
            "confidence": round(confidence, 3),
        }

    def _extract_equipment_evidence(
        self, sentences: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Extract equipment/technical evidence for the equipment cluster."""
        full_text = " ".join(s["text"] for s in sentences)
        equipment_matches = self._match_keywords(full_text, self.equipment_keywords)
        results = []
        for evidence_type, keywords in equipment_matches.items():
            results.append({
                "evidence_type": evidence_type,
                "evidence": keywords,
            })
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
        high_energy = self._extract_high_energy_evidence(sentences)
        outcome = self._extract_outcome_evidence(sentences)
        direct_control = self._extract_direct_control_assessment(sentences)
        two_if = self._extract_two_if_test(sentences)
        equipment = self._extract_equipment_evidence(sentences)
        return {
            "precursor_evidence": precursor_evidence,
            "task_types": task_types,
            "hazards": hazards,
            "controls": controls,
            "worker_info": worker_info,
            "environment": environment,
            "work_changes": work_changes,
            "high_energy": high_energy,
            "outcome": outcome,
            "direct_control": direct_control,
            "two_if_test": two_if,
            "equipment_evidence": equipment,
        }
