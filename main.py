# Entry point for the RTO Engine.
# Reads commands.txt line by line and runs each command.
#
# Usage:
#   python main.py
#   python main.py data/commands.txt
#   python main.py data/commands.txt outputs/results.txt

import sys
import os
import csv
from datetime import date, timedelta, datetime

# ── Import all models ─────────────────────────────────────────────────────────
from models.vehicle      import Vehicle
from models.owner        import Owner
from models.challan      import Challan
from models.registration import RegistrationSeries

# ── Import all engines ────────────────────────────────────────────────────────
from engine.tax_calculator      import (calculate_total_tax_private,
                                        calculate_quarterly_tax,
                                        get_unpaid_quarters_count,
                                        calculate_road_tax_2w,
                                        calculate_road_tax_lmv_private,
                                        calculate_road_tax_ev)
from engine.registration_engine import (issue_next_mark,
                                        auction_fancy_number,
                                        issue_temp_registration,
                                        next_series_prefix)
from engine.challan_engine      import (get_challan_amount,
                                        pay_challan,
                                        update_challan_status,
                                        contest_challan,
                                        resolve_contest,
                                        apply_document_waiver,
                                        add_licence_points,
                                        check_and_apply_suspension)
from engine.fitness_engine      import (issue_fitness_certificate,
                                        renew_fitness_certificate,
                                        issue_permit,
                                        renew_permit)
from engine.transfer_engine     import (process_transfer,
                                        terminate_hypothecation,
                                        issue_noc,
                                        confirm_noc_utilisation,
                                        calculate_depreciated_price,
                                        calculate_tax_refund)
from engine.report_engine       import (generate_vehicle_dossier,
                                        generate_daily_register,
                                        generate_challan_ageing_report)


# ── In-memory data store ──────────────────────────────────────────────────────
# All data lives in these dictionaries while the program runs.
# Key is always the unique ID.

vehicles  = {}    # { registration_mark: Vehicle }
owners    = {}    # { owner_id: Owner }
challans  = {}    # { challan_id: Challan }
series    = {}    # { series_prefix: RegistrationSeries }
fitness   = {}    # { registration_mark: FitnessCertificate }
permits   = {}    # { registration_mark: Permit }
nocs      = {}    # { noc_id: NOC }
transfers = {}    # { transfer_id: OwnershipTransfer }

# Additional data stores for data pack masters and evaluation outputs
parameters              = {}
fee_master              = {}
offence_master          = {}
series_list             = []
fancy_numbers           = {}
licences                = {}
vehicles_by_id          = {}
applications            = {}
challans_raw            = {}
auction_wins            = {}
issued_challan_ids      = set()
current_active_series_idx = 0
current_stream_date     = "2025-05-01"

registrations_rows       = []
application_results_rows = []
challan_history_rows     = []
licence_points_rows      = []
vehicle_dossier_rows     = []
daily_register_rows      = []
challan_ageing_rows      = []

# Output lines — collected here, written to file at the end
output_lines = []


# ── Output helper ─────────────────────────────────────────────────────────────

def out(message):
    """Print a message and also save it to output_lines."""
    print(message)
    output_lines.append(message)


# ── Command handlers ──────────────────────────────────────────────────────────
# Each function handles ONE command type.
# params is a list of strings — the values after the command name.

def handle_register_owner(params):
    """
    REGISTER_OWNER,owner_id,name,licence_number
    Example: REGISTER_OWNER,OWN001,Ravi Kumar,KA0120230012345
    """
    owner_id, name, licence_number = params[0], params[1], params[2]
    owner = Owner(owner_id, name, licence_number)
    owners[owner_id] = owner
    out(f"[OK] Owner registered: {owner_id} — {name}")


def handle_create_series(params):
    """
    CREATE_SERIES,series_prefix,tier:number,tier:number,...
    Example: CREATE_SERIES,KA01AB,1:786,2:1000,3:9999

    fancy numbers are listed as tier:number pairs after the prefix.
    """
    prefix = params[0]
    fancy  = {}

    for item in params[1:]:
        if ":" in item:
            tier_str, num_str = item.split(":")
            fancy[int(num_str)] = int(tier_str)

    series[prefix] = RegistrationSeries(prefix, fancy_numbers=fancy)
    out(f"[OK] Series created: {prefix} with {len(fancy)} fancy numbers")


def handle_register_vehicle(params):
    """
    REGISTER_VEHICLE,veh_id,series_prefix,class,fuel,price,
                     engine_cc,seating,laden_weight,mfg_date,
                     reg_date,owner_id,state[,ev_sunset_date]

    The veh_id is just used internally to track this command.
    The actual registration mark is issued by the series.
    """
    (veh_id, series_prefix, v_class, fuel,
     price, engine_cc, seating, laden_weight,
     mfg_date, reg_date, owner_id, state) = params[:12]

    # Optional EV sunset date (only needed for EV vehicles)
    ev_sunset_date = params[12] if len(params) > 12 else None

    # Validate series exists
    if series_prefix not in series:
        out(f"[ERROR] Series {series_prefix} not found")
        return

    # Validate owner exists
    if owner_id not in owners:
        out(f"[ERROR] Owner {owner_id} not found")
        return

    # Issue the next registration mark from the series
    s    = series[series_prefix]
    mark = issue_next_mark(s)

    if mark is None:
        out(f"[ERROR] Series {series_prefix} is exhausted — no marks available")
        return

    # Create the vehicle
    vehicle = Vehicle(
        registration_mark   = mark,
        vehicle_class       = v_class,
        ex_showroom_price   = int(price),
        fuel_type           = fuel,
        engine_cc           = int(engine_cc),
        seating             = int(seating),
        laden_weight_tonnes = float(laden_weight),
        manufacture_date    = mfg_date,
        registration_date   = reg_date,
        owner_id            = owner_id,
        state               = state
    )

    # Calculate and record road tax for private vehicles
    private_classes = ["2W", "LMV_PRIVATE", "EV"]
    if v_class in private_classes:
        tax_result = calculate_total_tax_private(vehicle, ev_sunset_date, reg_date)
        vehicle.road_tax_paid = tax_result["road_tax"]
        vehicle.cess_paid     = (tax_result["diesel_surcharge"] +
                                 tax_result["luxury_cess"] +
                                 tax_result["green_tax"])

        out(f"[OK] Vehicle registered: {mark} ({v_class}, {fuel})")
        out(f"     Road Tax : Rs {tax_result['road_tax']:,.2f}")
        if tax_result["diesel_surcharge"] > 0:
            out(f"     Diesel    : Rs {tax_result['diesel_surcharge']:,.2f}")
        if tax_result["luxury_cess"] > 0:
            out(f"     Luxury    : Rs {tax_result['luxury_cess']:,.2f}")
        if tax_result["green_tax"] > 0:
            out(f"     Green Tax : Rs {tax_result['green_tax']:,.2f}")
        out(f"     TOTAL     : Rs {tax_result['total']:,.2f}")
    else:
        # Transport vehicle — quarterly tax shown instead
        q_tax = calculate_quarterly_tax(v_class, int(seating), float(laden_weight))
        out(f"[OK] Vehicle registered: {mark} ({v_class})")
        out(f"     Quarterly Tax : Rs {q_tax:,.0f} per quarter")

    # Add vehicle to the owner's list
    owners[owner_id].vehicles.append(mark)
    vehicles[mark] = vehicle


