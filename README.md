# T122-PS-077 — RTO Vehicle Registration, Fitness and Challan Engine

**Team ID:** T122  
**Problem Statement:** PS-077  
**Language:** Python 3.10+  
**Domain:** Government – Transport (RTO)  

---

## What This Project Does

This is a command-file driven back-end engine that simulates the core operations
of a Regional Transport Office (RTO). It handles:

- Vehicle registration with road tax, green cess, diesel cess and luxury cess calculation
- Registration mark issuance with sequential series and fancy number auction
- Fitness certificates and permits for transport vehicles
- Ownership transfers, hypothecation and inter-state migration with NOC and tax refund
- Traffic challans with escalation, court referral, contest freezing and licence points
- Evaluation reports and CSV exports: registrations, applications, challan history, licence points, vehicle dossier, daily register, challan ageing

---

## How to Run

### 1. Install dependencies (one time only)

```bash
pip install pytest
```

No other external libraries are needed. The engine uses only Python's standard library.

### 2. Run the program

```bash
python3 main.py
```

This reads input master files and `commands.txt` from `data/` and writes all output files exclusively to the `outputs/` folder (`outputs/results.txt` and the 7 evaluation CSV files).

You can also supply custom data directories or command files:

```bash
python3 main.py data outputs
python3 main.py data/commands.txt outputs/results.txt
```

### 3. Run all tests

```bash
pytest -v
```

All 135 tests pass with this single command. No setup required.

---

## Project Structure

```text
T122-PS-077/
│
├── main.py                     ← Entry point — reads masters and command stream, runs engine
│
├── models/                     ← Data classes (what things ARE)
│   ├── vehicle.py              ← Vehicle
│   ├── owner.py                ← Owner and driving licence
│   ├── challan.py              ← Traffic fine
│   ├── fitness.py              ← Fitness certificate and permit
│   └── registration.py         ← Registration series tracker
│
├── engine/                     ← Business logic (what things DO)
│   ├── tax_calculator.py       ← Road tax, cess, quarterly tax (BR-01–BR-05)
│   ├── registration_engine.py  ← Mark issuance, fancy numbers (BR-06)
│   ├── fitness_engine.py       ← Fitness and permit rules (BR-07, BR-08)
│   ├── transfer_engine.py      ← Transfer, NOC, migration (BR-09, BR-10)
│   ├── challan_engine.py       ← Challan lifecycle, points (BR-11–BR-14)
│   └── report_engine.py        ← Dossier, register, ageing report
│
├── data/                       ← Input masters and event stream
│   ├── parameters.csv          ← Engine parameters (as-of date, EV sunset date, caps)
│   ├── fee_master.csv          ← Flat fees per vehicle class
│   ├── offence_master.csv      ← 12 offence codes with amounts and points
│   ├── series.csv              ← Registration series configuration
│   ├── fancy_numbers.csv       ← Reserved fancy numbers with tiers and reserves
│   ├── licences.csv            ← Driving licences master
│   ├── vehicles.csv            ← Vehicles master (legacy + to register)
│   ├── applications.csv        ← Fitness, permit, transfer, NOC applications
│   ├── prior_offences.csv      ← Historic licence offences for 24m window
│   ├── challans.csv            ← Challans issued during period
│   └── commands.txt            ← Ordered event command stream
│
├── outputs/                    ← Program outputs (auto-created, git-ignored)
│   ├── results.txt             ← Text logs from command execution
│   ├── registrations.csv       ← Evaluation CSV: permanent registrations
│   ├── application_results.csv ← Evaluation CSV: application decisions
│   ├── challan_history.csv     ← Evaluation CSV: challan state transitions
│   ├── licence_points.csv      ← Evaluation CSV: active licence point totals
│   ├── vehicle_dossier.csv     ← Evaluation CSV: vehicle dossier snapshots
│   ├── daily_register.csv      ← Evaluation CSV: daily registration register
│   └── challan_ageing.csv      ← Evaluation CSV: unpaid challan ageing
│
├── tests/                      ← Comprehensive automated test suite
│   ├── test_tax.py             ← 27 tests (BR-01 to BR-05)
│   ├── test_registration.py    ← 14 tests (BR-06)
│   ├── test_fitness.py         ← 18 tests (BR-07, BR-08)
│   ├── test_challan.py         ← 26 tests (BR-11 to BR-14)
│   ├── test_transfer.py        ← 24 tests (BR-09, BR-10)
│   ├── test_reports.py         ← 7 tests (report engine)
│   └── test_scenarios.py       ← 24 tests (EC-01 to EC-08, traps & full datapack)
│
├── design_document.pdf         ← Design document (Week 1 deliverable)
├── decision_log.txt            ← Decisions made during development
└── README.md                   ← This file
```

