# SRWB Operations Dashboard — Implementation Guide

## What You Are Installing

A full-stack web application:

```
RawData.xlsx  →  Upload Button  →  FastAPI Server  →  SQLite Database
                                         ↕
                                    index.html
                               (served in your browser)
```

- **Backend**: Python / FastAPI (the server that handles data)
- **Database**: SQLite (a single file — no separate database server needed)
- **Frontend**: index.html (the dashboard — served by the same Python server)

---

## Requirements

| Requirement | Minimum version | Check command |
|---|---|---|
| Python | 3.10 or newer | `python3 --version` |
| pip | Any recent | `pip --version` |
| A terminal / command prompt | — | — |
| A modern browser | Chrome / Edge / Firefox | — |

> **Windows users:** use Command Prompt or PowerShell. All commands below work on Windows, Linux and macOS.

---

## Step 1 — Get the Project Files

Copy the `srwb_app` folder to your computer. It should contain:

```
srwb_app/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── analytics.py
│   │   ├── catalogue.py
│   │   ├── panels.py
│   │   ├── records.py
│   │   ├── reports.py
│   │   └── upload.py
│   └── static/
│       └── index.html
├── data/
│   ├── srwb.db          ← SQLite database (pre-seeded)
│   └── records.json     ← Seed data backup
├── scripts/
│   ├── import_data.py
│   └── extract_from_html.py
├── requirements.txt
└── start.sh
```

---

## Step 2 — Open a Terminal in the Project Folder

**Windows:**
1. Open File Explorer and navigate to the `srwb_app` folder
2. Click in the address bar, type `cmd`, press Enter
3. A Command Prompt opens directly in that folder

**macOS / Linux:**
1. Open Terminal
2. Type `cd` followed by the path to the folder, e.g.:
   ```
   cd /Users/yourname/Desktop/srwb_app
   ```

Verify you are in the right place:
```bash
# Windows
dir

# macOS / Linux
ls
```
You should see `app`, `data`, `requirements.txt`, etc.

---

## Step 3 — Install Python Dependencies

Run this once. It installs FastAPI, the database library, and Excel support:

```bash
pip install -r requirements.txt
```

Expected output (last few lines):
```
Successfully installed fastapi-0.111.x uvicorn-0.29.x sqlalchemy-2.0.x ...
```

**If you get a permissions error on Linux/macOS:**
```bash
pip install -r requirements.txt --user
```

**Verify the install worked:**
```bash
python3 -c "import fastapi, uvicorn, sqlalchemy, openpyxl; print('All OK')"
```
Expected: `All OK`

---

## Step 4 — Start the Server

```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

You will see:
```
✓ Database tables ready
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

> **`--reload`** means the server automatically restarts if you edit any Python file.
> Remove it in production for slightly better performance.

**Keep this terminal open.** The server runs as long as this window is open.

---

## Step 5 — Open the Dashboard

Open your browser and go to:

```
http://localhost:8000
```

You should see the SRWB Operations & Performance Dashboard with data already loaded.

**Also available:**
- **API documentation (Swagger UI):** http://localhost:8000/docs
- **Alternative API docs (ReDoc):** http://localhost:8000/redoc
- **Health check:** http://localhost:8000/health

---

## Step 6 — Load Your Data (Monthly Update Workflow)

Every month when you have a new `RawData.xlsx`:

### Option A — Using the Upload Button (Recommended)

1. Open the dashboard at `http://localhost:8000`
2. Click the green **📤 Upload Data** button in the top navigation bar
3. Drag and drop your `RawData.xlsx` file onto the upload area, or click to browse
4. Select the import mode:
   - **Overwrite existing** — updates records that already exist (default, use for monthly refresh)
   - **Skip duplicates** — only adds new records, leaves existing untouched
   - **Clear & reimport** — deletes all records for those zones/months first, then imports
5. Click **Upload & Import**
6. The dashboard refreshes automatically with the new data

### Option B — Command Line Import

```bash
python3 scripts/import_data.py --excel data/RawData.xlsx --clear
```

Options:
```
--excel PATH    Path to your RawData.xlsx file
--sheet NAME    Sheet name (default: DataEntry)
--clear         Delete existing records first, then import fresh
```

Example — import without deleting existing data (only add new months):
```bash
python3 scripts/import_data.py --excel data/RawData.xlsx
```

---

## Step 7 — Stopping the Server

In the terminal where uvicorn is running, press:
```
Ctrl + C
```

---

## Step 8 — Running on a Different Port

If port 8000 is already in use:
```bash
python3 -m uvicorn app.main:app --reload --port 8080
```
Then open `http://localhost:8080`

---

## Accessing from Other Computers on Your Network

By default the server only accepts connections from the same computer.
To allow other computers on your office network to access the dashboard:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Other users on the same network can then open:
```
http://YOUR-COMPUTER-IP:8000
```

