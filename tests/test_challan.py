# Run with: pytest tests/test_challan.py -v

from datetime import date, timedelta
from models.challan import Challan
from models.owner import Owner
from engine.challan_engine import (
    get_challan_amount,
    get_effective_days,
    pay_challan,
    update_challan_status,
    contest_challan,
    resolve_contest,
    apply_document_waiver,
    add_licence_points,
    check_and_apply_suspension
)


# ── Helpers to create test objects quickly ────────────────────────────────────

def make_challan(challan_id="CHL001", offence_code="NO_HELMET",
                 offence_date="2024-01-01", vehicle_class="LMV_PRIVATE"):
    amount = get_challan_amount(offence_code, vehicle_class, prior_challans=[])
    return Challan(
        challan_id=challan_id,
        vehicle_id="KA01AB0001",
        offence_code=offence_code,
        offence_date=offence_date,
        amount=amount,
        evidence_flag="MANUAL"
    )

def make_owner():
    return Owner("OWN001", "Ravi Kumar", "KA0120230012345")


# ── BR-11: Challan amounts ────────────────────────────────────────────────────

def test_no_helmet_amount():
    amount = get_challan_amount("NO_HELMET", "2W", prior_challans=[])
    assert amount == 1000

def test_speeding_lmv_amount():
    amount = get_challan_amount("SPEEDING", "LMV_PRIVATE", prior_challans=[])
    assert amount == 1000

def test_speeding_hgv_amount():
    amount = get_challan_amount("SPEEDING", "HGV", prior_challans=[])
    assert amount == 2000

def test_drunk_driving_amount():
    amount = get_challan_amount("DRUNK_DRIVING", "LMV_PRIVATE", prior_challans=[])
    assert amount == 10000

def test_no_insurance_first_offence():
    amount = get_challan_amount("NO_INSURANCE", "LMV_PRIVATE", prior_challans=[])
    assert amount == 2000

def test_no_insurance_repeat_offence_fixed_amount():
    # Repeat NO_INSURANCE has a fixed amount of Rs 4,000 (not doubled from 2,000)
    recent_date = str(date.today() - timedelta(days=30))
    prior = [make_challan(offence_code="NO_INSURANCE", offence_date=recent_date)]
    amount = get_challan_amount("NO_INSURANCE", "LMV_PRIVATE", prior_challans=prior)
    assert amount == 4000

def test_repeat_offence_doubles_amount():
    recent_date = str(date.today() - timedelta(days=30))
    prior = [make_challan(offence_code="RED_LIGHT", offence_date=recent_date)]
    amount = get_challan_amount("RED_LIGHT", "LMV_PRIVATE", prior_challans=prior)
    assert amount == 2000   # 1000 × 2

def test_repeat_offence_capped_at_10000():
    # SPEEDING OTHER is Rs 2,000. Doubled = Rs 4,000. Under cap.
    # DRUNK_DRIVING is Rs 10,000. Doubled = Rs 20,000. Capped at Rs 10,000.
    recent_date = str(date.today() - timedelta(days=30))
    prior = [make_challan(offence_code="DRUNK_DRIVING", offence_date=recent_date)]
    amount = get_challan_amount("DRUNK_DRIVING", "LMV_PRIVATE", prior_challans=prior)
    assert amount == 10000   # capped


# ── BR-12: Challan lifecycle ──────────────────────────────────────────────────

def test_challan_starts_as_issued():
    c = make_challan()
    assert c.status == "ISSUED"

def test_challan_paid_within_60_days():
    c = make_challan(offence_date="2024-01-01")
    success, msg = pay_challan(c, payment_date="2024-02-15")
    assert success is True
    assert c.status == "PAID"

def test_challan_escalates_after_60_days():
    c = make_challan(offence_date="2024-01-01")
    # Day 61 — should escalate
    status = update_challan_status(c, current_date="2024-03-02")
    assert status == "ESCALATED"
    assert c.current_amount == 1500   # 1000 + 50% surcharge

def test_challan_not_escalated_on_day_60():
    # EC-10: day 60 exactly — still ISSUED, not ESCALATED
    c = make_challan(offence_date="2024-01-01")
    status = update_challan_status(c, current_date="2024-03-01")
    assert status == "ISSUED"

def test_challan_court_referred_after_90_days():
    c = make_challan(offence_date="2024-01-01")
    status = update_challan_status(c, current_date="2024-04-01")
    assert status == "COURT_REFERRED"

