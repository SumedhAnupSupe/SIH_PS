"""Deterministic location risk engine for SIF-AEGIS.

Risk is NOT simply report count. It incorporates:
- SIF potential (count + rate)
- SIF score
- Precursor density (active precursors per report)
- High-priority patterns
- Barrier/control failures
- Trend direction
- Recent activity weight

The formula is transparent and documented.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "CRITICAL"
    if score >= 0.55:
        return "HIGH"
    if score >= 0.30:
        return "MODERATE"
    return "LOW"


def _trend_direction(db: Session, location_id: int, recent_days: int = 90, earlier_days: int = 90) -> str:
    """Compare recent period with earlier period to determine trend."""
    now = datetime.now(timezone.utc).date()
    recent_start = now - timedelta(days=recent_days)
    earlier_start = recent_start - timedelta(days=earlier_days)
    earlier_end = recent_start - timedelta(days=1)

    recent = db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_cnt,
               COUNT(*) AS total
        FROM reports WHERE location_id=:lid AND event_date BETWEEN :rs AND :re
    """), {"lid": location_id, "rs": recent_start.isoformat(), "re": now.isoformat()}).fetchone()

    earlier = db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_cnt,
               COUNT(*) AS total
        FROM reports WHERE location_id=:lid AND event_date BETWEEN :es AND :ee
    """), {"lid": location_id, "es": earlier_start.isoformat(), "ee": earlier_end.isoformat()}).fetchone()

    if not recent or not earlier:
        return "STABLE"
    recent_rate = (recent[0] / recent[1]) if recent[1] > 0 else 0
    earlier_rate = (earlier[0] / earlier[1]) if earlier[1] > 0 else 0
    if earlier_rate == 0:
        return "INCREASING" if recent_rate > 0 else "STABLE"
    change = (recent_rate - earlier_rate) / earlier_rate
    if change > 0.15:
        return "INCREASING"
    elif change < -0.15:
        return "DECREASING"
    return "STABLE"


def calculate_location_risk(db: Session, location_id: int) -> dict:
    """Calculate comprehensive risk score for a single location."""
    loc = db.execute(text(
        "SELECT id, name, latitude, longitude, region, asset_type FROM locations WHERE id=:lid"
    ), {"lid": location_id}).mappings().first()
    if not loc:
        return {}

    # Report statistics
    stats = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_count,
            COALESCE(AVG(sif_score) FILTER (WHERE sif_score IS NOT NULL), 0) AS avg_sif_score,
            COALESCE(MAX(sif_score) FILTER (WHERE sif_score IS NOT NULL), 0) AS max_sif_score
        FROM reports WHERE location_id=:lid
    """), {"lid": location_id}).fetchone()

    total = stats[0] or 0
    sif_count = stats[1] or 0
    avg_sif_score = float(stats[2] or 0)
    sif_rate = (sif_count / total) if total > 0 else 0

    # Precursor density (active precursors per report)
    prec_count = db.execute(text("""
        SELECT COUNT(*) FROM report_precursors rp
        JOIN reports r ON r.id = rp.report_id
        WHERE r.location_id = :lid AND rp.status IN ('PRESENT','AMBIGUOUS')
    """), {"lid": location_id}).scalar() or 0
    precursor_density = (prec_count / total) if total > 0 else 0

    # Barrier failure rate
    barrier_rate = db.execute(text("""
        SELECT COALESCE(AVG(sa.barrier_failure_rate), 0)
        FROM sif_assessments sa JOIN reports r ON r.id = sa.report_id
        WHERE r.location_id = :lid
    """), {"lid": location_id}).scalar() or 0

    # High-priority patterns at this location
    high_patterns = db.execute(text("""
        SELECT COUNT(*) FROM patterns
        WHERE location = (SELECT name FROM locations WHERE id=:lid)
          AND priority_level IN ('CRITICAL','HIGH')
    """), {"lid": location_id}).scalar() or 0

    # Trend
    trend = _trend_direction(db, location_id)

    # --- Risk Score Formula ---
    # Components weighted:
    #   SIF rate:        30%
    #   SIF score:       20%
    #   Precursor density: 15%
    #   Barrier failure:  15%
    #   High patterns:    10%
    #   Trend modifier:   10%
    risk_score = 0.0
    risk_score += min(sif_rate * 1.0, 1.0) * 0.30
    risk_score += min(avg_sif_score, 1.0) * 0.20
    risk_score += min(precursor_density / 5.0, 1.0) * 0.15
    risk_score += min(float(barrier_rate), 1.0) * 0.15
    risk_score += min(high_patterns / 5.0, 1.0) * 0.10
    # Trend modifier
    if trend == "INCREASING":
        risk_score *= 1.10
    elif trend == "DECREASING":
        risk_score *= 0.90
    risk_score = min(risk_score, 1.0)

    risk_level = _risk_level(risk_score)

    return {
        "location_id": loc["id"],
        "name": loc["name"],
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "region": loc["region"],
        "asset_type": loc["asset_type"],
        "risk_score": round(risk_score, 4),
        "risk_level": risk_level,
        "report_count": total,
        "sif_count": sif_count,
        "sif_rate": round(sif_rate, 4),
        "avg_sif_score": round(avg_sif_score, 4),
        "max_sif_score": round(float(max_sif_score := stats[3] or 0), 4),
        "precursor_density": round(precursor_density, 4),
        "barrier_failure_rate": round(float(barrier_rate), 4),
        "high_pattern_count": high_patterns,
        "trend": trend,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def calculate_all_location_risks(db: Session) -> list[dict]:
    """Calculate risk for all locations and return ranked list."""
    locations = db.execute(text("SELECT id FROM locations ORDER BY id")).scalars().all()
    results = []
    for lid in locations:
        r = calculate_location_risk(db, lid)
        if r:
            results.append(r)
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results


def store_risk_snapshot(db: Session, location_id: int, risk_data: dict,
                        period_start: str | None = None, period_end: str | None = None):
    """Store a risk snapshot for historical tracking."""
    now = datetime.now(timezone.utc).date()
    if not period_start:
        period_start = (now - timedelta(days=90)).isoformat()
    if not period_end:
        period_end = now.isoformat()
    db.execute(text("""
        INSERT INTO location_risk_snapshots
        (location_id, period_start, period_end, risk_score, risk_level,
         sif_count, report_count, sif_rate, trend)
        VALUES (:lid,:ps,:pe,:rs,:rl,:sc,:rc,:sr,:tr)
        ON CONFLICT (location_id, period_start, period_end) DO UPDATE SET
        risk_score=EXCLUDED.risk_score, risk_level=EXCLUDED.risk_level,
        sif_count=EXCLUDED.sif_count, report_count=EXCLUDED.report_count,
        sif_rate=EXCLUDED.sif_rate, trend=EXCLUDED.trend, calculated_at=now()
    """), {
        "lid": location_id, "ps": period_start, "pe": period_end,
        "rs": risk_data["risk_score"], "rl": risk_data["risk_level"],
        "sc": risk_data["sif_count"], "rc": risk_data["report_count"],
        "sr": risk_data["sif_rate"], "tr": risk_data["trend"],
    })
    db.execute(text("""
        UPDATE locations SET risk_score=:rs, risk_level=:rl, sif_rate=:sr,
        trend=:tr, last_risk_calculated=now() WHERE id=:lid
    """), {"rs": risk_data["risk_score"], "rl": risk_data["risk_level"],
            "sr": risk_data["sif_rate"], "tr": risk_data["trend"], "lid": location_id})


def recalculate_all_risks(db: Session):
    """Recalculate and store risk snapshots for all locations."""
    results = calculate_all_location_risks(db)
    for r in results:
        store_risk_snapshot(db, r["location_id"], r)
    return results
