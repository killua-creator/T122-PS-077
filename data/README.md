# PS-077 – RTO Vehicle Registration, Fitness and Challan Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T122.

## Files

| File | What it holds | Row count |
|---|---|---|
| `parameters.csv` | Engine parameters (as-of date, EV sunset date, windows and caps) | 11 data rows |
| `fee_master.csv` | Flat fees per vehicle class (registration, fitness, permit, transfer, NOC) | 6 data rows |
| `offence_master.csv` | 12 offence codes with amounts, points, court referral and disqualification | 12 data rows |
| `series.csv` | Registration mark series in issue order with the start number of the active one | 3 data rows |
| `fancy_numbers.csv` | 150 reserved (fancy) numbers with tier and reserve price | 150 data rows |
| `licences.csv` | Driving licences referenced by vehicles and challans | 320 data rows |
| `vehicles.csv` | 400 vehicles: 250 legacy (already registered) and 150 to be registered in the period | 400 data rows |
| `applications.csv` | Fitness, permit, transfer, NOC and re-registration applications processed by APPLY commands | 110 data rows |
| `prior_offences.csv` | Licence-point history before the period (for the 24-month rolling window) | 27 data rows |
| `challans.csv` | Challans issued in the period (issued by ISSUE_CHALLAN commands) | 900 data rows |
| `commands.txt` | Ordered event stream: registrations, auctions, applications, tax, challans, payments, prints | 2322 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `parameters.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| key | string | — | — | parameter name |
| value | string | date or integer | — | — |
| notes | string | — | — | may be empty |

### `fee_master.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| vehicle_class | enum | — | 2W, LMV_PRIVATE, LMV_TRANSPORT, HGV, BUS, EV | — |
| registration_fee | decimal | Rs | — | — |
| fitness_fee | decimal | Rs | — | 0.00 where fitness is not applicable until 15 years |
| fitness_retest_fee | decimal | Rs | — | charged only for a 2nd+ re-test |
| permit_new_fee | decimal | Rs | — | — |
| permit_renewal_fee | decimal | Rs | — | fresh-after-lapse fee is 2x this |
| transfer_fee | decimal | Rs | — | — |
| noc_fee | decimal | Rs | — | — |

### `offence_master.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| offence_code | string | OFnn | — | primary key |
| description | string | — | — | — |
| amount_lmv | decimal | Rs | — | for 2W/LMV_PRIVATE/LMV_TRANSPORT/EV |
| amount_other | decimal | Rs | — | for HGV/BUS |
| repeat_amount | decimal | Rs | — | fixed repeat amount; empty means 'double, cap 10,000' |
| points | int | — | 0-5 | — |
| court_referral | bool | — | true/false | true = immediate COURT_REFERRED |
| licence_disqualification_months | int | months | — | 0 = none |

### `series.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| series_id | string | SER-nn | — | — |
| series_prefix | string | state+RTO+2 letters | — | mark = prefix + 4 digits |
| sequence_order | int | — | 1..3 | issue series in this order |
| start_number | int | — | 1-9999 | first number to try in the series |
| status | enum | — | ACTIVE, NEXT | — |

### `fancy_numbers.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| number | string | 4 digits | 0001-9999 | unique |
| tier | int | — | 1,2,3 | — |
| reserve_price | decimal | Rs | 100000/50000/25000 | minimum auction bid |

### `licences.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| licence_no | string | — | — | primary key |
| holder_name | string | — | — | — |
| gender | enum | — | M, F | — |
| issue_date | date | — | — | — |
| mobile | string | 10 digits | — | — |

### `vehicles.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| vehicle_id | string | VEH-nnnn | — | primary key |
| vehicle_class | enum | — | 2W, LMV_PRIVATE, LMV_TRANSPORT, HGV, BUS, EV | — |
| fuel | enum | — | PETROL, DIESEL, CNG, ELECTRIC | — |
| ex_showroom_price | decimal | Rs | — | excluding GST; tax/cess base |
| gst_amount | decimal | Rs | — | shown separately, never taxed |
| engine_cc | int | cc | — | empty for EV |
| motor_kw | int | kW | — | EV only |
| seating | int | seats | — | incl. driver |
| laden_weight_tonnes | decimal | tonnes | — | GLW; used for HGV tax |
| manufacture_date | date | — | — | — |
| registration_date | date | — | — | date of first/permanent registration (legacy) or the date REGISTER is applied (new) |
| registration_state | string | — | KA | — |
| registration_mark | string | — | — | empty = not yet registered; issue via REGISTER |
| temp_registration_date | date | — | — | new vehicles only; temp reg valid 30 days |
| owner_id | string | OWN-nnnn | — | — |
| owner_name | string | — | — | — |
| owner_licence_no | string | — | licences.csv | — |
| owner_city | string | — | — | — |
| hypothecated | bool | — | — | — |
| financier | string | — | — | when hypothecated |
| insurance_valid_till | date | — | — | — |
| puc_valid_till | date | — | — | — |
| fitness_valid_till | date | — | — | legacy transport vehicles and 15-year-old private vehicles |
| permit_type | enum | — | CONTRACT, STAGE, GOODS | legacy transport only |
| permit_valid_till | date | — | — | — |
| tax_paid_till | date | — | — | last quarter-end for which transport tax is paid |

