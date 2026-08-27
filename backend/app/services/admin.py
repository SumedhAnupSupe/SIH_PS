"""Admin overrides: allow a safety officer to correct a report's summary and
its structured analysis JSON. Corrections re-run ingestion for that report
(entities, evidence, features, embedding) so every downstream consumer stays
consistent. All overrides are audited in `analysis_runs` and stamped in
`reports.edited_at`.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.services.ingest_service import ingest_report


def _audit(db, report_id: int, action: str, detail: str):
    db.execute(
        text(
            "INSERT INTO analysis_runs (report_id, model_name, model_version, prompt_version, ran_at) "
            "VALUES (:r,:m,'admin',:p,now())"
        ),
        {"r": report_id, "m": f"admin:{action}", "p": detail[:500]},
    )


def _touch(db, report_id: int):
    db.execute(
        text("UPDATE reports SET edited_at=:t WHERE id=:r"),
        {"r": report_id, "t": datetime.now(timezone.utc)},
    )


def _get_report_meta(db, incident_id: str) -> dict | None:
    return db.execute(
        text(
            "SELECT id, raw_text, summary, location, event_date, injury_severity, sif_score, sif_class "
            "FROM reports WHERE incident_id=:i"
        ),
        {"i": incident_id},
    ).mappings().first()


def edit_summary(db, incident_id: str, summary: str) -> dict:
    row = _get_report_meta(db, incident_id)
    if not row:
        raise KeyError(incident_id)
    db.execute(
        text("UPDATE reports SET summary=:s, edited_at=:t WHERE id=:r"),
        {"s": summary, "t": datetime.now(timezone.utc), "r": row["id"]},
    )
    _audit(db, row["id"], "summary", f"summary.set len={len(summary)}")
    return {"incident_id": incident_id, "summary": summary, "edited": True}


def edit_raw_text(db, incident_id: str, raw_text: str) -> dict:
    row = _get_report_meta(db, incident_id)
    if not row:
        raise KeyError(incident_id)
    db.execute(
        text("UPDATE reports SET raw_text=:s, edited_at=:t WHERE id=:r"),
        {"s": raw_text, "t": datetime.now(timezone.utc), "r": row["id"]},
    )
    _audit(db, row["id"], "raw_text", f"raw_text.set len={len(raw_text)}")
    return {"incident_id": incident_id, "raw_text": raw_text, "edited": True}


def edit_analysis(db, incident_id: str, analysis: dict, summary: str | None = None) -> dict:
    """Replace the structured analysis JSON and re-derive all rows.

    The report's current summary is preserved unless explicitly overridden —
    so an earlier admin summary edit isn't silently clobbered by the
    pipeline's own diagnostic text inside the analysis JSON.
    """
    row = _get_report_meta(db, incident_id)
    if not row:
        raise KeyError(incident_id)

    # ensure identity is preserved so re-insert targets the same incident
    analysis.setdefault("metadata", {})["incident_id"] = incident_id
    new_summary = summary if summary is not None else (row["summary"] or "")
    raw_text = row["raw_text"] or ""

    conn = db.connection()
    rid = ingest_report(conn, analysis, {}, raw_text, new_summary)
    _audit(db, rid, "analysis", "analysis_json replaced by admin")
    _touch(db, rid)
    db.commit()
    return {
        "incident_id": incident_id,
        "report_id": rid,
        "result": "re-ingested",
        "summary_preserved": summary is None,
        "note": "precursor/evidence/hazards/embedding regenerated from edited JSON",
    }


def get_editable(db, incident_id: str) -> dict:
    row = db.execute(
        text(
            "SELECT id, incident_id, raw_text, summary, to_char(edited_at,'YYYY-MM-DD HH24:MI') AS edited_at, "
            "analysis_json FROM reports WHERE incident_id=:i"
        ),
        {"i": incident_id},
    ).mappings().first()
    if not row:
        raise KeyError(incident_id)
    return {
        "incident_id": incident_id,
        "raw_text": row["raw_text"],
        "summary": row["summary"],
        "edited_at": row["edited_at"],
        "analysis_json": row["analysis_json"] if isinstance(row["analysis_json"], dict)
                         else json.loads(row["analysis_json"] or "{}"),
    }