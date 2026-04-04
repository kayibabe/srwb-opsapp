"""
routers/catalogue.py

Lightweight metadata endpoints — the frontend calls these on startup
to build its slicer state without having to parse the full records list.

GET /api/catalogue/zones          — ordered list of zones
GET /api/catalogue/zone-schemes   — {zone: [scheme, ...]} mapping
GET /api/catalogue/months         — available months in the DB (ordered)
GET /api/catalogue/years          — available fiscal years
GET /api/catalogue/data-quality   — anomaly scan results
"""
from __future__ import annotations

from typing import List, Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import Record, get_db

router = APIRouter(prefix="/api/catalogue", tags=["Catalogue"])

MONTHS_ORDER = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March",
]


@router.get("/zones", response_model=List[str])
def list_zones(db: Session = Depends(get_db)):
    rows = db.query(Record.zone).distinct().order_by(Record.zone).all()
    return [r.zone for r in rows]


@router.get("/zone-schemes")
def zone_schemes(db: Session = Depends(get_db)) -> Dict[str, List[str]]:
    rows = (
        db.query(Record.zone, Record.scheme)
        .distinct()
        .order_by(Record.zone, Record.scheme)
        .all()
    )
    result: Dict[str, List[str]] = {}
    for zone, scheme in rows:
        result.setdefault(zone, []).append(scheme)
    return result


@router.get("/summary")
def catalogue_summary(db: Session = Depends(get_db)) -> Dict:
    """Quick stats for the status bar and dashboard header."""
    from sqlalchemy import func
    total   = db.query(func.count(Record.id)).scalar()
    zones   = db.query(Record.zone).distinct().count()
    schemes = db.query(Record.scheme).distinct().count()
    months  = db.query(Record.month).distinct().count()
    fy      = db.query(Record.fiscal_year).distinct().order_by(Record.fiscal_year.desc()).first()
    return {
        "total_records": total,
        "zones":   zones,
        "schemes": schemes,
        "months":  months,
        "fiscal_year": fy[0] if fy else None,
    }


@router.get("/months")
def available_months(db: Session = Depends(get_db)) -> List[str]:
    rows = db.query(Record.month).distinct().all()
    have = {r.month for r in rows}
    return [m for m in MONTHS_ORDER if m in have]


@router.get("/years", response_model=List[int])
def available_years(db: Session = Depends(get_db)):
    # Returns FY end years: 2026 = FY2025/26 (Apr 2025 to Mar 2026)
    rows = db.query(Record.year, Record.month_no).distinct().all()
    fy_years = set()
    for cal_year, month_no in rows:
        # Apr(4)-Dec(12) -> FY ends NEXT calendar year
        # Jan(1)-Mar(3)  -> FY ends THIS calendar year
        fy_end = cal_year + 1 if month_no >= 4 else cal_year
        fy_years.add(fy_end)
    return sorted(fy_years)


@router.get("/data-quality")
def data_quality(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Runs the same anomaly rules as the old frontend DQ page, server-side."""
    rows = db.query(Record).all()
    issues = []

    for r in rows:
        tag = f"{r.zone} / {r.scheme} / {r.month}"

        if r.total_debtors < -1000:
            issues.append({"sev": "High", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Total Debtors",
                "value": r.total_debtors,
                "msg": "Negative debtor balance — check debit/credit entries"})

        if r.private_debtors < -1000:
            issues.append({"sev": "High", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Private Debtors",
                "value": r.private_debtors,
                "msg": "Negative private debtors — overpayment or reversal error"})

        if r.stuck_meters < 0:
            issues.append({"sev": "Medium", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Stuck Meters C/Fwd",
                "value": r.stuck_meters,
                "msg": "Negative carried-forward — repairs exceed opening balance"})

        if r.staff_costs == 0 and r.active_customers > 500 and r.vol_produced > 0:
            issues.append({"sev": "Medium", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Staff Costs",
                "value": 0,
                "msg": "Zero staff costs with >500 customers — payroll data missing?"})

        if r.amt_billed > 0 and r.cash_collected > r.amt_billed * 3:
            issues.append({"sev": "Medium", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Cash Collected",
                "value": r.cash_collected,
                "msg": "Cash collected >3× amount billed — backdated receipts or error"})

        if r.vol_produced == 0 and r.month not in ("January", "February", "March"):
            issues.append({"sev": "Low", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Vol Produced",
                "value": 0,
                "msg": "No production recorded — data entry gap or dry period"})

        if r.pct_nrw > 0.5 and r.vol_produced > 500:
            issues.append({"sev": "High", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "NRW %",
                "value": round(r.pct_nrw * 100, 1),
                "msg": "NRW exceeds 50% — verify metering or check for pipe losses"})

        if r.revenue_water > r.vol_produced + 1:
            issues.append({"sev": "High", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "Revenue Water",
                "value": r.revenue_water,
                "msg": "Revenue water exceeds total produced — calculation error"})

        if r.nrw < 0:
            issues.append({"sev": "High", "zone": r.zone, "scheme": r.scheme,
                "month": r.month, "field": "NRW (m³)",
                "value": r.nrw,
                "msg": "Negative NRW — revenue water exceeds production"})

    summary = {
        "total": len(issues),
        "high":   sum(1 for i in issues if i["sev"] == "High"),
        "medium": sum(1 for i in issues if i["sev"] == "Medium"),
        "low":    sum(1 for i in issues if i["sev"] == "Low"),
    }

    return {"summary": summary, "issues": issues}
