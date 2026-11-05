# All fitness certificate and permit logic lives here.
# Rules covered: BR-07 (fitness), BR-08 (permit)

from datetime import date, timedelta
from models.fitness import FitnessCertificate, Permit

# ── Constants ──────────────────────────────────────────────────────────────────

# Fitness certificate (BR-07)
NEW_VEHICLE_FITNESS_YEARS    = 2     # first cert is valid for 2 years
RENEWAL_FITNESS_YEARS        = 1     # renewals are valid for 1 year
EARLY_RENEWAL_WINDOW_DAYS    = 60    # can renew up to 60 days before expiry
RETEST_WINDOW_DAYS           = 15    # free retest within 15 days of failed inspection
LATE_FEE_PER_DAY             = 50    # Rs 50 per day late fee
MAX_LATE_FEE                 = 5000  # Rs 5,000 cap on late fee

# Private vehicle fitness (BR-07)
PRIVATE_FITNESS_AGE_YEARS    = 15    # private vehicles need fitness after 15 years
PRIVATE_FITNESS_RENEWAL_YEARS = 5    # renewed every 5 years

# Permit (BR-08)
PERMIT_VALIDITY_YEARS        = 5     # permit is valid for 5 years
PERMIT_LAPSE_MONTHS          = 6     # lapsed by more than 6 months → fresh application
PERMIT_FRESH_FEE_MULTIPLIER  = 2     # fresh application fee = 2x renewal fee

# Transport vehicle tax (BR-05) — unpaid quarters block fitness/permit renewal
MAX_UNPAID_QUARTERS_ALLOWED  = 1     # 2 or more unpaid quarters → block renewal


# ── BR-07: Issue a new fitness certificate ────────────────────────────────────

def issue_fitness_certificate(vehicle_id, inspection_date, is_new_vehicle=True):
    """
    Issues a new fitness certificate after a passed inspection.
    New vehicles get 2-year validity.
    Renewals get 1-year validity (keeping the anniversary date).

    vehicle_id:       registration mark
    inspection_date:  string "YYYY-MM-DD"
    is_new_vehicle:   True for first-ever certificate

    Returns: a FitnessCertificate object
    """
    insp = date.fromisoformat(inspection_date)

    if is_new_vehicle:
        expiry = insp.replace(year=insp.year + NEW_VEHICLE_FITNESS_YEARS)
    else:
        expiry = insp.replace(year=insp.year + RENEWAL_FITNESS_YEARS)

    return FitnessCertificate(
        vehicle_id   = vehicle_id,
        issue_date   = inspection_date,
        expiry_date  = str(expiry),
        is_new_vehicle = is_new_vehicle
    )


# ── BR-07: Renew a fitness certificate ────────────────────────────────────────

def renew_fitness_certificate(existing_cert, application_date,
                               inspection_date, inspection_passed,
                               unpaid_quarters=0):
    """
    Renews an existing fitness certificate.

    existing_cert:     the current FitnessCertificate object
    application_date:  string "YYYY-MM-DD" — when renewal was applied
    inspection_date:   string "YYYY-MM-DD" — when inspection happened
    inspection_passed: True or False
    unpaid_quarters:   how many quarters of road tax are unpaid

    Returns: (True, new FitnessCertificate) if successful
             (False, reason string) if renewal is blocked
    """

    # BR-05: block renewal if 2 or more quarters unpaid
    if unpaid_quarters > MAX_UNPAID_QUARTERS_ALLOWED:
        return False, (f"Renewal blocked — {unpaid_quarters} quarters of "
                       f"road tax unpaid. Maximum allowed is "
                       f"{MAX_UNPAID_QUARTERS_ALLOWED}.")

    # Inspection failed — allow one free retest within 15 days
    if not inspection_passed:
        retest_deadline = (date.fromisoformat(inspection_date)
                           + timedelta(days=RETEST_WINDOW_DAYS))
        existing_cert.inspection_result = "FAILED"
        existing_cert.retest_deadline   = str(retest_deadline)
        existing_cert.status            = "FAILED"
        return False, (f"Inspection failed. Free retest available until "
                       f"{retest_deadline}.")

    app_date  = date.fromisoformat(application_date)
    insp_date = date.fromisoformat(inspection_date)
    exp_date  = date.fromisoformat(existing_cert.expiry_date)

    late_fee = 0.0

    # Check if renewal is within the early window (up to 60 days before expiry)
    days_before_expiry = (exp_date - app_date).days

    if days_before_expiry >= 0:
        # On time or early — new expiry keeps the same anniversary date
        # EC-05: exactly 60 days before is still valid (within window)
        if days_before_expiry <= EARLY_RENEWAL_WINDOW_DAYS:
            # Within the allowed early window
            new_expiry = exp_date.replace(year=exp_date.year + RENEWAL_FITNESS_YEARS)
        else:
            return False, (f"Too early to renew — expiry is "
                           f"{days_before_expiry} days away. "
                           f"Renewal window opens {EARLY_RENEWAL_WINDOW_DAYS} "
                           f"days before expiry.")
    else:
        # EC-06: Applied AFTER expiry — late fee applies
        # Validity starts from inspection date (not old expiry date)
        days_late = (insp_date - exp_date).days
        days_late = max(days_late, 0)
        late_fee  = min(days_late * LATE_FEE_PER_DAY, MAX_LATE_FEE)

        # New expiry = 1 year from inspection date
        new_expiry = insp_date.replace(year=insp_date.year + RENEWAL_FITNESS_YEARS)

    new_cert = FitnessCertificate(
        vehicle_id     = existing_cert.vehicle_id,
        issue_date     = inspection_date,
        expiry_date    = str(new_expiry),
        is_new_vehicle = False
    )
    new_cert.late_fee = late_fee

    return True, new_cert


