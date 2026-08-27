from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import recommendations as svc

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post("/patterns/{pattern_id}/recommendation",
             summary="Generate an evidence-grounded recommendation for a pattern")
def generate(pattern_id: int, db: Session = Depends(get_db)):
    exists = db.execute(
        text("SELECT id FROM patterns WHERE id=:p"), {"p": pattern_id}
    ).one_or_none()
    if not exists:
        raise HTTPException(404, "pattern not found")
    try:
        return svc.generate_for_pattern(db, pattern_id)
    except KeyError:
        raise HTTPException(404, "pattern not found")


@router.get("/recommendations", summary="List prioritized recommendations")
def list_recs(
    generate_missing: bool = Query(False, description="generate for all patterns lacking one"),
    db: Session = Depends(get_db),
):
    if generate_missing:
        missing = db.execute(text(
            "SELECT p.id FROM patterns p LEFT JOIN recommendations r ON r.pattern_id=p.id "
            "WHERE r.id IS NULL"
        )).scalars().all()
        for pid in missing:
            try:
                svc.generate_for_pattern(db, pid)
            except KeyError:
                continue
    return {"recommendations": svc.list_recommendations(db)}


@router.get("/recommendations/{rec_id}", summary="Recommendation with full evidence chain")
def get_rec(rec_id: int, db: Session = Depends(get_db)):
    rec = db.execute(
        text("SELECT * FROM recommendations WHERE id=:r"), {"r": rec_id}
    ).one_or_none()
    if not rec:
        raise HTTPException(404, "not found")
    evidence = db.execute(
        text(
            "SELECT e.evidence_type, e.report_id, r.incident_id, r.summary, "
            "e.kb_chunk_id, k.chunk_text, k.metadata AS kb_metadata "
            "FROM recommendation_evidence e "
            "LEFT JOIN reports r ON r.id=e.report_id "
            "LEFT JOIN knowledge_chunks k ON k.id=e.kb_chunk_id "
            "WHERE e.recommendation_id=:r"
        ),
        {"r": rec_id},
    ).fetchall()
    return {
        **dict(rec._mapping),
        "evidence": [
            {
                "type": e[0],
                "report": ({"id": e[1], "incident_id": e[2], "summary": (e[3] or "")[:200]}
                           if e[1] else None),
                "kb": ({"chunk_id": e[4], "text": (e[5] or "")[:300], "metadata": e[6]}
                       if e[4] else None),
            }
            for e in evidence
        ],
    }