def handle_issue_challan(params):
    """
    ISSUE_CHALLAN,challan_id,registration_mark,offence_code,
                  offence_date,evidence_flag[,licence_id]
    """
    if len(params) == 1 and (params[0] in challans_raw or params[0].startswith("CH-")):
        handle_issue_challan_cmd(params)
        return

    challan_id    = params[0]
    reg_mark      = params[1]
    offence_code  = params[2]
    offence_date  = params[3]
    evidence_flag = params[4]
    licence_id    = params[5] if len(params) > 5 else None

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    vehicle = vehicles[reg_mark]

    # Get prior challans for this vehicle to check repeat offence
    prior = [c for c in challans.values() if c.vehicle_id == reg_mark]

    # Calculate the fine amount
    amount = get_challan_amount(offence_code, vehicle.vehicle_class, prior)

    # Create the challan
    challan = Challan(
        challan_id    = challan_id,
        vehicle_id    = reg_mark,
        offence_code  = offence_code,
        offence_date  = offence_date,
        amount        = amount,
        evidence_flag = evidence_flag,
        licence_id    = licence_id
    )
    challan.licence_points = 0
    challans[challan_id]   = challan

    # Add licence points to the driver/owner
    owner = owners.get(vehicle.owner_id)
    if owner:
        add_licence_points(owner, offence_code, offence_date)
        suspension_result = check_and_apply_suspension(owner, offence_date)
        if suspension_result == "SUSPENDED":
            out(f"     [!] Licence {owner.licence_number} SUSPENDED until "
                f"{owner.licence_suspended_until}")
        elif suspension_result == "REVOKED":
            out(f"     [!] Licence {owner.licence_number} REVOKED permanently")

    out(f"[OK] Challan issued: {challan_id} | {reg_mark} | "
        f"{offence_code} | Rs {amount:,} | {offence_date}")

    # Drunk driving — immediately court referred, vehicle blocked
    if offence_code == "DRUNK_DRIVING":
        update_challan_status(challan, offence_date)
        vehicle.status = "BLOCKED"
        out(f"     [!] DRUNK DRIVING — {challan_id} COURT_REFERRED immediately")
        out(f"     [!] Vehicle {reg_mark} BLOCKED")


def handle_pay_challan(params):
    """
    PAY_CHALLAN,challan_id,payment_date
    """
    if len(params) >= 2 and (params[0] in challans_raw or params[0].startswith("CH-")):
        handle_pay_challan_cmd(params)
        return

    challan_id   = params[0]
    payment_date = params[1]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    challan = challans[challan_id]

    # Refresh status first — may have escalated by now
    update_challan_status(challan, payment_date)

    success, message = pay_challan(challan, payment_date)
    if success:
        out(f"[OK] {message} | Amount paid: Rs {challan.current_amount:,}")
    else:
        out(f"[ERROR] {message}")


def handle_contest_challan(params):
    """
    CONTEST_CHALLAN,challan_id,contest_date
    """
    if len(params) >= 2 and (params[0] in challans_raw or params[0].startswith("CH-")):
        handle_contest_challan_cmd(params)
        return

    challan_id   = params[0]
    contest_date = params[1]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    success, message = contest_challan(challans[challan_id], contest_date)
    status = "[OK]" if success else "[ERROR]"
    out(f"{status} {message}")


def handle_resolve_contest(params):
    """
    RESOLVE_CONTEST,challan_id,decision,resolution_date
    decision: DISMISSED or UPHELD
    """
    challan_id      = params[0]
    decision        = params[1]
    resolution_date = params[2]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    success, message = resolve_contest(
        challans[challan_id], decision, resolution_date
    )
    status = "[OK]" if success else "[ERROR]"
    out(f"{status} {message}")


def handle_issue_fitness(params):
    """
    ISSUE_FITNESS,registration_mark,inspection_date,is_new_vehicle
    is_new_vehicle: True or False
    """
    reg_mark        = params[0]
    inspection_date = params[1]
    is_new          = params[2].strip().lower() == "true"

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    cert            = issue_fitness_certificate(reg_mark, inspection_date, is_new)
    fitness[reg_mark] = cert
    out(f"[OK] Fitness certificate issued: {reg_mark} | "
        f"Valid until {cert.expiry_date}")


def handle_issue_permit(params):
    """
    ISSUE_PERMIT,registration_mark,permit_type,issue_date
    permit_type: CONTRACT, STAGE, or GOODS
    """
    reg_mark    = params[0]
    permit_type = params[1]
    issue_date  = params[2]

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    has_fitness   = reg_mark in fitness and fitness[reg_mark].status == "VALID"
    has_insurance = True   # simplified — assume insurance valid unless told otherwise

    success, result = issue_permit(
        vehicle_id          = reg_mark,
        permit_type         = permit_type,
        issue_date          = issue_date,
        has_valid_fitness   = has_fitness,
        has_valid_insurance = has_insurance
    )

    if success:
        permits[reg_mark] = result
        out(f"[OK] Permit issued: {reg_mark} | {permit_type} | "
            f"Valid until {result.expiry_date}")
    else:
        out(f"[ERROR] {result}")


def handle_transfer_vehicle(params):
    """
    TRANSFER_VEHICLE,transfer_id,registration_mark,
                     new_owner_id,sale_date,transfer_date
    """
    transfer_id  = params[0]
    reg_mark     = params[1]
    new_owner_id = params[2]
    sale_date    = params[3]
    transfer_date = params[4]

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    if new_owner_id not in owners:
        out(f"[ERROR] New owner {new_owner_id} not found")
        return

    vehicle       = vehicles[reg_mark]
    vehicle_challans = [c for c in challans.values()
                        if c.vehicle_id == reg_mark]

    success, result = process_transfer(
        transfer_id   = transfer_id,
        vehicle       = vehicle,
        challans      = vehicle_challans,
        new_owner_id  = new_owner_id,
        sale_date     = sale_date,
        transfer_date = transfer_date
    )

    if success:
        transfers[transfer_id] = result
        out(f"[OK] Transfer {transfer_id}: {reg_mark} → {new_owner_id} | "
            f"Fee: Rs {result.transfer_fee:,}")
    else:
        out(f"[ERROR] {result}")


def handle_issue_noc(params):
    """
    ISSUE_NOC,noc_id,registration_mark,noc_date,first_registration_date
    """
    noc_id          = params[0]
    reg_mark        = params[1]
    noc_date        = params[2]
    first_reg_date  = params[3]

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    vehicle          = vehicles[reg_mark]
    vehicle_challans = [c for c in challans.values()
                        if c.vehicle_id == reg_mark]

    success, result = issue_noc(
        noc_id                  = noc_id,
        vehicle                 = vehicle,
        challans                = vehicle_challans,
        road_tax_paid           = vehicle.road_tax_paid,
        first_registration_date = first_reg_date,
        noc_date                = noc_date
    )

    if success:
        nocs[noc_id] = result
        out(f"[OK] NOC issued: {noc_id} | {reg_mark} | "
            f"Refund due: Rs {result.refund_amount:,}")
    else:
        out(f"[ERROR] {result}")


def handle_auction_fancy(params):
    """
    AUCTION_FANCY,series_prefix,number,winning_bid
    """
    series_prefix = params[0]
    number        = int(params[1])
    winning_bid   = int(params[2])

    if series_prefix not in series:
        out(f"[ERROR] Series {series_prefix} not found")
        return

    success, result = auction_fancy_number(
        series[series_prefix], number, winning_bid
    )
    status = "[OK]" if success else "[ERROR]"
    out(f"{status} Auction: {series_prefix} | "
        f"Number {number:04d} | Bid Rs {winning_bid:,} | {result}")


