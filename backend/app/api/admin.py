"""Admin API - report overrides, audit trail."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import admin as svc
from app.services.auth import get_current_user, require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(
    x_admin_key: str | None = Header(default=None),
    user: dict | None = None,
):
    """Support both JWT auth and legacy admin key for backward compatibility."""
    # Try JWT first (dependency injected separately)
    if user and user.get("role") in ("ADMIN", "MANAGER"):
        return True
    # Fallback to admin key
    if settings.admin_key and x_admin_key == settings.admin_key:
        return True
    # If admin_key is not set (dev mode), allow all
    if not settings.admin_key:
        return True
    raise HTTPException(403, "Admin access required")


class SummaryEdit(BaseModel):
    summary: str


class RawTextEdit(BaseModel):
    raw_text: str


class AnalysisEdit(BaseModel):
    analysis: dict
    summary: str | None = None


@router.get("/reports/{incident_id}/editable", summary="Get editable view")
def editable(incident_id: str, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return svc.get_editable(db, incident_id)
    except KeyError:
        raise HTTPException(404, "report not found")


@router.put("/reports/{incident_id}/summary", summary="Admin: override summary")
def edit_summary(
    incident_id: str, body: SummaryEdit, _: bool = Depends(require_admin), db: Session = Depends(get_db)
):
    try:
        out = svc.edit_summary(db, incident_id, body.summary)
        db.commit()
        return out
    except KeyError:
        raise HTTPException(404, "report not found")


@router.put("/reports/{incident_id}/raw-text", summary="Admin: override raw report text")
def edit_raw_text(
    incident_id: str, body: RawTextEdit, _: bool = Depends(require_admin), db: Session = Depends(get_db)
):
    try:
        out = svc.edit_raw_text(db, incident_id, body.raw_text)
        db.commit()
        return out
    except KeyError:
        raise HTTPException(404, "report not found")


@router.put("/reports/{incident_id}/analysis", summary="Admin: replace analysis JSON")
def edit_analysis(
    incident_id: str, body: AnalysisEdit, _: bool = Depends(require_admin), db: Session = Depends(get_db)
):
    try:
        return svc.edit_analysis(db, incident_id, body.analysis, summary=body.summary)
    except KeyError:
        raise HTTPException(404, "report not found")


@router.get("/audit", summary="Admin: audit trail (analysis + override)")
def audit(db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            "SELECT ar.id, ar.report_id, r.incident_id, ar.model_name, ar.model_version, "
            "ar.prompt_version, to_char(ar.ran_at,'YYYY-MM-DD HH24:MI:SS') AS ran_at "
            "FROM analysis_runs ar LEFT JOIN reports r ON r.id=ar.report_id "
            "ORDER BY ar.ran_at DESC LIMIT 100"
        )
    ).mappings().all()
    return {"audit": [dict(x) for x in rows]}


@router.get("/audit/log", summary="Full audit log")
def audit_log(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.execute(
        text(
            "SELECT al.id, al.username, al.action, al.entity_type, al.entity_id, "
            "al.old_value, al.new_value, to_char(al.created_at,'YYYY-MM-DD HH24:MI:SS') AS created_at "
            "FROM audit_log al ORDER BY al.created_at DESC LIMIT :lim"
        ),
        {"lim": limit},
    ).mappings().all()
    return {"audit_log": [dict(x) for x in rows]}
