"""Configuration constants for the SIF NLP Pipeline."""

from enum import IntEnum
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Precursor Status (extended with NOT_APPLICABLE)
# ---------------------------------------------------------------------------

class PrecursorStatus(IntEnum):
    NOT_MENTIONED = 0
    ABSENT = 1
    AMBIGUOUS = 2
    PRESENT = 3
    NOT_APPLICABLE = 4


# ---------------------------------------------------------------------------
# Direct Control States
# ---------------------------------------------------------------------------

class DirectControlState:
    PRESENT = "PRESENT"
    FAILED = "FAILED"
    MISSING = "MISSING"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# IOGP Life-Saving Rules
# ---------------------------------------------------------------------------

class LSRStatus:
    BROKEN = "BROKEN"
    NOT_BROKEN = "NOT_BROKEN"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


IOGP_LSR_RULES: List[str] = [
    "driving",
    "bypassing_safety_controls",
    "confined_space",
    "energy_isolation",
    "hot_work",
    "line_of_fire",
    "safe_mechanical_lifting",
    "work_authorisation",
    "working_at_height",
]

IOGP_LSR_RULE_LABELS: Dict[str, str] = {
    "driving": "Driving",
    "bypassing_safety_controls": "Bypassing Safety Controls",
    "confined_space": "Confined Space",
    "energy_isolation": "Energy Isolation",
    "hot_work": "Hot Work",
    "line_of_fire": "Line of Fire",
    "safe_mechanical_lifting": "Safe Mechanical Lifting",
    "work_authorisation": "Work Authorisation",
    "working_at_height": "Working at Height",
}

