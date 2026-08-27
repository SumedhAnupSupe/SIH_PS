"""Generate ~100 dummy UA/UC reports with varying SIF scores and ingest them."""
import random
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import engine, apply_schema
from app.services.nlp_service import nlp_service

# Diverse report templates
TEMPLATES = [
    {
        "location": "Duliajan",
        "activity": "Transformer replacement at Substation Alpha",
        "base_text": """Incident Date: {date}
Incident ID: {incident_id}
Location: {location}
Worker Count: {workers}
Injury Severity: {severity}

Incident Description:
The crew was scheduled to replace a {transformer_type} transformer before the outage window ended. During the work, {weather_condition} began. The electrical hazard was recognized by the lead worker, who noted that the wet surfaces increased the risk of arc flash. {precursor_text}

The crew was under pressure to complete the work before the outage window closed. {lsr_text}

Immediate Actions Taken:
The crew continued working despite the increased hazard. No stop-work authority was exercised.
""",
        "precursors": [
            ("departure_from_routine", "Unexpected rain began during the transformer replacement."),
            ("hazard_recognition", "The electrical hazard was recognized by the lead worker, who noted that the wet surfaces increased the risk of arc flash."),
            ("plan_to_address_work_change", "No revised plan was developed after the rain started."),
            ("productivity_pressure", "The crew was under pressure to complete the work before the outage window closed."),
            ("risk_normalization", "One junior worker mentioned concern about the wet conditions but was told by the supervisor that they had done this many times before and it would be fine."),
            ("familiarity_with_task", "The supervisor noted that the crew had completed similar transformer replacements many times previously."),
            ("stop_work_execution", "No stop-work authority was exercised."),
            ("pre_task_plan", "The revised weather conditions were not included in the original pre-task plan."),
        ],
        "lsr_options": [
            ("LSR02", "Energy isolation was not verified before starting work on the transformer."),
            ("LSR03", "Workers positioned themselves in the line of fire during crane operations."),
            ("LSR09", "Fall protection not used while working on elevated transformer platform."),
        ]
    },
    {
        "location": "Moran",
        "activity": "Pipeline maintenance in confined space",
        "base_text": """Incident Date: {date}
Incident ID: {incident_id}
Location: {location}
Worker Count: {workers}
Injury Severity: {severity}

Incident Description:
Maintenance crew entered a {space_type} for {maintenance_task}. The confined space permit was {permit_status}. {precursor_text}

The supervisor stated that the team was experienced and had worked in similar conditions before. {lsr_text}

Immediate Actions Taken:
Work continued without proper atmospheric monitoring. No one raised concerns about the permit status.
""",
        "precursors": [
            ("safe_work_procedure", "The safe work procedure for confined space entry was not followed."),
            ("hazard_recognition", "The atmospheric hazard was not recognized before entry."),
            ("departure_from_routine", "Entry was made without the standard gas testing procedure."),
            ("plan_to_address_work_change", "No plan was in place for changing atmospheric conditions."),
            ("productivity_pressure", "The crew was under pressure to complete the maintenance before shift end."),
            ("rules_and_procedures", "Confined space entry procedures were not followed."),
            ("stop_work_execution", "Stop-work authority was not exercised when gas tester alarmed."),
        ],
        "lsr_options": [
            ("LSR04", "Confined space entered without valid permit and atmospheric testing."),
            ("LSR02", "Energy isolation not verified for connected piping."),
            ("LSR03", "No attendant posted outside confined space entry."),
        ]
    },
    {
        "location": "Digboi",
        "activity": "Hot work on crude oil storage tank",
        "base_text": """Incident Date: {date}
Incident ID: {incident_id}
Location: {location}
Worker Count: {workers}
Injury Severity: {severity}

Incident Description:
Welding crew performed hot work on a {tank_type} crude oil storage tank. The hot work permit was {permit_status}. {precursor_text}

The crew had adequate time to complete the work and there was no schedule pressure. {lsr_text}

Immediate Actions Taken:
Fire watch was posted but no gas monitoring was performed during work. Work continued when vapors detected.
""",
        "precursors": [
            ("hazard_recognition", "Vapor hazard was not recognized before hot work commenced."),
            ("safe_work_procedure", "Hot work permit requirements were not fully met."),
            ("departure_from_routine", "Work proceeded despite changing wind direction carrying vapors."),
            ("plan_to_address_work_change", "No revised plan when gas monitor indicated LEL increase."),
            ("risk_normalization", "Crew assumed tank was safe because it had been cleaned previously."),
            ("pre_task_plan", "Pre-task plan did not address continuous gas monitoring requirement."),
            ("stop_work_execution", "Stop-work authority not exercised when vapors detected."),
        ],
        "lsr_options": [
            ("LSR05", "Hot work performed without proper fire blankets and spark containment."),
            ("LSR02", "Adjacent piping not isolated and de-energized."),
            ("LSR07", "Gas monitor not calibrated before use."),
        ]
    },
    {
        "location": "Power Plant Unit 3",
        "activity": "Turbine maintenance and inspection",
        "base_text": """Incident Date: {date}
Incident ID: {incident_id}
Location: {location}
Worker Count: {workers}
Injury Severity: {severity}

Incident Description:
Technicians performed {maintenance_type} maintenance on the {equipment_turbine}. The technicians followed the standard operating procedure and completed the pre-task safety briefing as required. {precursor_text}

Both workers were properly trained on the equipment and had several years of experience with turbine maintenance. {lsr_text}

Immediate Actions Taken:
Stop-work authority was exercised appropriately. The crew halted the work and waited for the engineering team to assess the situation.
""",
        "precursors": [
            ("safe_work_procedure", "The technicians followed the standard operating procedure and completed the pre-task safety briefing as required."),
            ("familiarity_with_task", "Both workers were properly trained on the equipment and had several years of experience with turbine maintenance."),
            ("pre_task_plan", "The pre-task plan was comprehensive and included the cooling pump inspection."),
            ("perceived_safety_culture", "The safety culture at the facility was supportive of workers reporting concerns without fear of reprisal."),
            ("stop_work_execution", "Stop-work authority was exercised appropriately."),
            ("productivity_pressure", "No productivity pressure was applied to continue the work."),
        ],
        "lsr_options": [
            ("LSR01", "Valid work permit obtained and verified before maintenance."),
            ("LSR02", "Energy isolation verified by independent person before work."),
            ("LSR09", "Fall protection used for elevated turbine access."),
        ]
    },
    {
        "location": "Tinsukia",
        "activity": "Excavation near buried pipeline",
        "base_text": """Incident Date: {date}
Incident ID: {incident_id}
Location: {location}
Worker Count: {workers}
Injury Severity: {severity}

Incident Description:
Excavation crew using {equipment_excavation} near buried {pipeline_type} pipeline. The excavation permit was {permit_status}. {precursor_text}

The operator was experienced but the ground conditions were different from the drawings. {lsr_text}

Immediate Actions Taken:
Excavation continued despite proximity to pipeline. No hand digging verification performed.
""",
        "precursors": [
            ("hazard_recognition", "Pipeline hazard not recognized in excavation planning."),
            ("departure_from_routine", "Unexpected soil conditions encountered during excavation."),
            ("plan_to_address_work_change", "No revised plan when pipeline proximity identified."),
            ("safe_work_procedure", "Hand digging verification not performed near pipeline."),
            ("rules_and_procedures", "Excavation permit requirements not fully met."),
            ("risk_normalization", "Crew assumed pipeline was deeper based on old drawings."),
            ("stop_work_execution", "Stop-work authority not exercised when pipeline locate marks unclear."),
        ],
        "lsr_options": [
            ("LSR06", "Excavator operated without spotter near pipeline."),
            ("LSR03", "Workers in line of fire of potential pipeline strike."),
            ("LSR07", "Pipeline locator not calibrated/verified before use."),
        ]
    },
]