def handle_print_dossier(params):
    """
    PRINT_DOSSIER,registration_mark,current_date
    """
    if len(params) >= 2 and (params[0] in vehicles_by_id or params[0].startswith("VEH-")):
        handle_print_dossier_cmd(params)
        return

    reg_mark     = params[0]
    current_date = params[1]

    if reg_mark not in vehicles:
        out(f"[ERROR] Vehicle {reg_mark} not found")
        return

    vehicle          = vehicles[reg_mark]
    owner            = owners.get(vehicle.owner_id)
    vehicle_challans = [c for c in challans.values()
                        if c.vehicle_id == reg_mark]

    report = generate_vehicle_dossier(
        vehicle      = vehicle,
        owner        = owner,
        challans     = vehicle_challans,
        fitness_cert = fitness.get(reg_mark),
        permit       = permits.get(reg_mark),
        current_date = current_date
    )
    output_lines.append(report)


def handle_print_daily_register(params):
    """
    PRINT_DAILY_REGISTER,report_date
    """
    report_date = params[0]
    report      = generate_daily_register(vehicles, report_date)
    output_lines.append(report)


def handle_print_challan_ageing(params):
    """
    PRINT_CHALLAN_AGEING,current_date
    """
    current_date = params[0]
    handle_print_ageing_cmd(params)
    report       = generate_challan_ageing_report(
        list(challans.values()), current_date
    )
    output_lines.append(report)


# ── Helper functions for data pack & evaluation ──────────────────────────────

def count_unpaid_quarters(tax_paid_till, current_date_str):
    """
    Counts unpaid quarters between tax_paid_till and current_date_str.
    """
    if not tax_paid_till or not current_date_str:
        return 2
    try:
        t_paid = date.fromisoformat(tax_paid_till)
        curr   = date.fromisoformat(current_date_str)
    except Exception:
        return 2

    if t_paid >= curr:
        return 0

    next_day = t_paid + timedelta(days=1)
    unpaid = 0
    year = next_day.year
    month = next_day.month
    if month <= 1:
        m = 1
    elif month <= 4:
        m = 4
    elif month <= 7:
        m = 7
    elif month <= 10:
        m = 10
    else:
        m = 1
        year += 1

    q_start = date(year, m, 1)
    while q_start <= curr:
        unpaid += 1
        if q_start.month == 1:
            q_start = date(q_start.year, 4, 1)
        elif q_start.month == 4:
            q_start = date(q_start.year, 7, 1)
        elif q_start.month == 7:
            q_start = date(q_start.year, 10, 1)
        else:
            q_start = date(q_start.year + 1, 1, 1)

    return unpaid