LSR_RULE_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "driving": {
        "activity": [
            r"driving",
            r"vehicle\s*operation",
            r"operat(ed|ing)?\s*(a\s+)?(vehicle|truck|car|van|forklift)",
            r"transport(ing|ation)?",
            r"road\s*travel",
            r"travel(ing)?\s*(by|in|on)\s*(road|vehicle)",
            r"behind\s*(the\s+)?wheel",
            r"distract(ed)?\s*(driving|while)",
            r"mobile\s*phone\s*(use|while|during)",
            r"(speeding|speed\s*limit|excessive\s*speed)",
            r"seat\s*belt",
            r"(fatigue|tired|drowsy)\s*(driving|while|operator)",
        ],
        "violation": [
            r"(distract|distraction)\s*(ed)?\s*(driving|while\s*driving|phone)",
            r"(phone|mobile|cell)\s*(while|during)\s*(driving|operat)",
            r"(speed|speeding|excessive\s*speed)\s*(in|on|while|at)",
            r"(no|without)\s*seat\s*belt",
            r"seat\s*belt\s*(not|was\s*not)\s*(worn|used|fastened)",
            r"(fatigue|tired|drowsy)\s*(driving|while)",
            r"drove\s*(despite|knowing|while)",
            r"(impaired|intoxicated)\s*(driving|operation)",
            r"(ran|run)\s*(a\s+)?red\s*light",
            r"(overtaking|passing)\s*(in|at)\s*(unsafe|wrong|no\s*overtaking)",
        ],
    },
    "bypassing_safety_controls": {
        "activity": [
            r"safety\s*(control|system|device|interlock|guard)",
            r"protective\s*(device|equipment|system|control)",
            r"safeguard",
            r"interlock",
            r"emergency\s*(stop|shutdown|device)",
            r"per\s*m(g|it)",
            r"work\s*permit",
            r"lockout|tagout|loto",
        ],
        "violation": [
            r"(bypass|defeat|disable|override|remove|circumvent)\s*(the\s+)?(safety|control|interlock|guard|device|protective|emergency)",
            r"(safety|control|interlock|guard|device|protective|emergency)\s*(bypassed|defeated|disabled|overridden|removed|circumvented|cut|jumpered)",
            r"(without|no)\s*(a\s+)?(permit|authorization|permit\s*to\s*work|safe\s*work\s*permit)",
            r"(started|begin|commenc)\s*(the\s+)?work\s*(without|no)\s*(permit|authorization|permit\s*to\s*work)",
            r"(ignored|disregarded|did\s*not\s*follow)\s*(the\s+)?(safety|control|procedure|rule|protocol)",
            r"(no|without)\s*(lockout|tagout|loto)\s*(procedure|energy\s*isolation)",
        ],
    },
    "confined_space": {
        "activity": [
            r"confined\s*space",
            r"enclosed\s*(space|area)",
            r"(tank|vessel|silo|bin|pit|manhole|vault|tunnel|duct)\s*(entry|enter|entered)",
            r"non[-\s]?permit\s*confined\s*space",
            r"permit[-\s]?required\s*confined\s*space",
            r"atmospheric\s*(test|testing|monitor|monitoring)",
        ],
        "violation": [
            r"(entered?|entering)\s*(the\s+)?confined\s*space\s*(without|no)\s*(permit|authorisation|authorization|testing|monitoring| ventilation|training|supervision|rescue\s*plan)",
            r"(without|no)\s*(confined\s*space\s*)?(permit|authorisation|authorization|entry\s*permit)",
            r"(no|without)\s*(atmospheric|gas)\s*(test|testing|monitoring|monitor)",
            r"(no|without)\s*(ventilation|ventilating)\s*(the\s+)?confined\s*space",
            r"(no|without)\s*(rescue|retrieval)\s*(plan|equipment|team)",
            r"(entered?|entering)\s*(the\s+)?confined\s*space\s*without\s*(training|supervision|authorisation|authorization)",
            r"(confined\s*space)\s*(entry|enter)\s*(without|no)\s*(atmospheric|gas)\s*(test|testing|monitoring|monitor)",
        ],
    },
    "energy_isolation": {
        "activity": [
            r"energy\s*isolation",
            r"lockout|tagout|loto",
            r"(hazardous|stored|residual)\s*energy",
            r"deenergi[sz]",
            r"zero\s*energy\s*(state|verified|verification)",
            r"(isolate|isolated|isolating)\s*(the\s+)?(energy|power|source|supply|electrical|mechanical|hydraulic|pneumatic|chemical|thermal|gravity|spring|capacitor)",
            r"(verify|verified|verification)\s*(the\s+)?(zero|de-energized|de-energised|isolation)",
            r"(lock|locked|lockout)\s*(the\s+)?(energy|power|source|supply|breaker|valve)",
            r"(tag|tagged|tagout)\s*(the\s+)?(energy|power|source|supply|breaker|valve)",
        ],
        "violation": [
            r"(started?|begin|commenc)\s*(work|maintenance|repair|service|testing)\s*(before|prior\s*to|without)\s*(energy\s*isolation|lockout|tagout|loto|deenergi|verif|isolat)",
            r"(work|maintenance|repair|service|testing)\s*(began|commenced|started|initiated)\s*(before|prior\s*to|without)\s*(energy\s*isolation|lockout|tagout|loto|deenergi|verif|isolat)",
            r"(without|no)\s*(lockout|tagout|loto|energy\s*isolation|deenergi[sz]ation)",
            r"(the\s+)?(equipment|machine|system|device)\s*(was|were)\s*(opened|accessed|serviced|repaired|maintained|worked)\s*(while|when|during)\s*(energi[sz]ed|live|energized|energised|hot|charged|pressurized|pressurised)",
            r"(without|no)\s*(zero\s*energy|energy\s*verification|isolation\s*verification|lockout\s*verification|tagout\s*verification|lockout\s*confirmation)",
            r"(did\s*not|failed?\s*to)\s*(isolate|deenergi|lockout|tagout|verify\s*zero\s*energy)",
            r"(started|begin)\s*(work|maintenance|repair|service)\s*(while|before)\s*(energy|power|source)\s*(was\s+)?(on|active|live|energi[sz]ed)",
        ],
    },
    "hot_work": {
        "activity": [
            r"hot\s*work",
            r"(weld|welding|solder|soldering|cut|cutting|torch|grinding|grind)",
            r"(spark|sparks|flame|fire|heat)\s*(produced|generated|creating|from)",
            r"(fire\s*watch|fire\s*permit|hot\s*work\s*permit)",
            r"(combust|flammable)\s*(material|substance)",
        ],
        "violation": [
            r"(hot\s*work|weld|welding|cut|cutting|torch|grinding|grind)\s*(without|no)\s*(permit|authorization|authorisation|fire\s*watch|fire\s*permit|hot\s*work\s*permit|assessment|supervision|gas\s*test|atmospheric\s*test)",
            r"(without|no)\s*(fire\s*watch|fire\s*permit|hot\s*work\s*permit)",
            r"(hot\s*work|weld|welding|cut|cutting|torch|grinding|grind)\s*(near|around|close\s*to)\s*(flammable|combustible|explosive)",
            r"(started|begin|commenc)\s*(hot\s*work|weld|welding|cut|cutting|torch|grinding)\s*(without|no)\s*(permit|fire\s*watch|gas\s*test|assessment)",
            r"(did\s*not|failed?\s*to)\s*(obtain|get|check|verify|perform)\s*(hot\s*work\s*permit|fire\s*permit|gas\s*test|fire\s*watch|atmospheric\s*test)",
        ],
    },
    "line_of_fire": {
        "activity": [
            r"line\s*of\s*fire",
            r"(struck\s*by|hit\s*by|flying|falling|thrown|launch|propel|blast|explosion|energy\s*release)",
            r"(beneath|underneath|under)\s*(overhead|suspended|sling|load|crane|hoist|basket|platform)",
            r"(stored|pressur[ie]d|residual)\s*(energy|pressure|gas|fluid)",
            r"(between|crush|pinch|trap|caught)\s*(and|by|between)",
            r"(uncontrolled|unintended|unplanned)\s*(release|movement|motion|rotation|travel)",
            r"(load|object|material|equipment)\s*(dropped|fell|struck|hit|thrown|launched|moved|swung|shifted|rolled|slid)",
        ],
        "violation": [
            r"(position|stood|standing|placed|positioned|located|stayed|remained)\s*(in|within|inside|under|beneath|underneath|between|near|close\s*to)\s*(the\s+)?(line\s*of\s*fire|path|trajectory|swing|radius|drop\s*zone|fall\s*zone|impact\s*zone|crush\s*zone|pinch\s*point|struck-by)",
            r"(entered?|entering|walk|walked|walking|step|stepped|stepping|climb|climbed|climbing|move|moved|moving)\s*(in|within|under|beneath|underneath|between|through|into)\s*(the\s+)?(line\s*of\s*fire|path|trajectory|swing|radius|drop\s*zone|fall\s*zone|impact\s*zone|crush\s*zone|pinch\s*point|struck-by)",
            r"(no|without|lack\s*of)\s*(barrier|guard|barricade|shield|protection|exclusion\s*zone|safe\s*distance|clearance)",
            r"(remained|stayed|kept)\s*(in|within|under)\s*(the\s+)?(line\s*of\s*fire|path\s*of|trajectory|swing\s*radius|drop\s*zone|fall\s*zone|impact\s*zone|crush\s*zone)",
        ],
    },
    "safe_mechanical_lifting": {
        "activity": [
            r"(mechanical\s*)?lift(ing|ed)?",
            r"(crane|hoist|forklift|winch|jack|derrick|gantry)\s*(lift|operation|use|used)",
            r"(rigg?ing|rigger|rigger\s*qualified)",
            r"(sling|shackle|hook|spreader|lifting\s*beam|lifting\s*frame|lifting\s*device|lifting\s*gear|lifting\s*equipment)",
            r"(load\s*(chart|limit|rating|capacity|weight)|rated\s*capacity|working\s*load\s*limit)",
            r"(lift\s*plan|lift\s*assessment|lift\s*study|critical\s*lift|complex\s*lift)",
            r"(signal|banksman|tagline|guide\s*line|tag\s*line)",
            r"(out\s*of\s*service|defect|defective|damaged|failed|failed\s*load\s*test)",
        ],
        "violation": [
            r"(exceed|exceeded|exceeding|overload|over\s*load|over\s*capacity|over\s*rated|over\s*the\s*capacity|exceed\s*the\s*load\s*chart|exceed\s*rated\s*capacity|exceed\s*load\s*limit|exceed\s*working\s*load\s*limit)",
            r"(lift|lifting|hoist|hoisting|crane|rigg?ing)\s*(without|no)\s*(permit|authorisation|authorization|lift\s*plan|assessment|inspection|signal|banksman|tagline|supervision|competent|qualified)",
            r"(no|without|lack\s*of|failed?\s*to)\s*(inspect|inspection|check|checked|assessment|assessment|test|tested)\s*(the\s+)?(lift|crane|hoist|sling|shackle|hook|rigger|lifting\s*device|lifting\s*gear|lifting\s*equipment)",
            r"(failed?|fail|failure)\s*(to\s+)?(inspect|check|test|verify|assess|plan|assess|signal|guide|tag|direct)\s*(the\s+)?(lift|crane|hoist|sling|load|rigg?ing)",
            r"(person|worker|personnel|people|individual|human|one|someone|anyone)\s*(under|beneath|underneath)\s*(the\s+)?(load|crane|hoist|lift|suspended|overhead|rigg?ing)",
            r"(below|underneath|under)\s*(the\s+)?(suspended\s*load|load|crane|hoist|lift|overhead)",
            r"(without|no)\s*(qualified|competent|certified|trained|authorized|authorised)\s*(rigger|signal|banksman|operator|person)",
            r"(defective|damaged|failed|out[-\s]of[-\s]service|failed\s*load\s*test)\s*(sling|shackle|hook|crane|hoist|lifting\s*device|lifting\s*gear|lifting\s*equipment)\s*(used|using|operat)",
        ],
    },
    "work_authorisation": {
        "activity": [
            r"work\s*authorisation",
            r"work\s*authorization",
            r"permit\s*to\s*work",
            r"work\s*permit",
            r"job\s*permit",
            r"safe\s*work\s*permit",
            r"task\s*permit",
            r"written\s*authorisation",
            r"written\s*authorization",
        ],
        "violation": [
            r"(started?|begin|commenc|perform|carry\s*out|execute|initiate|undertake)\s*(work|maintenance|repair|testing|operation|task|job|activity)\s*(without|no)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit|approval|supervision)",
            r"(without|no)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit)",
            r"(work|maintenance|repair|testing|operation|task|job|activity)\s*(began|commenced|started|initiated|was\s*done|was\s*performed|was\s*carried\s*out|was\s*executed)\s*(without|no)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit|approval|supervision)",
            r"(did\s*not|failed?\s*to)\s*(obtain|get|check|verify|validate|review|confirm)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit|approval)",
            r"(started|begin|commenced)\s*(work|maintenance|repair|testing|operation|task|job|activity)\s*(before|prior\s*to|prior)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit|approval|supervision)\s*(was|were)?\s*(issued|granted|approved|obtained|received|available|present|in\s*place)",
            r"(expired|invalid|cancelled|revoked|withdrawn|not\s*valid)\s*(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit)\s*(used|using|relied\s*on|applied|in\s*effect)",
            r"(no|without)\s*(scope|scope\s*of\s*work|scope\s*of\s*permit)\s*(match|matching|consistent|specified|defined|covered)",
            r"(exceed|exceeded|exceeding|outside|beyond|not\s*within)\s*(the\s+)?(scope|scope\s*of\s*work|scope\s*of\s*permit|conditions|conditions?\s*of\s*permit|permit\s*conditions|authorisation\s*scope|authorization\s*scope)\s*(of|for|set\s*out|specified|defined|covered|outlined|stated)\s*(the\s+)?(permit|authorisation|authorization|permit\s*to\s*work|safe\s*work\s*permit)",
        ],
    },
    "working_at_height": {
        "activity": [
            r"(work|working)\s*(at\s+)?height",
            r"(elevated|high|high\s*level|upper\s*level)\s*(work|workplace|work\s*area|location|position)",
            r"(roof|ladder|scaffold|scaffolding|aerial\s*lift|cherry\s*picker|boom\s*lift|scissor\s*lift|platform|mezzanine|catwalk|gantry|stairway|staircase|stair|ladder|step\s*ladder)",
            r"(fall\s*(arrest|protection|restraint|guard|barrier|net|anchor|harness|lanyard|ropeline|lifeline|safety\s*line|fall\s*protection))",
            r"(edge|unprotected\s*edge|leading\s*edge|open\s*edge|floor\s*opening|wall\s*opening)",
            r"(ascending|descending|climb|climbed|climbing)",
            r"(fall\s*(from|height|distance))",
            r"(vertical\s*difference|drop|drop-off|drop\s*off|height\s*difference)",
        ],
        "violation": [
            r"(work|working)\s*(at\s+)?height\s*(without|no)\s*(fall\s*protection|harness|lanyard|guardrail|barrier|net|anchor|safety\s*line|lifeline|scaffold|permit|training|supervision|plan|assessment|rescue\s*plan)",
            r"(without|no)\s*(fall\s*protection|harness|lanyard|guardrail|barrier|net|anchor|safety\s*line|lifeline|fall\s*arrest|fall\s*restraint)",
            r"(on|from|at|near)\s*(roof|ladder|scaffold|aerial\s*lift|platform|elevated\s*platform|mezzanine|edge|unprotected\s*edge|leading\s*edge|floor\s*opening|wall\s*opening)\s*(without|no)\s*(fall\s*protection|harness|lanyard|guardrail|barrier|net|anchor|safety\s*line|lifeline|fall\s*arrest|fall\s*restraint)",
            r"(ladder|scaffold|scaffolding|aerial\s*lift|cherry\s*picker|boom\s*lift|scissor\s*lift|platform|mezzanine|catwalk|gantry|stairway|staircase|stair|step\s*ladder)\s*(without|no)\s*(guardrail|guard\s*rail|toe\s*board|mid\s*rail|net|harness|lanyard|fall\s*protection)",
            r"(fell|falling|fell\s*from|fell\s*off)\s*(roof|ladder|scaffold|scaffolding|aerial\s*lift|cherry\s*picker|boom\s*lift|scissor\s*lift|platform|elevated|mezzanine|catwalk|gantry|edge|stairway|staircase|stair|step\s*ladder|height|ladder)\s*(without|no)\s*(fall\s*protection|harness|lanyard|guardrail|barrier|net|anchor|safety\s*line|lifeline|fall\s*arrest|fall\s*restraint)",
            r"(no|without|lack\s*of|failed?\s*to)\s*(install|erect|construct|build|remove|inspect|check|verify|dismantle|dismantled)\s*(guardrail|guard\s*rail|toe\s*board|mid\s*rail|net|barrier|scaffold|scaffolding|fall\s*protection|fall\s*arrest|fall\s*restraint|lifeline|safety\s*line|anchor)",
        ],
    },
}