### `applications.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| app_id | string | APP-nnnn | — | primary key; APPLY|app_id |
| app_type | enum | — | FITNESS_NEW, FITNESS_RENEWAL, FITNESS_RETEST, PERMIT_NEW, PERMIT_RENEWAL, TRANSFER, NOC, REREGISTER | — |
| vehicle_id | string | — | vehicles.csv | — |
| application_date | date | — | — | — |
| inspection_date | date | — | — | fitness only |
| inspection_result | enum | — | PASS, FAIL | fitness only |
| permit_type | enum | — | CONTRACT, STAGE, GOODS | permit only |
| sale_date | date | — | — | transfer only |
| new_owner_id | string | OWN-Nnnn | — | transfer only |
| new_owner_name | string | — | — | — |
| new_owner_licence_no | string | — | licences.csv | — |
| destination_state | string | 2 letters | — | NOC/REREGISTER |
| first_registration_date | date | — | — | REREGISTER: base for depreciation |
| insurance_valid_till | date | — | — | as produced with the application |
| puc_valid_till | date | — | — | — |
| fee_paid | bool | — | — | — |

### `prior_offences.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| licence_no | string | — | licences.csv | — |
| offence_code | string | — | offence_master.csv | — |
| offence_date | date | — | — | before 2025-05-01 |
| points | int | — | — | — |
| status | enum | — | PAID | — |

### `challans.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| challan_id | string | CH-nnnn | — | unique except the planted duplicate |
| vehicle_id | string | — | vehicles.csv | — |
| offence_code | string | — | offence_master.csv (one invalid OF99 planted) | — |
| offence_ts | timestamp | — | — | offence time; day 0 of the 60/90-day clocks |
| driver_licence_no | string | — | licences.csv | empty = driver not identified |
| evidence | enum | — | CAMERA, OFFICER | — |
| location | string | — | — | — |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `REGISTER` | `vehicle_id|date` | Permanent registration: compute fees/tax/cess, issue the next mark from the active series |
| `AUCTION` | `number|vehicle_id|winning_bid` | Fancy-number auction result; the mark is assigned to the vehicle at its REGISTER |
| `APPLY` | `app_id` | Process the application row of applications.csv (type decides the rule set) |
| `HYP_NOC` | `vehicle_id|financier|date` | Financier's NOC received |
| `HYP_TERMINATE` | `vehicle_id|date` | Terminate hypothecation (needs a prior HYP_NOC) |
| `PAY_TAX` | `vehicle_id|quarter_start_date|payment_date` | Quarterly transport tax payment for the quarter starting on quarter_start_date |
| `ISSUE_CHALLAN` | `challan_id` | Issue the challan row of challans.csv (amount, repeat escalation, points) |
| `PAY_CHALLAN` | `challan_id|payment_timestamp` | Payment in full of whatever is due at that instant |
| `CONTEST_CHALLAN` | `challan_id|date` | Contest: freezes the escalation clock 30 days |
| `DECIDE_CONTEST` | `challan_id|UPHELD or DISMISSED|date` | Decision on a contested challan |
| `PRODUCE_DOCS` | `challan_id|INSURANCE or PUC|doc_valid_from|doc_valid_till` | Documents produced against a no-insurance / PUC challan |
| `NOMINATE_DRIVER` | `challan_id|licence_no|date` | Owner nominates the actual driver for a CAMERA challan |
| `NOC_UTILISED` | `vehicle_id|new_state|date` | Confirmation that the NOC was used (triggers pro-rata refund if within 12 months) |
| `PRINT_DOSSIER` | `vehicle_id|as_of_date` | Print the vehicle dossier |
| `PRINT_REGISTER` | `date` | Daily registration register for that date |
| `PRINT_AGEING` | `as_of_date` | Challan ageing report |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Ex-showroom price exactly Rs 50,000, Rs 5 lakh and Rs 20 lakh**
  - 2W priced exactly Rs 50,000 (10% slab upper bound) — `vehicles.csv VEH-0328 (row 328)`
  - LMV_PRIVATE priced exactly Rs 5,00,000 (13% slab upper bound) — `vehicles.csv VEH-0279 (row 279)`
  - Diesel LMV_PRIVATE priced exactly Rs 20,00,000 (17% slab upper bound; luxury cess applies only ABOVE 20 lakh; diesel cess 2% applies) — `vehicles.csv VEH-0299 (row 299)`