# ── BR-07: Failed inspection retest ───────────────────────────────────────────

def apply_retest(existing_cert, retest_date, retest_passed):
    """
    Applies a retest after a failed inspection.
    One free retest is allowed within 15 days of the failed inspection.

    Returns: (True, new FitnessCertificate) if retest passed
             (False, reason) if retest failed or window missed
    """
    if existing_cert.inspection_result != "FAILED":
        return False, "No failed inspection on record — retest not applicable"

    if existing_cert.retest_done:
        return False, "Free retest already used — must pay for a fresh inspection"

    # Check retest is within the 15-day window
    if retest_date > existing_cert.retest_deadline:
        return False, (f"Retest deadline was {existing_cert.retest_deadline} "
                       f"— retest window has closed")

    existing_cert.retest_done = True

    if not retest_passed:
        existing_cert.status = "EXPIRED"
        return False, "Retest also failed — certificate expired"

    # Retest passed — issue new certificate from retest date
    exp_date   = date.fromisoformat(existing_cert.expiry_date)
    retest     = date.fromisoformat(retest_date)
    new_expiry = retest.replace(year=retest.year + RENEWAL_FITNESS_YEARS)

    new_cert = FitnessCertificate(
        vehicle_id     = existing_cert.vehicle_id,
        issue_date     = retest_date,
        expiry_date    = str(new_expiry),
        is_new_vehicle = False
    )
    return True, new_cert


# ── BR-07: Check if private vehicle needs fitness ─────────────────────────────

def private_vehicle_needs_fitness(registration_date, current_date):
    """
    Private vehicles only need a fitness certificate after 15 years.
    Returns True if the vehicle is old enough to need one.
    """
    reg  = date.fromisoformat(registration_date)
    curr = date.fromisoformat(current_date)
    age_years = (curr - reg).days // 365
    return age_years >= PRIVATE_FITNESS_AGE_YEARS


# ── BR-08: Issue a permit ─────────────────────────────────────────────────────

def issue_permit(vehicle_id, permit_type, issue_date,
                 has_valid_fitness, has_valid_insurance,
                 unpaid_quarters=0):
    """
    Issues a new permit for a transport vehicle.

    Returns: (True, Permit object) if successful
             (False, reason) if blocked
    """
    # Must have valid fitness before a permit is issued
    if not has_valid_fitness:
        return False, "Cannot issue permit — vehicle does not have a valid fitness certificate"

    # Must have valid insurance
    if not has_valid_insurance:
        return False, "Cannot issue permit — vehicle does not have valid insurance"

    # Must not have unpaid tax for 2+ quarters
    if unpaid_quarters > MAX_UNPAID_QUARTERS_ALLOWED:
        return False, (f"Cannot issue permit — {unpaid_quarters} quarters "
                       f"of road tax unpaid")

    issue  = date.fromisoformat(issue_date)
    expiry = issue.replace(year=issue.year + PERMIT_VALIDITY_YEARS)

    # Annual renewal is due one year from issue
    annual = issue.replace(year=issue.year + 1)

    permit = Permit(
        vehicle_id          = vehicle_id,
        permit_type         = permit_type,
        issue_date          = issue_date,
        expiry_date         = str(expiry),
        annual_renewal_date = str(annual)
    )
    return True, permit


# ── BR-08: Renew a permit ─────────────────────────────────────────────────────

def renew_permit(existing_permit, renewal_date,
                 has_valid_fitness, has_valid_insurance,
                 unpaid_quarters=0, renewal_fee=5000):
    """
    Renews an existing permit.
    If permit lapsed by more than 6 months → fresh application at 2x fee.

    Returns: (True, new Permit, fee_charged) if successful
             (False, reason, 0) if blocked
    """
    # Same checks as issue
    if not has_valid_fitness:
        return False, "Renewal blocked — no valid fitness certificate", 0

    if not has_valid_insurance:
        return False, "Renewal blocked — no valid insurance", 0

    if unpaid_quarters > MAX_UNPAID_QUARTERS_ALLOWED:
        return False, (f"Renewal blocked — {unpaid_quarters} quarters "
                       f"of road tax unpaid"), 0

    exp_date  = date.fromisoformat(existing_permit.expiry_date)
    renew     = date.fromisoformat(renewal_date)

    # How long has the permit been lapsed?
    if renew > exp_date:
        lapsed_days   = (renew - exp_date).days
        lapsed_months = lapsed_days // 30

        if lapsed_months > PERMIT_LAPSE_MONTHS:
            # EC: lapsed more than 6 months → fresh application at 2x fee
            fee_charged = renewal_fee * PERMIT_FRESH_FEE_MULTIPLIER
            existing_permit.status = "LAPSED"

            # Issue a brand-new permit from today
            new_expiry = renew.replace(year=renew.year + PERMIT_VALIDITY_YEARS)
            annual     = renew.replace(year=renew.year + 1)

            new_permit = Permit(
                vehicle_id          = existing_permit.vehicle_id,
                permit_type         = existing_permit.permit_type,
                issue_date          = renewal_date,
                expiry_date         = str(new_expiry),
                annual_renewal_date = str(annual)
            )
            return True, new_permit, fee_charged

    # Normal renewal — extend by 5 years from renewal date
    fee_charged = renewal_fee
    new_expiry  = renew.replace(year=renew.year + PERMIT_VALIDITY_YEARS)
    annual      = renew.replace(year=renew.year + 1)

    new_permit = Permit(
        vehicle_id          = existing_permit.vehicle_id,
        permit_type         = existing_permit.permit_type,
        issue_date          = renewal_date,
        expiry_date         = str(new_expiry),
        annual_renewal_date = str(annual)
    )
    return True, new_permit, fee_charged