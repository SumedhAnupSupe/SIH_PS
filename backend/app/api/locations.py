"""Location intelligence APIs - risk, aggregation, precursor mapping."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import risk_engine

router = APIRouter(prefix="/api/sif", tags=["locations"])


@router.get("/locations", summary="All locations with aggregated SIF risk scores")
def list_locations(db: Session = Depends(get_db)):
    """Returns all locations with deterministic risk scores."""
    results = risk_engine.calculate_all_location_risks(db)
    return {"locations": results}


@router.get("/locations/{location_id}", summary="Location detail with full stats")
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.execute(text(
        "SELECT id, name, latitude, longitude, region, asset_type, risk_score, risk_level, "
        "sif_rate, trend FROM locations WHERE id=:lid"
    ), {"lid": location_id}).fetchone()
    if not loc:
        raise HTTPException(404, "Location not found")
    d = dict(loc._mapping)

    # Report stats
    stats = db.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_count,
               COALESCE(AVG(sif_score), 0) AS avg_score
        FROM reports WHERE location_id=:lid
    """), {"lid": location_id}).fetchone()
    d["total_reports"] = stats[0]
    d["sif_reports"] = stats[1]
    d["avg_sif_score"] = float(stats[2] or 0)

    # Top precursors
    prec = db.execute(text("""
        SELECT p.code, p.name, rp.status, COUNT(*) AS cnt
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        JOIN reports r ON r.id = rp.report_id
        WHERE r.location_id = :lid AND rp.status IN ('PRESENT','AMBIGUOUS')
        GROUP BY p.code, p.name, rp.status ORDER BY cnt DESC
    """), {"lid": location_id}).fetchall()
    d["precursors"] = [{"code": p[0], "name": p[1], "status": p[2], "count": p[3]} for p in prec]

    # Top patterns
    top_patterns = db.execute(text("""
        SELECT p.id, p.title, p.pattern_score, p.priority_level, p.report_count, p.trend
        FROM patterns p WHERE p.location = (SELECT name FROM locations WHERE id=:lid)
        ORDER BY p.pattern_score DESC LIMIT 5
    """), {"lid": location_id}).fetchall()
    d["top_patterns"] = [dict(x._mapping) for x in top_patterns]

    # Attention
    att = db.execute(text("""
        SELECT sa.attention_level, sa.risk_potential, sa.systemic_attention,
               sa.barrier_failure_rate, sa.prediction_mode
        FROM sif_assessments sa JOIN reports r ON r.id = sa.report_id
        WHERE r.location_id = :lid ORDER BY sa.risk_potential DESC LIMIT 1
    """), {"lid": location_id}).fetchone()
    d["attention"] = dict(att._mapping) if att else None

    # Risk snapshots
    snapshots = db.execute(text(
        "SELECT period_start, period_end, risk_score, risk_level, sif_rate, trend "
        "FROM location_risk_snapshots WHERE location_id=:lid "
        "ORDER BY period_end DESC LIMIT 12"
    ), {"lid": location_id}).fetchall()
    d["risk_history"] = [dict(x._mapping) for x in snapshots]

    return d


@router.get("/locations/{location_id}/precursors", summary="Precursor breakdown for a location")
def location_precursors(location_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT p.code, p.name,
               COUNT(*) FILTER (WHERE rp.status='PRESENT') AS present_count,
               COUNT(*) FILTER (WHERE rp.status='AMBIGUOUS') AS ambiguous_count,
               COUNT(*) FILTER (WHERE rp.status='NOT_MENTIONED') AS not_mentioned_count,
               COUNT(*) AS total,
               COALESCE(AVG(rp.confidence) FILTER (WHERE rp.status IN ('PRESENT','AMBIGUOUS')), 0) AS avg_confidence
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        JOIN reports r ON r.id = rp.report_id
        WHERE r.location_id = :lid
        GROUP BY p.code, p.name
        HAVING COUNT(*) FILTER (WHERE rp.status IN ('PRESENT','AMBIGUOUS')) > 0
        ORDER BY present_count DESC
    """), {"lid": location_id}).fetchall()
    return {
        "location_id": location_id,
        "precursors": [dict(r._mapping) for r in rows],
    }


@router.get("/precursors/{precursor_id}/locations", summary="Which locations have this precursor")
def precursor_locations(precursor_id: int, db: Session = Depends(get_db)):
    prec = db.execute(text("SELECT id, code, name FROM precursors WHERE id=:pid"), {"pid": precursor_id}).fetchone()
    if not prec:
        raise HTTPException(404, "Precursor not found")

    rows = db.execute(text("""
        SELECT l.id, l.name, l.latitude, l.longitude,
               COUNT(*) FILTER (WHERE rp.status='PRESENT') AS present_count,
               COUNT(*) FILTER (WHERE rp.status='AMBIGUOUS') AS ambiguous_count,
               COUNT(*) AS total,
               COALESCE(AVG(rp.confidence), 0) AS avg_confidence
        FROM report_precursors rp
        JOIN reports r ON r.id = rp.report_id
        JOIN locations l ON l.id = r.location_id
        WHERE rp.precursor_id = :pid AND l.id IS NOT NULL
        GROUP BY l.id, l.name, l.latitude, l.longitude
        ORDER BY present_count DESC
    """), {"pid": precursor_id}).fetchall()
    return {
        "precursor": dict(prec._mapping),
        "locations": [dict(r._mapping) for r in rows],
    }


@router.get("/precursors/list", summary="All precursors with counts")
def list_precursors(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT p.id, p.code, p.name,
               COUNT(*) FILTER (WHERE rp.status IN ('PRESENT','AMBIGUOUS')) AS active_count,
               COUNT(*) AS total_count
        FROM precursors p
        LEFT JOIN report_precursors rp ON rp.precursor_id = p.id
        GROUP BY p.id, p.code, p.name
        ORDER BY active_count DESC
    """)).fetchall()
    return {"precursors": [dict(r._mapping) for r in rows]}
