"""JWT authentication and role-based access control for SIF-AEGIS."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

ROLES = ["HSE_ENGINEER", "MANAGER", "ADMIN"]
ROLE_HIERARCHY = {"HSE_ENGINEER": 0, "MANAGER": 1, "ADMIN": 2}


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: str | None = None
    role: str = "HSE_ENGINEER"


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    is_active: bool


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    if not cred:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(cred.credentials)
    user_id = int(payload.get("sub", 0))
    row = db.execute(
        text("SELECT id, username, email, full_name, role, is_active FROM users WHERE id=:id"),
        {"id": user_id},
    ).mappings().first()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return dict(row)


def require_role(min_role: str):
    """Return a dependency that checks the user has at least `min_role`."""
    def dep(user: dict = Depends(get_current_user)):
        user_level = ROLE_HIERARCHY.get(user["role"], -1)
        required_level = ROLE_HIERARCHY.get(min_role, 99)
        if user_level < required_level:
            raise HTTPException(status_code=403, detail=f"Requires role {min_role} or higher")
        return user
    return dep


def optional_user(
    cred: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[dict]:
    """Like get_current_user but returns None if not authenticated."""
    if not cred:
        return None
    try:
        payload = decode_token(cred.credentials)
        user_id = int(payload.get("sub", 0))
        row = db.execute(
            text("SELECT id, username, email, full_name, role, is_active FROM users WHERE id=:id"),
            {"id": user_id},
        ).mappings().first()
        if row and row["is_active"]:
            return dict(row)
    except Exception:
        pass
    return None


def _audit(db: Session, user_id: int | None, username: str, action: str, entity_type: str,
           entity_id: str | None = None, old_value=None, new_value=None, ip: str | None = None):
    """Insert an audit log entry."""
    import json
    db.execute(
        text(
            "INSERT INTO audit_log (user_id, username, action, entity_type, entity_id, "
            "old_value, new_value, ip_address) VALUES (:uid,:un,:act,:et,:eid,:ov,:nv,:ip)"
        ),
        {
            "uid": user_id, "un": username, "act": action, "et": entity_type,
            "eid": str(entity_id) if entity_id else None,
            "ov": json.dumps(old_value) if old_value else None,
            "nv": json.dumps(new_value) if new_value else None,
            "ip": ip,
        },
    )


def create_user(db: Session, user_data: UserCreate) -> dict:
    """Create a new user. Returns user info."""
    if user_data.role not in ROLES:
        raise HTTPException(400, f"Invalid role: {user_data.role}")
    existing = db.execute(
        text("SELECT id FROM users WHERE username=:u OR email=:e"),
        {"u": user_data.username, "e": user_data.email},
    ).first()
    if existing:
        raise HTTPException(409, "Username or email already exists")
    pw_hash = hash_password(user_data.password)
    uid = db.execute(
        text(
            "INSERT INTO users (username, email, password_hash, full_name, role) "
            "VALUES (:u,:e,:p,:f,:r) RETURNING id"
        ),
        {"u": user_data.username, "e": user_data.email, "p": pw_hash,
         "f": user_data.full_name, "r": user_data.role},
    ).scalar()
    _audit(db, uid, user_data.username, "user_create", "user", str(uid),
           new_value={"role": user_data.role})
    db.commit()
    return {"id": uid, "username": user_data.username, "email": user_data.email,
            "full_name": user_data.full_name, "role": user_data.role}


def authenticate_user(db: Session, username: str, password: str) -> dict:
    """Authenticate and return token + user info."""
    row = db.execute(
        text("SELECT id, username, email, full_name, role, password_hash, is_active FROM users WHERE username=:u"),
        {"u": username},
    ).mappings().first()
    if not row or not row["is_active"] or not verify_password(password, row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(row["id"], row["username"], row["role"])
    _audit(db, row["id"], row["username"], "login", "user", str(row["id"]))
    db.commit()
    return {
        "access_token": token,
        "user": {k: row[k] for k in ("id", "username", "email", "full_name", "role")},
    }


def list_users(db: Session) -> list[dict]:
    rows = db.execute(
        text("SELECT id, username, email, full_name, role, is_active, created_at FROM users ORDER BY id")
    ).mappings().all()
    return [dict(r) for r in rows]


def change_user_role(db: Session, user_id: int, new_role: str, admin_user: dict) -> dict:
    if new_role not in ROLES:
        raise HTTPException(400, f"Invalid role: {new_role}")
    row = db.execute(text("SELECT id, username, role FROM users WHERE id=:id"), {"id": user_id}).mappings().first()
    if not row:
        raise HTTPException(404, "User not found")
    old_role = row["role"]
    db.execute(text("UPDATE users SET role=:r, updated_at=now() WHERE id=:id"), {"r": new_role, "id": user_id})
    _audit(db, admin_user["id"], admin_user["username"], "user_role_change", "user",
           str(user_id), old_value={"role": old_role}, new_value={"role": new_role})
    db.commit()
    return {"user_id": user_id, "old_role": old_role, "new_role": new_role}


def ensure_admin_user(db: Session):
    """Create a default admin user if none exists."""
    existing = db.execute(text("SELECT id FROM users WHERE role='ADMIN'")).first()
    if not existing:
        create_user(db, UserCreate(
            username="admin",
            email="admin@sif-aegis.local",
            password="admin",
            full_name="System Administrator",
            role="ADMIN",
        ))
