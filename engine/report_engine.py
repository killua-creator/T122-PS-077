# Generates three reports:
#   1. Vehicle dossier      — full history of one vehicle
#   2. Daily register       — all registrations on a given date
#   3. Challan ageing report — unpaid challans grouped by age

from datetime import date
from engine.challan_engine import get_effective_days, update_challan_status


# ── Report 1: Vehicle Dossier ─────────────────────────────────────────────────

def generate_vehicle_dossier(vehicle, owner, challans,
                              fitness_cert, permit, current_date):
    """
    Prints a full history report for one vehicle.

    vehicle:      Vehicle object
    owner:        Owner object
    challans:     list of Challan objects for this vehicle
    fitness_cert: FitnessCertificate object or None
    permit:       Permit object or None
    current_date: string "YYYY-MM-DD"

    Returns: a formatted string report (also prints it)
    """
    lines = []
    lines.append("=" * 60)
    lines.append("VEHICLE DOSSIER")
    lines.append("=" * 60)

    # ── Basic vehicle info ────────────────────────────────────────
    lines.append(f"Registration Mark : {vehicle.registration_mark}")
    lines.append(f"Vehicle Class     : {vehicle.vehicle_class}")
    lines.append(f"Fuel Type         : {vehicle.fuel_type}")
    lines.append(f"Ex-Showroom Price : Rs {vehicle.ex_showroom_price:,}")
    lines.append(f"Manufacture Date  : {vehicle.manufacture_date}")
    lines.append(f"Registration Date : {vehicle.registration_date}")
    lines.append(f"State             : {vehicle.state}")
    lines.append(f"Status            : {vehicle.status}")
    lines.append(f"Hypothecation     : {vehicle.hypothecation or 'None'}")
    lines.append("")

    # ── Owner info ────────────────────────────────────────────────
    lines.append("OWNER")
    lines.append(f"  Name            : {owner.name}")
    lines.append(f"  Owner ID        : {owner.owner_id}")
    lines.append(f"  Licence No.     : {owner.licence_number}")
    lines.append(f"  Licence Status  : {owner.licence_status}")
    if owner.licence_suspended_until:
        lines.append(f"  Suspended Until : {owner.licence_suspended_until}")
    lines.append("")

    # ── Tax paid ──────────────────────────────────────────────────
    lines.append("TAX RECORD")
    lines.append(f"  Road Tax Paid   : Rs {vehicle.road_tax_paid:,}")
    lines.append(f"  Cess Paid       : Rs {vehicle.cess_paid:,}")
    lines.append("")

    # ── Fitness certificate ───────────────────────────────────────
    lines.append("FITNESS CERTIFICATE")
    if fitness_cert:
        lines.append(f"  Status          : {fitness_cert.status}")
        lines.append(f"  Issue Date      : {fitness_cert.issue_date}")
        lines.append(f"  Expiry Date     : {fitness_cert.expiry_date}")
        if fitness_cert.late_fee > 0:
            lines.append(f"  Late Fee Paid   : Rs {fitness_cert.late_fee:,}")
    else:
        lines.append("  No fitness certificate on record")
    lines.append("")

    # ── Permit ────────────────────────────────────────────────────
    lines.append("PERMIT")
    if permit:
        lines.append(f"  Type            : {permit.permit_type}")
        lines.append(f"  Status          : {permit.status}")
        lines.append(f"  Issue Date      : {permit.issue_date}")
        lines.append(f"  Expiry Date     : {permit.expiry_date}")
        lines.append(f"  Next Annual Due : {permit.annual_renewal_date}")
    else:
        lines.append("  No permit on record")
    lines.append("")

    # ── Challan history ───────────────────────────────────────────
    lines.append("CHALLAN HISTORY")
    if not challans:
        lines.append("  No challans on record")
    else:
        for c in challans:
            # Refresh status before printing
            update_challan_status(c, current_date)
            lines.append(f"  [{c.challan_id}] {c.offence_date} | "
                         f"{c.offence_code} | "
                         f"Rs {c.current_amount:,} | "
                         f"{c.status}")
    lines.append("")

    # ── Licence points summary ────────────────────────────────────
    lines.append("LICENCE POINTS (last 24 months)")
    if not owner.licence_points:
        lines.append("  No points on record")
    else:
        today   = date.fromisoformat(current_date)
        cutoff  = today.replace(year=today.year - 2)
        total   = 0
        for entry in owner.licence_points:
            entry_date = date.fromisoformat(entry["date"])
            if entry_date >= cutoff:
                lines.append(f"  {entry['date']} | "
                             f"{entry['offence']} | "
                             f"{entry['points']} pts")
                total += entry["points"]
        lines.append(f"  TOTAL IN WINDOW : {total} pts")
    lines.append("=" * 60)

    report = "\n".join(lines)
    print(report)
    return report


