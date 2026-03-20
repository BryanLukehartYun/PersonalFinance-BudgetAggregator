# PersonalFinance — Budget Aggregator
A fully local, privacy-first budget aggregator that combines transaction exports from multiple banks into a single categorized master CSV. No data leaves your local machine.

## Key Features
* Zero Persistence System: Inputs are read from ~/Downloads and outputs are written back to ~/Downloads. No CSV data is ever stored within the project directory or committed to Git.
* Unified Toolchain: Built using uv for deterministic dependency management across Linux and macOS.
* Modular Parser Registry: Abstracted parser logic allows for seamless integration of new banking "plants" (e.g., Chase, Amex) without modifying the core engine.
---

## What It Does 💸

- Ingests CSV exports from **Capital One** and **Navy Federal (NFCU)** as of now. 
- Auto-detects which bank each file came from
- Categorizes every transaction through a 5-layer pipeline
- Outputs a single `budget_master.csv` to your Downloads folder

---

## Categorization Pipeline

| Layer | Method | Description |
|-------|--------|-------------|
| 0 | NFCU Native | Uses NFCU's own category label if present |
| 1 | Direct Lookup | Exact/substring match against `mapping/category_map.json` |
| 2 | RapidFuzz | Fuzzy string match against the same map |
| 3 | BGE Encoder | Semantic similarity via `BAAI/bge-small-en-v1.5` (local, offline) |
| 4 | Fallback | `Uncategorized` — for anything genuinely unknown |

---

## Project Structure

```
project/
├── budget_engine.py          # Main orchestrator — run this
├── analytics.py              # Responsible for descriptive figures
├── mapping/
│   └── category_map.json     # Direct lookup table (edit to add merchants)
└── parsers/
    ├── __init__.py            # Parser registry
    ├── capital_one.py         # Capital One CSV parser
    └── nfcu.py                # Navy Federal CSV parser
```

> **No CSV files are stored in this repo.** Inputs are sourced from Downloads and output goes back to Downloads.

---
## **!!! Important**

OS Compatibility: This engine was developed and verified on 
* macOS (M3 Pro) 
* CachyOS (Linux)
* Mint (Linux)  

It is currently untested on Windows. While Python's pathlib and uv provide significant cross-platform stability, Windows-specific pathing or GUI scaling may vary. *This is going to be tested at a later undisclosed date whenever convenient. If urgency is needed, please make a pull request*

## Setup

Requires [uv](https://github.com/astral-sh/uv).

1. Clone the repo.
2. Run `uv sync` to install the deterministic environment from `uv.lock`.

---

## Usage

```bash
uv run budget_engine.py
```

A file picker will open. Select one or more CSV exports (Capital One and/or NFCU — mix freely). The engine auto-detects the bank for each file.

**Output:** `~/Downloads/budget_master.csv`

| Column | Description |
|--------|-------------|
| `date` | Transaction date |
| `desc` | Merchant description |
| `amount` | Positive = money in, Negative = money out |
| `source_bank` | `Capital One` or `Navy Federal` |
| `category` | Assigned category label |
| `match_method` | Which layer categorized it |
| `confidence` | Confidence score (0.0 – 1.0) |

---

## Adding a New Bank 🏦

1. Create `parsers/your_bank.py` with `detect(df)` and `parse(df)` functions
2. Register it in `parsers/__init__.py`
3. That's it — the engine picks it up automatically

---

## Extending the Lookup Table

Edit `mapping/category_map.json` to add merchants the encoder misses:

```json
{
  "TRADER JOE": "Groceries",
  "NETFLIX": "Subscriptions"
}
```

Keys are matched case-insensitively as substrings, so `"TRADER JOE"` will catch `"TRADER JOE #1234 SEATTLE"`.

---

## 🚀 Roadmap
v1.1 - Release of Analytical Layer
* [✅] Automated Spending Summary: Generation of a secondary summary.csv or report.pdf grouping totals by category and month.

v1.1.X - Release of the Aggregator
* [ ] Additional Parsers: Adding logic for Chase, Amex, and BoA to further "anonymize" the user's primary banking manifold. If you desire a specific bank, please make a pull request and attach a sample csv **ANONYMIZED WITH NO IDENTIFYING INFO**

v1.2.0 - System Stability & Expansion
* [ ] Temporal Deduplication: Logic to identify and neutralize internal transfers (e.g., matching a -500 debit in Bank A with a +500 credit in Bank B within a 3-day window).
* [ ] CLI-only Mode: Optional flags to bypass the Tkinter GUI for power users on Linux/CachyOS environments. 🐧🐧
> Note: The CLI layer may not make the cut and may be shelved for future works. 

v1.3.0 - Analytical Layer (I'm trying to see how to package this)
* [ ] State Estimation Visualization: Basic terminal-based or Matplotlib charts showing month-over-month trends.

---

## Privacy 🔒

- All processing is local
- The BGE model runs fully offline after the initial download
- No transaction data is stored in the repo (`.csv` files are gitignored)

---

## Licensing
***The codes provided are covered under MIT License.*** A sample CSV each for certain banks are attached but does not correspond to any personal information at all. This script is intended to serve as a educational and personal finance tool, nothing more then that. 