def load_data_pack(data_dir):
    """
    Loads all master CSV files from the specified data directory.
    """
    param_path = os.path.join(data_dir, "parameters.csv")
    if not os.path.exists(param_path):
        return

    # 1. parameters.csv
    with open(param_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            parameters[r["key"].strip()] = r["value"].strip()

    # 2. fee_master.csv
    fee_path = os.path.join(data_dir, "fee_master.csv")
    if os.path.exists(fee_path):
        with open(fee_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                v_cls = r["vehicle_class"].strip()
                fee_master[v_cls] = {
                    k: float(v) for k, v in r.items() if k != "vehicle_class" and v.strip()
                }

    # 3. offence_master.csv
    off_path = os.path.join(data_dir, "offence_master.csv")
    if os.path.exists(off_path):
        with open(off_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                code = r["offence_code"].strip()
                offence_master[code] = {
                    "description": r["description"],
                    "amount_lmv": float(r["amount_lmv"]) if r["amount_lmv"].strip() else 0.0,
                    "amount_other": float(r["amount_other"]) if r["amount_other"].strip() else 0.0,
                    "repeat_amount": float(r["repeat_amount"]) if r["repeat_amount"].strip() else None,
                    "points": int(r["points"]) if r["points"].strip() else 0,
                    "court_referral": r["court_referral"].strip().lower() == "true",
                    "licence_disqualification_months": int(r["licence_disqualification_months"]) if r["licence_disqualification_months"].strip() else 0
                }

    # 4. fancy_numbers.csv
    fn_path = os.path.join(data_dir, "fancy_numbers.csv")
    if os.path.exists(fn_path):
        with open(fn_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                num_int = int(r["number"])
                fancy_numbers[num_int] = {
                    "tier": int(r["tier"]),
                    "reserve_price": float(r["reserve_price"]),
                    "str": r["number"]
                }

    # 5. series.csv
    ser_path = os.path.join(data_dir, "series.csv")
    if os.path.exists(ser_path):
        with open(ser_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            s_rows = list(reader)
            s_rows.sort(key=lambda x: int(x["sequence_order"]))
            fancy_tiers = {n: d["tier"] for n, d in fancy_numbers.items()}
            for r in s_rows:
                prefix = r["series_prefix"].strip()
                s = RegistrationSeries(prefix, fancy_numbers=fancy_tiers)
                s.series_id = r["series_id"].strip()
                s.sequence_order = int(r["sequence_order"])
                s.start_number = int(r["start_number"])
                s.current_number = s.start_number - 1
                s.status = r["status"].strip()
                s.issued_numbers = set()
                series[prefix] = s
                series_list.append(s)

    # 6. licences.csv
    lic_path = os.path.join(data_dir, "licences.csv")
    if os.path.exists(lic_path):
        with open(lic_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                lic_no = r["licence_no"].strip()
                o = Owner(owner_id="", name=r["holder_name"].strip(), licence_number=lic_no)
                o.gender = r["gender"].strip()
                o.issue_date = r["issue_date"].strip()
                o.status_since = r["issue_date"].strip()
                o.mobile = r["mobile"].strip()
                o.suspension_count = 0
                licences[lic_no] = o

    # 7. vehicles.csv
    veh_path = os.path.join(data_dir, "vehicles.csv")
    if os.path.exists(veh_path):
        with open(veh_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                v_id = r["vehicle_id"].strip()
                v_cls = r["vehicle_class"].strip()
                fuel = r["fuel"].strip()
                price = float(r["ex_showroom_price"]) if r["ex_showroom_price"].strip() else 0.0
                gst = float(r["gst_amount"]) if r["gst_amount"].strip() else 0.0
                cc = int(r["engine_cc"]) if r["engine_cc"].strip() else 0
                kw = float(r["motor_kw"]) if r["motor_kw"].strip() else 0.0
                seats = int(r["seating"]) if r["seating"].strip() else 0
                laden = float(r["laden_weight_tonnes"]) if r["laden_weight_tonnes"].strip() else 0.0
                mfg = r["manufacture_date"].strip()
                reg = r["registration_date"].strip()
                state = r["registration_state"].strip()
                mark = r["registration_mark"].strip()
                temp_reg = r["temp_registration_date"].strip()
                owner_id = r["owner_id"].strip()
                owner_name = r["owner_name"].strip()
                owner_lic = r["owner_licence_no"].strip()
                owner_city = r["owner_city"].strip()
                hyp = (r["hypothecated"].strip().lower() == "true")
                financier = r["financier"].strip()
                ins = r["insurance_valid_till"].strip()
                puc = r["puc_valid_till"].strip()
                fit = r["fitness_valid_till"].strip()
                permit_t = r["permit_type"].strip()
                permit_v = r["permit_valid_till"].strip()
                tax_paid = r["tax_paid_till"].strip()

                v = Vehicle(mark, v_cls, price, fuel, cc, seats, laden, mfg, reg, owner_id, state)
                v.vehicle_id = v_id
                v.gst_amount = gst
                v.motor_kw = kw
                v.temp_registration_date = temp_reg
                v.owner_name = owner_name
                v.owner_licence_no = owner_lic
                v.owner_city = owner_city
                v.hypothecated = hyp
                v.financier = financier
                v.insurance_valid_till = ins
                v.puc_valid_till = puc
                v.fitness_valid_till = fit
                v.permit_type = permit_t
                v.permit_valid_till = permit_v
                v.tax_paid_till = tax_paid
                v.hypothecation_noc_received = False

                if mark:
                    vehicles[mark] = v
                    if v_cls in ("2W", "LMV_PRIVATE", "EV"):
                        ev_sunset = parameters.get("ev_sunset_date", "2026-04-01")
                        tax_res = calculate_total_tax_private(v, ev_sunset, reg)
                        v.road_tax_paid = tax_res["road_tax"]
                        v.cess_paid = tax_res["diesel_surcharge"] + tax_res["luxury_cess"] + tax_res["green_tax"]
                vehicles_by_id[v_id] = v

                if owner_id:
                    if owner_id not in owners:
                        if owner_lic in licences:
                            o = licences[owner_lic]
                            o.owner_id = owner_id
                            owners[owner_id] = o
                        else:
                            o = Owner(owner_id, owner_name, owner_lic)
                            owners[owner_id] = o
                    else:
                        o = owners[owner_id]
                    if mark and mark not in o.vehicles:
                        o.vehicles.append(mark)

    # 8. applications.csv
    app_path = os.path.join(data_dir, "applications.csv")
    if os.path.exists(app_path):
        with open(app_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                applications[r["app_id"].strip()] = r

    # 9. prior_offences.csv
    prior_path = os.path.join(data_dir, "prior_offences.csv")
    if os.path.exists(prior_path):
        with open(prior_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                lic_no = r["licence_no"].strip()
                if lic_no in licences:
                    licences[lic_no].licence_points.append({
                        "date": r["offence_date"].strip(),
                        "points": int(r["points"]) if r["points"].strip() else 0,
                        "offence": r["offence_code"].strip()
                    })

    # 10. challans.csv
    chl_path = os.path.join(data_dir, "challans.csv")
    if os.path.exists(chl_path):
        with open(chl_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cid = r["challan_id"].strip()
                if cid not in challans_raw:
                    challans_raw[cid] = r


# ── Official format command handlers ──────────────────────────────────────────

def handle_register(params):
    vehicle_id = params[0]
    reg_date = params[1]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    vehicle.registration_date = reg_date
    v_class = vehicle.vehicle_class

    global current_active_series_idx
    active_series = series_list[current_active_series_idx]
    series_id = active_series.series_id
    mark = None

    if vehicle_id in auction_wins:
        win = auction_wins[vehicle_id]
        number = win["number"]
        mark = active_series.format_mark(number)
        active_series.issued_numbers.add(number)
    else:
        mark = issue_next_mark(active_series)
        if mark is None:
            if current_active_series_idx + 1 < len(series_list):
                current_active_series_idx += 1
                active_series = series_list[current_active_series_idx]
                series_id = active_series.series_id
                mark = issue_next_mark(active_series)
            else:
                out(f"[ERROR] All series exhausted")
                return

    vehicle.registration_mark = mark
    vehicles[mark] = vehicle

    if vehicle.owner_id and vehicle.owner_id in owners:
        owners[vehicle.owner_id].vehicles.append(mark)

    fees = fee_master.get(v_class, {})
    reg_fee = fees.get("registration_fee", 0.0)

    road_tax = 0.0
    diesel_cess = 0.0
    luxury_cess = 0.0
    green_tax = 0.0

    private_classes = ["2W", "LMV_PRIVATE", "EV"]
    if v_class in private_classes:
        ev_sunset = parameters.get("ev_sunset_date", "2026-04-01")
        tax_res = calculate_total_tax_private(vehicle, ev_sunset, reg_date)
        road_tax = tax_res["road_tax"]
        diesel_cess = tax_res["diesel_surcharge"]
        luxury_cess = tax_res["luxury_cess"]
        green_tax = tax_res["green_tax"]

    total_payable = reg_fee + road_tax + diesel_cess + luxury_cess + green_tax

    vehicle.road_tax_paid = road_tax
    vehicle.cess_paid = diesel_cess + luxury_cess + green_tax

    registrations_rows.append({
        "vehicle_id": vehicle_id,
        "registration_date": reg_date,
        "registration_mark": mark,
        "series_id": series_id,
        "registration_fee": f"{reg_fee:.2f}",
        "road_tax": f"{road_tax:.2f}",
        "diesel_cess": f"{diesel_cess:.2f}",
        "luxury_cess": f"{luxury_cess:.2f}",
        "green_tax": f"{green_tax:.2f}",
        "total_payable": f"{total_payable:.2f}",
        "status": "REGISTERED"
    })
    out(f"[OK] REGISTER: {vehicle_id} -> {mark} (Total: Rs {total_payable:.2f})")


def handle_auction(params):
    number = int(params[0])
    vehicle_id = params[1]
    bid = float(params[2])

    global current_active_series_idx
    active_series = series_list[current_active_series_idx]

    if number not in fancy_numbers:
        out(f"[REJECTED] AUCTION: {number:04d} is not a fancy number")
        return

    reserve_price = fancy_numbers[number]["reserve_price"]
    if bid < reserve_price:
        out(f"[REJECTED] AUCTION: Bid Rs {bid:.2f} below reserve Rs {reserve_price:.2f} for {number:04d}")
        return

    active_series.auctioned_numbers[number] = bid
    auction_wins[vehicle_id] = {"number": number, "bid": bid}
    out(f"[OK] AUCTION: Number {number:04d} won by {vehicle_id} with bid Rs {bid:.2f}")


def handle_apply(params):
    app_id = params[0]
    row = applications.get(app_id)
    if not row:
        out(f"[ERROR] Application {app_id} not found")
        return

    app_type = row["app_type"].strip()
    vehicle_id = row["vehicle_id"].strip()
    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found for {app_id}")
        return

    v_class = vehicle.vehicle_class
    fees = fee_master.get(v_class, {})

    decision = "APPROVED"
    reason = ""
    fee = 0.0
    late_fee = 0.0
    valid_from = ""
    valid_till = ""
    refund_amount = 0.0
    fresh_tax = 0.0

    app_date = row["application_date"].strip()

    if app_type == "FITNESS_NEW":
        fee = fees.get("fitness_fee", 0.0)
        if row.get("inspection_result", "").strip() == "FAIL":
            decision = "REJECTED"
            reason = "INSPECTION_FAILED"
            vehicle.last_failed_fitness_date = row.get("inspection_date", "").strip()
            vehicle.retest_count = 0
        else:
            decision = "APPROVED"
            reason = ""
            insp_date_str = row.get("inspection_date", "").strip()
            valid_from = insp_date_str
            insp_d = date.fromisoformat(insp_date_str)
            valid_till = str(insp_d.replace(year=insp_d.year + 2))
            vehicle.fitness_valid_till = valid_till

    elif app_type == "FITNESS_RENEWAL":
        fee = fees.get("fitness_fee", 0.0)
        app_d = date.fromisoformat(app_date)
        exp_d = date.fromisoformat(vehicle.fitness_valid_till) if vehicle.fitness_valid_till else app_d
        days_before_expiry = (exp_d - app_d).days

        if days_before_expiry > 60:
            decision = "REJECTED"
            reason = "OUTSIDE_WINDOW"
        elif row.get("inspection_result", "").strip() == "FAIL":
            decision = "REJECTED"
            reason = "INSPECTION_FAILED"
            vehicle.last_failed_fitness_date = row.get("inspection_date", "").strip()
            vehicle.retest_count = 0
        else:
            decision = "APPROVED"
            reason = ""
            insp_date_str = row.get("inspection_date", "").strip()
            insp_d = date.fromisoformat(insp_date_str)
            valid_from = insp_date_str
            if days_before_expiry >= 0:
                valid_till = str(exp_d.replace(year=exp_d.year + 1))
                late_fee = 0.0
            else:
                days_late = max((insp_d - exp_d).days, 0)
                late_fee = float(min(days_late * 50, 5000))
                valid_till = str(insp_d.replace(year=insp_d.year + 1))
            vehicle.fitness_valid_till = valid_till

    elif app_type == "FITNESS_RETEST":
        insp_date_str = row.get("inspection_date", "").strip()
        insp_d = date.fromisoformat(insp_date_str)
        last_failed = date.fromisoformat(vehicle.last_failed_fitness_date) if getattr(vehicle, "last_failed_fitness_date", None) else None
        retest_days = (insp_d - last_failed).days if last_failed else 999

        if last_failed and retest_days <= 15 and getattr(vehicle, "retest_count", 0) == 0:
            fee = 0.0
        else:
            fee = fees.get("fitness_retest_fee", 0.0)
        vehicle.retest_count = getattr(vehicle, "retest_count", 0) + 1

        if row.get("inspection_result", "").strip() == "FAIL":
            decision = "REJECTED"
            reason = "INSPECTION_FAILED"
        else:
            decision = "APPROVED"
            reason = ""
            valid_from = insp_date_str
            valid_till = str(insp_d.replace(year=insp_d.year + 1))
            vehicle.fitness_valid_till = valid_till

    elif app_type == "PERMIT_NEW":
        fee = fees.get("permit_new_fee", 0.0)
        if not (vehicle.fitness_valid_till and vehicle.fitness_valid_till >= app_date):
            decision = "REJECTED"
            reason = "NO_VALID_FITNESS"
        elif not (row.get("insurance_valid_till", "").strip() and row["insurance_valid_till"].strip() >= app_date):
            decision = "REJECTED"
            reason = "NO_VALID_INSURANCE"
        elif count_unpaid_quarters(vehicle.tax_paid_till, app_date) >= 2:
            decision = "REJECTED"
            reason = "UNPAID_TAX"
        else:
            decision = "APPROVED"
            reason = ""
            valid_from = app_date
            ad = date.fromisoformat(app_date)
            valid_till = str(ad.replace(year=ad.year + 5))
            vehicle.permit_type = row.get("permit_type", "").strip()
            vehicle.permit_valid_till = valid_till

    elif app_type == "PERMIT_RENEWAL":
        base_fee = fees.get("permit_renewal_fee", 0.0)
        if count_unpaid_quarters(vehicle.tax_paid_till, app_date) >= 2:
            decision = "REJECTED"
            reason = "UNPAID_TAX"
            fee = base_fee
        elif not (row.get("insurance_valid_till", "").strip() and row["insurance_valid_till"].strip() >= app_date):
            decision = "REJECTED"
            reason = "NO_VALID_INSURANCE"
            fee = base_fee
        else:
            exp = date.fromisoformat(vehicle.permit_valid_till) if vehicle.permit_valid_till else None
            ad = date.fromisoformat(app_date)
            if exp and (ad - exp).days > 180:
                fee = base_fee * 2
            else:
                fee = base_fee
            decision = "APPROVED"
            reason = ""
            valid_from = app_date
            valid_till = str(ad.replace(year=ad.year + 5))
            vehicle.permit_valid_till = valid_till

    elif app_type == "TRANSFER":
        base_fee = fees.get("transfer_fee", 0.0)
        if vehicle.hypothecated and not getattr(vehicle, "hypothecation_noc_received", False):
            decision = "REJECTED"
            reason = "HYPOTHECATED"
            fee = base_fee
        else:
            for c in challans.values():
                if c.vehicle_id == vehicle_id:
                    update_challan_status(c, app_date)

            pending_total = sum(
                c.current_amount for c in challans.values()
                if c.vehicle_id == vehicle_id and c.status in ("ISSUED", "ESCALATED")
            )
            if pending_total > 2000.0:
                decision = "REJECTED"
                reason = "PENDING_CHALLANS_EXCEEDED"
                fee = base_fee
            elif vehicle.status == "BLOCKED":
                decision = "REJECTED"
                reason = "VEHICLE_BLOCKED"
                fee = base_fee
            else:
                sale_d = date.fromisoformat(row["sale_date"].strip())
                transfer_d = date.fromisoformat(app_date)
                gap_days = (transfer_d - sale_d).days
                if gap_days > 30:
                    extra_days = gap_days - 30
                    delay_months = ((extra_days - 1) // 30) + 1
                    late_fee = float(delay_months * 300)
                else:
                    late_fee = 0.0
                fee = base_fee
                decision = "APPROVED"
                reason = ""
                valid_from = app_date
                vehicle.owner_id = row["new_owner_id"].strip()
                vehicle.owner_name = row["new_owner_name"].strip()
                vehicle.owner_licence_no = row["new_owner_licence_no"].strip()

    elif app_type == "NOC":
        fee = fees.get("noc_fee", 0.0)
        pending_challans = [
            c for c in challans.values()
            if c.vehicle_id == vehicle_id and c.status in ("ISSUED", "ESCALATED", "COURT_REFERRED")
        ]
        if pending_challans:
            decision = "REJECTED"
            reason = "PENDING_CHALLANS"
        else:
            decision = "APPROVED"
            reason = ""
            first_reg = vehicle.registration_date
            refund = calculate_tax_refund(vehicle.road_tax_paid, first_reg, app_date)
            refund_amount = float(refund)
            valid_from = app_date
            vehicle.noc_issued_date = app_date
            vehicle.noc_refund_amount = refund_amount
            vehicle.noc_destination_state = row.get("destination_state", "").strip()

    elif app_type == "REREGISTER":
        fee = fees.get("registration_fee", 0.0)
        first_reg = row.get("first_registration_date", "").strip() or vehicle.registration_date
        depreciated_price = calculate_depreciated_price(vehicle.ex_showroom_price, first_reg, app_date)
        if v_class == "2W":
            fresh_tax = calculate_road_tax_2w(depreciated_price)
        elif v_class == "LMV_PRIVATE":
            fresh_tax = calculate_road_tax_lmv_private(depreciated_price)
        elif v_class == "EV":
            ev_sunset = parameters.get("ev_sunset_date", "2026-04-01")
            fresh_tax = calculate_road_tax_ev(depreciated_price, app_date, ev_sunset)
        else:
            fresh_tax = 0.0
        decision = "APPROVED"
        reason = ""
        valid_from = app_date
        ad = date.fromisoformat(app_date)
        valid_till = str(ad.replace(year=ad.year + 15))

    application_results_rows.append({
        "app_id": app_id,
        "app_type": app_type,
        "vehicle_id": vehicle_id,
        "decision": decision,
        "reason": reason,
        "fee": f"{fee:.2f}",
        "late_fee": f"{late_fee:.2f}",
        "valid_from": valid_from,
        "valid_till": valid_till,
        "refund_amount": f"{refund_amount:.2f}",
        "fresh_tax": f"{fresh_tax:.2f}"
    })
    out(f"[OK] APPLY: {app_id} {app_type} for {vehicle_id} -> {decision} {reason}")


def handle_hyp_noc(params):
    vehicle_id = params[0]
    financier = params[1]
    noc_date = params[2]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    vehicle.hypothecation_noc_received = True
    vehicle.hypothecation_noc_date = noc_date
    out(f"[OK] HYP_NOC received for {vehicle_id} from {financier}")


def handle_hyp_terminate(params):
    vehicle_id = params[0]
    term_date = params[1]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    if not getattr(vehicle, "hypothecation_noc_received", False):
        out(f"[REJECTED] HYP_TERMINATE: Financier NOC not received for {vehicle_id}")
        return

    vehicle.hypothecated = False
    vehicle.financier = ""
    out(f"[OK] HYP_TERMINATE: Hypothecation terminated for {vehicle_id}")


def handle_pay_tax(params):
    vehicle_id = params[0]
    q_start_str = params[1]
    pay_date_str = params[2]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    v_class = vehicle.vehicle_class
    seating = vehicle.seating
    weight = vehicle.laden_weight_tonnes

    base_tax = calculate_quarterly_tax(v_class, seating, weight)

    q_start = date.fromisoformat(q_start_str)
    pay_date = date.fromisoformat(pay_date_str)
    days_late = (pay_date - q_start).days

    late_fee = 0.0
    if days_late > 0:
        months_late = ((days_late - 1) // 30) + 1
        rate = min(months_late * 0.02, 0.20)
        late_fee = round(base_tax * rate, 2)

    total = base_tax + late_fee

    year = q_start.year
    if q_start.month == 1:
        q_end = f"{year}-03-31"
    elif q_start.month == 4:
        q_end = f"{year}-06-30"
    elif q_start.month == 7:
        q_end = f"{year}-09-30"
    else:
        q_end = f"{year}-12-31"

    vehicle.tax_paid_till = q_end
    out(f"[OK] PAY_TAX: {vehicle_id} paid Q starting {q_start_str} (Rs {total:.2f}, Late fee: Rs {late_fee:.2f})")


def handle_issue_challan_cmd(params):
    challan_id = params[0]

    if challan_id in issued_challan_ids:
        out(f"[INFO] Ignoring duplicate challan {challan_id}")
        return

    if challan_id not in challans_raw:
        out(f"[ERROR] Challan {challan_id} not found in master")
        return

    raw = challans_raw[challan_id]
    vehicle_id = raw["vehicle_id"]
    offence_code = raw["offence_code"]
    offence_ts = raw["offence_ts"]
    offence_date = offence_ts[:10]
    driver_lic = raw.get("driver_licence_no", "").strip()
    evidence = raw.get("evidence", "").strip()

    if offence_code not in offence_master:
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": vehicle_id,
            "status": "REJECTED",
            "status_ts": offence_ts,
            "amount_due": "0.00",
            "points_applied": "0",
            "licence_no": ""
        })
        issued_challan_ids.add(challan_id)
        out(f"[REJECTED] Unknown offence code {offence_code} for challan {challan_id}")
        return

    off_info = offence_master[offence_code]
    vehicle = vehicles_by_id.get(vehicle_id)
    v_class = vehicle.vehicle_class if vehicle else "LMV_PRIVATE"

    prior = [c for c in challans.values() if c.vehicle_id == vehicle_id]
    amount = get_challan_amount(offence_code, v_class, prior, offence_date)

    points = off_info["points"]
    licence_target = driver_lic
    if not licence_target and evidence == "CAMERA" and vehicle and vehicle.owner_licence_no:
        licence_target = vehicle.owner_licence_no

    challan = Challan(
        challan_id = challan_id,
        vehicle_id = vehicle_id,
        offence_code = offence_code,
        offence_date = offence_date,
        amount = amount,
        evidence_flag = evidence,
        licence_id = licence_target
    )
    challan.offence_ts = offence_ts
    challan.driver_licence_no = driver_lic
    challan.evidence = evidence
    challan.licence_points = points
    challans[challan_id] = challan
    issued_challan_ids.add(challan_id)

    if licence_target and points > 0:
        lic_owner = licences.get(licence_target)
        if lic_owner:
            add_licence_points(lic_owner, offence_code, offence_date)
            check_and_apply_suspension(lic_owner, offence_date)

    disq_months = off_info["licence_disqualification_months"]
    if licence_target and disq_months > 0:
        lic_owner = licences.get(licence_target)
        if lic_owner and lic_owner.licence_status == "ACTIVE":
            lic_owner.licence_status = "DISQUALIFIED"
            lic_owner.status_since = offence_date

    if off_info["court_referral"]:
        challan.status = "COURT_REFERRED"
        challan.court_referred_date = offence_date
        if vehicle:
            vehicle.status = "BLOCKED"
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": vehicle_id,
            "status": "COURT_REFERRED",
            "status_ts": offence_ts,
            "amount_due": f"{amount:.2f}",
            "points_applied": str(points),
            "licence_no": licence_target or ""
        })
        out(f"[OK] ISSUE_CHALLAN: {challan_id} COURT_REFERRED (Vehicle BLOCKED)")
    else:
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": vehicle_id,
            "status": "ISSUED",
            "status_ts": offence_ts,
            "amount_due": f"{amount:.2f}",
            "points_applied": str(points),
            "licence_no": licence_target or ""
        })
        out(f"[OK] ISSUE_CHALLAN: {challan_id} ISSUED (Rs {amount:.2f})")


def handle_pay_challan_cmd(params):
    challan_id = params[0]
    payment_ts = params[1]
    pay_date_str = payment_ts[:10]

    if challan_id not in challans:
        out(f"[REJECTED] UNKNOWN_CHALLAN: {challan_id} has not been issued yet")
        return

    challan = challans[challan_id]
    if challan.status in ("PAID", "DISMISSED", "WAIVED", "REJECTED"):
        out(f"[ERROR] Challan {challan_id} already closed with status {challan.status}")
        return

    if challan.status == "COURT_REFERRED":
        out(f"[ERROR] Challan {challan_id} is COURT_REFERRED and cannot be paid")
        return

    offence_d = date.fromisoformat(challan.offence_date)
    pay_d = date.fromisoformat(pay_date_str)
    effective_days = (pay_d - offence_d).days - challan.frozen_days

    if effective_days > 60 and challan.status == "ISSUED":
        escl_date = offence_d + timedelta(days=61 + challan.frozen_days)
        escl_ts = f"{escl_date} 00:00:00"
        surcharged_amount = round(challan.original_amount * 1.5, 2)
        challan.current_amount = surcharged_amount
        challan.status = "ESCALATED"
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": challan.vehicle_id,
            "status": "ESCALATED",
            "status_ts": escl_ts,
            "amount_due": f"{surcharged_amount:.2f}",
            "points_applied": "0",
            "licence_no": challan.licence_id or ""
        })

    amount_paid = challan.current_amount
    challan.status = "PAID"
    challan.paid_date = pay_date_str
    challan_history_rows.append({
        "challan_id": challan_id,
        "vehicle_id": challan.vehicle_id,
        "status": "PAID",
        "status_ts": payment_ts,
        "amount_due": f"{amount_paid:.2f}",
        "points_applied": "0",
        "licence_no": challan.licence_id or ""
    })
    out(f"[OK] PAY_CHALLAN: {challan_id} PAID (Rs {amount_paid:.2f})")


def handle_contest_challan_cmd(params):
    challan_id = params[0]
    contest_date = params[1]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    challan = challans[challan_id]
    challan.is_contested = True
    challan.contest_start = contest_date

    challan_history_rows.append({
        "challan_id": challan_id,
        "vehicle_id": challan.vehicle_id,
        "status": "CONTESTED",
        "status_ts": f"{contest_date} 00:00:00",
        "amount_due": f"{challan.current_amount:.2f}",
        "points_applied": "0",
        "licence_no": challan.licence_id or ""
    })
    out(f"[OK] CONTEST_CHALLAN: {challan_id} CONTESTED")


def handle_decide_contest(params):
    challan_id = params[0]
    decision = params[1].strip().upper()
    decide_date = params[2]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    challan = challans[challan_id]
    c_start = date.fromisoformat(challan.contest_start) if challan.contest_start else date.fromisoformat(decide_date)
    d_date = date.fromisoformat(decide_date)
    frozen = min((d_date - c_start).days, 30)
    challan.frozen_days += frozen
    challan.is_contested = False
    challan.contest_start = None

    if decision == "DISMISSED":
        challan.status = "DISMISSED"
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": challan.vehicle_id,
            "status": "DISMISSED",
            "status_ts": f"{decide_date} 00:00:00",
            "amount_due": "0.00",
            "points_applied": "0",
            "licence_no": challan.licence_id or ""
        })
        out(f"[OK] DECIDE_CONTEST: {challan_id} DISMISSED")
    else:
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": challan.vehicle_id,
            "status": "UPHELD",
            "status_ts": f"{decide_date} 00:00:00",
            "amount_due": f"{challan.current_amount:.2f}",
            "points_applied": "0",
            "licence_no": challan.licence_id or ""
        })
        out(f"[OK] DECIDE_CONTEST: {challan_id} UPHELD")


