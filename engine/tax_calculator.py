# This file handles ALL tax and cess calculations.
# each finction does ONE job. Plain if/elif/else - no tricks.

# ── Constants ──────────────────────────────────────────────────────────────────
# Put all the numbers here at the top so changing a rule = changing one number.

# 2W road tax slabs (BR-01)
TAX_2W_SLAB1_LIMIT = 50000       # up to Rs 50,000
TAX_2W_SLAB1_RATE  = 0.10        # 10%
TAX_2W_SLAB2_LIMIT = 100000      # up to Rs 1,00,000
TAX_2W_SLAB2_RATE  = 0.12        # 12%
TAX_2W_SLAB3_RATE  = 0.18        # 18% above Rs 1,00,000

# LMV_PRIVATE road tax slabs (BR-02)
TAX_LMV_SLAB1_LIMIT = 500000     # up to Rs 5,00,000
TAX_LMV_SLAB1_RATE  = 0.13       # 13%
TAX_LMV_SLAB2_LIMIT = 1000000    # up to Rs 10,00,000
TAX_LMV_SLAB2_RATE  = 0.14       # 14%
TAX_LMV_SLAB3_LIMIT = 2000000    # up to Rs 20,00,000
TAX_LMV_SLAB3_RATE  = 0.17       # 17%
TAX_LMV_SLAB4_RATE  = 0.18       # 18% above Rs 20,00,000

# EV road tax (BR-03)
TAX_EV_RATE_BEFORE_SUNSET = 0.00  # 0% before sunset date
TAX_EV_RATE_AFTER_SUNSET  = 0.05  # 5% on or after sunset date

# Green cess and surcharges (BR-04)
DIESEL_SURCHARGE_RATE   = 0.02    # 2% extra for diesel LMV_PRIVATE
LUXURY_CESS_THRESHOLD   = 2000000 # Rs 20,00,000
LUXURY_CESS_RATE        = 0.01    # 1%
GREEN_TAX_CAR           = 5000    # Rs 5,000 per 5-year renewal for old cars
GREEN_TAX_2W            = 1000    # Rs 1,000 per 5-year renewal for old 2W
OLD_VEHICLE_AGE_YEARS   = 15      # vehicle is "old" after 15 years


# ── BR-01: Road tax for two-wheelers ──────────────────────────────────────────

def calculate_road_tax_2w(price):
    """
    Calculate one-time road tax for a two-wheeler (2W).
    price: ex-showroom price in rupees (a number, e.g. 50000)
    Returns: tax amount in rupees
    """
    if price <= TAX_2W_SLAB1_LIMIT:
        return round(price * TAX_2W_SLAB1_RATE, 2)
    elif price <= TAX_2W_SLAB2_LIMIT:
        return round(price * TAX_2W_SLAB2_RATE, 2)
    else:
        return round(price * TAX_2W_SLAB3_RATE, 2)


# ── BR-02: Road tax for private cars (LMV_PRIVATE) ────────────────────────────

def calculate_road_tax_lmv_private(price):
    """
    Calculate one-time road tax for a private car (LMV_PRIVATE).
    price: ex-showroom price in rupees
    Returns: tax amount in rupees
    """
    if price <= TAX_LMV_SLAB1_LIMIT:
        return round(price * TAX_LMV_SLAB1_RATE, 2)
    elif price <= TAX_LMV_SLAB2_LIMIT:
        return round(price * TAX_LMV_SLAB2_RATE, 2)
    elif price <= TAX_LMV_SLAB3_LIMIT:
        return round(price * TAX_LMV_SLAB3_RATE, 2)
    else:
        return round(price * TAX_LMV_SLAB4_RATE, 2)


# ── BR-03: Road tax for electric vehicles (EV) ────────────────────────────────

