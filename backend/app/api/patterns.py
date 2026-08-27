"""Patterns API - pattern listing, scoring, ranking, detail, and why."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import patterns as svc

router = APIRouter(prefix="/api", tags=["patterns"])


def _calc_pattern_score(report_count: int, sif_count: int, total_reports: int, lift: float | None) -> float:
    """Deterministic pattern score: incorporates frequency, SIF concentration, and lift.
    
    Formula:
      freq_score = min(report_count / 20, 1.0) * 0.3
      sif_score = (sif_count / max(report_count, 1)) * 0.35
      lift_score = min((lift or 1.0) / 3.0, 1.0) * 0.25
      recency_score = 0.1 (base for existing patterns)
    """
    freq = min(report_count / 20.0, 1.0) * 0.30
    sif_conc = (sif_count / max(report_count, 1)) * 0.35
    lift_s = min((lift or 1.0) / 3.0, 1.0) * 0.25
    recency = 0.10
    return min(freq + sif_conc + lift_s + recency, 1.0)


def _priority_from_score(score: float) -> str:
    if score >= 0.65:
        return "CRITICAL"
    if score >= 0.45:
        return "HIGH"
    if score >= 0.25:
        return "MODERATE"
    return "LOW"


def _trend_for_pattern(db: Session, pattern_id: int) -> str:
    """Determine if a pattern is emerging or escalating."""
    now = datetime.now(timezone.utc).date()
    recent_30 = now - timedelta(days=30)
    earlier_30 = recent_30 - timedelta(days=30)

    recent = db.execute(text("""
        SELECT COUNT(*) FROM pattern_reports pr
        JOIN reports r ON r.id = pr.report_id
        WHERE pr.pattern_id = :pid AND r.event_date >= :d
    """), {"pid": pattern_id, "d": recent_30.isoformat()}).scalar() or 0

    earlier = db.execute(text("""
        SELECT COUNT(*) FROM pattern_reports pr
        JOIN reports r ON r.id = pr.report_id
        WHERE pr.pattern_id = :pid AND r.event_date BETWEEN :s AND :e
    """), {"pid": pattern_id, "s": earlier_30.isoformat(), "e": recent_30.isoformat()}).scalar() or 0

    if earlier == 0 and recent > 0:
        return "NEWLY_EMERGING"
    if earlier == 0:
        return "STABLE"
    change = (recent - earlier) / earlier
    if change > 0.2:
        return "INCREASING"
    if change < -0.2:
        return "DECREASING"
    return "STABLE"


@router.get("/patterns", summary="List patterns (optionally build them)")
def list_patterns(
    build: bool = Query(False),
    build_lsr: bool = Query(False),
    min_reports: int = Query(2),
    location: str | None = Query(None),
    precursor: str | None = Query(None),
    priority: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if build:
        db.execute(text("DELETE FROM pattern_reports"))
        db.execute(text("DELETE FROM patterns"))
        groups = svc.build_sql_patterns(db, min_reports=min_reports)
        svc.persist_patterns(db, groups, pattern_type='precursor')
        if build_lsr:
            lsr_groups = svc.build_lsr_patterns(db, min_reports=min_reports)
            svc.persist_patterns(db, lsr_groups, pattern_type='lsr')
        # Calculate scores for all patterns
        _recalculate_all_scores(db)

    conditions = []
    params = {}
    if location:
        conditions.append("p.location ILIKE :loc")
        params["loc"] = f"%{location}%"
    if precursor:
        conditions.append("p.title ILIKE :prec")
        params["prec"] = f"%{precursor}%"
    if priority:
        conditions.append("p.priority_level = :pri")
        params["pri"] = priority.upper()

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = db.execute(
        text(
            f"SELECT p.id, p.title, p.description, p.pattern_type, p.location, p.activity, "
            f"p.report_count, p.severity, p.pattern_score, p.priority_level, p.sif_count, "
            f"p.sif_rate, p.trend, p.lift, p.first_detected, p.last_detected "
            f"FROM patterns p {where} ORDER BY p.pattern_score DESC NULLS LAST, p.report_count DESC"
        ),
        params,
    ).fetchall()
    return {"patterns": [dict(r._mapping) for r in rows]}


def _recalculate_all_scores(db: Session):
    """Recalculate pattern scores, priorities, trends, and SIF counts."""
    total_reports = db.execute(text("SELECT COUNT(*) FROM reports")).scalar() or 1
    patterns = db.execute(text("SELECT id FROM patterns")).scalars().all()

    for pid in patterns:
        member_ids = db.execute(
            text("SELECT report_id FROM pattern_reports WHERE pattern_id=:p"), {"p": pid}
        ).scalars().all()
        if not member_ids:
            continue

        n = len(member_ids)
        sif_count = db.execute(text(
            "SELECT COUNT(*) FROM reports WHERE id IN :ids AND sif_class IN ('HSIF','PSIF','HIGH','MEDIUM')"
        ), {"ids": tuple(member_ids)}).scalar() or 0

        # Get lift from why analysis
        why = svc.pattern_why(db, pid, member_ids)
        max_lift = 0
        for d in why.get("drivers", []):
            if d.get("lift") and d["lift"] > max_lift:
                max_lift = d["lift"]

        score = _calc_pattern_score(n, sif_count, total_reports, max_lift)
        priority = _priority_from_score(score)
        trend = _trend_for_pattern(db, pid)
        sif_rate = sif_count / n if n > 0 else 0

        db.execute(text(
            "UPDATE patterns SET pattern_score=:sc, priority_level=:pr, sif_count=:si, "
            "sif_rate=:sr, trend=:tr, lift=:lf, last_recalculated=now() WHERE id=:pid"
        ), {"sc": score, "pr": priority, "si": sif_count, "sr": sif_rate, "tr": trend,
            "lf": max_lift, "pid": pid})

    db.commit()


def _member_ids(db, pattern_id: int) -> list[int]:
    return db.execute(
        text("SELECT report_id FROM pattern_reports WHERE pattern_id=:p"),
        {"p": pattern_id},
    ).scalars().all()


@router.get("/patterns/{pattern_id}", summary="Pattern detail with score and evidence")
def get_pattern(pattern_id: int, db: Session = Depends(get_db)):
    pat = db.execute(text(
        "SELECT p.*, pr.name AS precursor_name, lsr.name AS lsr_name "
        "FROM patterns p "
        "LEFT JOIN precursors pr ON pr.id = p.precursor_id "
        "LEFT JOIN life_saving_rules lsr ON lsr.id = p.lsr_id "
        "WHERE p.id=:pid"
    ), {"pid": pattern_id}).mappings().first()
    if not pat:
        raise HTTPException(404, "pattern not found")

    # Member reports
    reports = db.execute(text(
        "SELECT pr.report_id, r.incident_id, r.location, to_char(r.event_date,'YYYY-MM-DD') AS event_date, "
        "r.injury_severity, r.sif_score, r.sif_class, pr.similarity "
        "FROM pattern_reports pr JOIN reports r ON r.id=pr.report_id WHERE pr.pattern_id=:p "
        "ORDER BY r.sif_score DESC NULLS LAST"
    ), {"p": pattern_id}).fetchall()

    # Why
    members = _member_ids(db, pattern_id)
    why = svc.pattern_why(db, pattern_id, members)

    return {
        "pattern": dict(pat),
        "reports": [dict(x._mapping) for x in reports],
        "why": why,
    }


@router.get("/patterns/{pattern_id}/reports", summary="Pattern member reports (v2)")
def pattern_reports(pattern_id: int, db: Session = Depends(get_db)):
    pid = db.execute(text("SELECT id FROM patterns WHERE id=:p"), {"p": pattern_id}).one_or_none()
    if not pid:
        raise HTTPException(404, "pattern not found")
    rows = db.execute(
        text(
            "SELECT pr.report_id, r.incident_id, r.location, to_char(r.event_date,'YYYY-MM-DD') AS event_date, "
            "r.injury_severity, r.sif_score, pr.similarity FROM pattern_reports pr "
            "JOIN reports r ON r.id=pr.report_id WHERE pr.pattern_id=:p ORDER BY pr.similarity DESC NULLS LAST"
        ),
        {"p": pattern_id},
    ).fetchall()
    return {"pattern_id": pattern_id, "reports": [dict(x._mapping) for x in rows]}


@router.get("/patterns/{pattern_id}/why", summary="Why this pattern is seen (dominance + lift)")
def pattern_why(pattern_id: int, db: Session = Depends(get_db)):
    pid = db.execute(text("SELECT id FROM patterns WHERE id=:p"), {"p": pattern_id}).one_or_none()
    if not pid:
        raise HTTPException(404, "pattern not found")
    members = _member_ids(db, pattern_id)
    return svc.pattern_why(db, pattern_id, members)