- **EC-02 EV registered on the sunset date itself**
  - EV with registration_date exactly on ev_sunset_date 2026-04-01 (5% applies: 'before' is strict) — `vehicles.csv VEH-0325 (row 325); parameters.csv ev_sunset_date`
  - Control: EV registered the day before the sunset date (0% road tax) — `vehicles.csv VEH-0338 (row 338)`
- **EC-03 Fitness renewal applied exactly 60 days before expiry and one day after expiry**
  - Fitness renewal applied exactly 60 days before expiry 2026-08-27 (allowed; keeps anniversary) — `applications.csv APP-0082 for VEH-0053 (row 82)`
  - Fitness renewal applied one day after expiry 2026-05-29 (Rs 50 late fee x days to inspection; validity restarts from inspection date) — `applications.csv APP-0072 for VEH-0121 (row 72)`
- **EC-04 Fancy number encountered in sequence when no auction exists for it**
  - Series KA01AA starts at 9850; fancy numbers 9876, 9889, 9898, 9999 lie in the sequence. 9876 and 9889 are pre-sold by AUCTION commands; 9898 has NO auction and must be skipped when the sequence reaches it — `commands.txt lines 14, 17; fancy_numbers.csv rows for 9898`
- **EC-05 Transfer applied on the 30th day after sale**
  - Transfer applied on the 30th day after the sale date (2026-02-10 -> 2026-03-12): no delay fee — `applications.csv APP-0057 for VEH-0022 (row 57)`
  - Control: transfer applied on the 31st day after sale (Rs 300 for one part-month of delay) — `applications.csv APP-0058 for VEH-0159 (row 58)`
- **EC-06 Depreciation at exactly 10 completed years (70% cap reached)**
  - Re-registration exactly 10 completed years after first registration (2016-06-15 -> 2026-06-15): depreciation 70% cap reached exactly — `applications.csv APP-0077 for VEH-0150 (row 77)`
  - Control: re-registration one day short of 10 completed years (9 years -> 63% depreciation) — `applications.csv APP-0079 for VEH-0250 (row 79)`
- **EC-07 Challan paid on day 60 at 23:59 versus day 61**
  - CH-0429 issued 2026-01-10, paid 2026-03-11 23:59:00 = day 60 (within window, no surcharge) — `challans.csv CH-0429 (row 430); commands.txt line 1263`
  - CH-0430 issued 2026-01-10, paid 2026-03-12 00:05:00 = day 61 (ESCALATED, 50% surcharge applies) — `challans.csv CH-0430 (row 431); commands.txt line 1264`
- **EC-08 Points reaching exactly 12 with the oldest offence falling outside 24 months the next day**
  - Licence KA5920100000015: offences 2024-10-31 (3 pts, prior_offences.csv row 1), 2025-03-02 (3), 2025-09-14 (3), 2026-10-30 (3) = exactly 12 within 24 months on 2026-10-30; on 2026-10-31 the oldest falls outside the window — `challans.csv CH-0896 (row 897) (the 2026-10-30 08:30:00 challan); prior_offences.csv rows 1-2`