# ---------------------------------------------------------------------------
# Unified SIF Classification Tree
# ---------------------------------------------------------------------------

UNIFIED_TREE_VERSION = "unified_sif_classification_v1"
PIPELINE_VERSION = "3.0.0"
PRECURSOR_SCHEMA_VERSION = "2.0.0"
FEATURE_SCHEMA_VERSION = "2.0.0"


class SIFClassification:
    ACTUAL_SIF_FATALITY = "ACTUAL_SIF_FATALITY"
    ACTUAL_SIF_SERIOUS_INJURY = "ACTUAL_SIF_SERIOUS_INJURY"
    HSIF = "HSIF"
    LSIF = "LSIF"
    PSIF = "PSIF"
    CAPACITY = "CAPACITY"
    SUCCESS = "SUCCESS"
    EXPOSURE = "EXPOSURE"
    LOW_SEVERITY = "LOW_SEVERITY"
    NO_SIF_POTENTIAL = "NO_SIF_POTENTIAL"
    SIF_POTENTIAL = "SIF_POTENTIAL"


SIF_CLASSIFICATION_TIER: Dict[str, int] = {
    SIFClassification.ACTUAL_SIF_FATALITY: 1,
    SIFClassification.ACTUAL_SIF_SERIOUS_INJURY: 1,
    SIFClassification.HSIF: 1,
    SIFClassification.LSIF: 1,
    SIFClassification.PSIF: 1,
    SIFClassification.CAPACITY: 2,
    SIFClassification.SUCCESS: 2,
    SIFClassification.EXPOSURE: 2,
    SIFClassification.LOW_SEVERITY: 3,
    SIFClassification.NO_SIF_POTENTIAL: 3,
    SIFClassification.SIF_POTENTIAL: 1,
}

UNIFIED_TREE_NODES: Dict[str, Dict] = {
    "Q1": {
        "node_id": "Q1",
        "question": "Did the event result in a FATALITY?",
        "yes_action": "terminal",
        "yes_outcome": SIFClassification.ACTUAL_SIF_FATALITY,
        "no_action": "Q2",
    },
    "Q2": {
        "node_id": "Q2",
        "question": "Did the event result in a LIFE-THREATENING or LIFE-ALTERING injury?",
        "yes_action": "terminal",
        "yes_outcome": SIFClassification.ACTUAL_SIF_SERIOUS_INJURY,
        "no_action": "Q3",
    },
    "Q3": {
        "node_id": "Q3",
        "question": "Was HIGH ENERGY present? (>500 ft-lbs / >1500 Joules)",
        "yes_action": "Q4",
        "no_action": "Q8",
    },
    "Q4": {
        "node_id": "Q4",
        "question": "Was there a HIGH-ENERGY INCIDENT? (energy released and worker in proximity)",
        "yes_action": "Q5",
        "no_action": "Q6",
    },
    "Q5": {
        "node_id": "Q5",
        "question": "Was a DIRECT CONTROL present? (targets energy source, effective with human error)",
        "yes_with_sif": SIFClassification.LSIF,
        "yes_no_sif": SIFClassification.CAPACITY,
        "no_with_sif": SIFClassification.HSIF,
        "no_no_sif": SIFClassification.PSIF,
    },
    "Q6": {
        "node_id": "Q6",
        "question": "High energy but no incident -- was a DIRECT CONTROL present?",
        "yes_action": "terminal",
        "yes_outcome": SIFClassification.SUCCESS,
        "no_action": "terminal",
        "no_outcome": SIFClassification.EXPOSURE,
    },
    "Q7": {
        "node_id": "Q7",
        "question": "Two-IF test: Would 2+ independent IF conditions need to fail for SIF?",
        "yes_action": "terminal",
        "yes_outcome": SIFClassification.NO_SIF_POTENTIAL,
        "no_action": "terminal",
        "no_outcome": SIFClassification.SIF_POTENTIAL,
    },
    "Q8": {
        "node_id": "Q8",
        "question": "Low-severity assessment: near miss/minor injury with no high-energy source?",
        "yes_action": "terminal",
        "yes_outcome": SIFClassification.LOW_SEVERITY,
        "no_action": "terminal",
        "no_outcome": SIFClassification.LOW_SEVERITY,
    },
}


# ---------------------------------------------------------------------------
# High-Energy Source Categories
# ---------------------------------------------------------------------------

HIGH_ENERGY_CATEGORIES: List[str] = [
    "electrical",
    "gravitational",
    "mechanical",
    "kinetic",
    "pressure",
    "chemical_toxic",
    "thermal",
    "radiation",
    "acoustic_vibration",
    "biological",
    "electromagnetic",
]

EXPOSURE_CATEGORIES: List[str] = [
    "falling_flailing_rolling_object",
    "stored_energy",
    "power_tool",
    "personal_contact",
    "motorized_vehicle_operation",
    "pedestrian_struck_by_vehicle",
    "electricity_arc_flash",
    "work_at_height",
    "confined_space",
    "loto_hazardous_energy",
    "hot_work_fire_explosion",
    "chemical_toxic_exposure",
    "ergonomic_risk",
    "engulfment_drowning",
    "other",
]

