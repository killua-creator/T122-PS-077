# All challan business logic lives here.
# Rules covered: BR-11 (amounts), BR-12 (lifecycle),
#                BR-13 (licence points), BR-14 (insurance/PUC waiver)

from datetime import date, timedelta
from models.challan import Challan

# ── Constants ──────────────────────────────────────────────────────────────────

# Challan lifecycle deadlines (BR-12)
ESCALATION_DAYS         = 60     # unpaid after 60 effective days → ESCALATED
COURT_REFERRAL_DAYS     = 90     # unpaid after 90 effective days → COURT_REFERRED
ESCALATION_SURCHARGE    = 0.50   # 50% surcharge added when ESCALATED
CONTEST_FREEZE_DAYS     = 30     # contesting freezes clock for 30 days
DOCUMENT_WAIVER_DAYS    = 15     # insurance/PUC docs must be produced within 15 days

# Licence points per offence (BR-13)
OFFENCE_POINTS = {
    "NO_HELMET":    2,
    "SPEEDING":     3,
    "RED_LIGHT":    3,
    "DRUNK_DRIVING":5,
    "NO_INSURANCE": 0,   # no points for insurance offence
    "EXPIRED_PUC":  0
}

# Base fine amounts (BR-11)
OFFENCE_AMOUNTS = {
    "NO_HELMET":        1000,
    "SPEEDING_LMV":     1000,   # speeding fine for LMV class vehicles
    "SPEEDING_OTHER":   2000,   # speeding fine for all other vehicles
    "RED_LIGHT":        1000,
    "NO_INSURANCE":     2000,   # first offence
    "NO_INSURANCE_RPT": 4000,   # repeat offence (fixed amount, not doubled)
    "DRUNK_DRIVING":    10000,
    "EXPIRED_PUC":      1000
}

# Maximum fine cap for doubling rule (BR-11)
REPEAT_OFFENCE_CAP = 10000

# Licence suspension threshold (BR-13)
SUSPENSION_POINTS_THRESHOLD = 12
SUSPENSION_DURATION_DAYS    = 180   # 6 months
ROLLING_WINDOW_DAYS         = 730   # 24 months (rolling window for points)
SECOND_SUSPENSION_YEARS     = 5     # second suspension within 5 years → revoked


# ── BR-11: Calculate challan amount ───────────────────────────────────────────

def get_challan_amount(offence_code, vehicle_class, prior_challans):
    """
    Returns the correct fine amount for an offence.

    offence_code:   string like "NO_HELMET", "SPEEDING", "DRUNK_DRIVING"
    vehicle_class:  string like "LMV_PRIVATE", "HGV", "2W"
    prior_challans: list of existing Challan objects for this vehicle/driver
                    used to check if this is a repeat offence within 12 months

    Returns: fine amount in rupees
    """

    # Check if this is a repeat offence within 12 months
    is_repeat = _is_repeat_offence(offence_code, prior_challans)

    # Special case: NO_INSURANCE has its own fixed repeat amount
    if offence_code == "NO_INSURANCE":
        if is_repeat:
            return OFFENCE_AMOUNTS["NO_INSURANCE_RPT"]
        return OFFENCE_AMOUNTS["NO_INSURANCE"]

    # Special case: SPEEDING depends on vehicle class
    if offence_code == "SPEEDING":
        lmv_classes = ["LMV_PRIVATE", "LMV_TRANSPORT"]
        if vehicle_class in lmv_classes:
            base = OFFENCE_AMOUNTS["SPEEDING_LMV"]
        else:
            base = OFFENCE_AMOUNTS["SPEEDING_OTHER"]
    else:
        base = OFFENCE_AMOUNTS.get(offence_code, 1000)

    # Repeat offence rule: double the amount, capped at Rs 10,000
    if is_repeat:
        doubled = base * 2
        return min(doubled, REPEAT_OFFENCE_CAP)

    return base


