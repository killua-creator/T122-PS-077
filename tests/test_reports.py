# Smoke tests — just check reports run without errors
# and contain the right key information.
# Run with: pytest tests/test_reports.py -v

from models.vehicle import Vehicle
from models.owner import Owner
from models.challan import Challan
from engine.report_engine import (
    generate_vehicle_dossier,
    generate_daily_register,
    generate_challan_ageing_report
)


def make_vehicle():
    v = Vehicle(
        registration_mark   = "KA01AB0001",
        vehicle_class       = "LMV_PRIVATE",
        ex_showroom_price   = 800000,
        fuel_type           = "PETROL",
        engine_cc           = 1200,
        seating             = 5,
        laden_weight_tonnes = 0,
        manufacture_date    = "2020-01-01",
        registration_date   = "2024-01-15",
        owner_id            = "OWN001",
        state               = "KA"
    )
    v.road_tax_paid = 112000
    v.cess_paid     = 0
    return v

def make_owner():
    return Owner("OWN001", "Ravi Kumar", "KA0120230012345")

def make_challan(status="ISSUED", days_old=10):
    from datetime import date, timedelta
    offence_date = str(date.today() - timedelta(days=days_old))
    c = Challan(
        challan_id    = "CHL001",
        vehicle_id    = "KA01AB0001",
        offence_code  = "NO_HELMET",
        offence_date  = offence_date,
        amount        = 1000,
        evidence_flag = "MANUAL"
    )
    c.status         = status
    c.current_amount = 1000
    return c


# ── Vehicle dossier ───────────────────────────────────────────────────────────

def test_dossier_contains_registration_mark():
    vehicle = make_vehicle()
    owner   = make_owner()
    report  = generate_vehicle_dossier(
        vehicle, owner,
        challans     = [],
        fitness_cert = None,
        permit       = None,
        current_date = "2024-06-01"
    )
    assert "KA01AB0001" in report

def test_dossier_contains_owner_name():
    vehicle = make_vehicle()
    owner   = make_owner()
    report  = generate_vehicle_dossier(
        vehicle, owner,
        challans     = [],
        fitness_cert = None,
        permit       = None,
        current_date = "2024-06-01"
    )
    assert "Ravi Kumar" in report

def test_dossier_shows_challan_history():
    vehicle  = make_vehicle()
    owner    = make_owner()
    challan  = make_challan(status="ISSUED", days_old=10)
    report   = generate_vehicle_dossier(
        vehicle, owner,
        challans     = [challan],
        fitness_cert = None,
        permit       = None,
        current_date = "2024-06-01"
    )
    assert "CHL001" in report
    assert "NO_HELMET" in report


# ── Daily register ────────────────────────────────────────────────────────────

def test_daily_register_finds_vehicle_on_date():
    vehicle      = make_vehicle()   # registered "2024-01-15"
    all_vehicles = {"KA01AB0001": vehicle}
    report       = generate_daily_register(all_vehicles, "2024-01-15")
    assert "KA01AB0001" in report

def test_daily_register_empty_on_wrong_date():
    vehicle      = make_vehicle()   # registered "2024-01-15"
    all_vehicles = {"KA01AB0001": vehicle}
    report       = generate_daily_register(all_vehicles, "2024-02-01")
    assert "No vehicles registered on this date" in report


# ── Challan ageing report ─────────────────────────────────────────────────────

def test_ageing_report_current_bucket():
    challan = make_challan(status="ISSUED", days_old=10)
    from datetime import date
    report  = generate_challan_ageing_report([challan], str(date.today()))
    assert "0–30 days" in report
    assert "CHL001" in report

def test_ageing_report_no_unpaid_challans():
    challan = make_challan(status="PAID", days_old=10)
    from datetime import date
    report  = generate_challan_ageing_report([challan], str(date.today()))
    assert "No unpaid challans" in report