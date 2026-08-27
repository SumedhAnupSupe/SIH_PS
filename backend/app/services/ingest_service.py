"""Shared report-ingestion core.

Used by the CLI (`scripts/ingest.py`) and the admin API (report edits).
Turns one NLP analysis JSON + optional feature dict into all derived rows
(precursors+evidence, hazards, tasks, work_changes, features, embedding)
inside a single DB connection.
"""
import json

from sqlalchemy import text as sa_text

from app.services.embeddings import compose_safety_repr, embed

PRECURSOR_ORDER = [
    "safe_work_procedure", "hazard_recognition", "departure_from_routine",
    "plan_to_address_work_change", "safety_attitudes", "rules_and_procedures",
    "familiarity_with_task", "risk_normalization", "productivity_pressure",
    "perceived_safety_culture", "stop_work_execution",
    "workers_inactive_in_safety", "pre_task_plan",
]


def _get_or_create(conn, table, code, name=None):
    conn.execute(
        sa_text(f"INSERT INTO {table} (code, name) VALUES (:c,:n) ON CONFLICT (code) DO NOTHING"),
        {"c": code, "n": name or code},
    )
    return conn.execute(sa_text(f"SELECT id FROM {table} WHERE code=:c"), {"c": code}).scalar()


def _to_bool(v) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y"):
        return True
    if s in ("0", "false", "no", "n", "nan", ""):
        return False
    return None


import math

