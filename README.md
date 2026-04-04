# SRWB Operations & Performance Dashboard

A full-stack internal web application for the **Southern Region Water Board (SRWB)** of Malawi.
Provides real-time operational KPIs, analytics, and reporting across all zones and schemes.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ / FastAPI |
| Database | SQLite (single file, no server needed) |
| Frontend | Single-page app — `app/static/index.html` |
| Auth | JWT (8-hour tokens) + bcrypt passwords |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Open in browser
http://localhost:8000
```

On first run the server creates `data/srwb.db` and a default **admin** account.  
Credentials are printed to the terminal. **Change the password immediately.**

## Configuration

| Environment variable | Purpose | Default |
|---|---|---|
| `SRWB_SECRET_KEY` | JWT signing secret | Auto-generated in `data/srwb.secret` |
| `SRWB_ADMIN_PASSWORD` | Default admin password on fresh install | `Admin@SRWB2025` |

## Project Structure

```
opsapp/
├── app/
│   ├── main.py          # FastAPI entry point, middleware, router registration
│   ├── auth.py          # JWT + bcrypt, role dependencies
│   ├── database.py      # SQLAlchemy models (Record, User)
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── routers/
│   │   ├── upload.py    # POST /api/upload/excel — Excel ingestion
│   │   ├── records.py   # CRUD + CSV export
│   │   ├── analytics.py # KPI aggregation endpoints
│   │   ├── panels.py    # Summary panel data
│   │   ├── reports.py   # Report generation
│   │   ├── catalogue.py # Zone / scheme catalogue
│   │   └── users.py     # Auth + admin user management
│   └── static/
│       └── index.html   # Dashboard SPA
├── scripts/
│   ├── migrate_add_unique_constraint.py  # One-time DB migration
│   └── import_data.py                   # Bulk data import helper
├── requirements.txt
├── start.sh             # Linux/macOS start script
└── run.bat              # Windows start script
```

## Roles

| Role | View | Export CSV | Upload Excel | Manage Users |
|---|---|---|---|---|
| `admin` | ✓ | ✓ | ✓ | ✓ |
| `user` | ✓ | ✓ | — | — |
| `viewer` | ✓ | — | — | — |

## Database Migration (existing installs)

If you installed before April 2026 and need to add the unique constraint on `(zone, scheme, month, year)`:

```bash
python scripts/migrate_add_unique_constraint.py
```

Safe to re-run — checks whether the constraint already exists.

## Windows Git Sync

```batch
git-sync.bat
```

Prompts for a commit message, then stages, commits, and pushes in one step.

## API Docs

With the server running, visit:  
`http://localhost:8000/docs` — Swagger UI  
`http://localhost:8000/redoc` — ReDoc
