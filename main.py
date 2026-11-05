# Entry point for the RTO Engine.
# Reads commands.txt line by line and runs each command.
#
# Usage:
#   python main.py
#   python main.py data/commands.txt
#   python main.py data/commands.txt outputs/results.txt

import sys
import os
from datetime import date

# ── Import all models ─────────────────────────────────────────────────────────
from models.vehicle      import Vehicle
from models.owner        import Owner
from models.challan      import Challan
from models.registration import RegistrationSeries

# ── Import all engines ────────────────────────────────────────────────────────
from engine.tax_calculator      import (calculate_total_tax_private,
                                        calculate_quarterly_tax,
                                        get_unpaid_quarters_count)
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
                                        confirm_noc_utilisation)
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
    report       = generate_challan_ageing_report(
        list(challans.values()), current_date
    )
    output_lines.append(report)


# ── Command dispatcher ────────────────────────────────────────────────────────
# Maps each command string to its handler function.

COMMANDS = {
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
}


# ── Command file reader ───────────────────────────────────────────────────────

def run_command_file(filepath):
    """
    Reads a command file line by line and executes each command.
    """
    out(f"RTO Engine starting — reading {filepath}")
    out("=" * 60)

    with open(filepath, "r") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            # Split on comma
            parts   = line.split(",")
            command = parts[0].strip().upper()
            params  = [p.strip() for p in parts[1:]]

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
    input_file  = "data/commands.txt"
    output_file = "outputs/results.txt"

    # Allow command-line overrides:
    # python main.py
    # python main.py data/my_commands.txt
    # python main.py data/my_commands.txt outputs/my_results.txt
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]

    # Make sure the outputs folder exists
    os.makedirs("outputs", exist_ok=True)

    # Run all commands
    run_command_file(input_file)

    # Write results to file
    with open(output_file, "w") as f:
        f.write("\n".join(output_lines))

    print(f"\nResults saved to {output_file}")