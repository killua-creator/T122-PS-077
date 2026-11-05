# A challan is a traffic fine.
# This class just holds all the data about one challan.

class Challan:
    def __init__(self, challan_id, vehicle_id, offence_code,
                 offence_date, amount, evidence_flag, licence_id=None):
        """
        challan_id:    unique ID e.g. "CHL001"
        vehicle_id:    registration mark of the vehicle e.g. "KA01AB0001"
        offence_code:  e.g. "NO_HELMET", "SPEEDING", "RED_LIGHT", etc.
        offence_date:  string "YYYY-MM-DD"
        amount:        fine amount in rupees
        evidence_flag: "MANUAL" (officer issued) or "CAMERA" (speed cam / CCTV)
        licence_id:    driving licence number if the driver was identified
                       None if driver was not identified at the time
        """

        # Identity
        self.challan_id    = challan_id
        self.vehicle_id    = vehicle_id
        self.licence_id    = licence_id
        self.offence_code  = offence_code
        self.offence_date  = offence_date
        self.evidence_flag = evidence_flag

        # Amount
        self.original_amount  = amount    # the base fine amount
        self.current_amount   = amount    # changes when surcharge is added

        # Status — starts as ISSUED
        self.status = "ISSUED"

        # Escalation tracking
        self.frozen_days   = 0            # days the clock was frozen due to contest
        self.contest_start = None         # date when contest was raised
        self.is_contested  = False

        # Payment
        self.paid_date = None

        # Court referral
        self.court_referred_date = None

        # Licence points this challan carries
        self.licence_points = 0

    def __str__(self):
        return (f"Challan({self.challan_id}, {self.offence_code}, "
                f"Rs {self.current_amount}, {self.status})")