"""
routers/reports.py

Single comprehensive monthly-aggregate endpoint used by all report pages.

GET /api/reports/monthly   — returns 12-month FY array with ALL report fields
"""
from __future__ import annotations
from collections import defaultdict
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from sqlalchemy import or_, and_
from app.database import Record, get_db

router = APIRouter(prefix="/api/reports", tags=["Reports"])

FY_MONTHS = [
    "April","May","June","July","August","September",
    "October","November","December","January","February","March",
]


def _filter(q, zones=None, schemes=None, months=None, year=None):
    if zones:   q = q.filter(Record.zone.in_(zones.split(",")))
    if schemes: q = q.filter(Record.scheme.in_(schemes.split(",")))
    if months:  q = q.filter(Record.month.in_(months.split(",")))
    if year:
        q = q.filter(or_(
            and_(Record.year == year - 1, Record.month_no >= 4),
            and_(Record.year == year,     Record.month_no <= 3),
        ))
    return q


def _latest_per_scheme(rows):
    """Return the latest record per (zone, scheme) — for stock metrics."""
    lv: Dict[tuple, Record] = {}
    for r in rows:
        k = (r.zone, r.scheme)
        if k not in lv or r.month_no > lv[k].month_no:
            lv[k] = r
    return list(lv.values())


