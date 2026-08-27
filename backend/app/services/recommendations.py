"""Recommendation engine: turn a detected pattern into an intervention proposal,
always grounded in evidence (member reports + retrieved safety-KB guidance).

Deterministic by design — no LLM hop. The mapping below is a starting point
that OIL/HSE admins can refine.
"""
from sqlalchemy import text

from app.services.embeddings import embed

# precursor/hazard/lsr -> proposed intervention
INTERVENTIONS = {
    "departure_from_routine": (
        "Mandatory documented re-assessment whenever conditions change mid-task",
        "procedure",
    ),
    "plan_to_address_work_change": (
        "Require a written plan revision signed by supervision on any work-change trigger",
        "procedure",
    ),
    "productivity_pressure": (
        "Explicitly de-couple schedule pressure from safety-critical decisions",
        "culture",
    ),
    "stop_work_execution": (
        "Reinforce stop-work authority with drills and non-punitive enforcement",
        "training",
    ),
    "risk_normalization": (
        "Leadership walkdowns that challenge accepted ('we always do it this way') risk",
        "culture",
    ),
    "familiarity_with_task": (
        "Rotate and refresh pre-job briefings to counter complacency on routine tasks",
        "training",
    ),
    "hazard_recognition": (
        "Targeted hazard-recognition refresher for this specific activity",
        "training",
    ),
    "pre_task_plan": (
        "Enforce pre-task plan quality check (not just signature) before start",
        "procedure",
    ),
    "safe_work_procedure": (
        "Audit procedure adherence at the point of work, not after",
        "procedure",
    ),
    "perceived_safety_culture": (
        "Anonymous worker feedback channel on safety climate",
        "culture",
    ),
    "safety_attitudes": (
        "Coach supervisors on visible safety leadership behaviours",
        "culture",
    ),
    "workers_inactive_in_safety": (
        "Involve workers directly in control selection and verification",
        "culture",
    ),
    "rules_and_procedures": (
        "Simplify and re-brief the governing rule at the worksite",
        "procedure",
    ),
    # LSR-based interventions
    "LSR01": (
        "Strengthen work authorization process — ensure all permits are obtained and verified before work starts",
        "procedure",
    ),
    "LSR02": (
        "Reinforce energy isolation compliance — mandatory LOTO verification by independent person",
        "procedure",
    ),
    "LSR03": (
        "Line of fire management — install physical barriers and exclusion zones for lifting/pressurized work",
        "engineering",
    ),
    "LSR04": (
        "Confined space entry controls — require atmospheric testing, ventilation, and attendant for every entry",
        "procedure",
    ),
    "LSR05": (
        "Falling object prevention — mandatory tool tethering and toe boards for all work at height",
        "engineering",
    ),
    "LSR06": (
        "Safe lifting operations — require approved lift plan, certified rigging, and competent supervisor",
        "procedure",
    ),
    "LSR07": (
        "Equipment fitness — implement pre-use inspection checklist and remove defective equipment immediately",
        "procedure",
    ),
    "LSR08": (
        "Driving safety — enforce seat belt use, no phone policy, and pre-trip vehicle inspection",
        "training",
    ),
    "LSR09": (
        "Fall protection — require 100% tie-off, guardrails, or fall arrest systems for all work at height",
        "engineering",
    ),
}
DEFAULT_INTERVENTION = ("Review and strengthen the failing critical control", "procedure")


def _top_driver(why: dict) -> dict | None:
    """Highest-lift driver (precursor, hazard, or LSR), else highest-count."""
    drivers = why.get("drivers", [])
    if not drivers:
        return None
    return max(drivers, key=lambda d: (d.get("lift") or 0, d["count"]))


def _kb_support(conn, query: str, top_k: int = 2) -> list[dict]:
    try:
        from app.services.embeddings import embed
        has_emb = conn.execute(
            text("SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                 "WHERE table_name='knowledge_chunks' AND column_name='embedding')")
        ).scalar()
        if not has_emb:
            return []
        vec = embed([query])[0]
        v = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        rows = conn.execute(
            text(
                "SELECT k.id, k.metadata, 1-(k.embedding <=> :v) AS sim FROM knowledge_chunks k "
                "WHERE k.embedding IS NOT NULL ORDER BY k.embedding <=> :v LIMIT :k"
            ),
            {"v": v, "k": top_k},
        ).fetchall()
        return [{"kb_chunk_id": r[0], "metadata": r[1], "similarity": round(float(r[2] or 0), 3)}
                for r in rows]
    except Exception:
        return []