def handle_produce_docs(params):
    challan_id = params[0]
    doc_type = params[1]
    doc_valid_from = params[2]
    doc_valid_till = params[3]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    challan = challans[challan_id]
    offence_d = date.fromisoformat(challan.offence_date)
    v_from = date.fromisoformat(doc_valid_from)
    v_till = date.fromisoformat(doc_valid_till)

    if v_from <= offence_d <= v_till:
        challan.status = "WAIVED"
        challan_history_rows.append({
            "challan_id": challan_id,
            "vehicle_id": challan.vehicle_id,
            "status": "WAIVED",
            "status_ts": f"{current_stream_date} 00:00:00",
            "amount_due": "0.00",
            "points_applied": "0",
            "licence_no": challan.licence_id or ""
        })
        out(f"[OK] PRODUCE_DOCS: {challan_id} WAIVED")
    else:
        out(f"[REJECTED] PRODUCE_DOCS: Documents invalid for {challan_id}")


def handle_nominate_driver(params):
    challan_id = params[0]
    nominated_lic = params[1]
    nominate_date = params[2]

    if challan_id not in challans:
        out(f"[ERROR] Challan {challan_id} not found")
        return

    challan = challans[challan_id]
    offence_d = date.fromisoformat(challan.offence_date)
    nom_d = date.fromisoformat(nominate_date)

    if (nom_d - offence_d).days <= 15:
        old_lic = challan.licence_id
        if old_lic and old_lic in licences:
            licences[old_lic].licence_points = [
                p for p in licences[old_lic].licence_points
                if not (p["date"] == challan.offence_date and p["offence"] == challan.offence_code)
            ]
        challan.licence_id = nominated_lic
        if nominated_lic in licences and challan.licence_points > 0:
            licences[nominated_lic].licence_points.append({
                "date": challan.offence_date,
                "points": challan.licence_points,
                "offence": challan.offence_code
            })
            check_and_apply_suspension(licences[nominated_lic], nominate_date)
        out(f"[OK] NOMINATE_DRIVER: Points reassigned to {nominated_lic}")
    else:
        out(f"[REJECTED] NOMINATE_DRIVER: After 15 days, points remain with owner")