To find your IP address:
- **Windows:** run `ipconfig` in Command Prompt → look for IPv4 Address
- **macOS:** run `ifconfig | grep "inet "` in Terminal
- **Linux:** run `hostname -I`

Example: `http://192.168.1.50:8000`

---

## Database Location

The SQLite database is a single file:
```
srwb_app/data/srwb.db
```

- **Back it up** by copying this file
- **Restore** by replacing this file with a backup copy
- The server must be stopped before copying the database file

---

## Troubleshooting

### "Command not found: python3"
Try `python` instead of `python3`:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

### "Module not found: fastapi"
The install did not complete. Run:
```bash
pip install fastapi uvicorn sqlalchemy python-multipart openpyxl
```

### "Address already in use" on port 8000
Another application is using port 8000. Use a different port:
```bash
python3 -m uvicorn app.main:app --reload --port 8080
```

### Dashboard shows "Cannot reach API server"
You have opened `index.html` directly in your browser (as a file).
Always access via the server URL: `http://localhost:8000` — not by double-clicking the HTML file.

### Upload fails with "Only .xlsx / .xlsm files accepted"
Make sure your file is saved as Excel format (.xlsx), not .csv or older .xls format.

### No data showing after upload
Check the upload result — it shows rows inserted/updated/skipped.
If skipped is high, try the **Clear & reimport** mode.

---

## Folder Structure Reference

```
srwb_app/
├── app/
│   ├── main.py              ← Server entry point and URL routing
│   ├── database.py          ← Database schema (all 112 columns)
│   ├── schemas.py           ← API request/response validation
│   ├── routers/
│   │   ├── analytics.py     ← KPI, monthly, by-zone aggregations
│   │   ├── catalogue.py     ← Zones, schemes, months, data quality
│   │   ├── panels.py        ← Dashboard tile drill-down data
│   │   ├── records.py       ← Raw record CRUD + CSV export
│   │   ├── reports.py       ← All 11 report pages data
│   │   └── upload.py        ← Excel file import
│   └── static/
│       └── index.html       ← The complete dashboard frontend
├── data/
│   ├── srwb.db              ← SQLite database (all operational data)
│   └── records.json         ← JSON backup of initial seed data
├── scripts/
│   ├── import_data.py       ← CLI import from JSON or Excel
│   └── extract_from_html.py ← One-time tool to extract legacy data
├── requirements.txt         ← Python package list
└── start.sh                 ← Linux/macOS convenience startup script
```

---

## API Endpoints Quick Reference

All endpoints are documented interactively at `http://localhost:8000/docs`

| Category | Endpoint | Description |
|---|---|---|
| **System** | `GET /health` | Server status |
| **Dashboard** | `GET /api/analytics/kpi` | Overall KPI summary |
| | `GET /api/analytics/monthly` | 12-month trend data |
| | `GET /api/analytics/by-zone` | Per-zone totals |
| | `GET /api/analytics/by-scheme` | Per-scheme totals |
| **Reports** | `GET /api/reports/monthly` | All 11 report pages data |
| **Catalogue** | `GET /api/catalogue/zones` | Available zones |
| | `GET /api/catalogue/zone-schemes` | Zone → scheme mapping |
| | `GET /api/catalogue/months` | Months with data |
| | `GET /api/catalogue/data-quality` | Anomaly scan |
| | `GET /api/catalogue/summary` | Record counts & fiscal year |
| **Records** | `GET /api/records/` | Raw records (filterable) |
| | `GET /api/records/export/csv` | Download as CSV |
| **Upload** | `POST /api/upload/excel` | Import RawData.xlsx |
| | `POST /api/upload/excel/validate` | Dry-run preview |

All filter endpoints accept: `?zones=Zomba,Mulanje&months=April,May,June&schemes=Domasi`

---

## Filter Parameters

The slicers on the left sidebar send these parameters automatically.
You can also use them directly in the API:

```
http://localhost:8000/api/analytics/kpi?zones=Zomba
http://localhost:8000/api/analytics/kpi?zones=Zomba,Mulanje&months=April,May,June
http://localhost:8000/api/reports/monthly?zones=Liwonde&months=April,May,June
```

---

## Production Deployment (Optional)

For a permanent server installation:

### Install as a system service (Linux)

Create `/etc/systemd/system/srwb.service`:
```ini
[Unit]
Description=SRWB Dashboard
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/srwb_app
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable srwb
sudo systemctl start srwb
sudo systemctl status srwb
```

### Run with Gunicorn (multiple workers, better performance)

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Upgrade to PostgreSQL (when data grows significantly)

In `app/database.py`, change the single line:
```python
# FROM:
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'srwb.db')}"

# TO:
DATABASE_URL = "postgresql://username:password@localhost:5432/srwb"
```
Then install: `pip install psycopg2-binary`

---

*SRWB Operations & Performance Dashboard — FY 2025/26*
