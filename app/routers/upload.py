"""
routers/upload.py

POST /api/upload/excel   — Upload RawData.xlsx, parse DataEntry sheet, upsert into DB.

Returns a summary: { inserted, updated, skipped, errors, zones_found, months_found }
"""
from __future__ import annotations

import io
import math
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import Record, get_db

router = APIRouter(prefix="/api/upload", tags=["Upload"])

# ── Excel column → ORM field mapping ─────────────────────────────────────────
# Maps exact DataEntry header text → Record attribute name
COLUMN_MAP: Dict[str, str] = {
    "Zone":                           "zone",
    "Scheme":                         "scheme",
    "Fiscal Year":                    "fiscal_year",
    "Year":                           "year",
    "Month No.":                      "month_no",
    "Month":                          "month",
    "Quarter":                        "quarter",
    # Water Production
    "Volume Produced (m³)":           "vol_produced",
    "Vol Billed Individual Postpaid": "vol_billed_indiv_pp",
    "Vol Billed CWP Postpaid":        "vol_billed_cwp_pp",
    "Vol Billed Institutions Postpaid":"vol_billed_inst_pp",
    "Vol Billed Commercial Postpaid": "vol_billed_comm_pp",
    "TOTAL Vol Billed Postpaid":      "total_vol_billed_pp",
    "Vol Billed Individual Prepaid":  "vol_billed_indiv_prepaid",
    "Vol Billed CWP Prepaid":         "vol_billed_cwp_prepaid",
    "Vol Billed Institutions Prepaid":"vol_billed_inst_prepaid",
    "Vol Billed Commercial Prepaid":  "vol_billed_comm_prepaid",
    "TOTAL Vol Billed Prepaid":       "total_vol_billed_prepaid",
    "TOTAL Revenue Water m³":         "revenue_water",
    "Non-Revenue Water m³":           "nrw",
    "% NRW":                          "pct_nrw",
    # Chemicals
    "Chlorine kg":                    "chlorine_kg",
    "Alum Sulphate kg":               "alum_kg",
    "Soda Ash kg":                    "soda_ash_kg",
    "Algae Floc litres":              "algae_floc_litres",
    "Sud Floc litres":                "sud_floc_litres",
    "Potassium Permanganate kg":      "kmno4_kg",
    "Cost of Chemicals MWK":          "chem_cost",
    "Chem Cost per m³":               "chem_cost_per_m3",
    # Power
    "Power Usage kWh":                "power_kwh",
    "Cost of Power MWK":              "power_cost",
    "Power Cost per m³":              "power_cost_per_m3",
    # Transport & Ops
    "Distances Covered km":           "distances_km",
    "Fuel Used litres":               "fuel_used_litres",
    "Cost of Fuel MWK":               "fuel_cost",
    "Maintenance MWK":                "maintenance",
    "Staff Costs MWK":                "staff_costs",
    "Wages MWK":                      "wages",
    "Other Overhead MWK":             "other_overhead",
    "TOTAL Operating Costs MWK":      "op_cost",
    "OpCost per m³ Produced":         "op_cost_per_m3_produced",
    "OpCost per m³ Billed":           "op_cost_per_m3_billed",
    # Staffing
    "Permanent Staff":                "perm_staff",
    "Temporary Staff":                "temp_staff",
    # Connections — aggregated
    "ALL Conn BroughtFwd":            "all_conn_bfwd",
    "ALL Conn Applied":               "all_conn_applied",
    "ALL Conn TOTAL Done":            "new_connections",
    "ALL Conn CarriedFwd":            "all_conn_cfwd",
    "Prepaid Meters Installed":       "prepaid_meters_installed",
    # Disconnections
    "Disconnected Individual":        "disconnected_individual",
    "Disconnected Institutional":     "disconnected_inst",
    "Disconnected Commercial":        "disconnected_commercial",
    "Disconnected CWP":               "disconnected_cwp",
    "TOTAL Disconnected":             "total_disconnected",
    # Active — Postpaid
    "Active Postpaid Individual":     "active_post_individual",
    "Active Postpaid Institutional":  "active_post_inst",
    "Active Postpaid Commercial":     "active_post_commercial",
    "Active Postpaid CWP":            "active_post_cwp",
    "TOTAL Active Postpaid":          "active_postpaid",
    # Active — Prepaid
    "Active Prepaid Individual":      "active_prep_individual",
    "Active Prepaid Institutional":   "active_prep_inst",
    "Active Prepaid Commercial":      "active_prep_commercial",
    "Active Prepaid CWP":             "active_prep_cwp",
    "TOTAL Active Prepaid":           "active_prepaid",
    # Active totals
    "TOTAL Active Customers":         "active_customers",
    "Total Metered Consumers":        "total_metered",
    # Population
    "Population Supply Area":         "pop_supply_area",
    "Population Supplied":            "pop_supplied",
    "Pct Population Supplied":        "pct_pop_supplied",
    # Stuck meters — aggregated
    "ALL StuckM CarriedFwd":          "stuck_meters",
    "ALL StuckM New":                 "stuck_new",
    "ALL StuckM Repaired":            "stuck_repaired",
    "ALL StuckM Replaced":            "stuck_replaced",
    # Pipe breakdowns — totals by material
    # (individual sizes summed into these fields during parse)
    "TOTAL Pipe Breakdowns":          "pipe_breakdowns",
    # Pumps & supply
    "Pump Breakdowns":                "pump_breakdowns",
    "Pump Hours Lost":                "pump_hours_lost",
    "Normal Supply Hours":            "supply_hours",
    "Power Failure Hours":            "power_fail_hours",
    # Development lines
    "DevLines 32mm":                  "dev_lines_32mm",
    "DevLines 50mm":                  "dev_lines_50mm",
    "DevLines 63mm":                  "dev_lines_63mm",
    "DevLines 90mm":                  "dev_lines_90mm",
    "DevLines 110mm":                 "dev_lines_110mm",
    "TOTAL Dev Lines Done":           "dev_lines_total",
    # Cash collected
    "TOTAL Cash Coll PP":             "cash_coll_pp",
    "TOTAL Cash Coll Prepaid":        "cash_coll_prepaid",
    "TOTAL Cash Collected":           "cash_collected",
    # Amounts billed
    "TOTAL Amt Billed PP":            "amt_billed_pp",
    "TOTAL Amt Billed Prepaid":       "amt_billed_prepaid",
    "TOTAL Amount Billed":            "amt_billed",
    # Charges
    "TOTAL Service Charge":           "service_charge",
    "TOTAL Meter Rental":             "meter_rental",
    "TOTAL Sales MWK":                "total_sales",
    # Debtors
    "Private Debtors MWK":            "private_debtors",
    "Public Debtors MWK":             "public_debtors",
    "TOTAL Debtors MWK":              "total_debtors",
    # Financial KPIs
    "OpCost per Sales":               "op_cost_per_sales",
    "Cash Collection Rate":           "collection_rate",
    "Collection per Total Sales":     "collection_per_sales",
    # Connection performance
    "Cust Applied Connection":        "conn_applied",
    "Days to Quotation":              "days_to_quotation",
    "Cust Fully Paid":                "conn_fully_paid",
    "Days to Connect":                "days_to_connect",
    "Connectivity Rate":              "connectivity_rate",
    # Query performance
    "Queries Received":               "queries_received",
    "Time to Resolve Queries":        "time_to_resolve",
    "Response Time avg":              "response_time_avg",
}

