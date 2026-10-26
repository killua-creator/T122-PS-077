"""Domain enumerations for the PS-077 RTO Engine.

Defines all statutory enumerated values for vehicle categories, fuel types,
challan lifecycle stages, permit types, and inspection results.
"""

from enum import Enum


class VehicleClass(str, Enum):
    """Statutory vehicle classification under RTO rules.

    Values:
    - TWO_WHEELER: Two-wheeled private motor vehicle ('2W')
    - LMV_PRIVATE: Light motor vehicle for personal use
    - LMV_TRANSPORT: Light commercial/transport vehicle (e.g., taxi, auto)
    - HGV: Heavy goods vehicle (commercial freight)
    - BUS: Heavy passenger vehicle
    - EV: Electric vehicle (across relevant sub-classes)
    """

    TWO_WHEELER = "2W"
    LMV_PRIVATE = "LMV_PRIVATE"
    LMV_TRANSPORT = "LMV_TRANSPORT"
    HGV = "HGV"
    BUS = "BUS"
    EV = "EV"


class FuelType(str, Enum):
    """Allowed fuel and powertrain options."""

    PETROL = "PETROL"
    DIESEL = "DIESEL"
    ELECTRIC = "ELECTRIC"
    CNG = "CNG"
    HYBRID = "HYBRID"


class ChallanStatus(str, Enum):
    """Lifecycle states of a traffic challan under BR-10.

    - ISSUED: Freshly recorded offence, awaiting action.
    - PAID: Satisfied within the allowed time frame.
    - CONTESTED: Disputed by the owner/driver; clock frozen for 30 days.
    - ESCALATED: Unpaid after 60 days; carries 50% surcharge.
    - COURT_REFERRED: Unpaid after 90 days; accrual stops, vehicle blocked.
    - DISMISSED: Contest upheld; removed from repeat-offence tracking.
    """

    ISSUED = "ISSUED"
    PAID = "PAID"
    CONTESTED = "CONTESTED"
    ESCALATED = "ESCALATED"
    COURT_REFERRED = "COURT_REFERRED"
    DISMISSED = "DISMISSED"


class PermitType(str, Enum):
    """Commercial vehicle permit types under BR-06."""

    CONTRACT = "CONTRACT"
    STAGE = "STAGE"
    GOODS = "GOODS"


class InspectionResult(str, Enum):
    """Vehicle fitness inspection outcome under BR-05."""

    PASS = "PASS"
    FAIL = "FAIL"
