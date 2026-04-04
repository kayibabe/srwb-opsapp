"""
main.py — FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --port 8000

Authentication
--------------
All /api/* routes (except /api/auth/login) require a JWT in the header:
    Authorization: Bearer <token>

Role-based access is enforced via FastAPI dependencies at the router level:
  - All read endpoints        → get_current_user  (any valid role)
  - /api/upload/*             → require_admin     (admin only)
  - /api/records/export/csv   → require_export    (admin or user; not viewer)
  - /api/admin/*              → require_admin     (admin only)
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from app.auth import ensure_default_admin, get_current_user, require_admin
from app.database import SessionLocal, create_tables
from app.routers import analytics, catalogue, panels, records, reports, upload
from app.routers.users import admin_router, auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables, bootstrap default admin if needed."""
    create_tables()
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    print("✓ Database tables ready")
    print("✓ User authentication active  (JWT / bcrypt)")
    yield


app = FastAPI(
    title="SRWB Operations Dashboard API",
    description=(
        "Backend API for the Southern Region Water Board "
        "Operations & Performance Dashboard.\n\n"
        "All monetary values are in **MWK (Malawian Kwacha)**. "
        "Volume in **m³**. Financial year runs April → March.\n\n"
        "**Authentication:** `POST /api/auth/login` with username + password "
        "to obtain a Bearer token.  Include it as:\n"
        "`Authorization: Bearer <token>`\n\n"
        "**Roles:** `admin` · `user` · `viewer`"
    ),
    version="2.0.0",
    contact={"name": "SRWB IT / Corporate Planning"},
    license_info={"name": "Internal Use"},
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── Auth endpoints (public — no auth dependency) ───────────────
app.include_router(auth_router)

# ── Admin user-management (admin role required) ───────────────
app.include_router(admin_router, dependencies=[Depends(require_admin)])

# ── Data read endpoints (any authenticated user) ──────────────
# require_export on /export/csv is enforced inside records.py
app.include_router(records.router,   dependencies=[Depends(get_current_user)])
app.include_router(analytics.router, dependencies=[Depends(get_current_user)])
app.include_router(catalogue.router, dependencies=[Depends(get_current_user)])
app.include_router(panels.router,    dependencies=[Depends(get_current_user)])
app.include_router(reports.router,   dependencies=[Depends(get_current_user)])

# ── Upload (admin only) ───────────────────────────────────────
app.include_router(upload.router, dependencies=[Depends(require_admin)])

# ── Static assets ─────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INDEX_PATH  = os.path.join(STATIC_DIR, "index.html")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Root — inject API base URL then serve dashboard ───────────
@app.get("/", include_in_schema=False)
async def serve_dashboard(request: Request):
    if not os.path.exists(INDEX_PATH):
        return {"message": "SRWB API running. Place index.html in app/static/"}
    base_url = str(request.base_url).rstrip("/")
    with open(INDEX_PATH, encoding="utf-8") as f:
        content = f.read()
    content = content.replace("__API_BASE__", base_url)
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        }
    )


# ── Health check (public) ─────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": app.version}
