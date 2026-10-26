"""Unit tests for precision monetary calculations and core domain enums.

Traceability:
- Foundation / Cross-rule invariants
- Precision Decimal arithmetic (Q-03, BR-03A, BR-08E)
"""

from decimal import Decimal
import pytest

from src.enums import (
    ChallanStatus,
    FuelType,
    InspectionResult,
    PermitType,
    VehicleClass,
)
from src.money import (
    calculate_percentage,
    round_currency,
    round_down_to_rupee,
    round_up_to_nearest_ten,
    to_decimal,
    validate_non_negative_currency,
)


class TestEnums:
    """Verify that domain enums contain all specified statutory values."""

    def test_vehicle_class_values(self) -> None:
        assert VehicleClass.TWO_WHEELER.value == "2W"
        assert VehicleClass.LMV_PRIVATE.value == "LMV_PRIVATE"
        assert VehicleClass.LMV_TRANSPORT.value == "LMV_TRANSPORT"
        assert VehicleClass.HGV.value == "HGV"
        assert VehicleClass.BUS.value == "BUS"
        assert VehicleClass.EV.value == "EV"

    def test_fuel_type_values(self) -> None:
        assert FuelType.PETROL.value == "PETROL"
        assert FuelType.DIESEL.value == "DIESEL"
        assert FuelType.ELECTRIC.value == "ELECTRIC"
        assert FuelType.CNG.value == "CNG"
        assert FuelType.HYBRID.value == "HYBRID"

    def test_challan_status_values(self) -> None:
        assert ChallanStatus.ISSUED.value == "ISSUED"
        assert ChallanStatus.PAID.value == "PAID"
        assert ChallanStatus.CONTESTED.value == "CONTESTED"
        assert ChallanStatus.ESCALATED.value == "ESCALATED"
        assert ChallanStatus.COURT_REFERRED.value == "COURT_REFERRED"
        assert ChallanStatus.DISMISSED.value == "DISMISSED"

    def test_permit_type_values(self) -> None:
        assert PermitType.CONTRACT.value == "CONTRACT"
        assert PermitType.STAGE.value == "STAGE"
        assert PermitType.GOODS.value == "GOODS"

    def test_inspection_result_values(self) -> None:
        assert InspectionResult.PASS.value == "PASS"
        assert InspectionResult.FAIL.value == "FAIL"


class TestToDecimal:
    """Verify conversion to Decimal without float contamination."""

    def test_convert_from_string(self) -> None:
        result = to_decimal("45000.50")
        assert result == Decimal("45000.50")
        assert isinstance(result, Decimal)

    def test_convert_from_int(self) -> None:
        result = to_decimal(50000)
        assert result == Decimal("50000.00")

    def test_convert_from_decimal(self) -> None:
        original = Decimal("123.45")
        result = to_decimal(original)
        assert result == Decimal("123.45")

    def test_reject_invalid_string(self) -> None:
        with pytest.raises(ValueError, match="Cannot convert 'not_a_number' to Decimal"):
            to_decimal("not_a_number")


class TestRoundingCurrency:
    """Verify standard 2-decimal-place rounding with ROUND_HALF_UP (Q-03)."""

    def test_round_half_up_cases(self) -> None:
        # Standard bankers/half-up verification
        assert round_currency(Decimal("10.005")) == Decimal("10.01")
        assert round_currency(Decimal("10.004")) == Decimal("10.00")
        assert round_currency(Decimal("10.000")) == Decimal("10.00")
        assert round_currency(Decimal("0.005")) == Decimal("0.01")


class TestRoundUpToNearestTen:
    """Verify ceiling to multiple of ₹10 for transport quarterly tax (BR-03A)."""

    def test_already_multiple_of_ten(self) -> None:
        assert round_up_to_nearest_ten(Decimal("1500")) == Decimal("1500")
        assert round_up_to_nearest_ten(Decimal("370.00")) == Decimal("370")

    def test_round_up_needed(self) -> None:
        # 375 becomes 380
        assert round_up_to_nearest_ten(Decimal("375")) == Decimal("380")
        # 370.01 has a fractional part, so it rounds up to 380
        assert round_up_to_nearest_ten(Decimal("370.01")) == Decimal("380")
        # 1 becomes 10
        assert round_up_to_nearest_ten(Decimal("1")) == Decimal("10")

    def test_zero_amount(self) -> None:
        assert round_up_to_nearest_ten(Decimal("0")) == Decimal("0")


class TestRoundDownToRupee:
    """Verify flooring to whole rupee for migration refund (BR-08E)."""

    def test_already_whole_rupee(self) -> None:
        assert round_down_to_rupee(Decimal("500.00")) == Decimal("500")

    def test_fraction_is_floored(self) -> None:
        assert round_down_to_rupee(Decimal("500.99")) == Decimal("500")
        assert round_down_to_rupee(Decimal("500.01")) == Decimal("500")
        assert round_down_to_rupee(Decimal("0.85")) == Decimal("0")


class TestCalculatePercentage:
    """Verify exact percentage calculations on currency base."""

    def test_clean_percentages(self) -> None:
        assert calculate_percentage(Decimal("50000"), Decimal("10")) == Decimal("5000.00")
        assert calculate_percentage(Decimal("500000"), Decimal("13")) == Decimal("65000.00")
        assert calculate_percentage(Decimal("100000"), Decimal("18")) == Decimal("18000.00")

    def test_fractional_percentage(self) -> None:
        # 2% of 45000.50 is 900.01
        assert calculate_percentage(Decimal("45000.50"), Decimal("2")) == Decimal("900.01")


class TestValidateNonNegative:
    """Verify validation helper against negative currency values."""

    def test_valid_positive_and_zero(self) -> None:
        validate_non_negative_currency(Decimal("0"), "test_fee")
        validate_non_negative_currency(Decimal("100.50"), "test_fee")

    def test_reject_negative(self) -> None:
        with pytest.raises(ValueError, match="test_fee cannot be negative"):
            validate_non_negative_currency(Decimal("-0.01"), "test_fee")
