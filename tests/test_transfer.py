# tests/test_transfer.py
# Run with: pytest tests/test_transfer.py -v

from models.vehicle import Vehicle
from models.challan import Challan
from models.transfer import NOC
from engine.transfer_engine import (
    can_transfer,
    calculate_transfer_fee,
    process_transfer,
    terminate_hypothecation,
    calculate_depreciated_price,
    calculate_tax_refund,
    issue_noc,
    confirm_noc_utilisation
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_vehicle(vehicle_class="LMV_PRIVATE", hypothecation=None,
                 status="ACTIVE"):
    v = Vehicle(
        registration_mark  = "KA01AB0001",
        vehicle_class      = vehicle_class,
        ex_showroom_price  = 800000,
        fuel_type          = "PETROL",
        engine_cc          = 1200,
        seating            = 5,
        laden_weight_tonnes = 0,
        manufacture_date   = "2020-01-01",
        registration_date  = "2020-02-01",
        owner_id           = "OWN001",
        state              = "KA"
    )
    v.hypothecation = hypothecation
    v.status        = status
    return v

def make_challan(status="ISSUED", amount=1000, offence_code="NO_HELMET"):
    c = Challan(
        challan_id   = "CHL001",
        vehicle_id   = "KA01AB0001",
        offence_code = offence_code,
        offence_date = "2024-01-01",
        amount       = amount,
        evidence_flag = "MANUAL"
    )
    c.status         = status
    c.current_amount = amount
    return c


# ── BR-09: Transfer eligibility ───────────────────────────────────────────────

def test_transfer_allowed_no_issues():
    vehicle = make_vehicle()
    allowed, reason = can_transfer(vehicle, challans=[])
    assert allowed is True

def test_transfer_blocked_under_hypothecation():
    vehicle = make_vehicle(hypothecation="HDFC Bank")
    allowed, reason = can_transfer(vehicle, challans=[])
    assert allowed is False
    assert "hypothecation" in reason.lower()

def test_transfer_blocked_vehicle_blocked():
    vehicle = make_vehicle(status="BLOCKED")
    allowed, reason = can_transfer(vehicle, challans=[])
    assert allowed is False

def test_transfer_blocked_high_pending_challans():
    vehicle  = make_vehicle()
    challans = [make_challan(status="ISSUED", amount=2500)]
    allowed, reason = can_transfer(vehicle, challans=challans)
    assert allowed is False

def test_transfer_allowed_pending_challans_below_limit():
    # Total pending = Rs 1,500 — under the Rs 2,000 threshold
    vehicle  = make_vehicle()
    challans = [make_challan(status="ISSUED", amount=1500)]
    allowed, reason = can_transfer(vehicle, challans=challans)
    assert allowed is True


# ── BR-09: Transfer fee calculation ──────────────────────────────────────────

def test_transfer_fee_within_30_days_no_delay():
    result = calculate_transfer_fee("LMV_PRIVATE", "2024-01-01", "2024-01-20")
    assert result["base_fee"]   == 500
    assert result["delay_fee"]  == 0
    assert result["total_fee"]  == 500

def test_transfer_fee_exactly_day_30_no_delay():
    # EC-08: exactly day 30 → no delay fee (rule says MORE than 30 days)
    result = calculate_transfer_fee("LMV_PRIVATE", "2024-01-01", "2024-01-31")
    assert result["delay_fee"] == 0
    assert result["total_fee"] == 500

def test_transfer_fee_day_31_first_delay_month():
    # Day 31 → 1 month of delay → Rs 300 extra
    result = calculate_transfer_fee("LMV_PRIVATE", "2024-01-01", "2024-02-01")
    assert result["delay_months"] == 1
    assert result["delay_fee"]    == 300
    assert result["total_fee"]    == 800

def test_transfer_fee_2w_lower_base():
    result = calculate_transfer_fee("2W", "2024-01-01", "2024-01-10")
    assert result["base_fee"]  == 150
    assert result["total_fee"] == 150


# ── BR-09: Hypothecation ──────────────────────────────────────────────────────

def test_hypothecation_terminated_with_noc():
    vehicle = make_vehicle(hypothecation="HDFC Bank")
    success, msg = terminate_hypothecation(vehicle, financier_noc_received=True)
    assert success is True
    assert vehicle.hypothecation is None

def test_hypothecation_not_terminated_without_noc():
    vehicle = make_vehicle(hypothecation="HDFC Bank")
    success, msg = terminate_hypothecation(vehicle, financier_noc_received=False)
    assert success is False
    assert vehicle.hypothecation == "HDFC Bank"

def test_hypothecation_termination_fails_if_none():
    vehicle = make_vehicle(hypothecation=None)
    success, msg = terminate_hypothecation(vehicle, financier_noc_received=True)
    assert success is False


# ── BR-10: Depreciation ───────────────────────────────────────────────────────

def test_depreciation_after_3_years():
    # 3 years × 7% = 21% depreciation → 79% of original
    price = calculate_depreciated_price(1000000, "2020-01-01", "2023-01-15")
    assert price == 790000.0

def test_depreciation_capped_at_10_years():
    # EC-09: 10 completed years × 7% = 70% — cap exactly reached
    # Depreciated price = 30% of original
    price = calculate_depreciated_price(1000000, "2014-01-01", "2024-01-15")
    assert price == 300000.0

def test_depreciation_capped_beyond_10_years():
    # 12 years would be 84% — but capped at 70%
    price = calculate_depreciated_price(1000000, "2010-01-01", "2024-01-15")
    assert price == 300000.0


# ── BR-10: Tax refund ────────────────────────────────────────────────────────

def test_tax_refund_after_3_years():
    # Paid Rs 1,00,000 tax. After 3 years, 12 of 15 years remain.
    # Refund = 1,00,000 × 12/15 = Rs 80,000
    refund = calculate_tax_refund(100000, "2020-01-01", "2023-01-15")
    assert refund == 80000

def test_tax_refund_zero_after_15_years():
    # Vehicle older than 15 years — no refund
    refund = calculate_tax_refund(100000, "2005-01-01", "2024-01-15")
    assert refund == 0

def test_tax_refund_rounded_down():
    # Refund that would be a decimal — must be rounded DOWN
    # Paid Rs 1,00,001. After 1 year, 14/15 remain.
    # Refund = 1,00,001 × 14/15 = 93,334.26... → Rs 93,334
    refund = calculate_tax_refund(100001, "2023-01-01", "2024-01-15")
    assert refund == 93334


# ── BR-10: NOC ───────────────────────────────────────────────────────────────

def test_noc_issued_with_no_pending_challans():
    vehicle = make_vehicle()
    success, noc = issue_noc(
        noc_id                 = "NOC001",
        vehicle                = vehicle,
        challans               = [],
        road_tax_paid          = 100000,
        first_registration_date = "2020-01-01",
        noc_date               = "2024-01-01"
    )
    assert success is True
    assert noc.status == "ISSUED"

def test_noc_blocked_with_pending_challan():
    vehicle  = make_vehicle()
    challans = [make_challan(status="ISSUED")]
    success, reason = issue_noc(
        noc_id                 = "NOC001",
        vehicle                = vehicle,
        challans               = challans,
        road_tax_paid          = 100000,
        first_registration_date = "2020-01-01",
        noc_date               = "2024-01-01"
    )
    assert success is False

def test_noc_refund_released_within_12_months():
    noc = NOC("NOC001", "KA01AB0001", "2024-01-01", 100000, 80000)
    success, amount = confirm_noc_utilisation(noc, "2024-12-31")
    assert success is True
    assert amount == 80000

def test_noc_refund_released_on_exactly_day_365():
    # EC-13: exactly day 365 → refund is released
    noc = NOC("NOC001", "KA01AB0001", "2024-01-01", 100000, 80000)
    success, amount = confirm_noc_utilisation(noc, "2024-12-31")
    assert success is True

def test_noc_refund_not_released_after_12_months():
    noc = NOC("NOC001", "KA01AB0001", "2024-01-01", 100000, 80000)
    success, msg = confirm_noc_utilisation(noc, "2025-02-01")
    assert success is False
    assert noc.refund_released is False