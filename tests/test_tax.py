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