# This handles issuing registration marks (number plates).
# Rules covered: BR-06

from models.registration import RegistrationSeries

# ── Constants ──────────────────────────────────────────────────────────────────

SERIES_MAX_NUMBER       = 9999      # when this is reached, start a new series
TEMP_VALIDITY_DAYS      = 30        # temporary registration is valid for 30 days

# Minimum bid amounts by fancy number tier (BR-06)
FANCY_MIN_BID = {
    1: 100000,   # tier 1 → Rs 1,00,000
    2: 50000,    # tier 2 → Rs 50,000
    3: 25000     # tier 3 → Rs 25,000
}


# ── BR-06: Issue the next available registration mark ─────────────────────────

def issue_next_mark(series):
    """
    Issues the next available (non-fancy) registration mark from the series.
    Skips over any fancy numbers that have not been auctioned.
    series: a RegistrationSeries object

    Returns: the full registration mark string e.g. "KA01AB0042"
             OR None if the series is exhausted (9999 reached)
    """
    if series.is_exhausted:
        return None

    # Keep incrementing until we find a number that is not a pending fancy number
    while series.current_number < SERIES_MAX_NUMBER:
        series.current_number += 1
        number = series.current_number

        if hasattr(series, "issued_numbers") and number in series.issued_numbers:
            continue

        if series.is_fancy(number):
            # This is a fancy number — has it been auctioned already?
            if number in series.auctioned_numbers:
                # It was auctioned — it can be issued
                if hasattr(series, "issued_numbers"):
                    series.issued_numbers.add(number)
                return series.format_mark(number)
            else:
                # EC-07: Fancy number in sequence but no auction — SKIP it
                continue

        # Normal number — issue it
        if hasattr(series, "issued_numbers"):
            series.issued_numbers.add(number)
        return series.format_mark(number)

    # Reached 9999
    series.is_exhausted = True
    return None


# ── BR-06: Auction a fancy number ─────────────────────────────────────────────

def auction_fancy_number(series, number, winning_bid):
    """
    Records a winning auction bid for a fancy number.
    The number can then be issued normally via issue_next_mark
    OR directly assigned to a vehicle that specifically requested it.

    series:      a RegistrationSeries object
    number:      the fancy number as an integer e.g. 786
    winning_bid: the winning bid amount in rupees

    Returns: (True, mark) if auction is valid
             (False, reason) if auction is invalid
    """
    # Check the number is actually in the fancy list
    if not series.is_fancy(number):
        return False, f"{number} is not a fancy number in this series"

    # Check the number hasn't already been auctioned
    if number in series.auctioned_numbers:
        return False, f"{number} has already been auctioned"

    # Check the bid meets the minimum for this tier
    tier = series.get_fancy_tier(number)
    min_bid = FANCY_MIN_BID[tier]

    if winning_bid < min_bid:
        return False, (
            f"Bid of Rs {winning_bid} is below the minimum "
            f"of Rs {min_bid} for tier {tier} number {number:04d}"
        )

    # All checks passed — record the auction
    series.auctioned_numbers[number] = winning_bid
    mark = series.format_mark(number)
    return True, mark


# ── BR-06: Issue temporary registration ───────────────────────────────────────

def issue_temp_registration(series, registration_date):
    """
    Issues a temporary registration mark (valid for 30 days).
    Uses the same sequence as permanent marks.

    registration_date: string "YYYY-MM-DD"
    Returns: a dictionary with the temp mark and its expiry date
    """
    from datetime import date, timedelta

    mark = issue_next_mark(series)
    if mark is None:
        return None

    # Calculate expiry date — 30 days from registration date
    reg_date_obj = date.fromisoformat(registration_date)
    expiry_date  = reg_date_obj + timedelta(days=TEMP_VALIDITY_DAYS)

    return {
        "mark":        mark,
        "issued_date": registration_date,
        "expiry_date": str(expiry_date),
        "is_temp":     True
    }


# ── Helper: check if a temporary registration has expired ─────────────────────

def is_temp_expired(temp_registration, current_date):
    """
    Returns True if the temporary registration has passed its 30-day window.
    temp_registration: the dictionary returned by issue_temp_registration()
    current_date: string "YYYY-MM-DD"
    """
    return current_date > temp_registration["expiry_date"]


# ── Helper: get the next series prefix ────────────────────────────────────────

def next_series_prefix(current_prefix):
    """
    When a series reaches 9999, the next series starts.
    e.g. "KA01AB" → "KA01AC", "KA01AZ" → "KA01BA"

    current_prefix: string like "KA01AB"
    Returns: the next series prefix string
    """
    # The last two characters are the letters we increment
    # e.g. KA01AB → the "AB" part changes
    base   = current_prefix[:-2]   # "KA01"
    letter1 = current_prefix[-2]   # "A"
    letter2 = current_prefix[-1]   # "B"

    if letter2 < "Z":
        # Just increment the last letter: B → C
        new_prefix = base + letter1 + chr(ord(letter2) + 1)
    elif letter1 < "Z":
        # Last letter wraps: Z → A, increment first letter: A → B
        new_prefix = base + chr(ord(letter1) + 1) + "A"
    else:
        # Both at Z — series is completely exhausted (very rare)
        new_prefix = None

    return new_prefix