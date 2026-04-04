"""
database.py — Full schema matching RawData.xlsx DataEntry sheet (222 cols),
              plus the User model for role-based authentication.
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    Boolean, DateTime, Index, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'srwb.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Record(Base):
    __tablename__ = "records"
    id                       = Column(Integer, primary_key=True, autoincrement=True)
    # Identity
    zone                     = Column(String(60), nullable=False, index=True)
    scheme                   = Column(String(80), nullable=False, index=True)
    fiscal_year              = Column(String(12), nullable=True)
    year                     = Column(Integer,    nullable=False)
    month_no                 = Column(Integer,    nullable=False)
    month                    = Column(String(20), nullable=False, index=True)
    quarter                  = Column(String(4),  nullable=False)
    # Water production & NRW
    vol_produced             = Column(Float, default=0.0)
    vol_billed_indiv_pp      = Column(Float, default=0.0)
    vol_billed_cwp_pp        = Column(Float, default=0.0)
    vol_billed_inst_pp       = Column(Float, default=0.0)
    vol_billed_comm_pp       = Column(Float, default=0.0)
    total_vol_billed_pp      = Column(Float, default=0.0)
    vol_billed_indiv_prepaid = Column(Float, default=0.0)
    vol_billed_cwp_prepaid   = Column(Float, default=0.0)
    vol_billed_inst_prepaid  = Column(Float, default=0.0)
    vol_billed_comm_prepaid  = Column(Float, default=0.0)
    total_vol_billed_prepaid = Column(Float, default=0.0)
    revenue_water            = Column(Float, default=0.0)
    nrw                      = Column(Float, default=0.0)
    pct_nrw                  = Column(Float, default=0.0)
    # Chemicals
    chlorine_kg              = Column(Float, default=0.0)
    alum_kg                  = Column(Float, default=0.0)
    soda_ash_kg              = Column(Float, default=0.0)
    algae_floc_litres        = Column(Float, default=0.0)
    sud_floc_litres          = Column(Float, default=0.0)
    kmno4_kg                 = Column(Float, default=0.0)
    chem_cost                = Column(Float, default=0.0)
    chem_cost_per_m3         = Column(Float, default=0.0)
    # Power
    power_kwh                = Column(Float, default=0.0)
    power_cost               = Column(Float, default=0.0)
    power_cost_per_m3        = Column(Float, default=0.0)
    # Transport & ops
    distances_km             = Column(Float, default=0.0)
    fuel_used_litres         = Column(Float, default=0.0)
    fuel_cost                = Column(Float, default=0.0)
    maintenance              = Column(Float, default=0.0)
    staff_costs              = Column(Float, default=0.0)
    wages                    = Column(Float, default=0.0)
    other_overhead           = Column(Float, default=0.0)
    op_cost                  = Column(Float, default=0.0)
    op_cost_per_m3_produced  = Column(Float, default=0.0)
    op_cost_per_m3_billed    = Column(Float, default=0.0)
    # Staffing
    perm_staff               = Column(Float, default=0.0)
    temp_staff               = Column(Float, default=0.0)
    # Connections aggregated
    all_conn_bfwd            = Column(Float, default=0.0)
    all_conn_applied         = Column(Float, default=0.0)
    new_connections          = Column(Float, default=0.0)
    all_conn_cfwd            = Column(Float, default=0.0)
    prepaid_meters_installed = Column(Float, default=0.0)
    # Disconnections
    disconnected_individual  = Column(Float, default=0.0)
    disconnected_inst        = Column(Float, default=0.0)
    disconnected_commercial  = Column(Float, default=0.0)
    disconnected_cwp         = Column(Float, default=0.0)
    total_disconnected       = Column(Float, default=0.0)
    # Active consumers — postpaid
    active_post_individual   = Column(Float, default=0.0)
    active_post_inst         = Column(Float, default=0.0)
    active_post_commercial   = Column(Float, default=0.0)
    active_post_cwp          = Column(Float, default=0.0)
    active_postpaid          = Column(Float, default=0.0)
    # Active consumers — prepaid
    active_prep_individual   = Column(Float, default=0.0)
    active_prep_inst         = Column(Float, default=0.0)
    active_prep_commercial   = Column(Float, default=0.0)
    active_prep_cwp          = Column(Float, default=0.0)
    active_prepaid           = Column(Float, default=0.0)
    # Active totals
    active_customers         = Column(Float, default=0.0)
    total_metered            = Column(Float, default=0.0)
    # Population
    pop_supply_area          = Column(Float, default=0.0)
    pop_supplied             = Column(Float, default=0.0)
    pct_pop_supplied         = Column(Float, default=0.0)
    # Stuck meters aggregated
    stuck_meters             = Column(Float, default=0.0)
    stuck_new                = Column(Float, default=0.0)
    stuck_repaired           = Column(Float, default=0.0)
    stuck_replaced           = Column(Float, default=0.0)
    # Pipe breakdowns
    pipe_pvc                 = Column(Float, default=0.0)
    pipe_gi                  = Column(Float, default=0.0)
    pipe_di                  = Column(Float, default=0.0)
    pipe_hdpe_ac             = Column(Float, default=0.0)
    pipe_breakdowns          = Column(Float, default=0.0)
    # Pumps & supply hours
    pump_breakdowns          = Column(Float, default=0.0)
    pump_hours_lost          = Column(Float, default=0.0)
    supply_hours             = Column(Float, default=0.0)
    power_fail_hours         = Column(Float, default=0.0)
    # Development lines
    dev_lines_32mm           = Column(Float, default=0.0)
    dev_lines_50mm           = Column(Float, default=0.0)
    dev_lines_63mm           = Column(Float, default=0.0)
    dev_lines_90mm           = Column(Float, default=0.0)
    dev_lines_110mm          = Column(Float, default=0.0)
    dev_lines_total          = Column(Float, default=0.0)
    # Cash collected
    cash_coll_pp             = Column(Float, default=0.0)
    cash_coll_prepaid        = Column(Float, default=0.0)
    cash_collected           = Column(Float, default=0.0)
    # Amounts billed
    amt_billed_pp            = Column(Float, default=0.0)
    amt_billed_prepaid       = Column(Float, default=0.0)
    amt_billed               = Column(Float, default=0.0)
    # Charges
    service_charge           = Column(Float, default=0.0)
    meter_rental             = Column(Float, default=0.0)
    total_sales              = Column(Float, default=0.0)
    # Debtors
    private_debtors          = Column(Float, default=0.0)
    public_debtors           = Column(Float, default=0.0)
    total_debtors            = Column(Float, default=0.0)
    # Financial KPIs
    op_cost_per_sales        = Column(Float, default=0.0)
    collection_rate          = Column(Float, default=0.0)
    collection_per_sales     = Column(Float, default=0.0)
    # Connection performance
    conn_applied             = Column(Float, default=0.0)
    days_to_quotation        = Column(Float, default=0.0)
    conn_fully_paid          = Column(Float, default=0.0)
    days_to_connect          = Column(Float, default=0.0)
    connectivity_rate        = Column(Float, default=0.0)
    # Query performance
    queries_received         = Column(Float, default=0.0)
    time_to_resolve          = Column(Float, default=0.0)
    response_time_avg        = Column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint(
            "zone", "scheme", "month", "year",
            name="uq_zone_scheme_month_year",
        ),
        Index("ix_zone_scheme_month_year", "zone", "scheme", "month", "year"),
    )

# ── User model (authentication & RBAC) ───────────────────────
class User(Base):
    """
    Application user for role-based access control.

    Roles:
      admin   — full access: view, export, upload Excel, manage users
      user    — view + export CSV; no upload; no user management
      viewer  — read-only; no export; no upload; no user management
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(60), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    role          = Column(String(20), nullable=False, default="user")
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    created_by    = Column(String(60), nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)

def recreate_tables():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