HIGH_ENERGY_KEYWORDS: Dict[str, List[str]] = {
    "electrical": [r"electri(cal|city|cution)", r"arc\s*flash", r"power\s*line", r"high\s*voltage", r"electroc", r"shock\s*(hazard|injury)"],
    "gravitational": [r"fall\s*(from|off|height)", r"dropped\s*(object|tool|material)", r"suspended\s*load", r"scaffold.*collapse", r"elevation", r"gravity"],
    "mechanical": [r"rotat(ing|e)\s*equipment", r"pinch\s*point", r"nip\s*point", r"reciprocating", r"bladed", r"sharp\s*(edge|equipment)"],
    "kinetic": [r"vehicle\s*(movement|operation)", r"struck\s*by\s*(moving|vehicle)", r"motorized\s*equipment", r"moving\s*(load|crane|rigging)"],
    "pressure": [r"pressur(ized|ised)\s*(vessel|system|tank)", r"high[\s-]?pressure", r"wellhead", r"BOP", r"pneumatic", r"hydraulic\s*(line|system)", r"steam", r"compressed\s*air"],
    "chemical_toxic": [r"H2S", r"hydrogen\s*sulfide", r"hydrocarbon\s*(release|exposure)", r"toxic\s*(gas|fume|vapor)", r"corrosive", r"chemical\s*(exposure|release|splash)", r"oxygen\s*deficient", r"NORM"],
    "thermal": [r"fire", r"combustion", r"molten", r"steam\s*burn", r"welding|cutting|grinding", r"extreme\s*(heat|cold)", r"cryogenic", r"burn"],
    "radiation": [r"ionizing", r"gamma", r"X[\s-]?ray", r"UV", r"laser", r"RF\s*radiation"],
    "acoustic_vibration": [r"blast\s*overpressure", r"explosion\s*overpressure", r"high[\s-]?decibel", r"HAV", r"hand[\s-]?arm\s*vibration", r"noise\s*(exposure|hazard)"],
    "biological": [r"venomous", r"snake", r"spider", r"scorpion", r"anaphylaxis", r"bloodborne", r"Legionella", r"vector[\s-]?borne"],
    "electromagnetic": [r"static\s*discharge", r"magnetic\s*field", r"uncontrolled\s*release\s*of\s*energy"],
}

EXPOSURE_KEYWORDS: Dict[str, List[str]] = {
    "falling_flailing_rolling_object": [r"falling\s*(object|material|tool)", r"struck\s*by\s*(falling|flying|thrown|rolling)", r"dropped\s*object"],
    "stored_energy": [r"stored\s*energy", r"residual\s*energy", r"accumulated\s*energy"],
    "power_tool": [r"power\s*tool", r"pneumatic\s*tool", r"electric\s*tool", r"grinder", r"drill"],
    "personal_contact": [r"human[\s-]?to[\s-]?human", r"personal\s*contact", r"struck\s*by\s*person"],
    "motorized_vehicle_operation": [r"vehicle\s*(operation|movement)", r"driving", r"operating\s*(a\s+)?vehicle", r"forklift", r"truck"],
    "pedestrian_struck_by_vehicle": [r"pedestrian", r"struck\s*by\s*vehicle", r"hit\s*by\s*(vehicle|truck|car)"],
    "electricity_arc_flash": [r"electri(cal|city)", r"arc\s*flash", r"electrocution", r"power\s*line"],
    "work_at_height": [r"(work|working)\s*(at\s+)?height", r"fall\s*from\s*(elevation|height|ladder|scaffold)", r"roof"],
    "confined_space": [r"confined\s*space", r"enclosed\s*space", r"tank\s*entry", r"vessel\s*entry"],
    "loto_hazardous_energy": [r"lockout", r"tagout", r"LOTO", r"hazardous\s*energy", r"energy\s*isolation"],
    "hot_work_fire_explosion": [r"hot\s*work", r"weld", r"cutting", r"fire", r"explosion", r"combustion"],
    "chemical_toxic_exposure": [r"chemical\s*exposure", r"toxic\s*(exposure|inhalation)", r"H2S\s*exposure", r"hydrocarbon\s*exposure"],
    "ergonomic_risk": [r"ergonomic", r"lifting\s*(injury|strain)", r"repetitive", r"musculoskeletal"],
    "engulfment_drowning": [r"engulfment", r"drowning", r"water\s*(rescue|entry)", r"bulk\s*material"],
    "other": [],
}


# ---------------------------------------------------------------------------
# 13 EEI Precursors + 9 Oil-and-Gas Extensions (22 total)
# ---------------------------------------------------------------------------

SIF_PRECURSORS: List[str] = [
    "safe_work_procedure",
    "hazard_recognition",
    "departure_from_routine",
    "plan_to_address_work_change",
    "safety_attitudes",
    "rules_and_procedures",
    "familiarity_with_task",
    "risk_normalization",
    "productivity_pressure",
    "perceived_safety_culture",
    "stop_work_execution",
    "workers_inactive_in_safety",
    "pre_task_plan",
    "critical_control_failure",
    "high_energy_exposure",
    "energy_isolation_failure",
    "line_of_fire_exposure",
    "critical_control_verification_failure",
    "management_of_change_gap",
    "competency_supervision_gap",
    "work_authorization_gap",
    "simops_or_concurrent_operations",
]

SIF_PRECURSOR_LABELS: Dict[str, str] = {
    "safe_work_procedure": "Safe Work Procedure",
    "hazard_recognition": "Hazard Recognition",
    "departure_from_routine": "Departure from Routine",
    "plan_to_address_work_change": "Plan to Address Work Change",
    "safety_attitudes": "Safety Attitudes",
    "rules_and_procedures": "Rules and Procedures",
    "familiarity_with_task": "Familiarity with Task",
    "risk_normalization": "Risk Normalization",
    "productivity_pressure": "Productivity Pressure",
    "perceived_safety_culture": "Perceived Safety Culture",
    "stop_work_execution": "Stop-Work Execution",
    "workers_inactive_in_safety": "Workers Inactive in Safety",
    "pre_task_plan": "Pre-Task Plan",
    "critical_control_failure": "Critical Control Failure",
    "high_energy_exposure": "High Energy Exposure",
    "energy_isolation_failure": "Energy Isolation Failure",
    "line_of_fire_exposure": "Line of Fire Exposure",
    "critical_control_verification_failure": "Critical Control Verification Failure",
    "management_of_change_gap": "Management of Change Gap",
    "competency_supervision_gap": "Competency/Supervision Gap",
    "work_authorization_gap": "Work Authorization Gap",
    "simops_or_concurrent_operations": "Simultaneous Operations (SIMOPS)",
}

EEI_PRECURSORS: List[str] = SIF_PRECURSORS[:13]
OG_PRECURSORS: List[str] = SIF_PRECURSORS[13:]


PRECURSOR_ENCODING: Dict[int, str] = {
    0: "NOT_MENTIONED",
    1: "ABSENT",
    2: "AMBIGUOUS",
    3: "PRESENT",
    4: "NOT_APPLICABLE",
}


# ---------------------------------------------------------------------------
# Precursor Cluster Definitions
# ---------------------------------------------------------------------------

CLUSTER_PERSONNEL: List[str] = [
    "hazard_recognition",
    "familiarity_with_task",
    "workers_inactive_in_safety",
    "stop_work_execution",
    "competency_supervision_gap",
]

CLUSTER_PLANNING: List[str] = [
    "safe_work_procedure",
    "pre_task_plan",
    "departure_from_routine",
    "plan_to_address_work_change",
    "management_of_change_gap",
    "work_authorization_gap",
]

CLUSTER_EQUIPMENT: List[str] = [
    "critical_control_failure",
    "energy_isolation_failure",
    "critical_control_verification_failure",
]

CLUSTER_BARRIER: List[str] = [
    "critical_control_failure",
    "critical_control_verification_failure",
    "energy_isolation_failure",
    "line_of_fire_exposure",
]

CLUSTER_ORGANIZATIONAL: List[str] = [
    "safety_attitudes",
    "risk_normalization",
    "productivity_pressure",
    "perceived_safety_culture",
    "rules_and_procedures",
]

CLUSTER_ENVIRONMENT: List[str] = [
    "departure_from_routine",
    "simops_or_concurrent_operations",
]

PRECURSOR_CLUSTERS: Dict[str, List[str]] = {
    "personnel": CLUSTER_PERSONNEL,
    "planning": CLUSTER_PLANNING,
    "equipment": CLUSTER_EQUIPMENT,
    "barrier": CLUSTER_BARRIER,
    "organizational": CLUSTER_ORGANIZATIONAL,
    "environment": CLUSTER_ENVIRONMENT,
}

CLUSTER_LABELS: Dict[str, str] = {
    "personnel": "Personnel / Human Performance",
    "planning": "Planning / Work Preparation",
    "equipment": "Equipment / Technical",
    "barrier": "Barrier / Control",
    "organizational": "Organizational / Cultural",
    "environment": "Environment / Work Conditions",
}

