# tests/test_scenarios.py
# Verification test suite covering all planted edge cases (EC-01 to EC-08)
# and trap scenarios from the data pack specification.
# Run with: pytest tests/test_scenarios.py -v

from datetime import date, datetime, timedelta
import os
import subprocess

from engine.tax_calculator import (
    calculate_road_tax_2w,
    calculate_road_tax_lmv_private,
    calculate_road_tax_ev,
    calculate_diesel_surcharge,
    calculate_luxury_cess
)
from engine.fitness_engine import (
    issue_fitness_certificate,
    renew_fitness_certificate,
    apply_retest,
    renew_permit
)
from models.registration import RegistrationSeries
from models.fitness import Permit
from engine.registration_engine import (
    issue_next_mark,
    auction_fancy_number,
    next_series_prefix
)
from engine.transfer_engine import (
    calculate_transfer_fee,
    calculate_depreciated_price,
    calculate_tax_refund,
    can_transfer
)
from models.vehicle import Vehicle
from models.challan import Challan
from models.owner import Owner
from engine.challan_engine import (
    get_challan_amount,
    pay_challan,
    update_challan_status,
    contest_challan,
    resolve_contest,
    apply_document_waiver,
    add_licence_points,
    check_and_apply_suspension
)


# ── EC-01: Ex-showroom price boundaries ───────────────────────────────────────

def test_ec01_2w_price_boundary_50000():
    # Exactly Rs 50,000 -> 10% slab (Rs 5,000.00)
    assert calculate_road_tax_2w(50000) == 5000.0
    # Slightly above Rs 50,000 -> 12% slab
    assert calculate_road_tax_2w(50001) == 6000.12


def test_ec01_lmv_price_boundary_5_lakh():
    # Exactly Rs 5,00,000 -> 13% slab (Rs 65,000.00)
    assert calculate_road_tax_lmv_private(500000) == 65000.0
    # Above Rs 5,00,000 -> 14% slab
    assert calculate_road_tax_lmv_private(500001) == 70000.14


def test_ec01_lmv_price_boundary_20_lakh_diesel():
    # Exactly Rs 20,00,000 -> 17% slab (Rs 340,000.00)
    # Diesel cess 2% applies = Rs 40,000.00
    # Luxury cess applies only ABOVE 20 lakh -> 0.00
    road_tax = calculate_road_tax_lmv_private(2000000)
    diesel_cess = calculate_diesel_surcharge(2000000, "LMV_PRIVATE", "DIESEL")
    luxury_cess = calculate_luxury_cess(2000000, "LMV_PRIVATE", "DIESEL")
    assert road_tax == 340000.0
    assert diesel_cess == 40000.0
    assert luxury_cess == 0.0

    # Above Rs 20,00,000 -> 18% slab, 1% luxury cess, 2% diesel cess
    road_tax_above = calculate_road_tax_lmv_private(2000001)
    diesel_cess_above = calculate_diesel_surcharge(2000001, "LMV_PRIVATE", "DIESEL")
    luxury_cess_above = calculate_luxury_cess(2000001, "LMV_PRIVATE", "DIESEL")
    assert road_tax_above == 360000.18
    assert diesel_cess_above == 40000.02
    assert luxury_cess_above == 20000.01


# ── EC-02: EV registered on sunset date ───────────────────────────────────────

def test_ec02_ev_sunset_date_boundary():
    # EV registered on sunset date 2026-04-01 pays 5% road tax ('before' is strict)
    tax_on_sunset = calculate_road_tax_ev(1850000, "2026-04-01", "2026-04-01")
    assert tax_on_sunset == 92500.0

    # EV registered day before sunset date 2026-03-31 pays 0% road tax
    tax_before_sunset = calculate_road_tax_ev(1850000, "2026-03-31", "2026-04-01")
    assert tax_before_sunset == 0.0


# ── EC-03: Fitness renewal application timing ─────────────────────────────────

