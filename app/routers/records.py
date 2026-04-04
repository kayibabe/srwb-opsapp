"""
routers/records.py

CRUD + analytic endpoints for operational records.

GET  /api/records                — filtered list (zone/scheme/month/quarter)
GET  /api/records/{id}           — single record
POST /api/records                — create one record
PUT  /api/records/{id}           — full update
DELETE /api/records/{id}         — remove record
GET  /api/records/export/csv     — download filtered dataset as CSV
"""
from __future__ import annotations

import csv
import io
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_export
from app.database import Record, User, get_db
from app.schemas import RecordIn, RecordOut

router = APIRouter(prefix="/api/records", tags=["Records"])


# ── helpers ───────────────────────────────────────────────────
def _apply_filters(q, zones, schemes, months, quarters, year):
    if zones:
        q = q.filter(Record.zone.in_(zones))
    if schemes:
        q = q.filter(Record.scheme.in_(schemes))
    if months:
        q = q.filter(Record.month.in_(months))
    if quarters:
        q = q.filter(Record.quarter.in_(quarters))
    if year:
        q = q.filter(Record.year == year)
    return q


def _record_to_dict(r: Record) -> dict:
    return {c.name: getattr(r, c.name) for c in r.__table__.columns}


# ── GET filtered list ─────────────────────────────────────────
@router.get("/", response_model=List[RecordOut])
def list_records(
    zones:    Optional[str] = Query(None, description="Comma-separated zone names"),
    schemes:  Optional[str] = Query(None, description="Comma-separated scheme names"),
    months:   Optional[str] = Query(None, description="Comma-separated month names"),
    quarters: Optional[str] = Query(None, description="Comma-separated quarters e.g. Q1,Q2"),
    year:     Optional[int] = Query(None),
    skip:     int = Query(0, ge=0),
    limit:    int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    q = db.query(Record).order_by(Record.zone, Record.scheme, Record.month_no)
    q = _apply_filters(
        q,
        zones.split(",")    if zones    else None,
        schemes.split(",")  if schemes  else None,
        months.split(",")   if months   else None,
        quarters.split(",") if quarters else None,
        year,
    )
    return q.offset(skip).limit(limit).all()


# ── GET single ────────────────────────────────────────────────
@router.get("/{record_id}", response_model=RecordOut)
def get_record(record_id: int, db: Session = Depends(get_db)):
    r = db.query(Record).filter(Record.id == record_id).first()
    if not r:
        raise HTTPException(404, f"Record {record_id} not found")
    return r


# ── POST create ───────────────────────────────────────────────
@router.post("/", response_model=RecordOut, status_code=201)
def create_record(payload: RecordIn, db: Session = Depends(get_db)):
    # Prevent duplicate zone+scheme+month+year
    existing = (
        db.query(Record)
        .filter(
            Record.zone == payload.zone,
            Record.scheme == payload.scheme,
            Record.month == payload.month,
            Record.year == payload.year,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            409,
            f"Record already exists for {payload.zone}/{payload.scheme}/{payload.month}/{payload.year}. "
            "Use PUT to update.",
        )
    data = payload.model_dump(by_alias=False)
    r = Record(**data)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# ── PUT update ────────────────────────────────────────────────
@router.put("/{record_id}", response_model=RecordOut)
def update_record(record_id: int, payload: RecordIn, db: Session = Depends(get_db)):
    r = db.query(Record).filter(Record.id == record_id).first()
    if not r:
        raise HTTPException(404, f"Record {record_id} not found")
    for k, v in payload.model_dump(by_alias=False).items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


# ── DELETE ────────────────────────────────────────────────────
@router.delete("/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    r = db.query(Record).filter(Record.id == record_id).first()
    if not r:
        raise HTTPException(404, f"Record {record_id} not found")
    db.delete(r)
    db.commit()


# ── CSV export ────────────────────────────────────────────────
@router.get("/export/csv")
def export_csv(
    zones:    Optional[str] = Query(None),
    schemes:  Optional[str] = Query(None),
    months:   Optional[str] = Query(None),
    quarters: Optional[str] = Query(None),
    year:     Optional[int] = Query(None),
    _:        User          = Depends(require_export),   # viewers blocked
    db:       Session       = Depends(get_db),
):
    q = db.query(Record).order_by(Record.zone, Record.scheme, Record.month_no)
    q = _apply_filters(
        q,
        zones.split(",")    if zones    else None,
        schemes.split(",")  if schemes  else None,
        months.split(",")   if months   else None,
        quarters.split(",") if quarters else None,
        year,
    )
    rows = q.all()
    if not rows:
        raise HTTPException(404, "No records match the given filters")

    buf = io.StringIO()
    cols = [c.name for c in Record.__table__.columns]
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for r in rows:
        writer.writerow(_record_to_dict(r))

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SRWB_Export.csv"},
    )