# Severity weights for evidence-weighted density
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS: Dict[str, float] = {
    p: 1.0 for p in SIF_PRECURSORS
}
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS["critical_control_failure"] = 1.5
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS["high_energy_exposure"] = 1.4
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS["energy_isolation_failure"] = 1.5
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS["line_of_fire_exposure"] = 1.3
DEFAULT_PRECURSOR_SEVERITY_WEIGHTS["critical_control_verification_failure"] = 1.3

# Interaction feature definitions
PRECURSOR_INTERACTIONS: List[Tuple[str, str, str]] = [
    ("risk_normalization_x_high_energy_exposure", "risk_normalization", "high_energy_exposure"),
    ("departure_from_routine_x_management_of_change_gap", "departure_from_routine", "management_of_change_gap"),
    ("work_change_x_reassessment_gap", "plan_to_address_work_change", "management_of_change_gap"),
    ("productivity_pressure_x_stop_work_failure", "productivity_pressure", "stop_work_execution"),
    ("competency_supervision_gap_x_high_energy_exposure", "competency_supervision_gap", "high_energy_exposure"),
    ("critical_control_failure_x_high_energy_exposure", "critical_control_failure", "high_energy_exposure"),
    ("line_of_fire_x_suspended_load", "line_of_fire_exposure", "high_energy_exposure"),
    ("energy_isolation_failure_x_stored_energy", "energy_isolation_failure", "high_energy_exposure"),
]


# ---------------------------------------------------------------------------
# Equipment/Technical Evidence Keywords (for equipment cluster)
# ---------------------------------------------------------------------------

EQUIPMENT_KEYWORDS: Dict[str, List[str]] = {
    "equipment_malfunction": [r"equipment\s*(malfunction|fail|failure|broke|broken)", r"mechanical\s*fail", r"machine\s*fail"],
    "equipment_degradation": [r"equipment\s*(degrad|wear|deteriorat)", r"corrosion", r"erosion", r"fatigue\s*(crack|failure)"],
    "inappropriate_equipment": [r"inappropriate\s*equipment", r"wrong\s*equipment", r"unsuitable\s*equipment"],
    "guarding_failure": [r"guard(ing)?\s*(fail|missing|removed|defeated|bypassed)", r"safety\s*guard\s*(missing|removed|defeated)"],
    "instrumentation_alarm_failure": [r"instrument(ation)?\s*(fail|malfunction)", r"alarm\s*(fail|not\s*(work|activate)|disable|silence)", r"sensor\s*(fail|malfunction)"],
    "mechanical_electrical_failure": [r"mechanical\s*(fail|breakdown)", r"electrical\s*(fail|fault|short)", r"motor\s*(fail|burn)"],
    "maintenance_deficiency": [r"maintenance\s*(deficien|lack|miss|overdue|delay)", r"not\s*(maintain|maintained|serviced)", r"overdue\s*maintenance"],
}


# ---------------------------------------------------------------------------
# SIF Score Configuration (old weighted sum -- retained for backward compat)
# ---------------------------------------------------------------------------

@dataclass
class SIFScoreConfig:
    """Configurable SIF score weights and components."""
    weights: Dict[str, float]
    weight_source: str
    components: List[str]


DEFAULT_SIF_SCORE_WEIGHTS: Dict[str, float] = {
    "severity_or_potential_consequence": 0.20,
    "hazard_energy_exposure": 0.15,
    "barrier_or_control_failure": 0.20,
    "critical_rule_violation": 0.15,
    "sif_precursor_signal": 0.20,
    "evidence_strength": 0.05,
    "extraction_confidence": 0.05,
}

SIF_SCORE_COMPONENTS: List[str] = [
    "severity_or_potential_consequence",
    "hazard_energy_exposure",
    "barrier_or_control_failure",
    "critical_rule_violation",
    "sif_precursor_signal",
    "evidence_strength",
    "extraction_confidence",
]


# ---------------------------------------------------------------------------
# CSV Column Definitions
# ---------------------------------------------------------------------------

LSR_CSV_COLUMNS: List[str] = [
    "life_saving_rule_broken_count",
    "life_saving_rule_broken",
]

LSR_CSV_STATUS_COLUMNS: List[str] = []
LSR_CSV_CONFIDENCE_COLUMNS: List[str] = []
for _rule in IOGP_LSR_RULES:
    LSR_CSV_STATUS_COLUMNS.append(f"lsr_{_rule}_status")
    LSR_CSV_CONFIDENCE_COLUMNS.append(f"lsr_{_rule}_confidence")

SIF_SCORE_CSV_COLUMNS: List[str] = [
    "sif_score",
    "sif_score_method",
    "sif_score_weight_source",
] + [f"sif_component_{c}" for c in SIF_SCORE_COMPONENTS]


# ---------------------------------------------------------------------------
# Precursor Keywords (original 13 + 9 new oil-and-gas)
# ---------------------------------------------------------------------------

