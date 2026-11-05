# T122-PS-077 — RTO Vehicle Registration, Fitness and Challan Engine

**Team ID:** T122
**Problem Statement:** PS-077
**Language:** Python 3.10+
**Domain:** Government – Transport (RTO)

---

## What This Project Does

This is a command-file driven back-end engine that simulates the core operations
of a Regional Transport Office (RTO). It handles:

- Vehicle registration with road tax, green cess and luxury cess calculation
- Registration mark issuance with sequential series and fancy number auction
- Fitness certificates and permits for transport vehicles
- Ownership transfers, hypothecation and inter-state migration with NOC and tax refund
- Traffic challans with escalation, court referral, contest freezing and licence points
- Reports: vehicle dossier, daily registration register, challan ageing

---

## How to Run

### 1. Install dependencies (one time only)

```bash
pip install pytest
```

No other libraries are needed. The engine uses only Python's standard library.

### 2. Run the program

```bash
python main.py
```

This reads `data/commands.txt` and writes output to `outputs/results.txt`.

You can also supply your own command file:

```bash
python main.py data/my_commands.txt
python main.py data/my_commands.txt outputs/my_results.txt
```

### 3. Run all tests

```bash
pytest -v
```

All tests pass with this single command. No setup required.

---

## Project Structure
T122-PS-077/
│
├── main.py ← Entry point — reads command file, runs engine
│
├── models/ ← Data classes (what things ARE)
│ ├── vehicle.py ← Vehicle
│ ├── owner.py ← Owner and driving licence
│ ├── challan.py ← Traffic fine
│ ├── fitness.py ← Fitness certificate and permit
│ └── registration.py ← Registration series tracker
│
├── engine/ ← Business logic (what things DO)
│ ├── tax_calculator.py ← Road tax, cess, quarterly tax (BR-01–BR-05)
│ ├── registration_engine.py ← Mark issuance, fancy numbers (BR-06)
│ ├── fitness_engine.py ← Fitness and permit rules (BR-07, BR-08)
│ ├── transfer_engine.py ← Transfer, NOC, migration (BR-09, BR-10)
│ ├── challan_engine.py ← Challan lifecycle, points (BR-11–BR-14)
│ └── report_engine.py ← Dossier, register, ageing report
│
├── data/
│ └── commands.txt ← Input command file
│
├── outputs/
│ └── results.txt ← Program output (auto-created)
│
├── tests/
│ ├── test_tax.py ← 27 tests (BR-01 to BR-05)
│ ├── test_registration.py ← 14 tests (BR-06)
│ ├── test_fitness.py ← 18 tests (BR-07, BR-08)
│ ├── test_challan.py ← 26 tests (BR-11 to BR-14)
│ ├── test_transfer.py ← 24 tests (BR-09, BR-10)
│ └── test_reports.py ← 7 tests (report engine)
│
├── design_document.pdf ← Design document (Week 1 deliverable)
├── decision_log.txt ← 10–20 decisions made during development
└── README.md ← This file


---

## Command File Format

Each line in the command file is one instruction. Format:
COMMAND,param1,param2,...


Lines starting with `#` are comments and are ignored.

### Supported Commands

| Command | Parameters | What it does |
|---|---|---|
| `REGISTER_OWNER` | owner_id, name, licence_number | Creates an owner record |
| `CREATE_SERIES` | prefix, tier:number, ... | Sets up a registration series with fancy numbers |
| `REGISTER_VEHICLE` | veh_id, series, class, fuel, price, cc, seats, weight, mfg_date, reg_date, owner_id, state [, ev_sunset_date] | Registers a vehicle and calculates tax |
| `ISSUE_CHALLAN` | challan_id, reg_mark, offence, date, evidence [, licence_id] | Issues a traffic fine |
| `PAY_CHALLAN` | challan_id, payment_date | Marks a challan as paid |
| `CONTEST_CHALLAN` | challan_id, contest_date | Freezes the challan clock for 30 days |
| `RESOLVE_CONTEST` | challan_id, decision, date | Resolves a contest (DISMISSED or UPHELD) |
| `ISSUE_FITNESS` | reg_mark, inspection_date, is_new_vehicle | Issues a fitness certificate |
| `ISSUE_PERMIT` | reg_mark, permit_type, issue_date | Issues an operating permit |
| `TRANSFER_VEHICLE` | transfer_id, reg_mark, new_owner_id, sale_date, transfer_date | Transfers ownership |
| `ISSUE_NOC` | noc_id, reg_mark, noc_date, first_reg_date | Issues NOC for inter-state migration |
| `AUCTION_FANCY` | series_prefix, number, winning_bid | Records a fancy number auction result |
| `PRINT_DOSSIER` | reg_mark, current_date | Prints full vehicle history |
| `PRINT_DAILY_REGISTER` | report_date | Prints all vehicles registered on a date |
| `PRINT_CHALLAN_AGEING` | current_date | Prints unpaid challans grouped by age |

---

## Business Rules Implemented

| Rule ID | Description |
|---|---|
| BR-01 | Road tax for two-wheelers (3 slabs: 10%, 12%, 18%) |
| BR-02 | Road tax for private cars (4 slabs: 13%, 14%, 17%, 18%) |
| BR-03 | Road tax for EVs (0% before sunset date, 5% after) |
| BR-04 | Green cess, diesel surcharge, luxury cess |
| BR-05 | Quarterly road tax for transport vehicles with late fee and cap |
| BR-06 | Sequential mark issuance, fancy number auction, temp registration |
| BR-07 | Fitness certificate: 2-year new, 1-year renewal, late fee, retest |
| BR-08 | Permit: 5-year validity, annual renewal, lapse rule |
| BR-09 | Ownership transfer: eligibility, fee, delay penalty, hypothecation |
| BR-10 | Inter-state migration: NOC, depreciated tax, pro-rata refund |
| BR-11 | Challan amounts by offence, repeat doubling, cap |
| BR-12 | Challan lifecycle: ISSUED → ESCALATED → COURT_REFERRED |
| BR-13 | Licence points: rolling 24-month window, suspension, revocation |
| BR-14 | Insurance and PUC document waiver within 15 days |
| BR-15 | Vehicle blocking on court referral |

---

## Edge Cases Handled

All 15 edge cases from the brief are explicitly handled and tested:

- EC-01 to EC-03: Exact price boundaries for tax slabs
- EC-04: EV registered on the sunset date itself (5% applies)
- EC-05: Fitness renewal exactly 60 days before expiry (accepted)
- EC-06: Fitness renewal one day after expiry (late fee applies)
- EC-07: Fancy number in sequence with no auction (skipped)
- EC-08: Transfer on exactly day 30 after sale (no delay fee)
- EC-09: Depreciation at exactly 10 years (70% cap reached)
- EC-10: Challan paid on day 60 vs day 61 (escalation boundary)
- EC-11: Licence points outside 24-month window not counted
- EC-12: Two unpaid quarters blocks fitness and permit renewal
- EC-13: NOC utilisation on exactly day 365 (refund released)
- EC-14: Insurance documents produced on day 15 (waiver granted)
- EC-15: Drunk driving immediately court-referred

---

## Design Document

See `design_document.pdf` for:
- Glossary of all domain terms
- Class diagram (entities and relationships)
- State diagrams for Vehicle, Challan, Fitness Certificate and Licence
- Full business rule register (BR-01 to BR-16)
- Edge case register (EC-01 to EC-15)

---

## Test Results
pytest -v
119 passed in X.XXs