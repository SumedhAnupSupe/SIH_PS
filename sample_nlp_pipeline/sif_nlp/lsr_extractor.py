"""Life-Saving Rules (LSR) extraction module for IOGP Life-Saving Rules."""

import re
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum


class LSRStatus(Enum):
    BROKEN = "BROKEN"
    NOT_BROKEN = "NOT_BROKEN"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class LSRDefinition:
    """Definition of a Life-Saving Rule with keywords for detection."""
    id: str
    name: str
    description: str
    broken_keywords: List[str]
    not_broken_keywords: List[str]
    applicable_keywords: List[str]


IOGP_LIFE_SAVING_RULES: List[LSRDefinition] = [
    LSRDefinition(
        id="LSR01",
        name="Work Authorization",
        description="Ensure all work is authorized before starting",
        broken_keywords=[
            r"no\s*(work\s+)?permit",
            r"without\s*(a\s+)?permit",
            r"permit\s*not\s*(obtained|issued)",
            r"unauthorized\s*work",
            r"did\s*not\s*(have|obtain)\s*(a\s+)?permit",
        ],
        not_broken_keywords=[
            r"permit\s*(was\s+)?(obtained|issued|in\s*place)",
            r"authorized\s*work",
            r"work\s*permit\s*(was\s+)?(valid|approved)",
        ],
        applicable_keywords=[
            r"permit",
            r"work\s*authorization",
            r"hot\s*work",
            r"confined\s*space",
            r"working\s*at\s*height",
        ],
    ),
    LSRDefinition(
        id="LSR02",
        name="Energy Isolation",
        description="Verify isolation before work begins",
        broken_keywords=[
            r"not\s*isolated",
            r"isolation\s*(not|missing|failed)",
            r"energy\s*not\s*isolated",
            r"lockout\s*not\s*(applied|used)",
            r"tagout\s*not\s*(applied|used)",
            r"loto\s*not\s*(applied|used)",
            r"de-energiz\w*\s*not",
            r"without\s*isolation",
        ],
        not_broken_keywords=[
            r"isolated\s*(and\s+)?verified",
            r"lockout\s*(applied|in\s*place|verified)",
            r"tagout\s*(applied|in\s*place|verified)",
            r"loto\s*(applied|in\s*place|verified)",
            r"energy\s*isolation\s*verified",
            r"de-energiz\w*\s*(and\s+)?isolated",
        ],
        applicable_keywords=[
            r"electrical",
            r"transformer",
            r"energy\s*isolation",
            r"lockout",
            r"tagout",
            r"loto",
            r"de-energiz",
            r"stored\s*energy",
            r"pressur",
        ],
    ),
    LSRDefinition(
        id="LSR03",
        name="Line of Fire",
        description="Keep yourself and others out of the line of fire",
        broken_keywords=[
            r"in\s*the\s*line\s*of\s*fire",
            r"line\s*of\s*fire\s*(not\s+)?(recognized|identified|managed)",
            r"struck\s*by",
            r"hit\s*by",
            r"falling\s*object",
            r"no\s*barrier\s*(against|for)\s*line\s*of\s*fire",
        ],
        not_broken_keywords=[
            r"line\s*of\s*fire\s*(identified|managed|controlled)",
            r"barrier\s*(in\s*place|installed)\s*(against|for)\s*line\s*of\s*fire",
            r"out\s*of\s*the\s*line\s*of\s*fire",
        ],
        applicable_keywords=[
            r"lifting",
            r"crane",
            r"rigging",
            r"hoist",
            r"overhead",
            r"falling",
            r"struck",
            r"pressure",
            r"pipe",
            r"valve",
        ],
    ),
    LSRDefinition(
        id="LSR04",
        name="Confined Space",
        description="Obtain authorization before entering a confined space",
        broken_keywords=[
            r"confined\s*space\s*(entry|entered)\s*without",
            r"no\s*confined\s*space\s*permit",
            r"entered\s*confined\s*space\s*without",
            r"confined\s*space\s*not\s*(tested|ventilated|monitored)",
        ],
        not_broken_keywords=[
            r"confined\s*space\s*permit\s*(obtained|in\s*place)",
            r"confined\s*space\s*(tested|ventilated|monitored)",
            r"authorized\s*confined\s*space\s*entry",
        ],
        applicable_keywords=[
            r"confined\s*space",
            r"tank",
            r"vessel",
            r"enclosed\s*space",
            r"manhole",
        ],
    ),
    LSRDefinition(
        id="LSR05",
        name="Falling Objects",
        description="Secure tools and materials to prevent falling objects",
        broken_keywords=[
            r"tool\s*(fell|dropped)",
            r"falling\s*(tool|material|object)",
            r"no\s*(tool\s+)?tether",
            r"unsecured\s*(tool|material|load)",
            r"dropped\s*object",
        ],
        not_broken_keywords=[
            r"tool\s*tether",
            r"secured\s*(tool|material|load)",
            r"falling\s*object\s*protection",
            r"toe\s*board",
            r"net\s*(installed|in\s*place)",
        ],
        applicable_keywords=[
            r"height",
            r"elevated",
            r"working\s*at\s*height",
            r"scaffold",
            r"lifting",
            r"crane",
            r"hoist",
        ],
    ),
    LSRDefinition(
        id="LSR06",
        name="Safe Mechanical Lifting",
        description="Plan lifting operations and control the area",
        broken_keywords=[
            r"lifting\s*(plan|not\s*planned|not\s*authorized)",
            r"no\s*lifting\s*plan",
            r"lift\s*not\s*(planned|supervised|controlled)",
            r"crane\s*not\s*(inspected|certified)",
            r"rigging\s*(failed|not\s*inspected)",
        ],
        not_broken_keywords=[
            r"lifting\s*plan\s*(in\s*place|approved)",
            r"lift\s*(planned|supervised|controlled)",
            r"crane\s*(inspected|certified)",
            r"rigging\s*inspected",
            r"competent\s*person\s*(supervised|oversaw)\s*lift",
        ],
        applicable_keywords=[
            r"crane",
            r"lifting",
            r"rigging",
            r"hoist",
            r"lift",
            r"sling",
            r"shackle",
        ],
    ),
    LSRDefinition(
        id="LSR07",
        name="Fit for Purpose Equipment",
        description="Use only equipment that is fit for purpose",
        broken_keywords=[
            r"equipment\s*(not\s+)?(fit|suitable|approved|inspected)",
            r"wrong\s*equipment",
            r"defective\s*equipment",
            r"equipment\s*(failed|malfunctioned)",
            r"not\s*inspected\s*equipment",
        ],
        not_broken_keywords=[
            r"equipment\s*(fit\s+for\s+purpose|inspected|approved|certified)",
            r"correct\s*equipment",
            r"suitable\s*equipment",
        ],
        applicable_keywords=[
            r"equipment",
            r"tool",
            r"machine",
            r"instrument",
        ],
    ),
    LSRDefinition(
        id="LSR08",
        name="Driving Safety",
        description="Follow safe driving rules",
        broken_keywords=[
            r"speeding",
            r"seat\s*belt\s*not\s*(worn|used)",
            r"distracted\s*driving",
            r"phone\s*(while|during)\s*driving",
            r"vehicle\s*not\s*inspected",
        ],
        not_broken_keywords=[
            r"seat\s*belt\s*(worn|used)",
            r"safe\s*driving",
            r"vehicle\s*inspected",
            r"speed\s*limit\s*observed",
        ],
        applicable_keywords=[
            r"vehicle",
            r"driving",
            r"truck",
            r"transport",
            r"forklift",
            r"road",
        ],
    ),
    LSRDefinition(
        id="LSR09",
        name="Working at Height",
        description="Protect yourself against falls when working at height",
        broken_keywords=[
            r"no\s*fall\s*protection",
            r"harness\s*not\s*(worn|used|attached)",
            r"fall\s*arrest\s*not\s*(used|worn)",
            r"guardrail\s*(missing|not\s*in\s*place)",
            r"unprotected\s*edge",
            r"no\s*scaffold",
        ],
        not_broken_keywords=[
            r"fall\s*protection\s*(worn|used|in\s*place)",
            r"harness\s*(worn|attached|used)",
            r"guardrail\s*(in\s*place|installed)",
            r"scaffold\s*(erected|inspected|in\s*place)",
            r"fall\s*arrest\s*(used|in\s*place)",
        ],
        applicable_keywords=[
            r"height",
            r"elevated",
            r"working\s*at\s*height",
            r"roof",
            r"ladder",
            r"scaffold",
            r"platform",
        ],
    ),
]