PRECURSOR_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "safe_work_procedure": {
        "present": [
            r"safe\s*work\s*procedure",
            r"followed?\s*(the\s+)?procedure",
            r"procedure\s*was\s*(followed|used|applied|in\s*place)",
            r"safe\s*method",
            r"standard\s*operating\s*procedure",
            r"sop\s*(was\s+)?followed",
            r"safety\s*procedure",
            r"work\s*procedure",
            r"followed?\s*safe\s*work",
            r"adhered?\s*to\s*(the\s+)?procedure",
        ],
        "absent": [
            r"did\s*not\s*follow",
            r"procedure\s*was\s*not",
            r"skipped?\s*(the\s+)?procedure",
            r"no\s*(safe\s+)?work\s*procedure",
            r"procedure\s*was\s*missing",
            r"lack\s*of\s*procedure",
            r"without\s*(a\s+)?procedure",
            r"bypassed?\s*procedure",
        ],
    },
    "hazard_recognition": {
        "present": [
            r"hazard\s*was\s*(recognized|identified|noted|observed)",
            r"identified?\s*(the\s+)?hazard",
            r"recognized?\s*(the\s+)?risk",
            r"hazard\s*awareness",
            r"knew\s*of\s*(the\s+)?hazard",
            r"aware\s*of\s*(the\s+)?danger",
            r"spot(ted)?\s*(the\s+)?hazard",
            r"saw\s*(the\s+)?hazard",
        ],
        "absent": [
            r"did\s*not\s*(recognize|identify|see|notice)",
            r"unaware\s*of\s*(the\s+)?hazard",
            r"failed?\s*to\s*(recognize|identify|see|notice)",
            r"no\s*hazard\s*(recognition|identification)",
            r"overlooked?\s*(the\s+)?hazard",
            r"missed?\s*(the\s+)?hazard",
            r"unseen\s*hazard",
        ],
    },
    "departure_from_routine": {
        "present": [
            r"departure\s*from\s*routine",
            r"unusual\s*(conditions?|circumstances?|situation)",
            r"change\s*from\s*normal",
            r"non[-\s]?routine",
            r"unexpected\s*(conditions?|circumstances?|situation|event|weather)",
            r"something\s*(was\s+)?different",
            r"conditions?\s*(were?\s+)?not\s*normal",
            r"new\s*(conditions?|circumstances?|situation)",
            r"modified\s*(conditions?|circumstances?|procedure)",
            r"deviated?\s*from\s*(the\s+)?norm",
            r"unexpected\s+rain",
            r"unexpected\s+weather",
            r"changed\s*conditions",
            r"conditions?\s*changed",
            r"abnormal\s*(conditions?|situation)",
            r"unplanned\s*(conditions?|event|situation)",
            r"unanticipated\s*(conditions?|event|situation)",
        ],
        "absent": [
            r"routine\s*(conditions?|task|operation)",
            r"normal\s*(conditions?|circumstances?|situation)",
            r"standard\s*(conditions?|circumstances?|situation)",
            r"nothing\s*(was\s+)?different",
            r"conditions?\s*(were?\s+)?normal",
        ],
    },
    "plan_to_address_work_change": {
        "present": [
            r"(developed?|created?|made?|updated?)\s*(a\s+)?plan",
            r"plan\s*(was\s+)?(developed|created|made|updated|revised)",
            r"addressed?\s*(the\s+)?change",
            r"adjusted?\s*(the\s+)?plan",
            r"revised?\s*(the\s+)?approach",
            r"modified?\s*(the\s+)?plan",
            r"plan\s*(to\s+)?address",
            r"new\s*plan",
            r"updated?\s*plan",
        ],
        "absent": [
            r"no\s*plan\s*(to\s+)?address",
            r"plan\s*was\s*not",
            r"did\s*not\s*(develop|create|make|update)\s*(a\s+)?plan",
            r"without\s*(a\s+)?plan",
            r"no\s*reassessment",
            r"failed?\s*to\s*(update|revise|modify)",
            r"no\s*revised?\s*plan",
            r"not\s*(included|account)\s*(in\s+)?(the\s+)?plan",
            r"did\s*not\s*account\s*for",
            r"no\s*updated?\s*(plan|briefing)",
            r"not\s*included\s*in\s*(the\s+)?original",
        ],
    },
    "safety_attitudes": {
        "present": [
            r"safety\s*(was\s+)?prioritized",
            r"good\s*safety\s*attitude",
            r"positive\s*safety\s*culture",
            r"crew\s*(was\s+)?concerned\s*about\s*safety",
            r"safety\s*(was\s+)?important",
            r"put\s*safety\s*first",
            r"safety[-\s]conscious",
        ],
        "absent": [
            r"disregarded?\s*safety",
            r"ignored?\s*safety",
            r"safety\s*was\s*(not|neglected|ignored)",
            r"poor\s*safety\s*attitude",
            r"unsafe\s*attitude",
            r"took\s*shortcuts?\s*on\s*safety",
            r"dismissed?\s*safety\s*concerns?",
            r"did\s*not\s*care\s*about\s*safety",
        ],
    },
    "rules_and_procedures": {
        "present": [
            r"followed?\s*(the\s+)?rules",
            r"followed?\s*(the\s+)?procedures?",
            r"adhered?\s*to\s*(the\s+)?rules?",
            r"complied?\s*with\s*(the\s+)?regulations?",
            r"rules?\s*(were?\s+)?followed",
            r"procedures?\s*(were?\s+)?followed",
            r"in\s*accordance\s*with\s*(the\s+)?rules",
        ],
        "absent": [
            r"violated?\s*(the\s+)?rules?",
            r"broke?\s*(the\s+)?rules?",
            r"did\s*not\s*follow\s*(the\s+)?rules?",
            r"non[-\s]?compliance",
            r"disregarded?\s*(the\s+)?rules?",
            r"ignored?\s*(the\s+)?procedures?",
            r"deviated?\s*from\s*(the\s+)?procedure",
        ],
    },
    "familiarity_with_task": {
        "present": [
            r"familiar\s*with\s*(the\s+)?task",
            r"experienced?\s*(with|in)\s*(this|the\s+)?task",
            r"performed?\s*(this|the\s+)?task\s*(many\s+)?times",
            r"routine\s*task",
            r"well[-\s]trained\s*on",
            r"done\s*(this|the\s+)?task\s*before",
            r"previous\s*experience",
            r"completed\s*(this|similar|the)\s*(task|work)\s*(many|several|multiple)\s*times",
            r"many\s*times\s*previously",
            r"years?\s*of\s*experience\s*with",
            r"experience\s*with\s*(similar|the)\s*(task|work)",
            r"similar\s*(task|work)\s*before",
            r"done\s*this\s*way\s*before",
            r"experienced\s*and\s*had\s*(done|worked)",
        ],
        "absent": [
            r"unfamiliar\s*with\s*(the\s+)?task",
            r"first\s*time",
            r"new\s*to\s*(this|the\s+)?task",
            r"inexperienced?\s*(with|in)\s*(this|the\s+)?task",
            r"never\s*(done|performed|attempted)\s*(this|the\s+)?task",
            r"no\s*experience\s*with",
        ],
    },
    "risk_normalization": {
        "present": [
            r"normalized?\s*risk",
            r"accepted?\s*(the\s+)?risk",
            r"risk\s*(was\s+)?(accepted|tolerated|normalized)",
            r"got\s*used\s*to",
            r"complacent",
            r"routine\s*complacency",
            r"thought\s*it\s*was\s*safe",
            r"assumed?\s*(it\s+)?was\s*safe",
            r"been\s*(done|doing)\s*this\s*way",
            r"had\s*(done|completed)\s*this\s*many\s*times",
            r"done\s*this\s*way\s*before",
            r"thought\s*it\s*would\s*be\s*fine",
            r"assumed?\s*(it\s+)?was\s*(safe|fine|ok)",
            r"continued?\s*(working|despite|through)\s*(the\s+)?(hazard|risk|danger)",
            r"despite\s*(the\s+)?(hazard|risk|danger)",
        ],
        "absent": [
            r"did\s*not\s*accept\s*(the\s+)?risk",
            r"recognized?\s*(the\s+)?risk",
            r"risk\s*was\s*(not|not\s+accepted)",
            r"did\s*not\s*normalize\s*risk",
            r"aware\s*of\s*the\s*risk",
        ],
    },
    "productivity_pressure": {
        "present": [
            r"productivity\s*pressure",
            r"pressure\s*to\s*(finish|complete|meet|keep|expedite|rush)",
            r"schedule\s*pressure",
            r"time\s*pressure",
            r"deadline\s*(was|approaching|pressure)",
            r"expedite\s*(the\s+)?work",
            r"rush(ed)?\s*(the\s+)?work",
            r"speed\s*up",
            r"behind\s*schedule",
            r"outage\s*window",
            r"production\s*pressure",
            r"had\s*to\s*(finish|complete)\s*before",
            r"limited\s*time",
        ],
        "absent": [
            r"no\s*(productivity|schedule|time|production)\s*pressure",
            r"adequate\s*time",
            r"sufficient\s*time",
            r"no\s*pressure\s*to\s*(finish|complete|rush)",
        ],
    },
    "perceived_safety_culture": {
        "present": [
            r"safety\s*culture",
            r"safety\s*(was\s+)?prioritized",
            r"safety\s*program",
            r"safety\s*reporting",
            r"open\s*(about|to)\s*safety",
            r"safety\s*(was\s+)?valued",
            r"safety\s*committee",
            r"safety\s*meeting",
        ],
        "absent": [
            r"poor\s*safety\s*culture",
            r"no\s*safety\s*culture",
            r"safety\s*was\s*not\s*valued",
            r"lack\s*of\s*safety\s*culture",
            r"safety\s*(was\s+)?ignored",
        ],
    },
    "stop_work_execution": {
        "present": [
            r"stop[-\s]?work\s*(authority|right|empowerment|executed|invoked|used|attempted)",
            r"stopped?\s*work",
            r"halted?\s*(the\s+)?work",
            r"cease[d]?\s*work",
            r"exercised?\s*(their\s+)?stop[-\s]?work",
            r"called\s*(a\s+)?stop",
        ],
        "absent": [
            r"did\s*not\s*stop",
            r"failed?\s*to\s*stop",
            r"no\s*stop[-\s]?work",
            r"stop[-\s]?work\s*(was\s+)?not\s*(used|exercised|called|attempted)",
            r"continued?\s*(working|despite|through)",
        ],
    },
    "workers_inactive_in_safety": {
        "present": [
            r"workers?\s*(were?\s+)?inactive\s*in\s*safety",
            r"did\s*not\s*participate\s*in\s*safety",
            r"no\s*safety\s*(meeting|input|discussion|involvement)",
            r"worker[s]?\s*did\s*not\s*(contribute|participate|speak\s*up|raise\s*concerns?)",
            r"passive\s*(about|in)\s*safety",
            r"disengaged?\s*from\s*safety",
            r"not\s*(involved|engaged|participating)\s*in\s*safety",
        ],
        "absent": [
            r"workers?\s*participated?\s*in\s*safety",
            r"active\s*(in|on)\s*safety",
            r"raised?\s*safety\s*concerns?",
            r"safety\s*input",
            r"participated?\s*in\s*safety\s*(meeting|discussion)",
        ],
    },
    "pre_task_plan": {
        "present": [
            r"pre[-\s]?task\s*(plan|review|briefing|planning)",
            r"pre[-\s]?job\s*(plan|review|briefing)",
            r"safety\s*briefing\s*(before|prior|prior\s+to)",
            r"job\s*hazard\s*analysis",
            r"jha",
            r"planned?\s*(before|prior|prior\s+to)\s*(starting|beginning|commencing)",
            r"assessed?\s*(the\s+)?hazards?\s*(before|prior|prior\s+to)",
            r"reviewed?\s*(the\s+)?task\s*(before|prior|prior\s+to)",
        ],
        "absent": [
            r"no\s*pre[-\s]?task\s*(plan|review|briefing)",
            r"did\s*not\s*(plan|review|brief|assess)",
            r"without\s*(a\s+)?pre[-\s]?task",
            r"no\s*job\s*hazard\s*analysis",
            r"skipped?\s*(the\s+)?briefing",
            r"planned?\s*without\s*(a\s+)?plan",
        ],
    },
    # --- Oil-and-Gas specific precursors ---
    "critical_control_failure": {
        "present": [
            r"critical\s*control\s*(fail|failure|breach|violation)",
            r"safety\s*(system|instrumented)\s*(fail|failure|bypass|override)",
            r"SIS\s*(fail|failure|bypass|override)",
            r"SIF\s*(fail|failure|bypass|override)",
            r"emergency\s*shutdown\s*(fail|failure|did\s*not\s*activate)",
            r"ESD\s*(fail|failure)",
            r"HIPPS\s*(fail|failure)",
            r"BOP\s*(fail|failure)",
            r"BMS\s*(fail|failure)",
        ],
        "absent": [
            r"critical\s*control\s*(was\s+)?(present|active|operational|functional|verified)",
            r"safety\s*(system|instrumented)\s*(was\s+)?(present|active|operational|functional|verified)",
            r"emergency\s*shutdown\s*(was\s+)?(present|active|operational|functional)",
        ],
    },
    "high_energy_exposure": {
        "present": [
            r"high[\s-]?energy\s*(exposure|source|hazard|incident)",
            r"energy\s*(release|release|uncontrolled)",
            r"energized|energised",
            r"stored\s*energy\s*(release|present)",
            r"arc\s*flash",
            r"pressure\s*(release|relief|blow|burst)",
            r"struck\s*by\s*(falling|moving|flying)",
            r"caught\s*between",
            r"engulfment",
            r"drowning",
        ],
        "absent": [],
    },
    "energy_isolation_failure": {
        "present": [
            r"energy\s*isolation\s*(fail|failure|absent|missing|not\s*(done|performed|verified))",
            r"(lockout|tagout|LOTO)\s*(fail|failure|absent|missing|not\s*(done|performed|verified))",
            r"(deenergi[sz]ed|de-energized|de-energised)\s*(not|failed|missing)",
            r"(started?|begin|commenc)\s*(work|maintenance|repair)\s*(before|prior\s*to|without)\s*(energy\s*isolation|lockout|tagout|LOTO|verif|isolat)",
            r"worked?\s*(while|on|at)\s*(energi[sz]ed|live|pressurized)",
        ],
        "absent": [
            r"energy\s*isolation\s*(was\s+)?(verified|confirmed|completed|in\s*place)",
            r"(lockout|tagout|LOTO)\s*(was\s+)?(applied|completed|verified|in\s*place)",
            r"zero\s*energy\s*(state\s+)?verified",
        ],
    },
    "line_of_fire_exposure": {
        "present": [
            r"line\s*of\s*fire",
            r"in\s*(the\s+)?line\s*of\s*fire",
            r"position(ed)?\s*(in|within|under|beneath)\s*(the\s+)?(line|path|trajectory|swing|drop\s*zone)",
            r"struck\s*by\s*(falling|flying|thrown|rolling|moving)",
            r"(load|object|material)\s*(dropped|fell|struck|hit|thrown|launched|moved|swung|shifted|rolled)",
            r"(between|crush|pinch|trap|caught)\s*(and|by|between)",
        ],
        "absent": [
            r"(exclusion|safe)\s*zone\s*(established|maintained|in\s*place)",
            r"(barricad|barrier|shield|guard)\s*(in\s*place|established|installed)",
        ],
    },
    "critical_control_verification_failure": {
        "present": [
            r"critical\s*control\s*(verification|check|inspection)\s*(fail|failure|not\s*(done|performed|completed|documented))",
            r"(failed?\s*to|did\s*not)\s*(verify|check|inspect|confirm)\s*(critical|safety)\s*control",
            r"control\s*verification\s*(missing|absent|not\s*(done|performed))",
            r"pre[\s-]?job\s*(verification|confirmation)\s*(not\s*(done|performed|completed)|missing|absent)",
        ],
        "absent": [
            r"critical\s*control\s*(verification|check|inspection)\s*(was\s+)?(completed|done|performed|documented|confirmed)",
            r"(verified?|confirmed?|checked?|inspected?)\s*(critical|safety)\s*control",
        ],
    },
    "management_of_change_gap": {
        "present": [
            r"management\s*of\s*change\s*(gap|failure|absent|missing|not\s*(done|performed|triggered))",
            r"MOC\s*(gap|failure|absent|missing|not\s*(done|performed|triggered))",
            r"(change|modification)\s*(without|no)\s*(MOC|management\s*of\s*change|review|assessment|approval)",
            r"(procedure|equipment|process|design)\s*(change|modification)\s*(without|no)\s*(MOC|assessment|review)",
        ],
        "absent": [
            r"management\s*of\s*change\s*(was\s+)?(completed|done|performed|triggered|initiated)",
            r"MOC\s*(was\s+)?(completed|done|performed|triggered|initiated)",
            r"change\s*(was\s+)?reviewed|assessed|approved",
        ],
    },
    "competency_supervision_gap": {
        "present": [
            r"(competen(cy|t)|qualifi(cation|ed)|train(ed|ing))\s*(gap|deficien|lack|issue|concern|missing|absent)",
            r"(supervision|supervisor)\s*(gap|deficien|lack|issue|absent|missing|not\s*(present|available))",
            r"(unsupervised|without\s*supervision|without\s*oversight)",
            r"(unqualifi|untrain|inexperi|unfamiliar)\s*(person|worker|operator|individual)",
            r"(did\s*not|failed?\s*to)\s*(train|qualify|certif|verify\s*competen)",
        ],
        "absent": [
            r"(competent|qualified|trained)\s*(person|worker|operator)",
            r"(adequate|proper|appropriate)\s*(supervision|oversight)",
            r"supervis(or|ion)\s*(present|available|on[\s-]?site)",
        ],
    },
    "work_authorization_gap": {
        "present": [
            r"work\s*(authorisation|authorization)\s*(gap|failure|absent|missing|not\s*(obtained|issued|verified))",
            r"(permit\s*to\s*work|PTW|safe\s*work\s*permit)\s*(gap|failure|absent|missing|expired|not\s*(obtained|issued|verified))",
            r"(started?|begin|commenc)\s*work\s*(without|no)\s*(permit|authorisation|authorization|approval|supervision)",
            r"(work|maintenance|repair)\s*(without|no)\s*(permit|PTW|safe\s*work\s*permit|authorization)",
        ],
        "absent": [
            r"work\s*(authorisation|authorization)\s*(was\s+)?(obtained|issued|verified|in\s*place)",
            r"(permit\s*to\s*work|PTW|safe\s*work\s*permit)\s*(was\s+)?(obtained|issued|valid|in\s*place)",
        ],
    },
    "simops_or_concurrent_operations": {
        "present": [
            r"simultaneous\s*operations",
            r"SIMOPS",
            r"concurrent\s*operations",
            r"concurrent\s*activities",
            r"parallel\s*(operations|activities|work)",
            r"(multiple|several)\s*(crews|teams|contractors|activities)\s*(in|at)\s*(the\s+)?(same|adjacent|near)",
            r"interface\s*(between|of)\s*(activities|operations|crews)",
        ],
        "absent": [],
    },
}


