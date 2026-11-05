# Holds data for a fitness certificate and a permit.
# These only apply to transport vehicles (LMV_TRANSPORT, HGV, BUS).

class FitnessCertificate:
    def __init__(self, vehicle_id, issue_date, expiry_date, is_new_vehicle=True):
        """
        vehicle_id:     registration mark e.g. "KA01AB0001"
        issue_date:     string "YYYY-MM-DD"
        expiry_date:    string "YYYY-MM-DD"
        is_new_vehicle: True for first certificate (2-year validity)
                        False for renewals (1-year validity)
        """
        self.vehicle_id     = vehicle_id
        self.issue_date     = issue_date
        self.expiry_date    = expiry_date
        self.is_new_vehicle = is_new_vehicle

        # Status
        self.status = "VALID"    # "VALID", "EXPIRED", "FAILED"

        # Inspection tracking
        self.inspection_result  = "PASSED"   # "PASSED" or "FAILED"
        self.retest_deadline    = None        # if failed, free retest before this date
        self.retest_done        = False

        # Late fee (if renewal was applied after expiry)
        self.late_fee = 0.0

    def __str__(self):
        return (f"Fitness({self.vehicle_id}, "
                f"expires={self.expiry_date}, {self.status})")


class Permit:
    def __init__(self, vehicle_id, permit_type, issue_date,
                 expiry_date, annual_renewal_date):
        """
        vehicle_id:          registration mark
        permit_type:         "CONTRACT", "STAGE", or "GOODS"
        issue_date:          string "YYYY-MM-DD"
        expiry_date:         string "YYYY-MM-DD" — 5 years from issue
        annual_renewal_date: string "YYYY-MM-DD" — next annual authorisation due
        """
        self.vehicle_id          = vehicle_id
        self.permit_type         = permit_type
        self.issue_date          = issue_date
        self.expiry_date         = expiry_date
        self.annual_renewal_date = annual_renewal_date

        # Status
        self.status = "VALID"    # "VALID", "EXPIRED", "LAPSED"

    def __str__(self):
        return (f"Permit({self.vehicle_id}, {self.permit_type}, "
                f"expires={self.expiry_date}, {self.status})")