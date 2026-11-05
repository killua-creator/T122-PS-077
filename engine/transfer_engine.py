# Ownership transfer, hypothecation, NOC and inter-state migration logic.
# Rules covered: BR-09 (transfer), BR-10 (migration)

from datetime import date, timedelta
from models.transfer import OwnershipTransfer, NOC

# ── Constants ──────────────────────────────────────────────────────────────────

# Ownership transfer (BR-09)
TRANSFER_FEE_DEFAULT         = 500    # Rs 500 for most vehicles
TRANSFER_FEE_2W              = 150    # Rs 150 for two-wheelers
TRANSFER_DELAY_FREE_DAYS     = 30     # no penalty if applied within 30 days of sale
TRANSFER_DELAY_FEE_PER_MONTH = 300    # Rs 300 per month of delay beyond 30 days
MAX_PENDING_CHALLAN_AMOUNT   = 2000   # pending challans above Rs 2,000 block transfer

# Inter-state migration (BR-10)
DEPRECIATION_RATE_PER_YEAR   = 0.07  # 7% per completed year
MAX_DEPRECIATION             = 0.70  # 70% cap
LIFETIME_TAX_YEARS           = 15    # road tax is treated as covering 15 years
NOC_UTILISATION_WINDOW_DAYS  = 365   # NOC must be utilised within 12 months


# ── BR-09: Check if transfer is allowed ───────────────────────────────────────

def can_transfer(vehicle, challans):
    """
    Checks whether a vehicle is eligible for ownership transfer.

    vehicle:  a Vehicle object
    challans: list of Challan objects for this vehicle

    Returns: (True, "OK") if transfer is allowed
             (False, reason) if transfer is blocked
    """
    # Block if vehicle is under hypothecation (bank loan)
    if vehicle.hypothecation is not None:
        return False, (f"Transfer blocked — vehicle is under hypothecation "
                       f"with {vehicle.hypothecation}. "
                       f"Obtain financier NOC first.")

    # Block if vehicle status is BLOCKED (court-referred challan)
    if vehicle.status == "BLOCKED":
        return False, "Transfer blocked — vehicle is BLOCKED due to court-referred challan"

    # Check total pending challan amount
    pending_amount = sum(
        c.current_amount
        for c in challans
        if c.status in ("ISSUED", "ESCALATED")
    )

    if pending_amount > MAX_PENDING_CHALLAN_AMOUNT:
        return False, (f"Transfer blocked — pending challan total "
                       f"Rs {pending_amount} exceeds Rs {MAX_PENDING_CHALLAN_AMOUNT}")

    return True, "OK"


# ── BR-09: Calculate transfer fee ─────────────────────────────────────────────