def _to_num(v):
    try:
        if v is None or str(v).lower() == "nan" or str(v) == "":
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _vec_str(vec) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def ingest_report(conn, analysis: dict, feats: dict | None = None,
                  raw_text: str = "", summary: str = "",
                  attention_output: dict | None = None) -> int | None:
    """Insert/update a report and all its derived rows. Returns reports.id."""
    meta = analysis.get("metadata", {}) or {}
    incident_id = meta.get("incident_id") or analysis.get("incident_id")
    if not incident_id:
        return None
    
    # Handle both old (sif.score/sif.class) and new (sif_score.value/sif_score.class) formats
    sif_score = analysis.get("sif_score") or {}
    sif = analysis.get("sif") or {}
    score = sif_score.get("value") if sif_score.get("value") is not None else sif.get("score")
    cls = sif_score.get("class") if sif_score.get("class") is not None else sif.get("class")
    sif_method = sif_score.get("method")
    sif_weight_source = sif_score.get("weight_source")
    sif_components = sif_score.get("components")
    
    feats = feats or {}

    rid = conn.execute(
        sa_text(
            "INSERT INTO reports (incident_id, location, event_date, injury_severity, raw_text, summary, "
            "sif_score, sif_class, sif_method, sif_weight_source, sif_components, analysis_json) "
            "VALUES (:iid,:loc,:d,:sev,:raw,:sum,:score,:cls,:meth,:wsrc,:scomp,:aj) "
            "ON CONFLICT (incident_id) DO UPDATE SET "
            "location=EXCLUDED.location, event_date=EXCLUDED.event_date, "
            "injury_severity=EXCLUDED.injury_severity, "
            "sif_score=EXCLUDED.sif_score, sif_class=EXCLUDED.sif_class, "
            "sif_method=EXCLUDED.sif_method, sif_weight_source=EXCLUDED.sif_weight_source, "
            "sif_components=EXCLUDED.sif_components, "
            "raw_text=EXCLUDED.raw_text, summary=EXCLUDED.summary, "
            "analysis_json=EXCLUDED.analysis_json "
            "RETURNING id"
        ),
        {
            "iid": incident_id, "loc": meta.get("location"), "d": meta.get("incident_date"),
            "sev": meta.get("injury_severity"), "raw": raw_text, "sum": summary,
            "score": score, "cls": cls, "meth": sif_method, "wsrc": sif_weight_source,
            "scomp": json.dumps(sif_components) if sif_components else None,
            "aj": json.dumps(analysis),
        },
    ).scalar()

    # derived data is regenerated; NOTE analysis_runs is intentionally NOT
    # cleared here — the audit/override trail is append-only.
    for tbl in ("precursor_evidence", "report_precursors", "report_hazards",
                "report_task_types", "report_work_changes", "report_features",
                "report_life_saving_rules", "lsr_evidence"):
        conn.execute(sa_text(f"DELETE FROM {tbl} WHERE report_id=:r"), {"r": rid})

    # --- precursors + evidence ---
    prec = analysis.get("precursor_analysis", {}) or {}
    present_precursors = []
    for code in PRECURSOR_ORDER:
        node = prec.get(code) or {}
        status = (node.get("status") or "NOT_MENTIONED").upper()
        if status not in ("PRESENT", "AMBIGUOUS", "NOT_MENTIONED"):
            status = "NOT_MENTIONED"
        pid = _get_or_create(conn, "precursors", code)
        conn.execute(
            sa_text(
                "INSERT INTO report_precursors (report_id, precursor_id, status, confidence, evidence_count) "
                "VALUES (:r,:p,:s,:cf,:e) ON CONFLICT (report_id, precursor_id) DO UPDATE SET "
                "status=EXCLUDED.status, confidence=EXCLUDED.confidence, evidence_count=EXCLUDED.evidence_count"
            ),
            {"r": rid, "p": pid, "s": status, "cf": node.get("confidence"), "e": node.get("evidence_count")},
        )
        if status in ("PRESENT", "AMBIGUOUS"):
            present_precursors.append(code)
        for polarity, key in (("present", "present_evidence"), ("absent", "absent_evidence")):
            for ev in node.get(key, []) or []:
                conn.execute(
                    sa_text(
                        "INSERT INTO precursor_evidence (report_id, precursor_id, evidence_text, sentence_id, polarity) "
                        "VALUES (:r,:p,:t,:s,:pl)"
                    ),
                    {"r": rid, "p": pid, "t": ev.get("text"), "s": ev.get("source_sentence_id"), "pl": polarity},
                )

    # --- hazards ---
    for h in analysis.get("hazards", []) or []:
        code = h.get("hazard_type")
        if not code:
            continue
        hid = _get_or_create(conn, "hazards", code)
        conn.execute(
            sa_text(
                "INSERT INTO report_hazards (report_id, hazard_id, evidence) "
                "VALUES (:r,:h,:e) ON CONFLICT (report_id, hazard_id) DO NOTHING"
            ),
            {"r": rid, "h": hid, "e": json.dumps(h.get("evidence", []))},
        )

    # --- task types ---
    task_types = []
    for t in analysis.get("task_types", []) or []:
        code = t.get("task_type")
        if not code:
            continue
        tid = _get_or_create(conn, "task_types", code)
        task_types.append(code)
        conn.execute(
            sa_text(
                "INSERT INTO report_task_types (report_id, task_type_id, evidence) "
                "VALUES (:r,:t,:e) ON CONFLICT (report_id, task_type_id) DO NOTHING"
            ),
            {"r": rid, "t": tid, "e": json.dumps(t.get("evidence", []))},
        )

    # --- work changes ---
    wc = analysis.get("work_changes", {}) or {}
    if wc:
        conn.execute(
            sa_text(
                "INSERT INTO report_work_changes (report_id, work_plan_changed, unexpected_condition, task_changed,"
                "equipment_changed, procedure_changed, work_sequence_changed, reassessment_performed, reassessment_missing) "
                "VALUES (:r,:a,:b,:c,:d,:e,:f,:g,:h) ON CONFLICT (report_id) DO NOTHING"
            ),
            {
                "r": rid, "a": wc.get("work_plan_changed"), "b": wc.get("unexpected_condition"),
                "c": wc.get("task_changed"), "d": wc.get("equipment_changed"),
                "e": wc.get("procedure_changed"), "f": wc.get("work_sequence_changed"),
                "g": wc.get("reassessment_performed"), "h": wc.get("reassessment_missing"),
            },
        )

    # --- features ---
    def _clean_for_json(obj):
        if isinstance(obj, dict):
            return {k: _clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_clean_for_json(v) for v in obj]
        elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj

    clean_feats = _clean_for_json(feats)
    conn.execute(
        sa_text(
            "INSERT INTO report_features (report_id, control_failure_present, missing_control_present,"
            "barrier_failure_present, control_deviation_present, report_length, sentence_count,"
            "relevant_sentence_count, relevance_ratio, features) "
            "VALUES (:r,:cf,:mf,:bf,:cd,:rl,:sc,:rsc,:rr,:fe) "
            "ON CONFLICT (report_id) DO UPDATE SET features=EXCLUDED.features, "
            "control_failure_present=EXCLUDED.control_failure_present,"
            "missing_control_present=EXCLUDED.missing_control_present,"
            "barrier_failure_present=EXCLUDED.barrier_failure_present,"
            "control_deviation_present=EXCLUDED.control_deviation_present"
        ),
        {
            "r": rid, "cf": _to_bool(feats.get("control_failure_present")),
            "mf": _to_bool(feats.get("missing_control_present")),
            "bf": _to_bool(feats.get("barrier_failure_present")),
            "cd": _to_bool(feats.get("control_deviation_present")),
            "rl": _to_num(feats.get("report_length")), "sc": _to_num(feats.get("sentence_count")),
            "rsc": _to_num(feats.get("relevant_sentence_count")), "rr": _to_num(feats.get("relevance_ratio")),
            "fe": json.dumps(clean_feats),
        },
    )

    # --- Life-Saving Rules ---
    lsr_analysis = analysis.get("life_saving_rules") or {}
    for rule in lsr_analysis.get("analysis", []) or []:
        # New model uses rule_name; old model uses rule_id. Handle both.
        rule_id_val = rule.get("rule_id") or rule.get("rule_name", "UNKNOWN")
        lsr_id = conn.execute(
            sa_text("INSERT INTO life_saving_rules (rule_id, name, description) VALUES (:rid,:n,:d) ON CONFLICT (rule_id) DO NOTHING RETURNING id"),
            {"rid": rule_id_val, "n": rule.get("rule_name", rule_id_val), "d": rule.get("description")},
        ).scalar()
        if not lsr_id:
            lsr_id = conn.execute(sa_text("SELECT id FROM life_saving_rules WHERE rule_id=:rid"), {"rid": rule_id_val}).scalar()
        conn.execute(
            sa_text(
                "INSERT INTO report_life_saving_rules (report_id, lsr_id, status, confidence, reason, applicable) "
                "VALUES (:r,:l,:s,:cf,:rs,:ap) ON CONFLICT (report_id, lsr_id) DO UPDATE SET "
                "status=EXCLUDED.status, confidence=EXCLUDED.confidence, reason=EXCLUDED.reason, applicable=EXCLUDED.applicable"
            ),
            {
                "r": rid, "l": lsr_id, "s": rule.get("status"),
                "cf": rule.get("confidence"), "rs": rule.get("reason"), "ap": rule.get("applicable"),
            },
        )
        # Evidence (old model: broken_evidence/compliance_evidence; new model: evidence)
        for ev in rule.get("broken_evidence", []) or []:
            conn.execute(
                sa_text(
                    "INSERT INTO lsr_evidence (report_id, lsr_id, evidence_text, sentence_id, evidence_type) "
                    "VALUES (:r,:l,:t,:s,:et)"
                ),
                {"r": rid, "l": lsr_id, "t": ev.get("text"), "s": ev.get("source_sentence_id"), "et": "broken"},
            )
        for ev in rule.get("compliance_evidence", []) or []:
            conn.execute(
                sa_text(
                    "INSERT INTO lsr_evidence (report_id, lsr_id, evidence_text, sentence_id, evidence_type) "
                    "VALUES (:r,:l,:t,:s,:et)"
                ),
                {"r": rid, "l": lsr_id, "t": ev.get("text"), "s": ev.get("source_sentence_id"), "et": "compliance"},
            )
        # New model format: rule["evidence"] is a list of evidence items
        for ev in rule.get("evidence", []) or []:
            if ev.get("text"):
                conn.execute(
                    sa_text(
                        "INSERT INTO lsr_evidence (report_id, lsr_id, evidence_text, sentence_id, evidence_type) "
                        "VALUES (:r,:l,:t,:s,:et)"
                    ),
                    {"r": rid, "l": lsr_id, "t": ev.get("text"), "s": ev.get("source_sentence_id"), "et": "rule_evidence"},
                )

    # --- embedding from entity-composed string (optional, requires pgvector) ---
    try:
        # Check if embedding column exists before attempting update
        has_emb = conn.execute(
            sa_text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='reports' AND column_name='embedding')")
        ).scalar()
        if has_emb:
            hazards = [h.get("hazard_type") for h in analysis.get("hazards", []) or []]
            safety_repr = compose_safety_repr({
                "location": meta.get("location"),
                "task_types": task_types,
                "hazards": [h for h in hazards if h],
                "present_precursors": present_precursors,
                "barrier_failure": _to_bool(feats.get("barrier_failure_present")),
                "work_changes": wc,
            })
            vec = embed([safety_repr])[0]
            conn.execute(
                sa_text("UPDATE reports SET embedding=:v WHERE id=:r"),
                {"v": _vec_str(vec), "r": rid},
            )
    except Exception:
        pass  # pgvector not available, skip embedding

    # --- location linking ---
    location_name = meta.get("location")
    if location_name:
        lid = conn.execute(
            sa_text("INSERT INTO locations (name) VALUES (:n) ON CONFLICT (name) DO NOTHING RETURNING id"),
            {"n": location_name},
        ).scalar()
        if not lid:
            lid = conn.execute(sa_text("SELECT id FROM locations WHERE name=:n"), {"n": location_name}).scalar()
        if lid:
            conn.execute(sa_text("UPDATE reports SET location_id=:l WHERE id=:r"), {"l": lid, "r": rid})

    # --- unified tree classification -> sif_class ---
    unified_tree = analysis.get("unified_tree") or {}
    tree_classification = unified_tree.get("classification")
    if tree_classification:
        conn.execute(
            sa_text("UPDATE reports SET sif_class=:c WHERE id=:r"),
            {"c": tree_classification, "r": rid},
        )

    # --- SIF assessment from attention model ---
    if attention_output:
        conn.execute(
            sa_text(
                "INSERT INTO sif_assessments "
                "(report_id, attention_level, urgency_score, risk_potential, systemic_attention, "
                "systemic_score, confidence, prediction_mode, actions, drivers, uncertainty, "
                "barrier_failure_rate, model_version) "
                "VALUES (:r,:al,:us,:rp,:sa,:ss,:cf,:pm,:act,:drv,:unc,:bfr,:mv) "
                "ON CONFLICT (report_id) DO UPDATE SET "
                "attention_level=EXCLUDED.attention_level, urgency_score=EXCLUDED.urgency_score, "
                "risk_potential=EXCLUDED.risk_potential, systemic_attention=EXCLUDED.systemic_attention, "
                "systemic_score=EXCLUDED.systemic_score, confidence=EXCLUDED.confidence, "
                "prediction_mode=EXCLUDED.prediction_mode, actions=EXCLUDED.actions, "
                "drivers=EXCLUDED.drivers, uncertainty=EXCLUDED.uncertainty, "
                "barrier_failure_rate=EXCLUDED.barrier_failure_rate, model_version=EXCLUDED.model_version"
            ),
            {
                "r": rid,
                "al": attention_output.get("attention", {}).get("level"),
                "us": attention_output.get("attention", {}).get("urgency_score"),
                "rp": attention_output.get("risk_potential_score"),
                "sa": attention_output.get("attention", {}).get("systemic_attention"),
                "ss": attention_output.get("attention", {}).get("systemic_attention_score"),
                "cf": attention_output.get("attention", {}).get("confidence"),
                "pm": attention_output.get("prediction_mode"),
                "act": json.dumps(attention_output.get("actions", [])),
                "drv": json.dumps(attention_output.get("drivers", [])),
                "unc": json.dumps(attention_output.get("uncertainty", {})),
                "bfr": attention_output.get("barrier_failure_rate"),
                "mv": attention_output.get("model_metadata", {}).get("rule_engine_version"),
            },
        )

    return rid