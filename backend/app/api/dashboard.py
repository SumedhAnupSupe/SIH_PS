"""Dashboard overview API - KPIs and aggregated intelligence summary."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", summary="Dashboard KPI summary")
def dashboard_overview(db: Session = Depends(get_db)):
    total = db.execute(text("SELECT COUNT(*) FROM reports")).scalar() or 0

    # SIF score distribution buckets
    high_sif = db.execute(text(
        "SELECT COUNT(*) FROM reports WHERE sif_score >= 0.65"
    )).scalar() or 0
    med_sif = db.execute(text(
        "SELECT COUNT(*) FROM reports WHERE sif_score >= 0.35 AND sif_score < 0.65"
    )).scalar() or 0
    low_sif = db.execute(text(
        "SELECT COUNT(*) FROM reports WHERE sif_score < 0.35 OR sif_score IS NULL"
    )).scalar() or 0

    # Also count by classification
    sif_count = db.execute(text(
        "SELECT COUNT(*) FROM reports WHERE sif_class IN ('HSIF','PSIF','MEDIUM','HIGH')"
    )).scalar() or 0

    loc_count = db.execute(text("SELECT COUNT(*) FROM locations")).scalar() or 0
    pattern_count = db.execute(text("SELECT COUNT(*) FROM patterns")).scalar() or 0

    avg_score = db.execute(text(
        "SELECT COALESCE(AVG(sif_score), 0) FROM reports WHERE sif_score IS NOT NULL"
    )).scalar() or 0

    high_attention = db.execute(text(
        "SELECT COUNT(*) FROM sif_assessments WHERE attention_level IN ('IMMEDIATE','SHORT_TERM')"
    )).scalar() or 0

    att_dist = db.execute(text("""
        SELECT attention_level, COUNT(*) FROM sif_assessments GROUP BY attention_level
    """)).fetchall()

    top_locs = db.execute(text("""
        SELECT l.name, COALESCE(AVG(r.sif_score),0) AS avg_score, COUNT(r.id) AS cnt,
               COUNT(*) FILTER (WHERE r.sif_class IN ('HSIF','PSIF','MEDIUM','HIGH')) AS sif_cnt
        FROM locations l JOIN reports r ON r.location_id = l.id
        GROUP BY l.name ORDER BY avg_score DESC LIMIT 10
    """)).fetchall()

    prec_dist = db.execute(text("""
        SELECT p.name, COUNT(*) AS cnt
        FROM report_precursors rp JOIN precursors p ON p.id = rp.precursor_id
        WHERE rp.status = 'PRESENT'
        GROUP BY p.name ORDER BY cnt DESC LIMIT 10
    """)).fetchall()

    class_dist = db.execute(text("""
        SELECT sif_class, COUNT(*) FROM reports WHERE sif_class IS NOT NULL GROUP BY sif_class
    """)).fetchall()

    # LSR broken counts
    lsr_broken = db.execute(text("""
        SELECT lsr.rule_id, lsr.name, COUNT(*) AS broken_count
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        WHERE rlsr.status = 'BROKEN'
        GROUP BY lsr.rule_id, lsr.name ORDER BY broken_count DESC
    """)).fetchall()

    # Barrier failure indicators (precursors that indicate barrier issues)
    barrier_indicators = db.execute(text("""
        SELECT p.code, p.name, COUNT(*) AS present_count
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        WHERE rp.status = 'PRESENT'
          AND p.code IN ('stop_work_execution', 'rules_and_procedures',
                         'perceived_safety_culture', 'safety_attitudes',
                         'workers_inactive_in_safety', 'pre_task_plan')
        GROUP BY p.code, p.name ORDER BY present_count DESC
    """)).fetchall()

    # Average SIF score per location
    sif_dist = db.execute(text("""
        SELECT
            COALESCE(AVG(sif_score), 0) AS avg_score,
            COALESCE(MAX(sif_score), 0) AS max_score,
            COUNT(*) FILTER (WHERE sif_score >= 0.65) AS high_count,
            COUNT(*) FILTER (WHERE sif_score >= 0.35 AND sif_score < 0.65) AS med_count,
            COUNT(*) FILTER (WHERE sif_score < 0.35 OR sif_score IS NULL) AS low_count
        FROM reports
    """)).fetchone()

    return {
        "total_reports": total,
        "sif_reports": sif_count,
        "high_sif_count": high_sif,
        "med_sif_count": med_sif,
        "low_sif_count": low_sif,
        "locations": loc_count,
        "patterns": pattern_count,
        "avg_sif_score": round(float(avg_score), 4),
        "high_attention_incidents": high_attention,
        "sif_distribution": dict(sif_dist._mapping) if sif_dist else {},
        "attention_distribution": {r[0]: r[1] for r in att_dist},
        "classification_distribution": {r[0]: r[1] for r in class_dist},
        "top_locations": [
            {"name": r[0], "avg_score": round(float(r[1]), 4), "count": r[2], "sif_count": r[3]}
            for r in top_locs
        ],
        "top_precursors": [{"name": r[0], "count": r[1]} for r in prec_dist],
        "lsr_broken": [{"rule_id": r[0], "name": r[1], "count": r[2]} for r in lsr_broken],
        "barrier_indicators": [{"code": r[0], "name": r[1], "count": r[2]} for r in barrier_indicators],
    }
