# Quick check that our classes work before we move on

from models.vehicle import Vehicle
from models.owner import Owner

# Create a test owner
owner1 = Owner(
    owner_id="OWN001",
    name="Ravi Kumar",
    licence_number="KA0120230012345"
)

# Create a test vehicle
vehicle1 = Vehicle(
    registration_mark="KA01AB0001",
    vehicle_class="LMV_PRIVATE",
    ex_showroom_price=800000,       # Rs 8 lakh
    fuel_type="PETROL",
    engine_cc=1200,
    seating=5,
    laden_weight_tonnes=0,
    manufacture_date="2023-01-15",
    registration_date="2023-02-01",
    owner_id="OWN001",
    state="KA"
)

# Print them to check everything works
print(owner1)
print(vehicle1)
print("Owner ID on vehicle:", vehicle1.owner_id)
print("Vehicle price:", vehicle1.ex_showroom_price)