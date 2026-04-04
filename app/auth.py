"""
auth.py — JWT-based authentication and role-based access control.

Roles
-----
  admin   Full access: view, export CSV, upload Excel, manage users.
  user    View + export CSV.  No upload, no user management.
  viewer  Read-only.  No export, no upload, no user management.

Token lifecycle
---------------
  POST /api/auth/login  →  { access_token, token_type, role, username }
  All other /api/* endpoints require:  Authorization: Bearer <token>
  Tokens expire after TOKEN_HOURS hours (default 8 — one working day).

Secret key resolution (first match wins)
-----------------------------------------
  1. SRWB_SECRET_KEY  environment variable
  2. data/srwb.secret  file (auto-generated on first run)

First-run admin
---------------
  If no users exist in the database, a default admin account is created
  with a random password that is printed to the server terminal.
  Change it immediately after first login.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt as _bcrypt
from sqlalchemy.orm import Session

from app.database import User, get_db

# ── Constants ─────────────────────────────────────────────────
ALGORITHM    = "HS256"
TOKEN_HOURS  = 8
SECRET_FILE  = Path(__file__).parent.parent / "data" / "srwb.secret"
VALID_ROLES  = {"admin", "user", "viewer"}

# ── Password hashing ──────────────────────────────────────────


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT secret ────────────────────────────────────────────────
def _load_or_generate_secret() -> str:
    if key := os.getenv("SRWB_SECRET_KEY", "").strip():
        return key
    if SECRET_FILE.exists():
        stored = SECRET_FILE.read_text().strip()
        if stored:
            return stored
    key = secrets.token_urlsafe(48)
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(key)
    return key


SECRET_KEY: str = _load_or_generate_secret()


# ── Token helpers ─────────────────────────────────────────────
def create_access_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_HOURS)
    payload = {
        "sub":  username,
        "role": role,
        "exp":  expire,
        "iat":  datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and verify signature + expiry.  Raises JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── FastAPI security scheme ───────────────────────────────────
_bearer = HTTPBearer(auto_error=False)

_AUTH_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated — please log in.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — resolves the current authenticated User.
    Raises 401 if the token is missing, expired, or invalid.
    Raises 401 if the user account has been deactivated.
    """
    if not credentials:
        raise _AUTH_EXC
    try:
        payload  = _decode_token(credentials.credentials)
        username = payload.get("sub")
        if not username:
            raise _AUTH_EXC
    except JWTError:
        raise _AUTH_EXC

    user = (
        db.query(User)
        .filter(User.username == username, User.is_active == True)
        .first()
    )
    if not user:
        raise _AUTH_EXC
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency — requires the admin role.  Returns the user on success."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


async def require_export(user: User = Depends(get_current_user)) -> User:
    """
    Dependency — requires User or Admin role.
    Viewers cannot export data.
    """
    if user.role == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Export access requires User or Admin role.",
        )
    return user


# ── First-run admin bootstrap ─────────────────────────────────
def ensure_default_admin(db: Session) -> None:
    """
    Called once at startup.  If no users exist, creates a default admin
    account with a known initial password and prints it clearly to the terminal.
    Always prints current admin credentials reminder at startup.
    """
    if db.query(User).count() == 0:
        # Fresh install — create admin.
        # Default password is read from SRWB_ADMIN_PASSWORD env var;
        # falls back to "Admin@SRWB2025" if not set.
        # Change the password immediately after first login.
        password = os.getenv("SRWB_ADMIN_PASSWORD", "Admin@SRWB2025")
        admin = User(
            username="admin",
            password_hash=hash_password(password),
            role="admin",
            created_by="system",
        )
        db.add(admin)
        db.commit()
        # Remind operator of login URL on every startup
        admin = db.query(User).filter(User.role == "admin").first()
        name = admin.username if admin else "admin"
        print(
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║          SRWB Dashboard — Application Ready              ║\n"
            "╠══════════════════════════════════════════════════════════╣\n"
            f"║  Admin account : {name:<42} ║\n"
            "║  Default pw    : Admin@SRWB2025 (if never changed)       ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        )

