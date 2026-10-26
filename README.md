# PS-077 — RTO Vehicle Registration, Fitness and Challan Engine

A backend application simulating Regional Transport Office (RTO) operations in Python 3.10+.

The engine processes vehicle registration, road tax and cess calculations, registration mark allocation, fitness certificates, permits, ownership transfers, interstate migration, traffic challan lifecycle, driver licence penalty points, and compliance reports.

---

## 1. Project Structure

```
T122-PS-077/
├── README.md               # Project overview and setup instructions
├── requirements.txt        # Development dependencies (pytest)
├── .gitignore              # Files excluded from version control
├── src/                    # Source code (Python standard library)
│   └── __init__.py
└── tests/                  # Automated tests mapped to BR-IDs
    ├── __init__.py
    └── test_smoke.py       # Test runner verification smoke test
```

---

## 2. Prerequisites

- **Python**: Version 3.10 or later (verified with Python 3.12)
- **Operating System**: Linux / macOS / Windows

---

## 3. Environment Setup

### Step 1: Create a virtual environment

In the project root directory, run:

```bash
python3 -m venv .venv
```

### Step 2: Activate the virtual environment

- **Linux / macOS**:
  ```bash
  source .venv/bin/activate
  ```
- **Windows (PowerShell)**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Running Tests

Run all automated tests using `pytest`:

```bash
pytest -v
```

To run a specific test file:

```bash
pytest tests/test_smoke.py -v
```

---

## 5. Architecture & Principles

- **Pure standard library for core domain**: Relies on standard library modules (`decimal`, `datetime`, `enum`, `typing`, `dataclasses`) without external database or web dependencies.
- **Precision monetary calculations**: Uses Python's `decimal.Decimal` for all financial computations to prevent floating-point inaccuracies.
- **Deterministic date evaluations**: Evaluates rules against provided command dates rather than system clocks, guaranteeing reproducible test results.
- **Traceable business rules**: Code and tests map directly to business rule identifiers (`BR-XX`).
