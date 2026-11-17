# Improvement Plan — PersonalFinance Budget Aggregator

Based on a read-through of the repo at `d69136c`. Nothing was run: there is no sample data in
the repo, so the bugs below come from reading the code. Items marked **(verify)** need a
fixture test to confirm.

Order matters: fix correctness first, restructure second, then build Streamlit on top of a
clean core. Building the UI first would bake the current bugs into it.

---

## Phase 0 — Correctness bugs (do first)

1. **"Spending" figures are actually money in.**
   Parsers define positive = money in, negative = money out. `analytics.py` filters
   `amount > 0` in `_spending_pivot` (line 49) and `build_bank_chart` (line 373), so every
   chart, the summary CSV and "Grand Total Spending" report credits and exclude purchases.
   - Fix: spending = `amount < 0`, plotted as absolute value; income = `amount > 0`, shown separately.
   - The featured panels (`Credit Card Payments`, `Deposits`, `Paychecks/Salary`) are income/transfer
     categories; move them to an income view.

2. **Mixed-case map keys never match directly.**
   `categorize()` upper-cases the description but not the keys, so `"Bagel Cafe"` can never hit
   Layer 1. The README promises case-insensitive matching.
   - Fix: upper-case keys once in `load_category_map`.

3. **Substring matching is too loose and order-dependent.**
   `"BP"`, `"SHELL"`, `"CVS"`, `"GOOGLE"`, `"TARGET"` match inside unrelated words, and
   `UBER EATS` vs `UBER` only works because of JSON key order.
   - Fix: match on word boundaries and try longest key first.

4. **NFCU title-row handling breaks on the second call. (verify)**
   `_maybe_fix_header` assigns `df.columns` on the caller's frame in `detect()` without dropping
   the header row. When `parse()` runs, the check no longer fires, so the header row stays in as
   a data row.
   - Fix: make it non-mutating (`df = df.copy()` first), or normalise once in the engine and pass
     the result to both `detect` and `parse`.
   - Also check whether `pd.read_csv` reads a file with a one-field title line the way the code assumes.

5. **Rows without an NFCU category may be labelled `NaN` / `nfcu_native`. (verify)**
   `row.get('nfcu_category')` is a truthiness check, and NaN is truthy. Under pandas 3 the
   `replace({'nan': None})` step likely leaves NaN.
   - Fix: use `pd.notna(...)` and a non-empty check.

6. **Category names are not one taxonomy.**
   NFCU native labels, the map (`"FOODS"` vs `"Dining"`) and the attractor categories all coexist,
   so the same kind of spend lands in several buckets.
   - Fix: one canonical category list, plus an alias table mapping NFCU labels onto it.

7. **Smaller items**
   - BGE prefix `"Represent this sentence: "` is not the model's documented instruction; for
     short-text similarity, drop the prefix on both sides and re-tune `SEMANTIC_THRESHOLD`.
   - `except Exception` in the file loop hides real failures; print the traceback or re-raise in a debug mode.
   - Overlapping exports (same date range picked twice) are concatenated with no dedupe.
   - The Tk root is never destroyed.

---

## Phase 1 — Project setup

1. **Package layout**
   ```
   src/budget_aggregator/
   ├── parsers/            # unchanged idea, one module per bank
   ├── categorize.py       # layers 1–4, no I/O
   ├── pipeline.py         # files -> categorized DataFrame, no I/O side effects
   ├── analytics.py        # DataFrame -> tables + figures (returns them, does not save)
   ├── config.py           # thresholds, paths, category list
   ├── cli.py              # argparse entry point
   └── app.py              # Streamlit UI (Phase 3)
   mapping/category_map.json
   tests/
   ```
   The key change: core functions take and return DataFrames/figures. Writing to disk and
   picking files happen only in `cli.py` and `app.py`.

2. **`pyproject.toml`**
   - Real `description`; one version number (file says `0.1.0`, charts say `v1.2`, README says v1.1).
   - Add `[build-system]` and `[project.scripts] budget = "budget_aggregator.cli:main"`.
   - Remove the empty `[tool.uv.workspace]` table and `managed = true`.
   - Relax `requires-python` to `>=3.11` unless 3.13 is needed.
   - Dependency groups: `dev` (pytest, ruff), optional `ui` (streamlit, plotly).
   - Pin torch to the CPU-only index via `[tool.uv.sources]`; the default Linux wheel pulls
     several GB of CUDA libraries for a 33 MB model.

3. **First-run model download.**
   The offline flags are set unconditionally, so a fresh clone fails with no cached model and
   the README does not say how to get it.
   - Add `budget fetch-model` (one explicit online step), then stay offline.