# ── Report 2: Daily Registration Register ─────────────────────────────────────

def generate_daily_register(all_vehicles, report_date):
    """
    Lists all vehicles registered on a specific date.

    all_vehicles: dictionary of {registration_mark: Vehicle object}
    report_date:  string "YYYY-MM-DD"

    Returns: a formatted string report (also prints it)
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"DAILY REGISTRATION REGISTER — {report_date}")
    lines.append("=" * 60)

    # Filter vehicles registered on this date
    registered_today = [
        v for v in all_vehicles.values()
        if v.registration_date == report_date
    ]

    if not registered_today:
        lines.append("No vehicles registered on this date.")
    else:
        lines.append(f"{'Mark':<15} {'Class':<18} {'Owner':<10} "
                     f"{'Price':>12} {'Status'}")
        lines.append("-" * 60)
        for v in registered_today:
            lines.append(f"{v.registration_mark:<15} "
                         f"{v.vehicle_class:<18} "
                         f"{v.owner_id:<10} "
                         f"Rs {v.ex_showroom_price:>9,} "
                         f"{v.status}")

    lines.append(f"\nTotal registered: {len(registered_today)}")
    lines.append("=" * 60)

    report = "\n".join(lines)
    print(report)
    return report


# ── Report 3: Challan Ageing Report ──────────────────────────────────────────

def generate_challan_ageing_report(all_challans, current_date):
    """
    Groups all unpaid challans by how old they are (effective days).
    Shows which challans are close to escalation or court referral.

    all_challans: list of all Challan objects in the system
    current_date: string "YYYY-MM-DD"

    Returns: a formatted string report (also prints it)
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"CHALLAN AGEING REPORT — {current_date}")
    lines.append("=" * 60)

    # Only unpaid challans are relevant
    unpaid = [
        c for c in all_challans
        if c.status in ("ISSUED", "ESCALATED", "CONTESTED")
    ]

    if not unpaid:
        lines.append("No unpaid challans.")
        lines.append("=" * 60)
        report = "\n".join(lines)
        print(report)
        return report

    # Group by age bucket
    bucket_0_30   = []   # 0–30 days — recent
    bucket_31_60  = []   # 31–60 days — approaching escalation
    bucket_61_90  = []   # 61–90 days — ESCALATED, approaching court
    bucket_90plus = []   # 90+ days — should be COURT_REFERRED

    for c in unpaid:
        eff_days = get_effective_days(c, current_date)
        if eff_days <= 30:
            bucket_0_30.append((c, eff_days))
        elif eff_days <= 60:
            bucket_31_60.append((c, eff_days))
        elif eff_days <= 90:
            bucket_61_90.append((c, eff_days))
        else:
            bucket_90plus.append((c, eff_days))

    def print_bucket(label, bucket):
        lines.append(f"\n{label}  ({len(bucket)} challans)")
        lines.append("-" * 60)
        if not bucket:
            lines.append("  None")
        else:
            for c, eff_days in bucket:
                lines.append(f"  {c.challan_id:<10} | "
                             f"{c.vehicle_id:<15} | "
                             f"{c.offence_code:<20} | "
                             f"Rs {c.current_amount:>6,} | "
                             f"Day {eff_days}")

    print_bucket("0–30 days   (CURRENT)",       bucket_0_30)
    print_bucket("31–60 days  (NEAR ESCALATION)", bucket_31_60)
    print_bucket("61–90 days  (ESCALATED)",      bucket_61_90)
    print_bucket("90+ days    (OVERDUE)",         bucket_90plus)

    lines.append(f"\nTotal unpaid challans : {len(unpaid)}")
    lines.append(f"Total amount outstanding : Rs "
                 f"{sum(c.current_amount for c, _ in bucket_0_30 + bucket_31_60 + bucket_61_90 + bucket_90plus):,}")
    lines.append("=" * 60)

    report = "\n".join(lines)
    print(report)
    return report