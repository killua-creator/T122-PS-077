# Run with: pytest tests/test_registration.py -v

from models.registration import RegistrationSeries
from engine.registration_engine import (
    issue_next_mark,
    auction_fancy_number,
    issue_temp_registration,
    is_temp_expired,
    next_series_prefix
)


# ── Normal sequential issue ───────────────────────────────────────────────────

def test_first_mark_issued_is_0001():
    series = RegistrationSeries("KA01AB")
    mark = issue_next_mark(series)
    assert mark == "KA01AB0001"

def test_second_mark_is_0002():
    series = RegistrationSeries("KA01AB")
    issue_next_mark(series)           # 0001
    mark = issue_next_mark(series)    # 0002
    assert mark == "KA01AB0002"

def test_mark_format_has_leading_zeros():
    series = RegistrationSeries("KA01AB")
    for _ in range(9):
        issue_next_mark(series)
    mark = issue_next_mark(series)    # should be 0010
    assert mark == "KA01AB0010"


# ── EC-07: Fancy number skipped when no auction ───────────────────────────────

def test_fancy_number_skipped_in_sequence():
    # Number 2 is fancy — should be skipped, so after 0001 we get 0003
    series = RegistrationSeries("KA01AB", fancy_numbers={2: 1})
    issue_next_mark(series)    # 0001
    mark = issue_next_mark(series)
    assert mark == "KA01AB0003"   # 0002 was skipped

def test_fancy_number_issued_after_auction():
    series = RegistrationSeries("KA01AB", fancy_numbers={1: 1})
    # Auction number 1 with a valid bid
    success, result = auction_fancy_number(series, number=1, winning_bid=100000)
    assert success is True
    # Now 0001 should be issued normally
    mark = issue_next_mark(series)
    assert mark == "KA01AB0001"


# ── Auction rules ─────────────────────────────────────────────────────────────

def test_auction_bid_below_minimum_rejected():
    series = RegistrationSeries("KA01AB", fancy_numbers={786: 2})
    # Tier 2 minimum is Rs 50,000 — bid of Rs 30,000 should fail
    success, reason = auction_fancy_number(series, number=786, winning_bid=30000)
    assert success is False

def test_auction_non_fancy_number_rejected():
    series = RegistrationSeries("KA01AB", fancy_numbers={786: 2})
    # 100 is not in the fancy list
    success, reason = auction_fancy_number(series, number=100, winning_bid=100000)
    assert success is False

def test_auction_same_number_twice_rejected():
    series = RegistrationSeries("KA01AB", fancy_numbers={786: 2})
    auction_fancy_number(series, number=786, winning_bid=50000)
    # Try to auction the same number again
    success, reason = auction_fancy_number(series, number=786, winning_bid=60000)
    assert success is False


# ── Series rollover ───────────────────────────────────────────────────────────

def test_next_series_prefix_normal():
    assert next_series_prefix("KA01AB") == "KA01AC"

def test_next_series_prefix_z_rolls_over():
    assert next_series_prefix("KA01AZ") == "KA01BA"

def test_series_exhausted_after_9999():
    series = RegistrationSeries("KA01AB")
    series.current_number = 9998
    issue_next_mark(series)    # 9999
    mark = issue_next_mark(series)
    assert mark is None
    assert series.is_exhausted is True


# ── Temporary registration ────────────────────────────────────────────────────

def test_temp_registration_issued_with_expiry():
    series = RegistrationSeries("KA01AB")
    temp = issue_temp_registration(series, "2024-01-01")
    assert temp["mark"] == "KA01AB0001"
    assert temp["expiry_date"] == "2024-01-31"
    assert temp["is_temp"] is True

def test_temp_registration_not_expired_on_day_30():
    series = RegistrationSeries("KA01AB")
    temp = issue_temp_registration(series, "2024-01-01")
    # Day 30 — still valid (expiry is "2024-01-31", current is "2024-01-31")
    assert is_temp_expired(temp, "2024-01-31") is False

def test_temp_registration_expired_on_day_31():
    series = RegistrationSeries("KA01AB")
    temp = issue_temp_registration(series, "2024-01-01")
    # Day 31 — expired
    assert is_temp_expired(temp, "2024-02-01") is True