SEVERITIES = ["Near Miss", "First Aid", "Medical Treatment", "Lost Time Injury", "Fatality"]
TRANSFORMER_TYPES = ["power", "distribution", "instrument"]
WEATHER_CONDITIONS = ["unexpected rain", "heavy rain", "thunderstorm", "high winds"]
SPACE_TYPES = ["storage tank", "process vessel", "separator", "heat exchanger"]
MAINTENANCE_TASKS = ["inspection", "cleaning", "repair", "valve replacement"]
PERMIT_STATUSES = ["obtained and valid", "obtained but incomplete", "not obtained", "expired"]
TANK_TYPES = ["floating roof", "fixed roof", "pressure"]
MAINTENANCE_TYPES = ["routine", "major overhaul", "bearing inspection", "vibration analysis"]
EQUIPMENT = ["gas turbine", "steam turbine", "compressor", "generator"]
EXCAVATION_EQUIPMENT = ["backhoe", "excavator", "trencher"]
PIPELINE_TYPES = ["crude oil", "natural gas", "water injection", "produced water"]

def generate_report(template, i, total):
    """Generate a single report with controlled SIF score variation."""
    # Determine SIF level target
    sif_target = random.choices(
        ["low", "medium", "high", "very_high"],
        weights=[0.3, 0.35, 0.25, 0.1]
    )[0]
    
    # Select precursors based on target
    if sif_target == "low":
        num_present = random.randint(0, 2)
        severity = random.choice(["Near Miss", "First Aid"])
    elif sif_target == "medium":
        num_present = random.randint(3, 5)
        severity = random.choice(["First Aid", "Medical Treatment"])
    elif sif_target == "high":
        num_present = random.randint(5, 7)
        severity = random.choice(["Medical Treatment", "Lost Time Injury"])
    else:
        max_present = min(7, len(template["precursors"]))
        num_present = random.randint(max_present, len(template["precursors"]))
        severity = random.choice(["Lost Time Injury", "Fatality"])
    
    # Shuffle and select precursors
    shuffled = template["precursors"][:]
    random.shuffle(shuffled)
    selected = shuffled[:num_present]
    remaining = shuffled[num_present:]
    
    # Build precursor text
    present_texts = [p[1] for p in selected]
    absent_texts = [p[1].replace("was", "was not").replace("were", "were not") for p in remaining[:2]]
    precursor_text = " ".join(present_texts + absent_texts)
    
    # Build LSR text
    lsr_text = ""
    if template["lsr_options"] and random.random() > 0.3:
        lsr = random.choice(template["lsr_options"])
        lsr_text = f"Life-Saving Rule {lsr[0]} ({lsr[1]}) was relevant to this activity."
    
    incident_id = f"INC-2026-{i:03d}"
    date = f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
    workers = random.randint(2, 8)
    
    text = template["base_text"].format(
        date=date,
        incident_id=incident_id,
        location=template["location"],
        workers=workers,
        severity=severity,
        transformer_type=random.choice(TRANSFORMER_TYPES),
        weather_condition=random.choice(WEATHER_CONDITIONS),
        precursor_text=precursor_text,
        lsr_text=lsr_text,
        space_type=random.choice(SPACE_TYPES),
        maintenance_task=random.choice(MAINTENANCE_TASKS),
        permit_status=random.choice(PERMIT_STATUSES),
        tank_type=random.choice(TANK_TYPES),
        maintenance_type=random.choice(MAINTENANCE_TYPES),
        equipment_turbine=random.choice(EQUIPMENT),
        pipeline_type=random.choice(PIPELINE_TYPES),
        equipment_excavation=random.choice(EXCAVATION_EQUIPMENT),
    )
    
    return {
        "incident_id": incident_id,
        "date": date,
        "location": template["location"],
        "raw_text": text,
    }

def main():
    apply_schema()
    
    num_reports = 100
    print(f"Generating {num_reports} dummy reports...")
    
    success = 0
    for i in range(1, num_reports + 1):
        template = random.choice(TEMPLATES)
        report = generate_report(template, i, num_reports)
        
        try:
            result = nlp_service.analyze_and_ingest(
                raw_text=report["raw_text"],
                incident_id=report["incident_id"],
                date=report["date"],
                location=report["location"],
            )
            sif = result.get("sif_score", {})
            print(f"  [{i}/{num_reports}] {report['incident_id']} @ {report['location']} - SIF: {sif.get('value', 0):.3f} ({sif.get('class', 'N/A')})")
            success += 1
        except Exception as e:
            print(f"  [{i}/{num_reports}] {report['incident_id']} FAILED: {e}")
    
    print(f"\nDone: {success}/{num_reports} reports ingested successfully")

if __name__ == "__main__":
    main()
