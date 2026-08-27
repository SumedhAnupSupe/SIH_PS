"""Configuration constants for the SIF NLP Pipeline."""

from enum import IntEnum
from typing import Dict, List


class PrecursorStatus(IntEnum):
    NOT_MENTIONED = 0
    ABSENT = 1
    AMBIGUOUS = 2
    PRESENT = 3


PRECURSOR_ENCODING: Dict[int, str] = {
    0: "NOT_MENTIONED",
    1: "ABSENT",
    2: "AMBIGUOUS",
    3: "PRESENT",
}

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
}

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
}

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

DATAFRAME_SCHEMA = {
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
