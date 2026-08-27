"""Barrier health dashboard and LSR analytics APIs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/api/sif", tags=["barriers"])


@router.get("/barriers/overview", summary="Barrier health overview across all reports")
def barrier_overview(db: Session = Depends(get_db)):
    """Aggregated barrier failure stats: precursors with PRESENT status that indicate barrier failures."""
    rows = db.execute(text("""
        SELECT p.code, p.name,
               COUNT(*) FILTER (WHERE rp.status = 'PRESENT') AS present_count,
               COUNT(*) FILTER (WHERE rp.status = 'AMBIGUOUS') AS ambiguous_count,
               COUNT(*) AS total,
               COALESCE(AVG(rp.confidence) FILTER (WHERE rp.status = 'PRESENT'), 0) AS avg_confidence
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        WHERE p.code IN (
            'stop_work_execution', 'rules_and_procedures',
            'perceived_safety_culture', 'safety_attitudes',
            'workers_inactive_in_safety', 'pre_task_plan'
        )
        GROUP BY p.code, p.name
        ORDER BY present_count DESC
    """)).fetchall()

    # LSR broken/uncertain stats
    lsr_rows = db.execute(text("""
        SELECT lsr.rule_id, lsr.name,
               COUNT(*) FILTER (WHERE rlsr.status = 'BROKEN') AS broken_count,
               COUNT(*) FILTER (WHERE rlsr.status = 'UNCERTAIN') AS uncertain_count,
               COUNT(*) AS total
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        GROUP BY lsr.rule_id, lsr.name
        ORDER BY broken_count DESC
    """)).fetchall()

    # SIF assessment barrier failure rates
    bfr_stats = db.execute(text("""
        SELECT
            COALESCE(AVG(barrier_failure_rate), 0) AS avg_bfr,
            COALESCE(MAX(barrier_failure_rate), 0) AS max_bfr,
            COUNT(*) FILTER (WHERE barrier_failure_rate >= 0.4) AS high_bfr_count,
            COUNT(*) AS total_assessed
        FROM sif_assessments
    """)).fetchone()

    return {
        "barrier_indicators": [dict(r._mapping) for r in rows],
        "life_saving_rules": [dict(r._mapping) for r in lsr_rows],
        "barrier_failure_rates": dict(bfr_stats._mapping) if bfr_stats else {},
    }


@router.get("/barriers/{barrier_code}/reports", summary="Reports affected by a specific barrier indicator")
def barrier_reports(barrier_code: str, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT r.id, r.incident_id, r.location, to_char(r.event_date, 'YYYY-MM-DD') AS event_date,
               r.sif_score, r.sif_class, rp.status, rp.confidence
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        JOIN reports r ON r.id = rp.report_id
        WHERE p.code = :code AND rp.status IN ('PRESENT', 'AMBIGUOUS')
        ORDER BY r.sif_score DESC NULLS LAST
    """), {"code": barrier_code}).fetchall()
    return {"barrier_code": barrier_code, "reports": [dict(r._mapping) for r in rows]}


@router.get("/lsr/overview", summary="Life-Saving Rules compliance overview")
def lsr_overview(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT lsr.rule_id, lsr.name,
               COUNT(*) FILTER (WHERE rlsr.status = 'BROKEN') AS broken,
               COUNT(*) FILTER (WHERE rlsr.status = 'NOT_BROKEN') AS not_broken,
               COUNT(*) FILTER (WHERE rlsr.status = 'UNCERTAIN') AS uncertain,
               COUNT(*) FILTER (WHERE rlsr.status = 'NOT_APPLICABLE') AS not_applicable,
               COUNT(*) AS total
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        GROUP BY lsr.rule_id, lsr.name
        ORDER BY lsr.rule_id
    """)).fetchall()

    # LSR by location
    by_location = db.execute(text("""
        SELECT r.location, lsr.rule_id, lsr.name, rlsr.status, COUNT(*) AS cnt
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        JOIN reports r ON r.id = rlsr.report_id
        WHERE rlsr.status IN ('BROKEN', 'UNCERTAIN')
        GROUP BY r.location, lsr.rule_id, lsr.name, rlsr.status
        ORDER BY r.location, cnt DESC
    """)).fetchall()

    return {
        "rules": [dict(r._mapping) for r in rows],
        "by_location": [dict(r._mapping) for r in by_location],
    }


@router.get("/lsr/{rule_id}/reports", summary="Reports related to a specific LSR")
def lsr_reports(rule_id: str, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT r.id, r.incident_id, r.location, to_char(r.event_date, 'YYYY-MM-DD') AS event_date,
               r.sif_score, rlsr.status, rlsr.confidence, rlsr.reason
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        JOIN reports r ON r.id = rlsr.report_id
        WHERE lsr.rule_id = :rule_id AND rlsr.status IN ('BROKEN', 'UNCERTAIN')
        ORDER BY r.sif_score DESC NULLS LAST
    """), {"rule_id": rule_id}).fetchall()
    return {"rule_id": rule_id, "reports": [dict(r._mapping) for r in rows]}


@router.get("/reports-by-location/{location_id}", summary="Reports for a specific location")
def reports_by_location(location_id: int, limit: int = Query(50), db: Session = Depends(get_db)):
    loc = db.execute(text("SELECT id, name FROM locations WHERE id=:lid"), {"lid": location_id}).fetchone()
    if not loc:
        return {"location": None, "reports": []}
    rows = db.execute(text("""
        SELECT r.incident_id, r.location, to_char(r.event_date, 'YYYY-MM-DD') AS event_date,
               r.injury_severity, r.sif_score, r.sif_class,
               (SELECT string_agg(p.name, ', ') FROM report_precursors rp
                JOIN precursors p ON p.id = rp.precursor_id
                WHERE rp.report_id = r.id AND rp.status = 'PRESENT') AS present_precursors
        FROM reports r
        WHERE r.location_id = :lid
        ORDER BY r.event_date DESC NULLS LAST
        LIMIT :lim
    """), {"lid": location_id, "lim": limit}).fetchall()
    return {"location_id": location_id, "location_name": loc[1], "reports": [dict(r._mapping) for r in rows]}