# PVC column names in order
PVC_COLS  = ["PVC 20mm","PVC 25mm","PVC 32mm","PVC 40mm","PVC 50mm","PVC 63mm",
             "PVC 75mm","PVC 90mm","PVC 110mm","PVC 160mm","PVC 200mm","PVC 250mm","PVC 315mm"]
GI_COLS   = ["GI 15mm","GI 20mm","GI 25mm","GI 40mm","GI 50mm","GI 75mm","GI 100mm","GI 150mm","GI 200mm"]
DI_COLS   = ["DI 150mm","DI 200mm","DI 250mm","DI 300mm","DI 350mm","DI 525mm"]
HDPE_COLS = ["HDPE 20mm","HDPE 25mm","HDPE 32mm","HDPE 50mm","AC 50mm","AC 75mm","AC 100mm","AC 150mm"]


def _safe_float(v: Any) -> float:
    """Convert a cell value to float, returning 0.0 for NaN/None/invalid."""
    if v is None:
        return 0.0
    try:
        f = float(v)
        return 0.0 if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return 0.0


def _safe_str(v: Any) -> str:
    return str(v).strip() if v is not None and not (isinstance(v, float) and math.isnan(v)) else ""


def parse_excel(content: bytes) -> tuple[list[dict], list[str]]:
    """
    Parse RawData.xlsx DataEntry sheet.
    Returns (rows: list[dict mapped to ORM fields], errors: list[str])
    """
    errors: list[str] = []
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name="DataEntry", header=1)
    except Exception as e:
        return [], [f"Failed to read Excel: {e}"]

    # Drop rows with no Zone value (summary/blank rows)
    df = df[df["Zone"].notna() & (df["Zone"].astype(str).str.strip() != "")]
    if df.empty:
        return [], ["No data rows found in DataEntry sheet"]

    rows: list[dict] = []
    for idx, raw in df.iterrows():
        row_num = idx + 3  # 1-indexed, header is row 2
        try:
            zone   = _safe_str(raw.get("Zone"))
            scheme = _safe_str(raw.get("Scheme"))
            month  = _safe_str(raw.get("Month"))
            year   = int(_safe_float(raw.get("Year")) or 0)

            if not zone or not scheme or not month or year == 0:
                errors.append(f"Row {row_num}: missing Zone/Scheme/Month/Year — skipped")
                continue

            # Validate month name
            valid_months = ["January","February","March","April","May","June",
                           "July","August","September","October","November","December"]
            if month not in valid_months:
                errors.append(f"Row {row_num}: invalid month '{month}' — skipped")
                continue

            record: dict = {}

            # Map all direct columns
            for xl_col, orm_field in COLUMN_MAP.items():
                val = raw.get(xl_col)
                if orm_field in ("zone", "scheme", "fiscal_year", "month", "quarter"):
                    record[orm_field] = _safe_str(val)
                elif orm_field in ("year", "month_no"):
                    record[orm_field] = int(_safe_float(val))
                else:
                    record[orm_field] = _safe_float(val)

            # Sum pipe breakdown sub-types
            record["pipe_pvc"]     = sum(_safe_float(raw.get(c)) for c in PVC_COLS  if c in df.columns)
            record["pipe_gi"]      = sum(_safe_float(raw.get(c)) for c in GI_COLS   if c in df.columns)
            record["pipe_di"]      = sum(_safe_float(raw.get(c)) for c in DI_COLS   if c in df.columns)
            record["pipe_hdpe_ac"] = sum(_safe_float(raw.get(c)) for c in HDPE_COLS if c in df.columns)

            rows.append(record)

        except Exception as e:
            errors.append(f"Row {row_num}: parse error — {e}")

    return rows, errors