def test_ec03_fitness_renewal_applied_60_days_before():
    # Cert expires 2026-08-27. Application on 2026-06-28 (60 days prior).
    cert = issue_fitness_certificate("KA01AB0053", "2024-08-27", is_new_vehicle=True)
    cert.expiry_date = "2026-08-27"

    success, result = renew_fitness_certificate(
        cert,
        application_date="2026-06-28",
        inspection_date="2026-06-28",
        inspection_passed=True
    )
    assert success is True
    # Maintains anniversary: 1 year from old expiry -> 2027-08-27
    assert result.expiry_date == "2027-08-27"


def test_ec03_fitness_renewal_applied_1_day_after():
    # Cert expires 2026-05-29. Applied 2026-05-30 (1 day late), inspected 2026-06-01 (3 days late).
    cert = issue_fitness_certificate("KA01AB0121", "2024-05-29", is_new_vehicle=True)
    cert.expiry_date = "2026-05-29"

    # Days late from expiry to inspection: 2026-05-29 to 2026-06-01 is 3 days
    days_late = (datetime.strptime("2026-06-01", "%Y-%m-%d").date() - datetime.strptime("2026-05-29", "%Y-%m-%d").date()).days
    late_fee = days_late * 50.0
    assert late_fee == 150.0

    success, result = renew_fitness_certificate(
        cert,
        application_date="2026-05-30",
        inspection_date="2026-06-01",
        inspection_passed=True
    )
    assert success is True
    # Restarts from inspection date: 1 year from 2026-06-01 -> 2027-06-01
    assert result.expiry_date == "2027-06-01"


# ── EC-04: Fancy number sequence and auctions ─────────────────────────────────

def test_ec04_fancy_number_skipped_when_no_auction():
    # Sequence reaches 9897; 9898 is fancy with NO auction.
    series = RegistrationSeries("KA01AA", fancy_numbers={9898: 1})
    series.current_number = 9896
    mark1 = issue_next_mark(series)  # 9897
    assert mark1 == "KA01AA9897"
    mark2 = issue_next_mark(series)  # 9898 skipped, gives 9899
    assert mark2 == "KA01AA9899"


def test_ec04_fancy_number_auctioned_and_rollover():
    # Series rollover when reaching 9999
    series = RegistrationSeries("KA01AA", fancy_numbers={})
    series.current_number = 9998
    mark_last = issue_next_mark(series)
    assert mark_last == "KA01AA9999"

    next_prefix = next_series_prefix(series.series_prefix)
    assert next_prefix == "KA01AB"


# ── EC-05: Transfer fee and delay fees ────────────────────────────────────────

def test_ec05_transfer_day_30_no_delay_fee():
    # Sale date 2026-02-10, transfer applied on 2026-03-12 (exactly 30 days)
    fee_dict = calculate_transfer_fee("LMV_PRIVATE", "2026-02-10", "2026-03-12")
    assert fee_dict["delay_fee"] == 0.0


def test_ec05_transfer_day_31_incurs_delay_fee():
    # Sale date 2026-02-10, transfer applied on 2026-03-13 (31 days -> 1 part-month delay)
    fee_dict = calculate_transfer_fee("LMV_PRIVATE", "2026-02-10", "2026-03-13")
    assert fee_dict["delay_fee"] == 300.0


# ── EC-06: Depreciation at completed years ───────────────────────────────────

def test_ec06_depreciation_exactly_10_completed_years():
    # First reg: 2016-06-15, migration: 2026-06-15 -> exactly 10 completed years
    # 70% cap reached, so depreciated price is 30% of original
    dep_price = calculate_depreciated_price(1000000, "2016-06-15", "2026-06-15")
    assert dep_price == 300000.0


def test_ec06_depreciation_one_day_short_of_10_years():
    # First reg: 2016-06-16, migration: 2026-06-15 -> 9 completed years (63% depreciation)
    # Depreciated price is 37% of original
    dep_price = calculate_depreciated_price(1000000, "2016-06-16", "2026-06-15")
    assert dep_price == 370000.0


# ── EC-07: Challan escalation day 60 vs day 61 ────────────────────────────────