def handle_noc_utilised(params):
    vehicle_id = params[0]
    new_state = params[1]
    util_date = params[2]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    noc_issued = getattr(vehicle, "noc_issued_date", None)
    if not noc_issued:
        out(f"[ERROR] NOC not issued for {vehicle_id}")
        return

    n_date = date.fromisoformat(noc_issued)
    u_date = date.fromisoformat(util_date)
    days_gap = (u_date - n_date).days

    if days_gap <= 365:
        vehicle.noc_refund_released = True
        out(f"[OK] NOC_UTILISED: Refund released for {vehicle_id} (Rs {getattr(vehicle, 'noc_refund_amount', 0.0):.2f})")
    else:
        vehicle.noc_refund_released = False
        out(f"[REJECTED] NOC_UTILISED: Beyond 12 months for {vehicle_id}")


def handle_print_dossier_cmd(params):
    vehicle_id = params[0]
    as_of_date = params[1]

    vehicle = vehicles_by_id.get(vehicle_id)
    if not vehicle:
        out(f"[ERROR] Vehicle {vehicle_id} not found")
        return

    pending_challans = [
        c for c in challans.values()
        if c.vehicle_id == vehicle_id and c.status in ("ISSUED", "ESCALATED", "COURT_REFERRED")
    ]
    pending_amount = sum(c.current_amount for c in pending_challans)

    service_status = "OK"
    if vehicle.status == "BLOCKED":
        service_status = "BLOCKED"
    else:
        curr = date.fromisoformat(as_of_date)
        if vehicle.temp_registration_date and not vehicle.registration_mark:
            t_date = date.fromisoformat(vehicle.temp_registration_date)
            if (curr - t_date).days > 30:
                service_status = "NON_COMPLIANT"

        if vehicle.vehicle_class in ("LMV_TRANSPORT", "HGV", "BUS"):
            if vehicle.fitness_valid_till:
                f_date = date.fromisoformat(vehicle.fitness_valid_till)
                if f_date < curr:
                    service_status = "NON_COMPLIANT"
            else:
                service_status = "NON_COMPLIANT"

            if vehicle.permit_valid_till:
                p_date = date.fromisoformat(vehicle.permit_valid_till)
                if p_date < curr:
                    service_status = "NON_COMPLIANT"
            else:
                service_status = "NON_COMPLIANT"

            if count_unpaid_quarters(vehicle.tax_paid_till, as_of_date) >= 2:
                service_status = "NON_COMPLIANT"

    vehicle_dossier_rows.append({
        "as_of_date": as_of_date,
        "vehicle_id": vehicle_id,
        "registration_mark": vehicle.registration_mark or "",
        "owner_id": vehicle.owner_id or "",
        "road_tax_paid": f"{vehicle.road_tax_paid:.2f}",
        "tax_paid_till": vehicle.tax_paid_till or "",
        "fitness_valid_till": vehicle.fitness_valid_till or "",
        "permit_valid_till": vehicle.permit_valid_till or "",
        "pending_challan_amount": f"{pending_amount:.2f}",
        "service_status": service_status
    })
    out(f"[OK] PRINT_DOSSIER: {vehicle_id} ({service_status})")


