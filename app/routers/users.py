"""
routers/users.py

Authentication and user-management endpoints.

Public (no token required)
  POST  /api/auth/login                  — obtain a JWT token

Authenticated (any role)
  GET   /api/auth/me                     — current user info
  POST  /api/auth/change-password        — change own password

Admin only
  GET   /api/admin/users                 — list all users
  POST  /api/admin/users                 — create a user
  PUT   /api/admin/users/{id}            — update role / active status
  POST  /api/admin/users/{id}/reset-password  — set new password for any user
  DELETE /api/admin/users/{id}           — delete a user (cannot delete self)
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth import (
    VALID_ROLES,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import User, get_db

# ── Two separate routers so auth and admin have distinct prefixes ──
auth_router  = APIRouter(prefix="/api/auth",  tags=["Auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Rate limiter — shares the same key_func as main.py's limiter
_limiter = Limiter(key_func=get_remote_address)


# ── Schemas ───────────────────────────────────────────────────
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str
    role:         str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password:     str

    @field_validator("new_password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v


class UserOut(BaseModel):
    id:         int
    username:   str
    role:       str
    is_active:  bool
    created_at: Optional[datetime]
    created_by: Optional[str]

    model_config = {"from_attributes": True}


class CreateUserIn(BaseModel):
    username: str
    password: str
    role:     str = "user"

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v

    @field_validator("password")
    @classmethod
    def _pw_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @field_validator("username")
    @classmethod
    def _uname(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters.")
        return v


class UpdateUserIn(BaseModel):
    role:      Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
        return v


class ResetPasswordIn(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


# ══════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════

@auth_router.post("/login", response_model=TokenOut)
@_limiter.limit("10/minute")
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)):
    """
    Authenticate with username + password.
    Returns a JWT access token valid for 8 hours.
    Rate-limited to 10 attempts per minute per IP.
    """
    user = (
        db.query(User)
        .filter(User.username == payload.username)
        .first()
    )

    # Verify existence, password, and active status in one place —
    # identical error message prevents username enumeration.
    if (
        not user
        or not verify_password(payload.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )

    token = create_access_token(user.username, user.role)
    return TokenOut(
        access_token=token,
        username=user.username,
        role=user.role,
    )


@auth_router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@auth_router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change own password.  Requires the correct current password.
    Returns 204 No Content on success.
    """
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()


# ══════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════

@admin_router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
):
    """List all user accounts.  Admin only."""
    return db.query(User).order_by(User.username).all()


@admin_router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: CreateUserIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new user account.  Admin only."""
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, f"Username '{payload.username}' is already taken.")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        created_by=current_user.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@admin_router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UpdateUserIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user's role or active status.  Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, f"User {user_id} not found.")

    # Prevent an admin from demoting or deactivating themselves
    if user.id == current_user.id:
        if payload.role is not None and payload.role != "admin":
            raise HTTPException(400, "You cannot change your own role.")
        if payload.is_active is False:
            raise HTTPException(400, "You cannot deactivate your own account.")

    if payload.role      is not None: user.role      = payload.role
    if payload.is_active is not None: user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return user


@admin_router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: int,
    payload: ResetPasswordIn,
    db: Session = Depends(get_db),
):
    """
    Set a new password for any user without knowing the current password.
    Admin only.  Returns 204 No Content.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, f"User {user_id} not found.")

    user.password_hash = hash_password(payload.new_password)
    db.commit()


@admin_router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a user account.  Admin only.
    An admin cannot delete their own account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, f"User {user_id} not found.")
    if user.id == current_user.id:
        raise HTTPException(400, "You cannot delete your own account.")

    db.delete(user)
    db.commit()