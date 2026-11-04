# This file represents a single vehicle in the RTO system.
# Think of this class as a form — it just holds all the information about one vehicle.

class Vehicle:
    def __init__(self, registration_mark, vehicle_class, ex_showroom_price,
                 fuel_type, engine_cc, seating, laden_weight_tonnes,
                 manufacture_date, registration_date, owner_id, state):

        # Basic identity
        self.registration_mark = registration_mark   # e.g. "KA01AB0001"
        self.vehicle_class = vehicle_class           # "2W", "LMV_PRIVATE", "LMV_TRANSPORT", "HGV", "BUS", "EV"
        self.ex_showroom_price = ex_showroom_price   # in rupees, as a number e.g. 500000

        # Engine and physical details
        self.fuel_type = fuel_type                   # "PETROL", "DIESEL", "ELECTRIC"
        self.engine_cc = engine_cc                   # engine size in cc (0 for EVs)
        self.seating = seating                       # number of seats (used for BUS and LMV_TRANSPORT tax)
        self.laden_weight_tonnes = laden_weight_tonnes  # used for HGV tax calculation

        # Dates — store as strings "YYYY-MM-DD" for now, easy to compare
        self.manufacture_date = manufacture_date     # e.g. "2020-03-15"
        self.registration_date = registration_date   # e.g. "2024-01-10"

        # Ownership and location
        self.owner_id = owner_id                     # links to an Owner object
        self.state = state                           # e.g. "KA" for Karnataka

        # Status — starts as ACTIVE when permanently registered
        self.status = "ACTIVE"

        # Tax and financial records (we will fill these later)
        self.road_tax_paid = 0        # total road tax paid in rupees
        self.cess_paid = 0            # total cess paid in rupees

        # Fitness and permit (we will fill these later)
        self.fitness_certificate = None
        self.permit = None

        # Hypothecation — is there a bank loan on this vehicle?
        self.hypothecation = None     # None means no loan. Will store financier name if under loan.

    def __str__(self):
        # This lets you print a vehicle and see something useful
        return f"Vehicle({self.registration_mark}, {self.vehicle_class}, {self.status})"