def _match_keywords(text: str, patterns: List[str]) -> List[str]:
    """Find all keyword matches in text."""
    matches = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            matches.append(m.group())
    return list(set(matches))


def _compute_lsr_status(
    full_text: str,
    definition: LSRDefinition,
    sentences: List[Dict],
) -> Dict:
    """Compute LSR status for a single rule."""
    # Check if rule is applicable
    applicable_matches = _match_keywords(full_text, definition.applicable_keywords)
    is_applicable = len(applicable_matches) > 0
    
    broken_matches = _match_keywords(full_text, definition.broken_keywords)
    not_broken_matches = _match_keywords(full_text, definition.not_broken_keywords)
    
    # Find evidence sentences
    broken_evidence = []
    not_broken_evidence = []
    
    for sent in sentences:
        sent_text = sent["text"]
        for pattern in definition.broken_keywords:
            if re.search(pattern, sent_text, re.IGNORECASE):
                broken_evidence.append({
                    "text": sent_text,
                    "source_sentence_id": sent["sentence_id"],
                    "matched_pattern": pattern,
                })
                break
        for pattern in definition.not_broken_keywords:
            if re.search(pattern, sent_text, re.IGNORECASE):
                not_broken_evidence.append({
                    "text": sent_text,
                    "source_sentence_id": sent["sentence_id"],
                    "matched_pattern": pattern,
                })
                break
    
    # Determine status
    if not is_applicable:
        status = LSRStatus.NOT_APPLICABLE
        confidence = 0.8
        reason = "Rule not applicable to this report's activities/hazards"
    elif broken_matches and not not_broken_matches:
        status = LSRStatus.BROKEN
        confidence = min(0.7 + len(broken_matches) * 0.1, 0.95)
        reason = f"Evidence of rule violation found ({len(broken_matches)} indicator(s))"
    elif not_broken_matches and not broken_matches:
        status = LSRStatus.NOT_BROKEN
        confidence = min(0.7 + len(not_broken_matches) * 0.1, 0.95)
        reason = f"Evidence of rule compliance found ({len(not_broken_matches)} indicator(s))"
    elif broken_matches and not_broken_matches:
        status = LSRStatus.UNCERTAIN
        confidence = 0.6
        reason = "Conflicting evidence of both violation and compliance"
    else:
        status = LSRStatus.UNCERTAIN
        confidence = 0.5
        reason = "Rule applicable but no clear evidence found"
    
    return {
        "rule_id": definition.id,
        "rule_name": definition.name,
        "description": definition.description,
        "status": status.value,
        "confidence": round(confidence, 3),
        "reason": reason,
        "applicable": is_applicable,
        "applicable_keywords": applicable_matches,
        "broken_evidence": broken_evidence,
        "compliance_evidence": not_broken_evidence,
    }


def extract_life_saving_rules(
    preprocessed_data: Dict,
    extracted_evidence: Dict,
) -> Dict:
    """
    Extract Life-Saving Rules analysis from preprocessed report.
    
    Returns:
        Dict with 'analysis' (list of rule analyses) and 'summary' stats
    """
    sentences = preprocessed_data.get("sentences", [])
    full_text = " ".join(s["text"] for s in sentences)
    
    rule_analyses = []
    broken_count = 0
    uncertain_count = 0
    not_applicable_count = 0
    not_broken_count = 0
    
    for definition in IOGP_LIFE_SAVING_RULES:
        analysis = _compute_lsr_status(full_text, definition, sentences)
        rule_analyses.append(analysis)
        
        if analysis["status"] == "BROKEN":
            broken_count += 1
        elif analysis["status"] == "UNCERTAIN":
            uncertain_count += 1
        elif analysis["status"] == "NOT_APPLICABLE":
            not_applicable_count += 1
        elif analysis["status"] == "NOT_BROKEN":
            not_broken_count += 1
    
    return {
        "analysis": rule_analyses,
        "broken_rule_count": broken_count,
        "uncertain_count": uncertain_count,
        "not_broken_count": not_broken_count,
        "not_applicable_count": not_applicable_count,
    }