- **Extra traps (not in the brief, but realistic):**
  - Fitness renewal applied 61 days before expiry 2026-08-31 — outside the 60-day window, must be REJECTED — `applications.csv APP-0084 for VEH-0118 (row 84)`
  - Failed fitness inspection followed by a re-test 10 days later (free re-test, within 15 days) — `applications.csv APP-0035 for VEH-0240 (row 35)`
  - Permit renewal by a vehicle whose tax is unpaid for 2 quarters (tax_paid_till 2026-03-31, application 2026-09-01) — must be refused — `applications.csv APP-0102 for VEH-0193 (row 102)`
  - Permit renewal applied 7.5 months after permit expiry (lapse > 6 months -> fresh permit at 2x renewal fee) — `applications.csv APP-0078 for VEH-0190 (row 78)`
  - Transfer of a vehicle under hypothecation (no HYP_NOC before it) — must be REJECTED — `applications.csv APP-0068 for VEH-0009 (row 68)`
  - Transfer while pending (unpaid) challans on the vehicle total more than Rs 2,000 — must be REJECTED — `applications.csv APP-0088 for VEH-0071 (row 88)`
  - Repeat of the same offence: helmet challans on 2025-08-03, 2026-08-03 (exactly 12 months later -> within 12 months, doubled to Rs 2,000) and 2026-08-04 (doubled again but capped at Rs 10,000 rule: 4,000) — `challans.csv CH-0143 (row 143), CH-0764 (row 765), CH-0765 (row 766) (VEH-0093)`
  - No-insurance challan first (Rs 2,000) then repeat (fixed repeat amount Rs 4,000, not doubling); valid insurance produced within 15 days waives the first one — `challans.csv CH-0315 (row 315), CH-0477 (row 478) (VEH-0223)`
  - Drunk-driving challan: Rs 10,000 and immediate court referral (vehicle BLOCKED) — `challans.csv CH-0541 (row 542) (VEH-0155)`
  - CAMERA challan with no driver identified: points go to the owner's licence unless NOMINATE_DRIVER arrives within 15 days (it arrives on day 16 -> too late) — `challans.csv CH-0582 (row 583) (VEH-0103)`
  - Contested challan: CONTEST_CHALLAN on day 50 freezes the escalation clock for 30 days; decision DISMISSED removes it from repeat counting — `challans.csv CH-0621 (row 622)`
  - Duplicate challan row: CH-0392 appears twice (identical) — second copy must be ignored — `challans.csv rows 392 and 393`
  - Challan with unknown offence code OF99 — must be REJECTED, not priced — `challans.csv CH-0901 (row 900)`
  - AUCTION for 9876 carries a bid exactly equal to its reserve price (valid); a third AUCTION below reserve for 0786 must be REJECTED — `commands.txt AUCTION lines near the top`
  - Sequence reaches 9999 inside the period: next registration must take KA01AB0001 (series roll-over) — `series.csv SER-01/SER-02; REGISTER commands after ~146 new registrations`
  - Quarterly tax for VEH-0018 quarter 2026-04-01 paid 32 days late (2 months or part -> 4% late fee) — `commands.txt line 164 onward (the 2026-04-01 quarter line)`
  - Out-of-order command: PAY_CHALLAN for CH-0400 appears before ISSUE_CHALLAN CH-0400 — must be rejected (UNKNOWN_CHALLAN); the later ISSUE still stands — `commands.txt lines 953 and 954`
  - VEH-0390: temporary registration dated 45 days before permanent registration — NON_COMPLIANT from day 31 until REGISTER — `vehicles.csv VEH-0390 (row 390)`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `registrations.csv`

One row per REGISTER / AUCTION-backed registration, in command order.

Columns, in order: `vehicle_id`, `registration_date`, `registration_mark`, `series_id`, `registration_fee`, `road_tax`, `diesel_cess`, `luxury_cess`, `green_tax`, `total_payable`, `status`

### `application_results.csv`

One row per APPLY in command order. late_fee and refund are 0.00 when not applicable.

Columns, in order: `app_id`, `app_type`, `vehicle_id`, `decision`, `reason`, `fee`, `late_fee`, `valid_from`, `valid_till`, `refund_amount`, `fresh_tax`

### `challan_history.csv`

One row per status change per challan in chronological order (ISSUED, ESCALATED, COURT_REFERRED, CONTESTED, DISMISSED, UPHELD, WAIVED, PAID, REJECTED).

Columns, in order: `challan_id`, `vehicle_id`, `status`, `status_ts`, `amount_due`, `points_applied`, `licence_no`

### `licence_points.csv`

State of every licence that has any points, as of the final command.

Columns, in order: `licence_no`, `points_in_window`, `suspension_count`, `licence_status`, `status_since`

### `vehicle_dossier.csv`

One row per PRINT_DOSSIER.

Columns, in order: `as_of_date`, `vehicle_id`, `registration_mark`, `owner_id`, `road_tax_paid`, `tax_paid_till`, `fitness_valid_till`, `permit_valid_till`, `pending_challan_amount`, `service_status`

### `daily_register.csv`

One row per registration on the PRINT_REGISTER date, sorted by registration_mark.

Columns, in order: `register_date`, `registration_mark`, `vehicle_id`, `vehicle_class`, `total_payable`

### `challan_ageing.csv`

One row per unpaid challan on the PRINT_AGEING date, sorted by challan_id.

Columns, in order: `as_of_date`, `challan_id`, `vehicle_id`, `status`, `days_outstanding`, `amount_due`

Format decisions made where the brief is silent: green tax at re-registration is reported in `green_tax` of registrations.csv; `service_status` is one of OK, NON_COMPLIANT, BLOCKED; `licence_status` is one of ACTIVE, DISQUALIFIED, SUSPENDED, REVOKED; quarterly transport tax is rounded up to the next Rs 10 per the brief; all money columns carry 2 decimals. Rolling 24-month point window: an offence counts on date X if its offence date is strictly after X minus 24 calendar months. Challan day counting: the offence date is day 0; 'paid within 60 days' means payment_timestamp date <= offence date + 60 days.