def calculate_transfer_fee(vehicle_class, sale_date, transfer_date):
    """
    Calculates the total transfer fee including any delay penalty.

    vehicle_class:  string like "2W", "LMV_PRIVATE"
    sale_date:      string "YYYY-MM-DD"
    transfer_date:  string "YYYY-MM-DD"

    Returns: dictionary with base_fee, delay_months, delay_fee, total_fee
    """
    # Base fee depends on vehicle class
    if vehicle_class == "2W":
        base_fee = TRANSFER_FEE_2W
    else:
        base_fee = TRANSFER_FEE_DEFAULT

    sale     = date.fromisoformat(sale_date)
    transfer = date.fromisoformat(transfer_date)
    days_gap = (transfer - sale).days

    # EC-08: transfer on exactly day 30 → NO delay fee
    # Delay fee only applies if MORE than 30 days have passed
    delay_fee    = 0
    delay_months = 0

    if days_gap > TRANSFER_DELAY_FREE_DAYS:
        # Calculate how many full months of delay beyond 30 days
        extra_days   = days_gap - TRANSFER_DELAY_FREE_DAYS
        delay_months = (extra_days // 30) + 1   # even part of a month counts
        delay_fee    = delay_months * TRANSFER_DELAY_FEE_PER_MONTH

    total_fee = base_fee + delay_fee

    return {
        "base_fee":     base_fee,
        "delay_months": delay_months,
        "delay_fee":    delay_fee,
        "total_fee":    total_fee
    }


# ── BR-09: Process ownership transfer ────────────────────────────────────────

def process_transfer(transfer_id, vehicle, challans,
                     new_owner_id, sale_date, transfer_date):
    """
    Processes a full ownership transfer.
    Checks eligibility, calculates fee, and returns a transfer record.

    Returns: (True, OwnershipTransfer object) if successful
             (False, reason string) if blocked
    """
    # Step 1 — eligibility check
    allowed, reason = can_transfer(vehicle, challans)
    if not allowed:
        return False, reason

    # Step 2 — calculate the fee
    fee_breakdown = calculate_transfer_fee(
        vehicle.vehicle_class, sale_date, transfer_date
    )

    # Step 3 — create transfer record
    transfer = OwnershipTransfer(
        transfer_id  = transfer_id,
        vehicle_id   = vehicle.registration_mark,
        old_owner_id = vehicle.owner_id,
        new_owner_id = new_owner_id,
        sale_date    = sale_date,
        transfer_date = transfer_date,
        transfer_fee = fee_breakdown["total_fee"]
    )

    # Step 4 — update vehicle owner
    vehicle.owner_id = new_owner_id

    return True, transfer


# ── BR-09: Hypothecation termination ──────────────────────────────────────────

def terminate_hypothecation(vehicle, financier_noc_received):
    """
    Removes hypothecation from a vehicle after the bank issues NOC.

    Returns: (True, message) or (False, reason)
    """
    if vehicle.hypothecation is None:
        return False, "Vehicle is not under hypothecation"

    if not financier_noc_received:
        return False, "Cannot terminate hypothecation — financier NOC not received"

    vehicle.hypothecation = None
    return True, f"Hypothecation removed from {vehicle.registration_mark}"


# ── BR-10: Calculate depreciated price ────────────────────────────────────────

def calculate_depreciated_price(original_price, first_registration_date,
                                 migration_date):
    """
    When a vehicle migrates to a new state, road tax is charged on the
    depreciated price — not the original price.

    Depreciation: 7% per completed year, capped at 70%.

    EC-09: at exactly 10 completed years, depreciation = 70% (cap reached).

    Returns: depreciated price in rupees
    """
    first_reg  = date.fromisoformat(first_registration_date)
    migration  = date.fromisoformat(migration_date)

    # Count only COMPLETED years (not partial years)
    completed_years = (migration - first_reg).days // 365

    # Apply depreciation rate, capped at maximum
    total_depreciation = min(
        completed_years * DEPRECIATION_RATE_PER_YEAR,
        MAX_DEPRECIATION
    )

    depreciated_price = original_price * (1 - total_depreciation)
    return round(depreciated_price, 2)


# ── BR-10: Calculate old-state tax refund ────────────────────────────────────

def calculate_tax_refund(road_tax_paid, first_registration_date, noc_issue_date):
    """
    When a vehicle leaves the state, the old state refunds the unused
    portion of the lifetime road tax.

    Refund = tax_paid × (remaining years out of 15) / 15
    Rounded DOWN to the nearest rupee.

    The "remaining years" is 15 minus the completed years since first registration.
    If vehicle is older than 15 years — no refund.

    Returns: refund amount in rupees (0 if no refund due)
    """
    first_reg = date.fromisoformat(first_registration_date)
    noc_date  = date.fromisoformat(noc_issue_date)

    completed_years  = (noc_date - first_reg).days // 365
    remaining_years  = LIFETIME_TAX_YEARS - completed_years

    if remaining_years <= 0:
        return 0   # vehicle older than 15 years — no refund

    refund = (road_tax_paid * remaining_years) / LIFETIME_TAX_YEARS
    return int(refund)   # rounded DOWN (int() truncates)


# ── BR-10: Issue NOC ──────────────────────────────────────────────────────────

def issue_noc(noc_id, vehicle, challans,
              road_tax_paid, first_registration_date, noc_date):
    """
    Issues an NOC for a vehicle migrating to another state.

    Blocked if: any challan is pending OR road tax is unpaid.

    Returns: (True, NOC object) if successful
             (False, reason) if blocked
    """
    # Check for pending challans
    pending_challans = [
        c for c in challans
        if c.status in ("ISSUED", "ESCALATED", "COURT_REFERRED")
    ]
    if pending_challans:
        return False, (f"NOC blocked — {len(pending_challans)} pending "
                       f"challan(s) must be cleared first")

    # Check road tax is paid
    if road_tax_paid <= 0:
        return False, "NOC blocked — road tax has not been paid"

    # Calculate the refund the old state owes
    refund = calculate_tax_refund(
        road_tax_paid, first_registration_date, noc_date
    )

    noc = NOC(
        noc_id        = noc_id,
        vehicle_id    = vehicle.registration_mark,
        issue_date    = noc_date,
        road_tax_paid = road_tax_paid,
        refund_amount = refund
    )
    return True, noc


# ── BR-10: Confirm NOC utilisation and release refund ─────────────────────────

def confirm_noc_utilisation(noc, confirmation_date):
    """
    Called when the new state sends confirmation that the NOC was used.
    Refund is released ONLY if confirmation arrives within 12 months of NOC issue.

    EC-13: confirmation on exactly day 365 → refund is released.

    Returns: (True, refund_amount) if refund is released
             (False, reason) if confirmation is too late
    """
    noc_issued    = date.fromisoformat(noc.issue_date)
    confirmation  = date.fromisoformat(confirmation_date)
    days_elapsed  = (confirmation - noc_issued).days

    noc.utilised_date = confirmation_date
    noc.status        = "UTILISED"

    # EC-13: within 365 days (12 months) → refund released
    if days_elapsed <= NOC_UTILISATION_WINDOW_DAYS:
        noc.refund_released = True
        return True, noc.refund_amount

    # Too late — no refund
    noc.refund_released = False
    return False, "Refund not released — NOC utilisation confirmed after 12 months"