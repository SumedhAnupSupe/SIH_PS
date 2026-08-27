"""Temporal analytics and search APIs for SIF-AEGIS."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import temporal

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/temporal", summary="Period-over-period temporal analytics")
def temporal_analytics(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    period: str | None = Query(None, description="7d, 30d, 90d, 6m, 1y"),
    location_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return temporal.get_temporal_analytics(db, start_date, end_date, period, location_id)


@router.get("/sif-trend", summary="SIF trend time-series")
def sif_trend(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    period: str | None = Query(None),
    location_id: int | None = Query(None),
    bucket: str = Query("month", description="day, week, month"),
    db: Session = Depends(get_db),
):
    return temporal.get_sif_trend(db, start_date, end_date, period, location_id, bucket)


@router.get("/location/{location_id}/trend", summary="Location-specific time-series")
def location_trend(
    location_id: int,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    period: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return temporal.get_location_time_series(db, location_id, start_date, end_date, period)


@router.get("/search", summary="Global search across reports, patterns, locations")
def global_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(20),
    db: Session = Depends(get_db),
):
    ql = f"%{q}%"
    reports = db.execute(text(
        "SELECT incident_id, location, to_char(event_date,'YYYY-MM-DD') AS event_date, "
        "sif_class, sif_score, summary FROM reports "
        "WHERE incident_id ILIKE :q OR location ILIKE :q OR summary ILIKE :q "
        "OR raw_text ILIKE :q ORDER BY event_date DESC NULLS LAST LIMIT :lim"
    ), {"q": ql, "lim": limit}).fetchall()

    patterns = db.execute(text(
        "SELECT id, title, description, pattern_type, location, report_count, pattern_score, priority_level "
        "FROM patterns WHERE title ILIKE :q OR description ILIKE :q OR location ILIKE :q "
        "ORDER BY pattern_score DESC NULLS LAST LIMIT :lim"
    ), {"q": ql, "lim": limit}).fetchall()

    locations = db.execute(text(
        "SELECT id, name, region, risk_level, risk_score FROM locations "
        "WHERE name ILIKE :q OR region ILIKE :q LIMIT :lim"
    ), {"q": ql, "lim": limit}).fetchall()

    return {
        "query": q,
        "reports": [dict(r._mapping) for r in reports],
        "patterns": [dict(r._mapping) for r in patterns],
        "locations": [dict(r._mapping) for r in locations],
    }
