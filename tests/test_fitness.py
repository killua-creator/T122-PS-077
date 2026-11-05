# Run with: pytest tests/test_fitness.py -v

from engine.fitness_engine import (
    issue_fitness_certificate,
    renew_fitness_certificate,
    apply_retest,
    private_vehicle_needs_fitness,
    issue_permit,
    renew_permit
)


# ── BR-07: Issue fitness certificate ─────────────────────────────────────────

def test_new_vehicle_gets_2_year_cert():
    cert = issue_fitness_certificate("KA01AB0001", "2024-01-01", is_new_vehicle=True)
    assert cert.expiry_date == "2026-01-01"
    assert cert.status == "VALID"

def test_renewal_gets_1_year_cert():
    cert = issue_fitness_certificate("KA01AB0001", "2024-01-01", is_new_vehicle=False)
    assert cert.expiry_date == "2025-01-01"


# ── BR-07: Renewal within window ─────────────────────────────────────────────

def test_renewal_within_60_day_window_keeps_anniversary():
    # Cert expires 2024-03-01. Apply renewal on 2024-01-01 (59 days before).
    cert = issue_fitness_certificate("KA01AB0001", "2022-03-01", is_new_vehicle=True)
    cert.expiry_date = "2024-03-01"

    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-01-01",
        inspection_date   = "2024-01-01",
        inspection_passed = True
    )
    assert success is True
    # New expiry should be 1 year from old expiry anniversary: 2025-03-01
    assert result.expiry_date == "2025-03-01"

def test_renewal_exactly_60_days_before_expiry_accepted():
    # EC-05: exactly 60 days before expiry is within the window
    cert = issue_fitness_certificate("KA01AB0001", "2022-03-01", is_new_vehicle=True)
    cert.expiry_date = "2024-03-01"

    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-01-01",   # exactly 60 days before 2024-03-01 (leap year)
        inspection_date   = "2024-01-01",
        inspection_passed = True
    )
    assert success is True

def test_renewal_too_early_rejected():
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.expiry_date = "2024-06-01"

    # Apply 120 days before expiry — too early
    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-02-01",
        inspection_date   = "2024-02-01",
        inspection_passed = True
    )
    assert success is False


# ── BR-07: Late renewal ───────────────────────────────────────────────────────

def test_renewal_one_day_after_expiry_incurs_late_fee():
    # EC-06: one day late → Rs 50 late fee
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.expiry_date = "2024-01-01"

    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-01-02",
        inspection_date   = "2024-01-02",
        inspection_passed = True
    )
    assert success is True
    assert result.late_fee == 50.0
    # Validity starts from inspection date
    assert result.expiry_date == "2025-01-02"

def test_late_fee_capped_at_5000():
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.expiry_date = "2024-01-01"

    # 200 days late = Rs 50 × 200 = Rs 10,000 — capped at Rs 5,000
    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-07-19",
        inspection_date   = "2024-07-19",
        inspection_passed = True
    )
    assert success is True
    assert result.late_fee == 5000.0


# ── BR-07: Failed inspection and retest ──────────────────────────────────────

def test_failed_inspection_allows_retest():
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.expiry_date = "2024-03-01"

    success, result = renew_fitness_certificate(
        cert,
        application_date  = "2024-02-15",
        inspection_date   = "2024-02-15",
        inspection_passed = False
    )
    assert success is False
    assert cert.status == "FAILED"
    assert cert.retest_deadline == "2024-03-01"   # 15 days from inspection

def test_retest_passed_within_window():
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.expiry_date      = "2024-03-01"
    cert.inspection_result = "FAILED"
    cert.retest_deadline  = "2024-03-01"
    cert.status           = "FAILED"

    success, new_cert = apply_retest(cert, retest_date="2024-02-25", retest_passed=True)
    assert success is True
    assert new_cert.expiry_date == "2025-02-25"

def test_retest_after_deadline_rejected():
    cert = issue_fitness_certificate("KA01AB0001", "2022-01-01", is_new_vehicle=True)
    cert.inspection_result = "FAILED"
    cert.retest_deadline   = "2024-02-20"
    cert.status            = "FAILED"

    success, msg = apply_retest(cert, retest_date="2024-02-25", retest_passed=True)
    assert success is False


# ── BR-07: Private vehicle fitness rule ──────────────────────────────────────

def test_private_vehicle_needs_fitness_after_15_years():
    # Registered 2005-01-01, checking in 2020-01-02 — over 15 years
    assert private_vehicle_needs_fitness("2005-01-01", "2020-01-02") is True

def test_private_vehicle_no_fitness_before_15_years():
    # Registered 2015-01-01, checking in 2024-01-01 — under 15 years
    assert private_vehicle_needs_fitness("2015-01-01", "2024-01-01") is False


# ── BR-08: Permit issue and renewal ──────────────────────────────────────────

def test_permit_issued_with_valid_fitness_and_insurance():
    success, permit = issue_permit(
        vehicle_id         = "KA01AB0001",
        permit_type        = "GOODS",
        issue_date         = "2024-01-01",
        has_valid_fitness  = True,
        has_valid_insurance = True,
        unpaid_quarters    = 0
    )
    assert success is True
    assert permit.expiry_date         == "2029-01-01"
    assert permit.annual_renewal_date == "2025-01-01"

def test_permit_blocked_without_fitness():
    success, reason = issue_permit(
        vehicle_id         = "KA01AB0001",
        permit_type        = "GOODS",
        issue_date         = "2024-01-01",
        has_valid_fitness  = False,
        has_valid_insurance = True
    )
    assert success is False

def test_permit_blocked_with_2_unpaid_quarters():
    success, reason = issue_permit(
        vehicle_id         = "KA01AB0001",
        permit_type        = "GOODS",
        issue_date         = "2024-01-01",
        has_valid_fitness  = True,
        has_valid_insurance = True,
        unpaid_quarters    = 2
    )
    assert success is False

def test_permit_lapsed_over_6_months_charges_double_fee():
    from models.fitness import Permit
    old_permit = Permit(
        vehicle_id          = "KA01AB0001",
        permit_type         = "GOODS",
        issue_date          = "2019-01-01",
        expiry_date         = "2024-01-01",
        annual_renewal_date = "2020-01-01"
    )
    # Renewal applied 8 months after expiry
    success, new_permit, fee = renew_permit(
        old_permit,
        renewal_date        = "2024-09-01",
        has_valid_fitness   = True,
        has_valid_insurance = True,
        unpaid_quarters     = 0,
        renewal_fee         = 5000
    )
    assert success is True
    assert fee == 10000    # 2x the renewal fee