# ---------------------------------------------------------------------------
# Other Keyword Dictionaries
# ---------------------------------------------------------------------------

TASK_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "electrical_work": [r"electrical", r"transformer", r"power\s*line", r"cable", r"substation", r"high\s*voltage", r"arc\s*flash"],
    "fall_protection": [r"fall", r"height", r"ladder", r"scaffold", r"elevated", r"roof", r"climbing"],
    "confined_space": [r"confined\s*space", r"tank", r"vessel", r"enclosed"],
    "crane_operations": [r"crane", r"lift", r"rigging", r"hoist", r"overhead"],
    "excavation": [r"excavat", r"dig", r"trench", r"hole"],
    "hot_work": [r"weld", r"cut", r"torch", r"grind", r"hot\s*work", r"fire"],
    "machine_guarding": [r"machine", r"guard", r"moving\s*parts", r"nip\s*point", r"rotating"],
    "lockout_tagout": [r"lockout", r"tagout", r"loto", r"energy\s*isolation", r"deenergiz"],
    "vehicle_operations": [r"vehicle", r"truck", r"driving", r"transport", r"forklift"],
    "working_around_traffic": [r"traffic", r"road", r"highway", r"vehicle\s*traffic"],
    "chemical_handling": [r"chemical", r"toxic", r"hazardous\s*material", r"hazmat"],
    "general_maintenance": [r"repair", r"maintenance", r"inspection", r"general"],
}