def handle_print_register_cmd(params):
    rep_date = params[0]

    matching = [
        v for v in vehicles.values()
        if v.registration_date == rep_date and v.registration_mark
    ]
    matching.sort(key=lambda x: x.registration_mark)

    for v in matching:
        tot = v.road_tax_paid + v.cess_paid
        fees = fee_master.get(v.vehicle_class, {})
        tot += fees.get("registration_fee", 0.0)

        daily_register_rows.append({
            "register_date": rep_date,
            "registration_mark": v.registration_mark,
            "vehicle_id": getattr(v, "vehicle_id", ""),
            "vehicle_class": v.vehicle_class,
            "total_payable": f"{tot:.2f}"
        })
    out(f"[OK] PRINT_REGISTER: {rep_date} ({len(matching)} vehicles)")


def handle_print_ageing_cmd(params):
    as_of_date = params[0]
    as_of_d = date.fromisoformat(as_of_date)

    unpaid = []
    for c in challans.values():
        offence_d = date.fromisoformat(c.offence_date)
        if offence_d > as_of_d:
            continue
        if c.paid_date and date.fromisoformat(c.paid_date) <= as_of_d:
            continue
        if c.status in ("DISMISSED", "WAIVED", "REJECTED"):
            continue

        effective_days = (as_of_d - offence_d).days - c.frozen_days

        status = c.status
        if c.is_contested:
            status = "CONTESTED"
        elif effective_days > 90 or c.offence_code == "DRUNK_DRIVING":
            status = "COURT_REFERRED"
        elif effective_days > 60:
            status = "ESCALATED"
        else:
            status = "ISSUED"

        amount_due = c.original_amount
        if status in ("ESCALATED", "COURT_REFERRED"):
            amount_due = round(c.original_amount * 1.5, 2)

        unpaid.append({
            "as_of_date": as_of_date,
            "challan_id": c.challan_id,
            "vehicle_id": c.vehicle_id,
            "status": status,
            "days_outstanding": str(max(effective_days, 0)),
            "amount_due": f"{amount_due:.2f}"
        })

    unpaid.sort(key=lambda x: x["challan_id"])
    challan_ageing_rows.extend(unpaid)
    out(f"[OK] PRINT_AGEING: {as_of_date} ({len(unpaid)} unpaid challans)")