@router.get("/monthly")
def reports_monthly(
    zones:   Optional[str] = Query(None),
    schemes: Optional[str] = Query(None),
    months:  Optional[str] = Query(None),
    year:    Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Returns one dict per FY month with ALL fields needed by all 11 report pages.
    Stock metrics (customers, debtors, etc.) use the latest snapshot per scheme.
    Flow metrics (volume, cash, etc.) use the sum across all records for that month.
    """
    rows = _filter(db.query(Record), zones, schemes, months, year).all()

    by_month: Dict[str, List[Record]] = defaultdict(list)
    for r in rows:
        by_month[r.month].append(r)

    result = []
    for month in FY_MONTHS:
        mrows = by_month.get(month, [])
        if not mrows:
            result.append({"month": month, "has_data": False})
            continue

        lv  = _latest_per_scheme(mrows)
        vol = sum(r.vol_produced for r in mrows)
        if vol == 0 and sum(r.active_customers for r in lv) == 0:
            result.append({"month": month, "has_data": False})
            continue
        nrw  = sum(r.nrw           for r in mrows)
        cash_pp  = sum(r.cash_coll_pp      for r in mrows)
        cash_pre = sum(r.cash_coll_prepaid for r in mrows)
        bill_pp  = sum(r.amt_billed_pp      for r in mrows)
        bill_pre = sum(r.amt_billed_prepaid for r in mrows)

        result.append({
            "month":    month,
            "has_data": True,

            # ── Production & NRW ───────────────────────────────────────
            "vol_produced":           round(vol, 1),
            "revenue_water":          round(sum(r.revenue_water for r in mrows), 1),
            "nrw":                    round(nrw, 1),
            "pct_nrw":                round(nrw / vol * 100, 2) if vol else 0,
            "vol_billed_pp":          round(sum(r.total_vol_billed_pp      for r in mrows), 1),
            "vol_billed_prepaid":     round(sum(r.total_vol_billed_prepaid for r in mrows), 1),

            # ── Chemicals ──────────────────────────────────────────────
            "chlorine_kg":            round(sum(r.chlorine_kg       for r in mrows), 2),
            "alum_kg":                round(sum(r.alum_kg           for r in mrows), 2),
            "soda_ash_kg":            round(sum(r.soda_ash_kg       for r in mrows), 2),
            "algae_floc_litres":      round(sum(r.algae_floc_litres for r in mrows), 2),
            "sud_floc_litres":        round(sum(r.sud_floc_litres   for r in mrows), 2),
            "kmno4_kg":               round(sum(r.kmno4_kg          for r in mrows), 2),
            "chem_cost":              round(sum(r.chem_cost         for r in mrows), 2),
            "chem_cost_per_m3":       round(sum(r.chem_cost for r in mrows) / vol, 4) if vol else 0,
            "ratio_prod_chem":        round(sum(r.chem_cost for r in mrows) / vol, 4) if vol else 0,
            "cost_per_vol_chem":      round(sum(r.chem_cost for r in mrows) / vol, 2) if vol else 0,
            "chem_per_m3":            round(sum(r.chem_cost for r in mrows) / vol, 2) if vol else 0,

            # ── Power & Operations ─────────────────────────────────────
            "power_kwh":              round(sum(r.power_kwh   for r in mrows), 1),
            "power_cost":             round(sum(r.power_cost  for r in mrows), 2),
            "fuel_cost":              round(sum(r.fuel_cost   for r in mrows), 2),
            "maintenance":            round(sum(r.maintenance for r in mrows), 2),
            "staff_costs":            round(sum(r.staff_costs for r in mrows), 2),
            "wages":                  round(sum(r.wages       for r in mrows), 2),
            "other_overhead":         round(sum(r.other_overhead for r in mrows), 2),
            "op_cost":                round(sum(r.op_cost     for r in mrows), 2),
            "maintenance_cost":       round(sum(r.maintenance for r in mrows), 2),
            "supply_hours":           round(sum(r.supply_hours for r in mrows) / max(len(mrows), 1), 1),

            # ── Customers (stock — latest per scheme) ──────────────────
            "total_metered":          round(sum(r.total_metered      for r in lv)),
            "total_disconnected":     round(sum(r.total_disconnected for r in lv)),
            "active_customers":       round(sum(r.active_customers   for r in lv)),
            "active_postpaid":        round(sum(r.active_postpaid    for r in lv)),
            "active_prepaid":         round(sum(r.active_prepaid     for r in lv)),
            "active_post_individual": round(sum(r.active_post_individual for r in lv)),
            "active_post_inst":       round(sum(r.active_post_inst       for r in lv)),
            "active_post_commercial": round(sum(r.active_post_commercial for r in lv)),
            "active_post_cwp":        round(sum(r.active_post_cwp        for r in lv)),
            "active_prep_individual": round(sum(r.active_prep_individual for r in lv)),
            "active_prep_inst":       round(sum(r.active_prep_inst       for r in lv)),
            "active_prep_commercial": round(sum(r.active_prep_commercial for r in lv)),
            "active_prep_cwp":        round(sum(r.active_prep_cwp        for r in lv)),

            # ── Population ─────────────────────────────────────────────
            "pop_supplied":           round(sum(r.pop_supplied    for r in lv)),
            "pop_supply_area":        round(sum(r.pop_supply_area for r in lv)),
            "stuck_meters":           round(sum(max(0, r.stuck_meters) for r in lv)),
            "stuck_new":              round(sum(r.stuck_new       for r in mrows)),
            "stuck_repaired":         round(sum(r.stuck_repaired  for r in mrows)),

            # ── NWCs (flow) ────────────────────────────────────────────
            "all_conn_bfwd":          round(sum(r.all_conn_bfwd    for r in lv)),
            "all_conn_applied":       round(sum(r.all_conn_applied  for r in mrows)),
            "new_connections":        round(sum(r.new_connections   for r in mrows)),
            "all_conn_cfwd":          round(sum(r.all_conn_cfwd     for r in lv)),
            "prepaid_meters_installed": round(sum(r.prepaid_meters_installed for r in mrows)),

            # ── Billing ────────────────────────────────────────────────
            "billed_pp":              round(bill_pp, 2),
            "collected_pp":           round(cash_pp, 2),
            "billed_prepaid":         round(bill_pre, 2),
            "collected_prepaid":      round(cash_pre, 2),
            "amt_billed":             round(bill_pp + bill_pre, 2),
            "amt_billed_pp":          round(bill_pp, 2),
            "amt_billed_prepaid":     round(bill_pre, 2),
            "cash_collected_pp":      round(cash_pp, 2),
            "cash_collected_prepaid": round(cash_pre, 2),
            "cash_collected":         round(cash_pp + cash_pre, 2),
            "service_charge":         round(sum(r.service_charge for r in mrows), 2),
            "meter_rental":           round(sum(r.meter_rental   for r in mrows), 2),
            "sc_mr_ratio":            round(sum(r.service_charge for r in mrows) / sum(r.meter_rental for r in mrows), 2) if sum(r.meter_rental for r in mrows) else 0,
            "total_sales":            round(sum(r.total_sales    for r in mrows), 2),

            # ── Debtors (stock) ────────────────────────────────────────
            "private_debtors":        round(sum(max(0, r.private_debtors) for r in lv), 2),
            "public_debtors":         round(sum(max(0, r.public_debtors)  for r in lv), 2),
            "total_debtors":          round(sum(max(0, r.total_debtors)   for r in lv), 2),
            "debtors_pct_billed":     round(sum(max(0, r.total_debtors) for r in lv) / (bill_pp + bill_pre) * 100, 1) if (bill_pp + bill_pre) else 0,

            # ── Breakdowns (flow) ──────────────────────────────────────
            "pipe_pvc":               round(sum(r.pipe_pvc       for r in mrows)),
            "pipe_gi":                round(sum(r.pipe_gi        for r in mrows)),
            "pipe_di":                round(sum(r.pipe_di        for r in mrows)),
            "pipe_hdpe_ac":           round(sum(r.pipe_hdpe_ac   for r in mrows)),
            "pipe_breakdowns":        round(sum(r.pipe_breakdowns for r in mrows)),
            "pump_breakdowns":        round(sum(r.pump_breakdowns for r in mrows)),

            # ── Pipelines extension (flow) ─────────────────────────────
            "dev_lines_32mm":         round(sum(r.dev_lines_32mm  for r in mrows)),
            "dev_lines_50mm":         round(sum(r.dev_lines_50mm  for r in mrows)),
            "dev_lines_63mm":         round(sum(r.dev_lines_63mm  for r in mrows)),
            "dev_lines_90mm":         round(sum(r.dev_lines_90mm  for r in mrows)),
            "dev_lines_110mm":        round(sum(r.dev_lines_110mm for r in mrows)),
            "dev_lines_total":        round(sum(r.dev_lines_total for r in mrows)),

            # ── Connectivity (avg across schemes) ─────────────────────
            "new_connections_pp":     round(max(0, sum(r.new_connections for r in mrows) - sum(r.prepaid_meters_installed for r in mrows))),
            "conn_applied":           round(sum(r.conn_applied       for r in mrows)),
            "days_to_quotation":      round(sum(r.days_to_quotation  for r in mrows)),
            "conn_fully_paid":        round(sum(r.conn_fully_paid    for r in mrows)),
            "days_to_connect":        round(sum(r.days_to_connect    for r in mrows)),
            "connectivity_rate":      round(sum(r.connectivity_rate  for r in mrows), 2),
            "queries_received":       round(sum(r.queries_received   for r in mrows)),
            "time_to_resolve":        round(sum(r.time_to_resolve    for r in mrows)),
            "response_time_avg":      round(sum(r.response_time_avg  for r in mrows) / max(len(mrows),1), 2),
        })

    return result