def _is_repeat_offence(offence_code, prior_challans):
    """
    Returns True if the same offence was committed within the last 12 months.
    Dismissed challans do NOT count as prior offences.
    prior_challans: list of Challan objects
    """
    from datetime import date
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    for challan in prior_challans:
        if challan.offence_code != offence_code:
            continue
        if challan.status == "DISMISSED":
            continue   # dismissed challans don't count
        challan_date = date.fromisoformat(challan.offence_date)
        if challan_date >= one_year_ago:
            return True

    return False


# ── BR-12: Challan lifecycle ───────────────────────────────────────────────────

def get_effective_days(challan, current_date):
    """
    The escalation clock counts only the days the challan was NOT frozen.
    effective_days = total days since issue - frozen days

    challan:      a Challan object
    current_date: string "YYYY-MM-DD"
    Returns: integer number of effective days
    """
    issue_date   = date.fromisoformat(challan.offence_date)
    current      = date.fromisoformat(current_date)
    total_days   = (current - issue_date).days
    return total_days - challan.frozen_days


def pay_challan(challan, payment_date):
    """
    Marks a challan as PAID if it is payable.
    Drunk driving challans go directly to court — they cannot be paid here.

    Returns: (True, message) if paid successfully
             (False, reason) if payment not allowed
    """
    # Drunk driving is always court-referred — cannot be paid
    if challan.offence_code == "DRUNK_DRIVING":
        return False, "Drunk driving challans are court-referred and cannot be paid"

    if challan.status not in ("ISSUED", "ESCALATED"):
        return False, f"Cannot pay a challan with status {challan.status}"

    challan.status    = "PAID"
    challan.paid_date = payment_date
    return True, f"Challan {challan.challan_id} marked as PAID"


def update_challan_status(challan, current_date):
    """
    Checks the effective days and updates the challan status if needed.
    Call this function whenever you need the current status of a challan.

    This is where BR-12 is enforced:
    - After 60 effective days unpaid → ESCALATED (+ 50% surcharge)
    - After 90 effective days unpaid → COURT_REFERRED

    Returns: the updated challan status string
    """
    # Already in a terminal state — nothing to update
    if challan.status in ("PAID", "DISMISSED", "COURT_REFERRED"):
        return challan.status

    # Drunk driving → immediately court-referred
    if challan.offence_code == "DRUNK_DRIVING" and challan.status == "ISSUED":
        challan.status = "COURT_REFERRED"
        challan.court_referred_date = current_date
        return challan.status

    effective_days = get_effective_days(challan, current_date)

    if effective_days > COURT_REFERRAL_DAYS:
        challan.status = "COURT_REFERRED"
        challan.court_referred_date = current_date

    elif effective_days > ESCALATION_DAYS:
        if challan.status == "ISSUED":
            # Add the 50% surcharge — only added once
            surcharge = round(challan.original_amount * ESCALATION_SURCHARGE, 2)
            challan.current_amount = challan.original_amount + surcharge
            challan.status = "ESCALATED"

    return challan.status


def contest_challan(challan, contest_date):
    """
    Owner contests a challan — freezes the escalation clock for 30 days.

    Returns: (True, message) or (False, reason)
    """
    if challan.status not in ("ISSUED", "ESCALATED"):
        return False, f"Cannot contest a challan with status {challan.status}"

    if challan.is_contested:
        return False, "Challan is already being contested"

    challan.is_contested  = True
    challan.contest_start = contest_date
    return True, f"Challan {challan.challan_id} is now CONTESTED — clock frozen for 30 days"


def resolve_contest(challan, decision, resolution_date):
    """
    Resolves a contested challan.
    decision: "DISMISSED" or "UPHELD"

    If DISMISSED: challan is dismissed, removed from repeat-offence count.
    If UPHELD: clock resumes from where it paused.
    If 30 days pass without a decision: clock resumes automatically.
    """
    if not challan.is_contested:
        return False, "This challan is not under contest"

    contest_start = date.fromisoformat(challan.contest_start)
    resolution    = date.fromisoformat(resolution_date)
    days_frozen   = (resolution - contest_start).days

    # Cap frozen days at CONTEST_FREEZE_DAYS (30 days maximum)
    days_frozen = min(days_frozen, CONTEST_FREEZE_DAYS)

    challan.frozen_days  += days_frozen
    challan.is_contested  = False
    challan.contest_start = None

    if decision == "DISMISSED":
        challan.status = "DISMISSED"
        return True, f"Challan {challan.challan_id} DISMISSED"

    # UPHELD or timeout — clock resumes
    return True, f"Challan {challan.challan_id} contest resolved as {decision} — clock resumed"