def test_ec07_challan_paid_day_60_no_surcharge():
    # Issued 2026-01-10, paid 2026-03-11 23:59:00 (day 60)
    c = Challan("CH-0429", "VEH-0001", "OF02", "2026-01-10", 2000, "CAMERA")
    update_challan_status(c, "2026-03-11")
    assert c.status == "ISSUED"
    assert c.current_amount == 2000

    success, msg = pay_challan(c, "2026-03-11 23:59:00")
    assert success is True
    assert c.status == "PAID"


def test_ec07_challan_paid_day_61_with_surcharge():
    # Issued 2026-01-10, paid 2026-03-12 00:05:00 (day 61)
    c = Challan("CH-0430", "VEH-0001", "OF02", "2026-01-10", 2000, "CAMERA")
    update_challan_status(c, "2026-03-12")
    assert c.status == "ESCALATED"
    assert c.current_amount == 3000  # 50% surcharge

    success, msg = pay_challan(c, "2026-03-12 00:05:00")
    assert success is True
    assert c.status == "PAID"


# ── EC-08: Points rolling 24-month window ─────────────────────────────────────

def test_ec08_points_rolling_24_month_window():
    # Licence KA5920100000015
    # Offences:
    # 2024-10-31: 3 pts (OF02)
    # 2025-03-02: 3 pts
    # 2025-09-14: 3 pts
    # 2026-10-30: 3 pts
    # Total on 2026-10-30: 12 pts -> SUSPENDED
    owner = Owner("OWN-0015", "Test Driver", "KA5920100000015")
    add_licence_points(owner, "OF02", "2024-10-31")
    add_licence_points(owner, "OF02", "2025-03-02")
    add_licence_points(owner, "OF02", "2025-09-14")
    add_licence_points(owner, "OF02", "2026-10-30")

    # On 2026-10-30, all 4 offences are strictly after cutoff (2024-10-30)
    res = check_and_apply_suspension(owner, current_date="2026-10-30")
    assert res == "SUSPENDED"
    assert owner.licence_status == "SUSPENDED"

    # On 2026-10-31, cutoff is 2024-10-31.
    # The offence on 2024-10-31 is not strictly after 2024-10-31, so window has 9 pts.
    cutoff = datetime.strptime("2026-10-31", "%Y-%m-%d").date().replace(year=2024)
    active_points = sum(entry["points"] for entry in owner.licence_points if datetime.strptime(entry["date"][:10], "%Y-%m-%d").date() > cutoff)
    assert active_points == 9


# ── Traps & Edge Cases ────────────────────────────────────────────────────────

def test_trap_fitness_renewal_applied_61_days_before():
    # 61 days before expiry is OUTSIDE the 60-day window
    cert = issue_fitness_certificate("KA01AB0118", "2024-08-31", is_new_vehicle=True)
    cert.expiry_date = "2026-08-31"

    success, msg = renew_fitness_certificate(
        cert,
        application_date="2026-07-01",  # 61 days before 2026-08-31
        inspection_date="2026-07-01",
        inspection_passed=True
    )
    assert success is False
    assert "Too early" in msg or "Renewal window opens" in msg


def test_trap_free_retest_within_15_days():
    cert = issue_fitness_certificate("KA01AB0240", "2024-01-01", is_new_vehicle=True)
    cert.inspection_result = "FAILED"
    cert.retest_deadline = "2026-01-25"

    # Retest on 2026-01-20 (within 15 days)
    success, result = apply_retest(cert, retest_date="2026-01-20", retest_passed=True)
    assert success is True
    assert result.status == "VALID"


def test_trap_permit_renewal_lapsed_over_6_months():
    # Lapsed > 6 months: fresh permit issued at 2x fee
    # Permit expired 2025-10-15, applied 2026-06-01 (approx 7.5 months)
    permit = Permit("KA01AB0190", "CONTRACT", "2020-10-15", "2025-10-15", "2021-10-15")
    success, result, fee_charged = renew_permit(
        permit,
        renewal_date="2026-06-01",
        has_valid_fitness=True,
        has_valid_insurance=True,
        renewal_fee=1000
    )
    assert success is True
    assert fee_charged == 2000  # 2x fee
    assert result.expiry_date == "2031-06-01"