def calculate_road_tax_ev(price, registration_date, ev_sunset_date):
    """
    EVs pay 0% tax if registered BEFORE the sunset date.
    EVs pay 5% tax if registered ON or AFTER the sunset date.
    registration_date: string "YYYY-MM-DD"
    ev_sunset_date:    string "YYYY-MM-DD"
    Returns: tax amount in rupees
    """
    if registration_date < ev_sunset_date:
        return 0.0
    else:
        return round(price * TAX_EV_RATE_AFTER_SUNSET, 2)


# ── BR-04: Cess and surcharges ─────────────────────────────────────────────────

def calculate_diesel_surcharge(price, vehicle_class, fuel_type):
    """
    Diesel LMV_PRIVATE pays an extra 2% of price.
    Returns: surcharge amount in rupees (0 if not applicable)
    """
    if vehicle_class == "LMV_PRIVATE" and fuel_type == "DIESEL":
        return round(price * DIESEL_SURCHARGE_RATE, 2)
    return 0.0


def calculate_luxury_cess(price, vehicle_class, fuel_type):
    """
    Vehicles priced ABOVE Rs 20 lakh pay 1% luxury cess.
    EVs are exempt from all cess.
    Returns: luxury cess amount in rupees (0 if not applicable)
    """
    if fuel_type == "ELECTRIC":
        return 0.0   # EVs never pay cess
    if price > LUXURY_CESS_THRESHOLD:
        return round(price * LUXURY_CESS_RATE, 2)
    return 0.0


def calculate_green_tax(vehicle_class, manufacture_date, application_date):
    """
    Vehicles older than 15 years at re-registration pay green tax.
    Green tax is per 5-year renewal: Rs 5,000 for cars, Rs 1,000 for 2W.
    manufacture_date:  string "YYYY-MM-DD"
    application_date:  string "YYYY-MM-DD"
    Returns: green tax amount in rupees (0 if vehicle is under 15 years old)
    """
    # Calculate age of vehicle in years
    manufacture_year = int(manufacture_date[:4])
    application_year = int(application_date[:4])
    age_years = application_year - manufacture_year

    if age_years > OLD_VEHICLE_AGE_YEARS:
        if vehicle_class == "2W":
            return GREEN_TAX_2W
        else:
            return GREEN_TAX_CAR
    return 0.0



# ── Master function: calculate ALL taxes for a private vehicle ─────────────────

def calculate_total_tax_private(vehicle, ev_sunset_date=None, application_date=None):
    """
    Calculates road tax + all cess for a private vehicle (2W, LMV_PRIVATE, EV).
    vehicle: a Vehicle object from models/vehicle.py
    Returns: a dictionary with a breakdown of every charge
    """
    price        = vehicle.ex_showroom_price
    v_class      = vehicle.vehicle_class
    fuel         = vehicle.fuel_type
    reg_date     = vehicle.registration_date
    mfg_date     = vehicle.manufacture_date

    road_tax      = 0.0
    diesel_charge = 0.0
    luxury_cess   = 0.0
    green_tax     = 0.0

    # Step 1 — Road tax (pick the right function based on vehicle class)
    if v_class == "2W":
        road_tax = calculate_road_tax_2w(price)

    elif v_class == "LMV_PRIVATE":
        road_tax = calculate_road_tax_lmv_private(price)

    elif v_class == "EV":
        if ev_sunset_date is None:
            raise ValueError("ev_sunset_date must be provided for EV vehicles")
        road_tax = calculate_road_tax_ev(price, reg_date, ev_sunset_date)

    # Step 2 — Cess (EVs skip all of this — checked inside each function)
    diesel_charge = calculate_diesel_surcharge(price, v_class, fuel)
    luxury_cess   = calculate_luxury_cess(price, v_class, fuel)

    # Step 3 — Green tax (only relevant at re-registration of old vehicles)
    if application_date:
        green_tax = calculate_green_tax(v_class, mfg_date, application_date)

    total = road_tax + diesel_charge + luxury_cess + green_tax

    return {
        "road_tax":       road_tax,
        "diesel_surcharge": diesel_charge,
        "luxury_cess":    luxury_cess,
        "green_tax":      green_tax,
        "total":          round(total, 2)
    }