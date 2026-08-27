"""Authentication API - login, register, user management."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_db
from app.services.auth import (
    UserCreate, UserLogin, create_user, authenticate_user,
    list_users, change_user_role, require_role, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", summary="Register a new user")
def register(body: UserCreate, db=Depends(get_db)):
    return create_user(db, body)


@router.post("/login", summary="Login and get JWT token")
def login(body: UserLogin, db=Depends(get_db)):
    return authenticate_user(db, body.username, body.password)


@router.get("/me", summary="Get current user info")
def me(user=Depends(get_current_user)):
    return user


@router.get("/users", summary="List all users (admin)")
def users(_: dict = Depends(require_role("ADMIN")), db=Depends(get_db)):
    return {"users": list_users(db)}


@router.put("/users/{user_id}/role", summary="Change user role (admin)")
def set_role(user_id: int, role: str, user=Depends(require_role("ADMIN")), db=Depends(get_db)):
    return change_user_role(db, user_id, role, user)
