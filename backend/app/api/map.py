"""Map/risk data API for Google Maps visualization."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import risk_engine

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/risk", summary="Map risk data for all locations")
def map_risk(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    risk_level: str | None = Query(None),
    precursor_id: int | None = Query(None),
    location_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Return aggregated risk data for map markers. Does NOT send all reports."""
    results = risk_engine.calculate_all_location_risks(db)

    # Apply filters
    if risk_level:
        results = [r for r in results if r["risk_level"] == risk_level.upper()]
    if location_id:
        results = [r for r in results if r["location_id"] == location_id]

    # If precursor filter, narrow down
    if precursor_id:
        loc_ids_with_precursor = db.execute(text("""
            SELECT DISTINCT r.location_id FROM report_precursors rp
            JOIN reports r ON r.id = rp.report_id
            WHERE rp.precursor_id = :pid AND rp.status IN ('PRESENT','AMBIGUOUS')
        """), {"pid": precursor_id}).scalars().all()
        results = [r for r in results if r["location_id"] in loc_ids_with_precursor]

    return {"locations": results}


@router.get("/locations", summary="Simplified location list for dropdowns")
def map_locations(db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, name, latitude, longitude, region, risk_level, risk_score "
        "FROM locations WHERE latitude IS NOT NULL AND longitude IS NOT NULL ORDER BY name"
    )).fetchall()
    return {"locations": [dict(r._mapping) for r in rows]}
