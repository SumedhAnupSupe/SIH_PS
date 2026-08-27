"""Reports API - listing, detail, submission, analysis."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, engine
from app.services.nlp_service import nlp_service
from app.services.auth import get_current_user, optional_user
from app.services.gemini_service import chat_with_gemini

router = APIRouter(prefix="/api", tags=["reports"])


class RelatedReport(BaseModel):
    incident_id: str
    similarity: float
    location: str | None = None
    event_date: str | None = None
    injury_severity: str | None = None
    shared: list[str] = []


class AnalyzeRequest(BaseModel):
    raw_text: str
    incident_id: str | None = None
    date: str | None = None
    location: str | None = None


class AnalyzeResponse(BaseModel):
    report_id: int
    incident_id: str
    analysis: dict
    summary: str
    sif_score: dict
    life_saving_rules: dict


class ReportSubmission(BaseModel):
    """Multi-step guided report submission."""
    report_type: str = "OBSERVATION"
    event_date: str | None = None
    event_time: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    activity: str | None = None
    work_area: str | None = None
    equipment: str | None = None
    work_type: str | None = None
    raw_text: str
    unsafe_act: str | None = None
    unsafe_condition: str | None = None
    near_miss_details: str | None = None
    immediate_action: str | None = None
    witnesses: str | None = None


class SummaryEditRequest(BaseModel):
    summary: str


def _fetch_related(db: Session, incident_id: str, top_k: int) -> list[dict]:
    row = db.execute(
        text("SELECT id, location FROM reports WHERE incident_id=:i"), {"i": incident_id}
    ).fetchone()
    if not row:
        raise HTTPException(404, f"report {incident_id} not found")
    rid = row[0]
    loc = row[1]

    has_emb = db.execute(text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_name='reports' AND column_name='embedding')"
    )).scalar()

    if has_emb:
        base = (
            "SELECT r.id, r.incident_id, r.location, to_char(r.event_date,'YYYY-MM-DD') AS event_date, "
            "r.injury_severity, 1 - (r.embedding <=> src.embedding) AS sim "
            "FROM reports r, reports src WHERE src.id=:rid AND r.id <> :rid "
            "AND r.embedding IS NOT NULL AND src.embedding IS NOT NULL "
            "ORDER BY r.embedding <=> src.embedding LIMIT :k"
        )
        rows = db.execute(text(base), {"rid": rid, "k": top_k}).fetchall()
    else:
        rows = db.execute(text(
            "SELECT r.id, r.incident_id, r.location, to_char(r.event_date,'YYYY-MM-DD') AS event_date, "
            "r.injury_severity, "
            "CASE WHEN r.location = :loc THEN 0.5 ELSE 0.0 END AS sim "
            "FROM reports r WHERE r.id <> :rid "
            "AND (r.location = :loc OR EXISTS ("
            "  SELECT 1 FROM report_precursors rp1 "
            "  JOIN report_precursors rp2 ON rp1.precursor_id = rp2.precursor_id "
            "  WHERE rp1.report_id = :rid AND rp2.report_id = r.id "
            "  AND rp1.status IN ('PRESENT','AMBIGUOUS') AND rp2.status IN ('PRESENT','AMBIGUOUS')"
            ")) ORDER BY sim DESC LIMIT :k"
        ), {"rid": rid, "k": top_k, "loc": loc}).fetchall()

    return [
        {
            "incident_id": r[1], "location": r[2], "event_date": r[3],
            "injury_severity": r[4], "similarity": round(float(r[5] or 0), 3),
        }
        for r in rows
    ]


def _enrich_shared(db: Session, rid: int, related: list[dict]) -> None:
    src = {
        "prec": {x[0] for x in db.execute(text(
            "SELECT precursor_id FROM report_precursors WHERE report_id=:r AND status IN ('PRESENT','AMBIGUOUS')"
        ), {"r": rid})},
        "hazard": {x[0] for x in db.execute(text(
            "SELECT hazard_id FROM report_hazards WHERE report_id=:r"), {"r": rid})},
        "task": {x[0] for x in db.execute(text(
            "SELECT task_type_id FROM report_task_types WHERE report_id=:r"), {"r": rid})},
    }
    for rel in related:
        other = db.execute(
            text("SELECT id FROM reports WHERE incident_id=:i"), {"i": rel["incident_id"]}
        ).fetchone()
        if not other:
            continue
        oid = other[0]
        o_prec = {x[0] for x in db.execute(text(
            "SELECT precursor_id FROM report_precursors WHERE report_id=:r AND status IN ('PRESENT','AMBIGUOUS')"
        ), {"r": oid})}
        o_haz = {x[0] for x in db.execute(text(
            "SELECT hazard_id FROM report_hazards WHERE report_id=:r"), {"r": oid})}
        o_task = {x[0] for x in db.execute(text(
            "SELECT task_type_id FROM report_task_types WHERE report_id=:r"), {"r": oid})}
        shared = []
        if o_prec & src["prec"]:
            shared.append("same precursor")
        if o_haz & src["hazard"]:
            shared.append("same hazard")
        if o_task & src["task"]:
            shared.append("same task type")
        rel["shared"] = shared


@router.get("/reports", summary="List reports")
def list_reports(
    limit: int = Query(50),
    offset: int = Query(0),
    location: str | None = Query(None),
    sif_class: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    report_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    conditions = []
    params: dict = {"l": limit, "o": offset}
    if location:
        conditions.append("r.location ILIKE :loc")
        params["loc"] = f"%{location}%"
    if sif_class:
        conditions.append("r.sif_class = :cls")
        params["cls"] = sif_class.upper()
    if start_date:
        conditions.append("r.event_date >= :sd")
        params["sd"] = start_date
    if end_date:
        conditions.append("r.event_date <= :ed")
        params["ed"] = end_date
    if report_type:
        conditions.append("r.report_type = :rt")
        params["rt"] = report_type
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = db.execute(
        text(
            f"SELECT r.incident_id, r.location, to_char(r.event_date,'YYYY-MM-DD') AS d, "
            f"r.injury_severity, r.sif_score, r.sif_class, r.report_type, r.activity, "
            f"r.processing_state, l.name AS loc_name "
            f"FROM reports r LEFT JOIN locations l ON l.id = r.location_id "
            f"{where} ORDER BY r.event_date DESC NULLS LAST LIMIT :l OFFSET :o"
        ),
        params,
    ).fetchall()
    total = db.execute(text(f"SELECT count(*) FROM reports r {where}"), 
                       {k: v for k, v in params.items() if k not in ("l", "o")}).scalar()
    return {"total": total, "items": [dict(r._mapping) for r in rows]}


@router.get("/reports/{incident_id}", summary="Full report with analysis")
def get_report(incident_id: str, db: Session = Depends(get_db)):
    r = db.execute(
        text(
            "SELECT id, incident_id, location, to_char(event_date,'YYYY-MM-DD') AS event_date, "
            "event_time, injury_severity, raw_text, sif_score, sif_class, sif_method, "
            "sif_weight_source, sif_components, report_type, activity, work_area, "
            "equipment, work_type, unsafe_act, unsafe_condition, near_miss_details, "
            "immediate_action, witnesses, processing_state, submitted_at "
            "FROM reports WHERE incident_id=:i"
        ),
        {"i": incident_id},
    ).one_or_none()
    if not r:
        raise HTTPException(404, "not found")
    rid = r._mapping["id"]

    # Current summary from report_summaries table
    summary_row = db.execute(text(
        "SELECT summary_text, summary_type, version, edited_by, edited_at, created_at "
        "FROM report_summaries WHERE report_id=:rid AND is_current=TRUE"
    ), {"rid": rid}).mappings().first()

    # Also get the report.summary as fallback
    report_summary = r._mapping.get("raw_text")  # we'll use report_summaries

    precursors = db.execute(
        text(
            "SELECT p.code, p.name, rp.status, rp.confidence, rp.evidence_count "
            "FROM report_precursors rp JOIN precursors p ON p.id=rp.precursor_id WHERE rp.report_id=:r "
            "ORDER BY rp.status, rp.confidence DESC"
        ),
        {"r": rid},
    ).fetchall()
    evidence = db.execute(
        text(
            "SELECT pe.evidence_text, pe.sentence_id, pe.polarity FROM precursor_evidence pe "
            "WHERE pe.report_id=:r ORDER BY pe.polarity"
        ),
        {"r": rid},
    ).fetchall()
    hazards = db.execute(
        text(
            "SELECT p.code, rh.evidence FROM report_hazards rh JOIN hazards p ON p.id=rh.hazard_id WHERE rh.report_id=:r"
        ),
        {"r": rid},
    ).fetchall()
    tasks = db.execute(
        text(
            "SELECT p.code, rt.evidence FROM report_task_types rt JOIN task_types p ON p.id=rt.task_type_id WHERE rt.report_id=:r"
        ),
        {"r": rid},
    ).fetchall()
    wc = db.execute(
        text("SELECT * FROM report_work_changes WHERE report_id=:r"), {"r": rid}
    ).one_or_none()
    feats = db.execute(
        text("SELECT * FROM report_features WHERE report_id=:r"), {"r": rid}
    ).one_or_none()

    lsr = db.execute(
        text(
            "SELECT lsr.rule_id, lsr.name, rlsr.status, rlsr.confidence, rlsr.reason, rlsr.applicable "
            "FROM report_life_saving_rules rlsr JOIN life_saving_rules lsr ON lsr.id=rlsr.lsr_id "
            "WHERE rlsr.report_id=:r ORDER BY lsr.rule_id"
        ),
        {"r": rid},
    ).fetchall()
    lsr_evidence = db.execute(
        text(
            "SELECT lsr.rule_id, le.evidence_text, le.sentence_id, le.evidence_type "
            "FROM lsr_evidence le JOIN life_saving_rules lsr ON lsr.id=le.lsr_id "
            "WHERE le.report_id=:r ORDER BY lsr.rule_id, le.evidence_type"
        ),
        {"r": rid},
    ).fetchall()

    sif_assess = db.execute(
        text(
            "SELECT attention_level, urgency_score, risk_potential, systemic_attention, "
            "systemic_score, confidence, prediction_mode, actions, drivers, uncertainty, "
            "barrier_failure_rate, model_version "
            "FROM sif_assessments WHERE report_id=:r"
        ),
        {"r": rid},
    ).one_or_none()

    barriers = db.execute(
        text(
            "SELECT b.code, b.name, rb.status, rb.confidence, rb.reason "
            "FROM report_barriers rb JOIN barriers b ON b.id=rb.barrier_id "
            "WHERE rb.report_id=:r"
        ),
        {"r": rid},
    ).fetchall()

    # Related patterns
    related_patterns = db.execute(text(
        "SELECT p.id, p.title, p.pattern_score, p.priority_level "
        "FROM pattern_reports pr JOIN patterns p ON p.id = pr.pattern_id "
        "WHERE pr.report_id = :r ORDER BY p.pattern_score DESC LIMIT 5"
    ), {"r": rid}).fetchall()

    return {
        "report": dict(r._mapping),
        "summary": dict(summary_row) if summary_row else {"summary_text": r._mapping.get("summary"), "summary_type": "g legacy"},
        "precursors": [dict(p._mapping) for p in precursors],
        "evidence": [dict(e._mapping) for e in evidence],
        "hazards": [{"code": h[0], "evidence": h[1]} for h in hazards],
        "task_types": [{"code": t[0], "evidence": t[1]} for t in tasks],
        "work_changes": dict(wc._mapping) if wc else None,
        "features": dict(feats._mapping) if feats else None,
        "life_saving_rules": [dict(l._mapping) for l in lsr],
        "lsr_evidence": [dict(e._mapping) for e in lsr_evidence],
        "sif_assessment": dict(sif_assess._mapping) if sif_assess else None,
        "barriers": [dict(b._mapping) for b in barriers],
        "related_patterns": [dict(p._mapping) for p in related_patterns],
    }


@router.get("/reports/{incident_id}/related", summary="Related reports (v1)")
def related(incident_id: str, db: Session = Depends(get_db)):
    results = _fetch_related(db, incident_id, settings.top_k)
    if not results:
        db.execute(text("SELECT id FROM reports WHERE incident_id=:i"), {"i": incident_id}).one()
        return {"related": results}
    rid = db.execute(
        text("SELECT id FROM reports WHERE incident_id=:i"), {"i": incident_id}
    ).scalar()
    _enrich_shared(db, rid, results)
    return {"incident_id": incident_id, "related": results}


@router.post("/reports", summary="Submit a new report (multi-step guided form)")
def submit_report(body: ReportSubmission, db: Session = Depends(get_db)):
    """Submit a structured report. Original report is immutable after submission."""
    # Generate immutable report ID
    incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:6].upper()}"

    # Resolve location
    location_name = body.location_name
    location_id = body.location_id
    if not location_name and location_id:
        loc_row = db.execute(text("SELECT name FROM locations WHERE id=:id"), {"id": location_id}).fetchone()
        if loc_row:
            location_name = loc_row[0]

    # Create raw text from structured fields
    raw_text_parts = [body.raw_text]
    if body.unsafe_act:
        raw_text_parts.append(f"Unsafe Act: {body.unsafe_act}")
    if body.unsafe_condition:
        raw_text_parts.append(f"Unsafe Condition: {body.unsafe_condition}")
    if body.near_miss_details:
        raw_text_parts.append(f"Near Miss Details: {body.near_miss_details}")
    if body.immediate_action:
        raw_text_parts.append(f"Immediate Action: {body.immediate_action}")
    full_text = "\n\n".join(raw_text_parts)

    # Store the report with structured fields
    rid = db.execute(text(
        "INSERT INTO reports (incident_id, location, location_id, event_date, event_time, "
        "injury_severity, raw_text, report_type, activity, work_area, equipment, work_type, "
        "unsafe_act, unsafe_condition, near_miss_details, immediate_action, witnesses, "
        "processing_state, submitted_at) "
        "VALUES (:iid, :loc, :lid, :ed, :et, :sev, :raw, :rt, :act, :wa, :eq, :wt, "
        ":ua, :uc, :nm, :ia, :w, :ps, :sat) "
        "RETURNING id"
    ), {
        "iid": incident_id, "loc": location_name, "lid": location_id,
        "ed": body.event_date, "et": body.event_time,
        "sev": body.near_miss_details and "Near Miss" or "Observation",
        "raw": full_text, "rt": body.report_type, "act": body.activity,
        "wa": body.work_area, "eq": body.equipment, "wt": body.work_type,
        "ua": body.unsafe_act, "uc": body.unsafe_condition,
        "nm": body.near_miss_details, "ia": body.immediate_action,
        "w": body.witnesses, "ps": "SUBMITTED", "sat": datetime.now(timezone.utc),
    }).scalar()

    # Link location if needed
    if location_id:
        db.execute(text("UPDATE reports SET location_id=:lid WHERE id=:rid"), {"lid": location_id, "rid": rid})

    db.commit()

    # Kick off background analysis (simplified - inline for now)
    try:
        _process_report_inline(rid, full_text, incident_id, location_name, body.event_date)
    except Exception as e:
        db.execute(text("UPDATE reports SET processing_state='ANALYSIS_FAILED' WHERE id=:rid"), {"rid": rid})
        db.commit()

    return {
        "report_id": rid,
        "incident_id": incident_id,
        "status": "submitted",
        "processing_state": "PROCESSING",
    }


def _process_report_inline(rid: int, raw_text: str, incident_id: str, location: str | None, date: str | None):
    """Run NLP pipeline inline and store results."""
    try:
        db = Session(bind=engine)
        db.execute(text("UPDATE reports SET processing_state='PROCESSING' WHERE id=:rid"), {"rid": rid})
        db.commit()

        result = nlp_service.analyze_and_ingest(
            raw_text=raw_text,
            incident_id=incident_id,
            date=date,
            location=location,
        )

        # Store summary separately in report_summaries
        summary_text = result.get("summary", "")
        if summary_text:
            db.execute(text(
                "INSERT INTO report_summaries (report_id, summary_text, summary_type, version, is_current) "
                "VALUES (:rid, :st, 'AI_GENERATED', 1, TRUE)"
            ), {"rid": rid, "st": summary_text})

        db.execute(text("UPDATE reports SET processing_state='COMPLETED' WHERE id=:rid"), {"rid": rid})
        db.commit()
        db.close()
    except Exception as e:
        try:
            db = Session(bind=engine)
            db.execute(text("UPDATE reports SET processing_state='ANALYSIS_FAILED' WHERE id=:rid"), {"rid": rid})
            db.commit()
            db.close()
        except Exception:
            pass
        print(f"[process] inline analysis failed for {incident_id}: {e}")


@router.post("/reports/analyze", summary="Analyze a new UA/UC report with NLP pipeline", response_model=AnalyzeResponse)
def analyze_report(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
):
    try:
        result = nlp_service.analyze_and_ingest(
            raw_text=request.raw_text,
            incident_id=request.incident_id,
            date=request.date,
            location=request.location,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.post("/reports/analyze/upload", summary="Analyze a report from uploaded file")
async def analyze_report_upload(
    file: UploadFile = File(...),
    incident_id: str | None = Form(None),
    date: str | None = Form(None),
    location: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith('.txt'):
        raise HTTPException(400, "Only .txt files are supported")
    content = await file.read()
    raw_text = content.decode('utf-8')
    try:
        result = nlp_service.analyze_and_ingest(
            raw_text=raw_text,
            incident_id=incident_id,
            date=date,
            location=location,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.get("/reports/{incident_id}/summary", summary="Get current AI summary")
def get_summary(incident_id: str, db: Session = Depends(get_db)):
    report = db.execute(text("SELECT id FROM reports WHERE incident_id=:i"), {"i": incident_id}).fetchone()
    if not report:
        raise HTTPException(404, "not found")
    rid = report[0]
    summary = db.execute(text(
        "SELECT rs.summary_text, rs.summary_type, rs.version, rs.edited_at, rs.created_at, "
        "u.username AS edited_by_name "
        "FROM report_summaries rs LEFT JOIN users u ON u.id = rs.edited_by "
        "WHERE rs.report_id=:rid AND rs.is_current=TRUE"
    ), {"rid": rid}).mappings().first()
    if not summary:
        # Fallback to report.summary
        old = db.execute(text("SELECT summary FROM reports WHERE id=:rid"), {"rid": rid}).scalar()
        return {"summary_text": old, "summary_type": "LEGACY", "version": 1}
    return dict(summary)


@router.put("/reports/{incident_id}/summary", summary="Admin: edit AI summary (creates new version)")
def edit_summary(
    incident_id: str,
    body: SummaryEditRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user["role"] != "ADMIN":
        raise HTTPException(403, "Only admins can edit summaries")
    report = db.execute(text("SELECT id FROM reports WHERE incident_id=:i"), {"i": incident_id}).fetchone()
    if not report:
        raise HTTPException(404, "not found")
    rid = report[0]

    # Get current version
    current = db.execute(text(
        "SELECT version FROM report_summaries WHERE report_id=:rid AND is_current=TRUE"
    ), {"rid": rid}).scalar() or 0

    # Mark old as not current
    db.execute(text(
        "UPDATE report_summaries SET is_current=FALSE WHERE report_id=:rid AND is_current=TRUE"
    ), {"rid": rid})

    # Insert new version
    new_version = current + 1
    db.execute(text(
        "INSERT INTO report_summaries (report_id, summary_text, summary_type, version, edited_by, edited_at, is_current) "
        "VALUES (:rid, :st, 'ADMIN_EDITED', :v, :uid, now(), TRUE)"
    ), {"rid": rid, "st": body.summary, "v": new_version, "uid": user["id"]})

    # Audit
    db.execute(text(
        "INSERT INTO audit_log (user_id, username, action, entity_type, entity_id, new_value) "
        "VALUES (:uid, :un, 'summary_edit', 'report', :eid, :nv)"
    ), {"uid": user["id"], "un": user["username"], "eid": incident_id,
         "nv": f'{{"version": {new_version}, "length": {len(body.summary)}}}'})
    db.commit()

    return {"incident_id": incident_id, "version": new_version, "summary_type": "ADMIN_EDITED"}