def generate_for_pattern(db, pattern_id: int) -> dict:
    pat = db.execute(
        text("SELECT id, title, location, activity FROM patterns WHERE id=:p"),
        {"p": pattern_id},
    ).one_or_none()
    if not pat:
        raise KeyError(pattern_id)

    members = db.execute(
        text("SELECT report_id FROM pattern_reports WHERE pattern_id=:p"),
        {"p": pattern_id},
    ).scalars().all()

    # reuse dominance+lift analysis
    from app.services.patterns import pattern_why

    why = pattern_why(db, pattern_id, members)

    driver = _top_driver(why)
    rec_text, itype = INTERVENTIONS.get(
        (driver or {}).get("name", ""), DEFAULT_INTERVENTION
    )

    # escalate priority when barrier failures dominate the pattern
    bfr = why.get("barrier_failure_rate", 0)
    priority = "HIGH" if bfr >= 0.4 else ("MEDIUM" if bfr > 0 or len(members) >= 3 else "LOW")

    conn = db.connection()
    kb = _kb_support(conn, f"{(driver or {}).get('name') or pat.title} critical control verification")

    # upsert one recommendation per pattern (regenerate replaces previous)
    db.execute(text("DELETE FROM recommendation_evidence WHERE recommendation_id IN "
                    "(SELECT id FROM recommendations WHERE pattern_id=:p)"), {"p": pattern_id})
    db.execute(text("DELETE FROM recommendations WHERE pattern_id=:p"), {"p": pattern_id})
    rid = db.execute(
        text(
            "INSERT INTO recommendations (pattern_id, recommendation, priority, intervention_type, confidence) "
            "VALUES (:p,:r,:pr,:it,:cf) RETURNING id"
        ),
        {"p": pattern_id, "r": rec_text, "pr": priority, "it": itype,
         "cf": round(min(1.0, ((driver or {}).get("lift") or 1.0) * len(members) / 10), 2)},
    ).scalar()

    # evidence: top-kb chunks + up to 5 member reports (highest sif first)
    for item in kb:
        db.execute(
            text("INSERT INTO recommendation_evidence (recommendation_id, evidence_type, report_id, kb_chunk_id) "
                 "VALUES (:r,'kb_document',NULL,:k)"),
            {"r": rid, "k": item["kb_chunk_id"]},
        )
    if members:
        placeholders = ",".join(f":m{i}" for i in range(len(members)))
        params = {f"m{i}": m for i, m in enumerate(members)}
        top_reports = db.execute(
            text(f"SELECT id FROM reports WHERE id IN ({placeholders}) "
                 f"ORDER BY sif_score DESC NULLS LAST LIMIT 5"),
            params,
        ).scalars().all()
        for m in top_reports:
            db.execute(
                text("INSERT INTO recommendation_evidence (recommendation_id, evidence_type, report_id, kb_chunk_id) "
                     "VALUES (:r,'report',:rep,NULL)"),
                {"r": rid, "rep": m},
            )
    db.commit()
    return {
        "recommendation_id": rid,
        "pattern_id": pattern_id,
        "pattern_title": pat.title,
        "driver": driver,
        "recommendation": rec_text,
        "priority": priority,
        "intervention_type": itype,
        "members": len(members),
        "barrier_failure_rate": bfr,
        "kb_support": kb,
    }


def list_recommendations(db) -> list[dict]:
    rows = db.execute(
        text(
            "SELECT rec.id, rec.pattern_id, p.title AS pattern_title, rec.recommendation, "
            "rec.priority, rec.intervention_type, rec.confidence, "
            "(SELECT count(*) FROM recommendation_evidence e WHERE e.recommendation_id=rec.id AND e.evidence_type='report') AS report_evidence, "
            "(SELECT count(*) FROM recommendation_evidence e WHERE e.recommendation_id=rec.id AND e.evidence_type='kb_document') AS kb_evidence "
            "FROM recommendations rec JOIN patterns p ON p.id=rec.pattern_id "
            "ORDER BY CASE rec.priority WHEN 'HIGH' THEN 0 WHEN 'MEDIUM' THEN 1 ELSE 2 END, rec.confidence DESC"
        )
    ).fetchall()
    return [dict(r._mapping) for r in rows]