4. **CLI mode** (already on the roadmap)
   - `budget run a.csv b.csv --out DIR --no-charts`; fall back to the Tk picker only when no paths are given.
   - Output directory configurable; `~/Downloads` stays the default.

5. **Repo hygiene**
   - Delete `main.py` (stub).
   - `.gitignore`: `*.json` is ignored while `mapping/category_map.json` is tracked; add
     `!mapping/*.json` and `!tests/fixtures/*.csv`. Stop ignoring `.python-version`.
   - Add ruff config and a pre-commit hook that blocks any `.csv`/`.xlsx` outside `tests/fixtures/`.

6. **Performance**
   - Categorise unique descriptions once and map back, instead of `df.apply` per row.
   - Batch-encode all Layer 3 descriptions in one `model.encode` call.
   - Load the encoder lazily, only if something reaches Layer 3.

---

## Phase 2 — Tests

1. Synthetic fixture CSVs for each bank (fake merchants, fake amounts), including an NFCU file
   with the `transactions` title row and rows with a blank category.
2. Parser tests: detection, sign convention, column schema.
3. Categoriser tests: case-insensitivity, word boundaries, longest-key-first, fuzzy false positives on short keys.
4. Analytics tests: spending totals equal the sum of negative amounts; income separate.
5. GitHub Actions: `uv sync`, `ruff check`, `pytest` (skip encoder tests or stub the model).

These fixtures also make the README's "a sample CSV is attached" line true; today none exists.

---

## Phase 3 — Streamlit app

Recommendation: yes, worth doing, after Phases 0–1. It replaces the Tk picker and the static
PNGs, and it enables the one feature the CLI cannot do well: reviewing and correcting categories.

**Name the file `app.py`, not `streamlit.py`.** A script called `streamlit.py` shadows the
`streamlit` package and `import streamlit` breaks.

1. **Privacy config** (`.streamlit/config.toml`, committed)
   - `browser.gatherUsageStats = false` (Streamlit sends usage telemetry by default).
   - `server.address = "localhost"`, `server.headless = true`.
2. **Upload page**: `st.file_uploader(accept_multiple_files=True)`, per-file detected bank, skipped files shown with the reason.
3. **Transactions page**: filterable table (date range, bank, category, match method, confidence).
4. **Review queue**: uncategorised and low-confidence rows in `st.data_editor`; saving a
   correction writes the merchant to `category_map.json`, so the next run gets it at Layer 1.
   This is the highest-value feature in the plan.
5. **Dashboard**: spending by category per month, income vs spending, per-bank trend, month-over-month
   table. Use Plotly for hover and zoom; keep the matplotlib export for PNGs.
6. **Export**: download buttons for the master CSV and summary instead of writing to `~/Downloads`.
7. **Caching**: `st.cache_resource` for the encoder and attractor index, `st.cache_data` for the pipeline.
8. Run with `uv run streamlit run src/budget_aggregator/app.py`; the CLI stays for scripted use.

---

## Phase 4 — Features already on the roadmap

1. **Transfer neutralisation**: match a debit in one account to an equal credit in another within
   a 3-day window; flag as `Transfer` and exclude from spending. Without this, a card payment is
   counted in both the checking export and the card export.
2. **Duplicate detection** across overlapping exports (date + amount + description + bank).
3. **More parsers** (Chase, Amex, BoA). Add a `Parser` protocol (`name`, `detect`, `parse`) so
   the registry is type-checked and the bank name is not derived from the module name.
4. **User overrides file** outside the repo (e.g. `~/.config/budget-aggregator/category_map.json`)
   layered over the shipped map, so personal merchants are not committed.

---

## Phase 5 — README

- "Reads from ~/Downloads" is inaccurate: input comes from a file picker.
- Pipeline is called 5-layer in the README and 4-layer in the code.
- Add the model-download step, the CLI and Streamlit commands, and a dashboard screenshot from fixture data.
- Bring the roadmap in line with this plan.

---

## Suggested order

| Step | Scope | Size |
|------|-------|------|
| 1 | Phase 0 items 1–5 + fixtures and tests for them | small |
| 2 | Phase 1 layout, `pyproject`, CLI, model fetch | medium |
| 3 | Phase 0 item 6 (taxonomy) + Phase 1 performance | small |
| 4 | Phase 3 Streamlit (upload, table, dashboard) | medium |
| 5 | Review queue writing back to the map | medium |
| 6 | Transfer neutralisation, dedupe, new parsers | ongoing |