def upsert_records(rows: list[dict], mode: str, db: Session) -> dict:
    """
    mode: 'append'  — skip existing zone+scheme+month+year combos
          'replace' — update existing records with new values
          'clear'   — delete all records for affected zones/months first
    """
    inserted = updated = skipped = 0

    if mode == "clear":
        zones  = {r["zone"]  for r in rows}
        months = {r["month"] for r in rows}
        years  = {r["year"]  for r in rows}
        deleted = (
            db.query(Record)
            .filter(Record.zone.in_(zones), Record.month.in_(months), Record.year.in_(years))
            .delete(synchronize_session=False)
        )
        db.commit()

    for record_data in rows:
        try:
            existing = (
                db.query(Record)
                .filter(
                    Record.zone    == record_data["zone"],
                    Record.scheme  == record_data["scheme"],
                    Record.month   == record_data["month"],
                    Record.year    == record_data["year"],
                )
                .first()
            )

            if existing:
                if mode == "append":
                    skipped += 1
                    continue
                # replace or clear — update in place
                for k, v in record_data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(Record(**record_data))
                inserted += 1

        except Exception:
            skipped += 1

    db.commit()
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


# ── Upload endpoint ────────────────────────────────────────────────────────────
@router.post("/excel")
async def upload_excel(
    file: UploadFile = File(...),
    mode: str = Form("replace"),          # append | replace | clear
    db: Session = Depends(get_db),
):
    """
    Upload RawData.xlsx and import the DataEntry sheet into the database.

    **mode** controls what happens when a Zone/Scheme/Month/Year already exists:
    - `append`  — skip duplicates (safe for first load)
    - `replace` — overwrite with new data from the file (default for monthly refresh)
    - `clear`   — delete all existing records for the same zones+months first, then insert
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Only .xlsx / .xlsm files are accepted")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Uploaded file is empty")

    rows, parse_errors = parse_excel(content)

    if not rows:
        return JSONResponse(status_code=422, content={
            "status": "error",
            "message": "No valid rows could be parsed from the file",
            "errors": parse_errors,
        })

    counts = upsert_records(rows, mode, db)

    zones_found  = sorted({r["zone"]  for r in rows})
    months_found = sorted({r["month"] for r in rows}, key=lambda m: [
        "April","May","June","July","August","September",
        "October","November","December","January","February","March"
    ].index(m) if m in ["April","May","June","July","August","September",
        "October","November","December","January","February","March"] else 99)

    return {
        "status":       "success",
        "rows_parsed":  len(rows),
        "inserted":     counts["inserted"],
        "updated":      counts["updated"],
        "skipped":      counts["skipped"],
        "zones_found":  zones_found,
        "months_found": months_found,
        "parse_errors": parse_errors[:20],  # cap to 20 for response size
        "total_parse_errors": len(parse_errors),
    }


# ── Validation endpoint (dry-run) ──────────────────────────────────────────────
@router.post("/excel/validate")
async def validate_excel(file: UploadFile = File(...)):
    """
    Parse the file and return a preview without writing to the database.
    Useful to confirm the file is correct before committing.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "Only .xlsx / .xlsm files are accepted")

    content = await file.read()
    rows, parse_errors = parse_excel(content)

    if not rows:
        return {"status": "error", "message": "No valid rows found", "errors": parse_errors}

    zones  = sorted({r["zone"]  for r in rows})
    months = sorted({r["month"] for r in rows})
    schemes = sorted({r["scheme"] for r in rows})

    # Sample first row for preview
    sample = rows[0] if rows else {}

    return {
        "status":         "ok",
        "rows_found":     len(rows),
        "zones":          zones,
        "schemes":        schemes,
        "months":         months,
        "parse_errors":   parse_errors[:10],
        "sample_record":  {k: v for k, v in sample.items()
                           if k in ("zone","scheme","month","year","quarter",
                                    "vol_produced","revenue_water","pct_nrw",
                                    "active_customers","cash_collected","op_cost")},
    }