---

## Command File Format

Each line in the command stream represents an event. Commands can be pipe-delimited (`COMMAND|arg1|arg2|...`) or comma-delimited (`COMMAND,arg1,arg2,...`). Lines starting with `#` are comments and blank lines are ignored.

### Supported Commands

| Command | Arguments | Meaning |
|---|---|---|
| `REGISTER` | `vehicle_id\|date` | Permanent registration: computes fee/tax/cess, issues next mark |
| `AUCTION` | `number\|vehicle_id\|winning_bid` | Fancy-number auction; mark assigned at registration |
| `APPLY` | `app_id` | Processes application row (FITNESS, PERMIT, TRANSFER, NOC, REREGISTER) |
| `HYP_NOC` | `vehicle_id\|financier\|date` | Financier's NOC received |
| `HYP_TERMINATE` | `vehicle_id\|date` | Terminates hypothecation (requires prior HYP_NOC) |
| `PAY_TAX` | `vehicle_id\|quarter_start_date\|payment_date` | Quarterly transport road tax payment with late fee logic |
| `ISSUE_CHALLAN` | `challan_id` | Issues challan from master with repeat doubling & point allocation |
| `PAY_CHALLAN` | `challan_id\|payment_timestamp` | Payment in full of outstanding challan amount |
| `CONTEST_CHALLAN` | `challan_id\|date` | Freezes challan escalation clock for 30 days |
| `DECIDE_CONTEST` | `challan_id\|decision\|date` | Resolves contest (DISMISSED or UPHELD) |
| `PRODUCE_DOCS` | `challan_id\|doc_type\|from\|till` | Waives insurance/PUC challan if valid docs produced within 15 days |
| `NOMINATE_DRIVER` | `challan_id\|licence_no\|date` | Transfers camera challan points to driver if within 15 days |
| `NOC_UTILISED` | `vehicle_id\|new_state\|date` | Confirms NOC utilisation and triggers pro-rata refund |
| `PRINT_DOSSIER` | `vehicle_id\|as_of_date` | Prints vehicle dossier |
| `PRINT_REGISTER` | `date` | Prints daily registration register |
| `PRINT_AGEING` | `as_of_date` | Prints unpaid challan ageing report |

*(Legacy command names `REGISTER_OWNER`, `REGISTER_VEHICLE`, `CREATE_SERIES`, `ISSUE_FITNESS`, `ISSUE_PERMIT`, `TRANSFER_VEHICLE`, `ISSUE_NOC`, `AUCTION_FANCY`, `RESOLVE_CONTEST` are also supported for backward compatibility).*

---

## Output CSV Format at Evaluation

All evaluation outputs are written exclusively to the `outputs/` folder:

1. **`outputs/registrations.csv`**: `vehicle_id`, `registration_date`, `registration_mark`, `series_id`, `registration_fee`, `road_tax`, `diesel_cess`, `luxury_cess`, `green_tax`, `total_payable`, `status`
2. **`outputs/application_results.csv`**: `app_id`, `app_type`, `vehicle_id`, `decision`, `reason`, `fee`, `late_fee`, `valid_from`, `valid_till`, `refund_amount`, `fresh_tax`
3. **`outputs/challan_history.csv`**: `challan_id`, `vehicle_id`, `status`, `status_ts`, `amount_due`, `points_applied`, `licence_no`
4. **`outputs/licence_points.csv`**: `licence_no`, `points_in_window`, `suspension_count`, `licence_status`, `status_since`
5. **`outputs/vehicle_dossier.csv`**: `as_of_date`, `vehicle_id`, `registration_mark`, `owner_id`, `road_tax_paid`, `tax_paid_till`, `fitness_valid_till`, `permit_valid_till`, `pending_challan_amount`, `service_status`
6. **`outputs/daily_register.csv`**: `register_date`, `registration_mark`, `vehicle_id`, `vehicle_class`, `total_payable`
7. **`outputs/challan_ageing.csv`**: `as_of_date`, `challan_id`, `vehicle_id`, `status`, `days_outstanding`, `amount_due`