# ── BR-14: Insurance and PUC waiver ───────────────────────────────────────────

def apply_document_waiver(challan, document_date, production_date):
    """
    Waives a NO_INSURANCE or EXPIRED_PUC challan if valid documents
    dated on or before the offence date are produced within 15 days.

    document_date:   date of the insurance/PUC certificate "YYYY-MM-DD"
    production_date: date the owner produces the document "YYYY-MM-DD"

    Returns: (True, message) or (False, reason)
    """
    if challan.offence_code not in ("NO_INSURANCE", "EXPIRED_PUC"):
        return False, "Document waiver only applies to NO_INSURANCE or EXPIRED_PUC challans"

    # Document must be dated on or before the offence
    if document_date > challan.offence_date:
        return False, "Document is dated after the offence — waiver not applicable"

    # Document must be produced within 15 days of the offence
    offence  = date.fromisoformat(challan.offence_date)
    produced = date.fromisoformat(production_date)
    days_to_produce = (produced - offence).days

    if days_to_produce > DOCUMENT_WAIVER_DAYS:
        return False, (f"Documents produced after {DOCUMENT_WAIVER_DAYS} days "
                       f"— waiver window has closed")

    challan.status = "DISMISSED"
    return True, f"Challan {challan.challan_id} waived — valid documents accepted"


# ── BR-13: Licence points ─────────────────────────────────────────────────────

def add_licence_points(owner, offence_code, offence_date):
    """
    Adds points to an owner's licence for a given offence.
    owner:        an Owner object from models/owner.py
    offence_code: string like "NO_HELMET"
    offence_date: string "YYYY-MM-DD"
    """
    points = OFFENCE_POINTS.get(offence_code, 0)
    if points == 0:
        return   # this offence carries no points

    owner.licence_points.append({
        "date":    offence_date,
        "points":  points,
        "offence": offence_code
    })


def check_and_apply_suspension(owner, current_date):
    """
    Checks if the owner's licence should be suspended.
    Uses a rolling 24-month window.

    If points in the last 24 months >= 12 → suspend for 6 months.
    If this is the second suspension within 5 years → revoke permanently.

    Returns: a string describing what happened ("SUSPENDED", "REVOKED", or "OK")
    """
    current  = date.fromisoformat(current_date)
    cutoff   = current - timedelta(days=ROLLING_WINDOW_DAYS)

    # Sum only the points within the rolling 24-month window
    recent_points = sum(
        entry["points"]
        for entry in owner.licence_points
        if date.fromisoformat(entry["date"]) >= cutoff
    )

    if recent_points < SUSPENSION_POINTS_THRESHOLD:
        return "OK"   # not enough points for suspension

    # Check if this would be a second suspension within 5 years
    if _is_second_suspension(owner, current_date):
        owner.licence_status         = "REVOKED"
        owner.licence_suspended_until = None
        return "REVOKED"

    # First suspension — suspend for 6 months
    suspension_end = current + timedelta(days=SUSPENSION_DURATION_DAYS)
    owner.licence_status          = "SUSPENDED"
    owner.licence_suspended_until = str(suspension_end)

    # Record this suspension event on the owner
    if not hasattr(owner, "suspension_history"):
        owner.suspension_history = []
    owner.suspension_history.append(current_date)

    return "SUSPENDED"


def _is_second_suspension(owner, current_date):
    """
    Returns True if the owner has already been suspended within the last 5 years.
    """
    if not hasattr(owner, "suspension_history"):
        return False

    current       = date.fromisoformat(current_date)
    five_years_ago = current.replace(year=current.year - 5)

    for suspension_date in owner.suspension_history:
        if date.fromisoformat(suspension_date) >= five_years_ago:
            return True

    return False