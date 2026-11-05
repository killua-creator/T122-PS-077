# One test per rule and per edge case.
# Run with:  pytest tests/test_tax.py -v

from engine.tax_calculator import (
    calculate_road_tax_2w,
    calculate_road_tax_lmv_private,
    calculate_road_tax_ev,
    calculate_diesel_surcharge,
    calculate_luxury_cess
)

# ── BR-01: 2W road tax ────────────────────────────────────────────────────────

def test_2w_tax_below_50000():
    assert calculate_road_tax_2w(40000) == 4000.0    # 10% of 40,000

def test_2w_tax_exactly_50000():
    # EC-01: boundary must use the LOWER slab (10%)
    assert calculate_road_tax_2w(50000) == 5000.0    # 10% of 50,000

def test_2w_tax_above_50000():
    assert calculate_road_tax_2w(60000) == 7200.0    # 12% of 60,000

def test_2w_tax_exactly_100000():
    assert calculate_road_tax_2w(100000) == 12000.0  # 12% of 1,00,000

def test_2w_tax_above_100000():
    assert calculate_road_tax_2w(150000) == 27000.0  # 18% of 1,50,000


# ── BR-02: LMV_PRIVATE road tax ───────────────────────────────────────────────

def test_lmv_tax_below_5_lakh():
    assert calculate_road_tax_lmv_private(400000) == 52000.0   # 13% of 4,00,000

def test_lmv_tax_exactly_5_lakh():
    # EC-02: boundary — 13% slab applies
    assert calculate_road_tax_lmv_private(500000) == 65000.0   # 13% of 5,00,000

def test_lmv_tax_between_5_and_10_lakh():
    assert calculate_road_tax_lmv_private(800000) == 112000.0  # 14% of 8,00,000

def test_lmv_tax_exactly_20_lakh():
    # EC-03: boundary — 17% slab applies, NO luxury cess (price must be ABOVE 20L)
    assert calculate_road_tax_lmv_private(2000000) == 340000.0 # 17% of 20,00,000

def test_lmv_tax_above_20_lakh():
    assert calculate_road_tax_lmv_private(2500000) == 450000.0 # 18% of 25,00,000


# ── BR-03: EV road tax ────────────────────────────────────────────────────────

def test_ev_tax_before_sunset():
    assert calculate_road_tax_ev(1000000, "2024-01-01", "2025-01-01") == 0.0

def test_ev_tax_on_sunset_date():
    # EC-04: ON the sunset date → 5% applies
    assert calculate_road_tax_ev(1000000, "2025-01-01", "2025-01-01") == 50000.0

def test_ev_tax_after_sunset():
    assert calculate_road_tax_ev(1000000, "2026-01-01", "2025-01-01") == 50000.0


# ── BR-04: Cess ───────────────────────────────────────────────────────────────

def test_diesel_surcharge_applies():
    # Diesel LMV_PRIVATE → 2% surcharge
    assert calculate_diesel_surcharge(1000000, "LMV_PRIVATE", "DIESEL") == 20000.0

def test_diesel_surcharge_not_for_petrol():
    assert calculate_diesel_surcharge(1000000, "LMV_PRIVATE", "PETROL") == 0.0

def test_diesel_surcharge_not_for_2w():
    # Diesel surcharge is only for LMV_PRIVATE
    assert calculate_diesel_surcharge(80000, "2W", "DIESEL") == 0.0

def test_luxury_cess_above_20_lakh():
    assert calculate_luxury_cess(2500000, "LMV_PRIVATE", "PETROL") == 25000.0

def test_luxury_cess_exactly_20_lakh():
    # EC-03: exactly 20 lakh → NOT above → no luxury cess
    assert calculate_luxury_cess(2000000, "LMV_PRIVATE", "PETROL") == 0.0

def test_luxury_cess_ev_exempt():
    # EVs never pay cess even if above 20 lakh
    assert calculate_luxury_cess(3000000, "EV", "ELECTRIC") == 0.0

from engine.tax_calculator import (
    calculate_quarterly_tax,
    calculate_quarterly_late_fee,
    get_unpaid_quarters_count
)

def test_lmv_transport_quarterly_tax():
    # 4 seats × Rs 1,500/year = Rs 6,000/year → Rs 1,500/quarter
    # Rs 1,500 is already a multiple of 10 — no rounding needed
    assert calculate_quarterly_tax("LMV_TRANSPORT", seating=4,
                                    laden_weight_tonnes=0) == 1500

def test_hgv_quarterly_tax_rounded_up():
    # 3 tonnes × Rs 1,000/year = Rs 3,000/year → Rs 750/quarter
    # Rs 750 is already a multiple of 10
    assert calculate_quarterly_tax("HGV", seating=0,
                                    laden_weight_tonnes=3) == 750

def test_bus_quarterly_tax():
    # 40 seats × Rs 2,500/year = Rs 1,00,000/year → Rs 25,000/quarter
    assert calculate_quarterly_tax("BUS", seating=40,
                                    laden_weight_tonnes=0) == 25000

def test_quarterly_tax_rounds_up_to_nearest_10():
    # 3 seats × Rs 1,500/year = Rs 4,500/year → Rs 1,125/quarter
    # Rounded UP to nearest Rs 10 = Rs 1,130
    assert calculate_quarterly_tax("LMV_TRANSPORT", seating=3,
                                    laden_weight_tonnes=0) == 1130

def test_quarterly_late_fee_1_month():
    # 2% of Rs 1,500 for 1 month = Rs 30
    assert calculate_quarterly_late_fee(1500, months_late=1) == 30.0

def test_quarterly_late_fee_capped_at_20_percent():
    # 11 months late → 22% → capped at 20%
    # 20% of Rs 1,500 = Rs 300
    assert calculate_quarterly_late_fee(1500, months_late=11) == 300.0

def test_unpaid_quarters_count():
    records = [
        {"quarter_start": "2024-01-01", "paid": True,  "paid_date": "2023-12-28"},
        {"quarter_start": "2024-04-01", "paid": False, "paid_date": None},
        {"quarter_start": "2024-07-01", "paid": False, "paid_date": None},
    ]
    count = get_unpaid_quarters_count(records, current_date="2024-08-01")
    assert count == 2   # two unpaid quarters that have already started

def test_future_quarter_not_counted_as_unpaid():
    records = [
        {"quarter_start": "2024-01-01", "paid": True,  "paid_date": "2023-12-28"},
        {"quarter_start": "2024-04-01", "paid": False, "paid_date": None},
        {"quarter_start": "2024-07-01", "paid": False, "paid_date": None},
    ]
    # Current date is before July quarter — only April quarter is overdue
    count = get_unpaid_quarters_count(records, current_date="2024-05-01")
    assert count == 1