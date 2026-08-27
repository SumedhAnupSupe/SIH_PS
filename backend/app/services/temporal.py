"""Temporal analytics engine for SIF-AEGIS.

Calculates period-over-period metrics deterministically.
All numerical values come from PostgreSQL, not from any LLM.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

PERIOD_PRESETS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "6m": 182,
    "1y": 365,
}


def _parse_dates(start_date: str | None, end_date: str | None, period: str | None) -> tuple[str, str]:
    """Resolve period to explicit date range."""
    if start_date and end_date:
        return start_date, end_date
    days = PERIOD_PRESETS.get(period or "90d", 90)
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    return start, end


def _previous_range(start: str, end: str) -> tuple[str, str]:
    """Compute the same-length period immediately before [start, end]."""
    from datetime import date as dt_date
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    length = (e - s).days
    prev_end = s - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length)
    return prev_start.isoformat(), prev_end.isoformat()


def _trend(current_val: float, previous_val: float, threshold: float = 0.05) -> str:
    if previous_val == 0:
        return "INCREASING" if current_val > 0 else "STABLE"
    change = (current_val - previous_val) / previous_val
    if change > threshold:
        return "INCREASING"
    elif change < -threshold:
        return "DECREASING"
    return "STABLE"


def get_temporal_analytics(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    location_id: int | None = None,
) -> dict:
    """Calculate comprehensive temporal analytics for a period, with period-over-period comparison."""
    start, end = _parse_dates(start_date, end_date, period)
    prev_start, prev_end = _previous_range(start, end)

    loc_filter = ""
    params = {"s": start, "e": end, "ps": prev_start, "pe": prev_end}
    if location_id:
        loc_filter = " AND r.location_id = :lid"
        params["lid"] = location_id

    # Current period
    cur = db.execute(text(f"""
        SELECT
            COUNT(*) AS total_reports,
            COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_count,
            COALESCE(AVG(sif_score) FILTER (WHERE sif_score IS NOT NULL), 0) AS avg_sif_score,
            COUNT(DISTINCT r.location_id) AS active_locations
        FROM reports r
        WHERE r.event_date BETWEEN :s AND :e {loc_filter}
    """), params).mappings().first()

    # Previous period
    prev = db.execute(text(f"""
        SELECT
            COUNT(*) AS total_reports,
            COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_count,
            COALESCE(AVG(sif_score) FILTER (WHERE sif_score IS NOT NULL), 0) AS avg_sif_score,
            COUNT(DISTINCT r.location_id) AS active_locations
        FROM reports r
        WHERE r.event_date BETWEEN :ps AND :pe {loc_filter}
    """), params).mappings().first()

    cur_total = cur["total_reports"] or 0
    cur_sif = cur["sif_count"] or 0
    cur_rate = (cur_sif / cur_total) if cur_total > 0 else 0
    prev_total = prev["total_reports"] or 0
    prev_sif = prev["sif_count"] or 0
    prev_rate = (prev_sif / prev_total) if prev_total > 0 else 0

    # Precursor counts for current period
    prec_params = dict(params)
    prec_rows = db.execute(text(f"""
        SELECT p.name, COUNT(*) AS cnt
        FROM report_precursors rp
        JOIN precursors p ON p.id = rp.precursor_id
        JOIN reports r ON r.id = rp.report_id
        WHERE rp.status IN ('PRESENT','AMBIGUOUS')
          AND r.event_date BETWEEN :s AND :e {loc_filter}
        GROUP BY p.name ORDER BY cnt DESC LIMIT 13
    """), prec_params).fetchall()

    # LSR broken for current period
    lsr_params = dict(params)
    lsr_rows = db.execute(text(f"""
        SELECT lsr.rule_id, lsr.name, COUNT(*) AS cnt
        FROM report_life_saving_rules rlsr
        JOIN life_saving_rules lsr ON lsr.id = rlsr.lsr_id
        JOIN reports r ON r.id = rlsr.report_id
        WHERE rlsr.status = 'BROKEN'
          AND r.event_date BETWEEN :s AND :e {loc_filter}
        GROUP BY lsr.rule_id, lsr.name ORDER BY cnt DESC LIMIT 9
    """), lsr_params).fetchall()

    # Pattern count
    pattern_count = db.execute(text("SELECT COUNT(*) FROM patterns")).scalar() or 0

    # Emerging patterns (first detected in current period)
    emerging = db.execute(text(
        "SELECT COUNT(*) FROM patterns WHERE first_detected BETWEEN :s AND :e"
    ), {"s": start, "e": end}).scalar() or 0

    return {
        "period": {"start": start, "end": end},
        "previous_period": {"start": prev_start, "end": prev_end},
        "current": {
            "total_reports": cur_total,
            "sif_count": cur_sif,
            "sif_rate": round(cur_rate, 4),
            "avg_sif_score": round(float(cur["avg_sif_score"] or 0), 4),
            "active_locations": cur["active_locations"] or 0,
        },
        "previous": {
            "total_reports": prev_total,
            "sif_count": prev_sif,
            "sif_rate": round(prev_rate, 4),
            "avg_sif_score": round(float(prev["avg_sif_score"] or 0), 4),
            "active_locations": prev["active_locations"] or 0,
        },
        "change": {
            "reports_change": cur_total - prev_total,
            "sif_count_change": cur_sif - prev_sif,
            "rate_change": round(cur_rate - prev_rate, 4),
            "rate_relative_change": round(((cur_rate - prev_rate) / prev_rate * 100), 1) if prev_rate > 0 else None,
            "reports_trend": _trend(cur_total, prev_total),
            "sif_trend": _trend(cur_sif, prev_sif),
            "rate_trend": _trend(cur_rate, prev_rate),
        },
        "top_precursors": [{"name": r[0], "count": r[1]} for r in prec_rows],
        "top_lsr_violations": [{"rule_id": r[0], "name": r[1], "count": r[2]} for r in lsr_rows],
        "pattern_count": pattern_count,
        "emerging_patterns": emerging,
    }


def get_sif_trend(
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
    location_id: int | None = None,
    bucket: str = "month",
) -> dict:
    """Get SIF trend as time-series buckets."""
    start, end = _parse_dates(start_date, end_date, period)
    loc_filter = ""
    params: dict = {"s": start, "e": end}
    if location_id:
        loc_filter = " AND r.location_id = :lid"
        params["lid"] = location_id

    if bucket == "week":
        trunc = "week"
    elif bucket == "day":
        trunc = "day"
    else:
        trunc = "month"

    rows = db.execute(text(f"""
        SELECT
            date_trunc('{trunc}', r.event_date) AS bucket,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')) AS sif_count,
            COALESCE(AVG(sif_score) FILTER (WHERE sif_score IS NOT NULL), 0) AS avg_score
        FROM reports r
        WHERE r.event_date BETWEEN :s AND :e {loc_filter}
        GROUP BY bucket ORDER BY bucket
    """), params).fetchall()

    return {
        "period": {"start": start, "end": end},
        "bucket": bucket,
        "data": [
            {
                "date": r[0].strftime("%Y-%m-%d") if r[0] else None,
                "total_reports": r[1],
                "sif_count": r[2],
                "sif_rate": round(r[2] / r[1], 4) if r[1] > 0 else 0,
                "avg_sif_score": round(float(r[3]), 4),
            }
            for r in rows
        ],
    }


def get_location_time_series(
    db: Session,
    location_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    period: str | None = None,
) -> dict:
    """Get time-series for a specific location."""
    return get_sif_trend(db, start_date, end_date, period, location_id=location_id)
