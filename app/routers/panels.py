"""
routers/panels.py

One endpoint per dashboard panel.  Each endpoint returns exactly the
numbers that panel needs — KPI stats + chart datasets — so the browser
makes one request per panel open instead of 2–3 separate calls.

GET /api/panels/production        — Water Production tile
GET /api/panels/nrw               — Revenue Water & NRW tile
GET /api/panels/customers         — Customers tile
GET /api/panels/connections       — New Connections tile
GET /api/panels/breakdowns        — Pipe & Pump Breakdowns tile
GET /api/panels/collections       — Bills & Collections tile
GET /api/panels/expenses          — Operating Expenses tile
GET /api/panels/debtors           — Debtors tile
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import Record, get_db

router = APIRouter(prefix="/api/panels", tags=["Panels"])

MONTHS_ORDER = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March",
]
ZONE_COLORS = {
    "Liwonde": "#0077b6", "Mangochi": "#0d9488",
    "Mulanje": "#16a34a", "Ngabu": "#d97706", "Zomba": "#7c3aed",
}


def _filter(q, zones=None, schemes=None, months=None):
    if zones:   q = q.filter(Record.zone.in_(zones))
    if schemes: q = q.filter(Record.scheme.in_(schemes))
    if months:  q = q.filter(Record.month.in_(months))
    return q


def _parse(v: Optional[str]):
    return v.split(",") if v else None


def _by_zone(rows):
    """Group rows by zone, returning latest-per-scheme snapshot for stock fields."""
    zone_rows = defaultdict(list)
    for r in rows:
        zone_rows[r.zone].append(r)

    result = []
    for zone, zrows in sorted(zone_rows.items()):
        latest = {}
        for r in zrows:
            if r.scheme not in latest or r.month_no > latest[r.scheme].month_no:
                latest[r.scheme] = r
        lv = list(latest.values())
        vol = sum(r.vol_produced for r in zrows)
        nrw = sum(r.nrw for r in zrows)
        result.append({
            "zone":             zone,
            "color":            ZONE_COLORS.get(zone, "#64748b"),
            "vol_produced":     round(vol, 1),
            "revenue_water":    round(sum(r.revenue_water for r in zrows), 1),
            "nrw":              round(nrw, 1),
            "nrw_pct":          round(nrw / vol * 100, 2) if vol else 0,
            "active_customers": round(sum(r.active_customers for r in lv)),
            "active_postpaid":  round(sum(r.active_postpaid  for r in lv)),
            "active_prepaid":   round(sum(r.active_prepaid   for r in lv)),
            "new_connections":  round(sum(r.new_connections  for r in zrows)),
            "cash_collected":   round(sum(r.cash_collected   for r in zrows), 2),
            "amt_billed":       round(sum(r.amt_billed       for r in zrows), 2),
            "op_cost":          round(sum(r.op_cost          for r in zrows), 2),
            "chem_cost":        round(sum(r.chem_cost        for r in zrows), 2),
            "power_cost":       round(sum(r.power_cost       for r in zrows), 2),
            "power_kwh":        round(sum(r.power_kwh        for r in zrows), 2),
            "fuel_cost":        round(sum(r.fuel_cost        for r in zrows), 2),
            "staff_costs":      round(sum(r.staff_costs      for r in zrows), 2),
            "pipe_breakdowns":  round(sum(r.pipe_breakdowns  for r in zrows)),
            "pump_breakdowns":  round(sum(r.pump_breakdowns  for r in zrows)),
            "service_charge":   round(sum(r.service_charge   for r in zrows), 2),
            "meter_rental":     round(sum(r.meter_rental     for r in zrows), 2),
            "private_debtors":  round(sum(max(0, r.private_debtors) for r in lv), 2),
            "public_debtors":   round(sum(max(0, r.public_debtors)  for r in lv), 2),
            "total_debtors":    round(sum(max(0, r.total_debtors)   for r in lv), 2),
            "stuck_meters":     round(sum(max(0, r.stuck_meters)    for r in lv)),
            "stuck_new":        round(sum(r.stuck_new    for r in zrows)),
            "stuck_repaired":   round(sum(r.stuck_repaired for r in zrows)),
            "supply_hours":     round(sum(r.supply_hours    for r in zrows) / max(len(zrows),1), 1),
            "power_fail_hours": round(sum(r.power_fail_hours for r in zrows)),
        })
    return result


def _monthly_series(rows):
    by_month = defaultdict(list)
    for r in rows:
        by_month[r.month].append(r)

    result = []
    for month in MONTHS_ORDER:
        mrows = by_month.get(month, [])
        if not mrows:
            result.append({"month": month, "has_data": False})
            continue
        latest = {}
        for r in mrows:
            k = (r.zone, r.scheme)
            if k not in latest or r.month_no > latest[k].month_no:
                latest[k] = r
        lv = list(latest.values())
        vol = sum(r.vol_produced for r in mrows)
        if vol == 0 and sum(r.active_customers for r in lv) == 0:
            result.append({"month": month, "has_data": False})
            continue
        nrw = sum(r.nrw for r in mrows)
        result.append({
            "month":             month,
            "has_data":          True,
            "vol_produced":      round(vol, 1),
            "revenue_water":     round(sum(r.revenue_water   for r in mrows), 1),
            "nrw":               round(nrw, 1),
            "pct_nrw":           round(nrw / vol * 100, 2) if vol else 0,
            "active_customers":  round(sum(r.active_customers for r in lv)),
            "active_postpaid":   round(sum(r.active_postpaid  for r in lv)),
            "active_prepaid":    round(sum(r.active_prepaid   for r in lv)),
            "new_connections":   round(sum(r.new_connections  for r in mrows)),
            "cash_collected":    round(sum(r.cash_collected   for r in mrows), 2),
            "amt_billed":        round(sum(r.amt_billed       for r in mrows), 2),
            "op_cost":           round(sum(r.op_cost          for r in mrows), 2),
            "chem_cost":         round(sum(r.chem_cost        for r in mrows), 2),
            "power_cost":        round(sum(r.power_cost       for r in mrows), 2),
            "power_kwh":         round(sum(r.power_kwh        for r in mrows), 2),
            "pipe_breakdowns":   round(sum(r.pipe_breakdowns  for r in mrows)),
            "pump_breakdowns":   round(sum(r.pump_breakdowns  for r in mrows)),
            "service_charge":    round(sum(r.service_charge   for r in mrows), 2),
            "meter_rental":      round(sum(r.meter_rental     for r in mrows), 2),
            "total_debtors":     round(sum(max(0, r.total_debtors) for r in lv), 2),
            "private_debtors":   round(sum(max(0, r.private_debtors) for r in lv), 2),
            "public_debtors":    round(sum(max(0, r.public_debtors)  for r in lv), 2),
            "stuck_meters":      round(sum(max(0, r.stuck_meters) for r in lv)),
            "stuck_new":         round(sum(r.stuck_new    for r in mrows)),
            "stuck_repaired":    round(sum(r.stuck_repaired for r in mrows)),
            "supply_hours":      round(sum(r.supply_hours for r in mrows) / max(len(mrows),1), 1),
            "power_fail_hours":  round(sum(r.power_fail_hours for r in mrows)),
        })
    return result


def _panel_base(zones=None, schemes=None, months=None, db=None):
    """Shared data fetch for all panels."""
    q = _filter(db.query(Record), _parse(zones), _parse(schemes), _parse(months))
    rows = q.all()
    by_zone   = _by_zone(rows)
    monthly   = _monthly_series(rows)
    return rows, by_zone, monthly


def _panel_route(suffix):
    return Query(None, description=f"Comma-separated {suffix}")


# ── Production ────────────────────────────────────────────────
@router.get("/production")
def panel_production(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    vol = sum(r.vol_produced  for r in rows)
    rw  = sum(r.revenue_water for r in rows)
    nrw = sum(r.nrw           for r in rows)
    return {
        "kpi": {"vol_produced": round(vol,1), "revenue_water": round(rw,1),
                "nrw": round(nrw,1), "nrw_pct": round(nrw/vol*100,2) if vol else 0},
        "by_zone": [{"zone":z["zone"],"color":z["color"],"vol_produced":z["vol_produced"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "vol_produced":m.get("vol_produced",0),"revenue_water":m.get("revenue_water",0)} for m in monthly],
    }


# ── NRW ───────────────────────────────────────────────────────
@router.get("/nrw")
def panel_nrw(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    vol = sum(r.vol_produced for r in rows)
    nrw = sum(r.nrw          for r in rows)
    return {
        "kpi": {"vol_produced": round(vol,1), "revenue_water": round(vol-nrw,1),
                "nrw": round(nrw,1), "nrw_pct": round(nrw/vol*100,2) if vol else 0},
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "revenue_water":z["revenue_water"],"nrw":z["nrw"],"nrw_pct":z["nrw_pct"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "pct_nrw":m.get("pct_nrw",0)} for m in monthly],
    }


# ── Customers ─────────────────────────────────────────────────
@router.get("/customers")
def panel_customers(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    lv_map = {}
    for r in rows:
        k = (r.zone, r.scheme)
        if k not in lv_map or r.month_no > lv_map[k].month_no:
            lv_map[k] = r
    lv = list(lv_map.values())
    return {
        "kpi": {
            "active_customers": round(sum(r.active_customers for r in lv)),
            "active_postpaid":  round(sum(r.active_postpaid  for r in lv)),
            "active_prepaid":   round(sum(r.active_prepaid   for r in lv)),
            "pop_supplied":     round(sum(r.pop_supplied      for r in lv)),
        },
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "active_customers":z["active_customers"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "active_customers":m.get("active_customers",0)} for m in monthly],
    }


# ── Connections ───────────────────────────────────────────────
@router.get("/connections")
def panel_connections(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    distances = round(sum(r.distances_km for r in rows), 1)
    return {
        "kpi": {"new_connections": round(sum(r.new_connections for r in rows)), "distances_km": distances},
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "new_connections":z["new_connections"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "new_connections":m.get("new_connections",0)} for m in monthly],
    }


# ── Breakdowns ────────────────────────────────────────────────
@router.get("/breakdowns")
def panel_breakdowns(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    pipe = sum(r.pipe_breakdowns for r in rows)
    pump = sum(r.pump_breakdowns for r in rows)
    lv_map = {}
    for r in rows:
        k=(r.zone,r.scheme)
        if k not in lv_map or r.month_no > lv_map[k].month_no: lv_map[k]=r
    active = sum(r.active_customers for r in lv_map.values())
    return {
        "kpi": {
            "pipe_breakdowns": round(pipe),
            "pump_breakdowns": round(pump),
            "total":           round(pipe + pump),
            "per_1k_customers": round(pipe/active*1000, 1) if active else 0,
        },
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "pipe_breakdowns":z["pipe_breakdowns"],"pump_breakdowns":z["pump_breakdowns"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "pipe_breakdowns":m.get("pipe_breakdowns",0)} for m in monthly],
    }


# ── Collections ───────────────────────────────────────────────
@router.get("/collections")
def panel_collections(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    cash   = sum(r.cash_collected for r in rows)
    billed = sum(r.amt_billed     for r in rows)
    rate   = cash / billed if billed else 0
    return {
        "kpi": {
            "cash_collected":  round(cash, 2),
            "amt_billed":      round(billed, 2),
            "collection_rate": round(rate * 100, 2),
            "billing_gap":     round(abs(billed - cash), 2),
            "surplus":          round(max(0, cash - billed), 2),
        },
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "cash_collected":z["cash_collected"],"amt_billed":z["amt_billed"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "cash_collected":m.get("cash_collected",0),"amt_billed":m.get("amt_billed",0)} for m in monthly],
    }


# ── Expenses ──────────────────────────────────────────────────
@router.get("/expenses")
def panel_expenses(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    op     = sum(r.op_cost     for r in rows)
    chem   = sum(r.chem_cost   for r in rows)
    power  = sum(r.power_cost  for r in rows)
    fuel   = sum(r.fuel_cost   for r in rows)
    staff  = sum(r.staff_costs for r in rows)
    kwh = sum(r.power_kwh for r in rows)
    return {
        "kpi": {
            "op_cost":    round(op, 2),
            "chem_cost":  round(chem, 2),
            "power_cost": round(power, 2),
            "power_kwh":  round(kwh, 1),
            "fuel_cost":  round(fuel, 2),
            "staff_costs":round(staff, 2),
        },
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "op_cost":z["op_cost"],"chem_cost":z["chem_cost"],
                     "power_cost":z["power_cost"]} for z in by_zone],
        "cost_split": [
            {"label":"Staff",      "value": round(staff, 2), "color":"#0077b6"},
            {"label":"Power",      "value": round(power, 2), "color":"#d97706"},
            {"label":"Chemicals",  "value": round(chem, 2),  "color":"#7c3aed"},
            {"label":"Fuel",       "value": round(fuel, 2),  "color":"#dc2626"},
            {"label":"Other",      "value": round(max(0, op-staff-power-chem-fuel), 2), "color":"#64748b"},
        ],
    }


# ── Debtors ───────────────────────────────────────────────────
@router.get("/debtors")
def panel_debtors(
    zones: Optional[str] = Query(None), schemes: Optional[str] = Query(None),
    months: Optional[str] = Query(None), db: Session = Depends(get_db),
):
    rows, by_zone, monthly = _panel_base(zones, schemes, months, db)
    lv_map = {}
    for r in rows:
        k=(r.zone,r.scheme)
        if k not in lv_map or r.month_no > lv_map[k].month_no: lv_map[k]=r
    lv = list(lv_map.values())
    total   = sum(max(0, r.total_debtors)   for r in lv)
    private = sum(max(0, r.private_debtors) for r in lv)
    public  = sum(max(0, r.public_debtors)  for r in lv)
    return {
        "kpi": {
            "total_debtors":   round(total, 2),
            "private_debtors": round(private, 2),
            "public_debtors":  round(public, 2),
            "private_pct":     round(private/total*100, 1) if total else 0,
        },
        "by_zone": [{"zone":z["zone"],"color":z["color"],
                     "total_debtors":z["total_debtors"],
                     "private_debtors":z["private_debtors"],
                     "public_debtors":z["public_debtors"]} for z in by_zone],
        "monthly": [{"month":m["month"],"has_data":m["has_data"],
                     "total_debtors":m.get("total_debtors",0)} for m in monthly],
    }