---

## Business Rules Implemented

| Rule ID | Description |
|---|---|
| BR-01 | Road tax for two-wheelers (3 slabs: 10%, 12%, 18%) |
| BR-02 | Road tax for private cars (4 slabs: 13%, 14%, 17%, 18%) |
| BR-03 | Road tax for EVs (0% before sunset date 2026-04-01, 5% on/after) |
| BR-04 | Green cess, diesel surcharge (2%), luxury cess (1% above 20L) |
| BR-05 | Quarterly road tax for transport vehicles with late fee and cap |
| BR-06 | Sequential mark issuance, fancy number auction, series rollover |
| BR-07 | Fitness certificate: 2-year new, 1-year renewal, late fee, free retest within 15d |
| BR-08 | Permit: 5-year validity, annual renewal, 2x fee after > 6m lapse |
| BR-09 | Ownership transfer: eligibility, fee, delay penalty, hypothecation check, pending challans cap |
| BR-10 | Inter-state migration: NOC, depreciated tax (7%/yr completed, 70% max), pro-rata refund |
| BR-11 | Challan amounts by offence, repeat doubling within 12 months, Rs 10,000 cap |
| BR-12 | Challan lifecycle: ISSUED → ESCALATED (day 61, +50%) → COURT_REFERRED (day 91) |
| BR-13 | Licence points: rolling 24-month calendar window, suspension, revocation |
| BR-14 | Insurance and PUC document waiver within 15 days |
| BR-15 | Vehicle blocking on court referral / drunk driving |

---

## Edge Cases Handled

All planted edge cases and traps from the specification are explicitly handled and tested:

- **EC-01**: Exact price boundaries for tax slabs (Rs 50,000, Rs 5,00,000, Rs 20,00,000)
- **EC-02**: EV registered on sunset date 2026-04-01 (5%) vs day before (0%)
- **EC-03**: Fitness renewal 60 days before expiry (anniversary preserved) vs 1 day after expiry (late fee + reset from inspection)
- **EC-04**: Fancy numbers in sequence skipped when no auction exists; rollover to next series on 9999
- **EC-05**: Transfer on day 30 (no delay fee) vs day 31 (delay fee charged)
- **EC-06**: Depreciation at exactly 10 completed years (70% cap reached) vs 9 years (63%)
- **EC-07**: Challan paid on day 60 (standard fine) vs day 61 (escalated +50% surcharge)
- **EC-08**: Rolling 24-month licence points window boundary (12 points on day X, oldest drops on X+1)
- **Traps**:
  - Fitness renewal applied 61 days before expiry rejected (`OUTSIDE_WINDOW`)
  - Free fitness re-test within 15 days of failure
  - Permit renewal refused when road tax unpaid for >= 2 quarters (`UNPAID_TAX`)
  - Permit renewal lapsed > 6 months charged 2x renewal fee
  - Transfer rejected if hypothecated without prior `HYP_NOC`
  - Transfer rejected if pending challans exceed Rs 2,000
  - Repeat offence within 12 months fine doubling (capped at Rs 10,000)
  - Insurance waiver within 15 days of offence
  - Drunk driving immediate court referral and vehicle blocking
  - Camera challan driver nomination after 15 days rejected
  - Contested challan clock freeze (30 days) and dismissal
  - Duplicate challan handling and out-of-order payment rejection

---

## Test Results

```bash
$ pytest
============================= 135 passed in 0.10s ==============================
```