def generate_licence_points():
    """
    State of every licence that has any points, as of the final command.
    """
    as_of_date = parameters.get("as_of_date", "2026-11-04")
    as_of_d = date.fromisoformat(as_of_date)
    if as_of_d.month == 2 and as_of_d.day == 29:
        cutoff = as_of_d.replace(year=as_of_d.year - 2, day=28)
    else:
        cutoff = as_of_d.replace(year=as_of_d.year - 2)

    for lic_no, owner in sorted(licences.items()):
        if not owner.licence_points:
            continue

        pts_in_window = sum(
            p["points"] for p in owner.licence_points
            if date.fromisoformat(p["date"][:10]) > cutoff
        )

        status_since = getattr(owner, "status_since", getattr(owner, "issue_date", ""))

        licence_points_rows.append({
            "licence_no": lic_no,
            "points_in_window": str(pts_in_window),
            "suspension_count": str(getattr(owner, "suspension_count", 0)),
            "licence_status": owner.licence_status,
            "status_since": status_since
        })


def write_csv(filepath, rows, fieldnames):
    """Writes list of dicts to CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ── Command dispatcher ────────────────────────────────────────────────────────
# Maps each command string to its handler function.

COMMANDS = {
    # Legacy commands
    "REGISTER_OWNER":        handle_register_owner,
    "CREATE_SERIES":         handle_create_series,
    "REGISTER_VEHICLE":      handle_register_vehicle,
    "ISSUE_CHALLAN":         handle_issue_challan,
    "PAY_CHALLAN":           handle_pay_challan,
    "CONTEST_CHALLAN":       handle_contest_challan,
    "RESOLVE_CONTEST":       handle_resolve_contest,
    "ISSUE_FITNESS":         handle_issue_fitness,
    "ISSUE_PERMIT":          handle_issue_permit,
    "TRANSFER_VEHICLE":      handle_transfer_vehicle,
    "ISSUE_NOC":             handle_issue_noc,
    "AUCTION_FANCY":         handle_auction_fancy,
    "PRINT_DOSSIER":         handle_print_dossier,
    "PRINT_DAILY_REGISTER":  handle_print_daily_register,
    "PRINT_CHALLAN_AGEING":  handle_print_challan_ageing,

    # Official evaluation commands
    "REGISTER":              handle_register,
    "AUCTION":               handle_auction,
    "APPLY":                 handle_apply,
    "HYP_NOC":               handle_hyp_noc,
    "HYP_TERMINATE":         handle_hyp_terminate,
    "PAY_TAX":               handle_pay_tax,
    "DECIDE_CONTEST":        handle_decide_contest,
    "PRODUCE_DOCS":          handle_produce_docs,
    "NOMINATE_DRIVER":       handle_nominate_driver,
    "NOC_UTILISED":          handle_noc_utilised,
    "PRINT_REGISTER":        handle_print_register_cmd,
    "PRINT_AGEING":          handle_print_ageing_cmd,
}


# ── Command file reader ───────────────────────────────────────────────────────

def run_command_file(filepath):
    """
    Reads a command file line by line and executes each command.
    """
    global current_stream_date
    out(f"RTO Engine starting — reading {filepath}")
    out("=" * 60)

    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Split on pipe or comma
            if "|" in line:
                parts = line.split("|")
            else:
                parts = line.split(",")

            command = parts[0].strip().upper()
            params  = [p.strip() for p in parts[1:]]

            for p in params:
                if len(p) >= 10 and p[4] == "-" and p[7] == "-":
                    current_stream_date = p[:10]

            # Look up the handler
            handler = COMMANDS.get(command)

            if handler is None:
                out(f"[LINE {line_num}] Unknown command: {command}")
                continue

            # Run it — catch errors so one bad line doesn't crash everything
            try:
                handler(params)
            except Exception as e:
                out(f"[LINE {line_num}] ERROR in {command}: {e}")

    out("=" * 60)
    out("RTO Engine finished.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Default paths
    data_dir    = "data"
    input_file  = "data/commands.txt"
    output_dir  = "outputs"
    output_file = "outputs/results.txt"

    # Allow command-line overrides:
    # python main.py
    # python main.py data/ outputs/
    # python main.py data/commands.txt
    # python main.py data/commands.txt outputs/results.txt
    if len(sys.argv) >= 2:
        arg1 = sys.argv[1]
        if os.path.isdir(arg1):
            data_dir = arg1
            input_file = os.path.join(data_dir, "commands.txt")
        else:
            input_file = arg1
            data_dir = os.path.dirname(input_file) or "data"

    if len(sys.argv) >= 3:
        arg2 = sys.argv[2]
        if os.path.isdir(arg2) or not arg2.endswith(".txt"):
            output_dir = arg2
            output_file = os.path.join(output_dir, "results.txt")
        else:
            output_file = arg2
            output_dir = os.path.dirname(output_file) or "outputs"

    # Make sure output directories exist
    os.makedirs(output_dir, exist_ok=True)

    # Load master CSV data if present
    load_data_pack(data_dir)

    # Run all commands
    run_command_file(input_file)

    # Generate final licence points summary
    generate_licence_points()

    # Write evaluation CSV outputs (in output_dir and root)
    csv_outputs = [
        ("registrations.csv", registrations_rows, [
            "vehicle_id", "registration_date", "registration_mark", "series_id",
            "registration_fee", "road_tax", "diesel_cess", "luxury_cess",
            "green_tax", "total_payable", "status"
        ]),
        ("application_results.csv", application_results_rows, [
            "app_id", "app_type", "vehicle_id", "decision", "reason",
            "fee", "late_fee", "valid_from", "valid_till", "refund_amount", "fresh_tax"
        ]),
        ("challan_history.csv", challan_history_rows, [
            "challan_id", "vehicle_id", "status", "status_ts", "amount_due",
            "points_applied", "licence_no"
        ]),
        ("licence_points.csv", licence_points_rows, [
            "licence_no", "points_in_window", "suspension_count", "licence_status", "status_since"
        ]),
        ("vehicle_dossier.csv", vehicle_dossier_rows, [
            "as_of_date", "vehicle_id", "registration_mark", "owner_id",
            "road_tax_paid", "tax_paid_till", "fitness_valid_till", "permit_valid_till",
            "pending_challan_amount", "service_status"
        ]),
        ("daily_register.csv", daily_register_rows, [
            "register_date", "registration_mark", "vehicle_id", "vehicle_class", "total_payable"
        ]),
        ("challan_ageing.csv", challan_ageing_rows, [
            "as_of_date", "challan_id", "vehicle_id", "status", "days_outstanding", "amount_due"
        ]),
    ]

    for fname, rows, fields in csv_outputs:
        write_csv(os.path.join(output_dir, fname), rows, fields)

    # Write results to file
    with open(output_file, "w") as f:
        f.write("\n".join(output_lines))

    print(f"\nResults saved to {output_file} and evaluation CSVs generated in {output_dir}/")