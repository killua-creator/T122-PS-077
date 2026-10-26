"""High-precision monetary calculation and rounding helpers.

Financial computations in the RTO Engine must always use decimal.Decimal
rather than binary floating-point numbers (float) to prevent precision drift.

Approved Rounding Rules:
- General Currency: Quantized to 2 decimal places (paise) using ROUND_HALF_UP (Q-03).
- Transport Quarterly Tax: Ceiled to the next multiple of ₹10 (BR-03A).
- Interstate Pro-Rata Refund: Floored to the nearest whole rupee (BR-08E).
"""

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Union

NumberLike = Union[str, int, float, Decimal]

TWO_PLACES = Decimal("0.01")
WHOLE_RUPEE = Decimal("1")
TEN_RUPEES = Decimal("10")


def to_decimal(value: NumberLike) -> Decimal:
    """Convert an input value to a Decimal representation safely.

    Integers and strings are converted directly.
    Floats are converted via string representation to avoid IEEE 754 float drift.

    Raises:
        ValueError: If the string cannot be parsed as a valid numeric decimal.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Convert float through str to avoid binary approximation issues
        return Decimal(str(value))
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Cannot convert '{value}' to Decimal") from exc


def round_currency(amount: Decimal) -> Decimal:
    """Round a monetary amount to 2 decimal places (paise) using ROUND_HALF_UP.

    Examples:
        Decimal('10.005') -> Decimal('10.01')
        Decimal('10.004') -> Decimal('10.00')
    """
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round_up_to_nearest_ten(amount: Decimal) -> Decimal:
    """Round up a monetary amount to the next multiple of ₹10 (BR-03A).

    If the amount is already an exact multiple of 10, it is unchanged.
    Otherwise, it rounds upward to the next multiple of 10.

    Examples:
        Decimal('1500')   -> Decimal('1500')
        Decimal('375')    -> Decimal('380')
        Decimal('370.01') -> Decimal('380')
        Decimal('0')      -> Decimal('0')
    """
    if amount <= Decimal("0"):
        return Decimal("0")

    # If already a whole multiple of 10
    remainder = amount % TEN_RUPEES
    if remainder == Decimal("0"):
        return amount.quantize(WHOLE_RUPEE)

    quotient = amount // TEN_RUPEES
    return (quotient + Decimal("1")) * TEN_RUPEES


def round_down_to_rupee(amount: Decimal) -> Decimal:
    """Round down a monetary amount to the whole rupee (BR-08E).

    Truncates fractional paise using ROUND_FLOOR.

    Examples:
        Decimal('500.99') -> Decimal('500')
        Decimal('500.00') -> Decimal('500')
        Decimal('0.85')   -> Decimal('0')
    """
    return amount.quantize(WHOLE_RUPEE, rounding=ROUND_FLOOR)


def calculate_percentage(base: Decimal, rate_percent: NumberLike) -> Decimal:
    """Compute (base * rate_percent / 100) rounded to standard 2-decimal currency.

    Args:
        base: The monetary base amount (e.g. ex-showroom price).
        rate_percent: The percentage rate (e.g. 10 for 10%).

    Returns:
        The resulting monetary value rounded to paise (2 decimal places).
    """
    rate = to_decimal(rate_percent)
    raw_amount = (base * rate) / Decimal("100")
    return round_currency(raw_amount)


def validate_non_negative_currency(amount: Decimal, field_name: str = "amount") -> None:
    """Ensure that a monetary amount is not negative.

    Raises:
        ValueError: If amount is strictly less than zero.
    """
    if amount < Decimal("0"):
        raise ValueError(f"{field_name} cannot be negative (got {amount})")