def test_drunk_driving_immediately_court_referred():
    c = make_challan(offence_code="DRUNK_DRIVING", offence_date="2024-01-01")
    status = update_challan_status(c, current_date="2024-01-01")
    assert status == "COURT_REFERRED"

def test_drunk_driving_cannot_be_paid():
    c = make_challan(offence_code="DRUNK_DRIVING")
    success, msg = pay_challan(c, payment_date="2024-01-05")
    assert success is False


# ── BR-12: Contest and freeze ─────────────────────────────────────────────────

def test_contest_freezes_clock():
    c = make_challan(offence_date="2024-01-01")
    # Contest on day 20
    contest_challan(c, contest_date="2024-01-21")
    # Decision on day 40 (20 days of freeze)
    resolve_contest(c, decision="UPHELD", resolution_date="2024-02-10")
    assert c.frozen_days == 20
    # Now check on what would be calendar day 65 — but effective is only 45
    status = update_challan_status(c, current_date="2024-03-06")
    assert status == "ISSUED"   # effective days < 60, so not escalated yet

def test_dismissed_challan_not_court_referred():
    c = make_challan(offence_date="2024-01-01")
    contest_challan(c, contest_date="2024-01-10")
    resolve_contest(c, decision="DISMISSED", resolution_date="2024-01-20")
    assert c.status == "DISMISSED"
    # Even after 90 days, a dismissed challan stays dismissed
    status = update_challan_status(c, current_date="2024-05-01")
    assert status == "DISMISSED"


# ── BR-14: Document waiver ────────────────────────────────────────────────────

def test_insurance_waiver_within_15_days():
    c = make_challan(offence_code="NO_INSURANCE", offence_date="2024-01-01")
    success, msg = apply_document_waiver(
        c,
        document_date="2023-12-01",    # insurance was valid before offence
        production_date="2024-01-10"   # produced within 15 days
    )
    assert success is True
    assert c.status == "DISMISSED"

def test_insurance_waiver_rejected_after_15_days():
    c = make_challan(offence_code="NO_INSURANCE", offence_date="2024-01-01")
    success, msg = apply_document_waiver(
        c,
        document_date="2023-12-01",
        production_date="2024-01-20"   # day 19 — too late
    )
    assert success is False

def test_insurance_waiver_rejected_if_doc_after_offence():
    c = make_challan(offence_code="NO_INSURANCE", offence_date="2024-01-01")
    success, msg = apply_document_waiver(
        c,
        document_date="2024-01-05",    # document dated AFTER the offence
        production_date="2024-01-10"
    )
    assert success is False


# ── BR-13: Licence points ─────────────────────────────────────────────────────

def test_points_added_for_offence():
    owner = make_owner()
    add_licence_points(owner, "NO_HELMET", "2024-01-01")
    assert len(owner.licence_points) == 1
    assert owner.licence_points[0]["points"] == 2

def test_no_points_for_insurance_offence():
    owner = make_owner()
    add_licence_points(owner, "NO_INSURANCE", "2024-01-01")
    assert len(owner.licence_points) == 0

def test_licence_suspended_at_12_points():
    owner = make_owner()
    # Add enough points to hit 12
    add_licence_points(owner, "DRUNK_DRIVING", "2024-01-01")  # 5 pts
    add_licence_points(owner, "SPEEDING",      "2024-02-01")  # 3 pts
    add_licence_points(owner, "RED_LIGHT",     "2024-03-01")  # 3 pts
    add_licence_points(owner, "NO_HELMET",     "2024-04-01")  # 2 pts = 13 total
    result = check_and_apply_suspension(owner, "2024-04-01")
    assert result == "SUSPENDED"
    assert owner.licence_status == "SUSPENDED"

def test_points_outside_24_months_not_counted():
    # EC-11: point from more than 24 months ago must not trigger suspension
    owner = make_owner()
    add_licence_points(owner, "DRUNK_DRIVING", "2021-01-01")  # 5 pts — older than 24 months
    add_licence_points(owner, "SPEEDING",      "2024-02-01")  # 3 pts
    add_licence_points(owner, "RED_LIGHT",     "2024-03-01")  # 3 pts
    # Total in window = 6 pts — not enough for suspension
    result = check_and_apply_suspension(owner, "2024-04-01")
    assert result == "OK"
    assert owner.licence_status == "ACTIVE"