HAZARD_KEYWORDS: Dict[str, List[str]] = {
    "electrical_hazard": [r"electrical", r"electrocution", r"arc\s*flash", r"shock", r"high\s*voltage"],
    "fall_hazard": [r"fall", r"height", r"elevated", r"unprotected\s*edge"],
    "struck_by_hazard": [r"struck\s*by", r"hit\s*by", r"falling\s*(object|material)", r"projectile"],
    "caught_between_hazard": [r"caught\s*between", r"caught\s*in", r"crush", r"pinch"],
    "stored_energy_hazard": [r"stored\s*energy", r"pressur", r"spring", r"gravity", r"capacitor"],
    "chemical_hazard": [r"chemical", r"toxic", r"exposure", r"spill", r"vapor"],
    "noise_hazard": [r"noise", r"hearing", r"decibel"],
    "ergonomic_hazard": [r"ergonomic", r"lifting", r"repetitive", r"strain"],
    "weather_hazard": [r"weather", r"rain", r"wind", r"lightning", r"ice", r"snow", r"temperature"],
}

CONTROL_KEYWORDS: Dict[str, List[str]] = {
    "control_present": [r"(provided|used|installed|applied|in\s*place|available|equipped|had)\s*(ppe|guard|barrier|control|protection|safety)", r"ppe\s*(was\s+)?(provided|used|available|worn)"],
    "control_missing": [r"no\s*(ppe|guard|barrier|control|protection)", r"missing\s*(ppe|guard|barrier|control|protection)", r"without\s*(ppe|guard|barrier|control|protection)", r"lack\s*of\s*(ppe|guard|barrier|control|protection)"],
    "control_failed": [r"(ppe|guard|barrier|control|protection)\s*(failed|broke|malfunctioned|did\s*not\s*work)", r"failure\s*of\s*(ppe|guard|barrier|control|protection)"],
}

WORKER_KEYWORDS: Dict[str, List[str]] = {
    "training_known": [r"trained", r"training", r"certified", r"qualified"],
    "experience_known": [r"experienced?", r"years?\s*of\s*experience", r"experience\s*(with|in)"],
    "supervision": [r"supervis", r"foreman", r"lead", r"overseen"],
    "communication_issue": [r"communication\s*(issue|failure|breakdown|problem|lack)", r"miscommunication", r"not\s*(communicated|told|informed|notified)"],
}

ENVIRONMENT_KEYWORDS: Dict[str, List[str]] = {
    "weather_change": [r"rain", r"wind", r"storm", r"lightning", r"snow", r"ice", r"temperature\s*change", r"weather\s*(changed|change|shift|deteriorated)"],
    "lighting_issue": [r"lighting", r"dark", r"dim", r"visibility", r"poor\s*light"],
    "site_condition_change": [r"ground\s*(condition|surface)\s*(changed|change|wet|muddy|unstable)", r"unstable", r"uneven"],
}


# ---------------------------------------------------------------------------
# Dataframe Schema (extended for v3.0.0)
# ---------------------------------------------------------------------------

DATAFRAME_SCHEMA: Dict[str, str] = {
    "incident_id": "str",
    "task_type": "str",
    "hazard_count": "int",
    "environmental_change": "int",
    "unexpected_condition": "int",
    "work_plan_changed": "int",
    "task_changed": "int",
    "equipment_changed": "int",
    "procedure_changed": "int",
    "work_sequence_changed": "int",
    "reassessment_performed": "int",
    "reassessment_missing": "int",
    "control_failure_present": "int",
    "missing_control_present": "int",
    "barrier_failure_present": "int",
    "control_deviation_present": "int",
    "worker_training_known": "int",
    "worker_experience_known": "int",
    "worker_hazard_awareness": "int",
    "worker_safety_engagement": "int",
    "supervision_present": "int",
    "communication_issue": "int",
    "procedure_information_missing": "int",
    "pre_task_plan_information_missing": "int",
    "worker_experience_information_missing": "int",
    "hazard_information_missing": "int",
    "stop_work_information_missing": "int",
    "report_length": "int",
    "sentence_count": "int",
    "relevant_sentence_count": "int",
    "relevance_ratio": "float",
}

for precursor in SIF_PRECURSORS:
    DATAFRAME_SCHEMA[precursor] = "int"
    DATAFRAME_SCHEMA[f"{precursor}_confidence"] = "float"
    DATAFRAME_SCHEMA[f"{precursor}_evidence_count"] = "int"
    DATAFRAME_SCHEMA[f"{precursor}_evidence_strength"] = "float"

DATAFRAME_SCHEMA["life_saving_rule_broken_count"] = "int"
DATAFRAME_SCHEMA["life_saving_rule_broken"] = "str"
for rule in IOGP_LSR_RULES:
    DATAFRAME_SCHEMA[f"lsr_{rule}_status"] = "str"
    DATAFRAME_SCHEMA[f"lsr_{rule}_confidence"] = "float"

# Unified tree features
DATAFRAME_SCHEMA["sif_tree_classification"] = "str"
DATAFRAME_SCHEMA["sif_tree_tier"] = "int"
DATAFRAME_SCHEMA["sif_tree_confidence"] = "float"
DATAFRAME_SCHEMA["sif_tree_version"] = "str"

for node_id in UNIFIED_TREE_NODES:
    DATAFRAME_SCHEMA[f"tree_node_{node_id}_answer"] = "str"
    DATAFRAME_SCHEMA[f"tree_node_{node_id}_confidence"] = "float"
    DATAFRAME_SCHEMA[f"tree_node_{node_id}_evidence_count"] = "int"

DATAFRAME_SCHEMA["high_energy_present"] = "int"
DATAFRAME_SCHEMA["high_energy_incident"] = "int"
DATAFRAME_SCHEMA["direct_control_state"] = "str"
DATAFRAME_SCHEMA["sustained_sif_injury"] = "int"
DATAFRAME_SCHEMA["fatality"] = "int"
DATAFRAME_SCHEMA["life_threatening_injury"] = "int"
DATAFRAME_SCHEMA["life_altering_injury"] = "int"
DATAFRAME_SCHEMA["two_if_applicable"] = "int"
DATAFRAME_SCHEMA["two_if_count"] = "int"
DATAFRAME_SCHEMA["two_if_result"] = "str"

# Cluster features
for cluster_name in PRECURSOR_CLUSTERS:
    DATAFRAME_SCHEMA[f"{cluster_name}_contribution_score"] = "float"
    DATAFRAME_SCHEMA[f"{cluster_name}_density"] = "float"
    DATAFRAME_SCHEMA[f"{cluster_name}_evidence_coverage"] = "float"

# Density features
DATAFRAME_SCHEMA["raw_precursor_density"] = "float"
DATAFRAME_SCHEMA["evidence_weighted_precursor_density"] = "float"
DATAFRAME_SCHEMA["high_energy_precursor_density"] = "float"
DATAFRAME_SCHEMA["barrier_density"] = "float"
DATAFRAME_SCHEMA["applicable_precursor_count"] = "int"
DATAFRAME_SCHEMA["present_precursor_count"] = "int"

# Interaction features
for inter_name, _, _ in PRECURSOR_INTERACTIONS:
    DATAFRAME_SCHEMA[inter_name] = "float"

# Consistency features
DATAFRAME_SCHEMA["classification_consistency_score"] = "float"
DATAFRAME_SCHEMA["classification_consistency_level"] = "str"