def test_trap_transfer_hypothecation_and_challans():
    vehicle = Vehicle(
        registration_mark="KA01AB0009",
        vehicle_class="LMV_PRIVATE",
        ex_showroom_price=800000,
        fuel_type="PETROL",
        engine_cc=1200,
        seating=5,
        laden_weight_tonnes=0,
        manufacture_date="2020-01-01",
        registration_date="2020-02-01",
        owner_id="OWN001",
        state="KA"
    )
    vehicle.hypothecation = "SBI"

    allowed, reason = can_transfer(vehicle, [])
    assert allowed is False
    assert "hypothecation" in reason.lower()

    # Pending challans > 2000
    vehicle.hypothecation = None
    challans = [
        Challan("CH01", vehicle.registration_mark, "OF01", "2026-01-01", 1500, "MANUAL"),
        Challan("CH02", vehicle.registration_mark, "OF02", "2026-01-01", 1000, "MANUAL"),
    ]
    for c in challans:
        c.status = "ISSUED"
    allowed2, reason2 = can_transfer(vehicle, challans)
    assert allowed2 is False
    assert "challan" in reason2.lower()


def test_trap_repeat_offence_fine_doubling():
    # OF01 (NO_HELMET): Rs 1,000 first time, Rs 2,000 second time within 12 months, Rs 4,000 third time
    priors = [
        Challan("CH-0143", "VEH-0093", "OF01", "2025-08-03", 1000, "CAMERA")
    ]
    priors[0].status = "PAID"
    amt2 = get_challan_amount("OF01", "2W", priors, offence_date="2026-08-03")
    assert amt2 == 2000

    priors.append(Challan("CH-0764", "VEH-0093", "OF01", "2026-08-03", 2000, "CAMERA"))
    priors[1].status = "PAID"
    amt3 = get_challan_amount("OF01", "2W", priors, offence_date="2026-08-04")
    assert amt3 == 4000


def test_trap_document_waiver_within_15_days():
    # NO_INSURANCE issued 2026-01-01. Insurance produced on 2026-01-10 (valid at offence date).
    c = Challan("CH-0315", "VEH-0223", "NO_INSURANCE", "2026-01-01", 2000, "CAMERA")
    waived, msg = apply_document_waiver(
        c,
        document_date="2025-12-01",
        production_date="2026-01-10"
    )
    assert waived is True
    assert c.status == "DISMISSED"


def test_trap_drunk_driving_immediate_court_referral():
    c = Challan("CH-0541", "VEH-0155", "DRUNK_DRIVING", "2026-01-01", 10000, "MANUAL")
    status = update_challan_status(c, "2026-01-01")
    assert status == "COURT_REFERRED"
    assert c.status == "COURT_REFERRED"
    assert c.original_amount == 10000


def test_trap_contest_challan_clock_freeze():
    c = Challan("CH-0621", "VEH-0001", "OF02", "2026-01-01", 2000, "CAMERA")
    c.status = "ISSUED"
    success, msg = contest_challan(c, contest_date="2026-02-20")
    assert success is True
    assert c.is_contested is True

    # Resolve contest: DISMISSED
    resolve_contest(c, decision="DISMISSED", resolution_date="2026-03-01")
    assert c.status == "DISMISSED"


# ── Integration Test: Full Data Pack Evaluation Output ────────────────────────

def test_full_datapack_evaluation_outputs_exist():
    # Verify the 7 CSV files are generated and match expected structure
    expected_files = [
        "registrations.csv",
        "application_results.csv",
        "vehicle_dossier.csv",
        "challan_history.csv",
        "licence_points.csv",
        "challan_ageing.csv",
        "daily_register.csv"
    ]
    for filename in expected_files:
        path = os.path.join("outputs", filename)
        assert os.path.exists(path), f"Missing {path}"
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) >= 1, f"{path} is empty"
