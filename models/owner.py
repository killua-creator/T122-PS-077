# This file represents a person who owns a vehicle and holds a driving licence.

class Owner:
    def __init__(self, owner_id, name, licence_number):

        # Identity
        self.owner_id = owner_id             # unique ID e.g. "OWN001"
        self.name = name                     # full name e.g. "Ravi Kumar"
        self.licence_number = licence_number # driving licence number e.g. "KA0120230012345"

        # Licence status
        self.licence_status = "ACTIVE"       # "ACTIVE", "SUSPENDED", "REVOKED"
        self.licence_suspended_until = None  # date string "YYYY-MM-DD" if suspended

        # Points system — stores a list of point entries
        # Each entry is a small dictionary: {"date": "2024-03-10", "points": 3, "offence": "SPEEDING"}
        self.licence_points = []

        # Vehicles this owner currently owns (list of registration marks)
        self.vehicles = []

    def __str__(self):
        return f"Owner({self.owner_id}, {self.name}, licence={self.licence_status})"