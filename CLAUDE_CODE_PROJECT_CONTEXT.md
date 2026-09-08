# IESS2047 Compiler Project Context & Working Instructions

## What We Are Building

We are building a true Excel execution engine / compiler for the IESS2047 energy model workbook.

The goal is NOT:

* Excel automation
* xlwings
* Graph API
* LibreOffice execution
* Windows-only execution
* workbook-specific hardcoding

The goal IS:

* Parse workbook structure
* Extract formulas
* Extract named ranges
* Extract tables
* Build dependency graph
* Execute workbook logic in Python
* Run on Windows, Linux, MacOS
* Support future deployment as API/service
* Support custom scenarios without Excel

Think of the workbook as source code.

Think of Python as the runtime.

The workbook should eventually become:

Workbook -> Compiler -> Runtime

not

Workbook -> Excel -> Runtime

---

## Architecture Philosophy

We are building a "German Engine", not a "Japanese Engine".

Japanese Engine:

UI -> Excel -> Calculation -> Output

German Engine:

UI -> Compiler Runtime -> Output

Excel is only the source language.

Excel is NOT the runtime.

The runtime must understand:

* formulas
* dependency chains
* structured references
* named ranges
* MATCH
* INDEX
* INDIRECT
* tables
* scenario switching
* custom lever overrides

without Excel being present.

---

## Current State

The compiler exists.

Current major modules:

* workbook_model.py
* evaluator.py
* engine.py

The runtime can:

* load workbook
* load formulas
* load cached values
* extract tables
* extract names
* evaluate formulas
* execute dependency chains
* perform scenario recalculation

Custom scenario propagation has already been demonstrated.

Changing input values propagates through the dependency graph and affects downstream outputs.

This means the architecture itself is working.

We are now in semantic compatibility mode.

---

## Current Validation Status (as of 2026-06-25)

**78/78 flow edges match Excel within 0.5 Mtoe. 72/78 non-zero outputs. Zero engine gaps workbook-wide — every formula evaluates. Full-precision audit (Excel raw vs. compiler raw, not rounded) confirmed parity on the two chains that initially looked mismatched — see Fix 6.**

This is the trusted, current baseline. Do not treat any earlier number (77/78, 9/78, 18/78) as current — see "The Diagnostic Tooling Incident" below for why those numbers existed and why they're obsolete. Also note: "0 engine gaps" and "matches Excel" are two different claims — a formula can evaluate without error and still be numerically wrong, which is exactly what Fix 6 caught. Always validate at full precision before declaring a chain correct.

---

## The Diagnostic Tooling Incident (read this before trusting any historical number)

At one point the project believed the compiler had regressed from ~77/78 to 9/78, which drove a lot of debugging effort aimed at the wrong target.

Root cause: there were **two separate workbook-loading implementations** in the codebase.

* `run_real.py` (now deleted) re-implemented its own openpyxl extraction using `read_only=True` for the formulas pass.
* The real engine path — `WorkbookModel.load()` → `ModelEngine.load()` → `Evaluator` — uses `read_only=False`.

**openpyxl silently drops structured `Table` objects (`ws.tables`) when a worksheet is opened with `read_only=True`.** `run_real.py` was therefore always evaluating against a workbook model with **0 tables**, so every formula depending on a structured table reference resolved to 0. That produced the falsely catastrophic "9/78" reading. It was never a real regression — it was a broken measuring instrument.

**Lesson, stated as a permanent rule:** *A broken diagnostic is worse than a broken compiler.* If the measurement path is wrong, every debugging decision built on it is suspect.

**Rule going forward: there must be exactly one workbook-loading pipeline.** Every script — validators, diagnostics, ad hoc inspection tools — must call `ModelEngine.load(...)` and consume the engine. No script may reimplement openpyxl extraction itself. If you are about to write a new diagnostic script, audit it against this rule before trusting its output.

The actual trusted path, always:

```text
Workbook
    ↓
WorkbookModel.load()      (openpyxl, read_only=False for formulas)
    ↓
ModelEngine.load()
    ↓
Evaluator
```

`count_flows.py` and `run_full.py` both go through this path and are the scripts to trust for validation numbers.

---

## Known Engine Gaps (historical — resolved this session, kept for reference)

The gap categories that existed before this session's fixes:

* `no match` (1848 occurrences — largest category)
* `unknown table` VII.c.Outputs / I.e.Outputs / IV.f.Outputs / I.d.Outputs (268 occurrences combined)
* `unknown column` references across Industry_Data_2, XVI.a.Inputs, Input_Data, etc. (262 occurrences)
* `cannot resolve INDIRECT('Vector'!Year.Matrix)` (48 occurrences)

All four categories were root-caused and fixed (see "Engine Fixes Applied" below). Total gaps went from 2378 → 2 across the whole workbook.

These were genuinely engine-level semantic gaps, not workbook-specific bugs — confirming the project's instinct that "no match" should not be patched per-cell. Do NOT patch workbook-specific rows or cells.

---

## Engine Fixes Applied This Session (all in `compiler/evaluator.py`)

All four fixes are general Excel-semantics corrections — none reference a sheet name, row number, or output name. Each was investigated with the standard format (problem → evidence → root cause → diff → side effects) and approved before applying.

### Fix 1 — IFERROR evaluated its arguments eagerly

**Problem:** `IFERROR(INDEX(...), MATCH(...), 0)` formulas (1848 of them) were logged as engine gaps instead of falling back to `0`.

**Root cause:** The evaluator is a recursive-descent parser that evaluates as it parses (no separate AST stage). `_parse_args` evaluates every function argument *before* the function is dispatched. So when `MATCH` raised `EvalError("no match")` while building `IFERROR`'s argument list, the exception escaped before `IFERROR`'s own `try/except` body (inside `_dispatch_function`) ever ran. Verified directly: across a full run, `IFERROR`'s dispatch body was entered only 264 times despite 1848 gap cells being wrapped in `IFERROR`.

**Fix:** Special-cased `IFERROR` in `_parse_ident` to split its raw, un-evaluated tokens (new `_split_call_args` helper, which respects nested paren/bracket depth), then evaluate the first argument inside a `try/except EvalError`, falling back to the second argument on failure or on an `ERROR` sentinel result. This matches Excel's true lazy-evaluation semantics for `IFERROR`. Scope was deliberately limited to `IFERROR` only — `IF`/`CHOOSE` keep eager evaluation since that wasn't the reported problem.

**Result:** eliminated the entire `no match` (1848x) and `unknown table` (268x) categories — the unknown-table gaps were also `IFERROR`-wrapped `INDIRECT(...)` chains hitting the same escape path.

### Fix 2 — Structured-reference specifiers (`#Headers`, `#Data`, `#All`, bare `[]`) misparsed as literal column names

**Problem:** `Industry_Data_2[#Headers]` and `Industry_Data_2[]` were raising `unknown column ... in Industry_Data_2` (262 gaps).

**Root cause:** Two compounding issues. (1) The tokenizer's `ident` regex didn't include `#` in its character class, so `#` was silently dropped character-by-character during tokenization — `[#Headers]` tokenized as plain `Headers`, indistinguishable from a real column literally named "Headers". (2) `_resolve_table_column` had no special-case handling for the Excel structured-reference keywords `#Data`/`#Headers`/`#All`, or for empty brackets (`TableName[]`, which some workbooks serialize as shorthand for the whole data body) — it always tried (and failed) a literal column-name lookup.

**Fix:** Extended the tokenizer's `ident` pattern to optionally allow a leading `#`. Added explicit handling in `_resolve_table_column` for `""`/`#Data` (whole data body range), `#Headers` (header row range), and `#All` (headers+data range), before falling through to the per-column lookup.

**Result:** eliminated the entire `unknown column` category for these specifier forms; gaps dropped 262 → 50.

### Fix 3 — Missing implicit intersection for whole-row/column references used in scalar context

**Problem:** `INDIRECT("'"&XVI.a.Inputs[#Headers]&"'!Year.Matrix")` (48 gaps) — every column of a formula row built the *same* INDIRECT string regardless of which column the formula was actually in.

**Root cause:** `XVI.a.Inputs[#Headers]` returns a `RangeRef` spanning the whole header row (one cell per table column). `_scalar()`, used to collapse a `RangeRef` to a single value for the `&` concatenation operator, always took `cells[0]` unconditionally. Real Excel performs *implicit intersection*: when a whole-row or whole-column structured reference is used in a scalar context from a formula cell that itself falls within that row/column's span, Excel intersects it down to the single cell aligned with the calling formula's own row or column.

**Fix:** Added an optional `ctx=(sheet,row,col)` parameter to `_scalar()` (default `None`, so all other ~50 existing call sites are unaffected). When `ctx` is supplied and the `RangeRef` is a single row spanning multiple columns (or single column spanning multiple rows) on the same sheet as the caller, and the caller's column (or row) falls within that span, intersect to that one cell. Wired `ctx` through at the one call site that needed it: `_parse_concat`'s `&` operator.

**Result:** each column's formula now correctly resolves its own header cell rather than copying column 1's value into every column.

### Fix 4 — Nested structured reference `TableName[[#This Row],[ColumnName]]` not parsed at all

**Problem:** Same `Year.Matrix` cluster also used `XVI.a.Inputs[[#This Row],[Vector]]` — the standard Excel "current row, specific column" structured reference. This wasn't just failing — it was **corrupting parsing of the rest of the formula**, because `_parse_table_ref` stopped consuming tokens at the *first* `]` it encountered (the inner one closing `#This Row`), leaving `,[Vector]]` unconsumed in the token stream for everything parsed afterward.

**Root cause:** `_parse_table_ref` was written only for the single-specifier form (`Table[Column]`) and had no handling for the two-part, doubly-bracketed row+column specifier form.

**Fix:** `_parse_table_ref` now detects a nested `[` immediately following the outer `[` and, in that case, reads two bracketed specs via new helpers `_read_bracket_spec` / `_read_spec_body` (which also preserve the single space between adjacent word tokens, so `#This` + `Row` reconstructs as `"#This Row"` instead of `"#ThisRow"`). When the row spec is `#This Row` and a column spec is present, it resolves the column's range and applies the same implicit-row-intersection logic from Fix 3 to pick out the current row's cell.

**Result:** combined with Fixes 2–3, this cluster's 48 gaps resolved fully; remaining workbook-wide gaps dropped to 2.

### Fix 5 — MATCH ignored its match_type argument and always did exact matching

**Problem:** The final 2 gaps: `=INDEX(Sectoral_GDP[],MATCH(K$8,Sectoral_GDP[Agriculture]),2)`. `K$8` is a year (2047); `Sectoral_GDP[Agriculture]` is a column of GDP-share fractions that never equals 2047 — so an exact match can never succeed. Yet Excel's own cached value for these cells is a real number (`0.068`, `0.345`), not an error.

**Root cause:** Excel's `MATCH` third argument (`match_type`) defaults to `1` ("approximate match": find the largest value ≤ target, assuming ascending order) when omitted — it is **not** an exact match by default. `_fn_match` ignored `args[2]` entirely and always performed exact matching, raising `EvalError("no match")` whenever no exact hit existed. Since every value in the Agriculture column is far smaller than the target year, Excel's approximate-match scan settles on the *last* row — which is exactly what the cached values (`0.068`, `0.345`, both last-row values in their respective columns) confirm.

**Fix:** `_fn_match` now reads `match_type` from `args[2]` (default `1`, matching Excel). `match_type == 0` keeps the existing exact-match behavior unchanged (this is the form already used by ~1846 other working calls in the workbook, e.g. `MATCH(x, y, 0)`). `match_type == 1`/`-1` perform a linear scan tracking the best candidate seen so far (largest value ≤ target / smallest value ≥ target respectively), matching Excel's actual scan behavior rather than requiring a true sort.

**Result:** the final 2 gaps resolved with cached-value-exact results (`0.068`, `0.345`). **Engine gap count: 0. Every formula in the workbook now evaluates.**

### Fix 6 — full-precision parity audit found 1 more root cause behind 2 chains (`INDEX(range,,col)` omitted argument)

Zero engine gaps does not mean zero wrong values — a formula can evaluate cleanly to the *wrong* number. A full-precision comparison (Excel raw values vs. compiler values, not rounded to 2 d.p.) found 7 of 78 flow rows mismatching across 53 of 624 data points. Rather than treating this as 7 bugs, the mismatches clustered into exactly two dependency chains:

* **Chain 1 (Coal):** Coal Imports → Coal→Solid → Solid→Thermal Generation → Thermal Generation→Electricity Grid / →Losses. Differences varied by year, converging to ~0 at 2047.
* **Chain 2 (Solar CSP):** Solar→Solar CSP → Solar CSP→Electricity Grid. Difference was a **constant +0.0397 across every single year**, including the Base year — a dead giveaway of a missing/zeroed additive term rather than a calculation error.

**Trace (Solar CSP chain, upstream from the flow edge):** `Flows!17,L` → `IV.b.Outputs[R.01]` row 258 (`=-H212` etc.) → `IV.b!212` (`=H211*constant`) → `IV.b!211` (`=H209*H210`) → `IV.b!209` (`=H104`) → `IV.b!104` (`=IF(input.choice=1, CHOOSE(...), H103)`) → since `input.choice=2`, falls to `H103` (`=H93+H83`) → `H83`:
```excel
=INDEX(csp.capacity,MATCH(INDIRECT("base.year"),INDEX(csp.capacity,,2),0),4)
```
This cell alone evaluated to `0` instead of `0.229` — exactly the size of the constant offset found at the flow level, confirming this was the single source.

**Root cause:** `INDEX(csp.capacity,,2)` uses the standard Excel idiom of an **omitted argument between two commas** to mean "row_num omitted → return the entire column as an array" (here, column 2 of `csp.capacity`, fed into `MATCH` as the lookup vector). Two compounding bugs:
1. **Parser (`_parse_args`):** had no concept of an empty argument slot. On hitting the second comma with nothing parsed yet, `_parse_primary`'s catch-all "unknown token, skip it" branch silently consumed the *next real token* (`2`) instead of recognizing the empty slot — corrupting the rest of the argument list for the whole formula.
2. **`_fn_index`:** had no handling for `row_num=0` (whole column) or `col_num=0` (whole row) — it always computed a single flat cell index, which for `row_num=0` produces a negative index and falls through to a default `0` return instead of an array.

**Fix:** `_parse_args` now checks, before calling `_parse_expr`, whether the next token is immediately `comma` or `rparen` — if so it pushes `0` for that argument slot without consuming the delimiter (general fix: any function with an omitted argument anywhere in the workbook benefits, not just `INDEX`). `_fn_index` now special-cases `row_num=0`/`col_num=0` to return the whole matching column/row as a `RangeRef`, before falling through to the existing single-cell-index logic (unchanged for every other call).

**Result:** both the Coal and Solar CSP chains now match Excel's full-precision values to within floating-point rounding (differences ≤ 1e-6, displayed as `-0.0`/`0.0`). **Full re-validation: 78/78 flow matches, 0 engine gaps, and full-precision parity confirmed on the previously-mismatching chains.**

---

## Critical Rule

Never solve a problem using:

```python
if sheet == "IV.a":
```

or

```python
if row == 148:
```

or

```python
if output == "Solar":
```

or any workbook-specific logic.

Every fix must improve the engine generally.

If a fix only works for IESS2047, reject it.

---

## Investigation Method

When debugging:

DO NOT start from workbook outputs.

DO:

1. Identify mismatch
2. Trace dependency chain upstream
3. Find first divergence
4. Explain divergence
5. Propose engine-level fix

Example:

Wrong:
I193 is wrong -> patch I193

Correct:
I193 -> I150 -> I148 -> upstream source -> first divergence

---

## Change Control Requirements

Before making ANY code change:

1. Explain the bug
2. Explain root cause
3. Explain why it occurs
4. Show exact code to be changed
5. Show old code
6. Show new code
7. Explain side effects
8. Wait for approval

Do not modify files immediately.

Do not auto-apply fixes.

Do not rewrite modules without approval.

Always ask before making changes.

---

## Expected Response Format

For every proposed change:

### Problem

What is wrong?

### Evidence

What traces prove it?

### Root Cause

What engine behavior causes it?

### Proposed Fix

Show exact code diff.

### Risk Assessment

What else could break?

### Approval Required

Wait for approval before changing code.

---

## Custom Lever / Scenario Verification (post full-validation phase)

After reaching 78/78 flow matches with 0 engine gaps, the next question was: does the engine actually support **custom scenario propagation** through the workbook's real lever system — the "Custom Pathway" UI shown in the workbook (sliders per technology/sector, Level of Ambition 1–4) — not just static formula evaluation?

### The lever system, as it actually exists in the workbook

The lever panel lives on the **`Control`** sheet: one row per lever, with columns:
- Column D = lever name
- Column E = "YOUR CHOICE" (the current 0–4/0–5 level value — this is the actual input cell)
- Column F = "LIMIT" (the max level allowed for that lever; usually 4, sometimes 3 or 5)

There are **51 real, usable levers** (a few rows are section headers with no value and were excluded). They cover both sides of the energy balance:
- **Supply:** Conventional Energy (Gas/Coal/CCS Power Stations), Renewable & Clean Energy (Solar PV, CSP, Distributed PV, Onshore/Offshore Wind, Nuclear, Large/Small Hydro), Bioenergy, Fossil Fuel Production (Domestic Coal/Gas/Oil), T&D/Trade/Storage.
- **Demand:** Transport (Passenger/Freight demand & mode shift, EVs), Buildings (floorspace growth, ACs, ECBC compliance), Industry (energy intensity, fuel mix, fuel switching for Cement/Steel), Cooking (fuel shift, cookstove efficiency), Agriculture & Telecom.
- **Economics:** GDP growth, Capital/Fuel/Infrastructure/Finance costs.

A user-provided screenshot of this exact lever panel UI was checked row-by-row against the `Control` sheet — every category and lever name in the screenshot maps onto a real `Control` sheet row. **The topic coverage matches completely** — this is not a partial/supply-only compiler.

### Two mode-switches gate the lever panel

Two cells must be set correctly for `Control` sheet levers to have any effect at all — otherwise the workbook is in a different input mode and lever changes are silently ignored (this is correct Excel behavior, not a bug, but it surprised us once):

- `'Target Year Input'!E10` — "Input method to the model": `1` = Pre-defined trajectories (lever-driven, what the screenshot shows), `2` = direct numeric entry on the `User-defined drivers` sheet. The workbook's saved default is `2`.
- `'IESS V3 Main Sheet'!E12` — "Predefined scenario": `0` = "None" (Custom Pathway — per-lever control), `1`–`4` = a preset bundled scenario that **overrides individual lever choices entirely**. The workbook's saved default is `2` (a preset), not `0`.

**Always set both of these to `1` and `0` respectively before testing/demoing individual levers**, e.g.:
```python
eng.set_lever("Target Year Input", "E10", 1)
eng.set_lever("IESS V3 Main Sheet", "E12", 0)
```
Forgetting this makes lever changes look like they "don't work" when actually the workbook is just correctly honoring a different active input mode.

### Verified: levers genuinely propagate, both supply and demand side

With the two switches set, moving `Control!E<row>` from level 1 to level 4 was confirmed to change the correct downstream `Flows` output for: Solar Photovoltaic, Onshore Wind, Domestic Gas Production, Domestic Coal Production (supply side), and Energy Intensity of Industry, Passenger Transport Demand, Commercial Floor Space, Fuel Shift/Cookstove Efficiency, Telecom electrification (demand side). This is captured in `xlcompiler/demo_lever_propagation.py`, a standalone script that sets each lever to level 1 and level 4 and asserts the paired Flow output actually changed.

**One nuance worth remembering:** picking the *correct* downstream flow to watch matters. "Coal Power Stations" (capacity lever) only shifts the coal/gas *mix* within a total electricity output that's fixed by demand — it does **not** change total generation, so watching "Thermal Generation → Electricity Grid" shows no change and looks like a false failure. The correct pairing is the *production*-side lever ("Domestic Coal Production") against the *production*-side flow ("Coal Production → Coal"). Similarly, "Domestic Coal/Gas Production" levers shift the **production vs. imports split** for a fuel whose *total* (production + imports) is demand-determined — so a combined "total coal supply" metric can look flat even while the lever's real effect (production up, imports down by the same amount) is large. Always check production and imports as separate numbers, not a summed total, when verifying these levers.

---

## Live Demo Web App (`xlcompiler/demo_app.py`)

A small local Flask app was built to let someone move sliders and see the real engine recalculate live — no precomputed JSON, no cached scenario table. Run with `python demo_app.py` from `xlcompiler/`, open `http://127.0.0.1:5000/`.

**What it contains:**
- All 51 real levers from the `Control` sheet, pulled programmatically (name, current value, per-row level limit) and grouped into collapsible categories — not hardcoded to a handful of "demo" levers.
- The two mode-switches (`Target Year Input!E10=1`, `IESS V3 Main Sheet!E12=0`) are set once at startup so the panel is "live" by default.
- An **Outputs** section split into three separate boxes — **Supply**, **Demand**, **Balance** — rather than one flat table, so supply-side and demand-side results are visibly distinct. The Demand box also lists every sector's individual 2047 value (Buildings, Industry, Transport, Agriculture, Telecom, Cooking, Miscellaneous), not just a combined total.
- A stacked **"Energy Demand by Sector"** line/area chart (2022–2047, via Chart.js) showing the same 7 sectors plus a Total line, recalculated on every lever change.
- Slider changes use the `input` event with a ~250ms debounce (not `change`) so the UI feels responsive while dragging, and any fetch/recalc failure surfaces a visible red error message instead of silently doing nothing.

**Bugs hit and fixed while building this, worth remembering for next time:**
1. A literal `width: 100%` in the page's inline CSS collided with Python's old-style `%`-string templating (`PAGE_TEMPLATE % {...}`), causing a `500 Internal Server Error`. Fixed by switching to plain `str.replace()` placeholder substitution (`__N_LEVERS__`, `__CATEGORIES_HTML__`, `__IDS_JSON__`) instead of `%`-formatting — avoids this whole class of bug for any future HTML/CSS template work.
2. **Windows allowed multiple Python processes to simultaneously bind to port 5000** across several `nohup`/restart cycles in this session — `netstat -ano | grep 5000` repeatedly showed 2+ PIDs `LISTENING` on the same port at once. This produced exactly the symptom "I changed the lever but the output never changes" because the browser could be talking to a stale process running old code. **Lesson:** when a local dev server "isn't picking up changes," always check `netstat -ano | grep <port>` for duplicate listeners before assuming the code is wrong, and kill *all* of them before restarting, not just the most recent one.
3. The output metric originally summed "Coal Production + Coal Imports" into one number, which is constant by construction (model holds total fuel demand fixed and trades production against imports) — this made the Coal/Gas levers look inert even though they were working correctly underneath. Fixed by splitting Domestic Production and Imports into separate displayed numbers.

---

## Project Folder Cleanup (2026-06-25)

`xlcompiler/` was cleaned of one-off diagnostic scripts and log dumps left over from earlier debugging phases (percentage-literal bug, table-loading `read_only` bug, BI146 cascade investigation) — all of these issues are resolved and already documented above, so the scripts were no longer needed: `INVESTIGATION_SUMMARY.txt`, `diagnose_full.txt`, `diagnose_output.txt`, `percentage_audit_report.txt`, `build_synthetic.py`, `test_compiler.py`, `test_cascade.py`, `test_table_resolution.py`, `inspect_grid_balance.py`, `inspect_model.py`, `inspect_unit_gw.py`, `trace_dependencies.py`, `percentage_audit.py`, `diagnose_tables.py`, plus `__pycache__/`.

**What remains in `xlcompiler/`:** `compiler/` (the engine), `count_flows.py` + `run_full.py` (the two trusted validators), `demo_lever_propagation.py`, `demo_app.py`.

**Left untouched deliberately:** `~$IESS2047_Version_3.0.xlsx` (Excel lock file — risk of disrupting an open Excel session), `IESS2047_Version_3.0.xlsx.compiled.pkl` (legitimate `WorkbookModel` load cache, not clutter), `fullcomparision.md` (a report the user authored/pasted, not generated by this assistant). **Note: this project is not a git repository**, so any future deletions are not trivially reversible — always list candidates and get explicit confirmation before removing files, the same way this cleanup was done.

---

## Long-Term Goal

End state:

User adjusts levers through UI.

Compiler runtime recalculates the model.

Outputs update without Excel.

Workbook becomes a source language.

Python becomes the execution engine.

All solutions should move the architecture toward that goal.

---

## Session Notes (2026-06-29) — Demo Readiness Q&A

Project status reaffirmed ahead of a live demo: 78/78 flow matches, 0 engine gaps, lever propagation verified (supply and demand sides), `demo_app.py` confirmed functional. Two questions came up worth recording permanently.

### Q: Why does the "Balance" box not move when a supply lever changes, but does move when a demand lever changes?

**Not a bug.** The model is demand-anchored: total final demand is computed from the demand-side drivers, and total supply is constrained to equal it by construction (an accounting identity, not two independently-computed numbers that happen to coincide).

- Moving a **demand lever** (e.g. Industry energy intensity, Passenger Transport demand) changes `total_demand` directly, so the balance (`total_supply - total_demand`) shifts too.
- Moving a **supply lever** (e.g. Domestic Coal Production, Solar PV capacity) changes the *mix*/composition of supply — the production-vs-imports split for fossil fuels, or which technology supplies the energy — but the aggregate `total_supply` across all `PRIMARY_SOURCES` rows stays pinned to the same total, because the workbook forces supply to balance against the (unchanged) demand total.

This is the same nuance already documented under "Custom Lever / Scenario Verification" above (the "Coal Power Stations" lever shifting mix, not total). To observe a supply lever's real effect, watch the individual breakdown fields in `compute_outputs()` (`domestic_production` vs `imports`, `renewables`, `nuclear`) rather than the aggregate balance, which is expected to stay flat under supply-mix levers and move only under demand levers.

### Q: Can this same compiler work, with small tweaks, on other similar Excel workbooks?

**Yes, by design.** The engine core (`workbook_model.py`, `evaluator.py`, `engine.py`) is general-purpose Excel semantics — formulas, named ranges, tables, INDEX/MATCH/INDIRECT, dependency-driven recalculation — and is workbook-agnostic per the Critical Rule above (no sheet/row/cell-specific logic in the engine itself).

What's workbook-specific and would need a small adapter layer for a new workbook (none of it requires touching the engine):
- `read_flows()` — assumes a `Flows`-sheet-shaped table; a new workbook needs its own flow-sheet reader pointed at its actual layout.
- `demo_app.py`'s lever discovery — assumes a `Control`-sheet-shaped lever table with name/value/limit columns; a new workbook needs its own column mapping.
- The two mode-switch cells (`Target Year Input!E10`, `IESS V3 Main Sheet!E12`) — only relevant if the new workbook has an analogous scenario-vs-preset input-mode concept.
- Output classification sets (`PRIMARY_SOURCES`, `FINAL_DEMAND_SECTORS`, sector groupings) — domain-specific row names for that workbook.

**Caveat:** a new workbook using an Excel function not yet implemented in `evaluator.py` would surface as a new engine gap. Fix it the same general way as Fixes 1–6 (trace → root cause → general fix), never as a per-workbook patch — consistent with the Critical Rule.

### Q: Does the engine trace results off the Flows sheet specifically — i.e. does it need a Flows-style sheet to function, the way some other tools require a fixed "WebOutput" sheet?

**No. Verified by direct grep across the engine source — zero hardcoded sheet-name dependency.**

`evaluator.py` and `workbook_model.py` contain no sheet-name references at all (`grep` for `"Flows"`, `"Control"`, `"WebOutput"`, `sheet ==` returns nothing in either file). The only sheet name anywhere in the engine layer is in `engine.py`'s `read_flows(self, flows_sheet="Flows", from_col="C", to_col="D", year_cols=(...), first_row=6, max_rows=200)` — and that's a **default argument value**, fully overridable by the caller, not a requirement baked into the logic.

**What this means concretely:**
- The core evaluator computes any cell on any sheet the same way: it reads the cell's formula, recursively resolves whatever it references (other cells, tables, named ranges, other sheets), and returns the final value — by re-deriving it from scratch each time, the same way Excel's own recalculation would. There is no special-case path for a "results" or "output" sheet.
- `read_flows()` is not part of the calculation engine — it runs *after* calculation is done, and its only job is to read already-computed values out of known column positions on whichever sheet you name. It is a configurable convenience reader, not a dependency. You could call `eng.ev.eval_cell(sheet, row, col)` directly on any cell, on a workbook with no Flows-style sheet at all, and get a correct answer.
- The IESS2047 workbook's `Flows` sheet is the original author's own pre-built report (formulas pulling together final answers for human readability) — useful to us as a ready-made answer key for validation and for the demo UI, but not something the compiler relies on to operate.

**Correct framing for the spec:** the engine has no required, fixed output-sheet structure (unlike tools that hardcode something like a "WebOutput" sheet). Any cell, on any sheet, in any workbook, can be evaluated directly and independently of whether a flow-summary sheet exists.

---

## Session Notes (2026-06-30) — Lever Propagation Mechanism & Demo UI Gap

### Q: Why does the "Coal Power Stations" lever visibly do nothing in the demo UI?

**Not a bug in the engine — a gap in the demo UI's output metrics.**

"Coal Power Stations" is a *capacity/mix* lever. It shifts the share of electricity generation coming from coal-fired vs. gas-fired thermal plants. It does **not** change `Coal Production`, `Coal Imports`, or `total_supply` — those are demand-anchored totals and stay flat by construction (the model forces total supply to balance against unchanged total demand).

The current `compute_outputs()` in `demo_app.py` only surfaces aggregate metrics (total supply, total demand, domestic production, imports, balance). There is no metric for generation mix (coal-fired share vs. gas-fired share of thermal output). So the lever's real effect exists underneath but is invisible in the UI.

**Correct pairing to observe this lever:** watch the coal-fired vs. gas-fired breakdown within Thermal Generation → Electricity Grid, not the aggregate supply total or Coal Production/Imports rows.

**Known nuance (already documented above under "Custom Lever / Scenario Verification"):** supply-mix levers shift composition, not totals. Always watch the specific production/imports split or technology breakdown, not a summed aggregate, when verifying supply-side levers.

---

### Q: How exactly do lever changes propagate to flow outputs — what is the mechanism?

**Three-step mechanism, no pre-built dependency graph required.**

#### Step 1 — `set_lever` writes into the override table and clears the entire cache

```python
# engine.py
def set_lever(self, sheet, a1, value):
    self.ev.set_override(sheet, r, c, value)

# evaluator.py
def set_override(self, sheet, row, col, value):
    self._overrides[(sheet, row, col)] = value
    self._cache.clear()   # ← entire result cache wiped
```

Moving a slider calls e.g. `eng.set_lever("Control", "E6", 2)`. That stores `("Control", 6, 5) → 2` in the override dict, then throws away every cached evaluation result. No dependency graph is needed — just invalidate everything.

#### Step 2 — `eval_cell` re-derives results recursively on demand

```python
# evaluator.py
def eval_cell(self, sheet, row, col):
    if key in self._overrides:
        return self._overrides[key]   # lever value wins immediately
    if key in self._cache:
        return self._cache[key]       # saved result wins
    # else: parse the formula string and evaluate it right now,
    # recursively calling eval_cell for every cell it references
    result = self._eval_formula(cell.formula, ...)
```

Every formula cell is computed by parsing its formula string and recursively calling `eval_cell` on every cell it references. Those cells do the same. Evaluating a single Flows output cell triggers a recursive tree walk all the way back through intermediate calculation sheets to the input cell, where the override intercepts and returns the new lever value.

#### Step 3 — `read_flows` just calls `eval_cell` on every Flows row

```python
# engine.py
for r in range(first_row, first_row + max_rows):
    frm  = self.ev.eval_cell("Flows", r, fc)
    to   = self.ev.eval_cell("Flows", r, tc)
    vals = [self.ev.eval_cell("Flows", r, yc) for yc in ycs]
```

No pre-computed answer exists anywhere. Each call triggers the full recursive re-evaluation of that cell's formula tree, which eventually reaches `Control!E<row>` somewhere deep in the chain, finds the override, and propagates the new value all the way back up to the Flows output.

#### Concrete chain for Coal Power Stations

```
Flows!row (formula)
  → IV.b.Outputs[column] (formula in the sector output sheet)
    → IV.b!intermediate cell (formula)
      → IF(input.choice = 1, CHOOSE(Control!E6, ...), ...)
                                        ↑
                              override lives here — returns new lever value
```

#### One-line summary

Excel internally: *cell has formula → evaluate it → if a dependency changes, re-evaluate.*
This compiler: *cell has formula → parse + evaluate it → if an override is set, cache clears → re-evaluates.*

The workbook's own formulas are the source code. Python is the interpreter. No logic was rewritten or hardcoded. The evaluator walks the exact same dependency tree Excel would walk internally — just without Excel being present.

This is the "German Engine" stated concisely: **the workbook became source code, and the evaluator is the runtime.**

---

## Project Folder Cleanup (2026-06-30)

`run_real.py` and `op.py` deleted by user.

- `run_real.py` — the broken diagnostic script that caused the "9/78 incident". Used `read_only=True` which silently drops all table objects, and reimplemented its own openpyxl extraction instead of going through `ModelEngine.load()`. Violated the one-pipeline rule. Dangerous to have around.
- `op.py` — empty file (1 line), no purpose.

**Current clean folder structure:**
```
xlcompiler/
├── compiler/
│   ├── __init__.py
│   ├── engine.py
│   ├── evaluator.py
│   └── workbook_model.py
├── demo_app.py
├── count_flows.py
├── run_full.py
└── demo_lever_propagation.py
```

Every file has a clear purpose. `count_flows.py` and `run_full.py` are the two trusted validators — never remove them.

---

## Session Notes (2026-06-30) — Predefined Scenario Engine + Sankey UI Design

### What is being built next

Two additions to `demo_app.py` only — no engine changes required.

**1. Predefined scenario selector (dropdown, top-left)**

The workbook has four predefined scenarios (Level 1–4) controlled by `IESS V3 Main Sheet!E12`:
- `E12=0` → Custom Pathway (per-lever control via the 51 Control sheet sliders)
- `E12=1..4` → Predefined bundled scenario (overrides all individual lever choices entirely)

The UI will show a dropdown in the top-left:
```
[ Determined Effort — L2 ▾ ]
  → Baseline
  → Determined Effort — L1
  → Determined Effort — L2  ✓
  → Determined Effort — L3
  → Determined Effort — L4
  → Custom Pathway
```

The left sidebar shows lever groups (Economics, Supply, Demand, Costs) with level badges (L2, L3 etc).

**Key UX rules (enforced by the UI, not the engine):**
- When a predefined level is selected → all sliders are **physically disabled** (greyed out). The engine is in preset mode and ignores lever values; disabling sliders makes this impossible to miss.
- When the user **touches any slider** → the dropdown automatically switches to "Custom Pathway" (`E12=0`) before applying the lever change. No manual mode switching required.
- These two modes are mutually exclusive at all times — no ambiguous in-between state.

**Why the UI must enforce this (not the engine):** The engine is intentionally dumb — it just honors whatever overrides are set. If `E12=2` and a slider is also moved, the workbook formula `IF(E12=0, use_levers, CHOOSE(E12,...))` silently ignores the slider. This is correct engine behavior, not a bug. The UI must prevent the user from ever being in that silent-ignore state.

**Backend:** A new `/set_scenario` endpoint sets `E12` and returns recalculated outputs. `Target Year Input!E10` stays `1` throughout (set once at startup) — both modes require it.

**Note on the pkl and overrides:** `E10` and `E12` are stored in the pkl as their Excel-last-saved cached values (`E10=2`, `E12=2` by default). The startup code overrides both in memory (`E10=1`, `E12=0`). All scenario switching happens purely in the evaluator's override dict — the pkl is never modified.

---

**2. Sankey flow diagram**

A live Sankey diagram (D3 + d3-sankey via CDN) showing energy flows (from → to → Mtoe value) for the selected year (2047 default), drawn from `read_flows()` output.

- Updates on every slider move and every scenario switch — same `/recalc` response feeds both the output boxes and the Sankey
- `compute_outputs()` extended to return a `sankey` payload: `{nodes: [...], links: [{source, target, value}]}` filtered to non-zero edges only
- Renders as SVG below the demand chart

---

### Tabs question (deferred)

The reference UI (screenshot) shows tabs: `All Energy`, `Electricity`, `Energy Security`, `Emissions`, `Indicators`, `Costs`, `Energy Flows`, `Land & Water`. These are deferred — current build focuses on the `All Energy` view + Sankey first.

---

## Session Notes (2026-07-01) — UI Rebuild: Predefined Scenario + Custom Lever Hybrid

### The exact UX behavior (settled after discussion)

Sliders are **never disabled**. The predefined vs. custom distinction is a mode the UI tracks, not a lock on the controls.

**User selects L4 from dropdown:**
- Engine sets `E12=4` (predefined mode) via `/set_scenario`
- All 51 sliders visually snap to `4` (reflecting the L4 starting state)
- Outputs recalculate from the L4 preset

**User then drags, say, the Coal lever from 4 → 2:**
- UI automatically switches the dropdown back to "Custom Pathway" (`E12=0`)
- Coal slider shows `2`; every other slider stays at `4` (where L4 left them)
- `/recalc` fires with `E12=0` + all current slider values (coal=2, everything else=4)
- Engine runs: "L4 everywhere, except coal is overridden to 2" — propagates through the full dependency graph

**Net result:** a hybrid scenario. Predefined scenario used as a starting point; individual levers tweaked on top. Every downstream flow recalculates correctly because the evaluator just re-derives the full dependency tree from whatever overrides are currently set.

This is the core UX nuance: **predefined scenarios are a starting point, not a lock.**

---

### How the backend supports the hybrid model

Two endpoints, clean separation of concerns:

**`/set_scenario {"level": N}`**
- Sets `IESS V3 Main Sheet!E12 = N`
- Does NOT touch any `Control!E` lever cells
- Returns `compute_outputs()` result
- Used when: user picks a predefined level from the dropdown

**`/recalc {lever_id: value, ...}`**
- Always sets `E12=0` first (calling `/recalc` implies Custom Pathway by definition)
- Sets all `Control!E` lever values from the slider payload
- Returns `compute_outputs()` result
- Used when: any slider moves

**Why this works for the hybrid case:**
When user is in L4 mode and moves Coal, the other sliders still show `4`. When `/recalc` fires, it sends all slider values (coal=2, others=4). The engine sets E12=0 and sets every Control lever. The workbook formulas now run in Custom Pathway mode with every lever at 4 except coal at 2 — which is exactly the hybrid the user intended.

The engine itself needs no changes — it just honors whatever overrides are set.

---

### Sliders as source of truth

The slider DOM values are the single source of truth for the custom lever state. When a predefined scenario is selected, the UI sets all slider `.value` attributes to `N` programmatically. From that point on, any slider movement sends the full current slider state to `/recalc`. This means:
- No separate "current lever state" object needed in JS
- No risk of slider display diverging from what the engine received
- The hybrid scenario just falls out naturally — sliders show the truth, `/recalc` reads the truth

---

### Full UI rebuild scope (approved for implementation)

**Layout:** two-column — left sidebar (levers) + right main (outputs + charts)

**Top bar (sticky):**
- App title + sub-line
- Scenario dropdown: Custom Pathway | L1 | L2 | L3 | L4
- Status chip ("live · 14:32:01" or "recalculating…")

**Left sidebar — Levers:**
- All 51 levers in collapsible category groups
- Each row: name + slider + value badge
- No disabling — always interactive
- Moving any slider while dropdown shows a predefined level → dropdown auto-switches to "Custom Pathway"

**Right main area:**
- Row 1: Three output boxes (Supply / Demand / Balance)
- Row 2: Energy Demand by Sector stacked area chart (Chart.js, 2022–2047)
- Row 3: Sankey flow diagram (D3 v7 + d3-sankey via CDN, non-zero 2047 edges, updates on every recalc)

**`compute_outputs()` extended** to return `sankey: {nodes, links}` alongside existing metrics. Links filtered to `value > 0.001` to exclude noise.

---

## Session Notes (2026-07-03) — UI Attachment Planning

### Live re-validation (not just trusted from the doc)

Re-ran `count_flows.py` directly against the real workbook path and confirmed **78/78 flow matches, 0 mismatches, 72/78 non-zero outputs** right now — matching the 2026-06-25 baseline exactly. Folder structure also matches the documented "clean" layout with zero drift. Confidence in the baseline is not just inherited from this doc; it was independently reproduced.

**Minor housekeeping note (left as-is, not a bug):** `count_flows.py`'s default workbook path argument (`D:/2047-old/compiler/workbook/IESS2047_Version_3.0.xlsx`) is stale/machine-specific and doesn't exist on this machine. It's harmless — a CLI arg overrides it — and the user asked to leave it untouched.

### Decision: UI build location

Next step is attaching a real UI to the compiler. Agreed constraints:
- New UI code goes in a **new top-level `ui/` folder**, sibling to `xlcompiler/` (i.e. `compiler/ui/`, alongside `compiler/xlcompiler/`).
- The UI must **never modify `xlcompiler/compiler/`** (the engine itself — `workbook_model.py`, `evaluator.py`, `engine.py`). It only consumes the engine, same as `demo_app.py` already does.
- This keeps the trusted, validated engine fully isolated from UI churn.

### UI build is paused pending a reference image

The user is preparing a proper image/collage showing exactly how the UI should look, to replace/refine the written UI spec from the 2026-06-30 and 2026-07-01 session notes above (predefined scenario dropdown, lever sidebar, Supply/Demand/Balance boxes, sector chart, Sankey diagram). **Do not start building the UI until that image is provided** — match it as closely as possible once shared, using the existing written spec as a fallback/baseline only where the image doesn't specify something.

---

## Session Notes (2026-07-03) — `ui/` Dashboard Built: Milestone 1 (Sidebar + Scenario Dropdown + All Energy Tab)

### Reference images received

User supplied screenshots of the target dashboard: a multi-tab layout (`All Energy`, `Electricity`, `Energy Security`, `Emissions`, `Indicators`, `Costs`, `Energy Flows`, `Land & Water`), a left sidebar of levers grouped into 4 parent categories (Economics, Supply, Demand, Costs) with count badges, a scenario dropdown ("Determined Effort — L2"), 4 KPI stat tiles per tab, stacked-area/bar/line charts, a donut chart, and (on the `Energy Flows` tab) a Sankey diagram with a year-selector button row (2022/2027/2032/2037/2042/2047).

**Explicit requirement from the user, worth re-stating precisely:** picking a predefined scenario (e.g. L4) is a *starting point*, not a lock. If the user then drags one lever (e.g. Coal L4→L3) while every other lever stays at its L4 value, the engine must recompute the *whole* model correctly (already proven architecture — see "Lever Propagation Mechanism" above) **and the UI must visually flag which values actually changed** relative to the L4 starting point, not just show new numbers.

### Delivery scope decided with the user

Two `AskUserQuestion` clarifications were resolved before building:
1. **Staged delivery** (not all-at-once): this milestone = sidebar + scenario dropdown + **All Energy tab only**. Electricity and Energy Flows (Sankey) tabs are explicitly deferred to future milestones and currently render as disabled "Coming soon" tab-bar items.
2. **Changed-value highlighting is required** (not just updated numbers) — KPI tiles and chart series must visually flag when they differ from the L4 (or whichever level) baseline the user started from.

### What was built

New **top-level `ui/` folder**, sibling to `xlcompiler/` (at `d:\ACPET\IESS\Excel_Enging\compiler\ui\`). **`xlcompiler/compiler/` (the engine) was never touched** — confirmed by re-running `count_flows.py` after the build: still 78/78 flow matches, 0 mismatches.

```
compiler/
├── xlcompiler/          (untouched)
└── ui/
    ├── app.py            Flask app: engine loading, /, /set_scenario, /recalc
    ├── outputs.py        compute_outputs(), classification sets, diff_outputs()
    ├── levers.py         Control-sheet lever discovery, 4-group sidebar bucketing
    └── templates_str.py  PAGE_TEMPLATE (str.replace() tokens, not %-formatting)
```

Run with `python app.py` from `ui/`, opens on **port 5050** (deliberately different from `demo_app.py`'s 5000, so both can run side by side).

**`levers.py`** — re-buckets `demo_app.py`'s existing 12 fine-grained `CATEGORY_RANGES` into the 4 parent sidebar groups shown in the reference image (Economics, Supply, Demand, Costs), via a new `SIDEBAR_GROUP_ORDER` + a 3rd tuple element on each `CATEGORY_RANGES` entry. Same underlying Control-sheet-scan approach as `demo_app.py` — nothing hardcoded to specific lever names.

**`outputs.py`** — new classification sets built the same UI-layer way as `demo_app.py`'s (over `read_flows()` edge names, never inside the engine):
- `SUPPLY_SOURCE_GROUPS` (Coal / Oil & Products / Natural Gas / Renewables / Biomass / Nuclear & Others) — buckets `PRIMARY_SOURCES` for the new "Primary Energy Supply by Source" stacked-area chart and the "2047 Energy Mix" donut.
- `FUEL_CONSUMPTION_GROUPS` (Coal & Solid Fuels / Oil & Liquid Fuels / Natural Gas / Electricity) — sums `read_flows()` edges where `from` is one of the Sankey's intermediate carrier nodes (`Solid`, `Liquid`, `Natural Gas`, `Electricity Grid` — confirmed by directly enumerating distinct `from`/`to` node names in `read_flows()` output) landing on a `FINAL_DEMAND_SECTORS` node, for the "Fuel-wise Consumption" line chart.
- **Population/per-capita metric — new data source found:** `'IESS V3 Results'!J3` = Population (Millions) for 2047 (row 3 = "Population", columns D..K = years 2020/2022/2027/2032/2037/2042/2047/2030). Verified: `total_demand(Mtoe) × 41,868,000,000 MJ/Mtoe ÷ (population_millions × 1,000,000)` reproduces the reference image's `38,069 MJ/person` almost exactly from its own `1,448 Mtoe` demand figure — cross-validated the formula, not guessed.
- `diff_outputs(current, baseline)` — pure UI-layer boolean diff (`abs(a-b) > 1e-6`) over KPIs and chart series, same shape as the data it's diffing. No engine involvement.

**`app.py` — the important nuance found during testing:**

Initial design (per the approved plan) was to snapshot `/set_scenario`'s own Preset-mode output (`E12=level`) as the diff baseline. **Testing caught that this is wrong.** Direct comparison proved the workbook's Preset mode (`'IESS V3 Main Sheet'!E12=4`) and Custom-Pathway mode with every Control lever manually set to 4 (`E12=0` + all levers=4) are **not numerically identical** — they are genuinely separate calculation branches inside the workbook (e.g. `total_demand` differed: 924.85 vs 912.85 in one test run). Root cause: `Control!E<row>` cells are **plain input values, not formulas** — they never respond to `E12` changes at all; the CHOOSE(E12,...)-driven preset path documented earlier in this file bypasses the Control sheet entirely.

**Fix applied:** `/set_scenario` now computes and returns two different things:
1. **`display_data`** — the true Preset-mode result (`E12=level`), returned to the browser and shown as the tab's numbers when a scenario is first picked (matches what the workbook itself would show).
2. **`baseline_snapshot`** (server-side only, never sent to the browser) — the *Custom-Pathway* equivalent, computed by setting `E12=0` and every lever to `min(level, lever.max)`. This is what `/recalc` actually diffs against, since `/recalc` always operates in Custom-Pathway mode. Using the Preset-mode number as the diff baseline would have produced false "changed" flags on every KPI on the very first slider touch, unrelated to whatever lever the user actually moved.

**Verified correct with a controlled test** (Domestic Coal Production lever, `Control!E28`, L4→L2, every other lever held at L4):
- `total_demand`, `total_supply`, `per_capita_demand` → `changed: False` (correctly unaffected — matches the already-documented "supply levers shift mix, not totals" nuance from the 2026-06-29 session notes).
- `import_dependence` → `changed: True` (15.1% → 16.9%, correctly flagged — this lever shifts the domestic-production-vs-imports split, exactly as expected).
- A no-op recalc (every lever left at its L4 baseline value, nothing touched) correctly returned `changed: False` for every KPI — proving the diff isn't just always-on noise.

**Also hit the documented duplicate-port-binding bug again while testing** (`CLAUDE_CODE_PROJECT_CONTEXT.md`'s "Bugs hit and fixed" section under the Live Demo Web App) — `pkill` under Git Bash did not kill the actual Windows `python.exe` processes, leaving 3 stale servers simultaneously `LISTENING` on port 5050 across restarts, which made debug output look nondeterministic/wrong until `netstat -ano | grep 5050` + `taskkill //F //PID <pid>` cleared all of them. Same lesson as before, reconfirmed: **always check for duplicate listeners before trusting "the code is wrong."**

**Frontend (`templates_str.py`):** vanilla JS + Chart.js from CDN (no new dependency vs. `demo_app.py`). Sidebar sliders are never disabled; touching any slider auto-switches the scenario `<select>` to "Custom Pathway" and clamps the sent value to `min(level, slider.max)` before calling `/recalc`. KPI tiles get an amber ring (`.kpi.changed`) when `changed.kpis[key]` is true; stacked-area chart series that changed get a dashed amber border instead of their normal color, and the containing card gets a "changed" note in its header.

### Verified end-to-end (via direct HTTP calls, Flask dev server on port 5050)

- `GET /` renders (200, ~33KB) with sidebar + tabs + KPI/chart placeholders.
- `POST /set_scenario {"level":4}` and `{"level":2}` both return full `kpis` + `demand_chart` + `supply_chart` + `fuel_chart` + `energy_mix` payloads with plausible, non-zero values.
- `POST /recalc` with a single-lever change correctly isolates the `changed` diff to only the KPIs actually affected by that lever, confirmed against the model's own documented supply-mix-vs-total nuance.
- Re-ran `count_flows.py` after all of the above: **still 78/78, 0 mismatches** — engine confirmed untouched.

### What's next (not built yet, per the Staged decision)

- **Electricity tab** — 4 KPI tiles + 4 charts (Net Electricity Generation, Installed Capacity, Electricity by Sector, Generation Share Fossil vs Non-fossil). Installed Capacity (GW) is a different data type than `read_flows()` provides (Mtoe energy flows) — its source sheet/cells haven't been located yet and will need the same trace-first investigation approach used for Population above.
- Remaining tabs (Electricity, Energy Security, Emissions, Indicators, Costs, Land & Water) stay as disabled "Coming soon" placeholders until scoped.

---

## Session Notes (2026-07-10) — Energy Flows Tab: Sankey Diagram Built

### What was built

The **Energy Flows** tab (previously a disabled "Coming soon" placeholder) is now live, built entirely inside `ui/` — **`xlcompiler/compiler/` untouched**, confirmed by re-running `count_flows.py` after the build: still **78/78 flow matches, 0 mismatches**.

**`ui/outputs.py`** — new pure UI-layer classification and aggregation, no engine involvement:
- `_node_category(name)` buckets every `read_flows()` node name into one of 5 categories by set membership: `source` (existing `PRIMARY_SOURCES`), `demand` (existing `FINAL_DEMAND_SECTORS`), `loss` (new `LOSS_NODES` = `{"Losses", "T&D Losses", "Over Generation/Exports"}`), `tech` (new `TECH_NODES` = the named generation/technology nodes — Solar PV, Solar CSP, Distributed Solar PV, Onshore/Offshore Wind, Off Grid Renewables, Green Hydrogen, Thermal Generation), and `carrier` as the catch-all (Coal/Oil/Gas/Solid/Liquid/Natural Gas/Electricity Grid — the intermediate energy-form nodes). Verified directly by enumerating all distinct `from`/`to` names across the 78 real flow edges (42 unique nodes, 70 non-trivial links at 2047) rather than guessed.
- `_sankey_for_year(edges, year_idx)` builds a `{nodes: [{name, category}], links: [{source, target, value}]}` payload for one year, filtering links below `SANKEY_MIN_VALUE = 0.05` Mtoe to keep the diagram readable (noise-edge cutoff, not a correctness change).
- `compute_sankey(edges)` returns this payload for all 6 chart years (`2022`...`2047`) in one call — cheap, since it's pure aggregation over `edges` that `compute_outputs()` already fetched via one `eng.read_flows()` call; no extra evaluator work.
- `compute_outputs()` now includes `"sankey": compute_sankey(edges)` in its return dict, so both `/set_scenario` and `/recalc` automatically carry full Sankey data for every year on every call — **no new Flask endpoint was needed**, since these two endpoints already recompute and return `compute_outputs()` on every lever move / scenario switch.

**`ui/templates_str.py`** — frontend, deliberately built "as sexy as possible" per explicit user request:
- Restructured the page body into two toggleable `.view` containers (`view-all-energy`, `view-energy-flows`); tab bar now supports two clickable tabs (`All Energy`, `Energy Flows`) via a `CLICKABLE_TABS` dict mapped to `data-view` slugs, the rest remain disabled placeholders.
- D3 v7 + `d3-sankey@0.12` loaded from CDN (`cdn.jsdelivr.net`), rendered inside a dark radial-gradient card (`.sankey-card`, near-black with a subtle dot-grid texture) sitting inside the otherwise light-themed dashboard — a deliberate visual "spotlight" treatment for the flow diagram.
- Each link is rendered with its own per-link SVG `linearGradient` (`id="flow-grad-{i}"`) that blends from the source node's category color to the target node's category color, rather than a single flat highway color — this is the core "sexy" visual choice.
- Node rects get `filter: drop-shadow(0 0 5px currentColor)` for a soft glow keyed to their own category color; labels are drawn as SVG `<text>` with a dark stroke (`paint-order: stroke`) so they stay legible over both light and dark parts of the diagram without a background box.
- **Interaction:** hovering a link or node dims every unrelated link/node to ~8-30% opacity and highlights the hovered element's connections, with a floating tooltip (exact Mtoe value for links, total throughput for nodes) that follows the cursor, positioned relative to `.sankey-card`'s bounding box.
- **Year selector:** a pill-button row (`.year-tabs`, values from `outputs.CHART_YEAR_LABELS`) switches years **entirely client-side** — all 6 years' data arrives in one payload, so switching years re-renders instantly with no server round-trip. Defaults to `2047` (`CHART_YEAR_LABELS[-1]`, wired through as `__DEFAULT_SANKEY_YEAR__` token).
- A `sankey-total` badge shows total primary supply for the selected year, computed client-side as `sum of links whose source node has category "source"`.
- Legend row explains the 5 category colors. `window.resize` triggers a re-render so the SVG stays responsive.
- Sankey re-renders automatically inside the existing `applyResult(data)` function (same one that already updates KPIs and the other 4 charts), so it stays live under every lever drag, scenario switch, and hybrid recalculation — no separate code path.

### Verified end-to-end

- Killed a stale duplicate Flask process still `LISTENING` on port 5050 from an earlier session (same documented duplicate-port-binding class of issue as before) before testing, confirmed only one PID bound afterward.
- `POST /set_scenario {"level":4}` and `POST /recalc {}` both return a `sankey` key with all 6 year labels; 2047 payload directly inspected: 42 nodes, 70 links, plausible values (e.g. Coal Production→Coal = 209.8 Mtoe).
- Re-ran `count_flows.py` after the full build: **still 78/78, 0 mismatches** — engine confirmed untouched.

### What's next

- **Electricity tab** — still not built (see note above; Installed Capacity/GW data source still needs locating).
- Possible follow-up on the Sankey itself (not yet requested/approved): drag-to-reorder nodes, animated flow direction (dashed-line marching ants), or a "diff mode" showing which links changed vs. the scenario baseline (mirroring the KPI/chart `changed` highlighting already built for the All Energy tab).

---

## Session Notes (2026-07-10) — Sankey Diagram: Two Real Bugs Found and Fixed Post-Build

The Sankey tab (built earlier this session, see note above) initially failed for the user with a blank dark card and a "FAILED" status chip. Two genuinely separate bugs were involved — worth recording precisely since the first one looked like the culprit but wasn't.

### Bug 1 — CDN CSP violation from the full `d3@7` bundle (real, but not the cause of the failure)

**Symptom:** Chrome DevTools "Issues" panel showed a CSP violation: *"Content Security Policy of your site blocks the use of 'eval' in JavaScript"*.

**Root cause:** `<script src="https://cdn.jsdelivr.net/npm/d3@7">` loads the *entire* d3 bundle (every submodule — scales, axes, formatting, CSV parsing, etc.), not just the pieces the Sankey code actually uses. One of those bundled submodules, `d3-dsv` (CSV/TSV row parsing — never called anywhere in this codebase), contains a `new Function(...)` call. Confirmed directly: downloaded all three CDN scripts (`d3@7`, `d3-sankey@0.12`, `chart.js`) and grepped for `new Function`/`eval(` — exactly 1 hit, inside `d3.js`, inside the `Wu()` DSV row-object constructor.

**Fix:** replaced the monolithic `d3@7` tag with only the submodules actually needed — `d3-array`, `d3-path`, `d3-shape`, `d3-selection` — plus `d3-sankey`. Verified each of these 5 scripts individually for `new Function`/`eval(` — zero hits across all of them. (`d3-shape` needs `d3-path` as a peer merged into the shared global `window.d3` object via each script's UMD wrapper — both must be present or `d3-shape`'s path-generation breaks silently.)

**This fix was necessary but not sufficient** — the diagram was still blank afterward. See Bug 2.

### Bug 2 — `d3-sankey` `nodeId` mismatch (the actual cause of the "FAILED" status)

**How it was actually found:** rather than keep guessing from screenshots, installed Playwright (`pip install playwright && playwright install chromium`) and drove a real headless Chromium instance against the running Flask server, capturing `console`/`pageerror` events directly. This immediately surfaced the real exception, which had been silently swallowed by the frontend's `try/catch` (visible to the user only as the generic "FAILED" status chip, with the actual error text never reaching the visible `#error` div because it was thrown from inside `applyResult()`, not the `fetch` call itself).

**Exact error:** `Error: missing: 0`, thrown inside `d3-sankey`'s internal link-resolution step.

**Root cause:** `ui/outputs.py`'s `_sankey_for_year()` builds links as `{"source": idx[f], "target": idx[t], "value": v}` — i.e. **numeric array indices** into the `nodes` list. But the frontend's `renderSankey()` had `d3.sankey().nodeId((d) => d.name)`, which tells d3-sankey to resolve `link.source`/`link.target` by matching against each node's `.name` **string**. Looking up the number `0` against a list of name strings never matches → `missing: 0`.

**Fix:** removed the custom `.nodeId((d) => d.name)` call entirely. d3-sankey's default `nodeId` is `(d, i) => i` (the node's array index) — which is exactly what the backend already sends. One-line fix, no backend change needed.

**Verified with the same Playwright harness after the fix:**
- Fresh page load → click "Energy Flows" tab → `document.querySelectorAll('#sankeySvg rect').length` = 42, `path` count = 70, zero console/page errors.
- Full interaction sequence (tab switch → drag a lever slider → wait for debounced `/recalc` → switch tab again → click a different year button) → zero errors, confirming the fix holds under real interaction, not just initial load.
- Screenshot captured via Playwright confirmed the diagram visually renders as intended: teal Primary Source nodes on the left → amber Energy Carrier / blue Generation-Technology nodes in the middle → purple Demand Sector nodes on the right, red Losses/Exports nodes, gradient links blending source→target category colors, "Total primary supply: 1584.1 Mtoe · 2047" badge populated correctly.

### Recurring operational gotcha, hit again during this debugging session

Multiple stale Flask processes ended up simultaneously bound to port 5050 across several restart attempts (the same class of issue documented earlier in this file under "Live Demo Web App" and the 2026-07-03 `ui/` build notes). At one point a curl check of the live page kept showing pre-fix source code even after editing the file and starting a new process, because an older still-running process was silently still holding the port. **Lesson reconfirmed a third time:** after any code change to a running Flask dev server, always verify with `netstat -ano | grep <port> | grep LISTENING` that exactly one PID is bound, and — critically — verify the *served content* directly (`curl | grep` for the specific line just changed) rather than assuming a restart succeeded, since a failed/blocked bind can leave an old process serving stale code with no obvious error on the new terminal.

### Lesson on debugging method going forward

When a frontend issue is reported only as a screenshot of visible symptoms (a blank chart, a status chip, a DevTools panel), the visible symptom is not necessarily the root cause — the CSP "Issues" panel entry looked exactly like the explanation, but the actual failure was a separate, unrelated bug that only surfaced once the CSP issue's script was replaced. **Prefer reproducing the failure directly** (headless browser + real console capture) over reasoning from a screenshot alone whenever the tooling is available — it found the real bug in one shot instead of another round of speculative fixes.

### Known latent issue, flagged but not yet fixed (pending user decision)

The slider `input` event handler debounces per-slider (`scheduleRecalc()`, ~250ms) but does not cancel in-flight `fetch` calls. Rapid multi-slider dragging can queue up several overlapping `/recalc` POSTs; all were observed to return `200` in testing, so this has not caused an actual failure yet, but it is a latent race condition (a stale response could in principle resolve after a newer one and repaint stale data). Proposed fix, not yet approved: wrap the `/recalc` fetch in an `AbortController`, aborting the previous in-flight request whenever a new one is scheduled.

---

## Session Notes (2026-07-10, cont'd) — Sankey Restyled to Match Reference Image (PowerSlides-style Light Theme)

The user supplied a reference image (a PowerSlides-style Sankey template) and asked to restyle our Energy Flows diagram to match its look: light background, flat colored node bars, smooth flowing gradient bands, dark labels — a complete departure from the original dark "glowing" theme built earlier this session.

### Scope decisions (resolved via `AskUserQuestion` before touching code)

The reference diagram is a simple 3-stage, single-color-family diagram with only 2 outputs. Ours has 42 nodes across 5 categories (source/tech/carrier/loss/demand). Two explicit choices were made with the user rather than assumed:

1. **Color scheme:** keep the existing 5-category color coding (teal source / blue tech / amber carrier / red loss / purple demand) rather than collapsing to the reference's single teal-green gradient — with 42 nodes, a single hue would make node types indistinguishable. Chosen: **keep 5-category colors**, just under the new light theme.
2. **Numeric scale axis:** the reference has a 0–5 numbered axis on the left. Chosen: **skip it** — tooltips already show exact Mtoe values on hover, and an axis would be mostly decorative at this node density.

### What changed (`ui/templates_str.py` only — no backend/engine changes)

- `.sankey-card`: replaced the dark radial-gradient background + dot-grid texture + glow shadow with a plain white card (`background:#fff; border:1px solid #e8e9f0`) matching every other card on the dashboard (KPI tiles, chart cards) — visual consistency with the rest of the app, not just the reference image.
- Link `stroke-opacity` raised from `0.45` → `0.55` (default) since the same gradient colors read lighter against white than they did against near-black); `mix-blend-mode: screen` (which only makes visual sense on dark backgrounds, where it lightens overlaps) was removed — never explicitly set in code before either, confirmed no blend-mode override needed on light bg.
- Node `rect` glow (`drop-shadow(0 0 5px currentColor)`, colored per-category) replaced with a neutral soft drop shadow (`drop-shadow(0 1px 3px rgba(20,22,50,0.25))`) — a subtle "lift" consistent with how KPI/chart cards are shadowed elsewhere in the UI, rather than a glow effect that only reads well on dark backgrounds.
- Node/link label text: fill flipped from white (`#f4f6ff`) to dark (`#1b1d29`), and the outline stroke flipped from black (`#05060d`) to white (`#fff`) — same `paint-order: stroke` halo technique as before, just inverted for a light background so labels stay legible whether they land over white space or over a colored flow band.
- Tooltip: flipped from a dark floating card (`rgba(12,14,28,0.96)` bg, white text) to a white floating card (`#fff` bg, `#1b1d29` text, `#e8e9f0` border) matching the dashboard's existing tooltip-less card style; accent text color changed from light blue (`#9fb1ff`) to the dashboard's primary accent (`#4f63d2`).
- Legend dots: removed the `box-shadow: 0 0 6px currentColor` glow (again, a dark-background-only effect).

### Verified

Used the same Playwright headless-browser method established earlier this session (not just visual inspection from a screenshot): loaded the page, clicked into the Energy Flows tab, captured zero `pageerror`/console events, and took a real screenshot confirming the restyle actually rendered — light card, flat category-colored bars, gradient bands still visible and legible against white, dark labels with white halos reading cleanly. Total primary supply badge and all 42 nodes / 70 links at 2047 confirmed present and correctly colored by category.

**Recurring operational note, hit yet again:** after editing `templates_str.py`, the running Flask process (from the prior dark-theme session) was still serving the old cached code — same stale-port-binding class of issue documented multiple times earlier in this file. Resolved the same way each time: `netstat -ano | grep 5050 | grep LISTENING` to find the actual bound PID, `taskkill //F //PID <pid>`, confirm the port is clear, then restart. This is now a well-established, expected step after every template edit in this project, not a one-off surprise — worth doing by habit rather than being caught out by it again.

---

## Session Notes (2026-07-10, cont'd) — All Energy Tab: 4 Charts Replaced to Match Reference IESS Website

The user supplied two reference screenshots from the original IESS website's own dashboard, showing 4 charts they wanted the All Energy tab to mirror: **Energy Demand** (stacked area by sector), **Energy Supply** (stacked area by individual source — Solar/Wind/Hydro/Nuclear/Others/Coal/Oil and petroleum products/Natural gas/Electricity Import), **Import Dependence** (line chart, % import share for Gas/Oil/Coking Coal/Non-coking Coal, with colored endpoint callout boxes like "Oil | 92.61 in 2047"), and **Energy Emissions intensity to GDP** (bar chart, kg CO2-eq/1000 INR).

**Explicit scope correction from the user mid-task, worth recording:** initial instinct was to manually dump raw workbook cells via openpyxl to locate the Import Dependence / Emissions data sources. The user stopped this, clarifying the ask was purely about **visual style matching** — "data is already we have and its recalculating." This reframed the task: the two genuinely new metrics (Import Dependence, Emissions intensity) still needed a real data source located (per the Critical Rule — no invented numbers), but the *investigation* should be lightweight and the emphasis should be on wiring existing engine capability into new chart visuals, not on open-ended workbook spelunking.

### New data sources found (read via `eng.read_cell`, the engine's own public API — not a new extraction path)

The workbook's own `'IESS V3 Results'` sheet — the same sheet already used for the Population/per-capita KPI — turned out to already contain both new metrics as pre-built, lever-reactive formula rows (author's own summary sheet, exactly like `Flows` is for edges):
- **Rows 105–111 "Import Dependence"** (header at 105, year headers at 106): row 107 = Non-coking Coal, 108 = Coking Coal, 109 = Oil, 110 = Gas, 111 = Overall (excluded — reference chart only shows the 4 individual fuels). Values are fractions (0–1), multiplied by 100 for the chart.
- **Row 118 "Energy Emissions intensity to GDP"**, unit `kg CO2-eq/1000 INR` — a single ready-to-plot series, no aggregation needed.
- **Column layout**: same sheet-wide pattern as row 3 (Population) — columns D..K = years [2020, 2022, 2027, 2032, 2037, 2042, 2047, 2030]. So `E..J` = the 6 chart years (2022→2047), matching `CHART_YEAR_LABELS` exactly.

Both rows are the workbook author's own formulas — confirmed live-reactive by construction (same evaluator path as everything else the engine computes; no special-casing needed, same as the existing `compute_population_millions()`).

### What changed (`ui/outputs.py` + `ui/templates_str.py` — no engine changes)

- `SUPPLY_SOURCE_GROUPS` regrouped from 6 buckets (Coal/Oil & Products/Natural Gas/Renewables/Biomass/Nuclear & Others) to 9 individual sources matching the reference's own legend order exactly: Solar, Wind, Hydro (Hydro+Small Hydro combined), Nuclear, Others (Municipal Waste + Agricultural Waste/Energy Crops), Coal, Oil and petroleum products, Natural gas, Electricity Import.
- New `IMPORT_DEPENDENCE_ROWS` (name→row mapping) and `EMISSIONS_INTENSITY_ROW` constants, plus `compute_import_dependence_chart(eng)` and `compute_emissions_intensity_chart(eng)` — both read directly via `eng.read_cell("IESS V3 Results", f"{col}{row}")`, same pattern as the existing Population read.
- Removed `compute_fuel_consumption_chart()` / `FUEL_CONSUMPTION_GROUPS` and `compute_energy_mix_donut()` — the "Fuel-wise Consumption" line chart and "2047 Energy Mix" donut were placeholders from the original Milestone 1 build; the reference image made clear the tab should show Import Dependence and Emissions Intensity instead. `compute_outputs()`'s return dict now has `import_dependence_chart` and `emissions_intensity_chart` in place of `fuel_chart`/`energy_mix`.
- **Frontend (`templates_str.py`):** built a small reusable `endpointLabelPlugin` (a genuine custom Chart.js plugin, `afterDatasetsDraw` hook) that draws a colored rounded callout box — `"{series name} | {last value}"`, filled in the series' own line color, white text — at the last point of each line. This directly reproduces the reference image's endpoint-label style (e.g. "Oil | 92.61 in 2047") without pulling in an extra CDN dependency. Added `layout.padding.right: 100` to the Import Dependence chart so the callout boxes have room instead of clipping off the canvas edge. Emissions Intensity is a plain Chart.js bar chart (`type: "bar"`), single blue series, matching the reference's simple bar style. Extended the shared `COLORS` palette from 8 to 9 entries (`+"#22d3a8"`) since the regrouped supply chart now has 9 series and would otherwise wrap and collide on the 9th color.

### Verified

- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.
- Used the same Playwright headless method established earlier this session to check the *actual* rendered Chart.js state (`page.evaluate(() => charts['emissionsChart'].data)`), not just a screenshot, and cross-checked it byte-for-byte against a direct `curl` of `/set_scenario`'s JSON response — both matched exactly, confirming the data pipeline (engine → `outputs.py` → JSON → Chart.js) is correct end-to-end.
- **False alarm caught and resolved before reporting to the user:** a first screenshot (taken ~1.5s after page load) appeared to show a broken chart — a large unexplained dip/near-zero gap in both the new Supply chart and Import Dependence chart. Investigated by re-querying the live Chart.js instance's `.data` (correct, smooth values) and re-screenshotting after a longer wait (3s) — the second screenshot rendered perfectly smoothly. Root cause: Chart.js's default draw animation (~1s) was still mid-transition when the first screenshot was captured, on a heavier page load (51 lever sliders + 4 charts + Sankey prep). **Lesson:** when verifying Chart.js (or any animated-canvas) output via automated screenshot, allow enough time post-load for the draw animation to finish, or query the chart instance's underlying `.data`/`.scales` directly instead of trusting a single early screenshot — the same "reproduce, don't guess from one artifact" principle already learned from the Sankey `nodeId` bug earlier this session, this time turned inward on my own verification method.

---

## Session Notes (2026-07-10, cont'd) — Electricity Tab Built: 2 Charts Matching Reference

The user supplied two more reference screenshots from the original IESS website, this time from its **Electricity** tab: "Electricity Demand (Including Captive)" (stacked area by sector, TWh, with a black "Total" line-with-dots overlay) and "Electricity Supply (Utility)" (stacked area by generation source, TWh, same Total overlay).

### Scope decision (resolved via `AskUserQuestion` before building)

The reference Supply chart's legend has 9 categories (Gas, Coal, CCS, Nuclear, Hydro, Solar, Wind, Bioenergy, Electricity trade). Investigation showed the workbook's `'IESS V3 Results'` sheet — the same sheet already used for Population, Import Dependence, and Emissions Intensity — only has electricity generation pre-aggregated into **4** buckets (Fossil-fuel based / Hydro & Nuclear / RE-based / Electricity Imports, rows 87-91): Coal, Gas, and CCS are combined into one "Thermal Generation" node everywhere in the model, including `read_flows()`'s own Sankey data (already documented earlier in this file under "Coal Power Stations lever visibly does nothing"). Getting the reference's full 9-way split would require tracing and summing generation rows across 6+ separate per-technology sheets (`II`, `III`, `IV.a`-`IV.e`) — real additional investigation, not a quick lookup.

**Chosen: use the 4 real categories already available**, rather than invest in the deeper multi-sheet trace. Fast, no new investigation, and — per the Critical Rule — 100% real already-computed data rather than an approximation assembled from scattered technology sheets.

### Data sources used (all via `eng.read_cell`, no engine changes)

Both charts read from `'IESS V3 Results'`, same D..K = [2020,2022,2027,2032,2037,2042,2047,2030] column layout as Import Dependence/Emissions:
- **Demand** (rows 52-63, section header "Total Electricity Consumption (Inc. Captive electricity)" — near-exact match to the reference chart's own title): row 55 Industry, 56 Residential, 57 Commercial, 58 Agriculture, 59 "Telecom + Cooking + Transport" (combined in the source data — the sheet doesn't split these three further), 60 Miscellaneous, 61 Hydrogen, 62 Refineries, 63 Total. Grouped in `outputs.py` as: Industry, Buildings (=Residential+Commercial), Agriculture, "Telecom, Cooking & Transport" (kept combined, honestly labeled rather than inventing a false split), Miscellaneous (Hydrogen + Refineries folded in, since the sheet doesn't break them out separately either).
- **Supply** (rows 85-91, section header "Net Electricity Generation (Gross generation - auxiliary consumption)"): row 87 Fossil-fuel based, 88 Hydro & Nuclear, 89 RE-based, 90 Electricity Imports, 91 Total — used as-is, no further grouping needed.
- Both `total` series come from the workbook's own Total row (63 / 91) directly, not summed client-side or server-side from the group series — guarantees the black overlay line always matches the workbook's own authoritative total even if float rounding differs slightly from the sum of displayed groups.

### What changed

- `ui/outputs.py`: new `ELECTRICITY_DEMAND_GROUPS`, `ELECTRICITY_SUPPLY_GROUPS` constants (name → list of source rows, supporting multi-row sums like Buildings), `compute_electricity_demand_chart(eng)` / `compute_electricity_supply_chart(eng)`, added to `compute_outputs()`'s return dict as `electricity_demand_chart` / `electricity_supply_chart`.
- `ui/templates_str.py`:
  - Added "Electricity" as a third clickable tab (`view-electricity`), alongside "All Energy" and "Energy Flows" — the rest remain disabled "Coming soon" placeholders.
  - **Noticed and fixed a pre-existing gap while building this:** the `demand_chart`/`supply_chart` payloads on the All Energy tab already carried a `total` field (computed since the very first Milestone 1 build), but the frontend never actually rendered it — no black Total line existed anywhere, unlike both reference images which prominently feature one. Extended `stackedAreaDatasets()` to push an unstacked black line-with-dots dataset (`order: 0`, drawn on top of the stacked areas) whenever `chartData.total` is present, and generalized `renderStackedChart()` to take an `opts` object (`unit`, `changedCardId`) instead of a hardcoded "Mtoe" label and a canvasId-sniffing card-highlight check. This one change means **all 4 stacked-area charts now show the Total overlay** — the 2 pre-existing All Energy charts (Demand/Supply, retrofitted) and the 2 new Electricity charts — matching the reference styling consistently across the whole dashboard, not just the newly-requested tab.

### Verified

- Direct `curl` of `/set_scenario` confirmed both new chart payloads return real, plausible, lever-reactive numbers (e.g. Electricity Demand Total: 1,253.97 → 5,585.1 TWh from 2022→2047 under L4; Supply Total 1,321.85 → 6,862.75 TWh, RE-based share visibly dominating by 2047 — consistent with an aggressive renewable scenario).
- Playwright: loaded the page, clicked into the Electricity tab, waited for the Chart.js draw animation to fully settle (3.5s, per the animation-timing lesson from the previous chart work this session) before screenshotting — zero console/page errors, both charts rendered correctly with the black Total line, correct TWh units, and titles matching the reference ("Electricity Demand (Including Captive)" / "Electricity Supply (Utility)").
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### What's still not built

- Electricity tab currently has only these 2 charts (matching what the user asked for this round). The earlier-documented 4-KPI-tile / Installed-Capacity-chart scope for this tab (from the very first "What's next" note) is still open if wanted later — Installed Capacity (GW) data source (rows 72-79 of the same `'IESS V3 Results'` sheet, found incidentally during this session's investigation) is now known, if that KPI is requested next.
- Remaining tabs (Energy Security, Emissions, Indicators, Costs, Land & Water) still disabled "Coming soon" placeholders.

---

## Session Notes (2026-07-10, cont'd) — Electricity Supply: Full 9-Category Trace + Changed-Highlighting + Delta Charts

Follow-up to the Electricity tab build above. The user asked for four things together: (1) extend the existing "changed since baseline" highlighting (dashed amber border, already built for the All Energy tab) to the two new Electricity charts, (2) add a way to visualize lever-driven *changes* rather than only static totals, (3) get design ideas for this, and (4) do the deferred "8-category trace" — i.e. actually go find Gas/Coal/CCS/Nuclear/Hydro/Solar/Wind/Bioenergy generation individually (the finer breakdown skipped earlier in favor of the coarse 4-bucket version, per that session's `AskUserQuestion` answer).

### The 8-category trace (now done — real data, not approximated)

Each of the 8 technologies has its **own dedicated module sheet** in the workbook, identified by directly reading each candidate sheet's own title cells (not guessed from sheet-name convention):

| Technology | Sheet | Sheet's own title (row 2, col B) |
|---|---|---|
| Gas | `I.a` | "Gas Power Stations" |
| Coal | `I.b` | "Coal power stations" |
| CCS | `I.c` | "Carbon Capture Storage (CCS)" |
| Nuclear | `II` | "Nuclear" |
| Hydro | `III` + `IV.d` | "Hydro Power Generation" + "Small Hydro" (combined) |
| Solar | `IV.a` + `IV.b` + `IV.e` | "Solar PV" + "Solar CSP" + "Distributed Solar PV" (combined) |
| Wind | `IV.c.1` + `IV.c.2` | "Onshore Wind" + "Offshore Wind" (combined) |
| Bioenergy | `V.a` | "Biomass Based Electricity" (V.b/V.c are liquid biofuels, not electricity — excluded) |

Within each sheet, the generation total lives in a consistently-templated row: **"Annual Generation from Existing Capacity (in GWh)"** — verified directly (not assumed) to equal the sum of the adjacent "...from Old Capacity" + "...from New Capacity" rows on every sheet checked, i.e. it's the technology's true total annual generation, not a partial figure. **Coal (`I.b`) is the one template exception**: its equivalent row is labelled "Annual Generation from Total Capacity (in GWh)" and sits in column B instead of C — caught by checking why the exact-string search that worked for every other sheet returned `None` for Coal, rather than silently skipping it. All 8 sheets share the same year-header row (`2020/2022/2027/2032/2037/2042/2047` in columns D-J) as every other data source used this session — confirmed per-sheet, not assumed from the pattern holding on the first two checked.

"Electricity trade" (the 9th category) isn't a technology sheet — reused the existing `'IESS V3 Results'` row 90 net-imports figure from the coarse breakdown.

**`ui/outputs.py`**: new `GENERATION_ROWS` dict (technology → list of `(sheet, row)` pairs, supporting the 3 combined technologies), `GENERATION_ORDER`, `GWH_TO_TWH = 1000.0` conversion constant. `compute_electricity_supply_chart()` rewritten to read each technology's own sheet directly via `eng.read_cell(sheet, f"{col}{row}")`, sum multi-sheet technologies, convert GWh→TWh, and add the `Electricity trade` row — replacing the old 4-bucket version entirely (no parallel coarse/fine toggle; the fine version is strictly better now that it's real data, so there was no reason to keep both).

### Changed-highlighting extended to all 4 stacked-area charts (not just Electricity)

Rather than special-case the 2 Electricity charts, generalized the existing mechanism: added a `DIFFABLE_CHARTS = ["demand_chart", "supply_chart", "electricity_demand_chart", "electricity_supply_chart"]` list in `outputs.py`, and rewrote `diff_outputs()` to loop over it instead of hardcoding just the first two. Zero behavior change for the pre-existing All Energy charts; the 2 Electricity charts get the same dashed-amber-border-on-changed-series + `changed` card-header badge treatment for free. Frontend: added `id="card-elec-demand"` / `id="card-elec-supply"` to the two Electricity cards (with the same `<span class="changed-note">changed</span>` markup already used elsewhere) and passed `data.changed.electricity_demand_chart`/`electricity_supply_chart` into the existing `renderStackedChart(..., changedCardId: ...)` call — no new CSS or highlighting logic needed, purely reuse.

### New: "Δ vs. scenario baseline" delta bar charts

New `compute_chart_deltas(current, baseline)` in `outputs.py`: for each `DIFFABLE_CHARTS` entry, returns `{year, labels, current, baseline, has_baseline}` — the final (2047) value of every series, current vs. baseline, ready to plot as a grouped bar chart. `has_baseline` distinguishes "no scenario picked / no lever moved yet" (baseline is `None` server-side) from a genuine zero-baseline value, so the frontend can show an honest "nothing to compare yet" state instead of implying a fake baseline of 0. Wired into `app.py`: both `/set_scenario` and `/recalc` now also return a top-level `deltas` key (`compute_chart_deltas(display_data, None)` for `/set_scenario`, `compute_chart_deltas(data, baseline_snapshot)` for `/recalc` — same baseline-handling pattern already established for `diff_outputs()`).

**Frontend**: new `renderDeltaChart()` — a grouped Chart.js bar chart, "Baseline" (light gray) vs. "Current" (blue) per category. Added under each Electricity card as its own chart card (`electricityDemandDeltaChart` / `electricitySupplyDeltaChart`), since a delta view answers a different question than the stacked area above it (composition over time vs. "how much did this specific lever move this specific category") and deserves its own space rather than being crammed into the same canvas.

### Why this is more informative than the stacked area alone (the "different chart types" ask)

Demonstrated directly during verification: moving the Coal Power Stations lever (a supply-mix lever) produced **no visible change at all** in either chart or its delta bars — investigated and confirmed via direct engine query (not assumed) that Coal generation is already fully phased down to 0 by 2047 under the L4 scenario baseline used for testing, so there's no headroom left for the lever to shift. This is exactly the kind of thing a stacked area chart hides (a flat-looking chart could mean "nothing changed" or "already saturated") and a delta chart makes checkable at a glance. Moving a lever with real remaining effect (Industry Energy Intensity) correctly lit up `changed: True` on both cards and showed a clear baseline (~2,500 TWh) vs. current (~3,700 TWh) jump in the Industry delta bar — confirming the whole pipeline (trace → diff → delta → render) works correctly end-to-end, not just that the code runs without error.

### Verified

- Playwright: headless-drove real lever drags via `el.dispatchEvent(new Event('input', {bubbles:true}))` (not `page.fill()`, which doesn't reliably fire `input` listeners on `<input type=range>`), waited for the status chip to actually flip to a *new* `"live"` state (compared against its pre-trigger text, not just a prefix match — an earlier naive `wait_for_function` false-positived by matching the *already-live* state from page load, not the post-recalc one) rather than a fixed sleep.
- **Recalc latency increased noticeably** with this change — round-trip observed at ~3-6s (vs. sub-second before), because every `/recalc` now reads ~48 additional cells across 8 separate technology sheets from a cleared cache, each potentially triggering its own recursive formula tree walk. Not addressed this session (no lag-reduction work requested), but worth flagging: if the sidebar starts feeling sluggish under rapid slider dragging, this is the likely cause, and a per-technology-sheet result cache (keyed off the override set, invalidated the same way the existing cache already is) would be the natural fix.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

---

## Session Notes (2026-07-10, cont'd) — Chart Polish: Y-Axis Negative Padding + Combined Hover Tooltips

Two small but visible UX issues flagged from a screenshot of the Electricity Supply chart: (1) the y-axis showed an ugly `-1000`/`-500` band below zero even though the actual data barely dips negative, and (2) hovering only showed one series' value at a time instead of every category at that year.

### Fix 1 — y-axis negative padding

**Root cause:** `Electricity trade` (net imports) is genuinely slightly negative every year (-1.6 to -5.4 TWh, tiny compared to the ~7,000 TWh scale). Chart.js's default axis-range algorithm doesn't tightly bound to the data's actual min — it rounds outward to "nice" tick steps (e.g. 500), so a data min of -5 was enough to make it generate a full extra `-500`/`-1000` gridline band, visually implying the chart goes far more negative than it actually does.

**Fix:** added `min: 0` to the y-scale in `renderStackedChart()` (`ui/templates_str.py`). The real negative sliver still renders below the y=0 line (not clipped from view — it's small enough not to matter visually), but the axis itself no longer pads out to `-1000`. Applies to all 4 stacked-area charts (both All Energy and both Electricity), since they share the one render function.

**Follow-up, same session:** the same padding artifact turned up in the "Δ vs. scenario baseline" delta bar charts too (a `-500` band even though the only near-zero value was `Electricity trade`, and the rest of the bars were all solidly positive) — same root cause, same fix: added `min: 0` to `renderDeltaChart()`'s y-scale as well. Since both delta charts (Demand and Supply) share that one function, one edit fixed both.

### Fix 2 — combined hover tooltips

**Root cause:** Chart.js's default tooltip interaction mode only shows the single dataset whose line/point is directly under the cursor, requiring precise hovering over one specific series to see its value — not useful for a 9-series stacked chart where the point is to compare categories at a glance.

**Fix:** added a shared `INDEX_INTERACTION = { mode: "index", intersect: false }` constant, applied as both `interaction` and `plugins.tooltip` on every chart config (`renderStackedChart`, `renderImportDependenceChart`, `renderEmissionsBarChart`, `renderDeltaChart`). Hovering anywhere along a given x-axis position (year) now pops one combined tooltip listing every series' value at that point — confirmed via screenshot: hovering 2037 on the Electricity Supply chart shows Total, Bioenergy, CCS, Coal, Electricity trade, Gas, Hydro, Nuclear, Solar, and Wind all in one box.

### Verified

- Playwright screenshot confirmed both fixes visually: clean 0-based y-axis, full combined tooltip on hover.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched.

---

## Session Notes (2026-07-10, cont'd) — Energy Security Tab Built

Third new tab this session, following the same reference-image-matching pattern as the Electricity tab. User supplied a screenshot from the original IESS website's Energy Security tab: **Import Dependence** (the same line chart already built for the All Energy tab) and **Energy Imports** (a new stacked-area chart, Mtoe, by fuel — Non-coking coal, Coking Coal, Oil, Gas — with the same black Total overlay line style used everywhere else this session).

### New data source found

Import Dependence is simply reused as-is (same `compute_import_dependence_chart()` data, rendered into a second canvas — the original IESS site shows this same chart on both its All Energy and Energy Security tabs, so duplicating rather than moving it matches the reference).

Energy Imports needed a genuinely new source, since Import Dependence is a *percentage* and this chart needs *absolute Mtoe* import volumes per fuel, split into Coking vs. Non-coking coal. Found in **`'Intermediate output'`** — a different sheet from every other data source used this session, and structured differently: it's the workbook's full historical+projected energy-balance table, one column per *calendar year* starting at 1970 (not the D-K sparse-year layout everything else uses), unit row 4 confirms `Mtoe / year`. Year columns for the 6 chart years were found by scanning row 4 for the literal year values rather than assumed from the D-K pattern holding elsewhere: `BC=2022, BD=2027, BE=2032, BF=2037, BG=2042, BH=2047`.

Row 44 "Coking Coal Imports" + row 45 "Non-coking Coal Imports" were verified (not assumed) to sum exactly to row 43 "Coal oversupply (imports)" at every year checked (e.g. 34.98 + 96.19 = 131.18, matching row 43's 131.18 to 2 d.p.) — confirming these are a real, unit-consistent split of the aggregate coal import figure rather than a guess. Oil (row 49) and Gas (row 51) import rows needed no splitting.

**Noted for future reference:** the Energy Imports chart's absolute Mtoe values don't visually resemble the reference screenshot's proportions (reference shows Non-coking coal as the dominant band; our render shows Oil and Gas larger, Non-coking coal shrinking toward ~0 by 2047). This is expected, not a bug — the reference screenshot was captured under the original site's own default scenario, while this session's engine has been sitting in the aggressive-renewables "Determined Effort L4" preset (used for testing all session), which phases down coal imports much faster. Same lever-propagation behavior already validated extensively earlier in this file — different scenario, different absolute trajectory, by design.

### What changed

- `ui/outputs.py`: new `ENERGY_IMPORTS_SHEET`, `ENERGY_IMPORTS_YEAR_COLS`, `ENERGY_IMPORTS_ROWS` constants; `compute_energy_imports_chart(eng)` (total computed by summing the 4 series client-side, same pattern as the All Energy Demand/Supply charts' totals — no single "Total Energy Imports" row exists in the source sheet to read instead). Added to `compute_outputs()`'s return dict as `energy_imports_chart`.
- `ui/templates_str.py`: added "Energy Security" as a fourth clickable tab (`view-energy-security`), between Electricity and Energy Flows. Two chart cards: `esImportDependenceChart` (calls the existing `renderImportDependenceChart()` a second time, pointed at a second canvas — zero new rendering code needed) and `energyImportsChart` (calls the existing `renderStackedChart()`, unit "Mtoe", no changed-highlighting or delta chart wired up for this tab — kept scope to what was shown in the reference image, unlike the Electricity tab where those were separately requested).

### Verified

- Direct `curl` of `/set_scenario` confirmed real, plausible, lever-reactive values (e.g. 2047 Non-coking coal imports drop to 0.0 under the L4 scenario, consistent with the near-zero Non-coking Coal import-dependence % already seen earlier this session on the same scenario).
- Playwright: loaded the page, clicked into the Energy Security tab, waited for the Chart.js draw animation to settle (3s), zero console/page errors, both charts rendered correctly — clean 0-based axis, Total overlay line, and the endpoint-callout-box styling correctly applied to the second Import Dependence chart instance too.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### What's still not built (superseded — Emissions tab built next, see below)

- Remaining tabs (Indicators, Costs, Land & Water) still disabled "Coming soon" placeholders.

---

## Session Notes (2026-07-10, cont'd) — Emissions Tab Built

Fourth new tab this session. User supplied a reference screenshot from the original IESS site's Emissions tab: **Energy-related GHG Emissions** (stacked area by sector, Million tonne CO2e, with the same black Total overlay line style used everywhere else this session) and **Per Capita GHG Emissions (Energy-related)** (bar chart, tonne CO2e per person).

### Data sources found

**Per Capita** was trivial — `'IESS V3 Results'` row 117 "Per Capita energy GHG Emissions" (unit `tCO2-eq.`) was already located earlier this session (during the Emissions Intensity investigation) but never used until now.

**Sector breakdown** needed new investigation: found in `'Intermediate output'` (the same sheet as Energy Imports, same `BC..BH` = 2022..2047 year columns), rows 174-192, an "Emissions by sector" block numbered with roman-numeral codes (I-XVII) in column C. Verified directly rather than assumed:
- Row 192 "Total Emissions in MT CO2" was confirmed to equal the sum of every row I-XVII at every year checked (e.g. 2022: 2745.24 both ways), **and** cross-validated against `'IESS V3 Results'` row 116 "Total energy GHG Emissions" — matched to the last decimal, two independent parts of the workbook agreeing.
- Grouped honestly by what the sheet actually contains rather than force-fitting to any assumed external legend: **Electricity** sums all 7 generation-technology rows (I-VII: Hydrocarbon fuel power, Nuclear, Hydro, National renewable, Bioenergy, Waste, Electricity storage) — the 6 zero-carbon ones are 0 in every scenario tested but summed anyway for correctness under any future scenario, not hardcoded to just row I. **Industry, Transport, Cooking, Agriculture, Fuel Production ("Fossil fuel production" in the sheet), Telecom** map 1:1 to their own named rows (XI-XVI). **"Other"** honestly bundles three rows with no clean name of their own — IX "Stress" and X "Buildings" (both zero-valued in every scenario tested, kept rather than dropped, for completeness) and XVII "Transfer" (nonzero, meaning not confirmed from the sheet's own labels — not renamed to "Refineries" or anything else just because it was the next line in a hypothetical legend; this project's rule is to never invent labels the source data doesn't confirm).

### What changed

- `ui/outputs.py`: new `EMISSIONS_SECTOR_GROUPS`, `EMISSIONS_TOTAL_ROW`, `PER_CAPITA_EMISSIONS_ROW` constants; `compute_emissions_by_sector_chart(eng)` (total read from the sheet's own row 192, same pattern as the other `'IESS V3 Results'`/`'Intermediate output'`-sourced charts that have an authoritative total row to read rather than sum) and `compute_per_capita_emissions_chart(eng)`. Both added to `compute_outputs()`.
- `ui/templates_str.py`: added "Emissions" as a fifth clickable tab (`view-emissions`), between Energy Security and Energy Flows. **Generalized `renderEmissionsBarChart()` into `renderBarChart(canvasId, chartData, opts)`** (taking `unit`/`color` options instead of a hardcoded "kg CO2e / 1000 INR" label) so the same function now serves both the pre-existing Emissions Intensity chart (All Energy tab) and the new Per Capita Emissions chart — no duplicated bar-chart code. `emissionsBySectorChart` reuses the existing `renderStackedChart()` with `unit: "Million tonne CO2e"`.

### Verified

- Direct `curl` of `/set_scenario`: summed the 8 returned series client-side and confirmed it matches the chart's own `total` field to within 0.01 (2491.03 vs. 2491.04) — the grouping is complete and correct, not just non-crashing.
- Playwright: zero console/page errors, both charts rendered correctly. The rendered shape is a real, informative result: Electricity's emissions collapse sharply after 2032 (consistent with the aggressive renewable buildout already seen throughout this session under the L4 scenario used for testing), Industry becomes the dominant emissions source by 2047, and per-capita emissions trend downward overall despite economic growth.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### What's still not built (superseded — Indicators tab built next, see below)

- Remaining tabs (Costs, Land & Water) still disabled "Coming soon" placeholders.

---

## Session Notes (2026-07-10, cont'd) — Indicators Tab Built (Sub-Tab 1 of 3)

Fifth new tab this session. Reference image showed **Indicators** has its own second-level sub-tab nav with 3 items — "Energy Emissions Intensity of GDP", "Per Capita Indicators", "Electricity Indicators" — but the screenshot only showed the first sub-tab's content (2 bar charts). Rather than guess what the other two sub-tabs contain, asked the user directly via `AskUserQuestion`; they chose to build sub-tab 1 fully now and share screenshots for the other two later (confirmed immediately after with a second screenshot, which matched sub-tab 1 exactly — no new info, just confirmation).

### Data sources

- **Energy Emissions Intensity of GDP** — reused the existing `emissions_intensity_chart` (row 118, `'IESS V3 Results'`), same data already shown on the All Energy tab, rendered again here per the reference (same duplication pattern already established for Import Dependence appearing on both All Energy and Energy Security).
- **Energy intensity of GDP** (MJ/INR) — new: `'IESS V3 Results'` row 49 "Energy Intensity", same sheet/column layout (E-J) as every other `'IESS V3 Results'`-sourced chart this session. Values (0.23 → 0.075 MJ/INR, 2022→2047) plausible and matched the user's own confirming screenshot exactly.

### What changed

- `ui/outputs.py`: new `ENERGY_INTENSITY_ROW = 49` constant, `compute_energy_intensity_chart(eng)`, added to `compute_outputs()` as `energy_intensity_chart`.
- `ui/templates_str.py`:
  - Added "Indicators" as a sixth clickable tab (`view-indicators`).
  - **New second-level sub-tab pattern** (not needed by any earlier tab this session): `.subtabs`/`.subtab`/`.subview` CSS (underline-style active state, matching the reference's own sub-nav look) plus a generic sub-tab click handler (`st.closest(".subtabs")` / `st.closest(".view")` scoping so it only affects sub-tabs within the same parent tab, ready to reuse if any other tab ever needs sub-navigation). Two of the three sub-tab buttons are rendered `disabled` with a "Coming soon" title, same convention already used for the top-level tab bar.
  - Both charts reuse the existing `renderBarChart()` (the function generalized during the Emissions tab work) — no new chart-rendering code needed, just two more call sites.

### Verified

- Direct `curl` confirmed real, plausible `energy_intensity_chart` values.
- Playwright: zero console/page errors; screenshot confirmed the sub-tab nav renders with the correct active/disabled states and both charts populate correctly.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### What's still not built (superseded — both remaining sub-tabs built next, see below)

- Remaining top-level tabs (Costs, Land & Water) still disabled "Coming soon" placeholders.

---

## Session Notes (2026-07-10, cont'd) — Indicators Tab: Sub-Tabs 2 & 3 Built (Per Capita + Electricity Indicators)

User supplied the two remaining reference screenshots (Per Capita Indicators: Per Capita GHG Emissions + Per Capita Primary Energy Supply; Electricity Indicators: Installed Capacity + Demand Electrification), closing out the Indicators tab.

### Data sources — two categories: reused, and newly derived

**Reused directly, no new work:**
- Per Capita GHG Emissions — same `per_capita_emissions_chart` (row 117) already built for the Emissions tab, rendered a third time here.

**New, but found as real pre-computed rows:**
- **Installed Capacity** — same 12 technology sheets as `GENERATION_ROWS` (Gas/Coal/CCS/Nuclear/Hydro/Solar/Wind/Bioenergy), this time reading each sheet's own "Cumulative Installed Capacity (in GW)" row instead of the generation row — found via the identical per-sheet search pattern, present in all 12 (this reference chart wants **Large Hydro and Small Hydro reported separately**, and **Solar PV/Solar CSP/Distributed Solar PV reported separately** too, rather than the combined "Hydro"/"Solar" buckets used on the Electricity Supply chart — 12 distinct series here instead of that chart's combined groupings, since the reference legend asked for the finer split and the sheets support it directly).
- **"Waste to Electricity"** (13th category) doesn't have a "Cumulative Installed Capacity" row like the other 12 — confirmed by directly searching sheet `VI` for "cumulative" (zero matches). Found instead: a differently-structured lever-trajectory table (header "Waste to electricity capacity deployed (GW)" at row 49, a "Chosen" row at row 56 selecting among 4 trajectory options — the same lever-selection pattern used throughout the workbook for other lever-driven values). That table's year columns are `I-N` (2022-2047), a **third distinct column layout** found this session (after the `D-J` pattern used almost everywhere, and the `BC-BH` calendar-year pattern used by `'Intermediate output'`) — confirmed directly per-sheet, not assumed.

**Two genuinely new derived metrics** (no single source cell exists for either — confirmed by searching the entire workbook for "electrification", "toe/person", and "per capita" + "primary" text, zero matches):
- **Per Capita Primary Energy Supply** (toe/person) — derived as `'IESS V3 Results'` row 48 (Total Primary Supply, Mtoe) ÷ row 3 (Population, millions) at each year. Dimensionally exact by unit cancellation (10⁶ toe ÷ 10⁶ people = toe/person), no conversion factor needed — same category of derivation as the pre-existing `per_capita_demand` KPI (which does need a conversion factor, `MTOE_TO_MJ`, since its target unit is MJ not toe).
- **Demand Electrification** (%) — derived from `read_flows()` edges: the "Electricity Grid" node's flow into `FINAL_DEMAND_SECTORS` as a share of total flow into `FINAL_DEMAND_SECTORS` from every carrier. Same computational pattern as the (now-removed) fuel-consumption chart from early this session — the underlying logic wasn't wasted, just repurposed for a cleaner single metric instead of a 4-series chart.

### What changed

- `ui/outputs.py`: new `PRIMARY_SUPPLY_ROW`, `POPULATION_ROW`, `CAPACITY_ROWS`, `CAPACITY_ORDER`, `WASTE_CAPACITY_SHEET`/`ROW`/`YEAR_COLS` constants; `compute_per_capita_supply_chart(eng)`, `compute_capacity_chart(eng)`, `compute_demand_electrification_chart(edges)`. All three added to `compute_outputs()`.
- `ui/templates_str.py`: enabled the two previously-disabled sub-tabs (`per-capita`, `electricity-indicators`), each with its own `subview` and 2 chart cards. Extended the shared `COLORS` palette from 9 to 13 entries (`+"#f2a93b", "#5c6bc0", "#26a69a", "#ec407a"`) since the Installed Capacity chart needs 13 distinct series. Both new bar charts reuse `renderBarChart()`; Installed Capacity reuses `renderStackedChart()` — no new chart-rendering code needed for any of the 4 new charts.
- **One label correction caught before shipping:** the reference screenshot's own y-axis for Per Capita GHG Emissions reads "kg CO2e/person", but the actual values shown (2 → 6 range) and the source cell's own declared unit (`'IESS V3 Results'` row 117, column C = `tCO2-eq.`) both indicate **tonnes**, not kilograms — a 1000x unit label error on the original reference site, not a hint to follow. Labeled our card as "tonne CO2e/person" (matching the workbook's own authoritative unit) rather than copying the reference's apparent typo.

### Verified

- Direct `curl`: `per_capita_supply_chart` (0.58 → 0.90 toe/person, 2022→2047) and `demand_electrification_chart` (15.9% → 36.3%) both plausible and smoothly trending. `capacity_chart` returns all 13 categories with sensible magnitudes (Solar PV and Onshore Wind dominating growth by 2047, consistent with the L4 aggressive-renewables scenario used for testing all session; Coal Power Stations capacity collapsing toward 2047, consistent with everything else observed this session under this scenario).
- Playwright: zero console/page errors on both sub-tabs; screenshots confirmed correct rendering, including the 13-color legend on the Installed Capacity chart with no color collisions.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### Indicators tab now fully complete

All 3 sub-tabs built: Energy Emissions Intensity of GDP, Per Capita Indicators, Electricity Indicators — 6 charts total, all real data.

### What's still not built (superseded — Costs tab built next, see below)

- Remaining top-level tab (Land & Water) still disabled "Coming soon" placeholder.

---

## Session Notes (2026-07-10, cont'd) — Costs Tab Built (2 Sub-Tabs, 4 Charts)

Sixth new tab this session, following the same sub-tab pattern established for Indicators. Reference screenshots: **Annual Import & Energy Costs** sub-tab (Annual Import Costs Nominal — Non-coking Coal/Coking coal/Crude oil/Gas; Annual Production Costs Nominal — Coal/Oil/Gas), and **Power Sector Cost** sub-tab (Power Sector capex — a *bar* chart bucketed into five-year periods rather than annual, 14 technologies; Annual Operating Costs — annual stacked area, same 14 technologies).

### Data sources — two dedicated cost sheets found

- **`'Cost - Import + Production'`** — a purpose-built cost sheet with 3 price-sensitivity scenarios (HIGH/POINT/LOW) for both import costs (rows 15-37) and domestic production costs (rows 74-93). Used **POINT** (the central estimate) throughout — the standard convention a dashboard would default to, not picked to match the reference screenshot's exact numbers (which, per this session's now-repeated finding, was captured under a different lever scenario than our L4 test state anyway). Import costs: Non-coking coal/Coking coal/Crude oil/Gas at rows 25-28, Total row 29. Production costs: Coal/Oil/Gas at rows 83-85, Total row 86. Standard `D-J` year-column layout.
- **`'Cost - Power Sector and H2'`** — same pattern, same POINT-scenario convention, for the 14-technology power-sector cost breakdown (the 12 generation-tech sheets from `GENERATION_ROWS`/`CAPACITY_ROWS`, plus "Standalone PV for Hydrogen" and "Standalone Wind for Hydrogen" — no separate "Waste to Electricity" line in this particular cost table, confirmed by its absence from the sheet's own technology list rather than dropped by us). Two sections:
  - **"2. Capital Costs (Five-yearly)"** (rows 71-85, POINT) — genuinely bucketed by 5-year period, not annual. Confirmed directly: its own header row (52) reads literal strings `'2020-2022'`, `'2022-27'`, `'2027-32'`, etc. in columns E-J, not year numbers — a different chart shape from everything else built this session, requiring a genuinely new **stacked bar chart renderer** rather than reusing the stacked-area one.
  - **"3. Annual Operating Costs"** (rows 138-152, POINT) — standard annual `D-J` layout, same as everywhere else.

### What changed

- `ui/outputs.py`: new constants (`COST_SHEET_IMPORT_PROD`, `IMPORT_COST_ROWS`/`PRODUCTION_COST_ROWS` + total rows, `COST_SHEET_POWER`, `CAPEX_ROWS_5YR` + `CAPEX_PERIOD_COLS`/`LABELS`, `OPEX_ROWS` + total row) and 4 compute functions (`compute_import_cost_chart`, `compute_production_cost_chart`, `compute_capex_chart`, `compute_opex_chart`), all added to `compute_outputs()`.
- `ui/templates_str.py`:
  - Added "Costs" as a seventh clickable tab (`view-costs`), reusing the sub-tab pattern from Indicators (2 sub-tabs this time, both enabled immediately since both reference screenshots were supplied together).
  - **New `renderStackedBarChart()`** — a genuinely new chart type this session (stacked *bar*, not area), needed because the five-year-period capex chart has discrete buckets rather than a continuous year axis; a stacked area there would misleadingly imply interpolation between periods that don't actually connect. Total overlay drawn as a `type: "line"` dataset mixed into an otherwise-bar chart config (Chart.js supports per-dataset type overrides), same black-line-with-dots styling as every other Total line this session.
  - Extended the shared `COLORS` palette from 13 to 14 entries (`+"#8d6e63"`) for the 14-series capex/opex charts.
  - Import/Production Cost charts and Operating Costs reuse the existing `renderStackedChart()` — no new code needed for those 3.

### Verified

- Direct `curl`: all 4 charts return real, lever-reactive, plausible values — e.g. capex total peaking mid-trajectory (₹26,442bn in 2037-2042) then declining as the renewable buildout matures, Gas import costs rising sharply toward 2047 (₹14,049bn) as coal imports collapse toward 0, consistent with everything else observed this session under the L4 scenario.
- Playwright: zero console/page errors on both sub-tabs; screenshots confirmed correct rendering — stacked areas with Total overlay for Import/Production/Operating costs, and the five-year discrete-bucket stacked bar chart (with its own Total line) for capex, all 14 technology colors distinct with no collisions.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### What's still not built (superseded — Land & Water tab built next, see below)

- All top-level tabs now built. See next session note.

---

## Session Notes (2026-07-10, cont'd) — Land & Water Use Tab Built (Final Top-Level Tab)

Seventh and final new top-level tab this session. Reference screenshot: **Land Use** (Million Hectares, stacked area, 8 categories mixing individual technologies with pre-aggregated buckets — Gas Power Stations, Coal Power Stations, CCS, Nuclear, Hydro Power Generation, Renewables, Bio Energy, Green Hydrogen) and **Water use** (Billion Litres, stacked area, 6 categories — Gas Power Stations, Coal Power Stations, Solar CSP, Nuclear, Domestic Fuel production, Green Hydrogen).

### Data sources — two dedicated sheets, found immediately by name

The workbook has sheets literally named `'Land Use'` and `'Water Use'` — no searching needed, confirmed present in the original sheet-name list gathered at the very start of this session. Both sheets already contain **exactly** the reference charts' category mix (individual technology rows alongside the sheet's own pre-aggregated bucket rows, e.g. "Renewables" on Land Use is already a sum of Solar PV/CSP/Onshore Wind/Small Hydro *within the sheet itself*, not something summed by us) — the two reference charts' odd mix of specific-vs-broad categories turned out to just be what the source sheets already present as their own headline rows.

**Column layout — a fourth and fifth distinct pattern found this session** (after `D-J`, `BC-BH`, and the `I-N` trajectory-table layout from the Waste-to-Electricity capacity row): Land Use uses `K=2022..P=2047`, Water Use uses `J=2022..O=2047` — both confirmed directly from each sheet's own row 4 year header, not assumed from either pattern already seen.

**Two unit judgment calls, both resolved by checking the source rather than trusting the reference screenshot's axis label:**
- Land Use's own section header (row 36) reads "Area in **M ha**" (million hectares). The reference chart's axis says "Hectares" with tick labels like "1.6M" — read as shorthand for "1.6 million Hectares", this is consistent with the sheet's own M-ha values, so no conversion needed. Labeled our card **"Million Hectares"** rather than bare "Hectares" to stay unit-honest without needing a custom large-number tick formatter (same category of correction as the earlier "kg CO2e" vs. "tonne CO2e" catch this session).
- Water Use's raw rows and the sheet's own later "Water in MCM" summary section are numerically identical to "Billion Litres" (1 MCM = 1,000,000 m³ = 1,000,000,000 L = 1 billion litres, exact unit equivalence) — used directly, no conversion factor.

### What changed

- `ui/outputs.py`: new `LAND_USE_SHEET`/`YEAR_COLS`/`ROWS`/`TOTAL_ROW` and `WATER_USE_SHEET`/`YEAR_COLS`/`ROWS`/`TOTAL_ROW` constants; `compute_land_use_chart(eng)` and `compute_water_use_chart(eng)`, both added to `compute_outputs()`.
- `ui/templates_str.py`: added "Land & Water" as the eighth and final clickable tab (`view-land-water`). Both charts reuse the existing `renderStackedChart()` — no new rendering code needed.

### Verified

- Direct `curl`: both charts return real, plausible, lever-reactive values. Land Use total grows from 0.30M to 2.75M hectares (2022→2047), dominated by "Renewables" (2.32M ha by 2047) — consistent with the well-known real-world land-footprint tradeoff of large-scale solar/wind buildouts, matching the aggressive L4 renewable scenario used throughout this session. Water Use shows Coal Power Stations' water demand collapsing to 0 by 2042 (coal phase-out, consistent with every other coal-related metric observed this session under L4) while Domestic Fuel production and Nuclear water demand rise to compensate.
- Playwright: zero console/page errors, both charts rendered correctly with Total overlay lines and correct units.
- Re-ran `count_flows.py`: still **78/78, 0 mismatches** — engine untouched, all changes confined to `ui/`.

### Milestone: all 8 top-level tabs now built

All Energy, Electricity, Energy Security, Emissions, Indicators (3 sub-tabs), Costs (2 sub-tabs), Energy Flows (Sankey), and Land & Water — every tab from the original reference screenshots is now live with real, lever-reactive data, none of it invented or approximated without explicit confirmation from the source workbook. `xlcompiler/compiler/` (the engine) remains untouched throughout — confirmed at 78/78 flow matches after every single change this entire session.

---

## Session Notes (2026-07-10, cont'd) — `ui/app.py` Silent-Output Bug, Sidebar Redesign

Note: this session's UI work happened in **`ui/app.py`** (`Flask(__name__)`, port **5050**), the newer/renamed sibling of the `xlcompiler/demo_app.py` described earlier in this doc — same architecture (loads `ModelEngine`, sets the two mode-switch levers, `/set_scenario` + `/recalc` endpoints), different file location. Treat `ui/` as the current live app going forward.

### Bug: running `python app.py` in a terminal showed no output at all

**Root cause:** stdout buffering, not an app bug. When Python's stdout isn't a real terminal (piped, or run through certain launcher/IDE terminal wrappers), `print(...)` and Flask's own startup banner sit in an internal buffer and never flush, so the terminal shows nothing even though the process is alive and (eventually, once the workbook load completes) actually serving requests.

**Fix:** run with `python -u app.py` (unbuffered stdout) instead of `python app.py`.

**Separately discovered while debugging this:** Windows will happily let multiple Python processes bind to the same port across restarts (same class of issue already documented above for port 5000 in the `demo_app.py` section — this recurred on port 5050 for `ui/app.py`). `netstat -ano | grep 5050` showed 3 stale `LISTENING` PIDs simultaneously. Symptom: code edits appear to have no effect because the browser/curl may be talking to an old process. **Always check `netstat -ano | grep <port>` and kill every stale PID before trusting a "it's not picking up my changes" observation** — this is now the second time this exact failure mode has appeared in this project (see the `demo_app.py` port-5000 note above), so treat it as a standing checklist item whenever a local server "isn't updating."

### Sidebar redesign — segmented, collapsible lever panel matching reference screenshot

User supplied a reference screenshot of the target lever-panel style: a "Custom Pathway" dropdown, group headers (Economics/Demand/Supply), and per-subcategory rows each showing a `›` expand chevron plus a row of four "Level of Ambition" boxes (1-4, filled black = selected level) — rather than the previous flat list of raw sliders under each subcategory heading.

**What changed, both in `ui/templates_str.py`:**
- `render_sidebar_html()`: each subcategory (e.g. "Transport", "Bioenergy" — label is the part after `" — "` in the existing `CATEGORY_RANGES` names from `ui/levers.py`, or the whole name if there's no `" — "`) now renders as a `.subcat-row` (chevron + title + 4 `.level-box` divs, `data-lever-ids` listing every lever id in that subcategory) followed by a collapsed-by-default `.subcat-detail` block containing the original per-lever slider rows (kept, not removed — the fine-grained control is still there, just hidden until expanded). A `.lever-legend` header ("Lever Settings" / "1 2 3 4") was added above the group list to match the screenshot's column headers.
- New CSS for `.lever-legend`, `.subcat-block`, `.subcat-row`, `.chevron` (rotates 90° via `.subcat-block.open`), `.level-boxes`/`.level-box` (`.active` = filled black), `.subcat-detail` (`display:none` until `.subcat-block.open`).
- New JS: clicking a `.level-box` sets every lever id in that subcategory's `data-lever-ids` to that box's level, **clamped per-lever to its own `data-max`** (same clamping convention already used by `/set_scenario`'s `min(level, ALL_LEVER_MAX[lever_id])` on the Python side — kept consistent client-side rather than inventing a different rule) — then triggers the existing debounced `scheduleRecalc()`. Clicking the row itself (outside a box) toggles `.subcat-block.open` to expand/collapse the detail sliders. `updateSubcatBoxes(row, leverIds)` recomputes which box (if any) should show `.active` from the current slider values — all-equal → highlight that level; mixed values → no box highlighted (signals "custom" within that subcategory). Wired into the existing slider `input` handler (so manually dragging a sub-slider updates its subcategory's box state) and into `setScenario()` (so picking a preset scenario also refreshes every subcategory's box state via a new `updateAllSubcatBoxes()` call).
- Deliberately did **not** change the underlying data model (`ui/levers.py`'s `CATEGORY_RANGES`/`SIDEBAR_GROUP_ORDER`) or the `/set_scenario` and `/recalc` endpoints — this was a presentation-layer change only, same lever ids and same backend contract.

**Verified:** `ast.parse()` confirmed the edited `templates_str.py` is syntactically valid Python; killed 3 stale processes on port 5050 (per the bug above), started one fresh `python -u app.py`, and confirmed via `curl` that the served HTML contains the new `.subcat-row`/`.level-box`/`.lever-legend` markup (the first `curl` attempt, before killing the stale processes, deceptively returned old markup — direct confirmation of why the netstat check above matters).

**Not yet done:** user hasn't yet manually clicked through the new panel in a live browser to confirm interaction feel (box click behavior, expand/collapse animation). Possible follow-up requests flagged but not actioned: clicking an already-active box to reset it to 0, renaming subcategory labels to match the screenshot's exact wording (e.g. splitting a "Costs" row out from "Economics").

---

## Session Notes (2026-07-13) — L1 Scenario Discrepancy Investigation: Slider Floor Bug (fixed) + Preset-Mode Ungated-Lever Finding (fix proposed, not yet applied)

User ran a true "L1 (Least Effort — all Control levels = 1)" scenario directly in Excel (resetting `Control!E5:E62` to match the sheet's own "Least Effort Scenario (All at level 1)" reference column, `Control!N`) and compared it against the dashboard's L1 preset. Found a consistent ~26.6% gap across Total Demand, Primary Supply, and Per-Capita Demand (dashboard higher in every case), plus a 15.8pp gap on Import Dependence.

### Investigation path (in order, each step ruling something out)

1. **Ruled out: on-disk `.compiled.pkl` cache staleness.** Forced a full fresh openpyxl reparse (`WorkbookModel.load(..., use_cache=False)`) — identical results to the cached load. Not a caching artifact.
2. **Ruled out: leftover in-process override state as a coincidence/methodology artifact** (user's own hypothesis, and a reasonable one). Tested with a fully wiped override dict (`eng.clear_levers()`) each time, three clean configurations:
   - Preset L1, sliders untouched → **1,880.65** Mtoe demand.
   - Preset L1, **but** sliders deliberately also set to 1 → **2,201.98**.
   - Custom mode, sliders set to 1, no preset → **2,201.98** (identical to the previous line).

   Since a clean Preset run changes answer depending on where the sliders happen to sit, this is reproducible, not a stale-state artifact — sliders are genuinely leaking into "Preset" results for at least some part of the calculation.
3. **Ruled out: the engine (`xlcompiler/compiler/`) itself.** Confirmed directly against the raw engine, bypassing the dashboard: `Control!E6` (Coal lever) set to `4` and then `2` while `E12=1` (Preset) — the workbook's own gate cell `I.b!7` returned `1.0` both times, correctly ignoring the slider. The engine faithfully executes whatever the workbook's formulas say; per the Critical Rule, this is not an engine bug and needed no engine change.

### Root cause, found by tracing the actual gating formula

Every module's "effective level" cell follows this pattern (e.g. `I.b!7`, Coal Power Stations):
```excel
=IF(predefined.scenario=1,1,IF(predefined.scenario=2,2,IF(predefined.scenario=3,3,IF(predefined.scenario=4,4,I.b.scenario))))
```
(`predefined.scenario` = `'IESS V3 Main Sheet'!$E$12`; `I.b.scenario` = `Control!$E$6`, the slider itself.) When a preset is active, this hardcodes the level and correctly ignores the slider, exactly matching the workbook's own documented behavior at `IESS V3 Main Sheet!7`: *"Selecting one out of the four prescribed scenarios does not change the inputs in option buttons, but results are generated automatically."*

**46 of the 51 levers follow this exact gated pattern — verified by searching every formula referencing each lever's named range for a `predefined.scenario` gate.** But **5 do not have any such gate anywhere in the workbook**: GDP Growth (`growth.scenario` → `Control!E31`) and the 4 Cost levers — Capital/Fuel/Infrastructure/Finance Costs (`cost.capital/fuel/infrastructure/finance.scenario` → `Control!E59-62`). These 5 are always read raw from the Control sheet, **regardless of what preset (`E12`) is selected** — a genuine, deliberate-looking asymmetry in the workbook itself, not an engine translation error. (Side confirmation: this is exactly why the "Least Effort" reference column, `Control!N`, has those same 5 rows set to `2` instead of `1` — first noticed during the original L1 comparison, at the time not yet understood as *why*.) GDP growth is one of the largest drivers of total energy demand in a macro model like this, so leaving it un-reset is enough on its own to explain a swing of the observed size.

### Bug 1 (found + fixed): lever sliders allowed a nonexistent "Level 0"

`ui/templates_str.py`'s lever slider markup had `min="0"` hardcoded, but the workbook only ever defines levels 1 through each lever's own max (usually 4, sometimes 3 or 5, from `Control!F` "LIMIT") — there is no "Level 0" concept anywhere in the workbook. Confirmed 3 levers (`Control!E6` Coal, `E22` Biomass Residue, `E26` Hydrogen Production) happened to be saved at `0` in the current workbook file, with no level-0 description in the sheet — i.e. stale/uninitialized data, not a deliberate "off" state. **Fixed:** `min="0"` → `min="1"` at [ui/templates_str.py:55](../ui/templates_str.py#L55). Side effect (accepted): those 3 levers will visually clamp up to `1` on next page load instead of showing `0`.

### Bug 2 (found + fixed): `/set_scenario`'s Preset display value was order-dependent

Because the 5 ungated levers were never explicitly reset by `ui/app.py`, `/set_scenario`'s `display_data` (the number shown for "Level 1") was computed using whatever GDP/Cost slider values happened to be left over from the previous `/recalc` call — making the displayed Preset number silently dependent on prior UI interaction, not a pure function of the picked level. This was a bug in `ui/app.py` only, not the engine.

**Fix applied** in `ui/app.py`: new `UNGATED_LEVER_ROWS = [31, 59, 60, 61, 62]`, `LEVEL_REF_COL = {1: "N", 2: "Q", 3: "P", 4: "O"}` (mapping preset level → the workbook's own per-scenario reference column — N=Least Effort/L1, O=Heroic/L4, P=Aggressive/L3, Q=Determined/L2), and a new `_apply_ungated_reference_levels(level)` helper called right after `eng.set_lever("IESS V3 Main Sheet", "E12", level)` and before `compute_outputs(eng)` in `/set_scenario`. Every Preset-level result is now deterministic regardless of leftover slider state — verified directly: deliberately left `Control!E31/E59-62` contaminated at `4`, called the fixed path, got the same result as a clean run.

**Isolated which of the 5 levers actually matters for these KPIs:** only `Control!E31` (GDP Growth) affects `total_demand`/`total_supply`/`per_capita_demand`/`import_dependence` — the 4 Cost levers (`E59-62`) only feed cost/financial outputs, confirmed by testing each in isolation (setting Costs to their reference value while leaving GDP untouched: zero change to any of the 4 KPIs).

### Net effect on the original 26.6% gap — the fix made it WORSE, not better (important, non-obvious result)

Isolated, clean before/after with the fix:
- Old (buggy, order-dependent) dashboard L1 total_demand: **1,880.65** Mtoe.
- New (fixed, deterministic, reference-column-driven) dashboard L1 total_demand: **2,201.98** Mtoe.
- User's Excel-side true L1 figure: **1,380.74** Mtoe.

The fix is *correct* per the workbook's own design (GDP Growth reference value for L1 is `1` on the Control sheet's own `N31` cell, and setting it there is exactly what the "Least Effort Scenario (All at level 1)" reference column says to do) — but it moves the dashboard's L1 number further from the user's Excel-reported L1 figure, not closer. **This proves the ungated-lever leak was a real, separately-worth-fixing bug, but it was never the actual explanation for the original 26.6% gap.** The real cause of that gap is still open and unexplained as of this note.

### Cache-clearing test (2026-07-13, user-initiated)

User deleted `workbook/IESS2047_Version_3.0.xlsx.compiled.pkl` and all `__pycache__/`/`.pyc` files by hand and reran `run_full.py` fresh, to rule out any stale-cache explanation for the gap. (Before this, it had already been checked once via `WorkbookModel.load(..., use_cache=False)` with identical results — this was a fully independent, from-scratch re-verification via the trusted validator script itself, not just a repeat of the earlier ad hoc check.) Both `.pkl` and `.pyc`/`__pycache__` are confirmed pure build artifacts — regenerated automatically on next load/import, safe to delete, not source-controlled (this project has no `.git` at all — confirmed via `git status` → "not a git repository" — so any IDE "M" modified-file badge on `__pycache__` entries is a stray editor/extension artifact, not a real tracked change).

**Operational note for `run_full.py`/`count_flows.py` going forward:** both scripts' built-in default workbook path is a deliberately-left-stale placeholder (per the 2026-07-03 session note) — always pass the real path explicitly as a CLI arg. Correct invocation from inside `xlcompiler/`: `python run_full.py "D:\ACPET\IESS\Excel_Enging\compiler\workbook\IESS2047_Version_3.0.xlsx"` (or the equivalent relative path `../workbook/IESS2047_Version_3.0.xlsx` — the workbook folder is a sibling of `xlcompiler/`, one level up, not inside it).

### `run_full.py`/`count_flows.py` fresh-cache re-verification: still 78/78, 0 mismatches

After the user manually deleted the `.pkl` and all `__pycache__/` and reran from a fully clean state: `count_flows.py` reported `edges_total=78, checks_numeric_cached=78, matches=78, mismatches=0, nonzero_compiler_2047=72` — identical to every prior validated run. User also independently hand-verified all 69 non-trivial `Flows` edges directly against the workbook's own `Flows!A1:N83` sheet (every From→To pair, every year column, to the penny) — zero discrepancies, including the 3 rows that read as all/near-zero (`Municipal Waste→Solid`, `Municipal Waste→Gas`, `Agricultural Waste/Energy Crops→Industry` — confirmed genuinely near-zero in the sheet too, not an engine gap). **This is the strongest possible confirmation that the engine's default/base-state formula translation is 100% correct** — the cache-clearing exercise fully ruled out any caching explanation for the L1 gap, independently, a second time.

### RESOLVED: the 26.6% L1 gap was never a compiler bug — it was an incomplete Excel-side scenario setup

Root-caused by comparing live values read directly from the user's actual open Excel session against our engine's own default (untouched) state:

- Live `IESS V3 Results!J17` in Excel right now = **1368.92** — NOT the `1380.74` the user's original report cited. The user caught this discrepancy themselves and flagged it.
- Live `IESS V3 Results!J48` in Excel right now = **1810.76**.
- Live `Control!E31` (GDP Growth lever) in Excel right now = **3** — despite the user's belief that `Control!E5:E62` had all been reset to match the "Least Effort" reference column.
- Live `Control!N31` (the actual L1 reference value for that row) = **1**. `E31` (3) and `N31` (1) do not match — GDP Growth was never actually set to its L1 value in the live workbook.

**The critical fact:** Excel's live `J17`/`J48` (`1368.92` / `1810.76`) match our engine's own default/untouched-state computation **exactly**, to the second decimal (this is the same default-state pair found earlier in this session, before any lever overrides were ever applied — see the "cached formula value" observation above). This means: for the exact same lever state, Excel and our engine produce identical results. There is no divergence between the two systems at all.

**What actually happened:** the user's original "true L1" Excel test never fully applied — at minimum, `Control!E31` (GDP Growth) was left at its old value (`3`) instead of being reset to `1`. Since GDP Growth alone was already isolated this session as the single lever responsible for the entire swing between the dashboard's two L1 readings (`1,880.65` → `2,201.98`, see Bug 2 above), an unreset `E31=3` in the Excel-side test is fully sufficient to explain the entire originally-reported 26.6% gap, with no compiler-side explanation needed.

**Verification step handed to the user (not yet confirmed as of this note):** manually set `Control!E31=1` in the live Excel session, force recalc, re-read `J17` — predicted to land near `2,201.98`, matching the engine's own reference-column-driven L1 computation (Bug 2 fix), if this diagnosis is correct.

### CORRECTION: the "no engine bug, ever" conclusion above was premature — reopened

User set `Control!E31=1` in the live Excel workbook, forced a full recalc, and re-read `IESS V3 Results!J17`/`J48` directly: **`1,380.74` / `1,832.31`** — exactly matching the user's original very-first report. So the original Excel-side L1 test was correct all along; the earlier `1368.92` reading was a transient in-between state, not the real answer, and the "GDP Growth alone explains it" theory above is **wrong** — confirmed by direct test: with `Control!E31=1` and every other lever at its true L1 reference-column value (`E10=1`, `E12=0`), our own engine computes total_demand = **2,188.79**, not anywhere near `1,380.74`. The gap is real, larger than first thought (~59%, not 26.6%), and unexplained by any single lever.

**Ruled out this round, in order:**
1. **KPI aggregation layer (`ui/outputs.py`).** Compared our own `compute_outputs()` KPI sum against Excel's dedicated `J17`/`J48` cells in the *default* (already-validated-78/78) state: total_supply matched exactly (`1810.76` = `1810.76`); total_demand was off by only `1.06` out of `1369` (0.08%, likely a single small edge classification nuance, noted but not chased — nowhere near large enough to matter here). **Conclusion: our KPI summation logic is correct.** The bug is upstream of the KPI layer, in the `Flows` edge values themselves under the lever-driven path.
2. **A red herring of my own making, worth recording so it isn't repeated:** re-testing "set every lever to its `N`-column reference value" via `eng.read_cell("Control", f"N{row}")` instead of the raw `.value` produced a wildly different, wrong number (`795.91`) — root cause was **not** a new engine finding, it was that 2 of the 51 lever rows (`Control!E45` "Commercial - ECBC Compliance", `E47` "Fuel Mix - Industry") have **no `N`-column "Least Effort" reference value defined at all** in the workbook, and `read_cell` on an empty cell returns `0` — silently reintroducing the same "phantom Level 0" class of bug already fixed in the UI slider, this time in an ad hoc diagnostic script. The methodologically correct figure remains `2,188.79` (using the version of the script that skips undefined-reference rows rather than defaulting them to 0).

### New finding: the evaluator has two silent-zero fallback paths that may be implicated

User asked directly: "is there anything in our code doing recalculation — `engine.py`?" Answer: `engine.py` has no separate recalc step; all recalculation is `evaluator.py`'s `eval_cell()` ([evaluator.py:89](xlcompiler/compiler/evaluator.py#L89)) — pure recursive, on-demand, dependency-walking evaluation, matching Excel's model conceptually. But it has two fallback branches that both silently return a constant `_circular_seed = 0`, with no error, warning, or log entry of any kind:
```python
if key in self._stack:
    return self._circular_seed   # true circular reference detected
if self._depth > self.MAX_DEPTH:   # MAX_DEPTH = 200
    return self._circular_seed   # not circular, just a long dependency chain
```
Real Excel either does proper iterative convergence for circular refs (if the workbook enables iterative calculation) or throws a visible `#REF`/circular-warning — it has no "give up after N levels and silently substitute 0" behavior. This is a plausible mechanism for a large, silent, systematic error that would never show up as an engine gap (`report_gaps()` doesn't track these fallback hits at all — a real blind spot in the diagnostic tooling, same category of issue as the original `run_real.py` incident).

**Instrumented directly (fresh engine, `E10=1`, `E12=0`, all 51 levers at true L1 reference values, matching the 2,188.79 computation):**
- `MAX_DEPTH` (200) fallback: **0 hits** — ruled out, the lever-driven chains are not that deep.
- Circular-reference fallback: **10 hits** out of 223,066 total `eval_cell` calls — small in count, but not yet identified *which* 10 cells, or how central/high-leverage they are in the dependency graph. A single circular cell that many downstream formulas fan out from could still explain a large aggregate error even at only 10 raw hits.

**Session paused here, at user's request, to save progress before going further.** Next concrete step (not yet done): identify and print the exact `(sheet, row, col)` of all 10 circular-fallback hits under the true-L1 lever configuration, then trace each one manually to see whether Excel handles it via iterative calculation (in which case our `0`-substitution is a real, general, previously-undiscovered engine gap — fixable the same way the original 6 fixes were) or whether it's cosmetic/inconsequential to the final KPIs.

### Bug 3 (found + fixed): `IF` was eagerly evaluating both branches, same class of bug as the original Fix 1 (`IFERROR`)

Named the exact 10 circular-fallback cells: all in the same year-interpolation formula template, across `VII.b` (rows 48-50), `III` (rows 38-40), `XIII.a` (row 81) — e.g. `VII.b!I48`:
```excel
=IF(I46<=2027, $H48+(I$46-$H$46)*$G48, $J48+(I$46-$J$46)*-0.3%)
```
`I46=2022`, which **is** `<=2027`, so Excel only ever needs the true branch — the false branch (referencing `$J48`) is never reached. But `J48`'s own formula references `$I48` back in a symmetrical way. **Root cause:** the evaluator's recursive-descent parser evaluates all of `IF`'s arguments eagerly (`_parse_args`, before dispatch) — exactly the same underlying issue as the original Fix 1, which explicitly special-cased `IFERROR` for laziness but *left `IF`/`CHOOSE` eager as an accepted, documented limitation at the time* ("wasn't the reported problem"). It became the problem: eager evaluation of the never-reached branch manufactures a fake circular dependency between two cells that Excel's own lazy `IF` never actually links.

**Fix applied** in `xlcompiler/compiler/evaluator.py`'s `_parse_ident`: extended the same lazy-branch technique already built for `IFERROR` (`_split_call_args`) to `IF` — evaluate the condition first from raw, un-evaluated tokens, then evaluate only the selected branch. `CHOOSE` left untouched (still out of scope, no evidence it's implicated).

**Verified:** re-ran `count_flows.py` from a fully cache-cleared state immediately after — still **78/78, 0 mismatches** (broad blast-radius risk from touching every `IF` in the workbook was explicitly flagged and accepted before applying). Re-instrumented the true-L1 circular-hit trace: **0 circular hits remaining** (down from 10) — the fix eliminates the spurious cycle completely, confirming the diagnosis.

**But it did not move the L1 KPI gap at all** — total_demand stayed exactly `2,188.79` before and after. Those 10 cells, while genuinely wrong before this fix, turned out to be inconsequential to `total_demand`/`total_supply` specifically. Real, valuable, permanent engine fix — but not the explanation for the L1 gap. Ruled out.

### Breakthrough: the Preset (`CHOOSE`) branch is now proven byte-for-byte correct — the bug is isolated to Custom Pathway mode specifically

User independently tested Excel's actual predefined-scenario dropdown (`Target Year Input!E10=1`, cycling `IESS V3 Main Sheet!E12` = 1 through 4) directly in the live workbook and reported real Excel values:

| Scenario | Excel value (Mtoe) |
|---|---|
| 1: Least Effort | **1,880.65** |
| 2: Determined Effort | 1,447.58 |
| 3: Aggressive Effort | 1,223.96 |
| 4: Heroic Effort | 1,073.94 |

**`E12=1` (Least Effort) = 1,880.65 in live Excel — an exact match to our engine's own Preset-mode computation from earlier this session** (also `1,880.65`, computed under the identical `E10=1, E12=1`, Control levers left at their default/untouched values). **This is the first exact, independently-cross-checked confirmation that the entire Preset/`CHOOSE(...)` calculation branch is correct in our engine, byte-for-byte, not just self-consistent.**

This sharply narrows the mystery. There are two structurally different calculation paths in this workbook:
- **Preset mode** (`E12≠0`, hardcoded `CHOOSE`/`IF(predefined.scenario=N,N,...)` trajectories) — **now proven correct**.
- **Custom Pathway mode** (`E12=0`, every lever read individually from `Control!E<row>`) — **still diverges**: our engine gives `2,188.79` for "every lever at its L1 reference value," Excel's equivalent test (the user's original report) gave `1,380.74`.

**Conclusion: the remaining bug, whatever it is, is confined specifically to how Custom Pathway mode processes the 51 individually-set Control-sheet levers** — not a general formula-engine problem (ruled out twice via 78/78, and now a third time via the exact Preset-mode match), not caching, not KPI aggregation, not circular references.

### CORRECTION to Bug 2: the "fix" was itself wrong — reverted

The Bug 2 fix (forcing GDP Growth + 4 Cost levers to their reference-column values before computing `display_data` in `/set_scenario`) was applied on the assumption that Preset mode *should* deterministically reset those 5 ungated levers. **Live Excel disproved this directly:** the user's independent Preset-scenario test (table above) had `Control!E31=3` (untouched, not reset to `1`) the whole time, and Excel still produced the correct `1,880.65`. **Excel's real behavior is to leave all 51 levers completely untouched when a preset is picked — including the 5 ungated ones — exactly as the workbook's own documentation says** ("does not change the inputs in option buttons"). The Bug 2 fix broke a previously-correct result: after applying it, the dashboard's Level-1 display moved from the correct `1,880.65` to an incorrect `2,201.98`.

**Reverted** in `ui/app.py`: removed the `_apply_ungated_reference_levels(level)` call from `/set_scenario`'s `display_data` computation (and deleted the now-dead `UNGATED_LEVER_ROWS`/`LEVEL_REF_COL`/`_apply_ungated_reference_levels` helper entirely — nothing else used it). **Verified directly (engine-side, before asking the user to restart the server):** Preset L1 now recomputes to exactly `1,880.65` again, matching Excel.

**Recurring operational note, hit yet again during this same fix:** two stale Flask processes were found simultaneously bound to port 5050 (`netstat -ano | grep 5050`) partway through this back-and-forth — same class of issue documented repeatedly throughout this project. Cleared both times via `taskkill //F //PID <pid>` before asking the user to restart and hard-refresh/use incognito to rule out browser-side caching too (a new variant of the same "stale artifact" lesson, this time client-side rather than server-side).

### The KPI/chart total IS correct — confirmed independently against live Excel, cell-by-cell

With the Bug 2 revert live, user independently verified Preset Level 1 against `'2047'!T11:T22` in Excel, category by category:

| Category | Excel | Our chart |
|---|---|---|
| Total | 1,880.65 | 1,880.64 ✅ |
| Agriculture, Buildings, Cooking, Telecom, Transport | (5 values) | all ✅ exact |
| Industry | 1,142.00 | 1,043.30 ❌ off by 98.70 |
| Miscellaneous | 31.95 | 130.64 ❌ off by 98.70 (opposite sign) |

**Root cause (found, fix proposed, not yet applied):** `ui/outputs.py`'s `DEMAND_SECTOR_GROUPS` buckets the `"Non-energy use"` `Flows` edge under `"Miscellaneous"`. Verified directly: `Electricity Grid → Miscellaneous` alone = `31.95` (exactly Excel's real "Miscellaneous"), and Industry-only edges + `Non-energy use` edges = `1,043.30 + 98.69 = 1,142.00` (exactly Excel's real "Industry"). **Pure UI-layer labeling error** — Excel's own sector rollup counts `"Non-energy use"` as part of Industry, not Miscellaneous. **Proposed fix (pending approval):** move `"Non-energy use"` from the `"Miscellaneous"` group to the `"Industry"` group in `DEMAND_SECTOR_GROUPS`. No engine change, no total/KPI change (the total was already correct) — only which visual bucket one line item falls into.

### A second suspected discrepancy, investigated and closed as NOT a bug — a genuine workbook design inconsistency

User separately tested Scenario 4 (Heroic Effort) against `'Intermediate output'!BF29:BF54` for 2037: 8 of 9 supply categories matched exactly; Coal was short by `26.36` (chart `297.59` vs. `Intermediate output`'s `323.95`). Traced directly:
- `Intermediate output!BF43` (Coal Imports, via coking/non-coking split: `BF44 (73.77, =XV.b!L155) + BF45 (20.62, a residual MAX(...) calc)`) = `94.38`. **Our engine's own live value for this exact cell also = `94.38`** — matches Excel, confirmed no bug here.
- `Flows!J7` ("Coal Imports" row, 2037 column) uses a **completely different formula** — `MAX(-XVII.b.Inputs[2037, Y.04], 0)`, a simple capped net-balance read from a different table entirely. Our engine computes `68.02` for this cell. **User confirmed live in Excel: `Flows!J7` is also `68.02`** — exact match.

**Conclusion: not a bug anywhere in `xlcompiler/` or `ui/`.** The workbook itself contains two different formulas that both purport to represent "Coal Imports 2037" and permanently disagree with each other by the coking/non-coking split amount (`26.36`) — `Intermediate output` computes one number, `Flows` computes a simpler, smaller one, and our chart (correctly, faithfully) sources from `Flows`, same as everything else validated at 78/78 all session. Logged as a **workbook modeling note** for whoever maintains the source file, not an engine or dashboard defect. No fix applied, none needed.

### Where the L1/dashboard investigation stood at that point

**The core mystery (Preset-mode calculation being correct) is resolved and confirmed multiple independent ways.** One concrete fix remained open at this point: the `Non-energy use` → `Industry` bucket correction in `ui/outputs.py`'s `DEMAND_SECTOR_GROUPS` (proposed, not yet applied — still true as of the end of this session, deprioritized in favor of the bug below which turned out to be more urgent). The original "Custom Pathway diverges from Excel" finding (`2,188.79` vs `1,380.74`) remains **still separately unresolved and untouched** — open for a future session.

---

## Session Notes (2026-07-13, cont'd) — Real Architecture Fix: `scoped_levers()`, Plus Residual & Performance Follow-ups (queued)

### Bug 4 (found + fixed properly, not patched): `/set_scenario`'s baseline computation was leaking into later requests

**Symptom, reproduced live:** clicking preset levels repeatedly on the running dashboard gave a *different* number each time for the same level (e.g. L2 showed `1,689.37`, then `1,564.93` on a direct re-check, neither matching the correct `1,449.22`) — instability that only showed up once multiple presets were clicked back-to-back on one long-running server, which is why it hadn't surfaced earlier in this session's mostly single-preset-per-restart testing.

**Root cause:** `/set_scenario` computes two things — `display_data` (the real answer, shown to the user) and `baseline_snapshot` (a hidden number used only for "changed" diff-highlighting, computed by actually setting all 51 `Control!E<row>` levers to `min(level, max)`). Both run against the **same single, persistent `ModelEngine` instance that lives for the whole life of the server** (necessary — reloading the 438k-cell workbook from scratch takes ~40s, far too slow per-request). The `baseline_snapshot` step's lever-setting was never undone afterward, so its scratch-work silently became the *starting state* for the next `/set_scenario` call's `display_data` — specifically corrupting the 5 ungated levers (GDP Growth, 4 Costs) each time, the same 5 rows implicated in Bugs 2/2-correction earlier this session.

**First proposed fix (correctly rejected by the user as a shortcut):** manually save/restore just those 5 rows around the `baseline_snapshot` block in `app.py`. User's objection, verbatim in spirit: this only patches the one call site and the one known set of rows — it doesn't fix the actual gap, and this project is meant to generalize to other Excel workbooks later, so a per-symptom patch in the UI layer was rejected in favor of a real engine capability.

**Actual fix — a new general-purpose engine primitive**, applicable to any future workbook or caller, not specific to IESS2047 or to these 5 rows:
- `xlcompiler/compiler/evaluator.py`: new `Evaluator.scoped_overrides()` — a `contextlib.contextmanager` that snapshots `self._overrides` on entry and restores it exactly on exit (via `finally`, so it's safe even if an exception occurs inside), plus clears the cache so the restored state re-evaluates cleanly.
- `xlcompiler/compiler/engine.py`: new `ModelEngine.scoped_levers()` — one-line public-API wrapper (`return self.ev.scoped_overrides()`) so callers never need to touch `Evaluator` internals directly.
- `ui/app.py`: `/set_scenario`'s `baseline_snapshot` block now runs inside `with eng.scoped_levers(): ...` — guaranteed to leave the engine's real lever state untouched afterward, no matter what it does inside.

**Verified:**
1. `count_flows.py` from a fully cache-cleared reparse: still **78/78, 0 mismatches**.
2. Direct repeat-call test on one persistent engine, exactly reproducing the original failure mode: `L1, L2, L1, L3, L1, L2` in sequence now gives `1880.65, 1449.22, 1880.65, 1225.04, 1880.65, 1449.22` — **every repeat of the same level returns the identical number**, in any order. Previously this exact sequence would drift.
3. Cross-checked against live Excel figures across all 4 levels:

| Level | Engine | Excel | Diff |
|---|---|---|---|
| L1 | 1,880.65 | 1,880.65 | 0.00 |
| L2 | 1,449.22 | 1,447.58 | 1.64 |
| L3 | 1,225.04 | 1,223.96 | 1.08 |
| L4 | 1,074.24 | 1,073.94 | 0.30 |

### Small residual gap (≤0.15%, present at every level) — not yet root-caused

A small, consistent gap remains at every preset level (`0.00` to `1.64` Mtoe, all under 0.15%) — same order of magnitude as an earlier, separately-noted discrepancy (default-state KPI vs. Excel's own `J17` total, `1,369.98` vs `1,368.92`, ~0.08%). Suspected to be a minor rounding or edge-classification nuance in how `ui/outputs.py` sums `Flows` edges into a KPI, not a deep engine bug — but this is an educated guess, not a confirmed diagnosis; no trace has been done yet. **Queued as a next step, not yet started:** trace the KPI backward to find the first specific edge/cell that disagrees with Excel, same method as every other fix this session.

### Performance: `/recalc` and `/set_scenario` are noticeably slow (~3-6s), cause not yet measured

Flagged by the user as worth improving, but explicitly **only if it doesn't risk breaking anything already working** — user was clear that safety takes priority over speed. Agreed approach: **profile first, change nothing yet.** The existing doc note attributing the slowness to "8 separate technology-sheet reads" (from the earlier Electricity-tab session) is an unconfirmed guess, not a measurement. A real architectural fix — teaching the evaluator to invalidate only the cells actually downstream of a changed override, instead of clearing its entire memoized cache and recomputing everything from scratch on every single lever change — was explicitly named as a **higher-risk change not to attempt casually**; if profiling points there, it needs its own careful proposal and sign-off before touching anything, per this project's standing Change Control rule. **Not started yet — queued for next session.**

### Net status at end of this session

Two real engine/dashboard bugs found and properly fixed this stretch (Bug 3: `IF` eager evaluation / spurious circular refs; Bug 4: `/set_scenario` baseline leak, fixed with a new general `scoped_levers()` engine primitive rather than a UI patch). The original Bug 2 "fix" was found to be wrong and reverted. One dashboard-only bucketing fix (`Non-energy use` → `Industry`) remains proposed but unapplied. Two follow-ups queued but not started: root-causing the small residual gap, and profiling `/recalc`/`/set_scenario` performance. The separate, larger "Custom Pathway mode diverges from Excel" mystery (`2,188.79` vs `1,380.74`) remains fully open, untouched since it was first isolated.

---

## Session Notes (2026-07-14) — Portability Question, Positioning Paragraph for Leadership, Demo Outline, Packaging Plan

### "Will this work on other, similarly-structured models?" — answered precisely, engine vs. dashboard split

User asked directly whether the compiler would work on other models built in a similar style to IESS. Answer given and worth preserving verbatim in spirit:

**Core engine (`xlcompiler/compiler/`): yes, with high confidence, backed by evidence from this session** — zero workbook-specific code (confirmed by grep, and by the fact that every fix made this entire session, including today's `scoped_levers()` addition, was a general Excel-semantics fix, never a per-file patch). Needs only: the target workbook uses formula constructs the evaluator already understands, or it needs one general fix to `evaluator.py` when it hits something new — the same `report_gaps()`-driven process used throughout this project.

**Dashboard/UI (`ui/`): no, not without real adaptation, and explicitly flagged as the *riskier* case for a "similar style" workbook, not the safer one.** `ui/outputs.py`/`levers.py`/`app.py` are built around this exact file's literal row numbers and sheet names. A visually similar sister-workbook is dangerous specifically *because* it looks familiar enough to tempt assuming the row numbers carry over — and this session proved even within this one file, non-obvious exceptions exist (5 ungated levers, two sheets disagreeing on Coal Imports, a category-bucketing mismatch) that a structurally-similar file could easily have its own different version of. Any new workbook needs the same fresh investigative verification this file got, not a copy-paste of `ui/`.

**Agreed framing for external communication:** "core engine works with minimal/no changes; UI needs a real per-workbook adapter" — this exact distinction was carried into the leadership positioning paragraph below.

### Positioning paragraph for leadership — two drafts, second one corrected for overclaiming

User drafted a paragraph (with input from elsewhere) pitching the tool to a director, including South Africa modernisation and Global Calculator interoperability as potential use cases. Reviewed and flagged specific claims as ahead of what's actually been built/verified this session, rather than rubber-stamping it:

**Accurate, evidence-backed claims (kept as-is):** "executes original workbook logic without Excel" (78/78 validated), "preserves original model logic, no rebuild needed," "model-agnostic, standard Excel semantics" (true specifically for the *engine*, not the dashboard).

**Claims flagged as ahead of current reality, softened in the redraft:**
- **"Secure, scalable web applications"** — current dashboard is a single Flask dev server (`app.run(debug=False)`), not production-hardened. Reads as delivered capability; it's actually a prototype.
- **"Supports multi-user web applications, collaboration"** — flagged as a real, specific technical gap, not just cautious hedging: the dashboard has **one shared engine instance for the entire server** (`eng` is module-level in `ui/app.py`). Two simultaneous users would corrupt each other's lever state — literally the same *class* of bug (shared mutable state with no isolation) that this whole session's `scoped_levers()` fix was built to solve for a *single* user's sequential requests. True concurrent multi-user support does not exist yet and would need its own real work (per-session state or a request-scoped engine).
- **"Adapted to similar pathway models with minimal effort"** — true for the engine specifically; risks being read as including the dashboard, which is not true per the portability answer above.
- **South Africa / Global Calculator interoperability** — legitimate as a proposed direction, but not yet scoped, tested, or evidenced — kept in the redraft but explicitly framed as future opportunity, not a claim of current capability.

**Redrafted paragraph produced** (two-paragraph version + 4 bullet "Key Benefits," engine-proven vs. dashboard-prototype distinction made explicit, e.g. "Extending this into a secure, multi-user, production-grade deployment is a defined next step rather than a current capability" and "Proof-of-concept for digital deployment" instead of "supports multi-user web applications"). Full text of both the original and the corrected redraft exists in this conversation's history; the key editorial principle applied was: **keep every claim that's actually been verified this session, soften or reframe-as-roadmap anything that hasn't.**

### Demo/session outline drafted (30-45 min format)

1. The problem (5 min) — fragile, single-person, Excel-dependent models.
2. What was built (5 min) — engine + validation headline number (78/78, 0 gaps) as the trust anchor.
3. Live demo (15 min) — preset scenario, drag a lever, Sankey diagram — all with Excel closed.
4. Trust/validation (5 min) — side-by-side Excel vs. compiler value match, for a technical audience's credibility.
5. Where this goes next (10 min) — packaging, portability to other models, capacity-building framing, open floor.

### Packaging question — answered, not yet started

User asked whether the engine could be distributed as an installable package/plugin for others to use in their own code. Answer: yes, and the engine is already most of the way there structurally (`xlcompiler/compiler/` is already a real Python package with a clean public API — `ModelEngine.load()`, `set_lever()`, `read_cell()`, `read_flows()`, `scoped_levers()`). What's actually missing, concretely:
1. A `pyproject.toml` (name, version, `openpyxl` dependency) to make it `pip install`-able.
2. A distribution decision — private Git/internal registry (fast, no public exposure) vs. public PyPI (bigger commitment: license, README, versioning discipline).
3. An explicit public-vs-internal API boundary, so future engine changes don't silently break external consumers.
4. Basic usage docs (the `load → set_lever → read_flows/read_cell` pattern already used everywhere in this project, just not yet written down for an outside reader).

**Not started — offered to draft the `pyproject.toml` + starter README as a first concrete step, not yet actioned.**

---

## Session Notes (2026-07-15, cont'd) — UI Visual Redesign Pass + Real Bug Found in Electricity Supply Chart Total

### UI: "looks AI-generated" feedback — first design pass applied

User feedback distilled via `AskUserQuestion` to a specific complaint: the generic "AI dashboard" look (purple/indigo accent, heavy rounded corners, soft blurred shadows, default system sans-serif) — not layout, not chart choice, not color-count. Explicit constraint given: **keep the layout almost entirely as-is, make it "look like an engineer made it."**

**Changes made, all in `ui/templates_str.py`, CSS/typography only — zero HTML structure or JS logic changes:**
- **Typeface**: added IBM Plex Sans (body) + IBM Plex Mono (numbers) via Google Fonts CDN — a typeface family designed for technical/engineering tools specifically, not a generic default stack. Mono applied deliberately only to places numbers matter: KPI tile values, lever readouts, the Sankey total badge, the status timestamp chip, and the custom Chart.js endpoint-callout-label plugin (canvas `ctx.font`). Also set `Chart.defaults.font.family` globally so every chart's axes/legends/tooltips inherit it too.
- **Accent color**: `#4f63d2` (a very recognizable generic "AI SaaS" indigo/purple) → `#2f5d8a` (a muted steel blue), replaced everywhere via `sed` across the file (17 occurrences — buttons, active tabs, links, lever value color, chart series-palette member, delta-chart bar color, Sankey gradient fallback).
- **Border radius**: sharpened broadly — 12/16/20px (soft, consumer-app rounding, including full pill shapes on the status chip and Sankey total badge) down to 3-4px across every card, tab, chip, and button.
- **Removed the two soft blurred `box-shadow`s** (Sankey card, Sankey tooltip) — a classic generic-dashboard tell — replaced with crisp 1px borders, consistent with every other card on the page.

**Verified:** `ast.parse()` confirmed the edited file is still syntactically valid Python (the whole page is one big triple-quoted string, worth checking after a large sed-based edit). Restarted the server (killed the stale port-5050 process first, per the now-standing habit) and visually confirmed via screenshots later in this session that charts render correctly with the new styling.

**Not yet done:** only one tab's worth of visual direction was confirmed before rolling out further (per the plan to check one tab before all nine) — user has not yet explicitly signed off that the new look lands correctly; further design iteration may follow.

### Performance — profiled, root cause identified, no fix applied yet (per user's explicit safety-first instruction)

Confirmed precisely where the ~3.3s `/recalc`/`/set_scenario` delay actually comes from (previously only guessed): **100% inside `evaluator.py`**, not `ui/outputs.py`. `cProfile` showed ~1,700+ unique formula cells being fully re-parsed and re-evaluated from scratch on every single call, because `set_override`/`scoped_overrides` clear the **entire** result cache on any lever change, not just the cells actually downstream of it. The evaluator's recursive-descent design also parses and evaluates a formula in the same pass (no separate compile-once AST step), so every fresh cell pays full tokenizing+parsing cost every time, not just first-cache-miss cost.

**The real fix — partial/dependency-aware cache invalidation instead of clearing everything — was explicitly named as a bigger, higher-risk engine change** and, per the user's own stated priority (safety over speed, no risky rewrites without a proper look first), **was not attempted.** Offered to scope it out as a formal proposal; not yet requested.

### Real bug found and fixed: Electricity Supply chart's "Total" line didn't match its own stacked series

User caught this from a screenshot showing the black Total line diverging sharply from the visible colored stack, and correctly pushed back when an initial "maybe it's just a Chart.js animation-timing screenshot artifact" theory was floated — right instinct, since the theory turned out to be wrong.

**Investigation, in order:**
1. Checked the underlying data via direct `curl` to the live server (bypassing the browser) — confirmed all 9 series' raw numbers were healthy, non-zero, and reasonable (Solar/Wind/Nuclear all rising steadily as expected under an aggressive scenario). Ruled out a backend calculation bug at the data-generation level.
2. Reproduced live via Playwright (the established headless-browser method from earlier in this project) — clean scenario pick via the dropdown, waited for the animation to fully settle, pulled the actual Chart.js instance's internal `data.datasets` directly. **Rendered correctly, no bug, screenshot attached as proof.** This ruled out "just always broken."
3. User then supplied two more screenshots with visible tooltips showing exact numbers, and manually summing the 9 series against the displayed Total revealed a **real, large, reproducible gap** — `1,053 TWh` (~20%) at 2047 under one specific scenario tested. Too large to be rounding or an animation artifact; a genuine data problem.

**Root cause, found in `ui/outputs.py`'s `compute_electricity_supply_chart()`:** the 9 colored series and the black "Total" line were being read from **two independent, unrelated data sources** — the series from each technology's own dedicated sheet (`GENERATION_ROWS`, the fine-grained per-technology data added in the "Full 9-Category Trace" session), the Total from `IESS V3 Results!{col}91` ("Net Electricity Generation"), a separate pre-aggregated row left over from this chart's earlier, coarser 4-bucket version. Nothing forces these two to agree, and under lever-driven scenarios, they don't — this was a real regression introduced when the chart was upgraded to 9 categories without re-checking whether the old Total-row reference still made sense afterward.

**Fix applied:** `total` is now computed as the sum of the 9 series themselves (`sum(series[name][i] for name in series)`), not pulled from row 91 — presented to the user as an explicit choice between two honest options (sum-the-series vs. keep-the-official-row-but-hide-the-breakdown) rather than silently picked; user chose sum-the-series. Guarantees by construction that the chart's own total always exactly equals its own visible stack, for any scenario, forever — verified directly (`6,908.39` sum == `6,908.39` total, to the decimal, post-fix).

**Verified:** re-ran `count_flows.py` — still **78/78, 0 mismatches**, engine untouched, fix confined entirely to `ui/outputs.py`.

### Lesson worth keeping: don't default to "it's probably just an animation/screenshot timing artifact"

This is the second time this project has reached for that explanation. The first time (Chart.js draw-animation timing, Emissions/Supply chart build session) it was genuinely correct. This time it was **not** — the user's persistence in re-checking with concrete tooltip numbers and doing the arithmetic by hand is what actually found the real bug. Going forward: that explanation should only be accepted after actually checking whether the underlying numbers add up, not offered as a first guess to explain away a visual discrepancy.

---

## Session Notes (2026-07-15) — "Critical Minerals" Tab Scaffolded, Emissions "Refineries" Rename Confirmed, New Task Noted, 2070 Extension Explicitly Deferred

### New placeholder tab: "Critical Minerals"

Added as the 9th top-level tab in `ui/templates_str.py` — real, clickable (not the greyed-out "coming soon" disabled style used for tabs before they're built), opens a view showing just the title and "Coming soon" as the subtitle. Required no JS changes since tab-switching (`.tab[data-view]`) is already fully generic — added `"Critical Minerals": "critical-minerals"` to `CLICKABLE_TABS`, `"Critical Minerals"` to `TABS`, and a new `<div class="view" id="view-critical-minerals">` block. This is scaffolding only — no data wired in yet (see new task below).

### Emissions chart: "Other" → "Refineries" rename, confirmed via external reference, not guessed

User compared the dashboard's "Energy-related GHG Emissions" chart against a reference chart from **an older version of the same underlying reference website/data lineage** (not an unrelated tool this time — same source line as the workbook itself, per the user's clarification: "we are using the same data from that website to make the 2047 new and carry forward to 2070 new" — see deferred-scope note below). Two things were checked before concluding anything, given this session's own recent lesson about not assuming a reference chart is comparable without checking its scenario/source first:

1. **The apparent "wrongness" (declining 2047 emissions) was not a bug.** Checked directly: emissions decline is scenario-specific (only under aggressive decarbonization presets like L4 Heroic Effort), not universal — confirmed by inspecting the actual year-by-year shape (rises to a peak around 2032, then declines as renewable buildout takes effect), consistent with already-documented behavior from earlier this session (Electricity's emissions collapsing after 2032 under L4). The reference chart showing a monotonic rise the whole way is presumably a lower-effort/different scenario, not evidence of a compiler bug.
2. **The "Refineries" label genuinely was missing from our chart** — confirmed by reading `ui/outputs.py` directly: `EMISSIONS_SECTOR_GROUPS` bundled rows `[183 "Stress", 184 "Buildings", 191 "Transfer"]` into a generic `"Other"` bucket, with an existing code comment explicitly noting `"Transfer"` was an *unconfirmed* label, deliberately not renamed to "Refineries" without evidence. The user's independent reference-site check supplied that evidence. Verified numerically before renaming: rows 183 and 184 are **both exactly `0`** in every scenario tested, so `"Other"` was already numerically identical to row 191 alone (`22.94` in 2047 under L4) — the rename changes only the label, not any calculation.

**Fix applied:** `EMISSIONS_SECTOR_GROUPS`'s `("Other", [183, 184, 191])` → `("Refineries", [183, 184, 191])` in `ui/outputs.py`, comment rewritten to document the external-confirmation chain. Verified: series keys now show `Refineries` instead of `Other`; total unchanged (`2,025.91` in 2047 under L4, matching the pre-rename value exactly). No other code referenced the old `"Other"` label for this specific chart (checked — the `"Other"` in `levers.py` is an unrelated sidebar-grouping fallback, not touched).

### 2070 extension — explicitly deferred, noted for future planning only

User clarified the reference-website comparison ties into a larger future goal: extending this same model/data lineage from 2047 out to 2070. **Explicitly not being worked on now** — user was clear this needs its own dedicated planning conversation, not folding into ad hoc fixes. Recorded here purely as context for why the reference-website comparison came up, not as an active task.

### New task noted for later: Critical Minerals ↔ Solar capacity linkage

User's actual ask for the new "Critical Minerals" tab, described precisely: **model how critical-mineral requirements scale with renewable energy buildout — specifically, as Solar PV and Solar CSP capacity/generation change (driven by the existing levers), calculate the resulting increase in critical-mineral demand.** Not started — noted here as the concrete scope for whenever this tab gets built for real, so a future session doesn't have to re-derive the ask from scratch.

**Relevant groundwork already in place, confirmed this session (useful starting point for that future work, not yet used for minerals specifically):**
- Solar is already tracked at multiple levels of granularity across the existing dashboard: combined (`Solar` in the All-Energy supply chart, Sankey nodes), combined-generation (`Solar PV + Solar CSP + Distributed Solar PV` in the Electricity Supply chart, from sheets `IV.a`/`IV.b`/`IV.e`), and — most relevantly for a minerals-per-GW calculation — **already split at the fine per-technology level** in the Indicators tab's Installed Capacity chart: `Solar PV` (row 76) and `Solar CSP` (row 77) as fully separate capacity series (GW), each individually lever-reactive.
- What's still missing for the actual Critical Minerals feature (not yet sourced or built): a mineral-intensity factor (e.g. tonnes of lithium/silver/copper/etc. per GW of Solar PV vs. Solar CSP capacity — these two technologies have very different mineral profiles) — this data does not appear to exist anywhere in the current `IESS2047_Version_3.0.xlsx` workbook and would need to come from an external source (the reference website mentioned, or another dataset), same "trace to a real source, never invent numbers" rule as every other chart built this project.

---

## Session Notes (2026-07-20) — EUCALC-Style Visual Redesign (CSS/Markup Only, No Data/Tab Changes)

User supplied a reference screenshot of the EUCALC ("European Calculator") tool's UI — dark top navbar with logo, a light sidebar with a "Pathway" dropdown and category rows each showing 4 progress dots, a horizontal underline-style tab bar, chart cards with a title+dropdown-caret header and a small "≡" menu glyph, and stacked-area charts using solid, muted/desaturated colors with a bottom dot-legend — and asked for the dashboard (`ui/`) to look "exactly this way," explicit constraint: **do not change the existing tabs or how data is displayed, styling only.**

### What changed — all in `ui/templates_str.py`, CSS/markup only, zero JS logic or data-flow changes

- **New dark top navbar** (`.navbar`, `#23262e` background, 46px tall): brand logo + title moved out of the sidebar into this new full-width bar, with a decorative hamburger icon at the right (non-functional, purely chrome, matching the reference).
- **Sidebar** (`.sidebar`): background lightened to `#f6f7f9`; added a "PATHWAY" label + "Choose example pathway for India:" subtitle above the existing scenario `<select>` (was previously unlabeled). Group headers (`details.group summary`) restyled uppercase/bold with a hairline top border between groups instead of hover-highlight blocks. **Level-boxes changed from rounded-square (`border-radius:4px`) to circles (`border-radius:50%`)** to match the reference's dot-style level indicators — this is the one visual element close to a functional control, so note it stayed **fully wired to the same click handlers**, only the shape changed.
- **Card headers**: added a small CSS-only dropdown caret (`.card h3::after`, a CSS border-triangle, not a Unicode glyph — see gotcha below) and a decorative "≡" icon top-right of every chart card (`.card::before`), mimicking the reference's per-chart menu affordance. Both are inert (no click handler) — purely cosmetic, matching the "classy engineering tool" chrome without adding new interactive scope the user didn't ask for.
- **Tabs / sub-tabs / Sankey year-tabs**: changed from filled "pill" buttons (`background + border-radius`) to flat underline-style active states (`border-bottom: 2px solid`, transparent otherwise) — the same pattern already used successfully in the earlier "looks AI-generated" design pass (2026-07-15), just extended further.
- **Border-radius flattened further** (already mostly flat from the 07-15 pass): KPI tiles and chart cards now sit inside a shared hairline grid (`1px` gap on a `#d9dce6` background, giving a thin shared border between adjacent tiles/cards) instead of individually-bordered rounded boxes.
- **Chart color palette swapped** (`COLORS` array in the page's inline `<script>`): from a bright/saturated palette (`#d2691e`, `#7b3f9e`, `#e53935`, etc.) to a muted/desaturated one (`#6f95b8`, `#8f8fc7`, `#7fae65`, `#c97a6d`, `#d1a35c`, etc.) modeled on the reference chart's soft blue/green/tan bands. Stacked-area fills changed from semi-transparent (`colorFor(i) + "cc"`) to **solid** fill, matching the reference's flat, non-gradient area bands.

### A real gotcha hit and fixed: Unicode glyphs in CSS `content:` silently rendered as tofu boxes

First pass used `content: "\25be"` (▾) for the card-header caret and `content: "\2261"` (≡) for the card menu icon. Both rendered as broken-glyph boxes in the live screenshot — **IBM Plex Sans (this page's body font) doesn't cover those Unicode codepoints**, and since `content` pseudo-elements inherit the element's `font-family` by default, there was no automatic fallback to a font that does. **Fix:** the dropdown caret was rewritten as a **pure CSS border-triangle** (`border-left/right: 4px solid transparent; border-top: 5px solid <color>`) — no font dependency at all, the most robust option. The "≡" menu icon was kept as a Unicode glyph but pinned to `font-family: Arial, sans-serif` explicitly on that one pseudo-element, since Arial reliably covers it. **Lesson for any future icon-via-`content` work on this page:** don't assume the page's primary webfont covers a symbol glyph — either pin an explicit fallback font on that pseudo-element, or avoid the font dependency entirely with a CSS-shape trick.

### Verified

- Killed the stale `ui/app.py` process on port 5050 (per this project's standing "check `netstat -ano | grep <port>` before assuming code changes aren't taking effect" rule — recurred here too, consistent with every prior occurrence) and restarted with `python -u app.py` before testing.
- Playwright screenshots of the **All Energy** tab (KPI row, demand/supply stacked-area charts, sidebar with dot-level selectors) and the **Energy Flows** (Sankey) tab, both fully data-populated under the L4 preset — confirmed visually: dark navbar, flat underline tabs, circular level dots, muted chart palette, hairline card grid, all levers/tabs/charts still fully functional (scenario dropdown, per-subcategory dot clicks, tab switching, Sankey year buttons all exercised).
- No engine or `ui/outputs.py`/`ui/app.py` changes at all this session — pure `ui/templates_str.py` CSS/markup edit, so no need to re-run `count_flows.py` (nothing that affects computed values changed).

---

## DONE (2026-07-21) — Split ui/ frontend into per-feature Python files + real static CSS/JS

Executed the plan below on 2026-07-21, same session it was approved and queued in. Migration completed exactly as planned, single atomic cutover, verified with zero behavior change (see "Verification, actually run" at the end of this section).

### What actually changed vs. the plan

Matches the plan below 1:1 — no deviations. Final file list:
- `ui/static/css/dashboard.css` — verbatim copy of the old `<style>` block.
- `ui/static/js/dashboard.js` — verbatim copy of the old `<script>` body, with `const ids = __IDS_JSON__;` → `const ids = window.APP_CONFIG.leverIds;` and `let currentSankeyYear = "__DEFAULT_SANKEY_YEAR__";` → `let currentSankeyYear = window.APP_CONFIG.defaultSankeyYear;`.
- `ui/pages/__init__.py` (empty), `sidebar.py` (`render_sidebar_html`/`_subcat_label`), `tabs.py` (`render_tabs_html`/`render_year_buttons_html`/`TABS`/`CLICKABLE_TABS`/`ACTIVE_TAB`).
- `ui/pages/{all_energy,electricity,energy_security,emissions,indicators,costs,energy_flows,land_water,critical_minerals}.py` — each a `render() -> str` returning that tab's `<div class="view">` block verbatim.
- `ui/pages/base.py` — `render_base()`, the outer shell with `<link rel="stylesheet" href="/static/css/dashboard.css">`, `__SIDEBAR_HTML__`/`__TABS_HTML__`/`__PAGES_HTML__` placeholders, the `window.APP_CONFIG = {...}` bootstrap block, and `<script src="/static/js/dashboard.js">`.
- `ui/app.py` — `/` route now does `pages_html = "".join(m.render() for m in PAGE_MODULES)` then the same `str.replace()` token substitution pattern as before, just pulling each piece from its own module. `/set_scenario`/`/recalc` untouched.
- `ui/templates_str.py` deleted (confirmed zero remaining importers repo-wide via grep before deleting).

### Verification, actually run

- No stale port-5050 listener found this time (`netstat -ano | grep 5050` clean before starting) — the recurring Windows multi-bind bug didn't strike this round, but the check was still done first per standing practice.
- `curl /` → 200, no leftover `__TOKEN__` placeholders anywhere in the served HTML (grepped for `__[A-Z_]*__` — zero matches).
- `curl /static/css/dashboard.css` → 200, `Content-Type: text/css`. `curl /static/js/dashboard.js` → 200, `Content-Type: text/javascript`.
- `POST /set_scenario {"level":4}` → KPIs `total_demand=1074.24, total_supply=1524.07, per_capita_demand=28251, import_dependence=15.1` — exact match to the L4 numbers already verified in the 2026-07-20 visual-redesign session (proves `/set_scenario`'s logic, including the `scoped_levers()`/Bug 4 fix, is untouched).
- Playwright: zero console/page errors on load. Screenshots of **All Energy** (pixel-identical to the pre-migration 07-20 screenshot), **Energy Flows** (Sankey renders, year-tabs work, tooltips wired), and **Indicators → Electricity Indicators** (sub-tab click switches correctly, both charts render) — all confirmed fully functional.
- Engine/`levers.py`/`outputs.py` untouched, so no `count_flows.py` re-run needed — nothing that affects computed values changed, only how the HTML/CSS/JS get assembled and served.

### Original plan text (for reference — already executed, kept for historical record)

### Context / why

The `ui/` Flask dashboard currently serves its entire frontend — every tab's HTML, all CSS, all JS — as one ~1150-line Python triple-quoted string (`PAGE_TEMPLATE` in `ui/templates_str.py`), assembled by `ui/app.py`'s `/` route via plain `str.replace()` token substitution (chosen originally to dodge a real bug where old `%`-style Python formatting collided with literal `%` in the CSS, e.g. `width: 100%`).

User wants two things, **explicitly not a Jinja/template-engine migration** (asked directly "why cant direct css or anything" and, when a Jinja-based plan was first drafted, corrected it: "we dont necessirily need jinja template... Necessarily not jinja"):
1. **Collaboration-friendly structure** — a base file, a sidebar file, and one file per tab/feature (e.g. someone owns the Sankey/Energy Flows file, someone else owns a different chart's file), each returning an HTML string the same way the code does today — just split apart so different engineers can work on different files without colliding in one 1150-line blob.
2. **Real `.css`/`.js` files** instead of CSS/JS embedded as Python string literals — doesn't need any templating engine at all; Flask serves a `static/` folder's files automatically regardless of how the HTML is built.

Pure reorganization — identical rendered HTML/CSS/JS behavior, identical tabs, identical lever wiring, identical chart rendering. **Not a performance fix** — the documented slowness (`evaluator.py`'s full-cache-clear per lever change, see 2026-07-15 session note above) is separate and explicitly out of scope; this was communicated to the user before drafting the plan so it isn't mistaken for a speed improvement later.

### Approach: plain Python functions returning HTML strings, one file per feature + real static assets (no Jinja)

Keep exactly the pattern already in use (`def render_x(): return f"""...HTML..."""`, assembled via `str.replace()`/f-string concatenation) — just split `templates_str.py` into many small, independently-ownable files instead of one big one.

**Layout:**
```
ui/
  app.py                      # route logic — assembles the page from the pieces below
  levers.py                   # unchanged
  outputs.py                  # unchanged
  static/
    css/dashboard.css         # entire current <style> block, verbatim, real file
    js/dashboard.js           # entire current inline <script> body, verbatim
  pages/
    base.py                   # render_base() -> full <html> shell with __TOKEN__ placeholders
    sidebar.py                # render_sidebar_html(sidebar_groups) -- moved as-is
    tabs.py                   # render_tabs_html(), render_year_buttons_html(), TABS/CLICKABLE_TABS/ACTIVE_TAB
    all_energy.py             # render() -> str
    electricity.py            # render() -> str
    energy_security.py        # render() -> str
    emissions.py               # render() -> str
    indicators.py              # render() -> str (keeps its 3 inline subtabs/subviews)
    costs.py                   # render() -> str (keeps its 2 inline subtabs/subviews)
    energy_flows.py            # render() -> str -- the Sankey tab, independently ownable
    land_water.py               # render() -> str
    critical_minerals.py        # render() -> str ("coming soon" stub)
    __init__.py                 # empty, just makes it a package
```

Each `pages/<tab>.py` is self-contained: one engineer edits `energy_flows.py` without touching `all_energy.py`. Public surface is just `render() -> str` (or the existing `render_sidebar_html(groups)`/`render_tabs_html()` signatures) — no shared mutable state between page files. Adding a 10th tab later = one new file + one line in `PAGE_MODULES`, no editing existing files.

`app.py`'s `/` route becomes:
```python
from pages.base import render_base
from pages.sidebar import render_sidebar_html
from pages.tabs import render_tabs_html, render_year_buttons_html
from pages import all_energy, electricity, energy_security, emissions, indicators, \
    costs, energy_flows, land_water, critical_minerals

PAGE_MODULES = [all_energy, electricity, energy_security, emissions, indicators,
                costs, energy_flows, land_water, critical_minerals]

@app.route("/")
def index():
    pages_html = "".join(m.render() for m in PAGE_MODULES)
    html = render_base()
    html = html.replace("__SIDEBAR_HTML__", render_sidebar_html(SIDEBAR_GROUPS))
    html = html.replace("__TABS_HTML__", render_tabs_html())
    html = html.replace("__PAGES_HTML__", pages_html)
    html = html.replace("__YEAR_BUTTONS_HTML__", render_year_buttons_html())
    html = html.replace("__DEFAULT_SANKEY_YEAR__", CHART_YEAR_LABELS[-1])
    html = html.replace("__IDS_JSON__", json.dumps(list(ALL_LEVER_ROWS.keys())))
    return html
```

**CSS/JS as real static files:** `ui/static/css/dashboard.css` is the current `<style>` block's contents, verbatim, in a real file — a CSS engineer edits it directly with real syntax highlighting, no Python involved. `ui/static/js/dashboard.js` is the current inline `<script>` body, verbatim, kept as **one shared file** (not split per page/chart) since it has cross-cutting module state (`charts`, `sankeyDataByYear`, `baseline`, `recalcTimer`) that a chart-by-chart split would risk breaking for no real benefit — a chart-owning engineer still only touches the one `renderXChart()` function relevant to them inside this one file. The two spots currently done via Python `.replace()` inside the script text (`const ids = __IDS_JSON__;` and `let currentSankeyYear = "__DEFAULT_SANKEY_YEAR__";`) move to a tiny inline bootstrap block still emitted by `base.py`:
```html
<script>
  window.APP_CONFIG = { leverIds: __IDS_JSON__, defaultSankeyYear: "__DEFAULT_SANKEY_YEAR__" };
</script>
<script src="/static/js/dashboard.js"></script>
```
`dashboard.js` reads `window.APP_CONFIG.leverIds`/`window.APP_CONFIG.defaultSankeyYear` instead of the two hardcoded lines. Flask serves `/static/css/...`/`/static/js/...` automatically (`Flask(__name__)`'s default `static_folder="static"`, confirmed unmodified) — no new route code needed.

### File changes

**New:** `ui/pages/base.py`, `sidebar.py`, `tabs.py`, `__init__.py`, the 9 `pages/<tab>.py` files, `ui/static/css/dashboard.css`, `ui/static/js/dashboard.js`.
**Removed:** `ui/templates_str.py` (once nothing imports from it).
**Edited:** `ui/app.py` only — swap the `templates_str` import for the per-module imports, rewrite the `/` route as above. `/set_scenario`/`/recalc` untouched (pure JSON routes). No changes to `ui/levers.py`, `ui/outputs.py`, or `xlcompiler/compiler/`.

### Migration sequence (single atomic cutover — the current template is too interlinked for a safe partial state)

1. Copy `<style>` block verbatim → `ui/static/css/dashboard.css`.
2. Copy `<script>` body verbatim → `ui/static/js/dashboard.js`; apply only the `APP_CONFIG` read swap (minimal diff, not a rewrite).
3. Create `ui/pages/__init__.py`, `sidebar.py` (port `render_sidebar_html`/`_subcat_label` verbatim), `tabs.py` (port `render_tabs_html`/`render_year_buttons_html`/`TABS`/`CLICKABLE_TABS`/`ACTIVE_TAB` verbatim).
4. Create the 9 `pages/<tab>.py` files, each `render()` body = that tab's current `<div class="view" ...>...</div>` block, copied verbatim.
5. Create `pages/base.py` — outer HTML skeleton (doctype/head with CSS `<link>` in place of the old inline `<style>`, navbar, `.app`/`.sidebar`/`.main` shell with the placeholders, CDN script tags, `APP_CONFIG` bootstrap block, `dashboard.js` `<script src>` tag).
6. Edit `ui/app.py` per above.
7. Delete `ui/templates_str.py` (confirm no remaining importers repo-wide first).
8. Run the app and do the verification pass below.

### Verification plan

- **Standing project bug, check first:** `netstat -ano | grep 5050` (or PowerShell `Get-NetTCPConnection`) and kill any stale listener before launching — recurred every single time a server-restart was needed in this project so far.
- Curl `/` pre- and post-migration and diff — should match except the intentional shift from inline `<style>`/`<script>` to `<link>`/`<script src>` tags; bytes served from `/static/css/dashboard.css` and `/static/js/dashboard.js` should equal what was inline before.
- Confirm `/static/css/dashboard.css` and `/static/js/dashboard.js` return 200 with correct `Content-Type`.
- POST sample payloads to `/set_scenario` and `/recalc` — confirm JSON responses byte-identical to pre-migration (pure regression check, these routes aren't touched).
- Playwright: screenshot all 9 tabs pre/post for pixel parity; click through tab switching, Indicators' 3 subtabs, Costs' 2 subtabs, a lever slider drag (confirm `scheduleRecalc`/`recalc` fires and charts update), a scenario dropdown pick, Energy Flows year-buttons + Sankey hover tooltips, subcat level-of-ambition circle clicks.
- Devtools console/network: `dashboard.css`/`dashboard.js` load 200 (not 404), no console errors (in particular no `APP_CONFIG is not defined`, which would mean script tag ordering is wrong).

### Critical files
`ui/app.py`, `ui/templates_str.py` (source to port from, then delete), `ui/levers.py`, `ui/outputs.py`.

---

## DONE (2026-07-22) — Safe backend speedup: formula-token cache, plus profiling of what's left

Approved 2026-07-21, executed 2026-07-22 exactly as planned below — no deviations.

### Context / why

User asked to optimize backend calculation/rendering speed. Graph rendering is client-side Chart.js and already fast — the real cost is server-side calculation. The existing documented bottleneck (2026-07-15 session note above) is `evaluator.py`'s `set_override()` doing a full `self._cache.clear()` on every lever change, forcing ~1,700+ formula cells to be fully re-tokenized and re-evaluated (~3.3s/lever change, 100% inside `evaluator.py` per cProfile).

**A dependency-graph/partial-invalidation fix was designed, stress-tested (two rounds — an Explore pass reading the entire evaluator, then a Plan-agent correctness stress-test of the specific design), and then explicitly rejected** based on direct user feedback during this planning session:
1. **This project has already been burned once by a partial-cache-invalidation bug — not written down anywhere in this file, but a real incident the user recalls directly.** The full `cache.clear()` on every override exists specifically *because* of that past failure, not as an arbitrary simplicity choice as the code comments (`engine.py`/`evaluator.py`) might suggest to a future reader. **This is important standing context for any future engine work: do not assume the full-clear design is naive or "obviously" improvable — it is a deliberate scar from a real prior bug.**
2. The workbook's energy-balance formulas are genuinely, deeply interconnected — a lever change legitimately cascades through most of the formula graph via the model's own supply=demand accounting identities (this is domain knowledge from the user, not derived from code). That means a "targeted" invalidation set would likely end up close to the full ~1,700 cells anyway for most levers, eroding most of the theoretical win while reintroducing the exact class of risk that already burned this project once.

Given both points, the approved plan does **not** touch cache-invalidation semantics at all. `set_override`, `clear_overrides`, `scoped_overrides` stay exactly as they are today — full `self._cache.clear()` on every override, unchanged. No new dependency graph, no partial cache eviction, nothing that could reintroduce the earlier failure mode.

### The fix: cache the tokenizer output, not the evaluated values

Confirmed by reading `evaluator.py:148-207` directly:
- `_eval_formula(formula, sheet, row, col)` (148-153) does `tokens = self._tokenize(expr)` **every single time a formula cell is evaluated** — even though `_tokenize` is a pure, deterministic function of the formula *text* alone (a regex-based lexer, `evaluator.py:156-188`), completely independent of `sheet`/`row`/`col`/overrides/lever state. The same formula text produces byte-identical tokens every time, regardless of what any lever is currently set to.
- `_peek`/`_next` (200-206) only ever *read* the `tokens` list by index (`tokens[pos[0]]`) — they never mutate it. The mutable cursor is the separate `pos = [0]` list, created fresh per call. This means a single cached `tokens` list object can be safely shared and re-read across many different evaluations of the same formula text — there is no hidden mutation to worry about.
- Since `_eval_formula` re-tokenizes from scratch on every `eval_cell` cache miss, and a full cache clear happens on every lever change, every one of the ~1,700 affected cells' formula text gets re-lexed from raw characters on every single lever drag, even though the vast majority of those formula *strings* are byte-for-byte identical to what was just lexed a moment ago (before the clear). This work is 100% redundant and can be eliminated with zero change to *what gets evaluated or when* — only *how the raw text gets turned into tokens* is cached.

**Change (confined to `evaluator.py`), add to `Evaluator.__init__`:**
```python
self._token_cache = {}   # formula text (post "=" strip) -> tokens list, pure/deterministic
```

**Change `_eval_formula`:**
```python
def _eval_formula(self, formula, sheet, row, col):
    expr = formula[1:] if formula.startswith("=") else formula
    tokens = self._token_cache.get(expr)
    if tokens is None:
        tokens = self._tokenize(expr)
        self._token_cache[expr] = tokens
    pos = [0]
    val = self._parse_expr(tokens, pos, sheet, row, col)
    return self._scalar(val)
```

That's the entire change. `self._token_cache` is **never cleared** by `set_override`/`clear_overrides`/`scoped_overrides` — it must not be, and this is safe *by construction*: it maps immutable formula text to its lexical tokens, a fact that never changes for the lifetime of a loaded workbook (formula text itself never changes at runtime; only override *values* do, and this cache never stores anything override- or value-dependent). There is no analogue here to the old bug's mechanism — nothing about this cache carries a computed *value* forward across a lever change; it only remembers how to split a string into token pieces.

### Why this is safe (explicitly addressing the concern the user raised)

- **No invalidation logic exists to get wrong.** The previous partial-invalidation design required correctly tracking *when* a cached value becomes stale relative to changing override values — that's exactly the kind of logic that (per the user's recollection) went wrong before. This design has no such logic: the token cache is keyed on formula text, which is static, so there is no "when does this become stale" question to answer incorrectly. It's a pure memoization of a pure function, with no dependency on evaluation order, override state, or lever values whatsoever.
- **The full value-cache clear behavior is completely untouched** — `self._cache.clear()` still runs in full on every `set_override`/`clear_overrides`/`scoped_overrides` exit, exactly as today. Every formula cell's *value* is still always fully recomputed after any lever change, with zero shortcuts. Only the *lexing* step is skipped on repeat.
- **Formula text identity across the workbook is common** — many cells share byte-identical formula templates (e.g. the same interpolation/trend formula copied across year columns, or across similar rows in a table), so the cache hit rate should be meaningfully high even on a workbook this size, without needing per-cell dependency reasoning of any kind.

### Expected impact (honest framing, not overpromising)

This targets only the tokenization/lexing cost, not the recursive-descent parse-and-evaluate cost itself (which is interleaved in one pass in this evaluator's design — a real AST/compile-once step would be a much larger, separate, higher-risk restructuring, not proposed here). The realistic expectation is a **moderate** reduction in per-recompute time, not an elimination of the ~3.3s cost — the interpretation work (recursive function dispatch, dict/list operations, string handling per node) likely remains the dominant cost and is unaffected by this change. This should be measured, not assumed, and reported honestly once real numbers are in hand.

### Verification plan

**Correctness (must be trivially true, but confirm anyway given engine-change discipline):**
- Re-run `count_flows.py` from a fully cache-cleared reparse — must still show **78/78, 0 mismatches**. Since this change cannot alter *what* any formula evaluates to (same tokens in, same parse/eval behavior, same result), this is a sanity check rather than a real risk, but it's free to run and this project's standing rule is to always verify after any `evaluator.py` touch.
- Directly assert `self._token_cache[expr]` byte-equals a fresh `self._tokenize(expr)` call for a sample of formulas, to catch any accidental aliasing/mutation bug in case `tokens` is ever touched by future code that assumes a fresh list per call.

**Performance (measure, don't assume):**
- Reuse the existing profiling methodology (same machine, warm/cold state, averaged over N runs) so before/after numbers are directly comparable to the already-documented 3.3s baseline.
- Instrument (temporarily) a token-cache hit/miss counter to see the actual hit rate on this specific workbook — this tells us empirically whether formula-text repetition is as common as expected, rather than assuming it.
- Report the real before/after wall-clock numbers for a `/recalc` call plainly, including if the improvement turns out to be small — no overstating the win.

### Critical files
`xlcompiler/compiler/evaluator.py` (only `__init__` and `_eval_formula` change; `set_override`/`clear_overrides`/`scoped_overrides`/`eval_cell` — the actual value-caching and invalidation logic — are **not modified at all**).

### Results, actually measured

- Implemented exactly as specified above — `self._token_cache = {}` added to `Evaluator.__init__`, `_eval_formula` changed to consult/populate it instead of unconditionally calling `self._tokenize(expr)`. Nothing else in `evaluator.py` touched.
- **Correctness**: `count_flows.py` → still **78/78, 0 mismatches**. Token cache confirmed stable (no growth) across repeated lever drags in a session — `len(eng.ev._token_cache)` held flat (~16k-23k entries depending on test) across 8 consecutive simulated drags, confirming it populates once and never leaks/grows unboundedly.
- **Performance, measured with the exact real `/recalc` pattern** (resending all 51 levers every call + force `E12=0`, matching what `dashboard.js` actually does): steady-state repeated drags went from the documented **~3.3s baseline → ~2.6s** (averaged over 8 consecutive drags, excluding the first/cold one). A real, modest win (~20%), honestly in line with what was predicted — this only removed the redundant re-lexing cost, not the dominant interpretation/dispatch cost.

### Follow-up profiling: where the remaining ~2.6s actually goes (measured, not guessed)

Ran `cProfile` over 2 back-to-back realistic `/recalc` calls (all-51-levers-resent pattern) post-token-cache-fix. Findings:
- **`_fn_sumifs` alone accounts for ~40% of total evaluator time** — only ~7,600 calls, but each does a full row-range scan with per-cell `.strip().lower()` string-normalize comparisons to match criteria (`evaluator.py:821-835`).
- **One single chart — `compute_emissions_by_sector_chart` (`ui/outputs.py:488-500`) — is responsible for ~41% of the entire recalc's time by itself**, far more than any other chart. It reads 8 sector-group row sums × 6 year columns from the `'Intermediate output'` sheet, each of which appears to resolve through `SUMIFS`-style range formulas upstream in the workbook.
- `_flatten_nums` (the shared range-walking helper behind SUM/SUMIF/SUMIFS/AVERAGE/etc.) shows up throughout, as expected given the above.

**Next possible optimization identified but NOT started, NOT approved**: if the criteria columns that `SUMIFS` matches against (e.g. a sector-label column) are static data cells that never themselves change value when any lever moves, it would be safe to cache "which rows match this criteria" instead of re-scanning and re-normalizing strings on every call. This is explicitly **not yet verified** — whether those criteria columns are lever-invariant needs to be checked (read-only) before proposing this, per the same "safety over speed" discipline as the last fix. **Do not implement this without that verification and without going through the same plan/approval process as the token-cache fix** — this is a new, not-yet-reviewed change to a hot path, not an extension of anything already approved.

---

## RESOLVED (2026-07-22) — Where "2,201.98" comes from, and the E10/E12 mode-switch mismatch that caused external confusion

A pasted external report (from a different investigation, not from this project's own tooling) claimed toggling `'IESS V3 Main Sheet'!E12` to 1 ("Least Effort" preset) in Excel only moved Total Energy Demand 2047 from 1,368.92 → 1,372.39 Mtoe — "nowhere near" the 2,201.98 figure this project's own history (2026-07-13 session, documented above) had previously produced, and asked where 2,201.98 actually came from.

### Root cause of the external report's confusion: the `E10` mode-switch was very likely left at its default

Reproduced directly against the live engine (`ui/outputs.py`'s `compute_outputs()`, KPI formulas confirmed to be simple sums over `read_flows()` edges — no accumulation/state-carrying bug in the KPI code itself):

| Config | E10 | E12 | Total Demand 2047 |
|---|---|---|---|
| Workbook's saved default | 2 | 2 | 1,369.98 |
| **E10 left at default, E12→1** | **2** | **1** | **1,370.85** ← barely moves |
| Correct lever-driven mode, Preset L1 | **1** | 1 | **1,880.65** |
| Correct lever-driven mode, Preset L2 | 1 | 2 | 1,449.22 |
| Correct lever-driven mode, Preset L3 | 1 | 3 | 1,225.04 |
| Correct lever-driven mode, Preset L4 | 1 | 4 | 1,074.24 |

Leaving `'Target Year Input'!E10` at its saved default of `2` ("direct numeric entry" mode) while only toggling `E12` reproduces almost exactly the external report's near-null result (1,370.85 vs. their 1,372.39 — same order of magnitude, same near-no-op shift). This strongly confirms the external check never set `E10=1` first — both mode-switches (`E10=1` AND `E12`) are required together for Control-sheet levers/presets to have any real effect, a rule already documented in this file's "Custom Lever / Scenario Verification" section from much earlier in the project. With both set correctly, the engine reproduces **1,880.65** — matching this project's own previously live-Excel-verified L1 figure exactly.

### Where 2,201.98 actually comes from — reproduced live, directly

| Configuration | Total Demand 2047 |
|---|---|
| Preset L1 alone (`E12=1`, sliders left untouched) | **1,880.65** |
| Preset L1 **+ all 51 Control-sheet levers also manually forced to 1** | **2,201.98** |
| Custom mode (`E12=0`) with all 51 levers forced to 1 (no preset active at all) | **2,201.98** |

The third row is the proof: **2,201.98 is identical whether or not a preset is even active** — it depends only on where the 51 sliders themselves sit. So 2,201.98 was never a "Preset L1" number; it's the result of manually forcing every Control-sheet lever to 1 (the "Custom Pathway, all sliders at 1" state), which is a different action from picking "Least Effort" from the scenario dropdown.

**Why these differ, and why that's correct, not a bug** (also already documented earlier in this file under Bug 2/the L1 gap investigation, re-confirmed here): picking a preset overrides each module's effective level via a formula like `=IF(predefined.scenario=1,1,IF(predefined.scenario=2,2,...))` for 46 of the 51 levers — this **bypasses** the physical slider value entirely for those 46. But **5 levers have no such override formula anywhere in the workbook** (GDP Growth + the 4 Cost levers) — they always read the raw slider value regardless of preset, by the original Excel author's own design (confirmed in the workbook's own documentation cell). So Preset L1 = 46 gated levers forced to 1 + those 5 ungated levers left wherever they happened to be sitting; all-51-forced-to-1 = literally every lever, including those 5, actually at 1. Since GDP Growth is one of the largest single drivers of total demand in this model, that alone explains most of the ~321 Mtoe gap between 1,880.65 and 2,201.98.

**Conclusion for future reference**: "Preset scenario" and "manually dragging every slider to that scenario's nominal level" are two genuinely different calculation paths in this workbook, not two ways of asking the same question — it would actually be a red flag if they produced identical numbers, since that would mean the preset-override formulas weren't doing anything. No engine or dashboard bug involved in any of this.

---

## Session Notes (2026-07-23) — Preset-as-editable-starting-point Request (flagged, deferred, NOT implemented), KPI Row Removed, "Insights" Placeholder Added

### Request considered and explicitly NOT implemented yet: presets as a live, editable starting point

User asked for a real UX change: picking a preset (e.g. L2) should visibly snap all 51 sliders to L2's actual values, and from there, dragging any single lever (e.g. a Renewables lever) should recalculate "L2 with that one lever changed" — everything else staying at L2's values, Sankey included.

**Flagged before touching anything**: this is exactly the "Bug 2" fix from the 2026-07-13 session above — already implemented once, already reverted, because it broke the dashboard's Preset-mode number matching Excel's own real Preset output (moved Preset L1 from the Excel-verified-correct 1,880.65 to 2,201.98). The two are fundamentally different calculation paths in the workbook itself:
- **Real Excel preset behavior**: `E12=N` overrides 46 of 51 levers' *effective value* via `=IF(predefined.scenario=N,N,...)`-style formulas, entirely bypassing whatever the physical slider shows. 5 levers (GDP Growth + 4 Cost levers) have no such override and always read the raw slider.
- **What the user is asking for**: snap all 51 sliders to that preset's reference-column values (N/O/P/Q, per-level columns already identified in this project) and switch to Custom-lever calculation for everything from then on.

Doing the second thing necessarily means the dashboard's displayed "Preset L2" total will **stop being bit-for-bit identical to Excel's real Preset L2 total** — because Excel's real preset never touches the 5 ungated levers, but a "snap all sliders + switch to custom" approach would. This trade-off was explained to the user directly (interactivity vs. exact Excel-match for preset totals) and **the user has not yet made a final call** — this session moved on to a different request (KPI removal, below) before resolving it. **Do not implement the preset-snap approach without an explicit decision from the user on this trade-off, and go through the same plan/approval process as the token-cache fix, given this is the second time this exact idea has come up.**

### KPI row removed from the All Energy tab, replaced with an "Insights — Coming soon" placeholder

User's reasoning, verbatim in spirit: the 4 KPI tiles (Total Demand, Total Supply, Per Capita Demand, Import Dependence) are exactly the numbers implicated in the Preset-vs-manual-lever confusion documented above — they read as one authoritative headline figure, but the workbook genuinely supports two different, both-"correct" calculations depending on how you got there (preset-gated vs. every-lever-set-by-hand). User's call: rather than publish a number that can be honestly challenged ("why does this not match Excel's preset number"), remove the KPIs entirely until there's an unambiguous way to present them, and use the freed space for a labeled placeholder instead.

**What changed:**
- `ui/pages/all_energy.py`: removed the `.kpi-row` block (4 tiles) entirely. Replaced with a `.card` containing an "Insights" heading, "Coming soon" sub-label, and the existing `.coming-soon-note` placeholder style (same pattern already used for the Critical Minerals tab) — so the tab isn't left with a blank gap. Module docstring updated to explain why, for a future reader.
- `ui/static/js/dashboard.js`: removed `renderKpis()` (the function) and its call site inside `applyResult()` — since the DOM elements it targeted (`v-total_demand` etc.) no longer exist, leaving the call in would have thrown a null-reference error on every recalc.
- **Backend untouched deliberately**: `ui/outputs.py`'s `compute_outputs()` still computes and returns `kpis` in the JSON payload (used internally by `diff_outputs`/baseline-comparison logic) — only the frontend display and its DOM-touching JS were removed. No engine or calculation change.

**Verified**: killed 2 stale port-5050 listeners (recurring project bug, same as every prior restart), fresh `python -u app.py` start, Playwright screenshot confirmed the Insights placeholder renders correctly where the KPI row used to be, zero console/page errors. Re-ran `count_flows.py` — still **78/78, 0 mismatches** (expected, pure UI change, engine/outputs.py computation logic untouched).

### Aside: explained (not changed) — why `compute_electricity_supply_chart`'s Total line is computed as a sum of its own series, not read from a workbook row

User asked for a plain explanation of the existing code comment at `ui/outputs.py:650-657`. No code change — this was already-existing, already-correct code from the 2026-07-15 session (documented above under "Real bug found and fixed: Electricity Supply chart's 'Total' line didn't match its own stacked series"). Explained for the user: the workbook has two different, both real, Excel-computed "total electricity supply" numbers (the 9 individual technology sheets summed, vs. a separate pre-aggregated `'IESS V3 Results'` row 91) that can diverge under lever-driven scenarios by ~20%. The chart deliberately sums its own 9 visible series for the Total line rather than reading row 91, guaranteeing the black total line always matches its own stack, by construction, for any scenario.

---

## Session Notes (2026-07-23, cont'd) — Dashboard Default Changed to L1, Land/Water Chart Number Formatting Fixed, Recurring Duplicate-Port Bug Diagnosed Again

### Dashboard default changed from L4 to L1

User's complaint: the dashboard always opened on "Determined Effort — L4" with every lever slider showing 4 — "that is not the correct way to project" (i.e. L4/Heroic Effort as a default gives a misleadingly aggressive first impression, not a neutral starting point).

**Fix**: `ui/pages/base.py`'s scenario `<select>` — moved the `selected` HTML attribute from the `value="4"` option to `value="1"`. That's the entire change; `dashboard.js`'s existing `setScenario(document.getElementById("scenario").value)` call (already runs once on every page load) automatically picks up whichever option is marked `selected`, so no JS logic change was needed — it now POSTs `/set_scenario {level:1}` on load instead of `{level:4}`, which snaps every slider to 1 and computes L1's numbers by default.

**Verified**: Playwright screenshot confirmed "Determined Effort — L1" selected and every sidebar lever's level-1 dot filled on fresh page load; `count_flows.py` still 78/78 (pure frontend default-value change, no engine/data-path touched).

### Land Use / Water Use charts: fixed unreadable decimal display, now show real numbers with k/M/B/T suffixes

User compared our Land Use chart against a reference chart and asked why ours showed tiny decimals (e.g. `0.804`) while the reference showed large, readable numbers (e.g. `1.08745M`). **Not a data/calculation bug** — both were representing the same underlying magnitude, just formatted differently: our chart pre-divided into "Million Hectares"/"Billion Litres" units (so 804,000 hectares displayed as `0.804`), while the reference displays raw hectares/litres with a compact k/M/B suffix.

**Fix, all display-only, no engine/value change:**
- `ui/outputs.py`: `compute_land_use_chart`/`compute_water_use_chart` now multiply the sheet's raw (pre-scaled) values back up by `LAND_USE_SCALE = 1_000_000` and `WATER_USE_SCALE = 1_000_000_000` respectively, so the chart data is now in plain hectares/litres instead of millions/billions-of-hectares/litres.
- `ui/pages/land_water.py`: card-sub unit labels updated from "Million Hectares"/"Billion Litres" to plain "Hectares"/"Litres".
- `ui/static/js/dashboard.js`: added a new `formatCompact(value)` helper (`Intl.NumberFormat` with `notation: "compact"`, e.g. `804000 → "804k"`, falls back to a plain fixed-2 string under 1000 so small early-year values don't render oddly). Wired into `renderStackedChart` via a new opt-in `opts.compact` flag (affects that chart's y-axis tick callback and tooltip label callback only — every other chart using `renderStackedChart` is completely unaffected, since the flag defaults to off). `applyResult()`'s calls for `landUseChart`/`waterUseChart` now pass `{ unit: "Hectares", compact: true }` / `{ unit: "Litres", compact: true }`.

**Verified**: Playwright screenshot of the Land & Water tab shows the Land Use axis now reading `200K, 400K, ... 1.4M` and Water Use reading `2T, 4T, ... 18T`, matching the reference chart's readability; zero console errors; `count_flows.py` still 78/78 (engine and `outputs.py`'s underlying `read_cell` calls unchanged — only the display-value scale factor and frontend formatting changed).

### Recurring bug hit again: duplicate stale processes on port 5050 causing "random-looking" wrong calculations on reload

User reported: "whenever we reload sometimes the calculations are going extremely wrong... graphs getting crooked." Checked immediately: **two separate Python processes (different PIDs) were simultaneously `LISTENING` on port 5050** — the same class of bug documented repeatedly throughout this project (port 5000 in `demo_app.py`, port 5050 in `ui/app.py`, at least 5 separate occurrences now across sessions).

**Root cause, explained plainly for the record**: this is a process-management issue, not a calculation/engine bug. Each stray process has its own independent, in-memory `ModelEngine` instance (`ui/app.py`'s module-level `eng`), built up from whatever sequence of requests *that specific process* happened to receive — including potentially running an older version of the code from before a recent fix. Since Windows will let multiple processes bind the same port, a browser reload gets routed nondeterministically to whichever process happens to accept the connection — so consecutive reloads can show completely different, inconsistent results, looking exactly like "sometimes extremely wrong" / "crooked graphs," even though no formula or chart logic is actually broken.

**Fixed**: killed both stale PIDs, started exactly one fresh `python -u app.py`, confirmed via `netstat`/`Get-NetTCPConnection` that only one process is listening.

**Operational note for the user going forward (asked and answered this session, worth keeping close at hand)**: the user is working in **native Windows PowerShell, not Git Bash** — commands given earlier in this project's history (`netstat -ano | grep 5050`, `taskkill //F //PID <pid>`) use Git-Bash/Unix syntax (`grep`, double-slash flags) that **do not work in real PowerShell** (confirmed directly: `grep` errored as an unrecognized cmdlet). Correct PowerShell-native equivalents, to give from now on when helping with this project's port-check routine:
```powershell
Get-NetTCPConnection -LocalPort 5050 -State Listen   # lists PID(s) bound to the port, column "OwningProcess"
Stop-Process -Id <pid> -Force                        # kills one, PowerShell-native syntax (single dash, no // )
```
(`netstat -ano | findstr 5050 | findstr LISTENING` also works in PowerShell as a `grep`-alternative if preferred, since `findstr` is a real Windows command unlike `grep`.) **Use PowerShell syntax by default for any future command given directly to this user to run themselves** — the Bash-tool-style commands used internally by the assistant (via the Bash tool, which runs Git Bash) are not what the user's own terminal understands.

---

## Session Notes (2026-08-07) — Real Bug Found & Fixed in Electricity Supply Chart (Coal Column-Shift), Custom-Lever Numeric Verification Closed, Sankey Audit, Energy Flows Cleanup, 2070/Figma Redesign Scoped as Future Proposal

### Real bug found and fixed: Electricity Supply chart's Coal series collapsed to 0 at 2047

**Symptom**: user screenshotted the "Electricity Supply (Utility)" chart — total rose smoothly from 2022 to a peak of ~5,227 TWh at 2042, then **collapsed to 2,966.89 TWh at 2047** (a ~43% one-step drop), with Coal reading exactly `0` in the 2047 tooltip.

**Investigation, in order** (per this project's standing "trace upstream, don't patch the symptom" method):
1. Confirmed the chart's own arithmetic was internally consistent (the 9 series summed exactly to the stated Total) — ruled out a totaling bug, pointed at a data-source problem for Coal specifically.
2. Used the engine directly (`ModelEngine.load()`, no Excel) to read `I.b!J470` (the cell `GENERATION_ROWS["Coal"]` points to for 2047) — engine returned `0`.
3. Went to the raw `.xlsx` via `openpyxl` (both `data_only=True` and `data_only=False`) to rule out an engine evaluation bug: `I.b!J470`, and its whole dependency chain (`I.b!J469`, `J471`, `J487`), have **no formula and no cached value at all** — genuinely blank in the source file. Not an engine bug; the cell the code was reading is empty.
4. Found the real root cause by reading `I.b`'s own year-header rows (464, 564, 574 — all three agree): sheet `I.b` (Coal) lays its years out as **`C:I` = [2020, 2022, 2027, 2032, 2037, 2042, 2047]** — one column to the *left* of every other generation-technology sheet. Verified `I.a` (Gas), `II` (Nuclear), `III` (Hydro), `IV.a`/`IV.b`/`IV.c.1` (Solar/Wind), `V.a` (Bioenergy) all individually use the standard **`D:J`** layout. `I.b` is the one exception, undocumented anywhere before this session.
5. `ui/outputs.py`'s `compute_electricity_supply_chart()` read every `GENERATION_ROWS` sheet with one hardcoded column list, `IMPORT_DEPENDENCE_YEAR_COLS = ["E","F","G","H","I","J"]` (correct for the `D:J` sheets, i.e. 2022→E ... 2047→J). Applied to `I.b`, this is off by one column: it read `I.b!J470` for "2047," but `I.b`'s real 2047 column is `I` — and `J` is simply blank. Worse: this wasn't only a 2047 problem — the whole Coal series was silently shifted, e.g. the number the chart labeled "2042" was actually `I.b`'s real 2047 figure.

**Fix applied**, `ui/outputs.py`:
- Added `GENERATION_YEAR_COLS_OVERRIDE = {"I.b": ["D","E","F","G","H","I"]}` (documented inline with the full reasoning above), keyed by sheet name so the one real exception doesn't need an `if sheet == "I.b"` at the call site.
- `compute_electricity_supply_chart()` now looks up `GENERATION_YEAR_COLS_OVERRIDE.get(sheet, IMPORT_DEPENDENCE_YEAR_COLS)[i]` per sheet instead of assuming one column list for all 8 technology sheets.

**Verified**:
- Coal 2047 now reads a smooth continuation of its own trend (`1786.42` TWh under Custom Pathway/saved-lever state, `2970.74` under Preset L1 — see below), never `0`.
- `count_flows.py` (the trusted 78/78 validator) re-run after the fix: **still 78/78, 0 mismatches** — confirms this was a pure UI-layer fix with zero engine impact.
- Cross-checked against a screenshot of an older/reference dashboard built on "the same data": that reference showed Coal 2047 = 3,212.71 TWh and a smoothly-rising total (6,168.23) — same shape as our post-fix chart, confirming the fix direction was right (exact figures differ because the reference was evidently generated under a different scenario/lever state, not because of a remaining bug — see the Preset-L1 exact-match finding further down, which independently confirms the fixed code is numerically correct).

**Operational note hit again during this fix**: the running `ui/app.py` Flask process (port 5050) had been started *before* the code edit, so it kept serving the old, buggy chart even after the fix was saved and even after a hard browser refresh — the standing "stale process" class of bug this project has hit repeatedly. Confirmed via `Get-NetTCPConnection -LocalPort 5050 -State Listen` that exactly one process was listening (not the duplicate-process variant this time, just a stale one), killed it, restarted `python -u app.py`, and verified via direct `curl` to `/set_scenario` that the live server's JSON response reflected the fix before asking the user to refresh.

### Custom-Pathway single-lever numeric verification — closed, real Excel match confirmed

This project's history had an open gap (see 2026-07-13/07-22 sessions above): predefined presets were proven byte-for-byte correct against live Excel, but no single-lever Custom Pathway drag had been cross-checked against live Excel to the same exact-match standard (only directional correctness had been verified).

**Closed this session**: set `Control!E13` ("Solar Photovoltaic") to `1` then `4` under `Target Year Input!E10=1, IESS V3 Main Sheet!E12=0` (Custom Pathway), read `IV.a!J230` (2047 Solar PV generation, GWh) both times:

| `Control!E13` | Engine result |
|---|---|
| 1 | 972,913.148707817 |
| 4 | 2,546,297.94808391 |

User independently reproduced the identical lever change live in Excel and reported the same two numbers to the decimal. **This is now a confirmed, real, single-lever numeric match for Custom Pathway mode** — closing the last open item from the "predefined vs. custom" verification question, not just a directional check.

### A second, unrelated AI/tool session's investigation of this same chart — reviewed, found to be wrong on its two main conclusions

User separately consulted a different assistant (working directly inside a live Excel session on this workbook, via some Excel-integrated copilot/automation tool — the kind of Excel-automation approach this project's own charter explicitly rejected as an architecture from day one) about the same Electricity Supply chart screenshot, and asked this session to review that other transcript.

**Two real problems found in that other session**:
1. **It accidentally overwrote a live formula cell, `IV.a!J44`, with stray text — twice in a row** ("ty", then "so ", presumably leaked keystrokes from its own chat input landing in the spreadsheet grid). Both times it caught and restored the formula (`='User-defined drivers'!E70`, evaluating to `85.4185584016124`), but the fact that it recurred immediately after being "fixed" once suggests the actual focus-routing bug was never diagnosed, only patched reactively. **Checked our own copy of the workbook directly** (`d:\ACPET\IESS\Excel_Enging\compiler\workbook\IESS2047_Version_3.0.xlsx`, last modified 2026-06-08, `I.b`/`IV.a!J44` both intact) — confirmed this did **not** touch the file our engine reads, so no risk to this project's own validated state, but flagged as a live-file-integrity concern for whatever session/copy that other tool was operating on.
2. **It concluded the chart "isn't generated from this workbook at all,"** based on searching the raw `.xlsx` for the literal label strings shown in the chart ("Bioenergy," "Electricity trade," "CCS" as a generation bucket) and finding zero matches. **This test is fundamentally flawed and was disproven directly**: those labels are `ui/outputs.py`'s own Python-layer display names (`GENERATION_ORDER = ["Gas","Coal","CCS","Nuclear","Hydro","Solar","Wind","Bioenergy"]` plus a separately-computed "Electricity trade" series) — they are never written as literal text anywhere in the source `.xlsx`, regardless of which dashboard/tool is reading it, so a text search for them was guaranteed to return zero matches whether or not the chart came from this workbook.
3. It also concluded "this can't be the L1 case" because `Control!E5:E15` wasn't all set to `1` — missing the already-documented nuance (2026-07-13/07-22 sessions above) that once a preset (`E12≠0`) is active, the workbook's own formulas override the individual Control-sheet lever values entirely, so the raw slider positions are irrelevant.

**Proved definitively, live, using this project's own engine** (`ModelEngine.load()` + `compute_electricity_supply_chart()`, `E10=1, E12=1` = Preset L1): every single value in the disputed screenshot reproduces **exactly**, to the decimal —

| Category | Screenshot | Engine, Preset L1 |
|---|---|---|
| Gas | 54.69 | 54.69 |
| Coal | 2,970.74 | 2,970.74 |
| CCS | 34.36 | 34.36 |
| Nuclear | 379.81 | 379.81 |
| Hydro | 234.56 | 234.56 |
| Solar | 1,144.21 | 1,144.21 |
| Wind | 1,097.43 | 1,097.43 |
| Bioenergy | 21.83 | 21.83 |
| Electricity trade | 22.35 | 22.35 |
| **Total** | **5,959.98** | **5,959.98** |

**Conclusion for future reference**: this screenshot is this project's own fixed dashboard, running Preset L1 — not an external tool, not evidence of a remaining bug. The other session's methodology (literal text search inside the `.xlsx` to determine chart provenance) should not be reused or trusted for this kind of question; the engine-based reproduction test above (build the same scenario, run `compute_*` directly, diff the numbers) is the reliable way to settle it, consistent with this project's whole "trust but verify against live values" discipline.

### Sankey diagram (Energy Flows tab) — audited, holds up

Given the Coal bug above, did the same audit on the Sankey diagram before the user leans on it for a demo. Cross-checked `compute_sankey()`'s own totals against `compute_outputs()`'s independently-computed `total_supply`/`total_demand` KPIs (both ultimately derived from the same `read_flows()` edges, but via separate code paths) across 3 presets (L1, L2, L4) × all 6 chart years:
- Sum of Sankey's source-origin link values matched `total_supply` almost exactly at every single point (e.g. L1 2047: `2,504.54` both ways, exact).
- The handful of small deviations found (≤0.25 out of ~1,500–2,500, i.e. <0.02%) are explained by the diagram's own deliberate `SANKEY_MIN_VALUE = 0.05` noise-filter (hides sub-0.05-Mtoe flows from the visual) — not a bug.
- Zero nodes fell outside the `source/demand/loss/tech/carrier` categorization across every scenario/year tested.

**Conclusion**: the Sankey is solid and can be used as the centerpiece of a demo as-is.

### Energy Flows tab — "Total primary supply" box removed (user request)

Removed the small `Total primary supply: <b>–</b> Mtoe` box that sat next to the year-tab toolbar on the Energy Flows tab, since the user didn't want it. Three-part removal (verified nothing was left dangling):
- `ui/pages/energy_flows.py` — removed the `<div class="sankey-total" id="sankey-total">...</div>` markup.
- `ui/static/js/dashboard.js` — removed the `document.getElementById("sankey-total").innerHTML = ...` write inside `renderSankey()` (would otherwise throw on every year-switch once the element no longer exists).
- `ui/static/css/dashboard.css` — removed the now-orphaned `.sankey-total`/`.sankey-total b` rules.

Confirmed live (`curl` the served page, `grep -c sankey-total` → `0`) and confirmed the toolbar row doesn't look broken with just the year-tabs left in it (`justify-content: space-between` with one child just left-aligns, no visible gap).

### Electricity tab chart restyle — attempted, then fully reverted per user feedback ("looks weird")

User asked to make the Electricity Demand/Supply charts look more like a reference (Plotly-style: persistent colored "Name | value" endpoint labels, larger fonts). Implemented:
- Wired the dashboard's existing (but previously only-`renderImportDependenceChart`-only) `endpointLabelPlugin` into `renderStackedChart` behind a new opt-in `opts.endpointLabels` flag, enabled it for the two Electricity charts, and reserved right-hand canvas padding for the labels.
- Bumped `Chart.defaults.font.size` (12→13 globally), legend label font size (10→12), endpoint-label font (10px→11px) and box height (16→18), and added thousands-separators to the endpoint-label values.
- Increased the Electricity Demand/Supply canvases from `height="220"` to `height="340"` to give the new endpoint labels room (several 2047 values sit close together, e.g. Solar 1,144 / Wind 1,097, and would have overlapped at the old compact size).

**User's verdict after seeing it live: "looks weird," roll it back.** Fully reverted every piece above, byte-for-byte back to pre-session behavior — global font size, legend size, `renderStackedChart` (no endpoint-label option wired for the electricity charts), `endpointLabelPlugin`'s own font/box size, and the canvas heights back to `220`. Verified via `curl` that the served page shows `height="220"` again and the JS no longer references `endpointLabels` for either electricity chart. **Lesson for next time**: this user wants to see a styling change live before committing further — don't assume "matches a reference screenshot" automatically reads as an improvement; get a look-and-feel sign-off before layering more changes on top (font + labels + size were changed together, making it unclear afterward which specific piece felt "weird" — if revisited, change one dimension at a time).

### 2070 model extension — clarified as the project's actual end goal, not a someday-maybe

User shared a Figma mockup for a substantially different dashboard design, titled "India's Energy Security **2070**" (dark navbar, `Level 0–3 / Net Zero` top-bar scenario selector, a new tab taxonomy — Economy, Critical Minerals, Energy, Transport, Industry, Buildings, Agriculture, Electricity, Emissions, Imports, Security, Scenarios — a "Demand-Side Analysis" section with a bespoke isometric house illustration, and a right-hand "Simulation Insights" glossary/trend-explainer sidebar), and asked whether to build "this exact UI as the next step."

**Flagged before touching anything** (per this project's standing change-control discipline, applied here to a design decision rather than code): this is a new design system, not a re-skin, and one hard fact blocks treating it as real: **the actual workbook, `IESS2047_Version_3.0.xlsx`, only has data through 2047** — confirmed directly, every technology sheet's own year-header row lists `2020/2022/2027/2032/2037/2042/2047` and nothing further. Any 2070 number in that mockup cannot currently come from this file. Also flagged as separate open decisions: the new `Level 0–3/Net Zero` scenario paradigm vs. today's `Custom Pathway/L1–L4`; the new tab taxonomy vs. today's tabs; and the bespoke illustration/glossary content, which needs real assets and authored copy, not derived data.

**User's response, clarifying the actual project direction**: *"we are heading towards 2070 only. That is the whole idea here."* — i.e. the 2047 dashboard/engine work done across this whole project is groundwork toward a real 2047→2070 model extension, not the end deliverable. This directly supersedes the earlier (2026-07-15) framing of "2070 extension — explicitly deferred, noted for future planning only": it is not deferred, it's the actual goal, though the *data source* for 2070 numbers is still unresolved (asked directly; no answer yet — could be a forthcoming extended workbook, a modeling extrapolation this project would need to build, or something else).

**Current status, explicitly stated by the user**: **not active work.** User has no time to build this redesign right now; sharing the Figma mockup was to *propose* the change to others (a team/stakeholder), on the reasoning that a real 2070 extension will need a genuinely new UI, not a re-skin of the 2047 dashboard. **Do not start implementing this redesign unprompted in a future session** — it's parked at proposal stage until (a) the 2070 data-source question is answered and (b) the user explicitly asks to build it. (Recorded as a durable memory as well, not just here.)

Saved to this session's persistent memory system as a `project`-type entry (`project_2070_goal.md`) so this framing survives into future conversations even without re-reading this file's full session-note history.

### Aside: a third reference shown for its look, no action taken

User also shared a screenshot of the Climact "2050 Pathways Explorer" (the EUCALC-family tool) purely to express appreciation for its look. Noted for the record: this is the same design lineage the current dashboard's 2026-07-20 "EUCALC-style redesign" session already deliberately borrowed from (dark navbar, underline tabs, circular per-lever level-dots, muted stacked-area palette) — so the resemblance is intentional, not a coincidence. Specific elements that stood out as nicer than what exists today and were **not yet implemented** (raised as a possible small future follow-up, not started): the hover tooltip's dashed vertical year-marker + inline legend-value list, the "Lock your scenario" affordance, and the visualization-type switcher icons (line/table/chart/tree) above a chart.

---

## Session Notes (2026-08-07, cont'd) — Duplicate Stale Port-5050 Processes (killed), Multi-User Shared-Engine Gap Confirmed (fix proposed, not yet applied)

### Symptom reported: lever changes producing wrong/inconsistent output ("stupid combinations")

User reported that changing levers was producing wrong-looking results and suspected either caching or something structural. Asked to re-read this file first (standing instruction for any session touching lever behavior).

### Bug found + fixed: two stale processes simultaneously bound to port 5050

`netstat -ano | grep 5050` showed **two independent `python -u app.py` processes LISTENING on the same port at once** (PIDs from two different session starts, ~13:10 and ~15:05 the same day — not a Werkzeug reloader parent/child pair, confirmed by the ~2hr gap between `StartTime`s via `Get-CimInstance Win32_Process`). This is the exact same recurring class of bug documented at least 4 times earlier in this project (2026-06-25, 2026-07-13 ×2, 2026-07-22) — the browser can end up talking to whichever process happens to answer, including one serving code from before the last edit/restart.

**Fixed:** killed both PIDs (`taskkill //F //T`), confirmed port 5050 free, started one fresh `python -u app.py`, confirmed `curl` → `200`. User was told to hard-refresh/incognito afterward to rule out browser-side caching too (same "stale artifact, client-side variant" lesson from 2026-07-13).

### Real, separate, still-open finding: the dashboard has ONE shared engine for ALL users, confirmed still true today

User's real underlying fear, once the port bug was explained as a single-machine artifact: *"if a lot of people use it at the same time, how will that even work?"* This is not the port bug — it's a distinct, already-flagged-but-never-fixed architecture gap. Re-confirmed directly against the current code (not just trusting the old 2026-07-14 note):

- [`ui/app.py:28`](ui/app.py#L28): `eng = ModelEngine.load(...)` is created **once**, at module scope. `/set_scenario` ([app.py:63-97](ui/app.py#L63-L97)) and `/recalc` ([app.py:100-110](ui/app.py#L100-L110)) both call `eng.set_lever(...)` directly on that one shared instance. No session/request-scoped state exists anywhere in the file.
- **Effect under real concurrent use:** every visitor is editing the same whiteboard. Person A drags a lever, sees a correct result; Person B drags a different lever a moment later, and the server's *one* lever configuration now reflects Person B's choice — Person A's next request recalculates from state they never set. Not framed as a threading/race bug (the Werkzeug dev server here answers one request at a time by default) — simpler and worse: there is exactly one lever state on the server, period, no matter how many browsers are open.
- User's stated deployment shape (asked directly via `AskUserQuestion`): **many people, concurrently, each needing their own independent scenario** — the strictest case, not a take-turns kiosk/demo.

### Why the fix is cheap, confirmed by reading the engine's own separation of concerns

Checked whether per-user isolation would mean re-parsing the ~40s workbook load per visitor — it would not, confirmed via [`engine.py`](xlcompiler/compiler/engine.py):
- `ModelEngine.__init__(self, model)` takes an already-loaded `WorkbookModel` and only constructs a fresh `Evaluator(model)` — cheap, no reparse.
- `Evaluator.__init__` ([evaluator.py:57-71](xlcompiler/compiler/evaluator.py#L57-L71)) stores `self.m = model` (a reference) plus its own private `_cache`, `_token_cache`, `_overrides`, `_stack` — all per-instance.
- **Grepped `evaluator.py` for any write into the shared model** (`self.m.x = ...`): **zero matches** anywhere in the file. The `Evaluator` only ever reads from `model`, never mutates it.

Conclusion: one `WorkbookModel` (the expensive, formulas/tables/names part) can safely be shared read-only across many `Evaluator`/`ModelEngine` instances at once. Per-session isolation is purely a `ui/app.py`-layer fix — **zero changes needed in `xlcompiler/compiler/`**, so the 78/78 validated baseline is not at risk.

### Proposed fix (presented to user, NOT yet implemented — awaiting explicit go-ahead per this file's Change Control rule)

- Keep the single `model = WorkbookModel.load(...)` at startup, unchanged.
- Replace the module-level `eng` with a per-session dict (`sessions: dict[str, ModelEngine]`), keyed by a Flask session cookie (needs `app.secret_key`).
- `get_engine()` helper: look up this visitor's `ModelEngine`; create one fresh (cheap) on first visit, applying the same two mode-switches (`E10=1`, `E12=0`) startup already applies.
- `/recalc` / `/set_scenario` call `get_engine()` instead of touching a shared global.
- Add idle-session eviction so long-running deployments don't accumulate `Evaluator` caches (~1,700+ cells each, per the 2026-07-22 profiling note) forever.
- Add `threaded=True` to `app.run(...)` — without it the dev server answers one request at a time globally regardless of the state fix, so concurrent users would still queue behind each other's ~3s recalcs.

**Risk flagged, not yet a blocker:** if this ever moves to multiple worker *processes* (e.g. `gunicorn -w 4`) rather than one process, an in-memory `sessions` dict won't be shared across workers — a user's session could get routed to a worker that's never seen them. That's a separate horizontal-scaling question (would need Redis or similar for shared session storage), distinct from the single-process fix proposed here.

**Status at end of this note: proposed, not implemented.** Waiting on explicit approval before touching `ui/app.py`.

---

## Session Notes (2026-08-31) — Phase 1 of the "Organic dashboard mockups" UI redesign shipped: new All Energy overview + lever panel, all 51 real levers preserved

User provided a new visual design built with Claude's Design Canvas tool (`Organic dashboard mockups/India Energy Scenarios 2047 v3.dc.html` — a `.dc.html` file, not deployable as-is; it only runs inside the Design Canvas host, which supplies `window.React`/`ReactDOM` via `support.js`). Asked for a plan to wire it into the real Flask app, UI work first, multi-user session isolation (proposed in the note above) deferred to afterward. Plan was written via `EnterPlanMode`/`ExitPlanMode` and approved; this note records what actually shipped.

### Scope decision confirmed against the real reference site, not just the mockup

The mockup's lever data (`GROUPS`/`NET` in its `<script>` block) is a synthetic, simplified **19-lever** set. Cross-checked against a screenshot of the actual live government IESS site the user had pasted earlier (`Organic dashboard mockups/uploads/pasted-1788155589382-0.png`) — confirmed the mockup is missing a "Growth of the Economy" row, a "Waste to Energy" row, and per-sector sub-drilldowns for most categories that the real site has. This app's own workbook already exposes all **51** real Control-sheet levers via `levers.py`. Decision: port the mockup's *visual widget* (track + level-dots, grouped cards, scenario dropdown, KPI overview tiles, chart-tab switcher) but generate it from the real 51-lever `SIDEBAR_GROUPS` data, not the mockup's own 19-lever hardcoded list — no capability regression versus the dashboard that existed before this session.

### What shipped

- **`ui/levers.py`**: `CATEGORY_RANGES`' old single "Supply" umbrella split into three groups — **Renewable & Clean Energy** (Renewable Generation + Bioenergy subcats), **Conventional Energy** (Power Stations & CCS + Fossil Fuel Production subcats), **Network & Systems** (Grid, Trade & Storage) — matching the mockup's taxonomy. Same row ranges as before, pure regrouping; `load_levers()`'s return shape unchanged.
- **`ui/pages/sidebar.py`**: rewritten to render each lever as the mockup's track-with-level-dots control (`GROUP_ACCENTS` dict gives each top-level group its own accent color, applied via a `--lever-accent` CSS custom property on the `<details class="group">` element) instead of a native `<input type=range>`. Each lever keeps a hidden `<input id="lv{row}">` as the value source of truth, so `/recalc`'s payload-building JS needed no changes.
- **`ui/pages/all_energy.py`**: rewritten to the mockup's layout — 3 KPI tiles (Final Energy Demand / Primary Supply / Imported Energy, each with a thin progress bar + a real descriptive delta line) above a 3-way chart-tab switcher (Energy Demand / Energy Supply / Import Dependence), reusing the existing `.subtabs`/`.subview` mechanism already built for the Indicators/Costs tabs rather than inventing a new one. The KPI tiles are safe to reintroduce despite the 2026-07-23 removal note (they read from the exact same `compute_outputs()` call already driving every chart on the page — one state, not two conflicting ones). Dropped the page's old duplicate `emissionsChart` canvas (same `emissions_intensity_chart` data already shown on the Indicators tab).
- **`ui/static/js/dashboard.js`**: added a single `setLeverLevel(id, level)` helper (updates the hidden input, the track-dot active/past classes, and the fill-line width) and reused it at all three places a lever's value can change (scenario-preset snap, per-lever dot click, subcategory quick-level-box click) — replaced the old per-slider `input` listener entirely. Added `renderOverviewKpis(data)`, called at the top of `applyResult()`.
- **`ui/pages/base.py`**: fixed a pre-existing mislabel where all 4 scenario dropdown options read "Determined Effort — L1/L2/L3/L4" — now correctly "Least Effort — L1", "Determined Effort — L2", "Aggressive Effort — L3", "Heroic Effort — L4".
- **Other 8 tabs** (Electricity, Energy Security, Emissions, Indicators, Costs, Energy Flows, Land & Water, Critical Minerals): deliberately untouched — no mockup exists for them, so only the shared shell (header/nav, already centralized in `pages/base.py`) carries over.

### A real bug found and fixed mid-verification, not present in the mockup itself

Per this project's own standing rule to verify UI changes live rather than just claim success, drove the running app with Playwright (`chromium-cli` wasn't available in this Windows/Git-Bash environment; the Python `playwright` package + a locally-installed Chromium were, so used those directly). First screenshot showed the new Energy Demand chart rendering as a tiny, garbled, never-finishing draw; second attempt (after fixing a test-script timing bug) showed it fully blank. Root cause: Chart.js's default `maintainAspectRatio: true` derived a ratio from the canvas's default 300×260 HTML attributes, and once the chart moved from the old 2-column `.chart-grid` into a full-width standalone card (needed for the new single-chart-at-a-time tab layout), the same ratio math stretched the canvas to a ~1150×1000px oversized, slow-to-settle size. **Fixed** by wrapping the 3 All Energy canvases in a `.chart-wrap` div with an explicit CSS height (`360px`) and passing `maintainAspectRatio: false` through `renderStackedChart`/`renderImportDependenceChart`'s new `opts.maintainAspectRatio` parameter (default `true`, so every other page's existing charts are unaffected). Re-verified with a fresh Playwright run: chart renders correctly, KPI tiles show correct numbers, clicking a lever's level-4 dot (Passenger Transport Demand) visibly updates that lever's track state and produces a real, correct recalculation (`1,880.65` → `2,144.28` Mtoe demand — matches a direct `curl /recalc` check of the same lever/value done earlier in the session), the "CHANGED SINCE BASELINE" badges and dashed-changed-series chart styling both activate correctly, zero browser console errors.

### Verified

- `count_flows.py` re-run after all changes: still **78/78, 0 mismatches** — confirms this was a pure UI-layer change, `xlcompiler/compiler/` untouched.
- All 51 real levers confirmed present and individually settable in the new widget (group counts sum to 51: 1 Economics + 21 Demand + 13 Renewable & Clean + 8 Conventional + 3 Network & Systems + 4 Costs + 1 Other).
- Direct `/set_scenario`/`/recalc` curl checks and the Playwright browser run both reproduced the known-correct L1 preset value (`1,880.65` Mtoe) and a known lever-specific delta, cross-checked against each other.

### Not yet done

Phase 2 (shell-consistency-only pass on the other 8 tabs) and Phase 3 (multi-user per-session engine, scoped in the note above) were both explicitly sequenced after this phase and have not been started.

---

## Session Notes (2026-08-31, cont'd) — Phase 1 redone: had ported the WRONG mockup version (v3, not v2)

### The mistake, and how it was caught

User looked at the Phase 1 result above and said it didn't match the mockup at all — first suspected a routing/caching bug (server was restarted onto a fresh port, 5051, to rule that out definitively), then said directly: "I want the UI exactly like the mockup." Re-investigated from scratch rather than guessing: the `Organic dashboard mockups/` folder contains a `.thumbnail` file (a WebP, auto-generated by the Design Canvas tool from whatever's actually the current/active design). Converted and viewed it — it showed a **visually different page** than what Phase 1 had been built from (`India Energy Scenarios 2047 v3.dc.html`): different headline ("Where the country's energy comes from in 2047"), different KPI set (4 stat cards including Clean Share % and Emissions GtCO2, not 3), a dark bottom "Control deck" lever band instead of a light sidebar, segmented 1-4 buttons instead of dot-tracks. Grepped the thumbnail's headline text across all 3 `.dc.html` files — it matched **v2**, not v3. **The file-naming ("v3" = newest) was a false assumption** — v2 is the one the user actually continued working on / considers current, confirmed by the tool's own auto-generated thumbnail, the most authoritative signal available. Lesson: when multiple versioned design files exist, check the thumbnail/most-recently-referenced artifact before assuming the highest version number is current — don't infer from filename alone.

### Redone against the correct file (v2)

Read `India Energy Scenarios 2047 v2.dc.html` in full and rebuilt Phase 1 against it, keeping the same underlying safe decisions from before (all 51 real levers preserved, no `xlcompiler/compiler/` changes, same `compute_outputs()` data contract):

- **`ui/levers.py`**: group names/order changed to match v2's actual taxonomy — Demand side, Clean build-out, Conventional supply, Network and systems, plus Economics and Costs appended (not in the mockup at all, kept so no lever loses coverage). Same row ranges as before, renamed only.
- **`ui/pages/base.py`**: full shell rewrite — dropped the old dark navbar + light sidebar entirely. New structure: kicker + Space Grotesk headline + "Current pathway" readout, a rounded pill-style tab selector (replacing underline tabs), a two-column body (a static "Explore" sub-nav card + main content), and a full-width dark "Control deck" band at the very bottom (shared across all tabs, replacing the old per-tab-invisible sidebar — still site-wide, just relocated).
- **`ui/pages/sidebar.py`**: rewritten from a collapsible `<details>` sidebar to flat Control Deck group cards, each lever rendered as a segmented 1..max button group (colors matching v2's `LEVEL_FILL`/`LEVEL_TEXT` arrays exactly) — no nested sub-categories, matching v2's flat list (v2 has no chevron/drilldown mechanism at all, unlike the v3 attempt).
- **`ui/pages/tabs.py`**: `render_tabs_html()` now emits the pill-tab markup.
- **`ui/pages/all_energy.py`**: rewritten to v2's exact section order — 4 stat cards (Final demand / Clean share / Imported fuel / Emissions), a two-column "Energy demand by sector" chart + "Primary supply split" panel, then a full-width "Reliance on imported fuel" chart.
- **`ui/static/css/dashboard.css`**: full rewrite of tokens (added Space Grotesk for headings, v2's off-white/ink/blue palette, 12px-rounded cards) and new component classes for the pill tabs, Explore sidebar, stat cards, and the dark Control Deck; also carried the same rounded-card language onto the shared `.card`/`.chart-grid`/`.kpi` classes used by the other 8 tabs, so the whole app reads as one system without needing to touch those 8 pages individually.
- **`ui/static/js/dashboard.js`**: replaced the track-dot lever wiring with segmented-button wiring (`setLeverLevel` now targets `.cd-lever`/`.cd-seg-btn`); added `renderOverviewKpis` (new 4-stat set, Clean Share computed client-side as `(renewables+nuclear)/total_supply`, Emissions read from `emissions_by_sector_chart.total`'s last year); added `renderSupplySplit` (a hand-built horizontal %-bar + list, not Chart.js, for the "Primary supply split" panel); added `updatePathwayName`/`updateGroupAvgs` for the header's live pathway label and each Control Deck group's live average.

### A real correctness bug found and fixed mid-verification (not present in the mockup, introduced by a naive port)

The mockup's "Reliance on imported fuel" chart implies one combined line. The obvious-looking implementation — sum `import_dependence_chart`'s 4 fuel-type series per year — produced a nonsense **230-310%** y-axis, caught immediately by looking at the actual rendered screenshot rather than trusting the code. **Root cause:** those 4 series are each a fuel's own import dependence as a % of *that fuel's own demand* (independent ratios, not shares of one whole), so summing them is meaningless — confirmed by checking `outputs.py`'s `compute_import_dependence_chart`. **Fix:** compute the combined line the same way the already-correct `kpis.import_dependence` scalar is computed — `energy_imports_chart.total[i] / supply_chart.total[i] * 100` per year — both of which *are* genuinely additive Mtoe totals. Re-verified: chart now shows a sane 44%→64% curve across 2022-2047, and its final point matches the KPI tile's 64.3% exactly, confirming internal consistency.

### Verified

- Full Playwright browser run (fresh page load + a real lever click on "Passenger Transport Demand" → level 4): all 4 stat cards populate with real numbers, both charts render correctly (no repeat of the earlier Chart.js sizing bug — same `chart-wrap` + `maintainAspectRatio:false` pattern reused), the header's "Current pathway" label correctly flips from "Least Effort" to "Custom pathway", the clicked lever's segmented button and its group's live average both update, the "CHANGED" badge correctly lights up on both the demand chart and the (cascading) supply-split panel, zero browser console errors.
- `count_flows.py` re-run after all changes: still **78/78, 0 mismatches**.
- Visually cross-checked the rendered page against the mockup's own `.thumbnail` image side by side — matching section order, typography (Space Grotesk headline + IBM Plex body/mono), pill tabs, stat-card style, and dark Control Deck.

### App now running on port 5051, not 5050

Per the user's explicit request, to eliminate any ambiguity from browser caching against the old server: killed the process that had been on port 5050 across this whole session's edits, changed `app.run(..., port=5050)` → `port=5051` in `ui/app.py`, and restarted fresh. **`http://127.0.0.1:5051/` is the current URL** — 5050 is intentionally dead.

### Not yet done

Same as before: Phase 2 (shell-consistency pass on the other 8 tabs — partially done already as a side effect of the shared `.card`/`.kpi` CSS rewrite above, but their internal chart layouts are untouched) and Phase 3 (multi-user per-session engine) remain for later, in that order, per the user's own sequencing.

---

## Session Notes (2026-08-31, cont'd) — Lever panel restructured again: dark bottom "Control deck" → light boxes near the top, sub-sectors collapsed by default

### The feedback

User looked at the v2-matched build above and said the lever panel's *structure* was still wrong: the dark full-width "Control deck" band sat at the very bottom of the page, so reaching it meant a long scroll. They pasted a screenshot of the actual real government reference site (`India Energy Security Scenarios 2047`, the original public tool this whole project models) and said: match *that* structure — light boxes in a compact grid, positioned right near the top — while keeping this project's current v2-mockup visual language (Space Grotesk, rounded cards, the segmented button widget), not the reference site's dated 2012-era look. Two distinct asks: structure from the reference site, aesthetics from what's already built.

### Root cause of the "too much scrolling" complaint

Not just position — **height**. The dark Control Deck listed all 21 real "Demand side" levers as flat rows in one column; the real reference site instead shows just 5-7 top-level rows per box (Transport, Buildings, Industry, Cooking, Agriculture, Telecom), each with its own "Drop down for Sub-Sectors" chevron that reveals the granular levers underneath only when clicked. This collapsed-by-default pattern is exactly what the *first* attempt at this redesign (the abandoned v3-based version, from earlier this session) already had — it was dropped when rebuilding against v2, since v2's own illustrative mockup only has ~19 fake flat levers so flatness looked fine there. With real data (51 levers, up to 21 in one group), flat was never going to be compact. Reintroducing the collapse/expand mechanism is what actually fixes the height problem; repositioning alone would not have been enough.

### What changed

- **`ui/pages/sidebar.py`**: rewritten again — each Control-sheet group renders as a light, rounded `.lg-box` card. Inside, each *sub-category* (the same `CATEGORY_RANGES` groupings already in `levers.py` — e.g. "Transport", "Power Stations & CCS") is a collapsed row by default: a chevron, a title, and a compact "quick-select" segmented 1-4 control that snaps every lever in that sub-category at once. Clicking the row expands it to reveal each individual real lever, each with its own full segmented 1..max control (same `cd-seg-btn` widget already built for v2).
- **`ui/pages/base.py`**: the lever section (`<section class="lever-panel">`) moved from the very end of the page to directly below the pill-tab bar — the first thing in the main flow, above the "Explore" sidebar and all chart content, so it's reachable without scrolling on a normal viewport. The dark `.control-deck` background is gone entirely; the panel is full-width but visually light, matching every other card on the page. The Key box (effort-level legend) is now just one more box in the same grid instead of a separate dark panel.
- **`ui/static/css/dashboard.css`**: replaced the whole dark Control Deck block with `.lever-panel`/`.lg-box`/`.lg-subcat`/`.lg-subcat-row`/`.lg-subcat-detail`/`.lg-quick-btn` — light theme throughout (white cards, `var(--line)` borders, muted greys), reusing `.cd-lever`/`.cd-seg`/`.cd-seg-btn` for the expanded individual-lever rows but recolored for a light background (they were built dark-background-only before).
- **`ui/static/js/dashboard.js`**: replaced `updateGroupAvgs()` (a live group-wide average, no longer shown) with `updateSubcatQuickButtons()`/`updateAllSubcatQuickButtons()` — mirrors the pre-v2 `.level-box` behavior: a sub-category's quick-select shows the shared level highlighted only when every lever inside it currently matches, otherwise none highlighted. Added click handlers for `.lg-subcat-row` (toggle `.open` to expand/collapse) and `.lg-quick-btn` (snap every lever in that sub-category to the clicked level, then recalc) — same pattern the original sidebar used before the v2 rewrite, just targeting the new markup/classes.

### Verified

- Playwright run: expanded "Conventional Supply" → "Power Stations & CCS" (chevron rotates, reveals exactly its 5 real levers — Gas/Coal Power Stations, Coal efficiency, CCS Power Stations, CCS Fuel Mix — matching the real Control-sheet row count for that sub-category); clicked the quick-select "4" on "Demand side" → "Transport" (snaps all 7 Transport levers to 4, recalculates for real: `1,880.65` → `2,013.74` Mtoe, matches the KPI tiles/charts/pathway-name/"CHANGED" badges all updating together, consistent with every other verification this session). Zero console errors both times.
- Visual check: lever panel now sits directly under the tab bar, fully visible without scrolling at a normal 1000px+ viewport height — the specific complaint that triggered this change.
- `count_flows.py` re-run after all changes: still **78/78, 0 mismatches** — no engine/outputs changes, UI-layer only.

### Not yet done

Phase 2 (shell-consistency pass on the other 8 tabs) and Phase 3 (multi-user per-session engine) remain queued, in that order, unchanged from before.

---

## Session Notes (2026-09-01) — Lever panel: light grid-of-boxes → persistent dark rail, side by side with the data

### The feedback

User rejected the light grid-of-boxes version (the one built directly from the reference-site screenshot) on two points at once: (1) the control panel and the data still weren't visible together without scrolling — stacking the lever panel above the charts meant you could reach *one* of them without scrolling, not both at the same time; (2) it should be **black** — stated directly that "control panel is the driving factor of the entire website/calculator, if not there is no meaning to it," i.e. the lever panel is this tool's primary control surface and should look like one (visually dominant, dark), not blend in as one light card among many.

### The fix: side-by-side layout, not stacked

Restructured `.body-cols` from "light lever panel full-width, then Explore sidebar + main content below it" to a genuine two-column split: a **dark, sticky, independently-scrolling left rail** (`.control-rail`, `position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow-y: auto`) holding the pathway selector + all lever groups, next to the KPI/chart content on the right. Side-by-side (not stacked) is what actually guarantees both are on screen together — no amount of repositioning a stacked single-column layout can achieve that once there's enough chart content to exceed one viewport height, which this page always will have. The sticky+internal-scroll combination means the rail stays visible even if you scroll the right column, and the rail itself scrolls internally if its own content (7 groups) runs past viewport height, rather than pushing the page layout around.

- **`ui/pages/base.py`**: dropped the old light `.lever-panel` (full width, above `.body-cols`) and the decorative `.explore` sidebar entirely. New `.control-rail` (dark) is the left column of `.body-cols`; `.main-col` (KPI stat row + charts) is the right column. `#status-chip` moved inside `.main-col` since the dedicated bottom band it used to live in is gone.
- **`ui/static/css/dashboard.css`**: `.control-rail`/`.cr-head`/`.cr-title`/`.cr-desc`/`.cr-key`/`.cr-key-item` added (dark, `var(--ink)` background). `.lg-box`/`.lg-subcat*`/`.lg-chevron`/`.lg-quick-btn`/`.cd-lever-label`/`.cd-seg`/`.cd-seg-btn` all recolored from the light theme back to dark (light text on `#1c1e23`/`#2d3038`-bordered surfaces) — same markup and JS hooks as the previous light version, only the color values changed, so none of the interaction logic needed to change.
- No Python-side data/structure changes beyond what the light version already had — same `CATEGORY_RANGES`-driven collapsible sub-sectors, same segmented 1..max buttons, same quick-select-per-sub-sector mechanism.

### Verified

- Fresh screenshot at a normal 1500&times;1000 viewport: all 7 lever groups' collapsed rows (Demand Side through Economics/Costs, "Other" partially visible at the rail's own internal scroll boundary) are visible on the left, simultaneously with all 4 KPI stat cards and both the demand/supply-split charts on the right — the exact "both in the same place, no scrolling" requirement.
- Playwright interaction test (same as previous version, re-run to confirm the relayout didn't break anything): expanded "Conventional Supply" → "Power Stations & CCS" (still reveals its 5 real levers), quick-selected "Demand side" → "Transport" to level 4 (still recalculates for real: `1,880.65` → `2,013.74` Mtoe, "CHANGED" badges, pathway name flip to "Custom pathway", all identical to before). Zero console errors.
- `count_flows.py` re-run: still **78/78, 0 mismatches** — UI-layer only change, `xlcompiler/compiler/` untouched throughout this entire redesign arc.

### Not yet done

Unchanged: Phase 2 (shell-consistency pass on the other 8 tabs) and Phase 3 (multi-user per-session engine) remain queued, in that order.

---

## Session Notes (2026-09-01, cont'd) — Control deck: side-by-side rail → horizontal band docked to the bottom, whole page fit to one viewport, no scrolling anywhere

### The feedback

User acknowledged the dark side-by-side rail as progress, then asked for a different arrangement: horizontal, docked to the **bottom** of the page (not the side), and explicitly **not scrollable** — the control deck itself must never need a scrollbar. Explicitly OK'd shrinking the KPI cards and charts to make room, prioritizing the control deck's full visibility over chart size.

### What changed — this is a genuine fixed-viewport layout now, not a tall page

Previous versions all let the page grow taller than one screen and relied on scrolling (either the whole page, or an internal scrollbar on the rail) to reach everything eventually. This iteration changes that assumption: `.page` is now `height: 100vh` with `display:flex;flex-direction:column`, so the layout is a fixed budget, not an open-ended one.

- **`ui/pages/base.py`**: `.control-rail` (side column) removed entirely; replaced with `<section class="control-deck-h">` as a sibling *after* `.main-col`, docked to the bottom. Pathway select, the effort-level key, and `#status-chip` are now one horizontal header row (`.cdh-head`) above the lever grid, instead of stacked block elements — saves vertical space specifically inside the deck.
- **`ui/static/css/dashboard.css`** (full rewrite of the layout-critical rules):
  - `.page`: `height:100vh; display:flex; flex-direction:column`. `.page-head`/`.pill-tabs`: `flex:none` (fixed height). `.main-col`: `flex:1 1 auto; min-height:0; overflow-y:auto` — takes whatever vertical space remains, scrolls internally only as a last-resort fallback (not the expected path). `.control-deck-h`: `flex:none; max-height:34vh; overflow:hidden` — a hard cap, deliberately not `overflow-y:auto`, because the requirement is "never has a scrollbar," not "scrolls if it must."
  - `.lever-grid` changed from a single stacked column (the side-rail version) to `grid-template-columns: repeat(7, minmax(150px,1fr))` — all 7 groups side by side in **one row**. A 2-row grid was tried first and rejected before shipping: splitting into 2 rows halves the vertical space available to the tallest group (Demand Side, 5 sub-sectors), which was tight enough to risk clipping; one row gives every box the full deck height instead.
  - Every font size, padding, and chart height in the KPI/chart area was reduced (`.stat-value` 32px→21px, `.chart-wrap` 260px→230px, etc.) — the explicit "shrink the data, not the control deck" instruction from the user.
  - `.supply-list`'s temporary `max-height + overflow-y:auto` (added defensively, then found unnecessary once chart heights were retuned) was removed — it was a second, smaller scrollbar that had no reason to exist once there was enough room to show all 9 supply-mix rows directly.

### A sizing mistake caught and corrected before shipping

First pass at the chart heights left a large dead-space gap between the "Reliance on imported fuel" chart and the control deck at the bottom — `.main-col`'s `flex:1` correctly claimed all the leftover vertical space, but its content (KPI row + 2 chart sections) didn't grow to fill that space, since none of the chart heights were flexible. Caught this by looking at the actual rendered screenshot rather than assuming the numbers were fine, then increased the fixed chart heights to use the space properly. This is a lower-effort fix than making the charts genuinely flex-fill (which would adapt perfectly to any viewport height, at the cost of a bigger refactor) — flagged as a known limitation: these are still fixed pixel heights tuned to look right at a ~1000px-tall viewport, not a fully responsive fill. If a real viewport is meaningfully shorter or taller, the balance between chart size and empty space will drift; a proper flex-fill (making `.chart-wrap` `flex:1;min-height:0` inside a flex-column view, instead of a fixed height) would be the next step if this comes up again.

### Verified

- Fresh screenshot, 1500&times;1000 viewport: **zero scrollbars anywhere** — all 4 KPI cards, both two-column charts, the full "Reliance on imported fuel" chart, and all 7 control-deck groups (every one of Demand Side's 5 sub-sectors included) are visible simultaneously, matching the literal ask.
- Expand/collapse re-tested: opening "Conventional Supply" → "Power Stations & CCS" reveals its 5 real levers with no clipping inside the now-shorter, wider box — confirms the one-row-of-7 layout (not 2 rows) leaves enough headroom for expansion.
- Quick-select re-tested: "Demand side" → "Transport" → level 4 still recalculates correctly (`1,880.65` → `2,013.74` Mtoe), same numbers as every prior verification pass this session. Zero console errors.
- `count_flows.py`: still **78/78, 0 mismatches** — this whole session's redesign arc has never touched `xlcompiler/compiler/`.

### Not yet done

Unchanged: Phase 2 (shell-consistency pass on the other 8 tabs) and Phase 3 (multi-user per-session engine) remain queued, in that order. Also newly flagged above: the KPI/chart area's heights are fixed-pixel, tuned for ~1000px viewports — a true flex-fill would be more robust across different screen sizes if this becomes a problem.

---

## Session Notes (2026-09-01, cont'd) — Control deck box arrangement matched to the real reference site's layout; dark theme confirmed, not abandoned

### The feedback, and resolving an apparent contradiction before touching any code

User pasted the real reference IESS site screenshot again and said the layout still wasn't matching what they'd asked for. This looked contradictory at first: the previous message had explicitly asked for **black**, but the reference screenshot is light/white with colored per-section icons. Rather than guess a sixth time, asked directly via `AskUserQuestion` whether the theme should flip to light (matching the screenshot's actual colors) or stay dark (matching the screenshot's *structure* only). **Confirmed: stay dark** — "exact layout" meant the box arrangement, not the color scheme.

### What changed — box arrangement + icons, same dark theme, same single-row-height safety property

- **`ui/pages/sidebar.py`**: added `GROUP_ICONS` (one emoji per group — person/leaf/factory/network/etc., matching the reference's per-section icon convention, no external asset needed) prefixed onto each `.lg-box-title`. Added an explicit CSS `order` per box (`_order_for()`) so groups still render in their natural data order (Demand, Clean, Conventional, Network, Economics, Costs, Other) but *display* with Network/Economics/Costs/Other shifted one slot later — freeing slot 4 for the Key box.
- **`ui/pages/base.py`**: the small inline effort-level legend that lived in the control deck's header row was pulled out into a proper `.lg-box.lg-key-box` (`order:4`), matching the reference site's own dedicated "Key" box sitting immediately after the 3 main sector boxes — not just a compact strip of swatches.
- **`ui/static/css/dashboard.css`**: `.lever-grid` widened from 7 to 8 grid columns (7 real groups + 1 Key box), still **one row** — a 2-row arrangement (which would visually match the reference's "3 boxes + Key on top, Network below" even more closely) was deliberately not used again: it's exactly the layout that was tried and rejected two sessions ago in this same arc, because splitting into 2 rows halves the vertical space available to the tallest group (Demand side, 5 sub-sectors) and risks clipping it. Keeping everything in one row, just reordered via CSS `order`, gets the *visual adjacency* the reference has (Key box right next to the 3 main groups) without reintroducing that height risk.

### Verified

- Screenshot: Key box now sits as the 4th box, immediately after Demand Side / Clean Build-out / Conventional Supply — matching the reference's adjacency. Icons render as intended in a normal browser (Segoe UI Emoji on Windows Chrome/Edge); the headless test browser used for verification lacks a system emoji font and showed placeholder boxes instead — flagged as a test-environment artifact, not expected to reproduce in the user's actual browser, but worth confirming with the user directly since it hasn't been checked in a real browser this session.
- Re-tested expand/collapse on "Conventional Supply" (now in a narrower 8-column slot instead of 7): still reveals all 5 real sub-levers with no clipping — confirms the one-row structure remains safe even with one more column squeezed in.
- Re-tested quick-select on "Demand side" → "Transport" → level 4: still recalculates correctly (`1,880.65` → `2,013.74` Mtoe), consistent with every prior check this session.
- `count_flows.py`: still **78/78, 0 mismatches**.

### Not yet done

Unchanged: Phase 2, Phase 3, and the fixed-pixel-height chart sizing caveat all carry forward from the previous note. New: **the emoji icons haven't been confirmed in a real (non-headless) browser** — worth a quick look before treating this as fully done.

---

## Session Notes (2026-09-03) — Recalculation correctness: a concurrency race, a preset/lever desync, and out-of-range levers. **Read this before trusting `1,880.65` as the Level-1 answer.**

### The report

User: *"if I change the lever multiple times suddenly our entire website renders every possible wrong data"*, plus a request to fix it **without changing the core idea of the engine**. Three separate bugs turned out to be involved. None of them were in `evaluator.py`/`engine.py` — the engine was never modified this session. All three were in how `ui/app.py` and `ui/static/js/dashboard.js` *use* it.

Method: every claim below was reproduced with a script before any code changed, and re-run after. Scripts are throwaway (scratchpad, not committed), but the reproductions are described precisely enough to rebuild.

### Bug 1 — a concurrency race: the actual "wrong data"

`evaluator.py` is a correct **single-threaded** design. `eval_cell()` shares three mutable structures across the whole engine: `_cache`, `_depth`, and `_stack` (its cycle detector). `set_override()` clears `_cache` so downstream cells recompute. None of that is a bug on its own.

But Flask's dev server is **threaded by default**, and `eng` is one module-level singleton, so two overlapping POSTs ran inside that shared state simultaneously.

Reproduction (concurrent POSTs to `/recalc`, 8 workers, alternating all-levers-1 and all-levers-4):

| | Result |
|---|---|
| Sequential all-1 / all-4 | `2201.98` / `912.85` — perfectly repeatable |
| **Two overlapping requests** | **every single response came back `349.92` or `347.38`** — matching neither payload, roughly a sixth of the correct value |

Mechanism, in order of severity:

1. **`_stack` false positives.** While thread A is evaluating cell X, X is in `_stack`. Thread B evaluating that same X hits the `if key in self._stack: return self._circular_seed` branch — concludes "circular reference" and returns `0` for a cell that is not circular at all. Whole subtrees of the model zero out. This is what produced the ~1/6 figures.
2. **Shared `_depth`.** Both threads increment it, so `MAX_DEPTH` trips early → more spurious `_circular_seed` returns.
3. **Mid-computation `_cache.clear()`.** Thread B's `set_override` wipes the cache while A is halfway through, so A's answer mixes values derived from two different lever states.
4. **`scoped_overrides()` cross-talk.** `/set_scenario` saved and restored `self._overrides` wholesale; a concurrent `/recalc` writing levers inside that window had its writes silently reverted on exit.

**Fix — in the caller, not the engine.** `ui/app.py` now holds a single process-wide `MODEL_LOCK = threading.Lock()` across every handler that reads or mutates `eng` **or** `baseline_snapshot` (one request writes it, later requests read it). `/set_scenario` was split so the lock scope is explicit: the route acquires the lock and delegates to `_set_scenario_locked()`, whose docstring states the requirement. `GET /` needs no lock — it only reads the precomputed `SIDEBAR_GROUPS`, never `eng`.

Serialising costs no real throughput here: the model is CPU-bound, so concurrent requests were never actually parallel work, just corruption.

**Do not "optimise" this by removing the lock, or by making the evaluator thread-safe with finer-grained locking.** The engine's single-threaded contract is a deliberate simplification that makes the cache and cycle detector cheap. Serialise at the door instead.

### Bug 1b — the client half: out-of-order responses

Same symptom, independent cause. `recalc()` had **no in-flight guard and no response sequencing**, while `scheduleRecalc()` debounced only 250ms and a model run takes seconds. Rapid clicking put several POSTs in flight; whichever **landed last** called `applyResult()`, so a stale answer could overwrite a fresher one.

`dashboard.js` now has a coalescing queue: `requestModel(task)` / `pumpModel()`, with `modelBusy` and a single `queuedTask` slot. Only one request is ever in flight; while it runs, newer intents **replace** the waiting one (an intermediate lever state nobody is looking at any more is not worth a round trip). Levers are read at *send* time, not click time, so a queued request picks up every click made while it waited. `setScenario()` goes through the same queue, so presets and lever edits can't overlap each other either. The status chip only returns to `live` once the queue has drained, so a burst reads as one continuous recalculation.

Consequence: out-of-order application is now structurally impossible rather than merely unlikely. Measured: 12 rapid clicks → **1** coalesced POST; 25 random clicks at 80ms → **1** POST.

### Bug 2 — presets were computed from stale lever state (the big one)

`/set_scenario` used to set `E12 = level`, compute `display_data` **with whatever Control-row values the previous interaction had left in the engine**, and compute the diff baseline inside `scoped_levers()` (which then undid it). The browser, on receiving the response, set every hidden input to `level`.

So the screen claimed "all levers at N" while the numbers on it had been computed from unrelated leftover values — and the result depended on click history:

| State of Control rows underneath | `E12=4` reports |
|---|---|
| levers still at 1 | `1255.53` |
| levers still at 2 | `1161.94` |
| levers set to 4 | `1074.24` |

A **17% swing** on the same button, decided by what the user had clicked earlier. This is the most likely direct cause of the reported symptom, alongside Bug 1.

**Fix.** An example pathway is now defined as *every lever at that effort level*, and `/set_scenario` and `/recalc` share one code path — a new `_apply_levels(levels)` helper that pins `E12=0`, writes **every** known lever, and clamps each to its own max. The chosen pathway also *becomes* `baseline_snapshot` directly instead of being recomputed as a separate what-if, so `scoped_levers()` is no longer needed here and **picking a pathway is now ~2× faster** (one model evaluation instead of two).

Because every lever is written on every request, a result is a pure function of the request payload and cannot inherit anything from the previous one.

### Correction — what `predefined.scenario` / `E12` actually does (supersedes the claim near line 608)

The doc previously stated that `E12=1..4` selects a preset that *"overrides individual lever choices entirely"*, via `IF(E12=0, use_levers, CHOOSE(E12,...))`, and that the UI must therefore force `E12=0` before touching a slider or the workbook will "silently ignore" it.

Two corrections, both measured:

1. **The defined name is real.** `predefined.scenario` → `'IESS V3 Main Sheet'!$E$12` exists in the workbook's defined names. (An earlier statement made *in this session* that "nothing reads E12" was wrong — a plain-text formula scan misses it because formulas reference the **name**, not the literal `E12`. Recorded here so the mistake isn't repeated: always resolve defined names before concluding a cell is unread.)
2. **But it does not override levers in this engine.** If it did, `E12=4` would give one answer regardless of the Control rows. It gives three different answers (table above). Levers dominate. Whatever Excel does natively, this compiler evaluates only a handful of cells that consume `predefined.scenario`, so its total influence is:

| Level | all-levers-N, `E12=0` | same, `E12=N` | delta |
|---|---|---|---|
| 1 | 2201.98 | 2201.98 | **0.00** |
| 2 | 1564.93 | 1564.93 | **0.00** |
| 3 | 1225.04 | 1225.04 | **0.00** |
| 4 | 1070.58 | 1074.24 | 3.66 (0.34%) |

That level-4-only 3.66 Mtoe perturbation *was* the entire "preset vs custom" discrepancy the user objected to. `E12` is now pinned to `0` permanently, so preset ≡ custom **by construction at every level**, and the UI's claim that all buttons sit at N is truthful.

Practical upshot: the "must switch to Custom Pathway before moving a slider" rule the doc describes is no longer load-bearing, because the app never leaves `E12=0`.

### Correction — "Least Effort" is `2,201.98`, not `1,880.65` (supersedes ~21 references)

`1,880.65` appears throughout this document as *the* correct Level-1 / Least-Effort figure, including in `app.py`'s own comment warning against "breaking the match". It is **not** level 1. It is the demand produced by the workbook's **saved** Control-sheet lever mix, whose level distribution is:

```
{0: 3 levers, 1: 3, 2: 21, 3: 23, 4: 1}     -> total demand 1,880.65
```

Mostly 2s and 3s — a middling working state someone left saved in the file, plus three levers at level **0**, which the UI doesn't even offer. Labelling it "Least Effort (All at level 1)" was simply wrong, and it sat *below* the true all-at-1 figure, which made the pathway ladder non-monotonic.

The four pathways now form a coherent ladder — more effort, less demand:

```
level 1  2201.98      level 2  1564.93      level 3  1225.04      level 4  1070.58
```

**Any historical number in this document computed under "Least Effort" or "level 1" before 2026-09-03 was almost certainly computed against that saved mix, not against level 1.** Treat pre-2026-09-03 figures as unreliable for comparison — the same caution the Diagnostic Tooling Incident section applies to the 9/78 era. Notably the frequently-quoted `1,880.65 → 2,013.74` lever-change check is superseded; the equivalent check is now `2,201.98 → 2,013.74`.

If the saved mix is wanted as a selectable pathway (it is a plausible "Reference / business-as-usual" case), it should be added as its own named option — **not** as level 1.

### Bug 3 — out-of-range lever values

`/recalc` pushed `int(levers[lever_id])` straight into the workbook with no bound, while `/set_scenario` clamped to `ALL_LEVER_MAX`. The deck renders four buttons for every row regardless of that row's real maximum, so any lever with a max below 4 could be driven out of range. Five are affected:

| Control row | Max | Lever |
|---|---|---|
| 31 | 3 | Growth of the Economy |
| 40 | 3 | Growth of floorspace |
| 59 | 3 | Capital Costs |
| 60 | 3 | Fuel Costs |
| 61 | 3 | Infrastructure Costs |

(Row 49, Fuel Switching — Iron & Steel, has max **5**, above the UI's range.)

The browser clamps via `data-max` in `setLeverLevel()`, so the UI was mostly shielded — but the server must not trust the client. `_apply_levels()` now clamps server-side with `max(1, min(value, ALL_LEVER_MAX[...]))`. This is why an all-4 payload moved from `912.85` (out-of-range, meaningless) to `1070.58` (correct).

### Invariants to preserve — do not undo these

1. **Every handler touching `eng` or `baseline_snapshot` holds `MODEL_LOCK`.** New endpoints must too.
2. **`_apply_levels()` is the only place lever values reach the engine**, and it writes *all* levers and pins `E12=0`. Keep both properties: writing all levers is what makes a response independent of request history.
3. **`/set_scenario` and `/recalc` must stay one code path.** The moment presets get their own computation, the preset-vs-custom gap comes back.
4. **The client must never have two model requests in flight.** Keep the `modelBusy` / `queuedTask` queue; don't "parallelise" it for responsiveness.
5. Clamp server-side even though the client clamps.

### Verified

- **Race gone**: same 8-way concurrent reproduction now returns each payload's own correct answer (`2201.98` for all-1, `1070.58` for all-4), engine still correct afterwards.
- **Gap gone**: `/set_scenario N` vs `/recalc` all-N identical at all four levels across five metrics simultaneously (total demand, total supply, import dependence, and the final-year totals of both All-Energy charts) — not just the headline number.
- **History-independent**: preset 4 returns `1070.58` after all-1, after all-2 and after all-3.
- **Repeatable**: identical payload twice → identical fingerprint.
- **Browser end-to-end**, in each case comparing the *rendered* KPI and both chart totals against an independent single-request recompute of the lever state actually on screen: 12 rapid clicks (1 POST) → match; 25 random clicks at 80ms (1 POST) → match; levers **interleaved with preset clicks** (2 POSTs) → match; one row hammered 10× (1 POST) → match; presets 4→2→3→1 rapid → lands on the last one clicked.
- All 9 tabs render, zero console errors throughout.

### Also done this session (UI, same date)

- **Control deck flipped to a dark slate band** (`--deck-bg: #39404B`, matching the menu drawer's header). All deck colours now derive from `--deck-*` tokens, so light/dark is a handful of values. Caught a half-applied state in the process: the CSS had gone dark while `sidebar.py`'s `LEVEL_FILL`, `base.py`'s inline Key swatches and `dashboard.js`'s unselected-chip literal still held light-deck values — a selected level-1 chip was invisible against the band (`#4a5160` on `#39404B`) and, since every row defaults to level 1, **the whole deck read as unset**. Contrast now measured, not eyeballed: selected chips ≥5.96:1, unselected ≥6.39:1, all deck text ≥5.45:1. **`base.py`'s Key swatches are inline styles and must be kept in step with `sidebar.py`'s `LEVEL_FILL`/`LEVEL_TEXT` by hand.**
- **Masthead band** added (full-bleed, product name centred, hamburger right) plus a **right-hand slide-in drawer** (How-to / Videos / Project / Science / Feedback / Legal — all still `href="#"` placeholders; Feedback needs a real mailbox). Pathway readout moved out of the masthead to an indicator chip at the right end of the tab row, its dot colour-coded by effort level.
- **Charts**: All Energy now shows Energy Demand + Energy Supply as two equal stacked-area panels (the old "Primary supply split" percentage bar and the duplicated import-reliance chart are gone; `renderSupplySplit`, `computeImportRelianceSeries`, `renderDeltaChart` and `compute_chart_deltas` went with them as dead code). Electricity's two Δ-vs-baseline bar charts removed. EUCalc-style palette adopted with a **semantic** `SERIES_COLOR` map so a category keeps its colour on every chart, plus in-band series labels.
- **Layout**: one shared `--chart-wrap-duo` height (258px) tuned so every tab fits a ~900px viewport with no inner scroll containers; Energy Flows is the deliberate exception, where the Sankey takes the space. Fixed a long-standing Sankey bug: it laid out to a hardcoded `height = 640` while its box was shorter, so `preserveAspectRatio="meet"` scaled the whole diagram down — it had been drawing at **31%** of available width. It now measures `clientHeight`, so scale is 1.0.
- **Deleted** (old versions/artifacts, ~2.7MB): `Organic dashboard mockups/` (v1/v2/v3 `.dc.html` + `support.js` — the `.zip` beside it was verified to archive all 15 files byte-for-byte and was **kept** as the only recovery path, since this is not a git repo), `compiler/$SP/` (sankey debug PNGs), `ui/debug_supply_chart.png`, and all `__pycache__` — including `templates_str.cpython-312.pyc`, bytecode for a UI module that no longer exists. Comments in `levers.py` and `base.py` that cited the deleted mockup files by name were rewritten to point at the zip.

### Not yet done

- The drawer's six links are placeholders; **Feedback** needs a real address (deliberately not guessed).
- The Sankey doesn't fill its card's full **width** — it renders centred with dead space either side. The height bug is fixed; this is a separate layout question in the d3-sankey extent, not yet investigated.
- The saved-mix pathway (`1,880.65`) is not offered as an option; if it's wanted, add it as a named "Reference" pathway rather than reinstating it as level 1.
- The `MODEL_LOCK` makes concurrent users queue. Fine for a demo and for a single presenter; if this is ever served to several officials at once, the real answer is a worker pool of engine instances (one `ModelEngine` per worker), not finer-grained locking.
- The remaining `--deck-*` light/dark duality means a future theme flip must also revisit `sidebar.py`'s `LEVEL_FILL` and `base.py`'s inline Key swatches, which live outside CSS.

---

## Session Notes (2026-09-04) — Capacity work: faster calculation + response caching + precomputed pathways. **Corrects the "~1,700 cells" figure to 39,791.**

### Why

The dashboard is to go in front of **lakhs of genuinely concurrent users** at a launch
peak. Measured starting point: one request cost **2.84 s** and **40.3 KB**, giving
**0.35 req/s per worker** at **312 MB** each. 200,000 users at one action per 20 s is
10,000 req/s — roughly **28,000 workers and 4.4 TB of RAM** by brute force. Not an
option.

Two measurements decided the approach. The model is a **pure, deterministic function of
the clamped 51-lever vector** (identical payload → identical response, independent of
request history — established 2026-09-03), and a repeat with no lever change already
cost 0.004 s versus 2.84 s. So this is a caching problem, not a compute problem. And the
states real traffic reaches are few: **9.0e29 theoretical, but only ~596 for "any
preset plus one lever moved"**.

Agreed with the user: unlimited free-form exploration is kept, and a genuinely novel
combination may take ~3 s behind a loading state. Deployment target is **still
undecided**, so nothing here depends on it.

### Step 1 — the constraint: not one output number may change

`tools/golden_master.py` makes that a test rather than a promise.

- `capture` records the full 28-key payload per lever vector to `tests/golden/<profile>/`;
  `verify` recomputes and asserts **byte-identical**, naming the first differing key path.
- Drives the real request path (imports `ui/app.py`, calls its own `_apply_levels`), so
  clamping and lever-write order are exercised exactly as a live request would.
- Vectors include **200 randomised mixed states**, not just uniform all-N. Uniform states
  hide per-lever bugs: an all-4 request clamps the seven non-4-max levers identically
  every time, so a per-lever mistake stays invisible. Plus the 4 presets, boundary and
  deliberately over-range values for every lever whose max isn't 4, and the workbook's
  saved mix as an anchor. `report_gaps() == 0` is asserted too.
- Profiles: `quick` (10 vectors, ~19 s) for iteration, `full` (221, ~7 min) as the gate.
- `--allow-new` tolerates keys *added* since capture (nothing read them before, so they
  cannot change a displayed value) while still requiring every pre-existing key to match
  and treating a *missing* key as failure.

**The full 221-vector gate was captured from pristine code before any edit and re-run
green after every change.** There is no git here, so that baseline is irreplaceable —
do not regenerate it casually.

### Step 2 — one calculation, ~36% faster, 75% smaller

Cost was concentrated in two places; the other 19 keys totalled ~0.15 s. `read_flows()`
(~1.4 s) is irreducible — the whole landing tab derives from `edges`.

**Engine, `xlcompiler/compiler/evaluator.py` — two safe classes of change only:**

- **No-op override guard in `set_override()`.** It cleared the entire cache even when
  the value was unchanged, and `_apply_levels` writes all 51 levers + E12 every request.
  An idempotent request (tab switch, re-clicking the active pathway, the initial
  `setScenario` on load) therefore paid a full recompute. Measured **2.817 s → 0.004 s,
  794×**, with a genuine lever change still recomputing fully (2.475 s). Semantics
  preserved: a write that changes nothing cannot change anything downstream.
- **Pure-function work removed/memoised** — all value-independent, so none can carry a
  computed value across a lever change (categorically safer than cache invalidation):
  `_peek` (~4.0 M calls/pass) no longer re-evaluates `len(tokens)`; `_numz` no longer
  re-imports `math` inside the function body (~104 k times) when it is already imported
  at module level; `_a1_to_rc` is an `lru_cache`d module function; `_make_range` caches
  an **immutable tuple** and hands callers a fresh `list()` copy, so the invariant
  "nobody mutates `RangeRef.cells`" (verified — the only assignment is in `__init__`)
  cannot be broken later; ranges over 4096 cells are built directly so whole-column
  refs on the big sheets (`Grid_Balance_V2` alone is 184 k cells) can't balloon memory;
  the per-call inline cell-ref regex is compiled once as `_CELLREF_RE`; and
  `WorkbookModel.get_name` lowercases once instead of twice.

**Output layer, `ui/outputs.py`:**

- **`emissions_2047_total`** — `'IESS V3 Results'!J116`, the workbook's own total row.
  The landing tab's 4th stat card used to derive its number from
  `emissions_by_sector_chart.total[-1]`, which costs 102 `read_cell`s. The scalar is
  equal to it **on all 221 golden-master vectors** (asserted per vector, including all
  200 mixed ones — this is what validated it beyond uniform states).
  *Correction to an in-session claim:* J116 is not free at 0.000 s — that reading was
  taken with the cache already warmed by the chart. Cold it costs ~0.23 s, so the saving
  is real but smaller than first stated.
- **`DEFERRABLE_KEYS = ("emissions_by_sector_chart", "sankey")`** with a `defer=`
  parameter. Each is wanted by exactly one non-default tab; `sankey` alone was **31 KB
  of the 40 KB response** while costing only ~2 ms to build (a bandwidth problem, not a
  compute one). `compute_outputs(eng)` with the default `defer=()` still returns
  everything, which is what keeps the golden master a strict gate on the model.

**Result: 2.84 s → 1.83 s median (−36%), 40.3 KB → 9.9 KB (−75%), 0.35 → 0.55 req/s.**
Short of the 1.2–1.5 s estimate in the plan, because `read_flows` is the floor. The full
221-vector run dropped 535 s → 412 s, confirming the gain across the whole set.

**Per-tab endpoints stay ruled out** (measured 2026-09-03: nine tabs together 3.49 s,
independently 10.7 s). Deferring two keys is a *payload* split, not a compute split.

### Step 3 — response caching

`ui/app.py`. Same scenario asked twice is computed once.

- **`canonical_levels(levels)`** is the single source of truth for both what is written
  to the engine and what the cache key hashes, so the two cannot diverge — a divergence
  would serve one pathway's numbers under another's key, the worst failure available.
  It also **fixed a latent history-dependence**: `_apply_levels` previously skipped
  levers absent from the payload, leaving them at whatever the last request set. Omitted
  levers now default to 1, verified identical to sending 1 explicitly and stable across
  an intervening unrelated request.
- **`pathway_key`** = 12-char workbook content fingerprint + hash of the clamped vector.
  The fingerprint is essential: replacing the workbook would otherwise silently serve
  answers from the previous model. Clamping inside the key means two requests differing
  only *above* a lever's max share one entry — verified `lv31=3` and `lv31=9` produce the
  same key and the same numbers, while `lv31=1` differs.
- **Two tiers**: a bounded in-process `OrderedDict` (512) plus a directory of gzipped
  JSON shared by all workers, written with write-then-rename so a reader never sees a
  partial file. Plain files deliberately — works unchanged on a laptop, a shared volume
  or an object store; Redis can slot in behind `cache_get`/`cache_put` later.
- **`changed` is never cached.** It is a diff against the mutable `baseline_snapshot`,
  not a function of the lever vector, so it is attached per request over a `dict(data)`
  copy that leaves the cached object pristine.
- **Single-flight**: concurrent callers for the same uncached key elect one leader and
  the rest wait. Without it, a scenario that suddenly becomes popular is computed once
  per waiting request and stalls the pool exactly when it is busiest.
- **`GET /pathway/<key>.json`** serves an already-computed pathway with
  `Cache-Control: public, max-age=31536000, immutable` — content-addressed, so the body
  for a URL can never change. This is the tier a CDN can serve without Python running at
  all. A miss is 404 (the key alone carries no lever vector) and the client falls back to
  `POST /recalc`. The blanket `no_cache` after-request hook now leaves an explicitly-set
  `Cache-Control` alone.
- `/cache_stats` exposes hit/miss/coalesced counters.

**Bug caught during this work:** the route held `MODEL_LOCK` and then called
`compute_pathway`, which acquires it again — `threading.Lock` is not reentrant, so it
self-deadlocked. Restructured to exactly one acquisition point; `_set_scenario_locked`
became `_set_scenario` and takes no lock (assigning `baseline_snapshot` is a single
atomic rebind).

### Step 4 — precomputed frontier

`tools/precompute_pathways.py` enumerates the 4 pathways plus every single-lever
deviation from each, deduplicated by `pathway_key`: **596 distinct states**. Reuses the
server's own `pathway_key`/`compute_pathway`/`cache_put`, so there is no second key
algorithm to drift. Idempotent and resumable. Also fills the deferred bundle per state,
which is nearly free because that worker's evaluator cache is still warm for exactly
that lever state.

**579 states computed in 6.0 min on 4 workers (16-core box) → 4.1 MB across 1,189
files.** Each worker loads its own engine (~1.4 s, ~312 MB), so `--workers` is bounded by
RAM; the work is CPU-bound so there is nothing to gain past the core count.

### Measured outcome

| Journey | Before | After |
|---|---|---|
| Example pathway click (most visitors) | ~2,840 ms | **15 ms** (190×) |
| First lever tweak from a preset | ~2,840 ms | **24 ms** |
| Deep custom state nobody precomputed | ~2,840 ms | **1,850 ms** |
| Repeat of any scenario | ~2,840 ms | **29 ms** (125×) |
| `GET /pathway/<key>.json` (CDN tier) | — | **5 ms** |
| Response payload | 40.3 KB | **9.9 KB** |
| `/deferred` on a warm lever state | — | **30 ms** |

### Corrections to this document

- **A full pass evaluates 39,791 distinct cells (206,389 `eval_cell` calls), not
  "~1,700".** The ~1,700 figure repeated in the earlier notes is the number of
  *top-level* reads the UI layer makes (`read_flows` over 200 rows × 8 year columns plus
  ~35 `read_cell` sites) — which is exactly what a *warm* pass costs. The transitive
  closure is 23× larger. **Any capacity planning based on ~1,700 was wrong.**
- **The claim that targeted invalidation "would likely end up close to the full ~1,700
  cells anyway" is false.** When one lever changes, only **1,842 of 39,791** cached
  values actually move — **4.6%** — so the theoretical prize is ~20×. It stays deferred
  anyway (see below), but not for the reason previously recorded.

### Deferred, with reasons

- **Targeted cache invalidation.** ~20× prize, but no dependency tracking exists and a
  graph learned from one lever state is *unsound* for another: `INDIRECT` resolves a
  computed string, `INDEX`/`MATCH`/`CHOOSE` select by value, and `IF`/`IFERROR` evaluate
  only the taken branch, so unobserved edges are invisible. This is the one change that
  could alter results.
- **Shared workbook model across workers.** Verified safe by experiment (SHA-1
  fingerprint of every cell unchanged after two independent passes from two engines over
  one shared model; no cross-contamination). Would cut memory from 312 MB/worker to
  ~308 MB once + ~5 MB each, after hoisting the 32 MB `_token_cache` to shared — itself
  safe, being keyed by formula text, never mutated and idempotent. Not needed until
  deployment is decided; on Linux `gunicorn --preload` + `fork()` gives most of it free,
  Windows has no `fork()`.
- **`_split_call_args` memo** (~0.49 s). Skipped deliberately: it would have to be keyed
  on `id(tokens)` plus a strong reference to keep ids from being recycled, and it returns
  sublists callers would have to promise never to mutate. Least clear safety story of the
  memo set for the smallest confidence.

### Invariants — do not undo these

1. Every handler touching `eng` or `baseline_snapshot` holds `MODEL_LOCK`, and there is
   exactly **one** acquisition point per request path (it is not reentrant).
2. `canonical_levels()` is the only definition of a lever vector: it writes **all**
   levers and clamps them, and both the engine write and the cache key derive from it.
3. `/set_scenario` and `/recalc` remain one code path (`compute_pathway`). Split them and
   the preset-vs-custom gap returns.
4. `changed` is computed per request, never cached.
5. The cache key includes the workbook fingerprint.
6. `compute_outputs(eng)` with default `defer=()` must keep returning the complete
   payload — the golden master gates on it.
7. The client keeps one model request in flight (`modelBusy`/`queuedTask`).

### Not yet done

- **Prerendering `/`.** Still rebuilt per request via `render_base()` + `str.replace()`
  though it is static apart from the lever id list. Should be rendered once at startup;
  page loads would then cost zero Python. Listed in the plan, not yet implemented.
- **Client-side key + `GET`-first fetching.** The `GET /pathway/<key>.json` tier exists
  and is verified, but `dashboard.js` still always POSTs; it does not yet compute the key
  itself and try the cacheable GET first. Until it does, the CDN tier is unused by the
  real client. **This needs a shared key spec and a randomised client/server agreement
  test — a divergence would silently serve another pathway's numbers.**
- **gzip/brotli on responses** (9.9 KB → ~2-3 KB) not yet enabled.
- **Load test** at simulated peak to measure the real hit rate; the 77% seen in a short
  synthetic run is not evidence.
- Deepening the frontier to two tweaks (~88 k states, ~600 MB) only if telemetry shows
  the tail matters.
- `cache/pathways/` (4.1 MB, 1,189 files) is generated output — it should be
  git-ignored/excluded from any archive rather than shipped, and regenerated per
  workbook version.

---

## Session Notes (2026-09-06) — Disaster recovery: all of `ui/` silently reverted to pre-session snapshots on disk; full reconstruction from conversation history alone

### What happened

Mid-session (adding masthead logos), discovered every file under `ui/` had reverted **on
disk** to old snapshots — `ui/levers.py` to **2026-07-10**, most others to
**2026-07-21 – 2026-07-24** — while the *running* Flask process kept serving correct
behaviour, because Python keeps an imported module's code in memory once loaded; only
the static `dashboard.css`/`dashboard.js` (read fresh from disk on every request) broke
live. **Root cause unknown.** This is not a git repo, the user had no separate backup,
and the reverted files' mtimes predate this whole session — something outside this
tooling touched the filesystem. **If it recurs, suspect a sync/backup/antivirus-rollback
tool on `D:\ACPET\...` before assuming it's a self-inflicted edit.**

At the user's own request, the live server was restarted to "see what went wrong" —
this discarded the last surviving good in-memory copy, leaving disk as the only (bad)
source of truth from that point on.

**Affected:** `ui/app.py`, `ui/outputs.py`, `ui/levers.py`, `ui/pages/base.py`,
`ui/pages/sidebar.py`, all 9 tab page modules + `ui/pages/tabs.py`,
`ui/static/css/dashboard.css`, `ui/static/js/dashboard.js`.

**Untouched, verified intact:** `xlcompiler/compiler/evaluator.py` (the engine),
`cache/pathways/` (1,212 precomputed files), `tests/golden/` (both the 10-vector quick
profile and the full 221-vector gate), `tools/golden_master.py`,
`tools/precompute_pathways.py`, and this document.

### Recovery method

No git, no backup of the code itself — every affected file was reconstructed **from
this conversation's own history**: exact text captured by earlier Read/Edit/Write tool
calls in the same session, not from memory of "what it probably said." Where a file
predated this session's own edits (all 9 page modules, `levers.py`), it was rebuilt from
the still-correct *mechanical* facts that survive independently of styling — canvas ids,
subtab wiring, and `CATEGORY_RANGES` row numbers, all of which this document and
earlier plan-mode exploration in this same session had recorded verbatim.

### Verification (not assumed — run and checked)

- **`tools/golden_master.py verify --profile full --allow-new`: PASS, all 221 payloads
  byte-identical.** (`--allow-new` tolerates `emissions_2047_total`, a key added after
  these particular snapshots were captured — every pre-existing key still had to match.)
- Full Playwright pass across all 9 tabs: no-scroll fit holds everywhere except Energy
  Flows (its own pre-existing, intentional exception), zero console errors, a lever
  change propagates correctly end-to-end (deck → `/recalc` → charts → change sidebar →
  Insights popup).

### Real bugs found *during* reconstruction — independent of the revert, not introduced by it

1. **`compute_electricity_supply_chart`'s Coal series read the wrong column.** Sheet
   `I.b`'s year columns are laid out one column earlier than every other technology
   sheet in `GENERATION_ROWS` (`I.b!D470` is the 2022 figure, not `E470`). The
   golden-master gate caught this directly (Coal values shifted by exactly one year
   across every test vector) — fixed with a per-sheet column override
   (`_IB_SHEET_YEAR_COLS`), confirmed by reading the workbook cell-by-cell, not guessed.
2. **Sankey rendering used node *names* as `d3.sankey()`'s `nodeId`**, but
   `compute_sankey()` (`ui/outputs.py`) links reference nodes by **array index**, not
   name — d3-sankey's *default* `nodeId` already is array index, so the fix was to stop
   overriding it. Also fixed reading `node.type` (doesn't exist on the payload) →
   `node.category` (what `_node_category()` actually returns: source/tech/carrier/loss/
   demand).
3. **`endpointLabelPlugin` (the "Name | value" endpoint callout, meant only for the
   Import Dependence chart) fired on every stacked-area chart.** Chart.js auto-populates
   an empty `{}` for every *registered* plugin's options on every chart it draws (so a
   plugin can always safely read its own config without an existence check) — so a plain
   truthiness check (`!chart.options.plugins.endpointLabels`) was always `false`, never
   short-circuiting. Needed a strict `=== true` check instead, matching how the other two
   opt-in plugins (`bandLabels`, `crosshairTooltip`) already correctly check a nested
   `.display` property rather than the container object's own truthiness.

### Cleanup

Deleted 44 stray screenshot PNGs and `CLAUDE_CODE_PROJECT_CONTEXT.md.bak` that had
accumulated directly in the project root during this session's verification work (they
should have gone to the scratchpad directory, not here) — pure debug artifacts with no
ongoing value now the golden master + Playwright suite cover the same ground
reproducibly and repeatably.

### Not yet done

- The masthead logo swap requested just before the revert was discovered (replace the
  "India Energy Security Scenarios" title text with the ICSS logo image; NITI Aayog
  logo on the masthead's left; ACPET logo on the right before the menu button) — paused
  for this recovery, not yet implemented.
- Every invariant from the 2026-09-03/09-04 sessions above (MODEL_LOCK, canonical_levels,
  compute_pathway single-flight, the two-tier cache) was reconstructed to match this
  document's own description of them exactly, then confirmed against the golden master —
  not re-litigated or redesigned. If a future session finds `ui/app.py` looking
  unfamiliar again, this document plus the golden master is the fastest way back.

---

## Session Notes (2026-09-06, cont'd) — Post-recovery chart sizing: two real bugs found, then per-tab chart heights tuned so every tab matches All Energy's own proportions exactly

### Bug 1 — `endpointLabelPlugin` (Import Dependence's "Name | value" callout) was drawing on every chart

Found while enlarging chart heights and screenshotting the result: every stacked-area
chart (not just Import Dependence, the only one meant to have it) showed a stray
"Total | 2201.98"-style box overlapping its legend. Cause: Chart.js auto-populates an
empty `{}` for every *registered* plugin's resolved options on every chart it draws (so
a plugin can always safely read its own config without an existence check) — so the
plugin's own guard, `if (!chart.options.plugins.endpointLabels) return;`, was always
`false` (`{}` is truthy) and never actually skipped anything. Fixed with a strict
`=== true` check instead of a truthiness one — matching how `bandLabelPlugin` and
`crosshairTooltipPlugin` were already correctly written (they check a nested `.display`
property, not the container object's own truthiness, which is the general lesson here:
**never gate a globally-registered Chart.js plugin on `!chart.options.plugins.<id>`
alone — check a specific property inside it.**

### Bug 2 — legend position was silently shrinking the plot area on 8 of 9 tabs

All Energy/Electricity's charts use `legendPosition: "right"` (vertical legend beside
the plot). Every other stacked-area chart (`energyImportsChart`, `emissionsBySectorChart`,
`capacityChart`, `importCostChart`, `productionCostChart`, `opexChart`, `landUseChart`,
`waterUseChart`) defaulted to Chart.js's bottom legend instead — which, inside a
**fixed-height** `.chart-wrap` container, eats into the same box the plot area itself
has to fit in. So even after the container heights were made numerically equal, the
*visible plotted chart* on those 8 tabs was shorter than All Energy's, with a legend row
underneath eating the difference. Fixed by adding `legendPosition: "right"` to all of
them in `applyResult()` (`ui/static/js/dashboard.js`) — every stacked-area chart across
every tab now uses the same vertical right-hand legend.

### The real ask, arrived at in three passes

1. First ask: make every other tab's charts the same *container* height as All
   Energy's/Electricity's (`.chart-wrap` raised from 270→301px to match
   `.chart-wrap-duo`). This surfaced Bug 2 above — equal container height alone doesn't
   mean equal-looking chart, if legend placement differs.
2. Second ask: since 8 of the 9 tabs have no KPI stat-row above their charts (only All
   Energy does), they have *more* free vertical room than All Energy before hitting the
   control deck — so let their charts (and the change sidebar beside them, which
   stretches to match `.main-col`'s height via `align-items:stretch` on `.content-row`)
   grow to use that freed space, rather than leaving it as dead space above the deck.
   First attempt used one shared bigger value for every non-KPI tab
   (`.chart-wrap { height: 395px }` cf. `.chart-wrap-duo`'s 301px) — this undershot
   slightly (a ~4% overlap the user caught by screenshot: the sidebar's bottom edge
   crept past the deck's top edge on the tightest tab) and was pulled back to 380px.
3. **Final ask — reversed direction entirely: make every tab match All Energy's
   proportions exactly, not grow past them.** "Bigger where there's room" turned out to
   be the wrong instinct — the actual want was **visual consistency**: the change
   sidebar (and by extension each chart) should be the *same* size on every tab,
   using All Energy's own size as the one reference, full stop.

### Why one shared height doesn't produce equal sidebar heights, and what does

`.main-col`'s total height differs per tab for two independent reasons — whether a KPI
row is present (All Energy only) and whether a sub-tab row is present (Indicators/Costs
only) — plus a *third*, smaller effect: the `.panel` wrapper (All Energy/Electricity's
chart-duo layout) and the `.card` wrapper (every other tab's chart-grid layout) don't
carry quite the same chrome height, so the same numeric chart height doesn't produce
the same numeric `.main-col` total between the two layouts. Since `.change-sidebar`
stretches to match `.main-col`, matching *sidebar* height requires four separate chart
heights, not one:

```css
.chart-wrap-duo    { height: 301px; }  /* All Energy — the reference */
.chart-wrap-duo-lg { height: 398px; }  /* Electricity: .panel chrome, no KPI row */
.chart-wrap-lg     { height: 373px; }  /* Emissions / Energy Security / Land & Water: .card chrome, no KPI, no subtabs */
.chart-wrap        { height: 340px; }  /* Indicators / Costs: .card chrome, no KPI, has a subtab row */
```

These four numbers were **derived from one measurement, not guessed repeatedly**:
with all four tiers temporarily equal, the actual rendered sidebar height was measured
per tab (Playwright, `getBoundingClientRect()`), the shortfall from All Energy's own
value computed per tier, and each tier's height raised by exactly that (visual-px,
divided by `--ui-scale` for the logical value) shortfall in one pass. Verified
afterward: every tab with charts now measures **within 0.5px of All Energy's own
sidebar height** (~401px), and the sidebar-to-deck gap is ~54px everywhere charts
exist (Critical Minerals, the one placeholder "coming soon" tab with no chart content
at all, is the one exception — nothing to stretch its sidebar against, not fixable
without inventing fake content there).

**If a chart or a tab's structure changes again** (a KPI row added/removed elsewhere, a
sub-tab added to a tab that didn't have one, a chart moved between `.panel` and `.card`
layout), these four numbers will drift out of sync again — re-measure with the same
method (equalize the tiers, measure the shortfall per tab via `getBoundingClientRect()`
on `.change-sidebar`, correct once) rather than adjusting by feel.

### Verified

- Full Playwright pass, every tab and every subtab (Indicators' 3, Costs' 2): no-scroll
  fit holds everywhere except Energy Flows (its own pre-existing, intentional exception),
  zero console errors.
- Sidebar height measured per tab: All Energy 401.3px, Electricity 401.3px, Energy
  Security/Emissions/Land & Water 401.0px, Indicators/Costs 401.4px — all within 0.5px of
  each other. Sidebar-to-deck gap ~54px on every one of them.
- Import Dependence chart's endpoint labels ("Oil | 92.61" etc.) still render correctly
  after the `endpointLabelPlugin` opt-in fix — confirmed it wasn't accidentally disabled
  everywhere instead of just the other 8 charts.

### Not yet done

- The masthead logo swap (ICSS/NITI Aayog/ACPET) is still pending — paused before this
  chart-sizing detour, same as noted in the entry above.

---

## Session Notes (2026-09-06 through 2026-09-08) — Masthead logos; Pathway Impact rail redesigned four times over; Custom Pathways (formerly "Control deck") reorganized; per-lever level caps fixed; charts made bigger (fixed, not dynamic); Insights redesigned twice; levers switched to a dot-track slider with real hover tooltips sourced from the workbook itself

A long, iterative UI session — most features went through 2-4 rounds of "try it → screenshot → user redirects" before landing. Recorded here in the order they actually happened, since several early attempts were explicitly reverted and the reasoning for *why* matters for anyone tempted to redo them.

### Masthead logos added

Two of the three logo files sitting unused in the top-level `img/` folder (`ACPET_LOGO_White.png`, `niti-aayog-logo-vector.svg`) were copied into `ui/static/img/` and wired into `.site-banner`: NITI Aayog on the left, ACPET on the right next to the menu button (`.site-banner-logo { height: 26px; }` caps them so the masthead height doesn't change). The third file, `ICSS-logo-small.png`, is the product's own "India Energy Security Scenarios 2047" logo — skipped because it visually duplicates the centred title text; left in `ui/static/img/` unused in case it's wanted later.

### Pathway Impact rail: four iterations, only the last one stuck

1. **First attempt** — turned the `.change-sidebar` (a flex sibling of `.main-col` that stretched to match its height) into a CSS Grid (`.page-grid`) with the rail spanning the full page height, all the way down past the Control Deck. **User said "roll back" immediately** — reverted to the original flex-sibling design in full.
2. **Insights popup → docked panel.** Separately, the floating "Insights" popup (a `position:fixed` box that opened beside its trigger button) was turned into a docked flex column inside `.content-row` that slid open via `flex-basis` animation (same technique the Control Deck's own lever-flyout rail already used) — this stuck.
3. **Full-height grid redone properly**, this time keeping the Insights-as-flyout mechanism, and it stuck long enough to build on: `.page-grid` (rail + `.page-main`) with the rail `position:sticky`, and — critically — the user then asked for the **Pathway Impact block itself removed**, leaving Insights as the rail's only content, permanently rendered (`renderInsights()` called on every recalc, no open/close state any more).
4. **User then asked to cut the rail before Custom Pathways and let Custom Pathways run full-width again** — `.control-deck-h` moved back OUT of `.page-grid` entirely, becoming a full-bleed sibling section again (own `margin-top` fixed at 16px, not the page-filling `margin-top:auto` it used to have, since the page no longer artificially stretches to viewport height for this to make sense). This is the layout that shipped: rail covers only the tab row + KPI cards + charts; Custom Pathways is a separate full-width band below, like the masthead.

**Rail bottom-alignment bug, found and fixed within step 4:** the rail had `max-height: calc(100vh / var(--ui-scale)); overflow-y: auto` (meant for "scroll internally if Insights text is unusually long"). Once charts started rendering taller (see chart-sizing section below), that cap made the rail's blue background stop at one viewport height while `.page-main` kept growing — the two no longer shared a bottom edge. Fix: dropped the cap entirely. `align-items:stretch` (the CSS Grid default) already makes the rail match `.page-main`'s real height with no ceiling, and plain `position:sticky` on an over-tall element already does the right thing on its own (sticks near the top, then scrolls away normally near the end) — the cap was solving a problem `position:sticky` doesn't actually have.

### Custom Pathways (renamed from "Control deck")

- Heading text changed to "Custom Pathways"; the description line under it ("Build your own pathway by...") removed.
- The static "Key" legend box (four swatch+label rows, used to be its own grid column) and the separate bare "Example pathway" 1/2/3/4 button row were **merged into one control**, "Predefined scenarios" — each button now shows the level's full name ("Least effort", "Determined effort", ...) plus a colour dot, and is still clickable (same `data-level` handling, no JS logic changed).
- `DECK_COLUMNS` in `ui/pages/sidebar.py` reorganised so Costs and Economics share the deck's last column (the slot the Key box used to occupy), with "Other" listed explicitly under Network/Systems so it can't silently fall into that column by the leftover-group fallback.

### Real bug found: lever level caps were being ignored in the UI

The segmented 1-4 button row was **hardcoded to always render 4 buttons** (`range(1, 5)`), regardless of a lever's real ceiling. The Control sheet actually caps some levers lower — confirmed via the golden test fixtures (`tests/golden/full/max-lv31.json` sets lv31 to 3, `over-lv31.json` tests clamping a value of 9 down to it) — "Growth of the Economy" (lv31) is capped at 3, and one of Buildings' six bundled levers (lv40, "Growth of floorspace") is also capped at 3 even though its five siblings go to 4. `setLeverLevel()` in `dashboard.js` already clamped correctly (`Math.min(level, max)`) — only the *rendering* was wrong, silently offering a 4th button that would immediately snap back to 3 if clicked. **[SUPERSEDED 2026-09-08 — `min()` was the wrong rule and broke Buildings/Industry; see the next session's entry. It is `max()` now.]** Fixed in `ui/pages/sidebar.py`: the shared quick-set row now uses `row_max = min(lv["max"] for lv in levers)`, and each flyout row uses its own lever's real `max` — this incidentally also fixed the previously-invisible per-lever cap on the Buildings bundle.

### Chart growth: tried a dynamic flex-grow cascade, reverted to bigger fixed heights

Asked to make charts grow to fill leftover vertical space (rather than leaving a blank band above Custom Pathways once it stopped being pinned to the viewport bottom), a flex-grow chain was wired through every layer — `.page-grid` → `.main-col` → `.view.active`/`.subview.active` → `.chart-duo`/`.chart-grid` → `.panel`/`.card` → the `.chart-wrap*` tiers — with `min-height`/`max-height` pairs replacing the old fixed `height`. **This did not work as hoped:** capping the growth anywhere in that chain (needed once "looks AI, too much empty space" feedback came in) just relocated the same blank band to whichever ancestor was still uncapped one level up — capping `.chart-wrap-duo` left blank space in `.panel`; capping `.panel`'s row (`.chart-duo`) left it in `.view.active`; and so on. There is no single place to cap a multi-level flex-grow chain and get zero blank space at every level unless every level's cap is hand-tuned to match exactly — not worth the fragility.

**Reverted in full** back to `flex: 0 0 auto` at every one of those levels, and instead the four `.chart-wrap*` tiers just got bigger *fixed* numbers:

```css
.chart-wrap-duo    { height: 380px; }  /* was 301px — All Energy, the reference */
.chart-wrap-duo-lg { height: 460px; }  /* was 398px — Electricity */
.chart-wrap-lg     { height: 440px; }  /* was 373px — Emissions/Energy Security/Land & Water */
.chart-wrap        { height: 400px; }  /* was 340px — Indicators/Costs */
```

A fixed size can never mismatch its own container the way a capped-partway-through-a-growth-chain one can. If a future ask wants charts that adapt to viewport height again, don't redo the cascade — read this section first.

### Insights panel content: redesigned twice

First pass (in response to "looks old school and boring, add some segregation"): grouped the output into labelled sections with dividers ("Levers changed" / "Impact on results"), replaced the bare ▲/▼ glyph with a small filled colour badge (reusing the existing `LEVEL_FILL` blue/green, not new colours), and bolded the changed figures in `var(--head)` (the same display face the big KPI numbers use) for typographic contrast. Also fixed actual white-on-blue body text to black — the blue gradient background only clears ~3:1 contrast even with pure white text (borderline-failing even for the large headline), versus ~6.4:1 with black.

Second pass (user: "we don't need the Final Demand box, just show what lever changed"): dropped the always-shown "Current pathway" KPI snapshot (Final demand/Imported fuel/Clean share/Emissions) entirely — that data already lives in the KPI stat cards above. The idle/base state (nothing moved yet) is now a single line: *"This is the base pathway — nothing has been changed yet. Adjust a lever in Custom Pathways below to see its impact."* `renderInsights(data)` now takes the recalc response directly rather than stashing lever/KPI deltas on the rail's dataset and re-reading them (that indirection had exactly one caller — `renderChangeStrip()` was deleted, its job folded straight into `renderInsights()`).

### Levers switched from numbered buttons to a dot-and-track slider, with real hover tooltips

Prompted by a reference screenshot (an EU-Calc-style "Ambition level 1: ..." hover tooltip over a dot slider). Two parts:

1. **Visual**: `.lg-quick-seg`/`.lg-quick-btn` redesigned from a segmented pill of numbered squares into a thin line with one small dot per level, the current level shown as a filled square (unchanged colours). The digit is gone from the button's visible content — `aria-label="Ambition level N"` carries it for accessibility instead. Click handling and the "all levers at N → highlight that level" sync logic in `dashboard.js` needed **zero changes**, since both still key off `.lg-quick-btn` + `data-level`.

2. **Tooltip content — real, not invented.** Before promising this, checked whether per-level descriptions existed anywhere; **they do** — the Control sheet has never-before-read columns H-K (columns 8-11) holding one ambition-level note per lever per level (e.g. row 5, "Gas Power Stations": col H = level-1 note, I = level-2, J = level-3, K = level-4). Confirmed via a direct `openpyxl` read before writing any code, specifically to avoid fabricating descriptive text that isn't grounded in the actual model. `ui/levers.py`'s `load_levers()` now also captures these into a `descs: {1: "...", 2: "...", ...}` dict per lever item. `ui/pages/sidebar.py` threads it through to `_seg_button_html(n, value, desc=None)`, which HTML-escapes it into a `data-desc` attribute. `dashboard.js`'s `initLeverTooltip()` is one shared floating box (position:fixed, same measured-`getBoundingClientRect()` technique the Sankey's own tooltip already used) shown on hover/focus of any dot carrying a `data-desc`.

   **Deliberately not shown everywhere**: a sub-sector's *shared* quick-set row (when it bundles more than one real lever, e.g. Transport's 6 levers moved together) has no tooltip — its dot represents an *average* across levers whose own level-N notes may say different things, so no single sentence could honestly describe it. Only single-lever rows, and every row inside a multi-lever group's flyout (each of which controls exactly one real lever), get one.

### Recurring incident this session: stale Flask process serving old code

Happened at least three times and cost real back-and-forth ("nothing changed!", "still broken!") before being correctly diagnosed each time: the user runs their own long-lived `python app.py`/`python ui/app.py` process outside of any session started here, and — unlike the CSS/JS static files, which Flask serves fresh from disk on every request — **the HTML template (`render_base()` in `ui/pages/base.py`) is a Python function baked into that process's memory at import time.** Editing it on disk does nothing to a process that's already running; only a full stop+restart of *their* process picks it up. A plain browser refresh, or even a hard refresh, is not enough when the mismatch is server-side.

**Established pattern for verifying UI changes in this project without touching the user's own server:** launch a disposable second instance on a throwaway port (`python -c "import app; app.app.run(port=50XX)"` from inside `ui/`), screenshot it with Playwright, then kill only that specific PID (matched by its distinctive `port=` command-line argument) — never broadly kill anything matching `*app.py*`, which risks taking down the user's own server instead (this happened once, by accident, earlier in the project's history — see the port-5050 incident referenced above). When something "still looks unchanged" after an edit, checking for a stale process on the user's side is the first thing to suspect, not the CSS/JS itself.

### Files touched this session

`ui/pages/base.py`, `ui/pages/sidebar.py`, `ui/levers.py`, `ui/static/css/dashboard.css`, `ui/static/js/dashboard.js`, plus two new files under `ui/static/img/`.

### Verified

- Full-page Playwright screenshots across all 9 tabs (including both of Indicators' and Costs' sub-tabs) after every major change in this log — chart growth/revert, rail bottom-alignment, dot-track + tooltip on both a single-lever row and a multi-lever row's flyout, Predefined Scenarios buttons still functionally set the scenario and reflect the active one.
- Tooltip content spot-checked against the workbook directly (Gas Power Stations level 1, Growth of the Economy level 2) — text matches column H/I on the Control sheet exactly.
- Zero console errors at every checkpoint.

### Not yet done

- Responsive breakpoints (~1100px rail-collapses-to-horizontal-strip, ~700px single-column) from the original detailed rail spec were explicitly deferred pending review of the desktop layout, and haven't been revisited since the rail's shape changed twice more after that spec was written — re-scope before implementing, don't build against the old spec as-is.

## Session Notes (2026-09-08) — Full UI pass: the interface now fits itself to the window instead of to 1920×1080; Chart.js was found to size canvases WRONGLY under CSS `zoom` (long-standing, latent); a bundled lever row's ceiling was `min()` of its members and held them back; Insights became a right-hand card; the whole palette moved onto EU-Calc's white/grey/green/blue with Ranade as the type face; boxes removed from the charts and the deck; the deck's top rule became a working GHG gauge. **Several decisions here were superseded within the same session — read "Where this session actually landed" at the end before trusting any step in the middle, and read the `--ui-scale` circular-dependency warning before touching any viewport-derived height.**

Started from "isn't the UI dynamic for monitor resolutions? I have a huge monitor and it looks like this" (3440×1297 screenshot: content stopping ~65% down the window with a wide band of dead page background under the footer).

### First attempt was in the WRONG DIRECTION — capped and centred the page. Reverted.

Misread the ask as "it stretches too wide" and added `max-width: 2000px; margin: 0 auto` to `.page`. That is the opposite of what was wanted, and made the dead space worse. The user's own clarification, with an EU-Calc reference screenshot: *"the way it spans across my screen. it shouldnt held by a resolution restricted no"* — i.e. **fill the monitor**, don't cap to a chosen resolution. Reverted in full; there is no `max-width` on `.page` now, and none should be added.

Two things worth keeping from that detour:

- A plain px `max-width` inside the zoomed subtree renders at `value × --ui-scale` (2000px capped at ~1800 real px). Any fixed px length written against real screen pixels has to be divided by `--ui-scale`, exactly like `.page`'s existing `min-height: calc(100vh / var(--ui-scale))`. `vh`/`vw` resolve against the true viewport and need that division; percentages and `width:auto` compensate on their own and do not.
- "Nothing changed!" recurred here for the reason already documented in the previous session's *stale Flask process* note. It cost several rounds again. `base.py` is baked into the running process at import time.

### The actual problem, and the fix: `fitUiScale()`

`dashboard.css` is px-based end to end and every `.chart-wrap*` height is a fixed number tuned against a ~1080p window (see the previous session's chart-growth section), with `--ui-scale` (`zoom` on `body`) as the single knob resizing the lot. Pinned at `0.9`, the interface rendered at that same *physical* size on every monitor — hence the dead band on anything bigger. The footer's "Best viewed in 1920 x 1080 resolution, scale: 100%" note was covering for precisely this.

`fitUiScale()` in `dashboard.js` now measures instead of assuming: the footer is `.page`'s last child and `.page` is a flex column packed to the top, so **the footer's own bottom edge IS the content's bottom edge** (`.page`'s `min-height` stretches the container, never the footer's position). It iterates `--ui-scale` until that edge meets the bottom of the window. Runs on load, on `resize`, and on tab/sub-tab switches (each tab carries a different chart height, so the fitting scale differs per tab). Energy Flows is skipped — `#sankeySvg`'s height is already `100vh`-derived, so measuring it chases a target that moves with the scale and just runs the UI to `UI_SCALE_MAX`.

Measured results, deterministic across repeated runs:

| Window | Fitted `--ui-scale` |
|---|---|
| 3440×1297 | 1.271 |
| 2560×1440 | 1.431 |
| 1920×1080 | 1.042 |
| 1366×768 | 0.707 |

Clamped to `[0.7, 1.8]`. Below ~1280×720 it floors at 0.7 and the page scrolls rather than shrinking into illegibility. **Widths were left alone deliberately** — every column was already fluid; only the vertical axis was ever short.

Two traps found while building it:

1. **Measure against `documentElement.clientHeight`, NOT `window.innerHeight`.** `innerHeight` counts the space a horizontal scrollbar occupies, so fitting to it lands the content a scrollbar's width too tall → vertical scrollbar → steals width → horizontal scrollbar → the two feed each other and the page ends up scrolling in both axes. `clientHeight` is the real content box.
2. `getBoundingClientRect()` reports **real (post-zoom)** pixels; `clientWidth`/`clientHeight`/`offsetWidth` report **logical (unzoomed)** ones. `<html>` is not zoomed (the zoom is on `body`), so a rect measured on content is directly comparable with `documentElement.clientHeight`. Mixing the two silently is the root of most of the bugs in this session.

### Real long-standing bug found: Chart.js mis-sizes every canvas whenever `--ui-scale` ≠ 1

Chart.js reads its container in **real** pixels and writes that number as the canvas's **logical** CSS width. The error is exactly the scale factor. Evidence from the DOM: a `1727px`-wide card held a `1554.3px` canvas at scale 0.9 — `1727 × 0.9`.

**This predates this session and was invisible**, because at a fixed 0.9 the canvas is too *small*, which merely leaves a margin inside the card. Above 1.0 the same error inverts: the canvas is *wider* than its card, and since `.panel` is `min-width: 0` it does not stretch the card — it paints its legend straight over the neighbouring chart's axis and drags the page's `scrollWidth` past the window. Symptom seen on screen: the Energy Demand legend ("Cooking", "Miscellaneous") colliding with Energy Supply's rotated `Mtoe` title and its `1,500`/`1,000` labels.

Three fixes were tried; only the last is sound:

1. `chart.resize()` inline, right after setting the scale — measures a container whose `zoom` has not reflowed yet and oversizes the canvas the *other* way (axis labels landing outside the card).
2. `chart.resize()` deferred a frame, still with `responsive: true` — better but **a race**. Chart.js's `ResizeObserver` answers every size change *including ours*, re-applying its own mis-measurement on top of the correction; which one landed last was timing-dependent, and roughly **1 load in 5** rendered overflowing. Do not go back to this.
3. **Shipped:** all four `new Chart(...)` sites create charts with `responsive: false` via a `newSizedChart()` helper that sizes them in the same turn (no wrong first frame), and `sizeChartToContainer()` owns sizing from then on. With Chart.js's observer off there is no competing writer, and results became byte-identical across runs.

`sizeChartToContainer()` details that matter:

- Target size is `wrap.getBoundingClientRect() / scale`, **not** `wrap.clientWidth`. Both nominally give the logical size, but `clientWidth` read in the same turn as a `zoom` change can still answer from the pre-change layout — observed as `1727` for a container that was really `1181`, sizing the canvas 546px over its card.
- `chart.options.devicePixelRatio = (window.devicePixelRatio || 1) * scale`. A canvas bitmap must be sized in **device** pixels, and `zoom` is a multiplier on top of `devicePixelRatio` that Chart.js cannot see: it asks the platform, gets 1, and allocates a bitmap 1:1 with the logical width, which the browser then stretches over `width × scale` real pixels — **visibly blurry charts** (reported as "the charts are too blurry"). Below 1.0 the same error downscales instead, which is effectively supersampling and looks fine, which is the other reason the old fixed 0.9 hid all of this. After the fix: a `1172.1px × 380px` box carries a `1490 × 483` bitmap at 3440.
- `applyResult()` also calls it on a `requestAnimationFrame` after rendering, because charts built from data that arrives *after* the fit passes were otherwise never corrected. Hanging this off the fit's own timers was tried and is not enough — a recalc slower than the last timer left its charts overflowing.

### Where this lives in `dashboard.js` (call map)

All of it is appended at the end of the file, after `renderSankey()`:

- **`fitUiScale()`** — the measure-and-iterate loop: max 6 passes, clamped to `UI_SCALE_MIN`/`UI_SCALE_MAX` = `[0.7, 1.8]`, with a `0.995` safety factor so rounding can't summon the scrollbar the fit is trying to avoid. Returns early on the Energy Flows view. Schedules the chart-correction passes below; deliberately does **not** resize charts inline.
- **`finishFit(scale)`** — calls `resizeChartsToContainers()`, then does it again on the next frame and reports. The repeat is not superstition: Chart.js answers our resize with an observer callback of its own, and the second call is the one that survives it.
- Correction passes fire at `requestAnimationFrame`, `150ms` and `600ms` after a fit (`fitUiScale._settle` / `fitUiScale._settleLate`, both `clearTimeout`-guarded so repeated fits don't stack timers). Each pass is idempotent, so the extra ones cost a measurement.
- **`resizeChartsToContainers()`** → **`sizeChartToContainer(id)`** for each entry in the pre-existing `charts` registry.
- **`newSizedChart(id, ctx, config)`** — wraps `new Chart(...)` at all four creation sites, registers into `charts`, and sizes in the same turn so there is no wrong first frame under `responsive: false`.
- **`reportUiFit(scale)`** — writes the `data-ui-fit` attribute described under **Verified** below.
- **`refitViewport()`** = `fitUiScale()` plus a Sankey re-render when Energy Flows is active; bound to `window.resize`.
- **Tab and sub-tab clicks bind `fitUiScale` directly, NOT `refitViewport`.** Those listeners are registered after the existing view-switching ones, so the active view has already changed by the time they run, and the Energy Flows switch handler re-renders the Sankey itself — going through `refitViewport` there would render it twice.
- Initial load: `setScenario(1)`, then a fit on `requestAnimationFrame` and again on `document.fonts.ready` (a webfont swapping in changes measured text height, and with it the fitting scale — which is why the scale used to vary 1.257–1.272 between runs at 3440 before the Chart.js sizing was made deterministic).

### ⚠️ Do not give any element a height derived from `--ui-scale`

The Insights card was first given `max-height: calc((100vh / var(--ui-scale)) - 2 * var(--page-top))` plus `overflow-y: auto`, for "scroll internally if the text runs long". **This hung the page outright** at 3440×1297 while working fine at 1366×768.

`fitUiScale()` computes `--ui-scale` *from* the content height, so any height that reads `--ui-scale` back closes the loop — the two chase each other and layout never settles. It does not degrade gracefully; whether it converges depends on the numbers, so it looks perfectly reasonable until some window size hangs the browser. Any cap on such an element must be a plain px value, independent of both the scale and the viewport. (Note this is the *second* time a `max-height: calc(100vh / var(--ui-scale))` on this same rail has had to be removed — see the previous session's rail bottom-alignment bug. Uncapped is correct here: `renderInsights()` emits at most two groups and a handful of lines.)

### Insights: left-hand full-bleed blue column → right-hand card

Asked to move it to the right of the page and make it "a proper box in a slightly corporate modern way instead of being very monotonous".

- `ui/pages/base.py`: the `<aside id="pathway-rail">` now comes **after** `.page-main`, so it is second in the DOM as well as second in the grid — it reads after the charts it comments on.
- `.page-grid` is now `minmax(0, 1fr) 268px` with `align-items: start`. The negative `margin-left` that existed solely to bleed the old blue column off the left edge of the window is **gone**, so both sides sit on the normal page inset.
- `.pathway-rail` is a card in the same language as `.panel`/`.stat-card` (white, 1px `--line`, 12px radius, soft shadow), `align-self: start` so it is content-height rather than stretching to match whatever chart is beside it, and `sticky` so it stays in view. Its identity is carried by detail rather than a wash of colour: an accent hairline across the top (clipped by the card's own `overflow: hidden`, so it needs no corner values), a tinted `--accent` tile around the lightbulb icon, and a rule under the header. The group label ("BASE STATE") is a pill chip now — the header rule already does the dividing.
- The inner colours were `rgba(16,17,20,…)` mixes chosen to sit on the old blue panel; on white they resolve to the existing `--muted`/`--line` tokens, so the card no longer carries a private palette. **The white-on-blue contrast note from the previous session no longer applies** — that background is gone.
- The right column now has empty space below the card (inherent to a content-height box). Flagged to the user, not "fixed".

### Footer copy corrected

`© 2023 NITI AAYOG | DESE ACPET | (Best viewed in 1920 x 1080 resolution, scale: 100%) | … | VIDEO`
→ `© 2026 NITI AAYOG | ACPET | DOWNLOADS: ONE PAGER DOCS | IESS V3.0 EXCEL`

2023→2026, "DESE ACPET"→"ACPET", resolution note removed (the UI now fits itself, so there is no blessed resolution left to advise), `VIDEO` link removed, no orphaned `|`. Comments in `dashboard.css` and `dashboard.js` that referenced that note as present tense were updated to read as history.

### Base layer beige  **[SUPERSEDED later the same session — the whole palette moved onto EU-Calc's white/grey/green/blue; see that section below]**

`--bg: #f6f6f4` → `#F4EFE3`. Ground only — cards, panels and bands keep their own surfaces (verified by sampling rendered pixels). `--muted` was darkened `#6a707c` → `#666c78` alongside it: small muted text sits directly on that ground in places (`.sankey-legend`, `.pathway-chip-label`), and beige is a darker ground than the old near-white, which dropped contrast to 4.34:1 — under the 4.5 threshold this project already tunes to (cf. the `--deck-muted` note). The new value restores 4.60:1 and only improves muted text on white.

`--bg` is also the hover fill for the masthead menu button and drawer items plus the new Insights chip, so those pick up the same warm tint — consistent by design, not leftovers.

**Left alone deliberately** (user said base layer, not the boxes): the Custom Pathways band `--deck-bg: #EBEBE8` and the pill-tab container `#e6e6e2` are still neutral greys and now read slightly cool against the beige. The original CSS says that warm-paper-vs-neutral-grey split is intentional. Warming them to ~`#EAE4D6`/`#E8E1D3` was offered and not actioned.

### Real bug fixed: a bundled row's ceiling was `min()` of its levers, so capped levers held their siblings back. **This supersedes the `row_max = min(...)` fix recorded in the 2026-09-06→09-08 entry.**

Reported from the UI: Buildings bundles 6 levers, of which only `lv40` "Growth of floorspace" caps at 3; the other five go to 4. The shared row was rendered with `row_max = min(...)` = **3**, so dragging the Buildings row could never set its five uncapped levers above 3. The previous session introduced that `min()` deliberately (reasoning: "the row can't offer a level any of its levers can't actually take") — the reasoning was backwards, because the *row* is not a lever, and `setLeverLevel()` in `dashboard.js` has always clamped each lever to its own `data-max` on write.

**The rule now is `max()`:** the row spans the widest range any member supports, and each member saturates at its own ceiling. Offering a level some member can't take is safe precisely because nothing downstream trusts the row.

Blast radius, measured off the rendered page rather than assumed — only **two** of the 13 sub-sector rows bundle levers with differing caps:

| Row | Lever caps | Old row max | New row max |
|---|---|---|---|
| Buildings | `lv40`=3, `lv41`-`lv45`=4 | 3 | **4** |
| Industry | `lv46`-`lv48`=4, **`lv49`=5** | 4 | **5** |

**Industry was silently broken the other way** and nobody had reported it: "Fuel Switching Choices - Iron and Steel" (`lv49`) supports **level 5** in the Control sheet, and a `min()` row of 4 meant level 5 was unreachable from the group control. It now renders 5 stops. This was not part of the original request — flagged to the user as a visible consequence of applying one consistent rule. The 11 homogeneous rows are byte-identical (Costs stays 3, all four of its levers cap at 3; "Growth of the Economy" stays 3, single lever).

**`updateLeverRow()` needed a matching change**, or every Buildings row at level 4 would have worn the "mixed" ring forever. It previously read the row back as `allSame ? values[0] : round(average)`. Two problems once a row can exceed a member's cap:

- The average mis-reports the row's position. `[3,4,4,4,4,4]` averages to 3.83 → 4 by luck; a row with more capped levers would not be so lucky (`[2,2,2,4,4,4]` averages to 3 when the user set 4).
- A lever sitting at its own ceiling is **saturated, not out of step**, and shouldn't read as a mixed row.

It now computes `target = Math.max(...values)` for the position, and treats the row as in-step when `values.every((v, i) => v === Math.min(target, caps[i]))` — i.e. mixed is reported only when some lever is below the target *and* below its own cap, which is exactly the flyout-edited case that ring is for. Caps are read per-lever from each hidden input's `data-max`.

**Verified** (this one is properly covered, unlike the tab sweep above):

- The row/saturation arithmetic was extracted into a standalone Node script and asserted, rather than eyeballed — 15 assertions over both real cap vectors: dragging Buildings to 1/2/3/4 and Industry to 1/2/3/4/5 each yields the expected member values, expected thumb position and no mixed ring; genuine mixes (`[3,1,4,4,4,4]`, and a capped lever forced *below* its cap) still report mixed; homogeneous rows behave exactly as before.
- Rendered ceilings re-parsed from the served HTML for all 13 rows: only Buildings (3→4) and Industry (4→5) moved, `data-max`, the range input's `max` and the tick count agreeing in each.
- End-to-end through `/recalc`, which is what proves the level was genuinely unreachable before and does real work now:

  | Buildings row | `lv40` | total_demand | Buildings 2047 |
  |---|---|---|---|
  | baseline (all levers 1) | 1 | 2201.98 | 210.44 |
  | 3 (the old ceiling) | 3 | 2133.42 | 146.36 |
  | **4 (new)** | 3 (clamped) | **2099.82** | **114.95** |

- Also confirmed the UI's clamp cannot diverge from the model's: posting `lv40=4` (out of range) returns byte-identical output to `lv40=3`, so the server clamps the same way the client does.
- Visual check at 3x on the DEMAND box: Buildings now shows 4 tick stops like its Transport/Cooking siblings, Industry shows 5.

**Noticed, not fixed** (no instruction to): two Industry lever names arrive mojibaked from the workbook read — `Fuel Switching Choices <?> Cement` / `<?> Iron and Steel`, an en-dash decoded with the wrong codec somewhere in `levers.py`'s read path. It is visible to users in the flyout, so worth a look.

### Levers restyled, and the effort ramp single-sourced (it had already drifted)

Asked to make the levers "look classy... premium and corporate" instead of cheap, and to change their colour.

**The colour complaint turned out to be a real inconsistency, not taste.** `LEVEL_FILL[0]` was a bright cyan `#29B6C7`, while every *other* level-1 indicator in the interface — the Predefined-scenarios dot, the pathway chip, the deck's top rule — used slate `#9AA3B2`. Since every lever defaults to level 1, a lever at rest was the only cyan thing on screen. The ramp existed as **eight scattered hex literals** across `sidebar.py`, `base.py` and `dashboard.css`, which is how that drift happened unnoticed.

It is now **one definition**: `--lvl-1`..`--lvl-5` in `dashboard.css`'s `:root`, referenced by the lever fill/thumb, the preset dots, the pathway chip, the deck's `::before` rule, the active preset button, the Insights direction badges and two `--group-accent` values. `sidebar.py`'s `LEVEL_FILL` now emits `"var(--lvl-N)"` strings rather than hex — `paintLever()` drops the chosen entry straight into the `--lg-lever-color` custom property, and a custom property may hold a `var()` reference, so it resolves at use. Verified by sampling rendered pixels: the level-1 thumb ring reads exactly `#8D96A5`, so the indirection resolves rather than silently falling back to nothing.

Ramp deepened and desaturated — electric blue and mint read as consumer-tech; navy and forest green read as institutional:

| Level | Was | Now |
|---|---|---|
| 1 | `#29B6C7` cyan (levers) / `#9AA3B2` slate (everywhere else) | `#8D96A5` slate |
| 2 | `#5468DC` indigo | `#4A6B9A` steel blue |
| 3 | `#3B62FF` electric blue | `#234978` navy |
| 4 | `#00C08B` mint | `#1C6B57` forest green |
| 5 | `#00C08B` (duplicate) | `#1C6B57` (duplicate — only `lv49` reaches it) |

`.insights-arrow-down`'s label colour went from `#04231a` to `#fff`, since the new level-4 green is dark enough that near-black text on it would fail contrast.

**Geometry.** What actually read as cheap was three stacked effects, all removed: a radial-gradient "bubble" thumb with a specular highlight, a saturated glow halo ringing the thumb permanently, and a heavy `inset 0 1px 3px rgba(0,0,0,.22)` pressed into the track. Now: a 4px flat track (hairline instead of inset), 2px tick dots at 26% ink, and a 14px **white disc with the level's colour as an inset ring** — which keeps the ramp legible at that size and reads as a precision control rather than a toy. Hover and drag deepen the shadow and thicken the ring instead of scaling the thumb up (a control that grows under the cursor being the other tell). The `is-mixed` state is now a hollow thumb — the ring without a settled centre — replacing a triple-ring halo.

**Knowingly reversed an earlier decision:** the comment above `LEVEL_FILL` argued for cyan on the grounds that a slate level 1 "read as unset". That reasoning was written for the *dark* control deck; the deck is a light panel now, and the cyan matched nothing else. The consequence to be aware of is that with every lever at level 1 by default, the deck at rest is now entirely monochrome (slate rings, empty tracks). It reads as minimum-effort rather than disabled — the white core, defined ring and drop shadow carry that — but if it ever reads as "unset" again, the dial is `--lvl-1` alone, not a return to cyan.

**Verified:** a standalone harness (`scratchpad/ramp.html`) that links the *real* stylesheet off the running server and renders the lever markup at every level of both a 4-level and the 5-level row, plus the hover/drag/mixed states — screenshotted and inspected at 2x, because the live page only ever shows level 1 at rest and clicking through presets headlessly isn't wired up. Also re-checked the deck header in the live page: top rule gradient, all four preset dots and the active-button fill all pick the new tokens up.

### Removed the dashed "changed series" stroke from the charts

A series whose values moved since the baseline was redrawn with `borderColor: "#a0761f", borderWidth: 3, borderDash: [4, 2]` in `stackedAreaDatasets()`. So moving any lever scribbled a thick amber dotted line along the boundary of every band it affected — drawn over the data, on the chart you had just changed in order to read, and re-applied on every recalc. Reported as "the annoying part is it's creating a dotted line over it".

Every series now draws identically (`borderColor: color, borderWidth: 0.5`, no dash); there is no longer any code path that can produce a dashed stroke. `changedSeries` was dropped from `stackedAreaDatasets()`'s signature — it had exactly one caller — while `renderStackedChart()` still receives it, because the **card-level badge is deliberately kept**: `.changed-note` / `opts.changedCardId` still marks which chart moved ("CHANGED SINCE BASELINE"), which conveys the same fact without drawing on the data. Offered to remove that too; not asked for.

Verified: no `borderDash` remains anywhere in `dashboard.js` outside the comment recording what was removed, and the page still renders with `data-ui-fit` written (that attribute is set at the end of the fit passes, so its presence proves the module executed past the changed call site rather than throwing). The behaviour after an actual lever move is guaranteed by construction rather than observed — the styling is now unconditional, with no changed/unchanged branch left — since driving a lever and re-screenshotting isn't wired up headlessly.

### Custom Pathways recoloured warm, boxes inverted to raised cards, and a false accessibility claim corrected

The deck band was the last cool surface left after `--bg` went beige — a neutral grey (`#EBEBE8`) originally chosen to contrast the page's "warm paper", which worked while the page was near-white `#f6f6f4` and stopped working once it was beige. Asked for "a different colour but it should be complementing the overall colour".

Two changes, one asked for and one structural:

1. **Warm, not grey.** The band and its tokens are now the same warm family as `--bg`, a step deeper so the band still separates from the page.
2. **Boxes lighter than the band, not darker.** `--deck-panel` used to be *darker* than `--deck-bg`, making each group an inset well. Inverting that makes them raised cards on a ground — which is exactly the relationship the whole top half of the page already uses (white cards on `--bg`), so the deck now belongs to one system instead of being its own idiom. It also puts most of the deck's small print on the lightest surface available, which is what made the contrast work out.

| Token | Was | Now |
|---|---|---|
| `--deck-bg` (band) | `#EBEBE8` cool grey | `#E9E0CE` warm sand |
| `--deck-panel` (group boxes) | `#E0E0DC` (darker than band) | `#F8F4EC` (lighter than band) |
| `--deck-line` | `#C6C6C1` | `#D8CDB8` |
| `--deck-muted` | `#6E7580` | `#5D646F` |

**A comment in this stylesheet was claiming something untrue.** `--deck-muted`'s comment read "darkened until the deck's small print clears 4.5:1 against --deck-panel" — the value it described actually measured **3.51:1** on the old panel and **3.89:1** on the old band. Both fail. Rather than carry that forward, contrast was computed properly (a throwaway script over the real token values, `scratchpad/contrast.py`) and `--deck-muted` solved against the **band**, which is the darker of the two surfaces this text lands on and therefore the binding constraint — not the panel the old comment named.

Measured, all five pairs the deck actually renders:

| Pair | Before | After |
|---|---|---|
| `--deck-muted` on panel (`.lg-box-avg`, 10px) | 3.51:1 ✗ | **5.44:1** ✓ |
| `--deck-muted` on band (`#status-chip`, 10.5px) | 3.89:1 ✗ | **4.55:1** ✓ |
| `--deck-ink-2` on panel (`.lg-subcat-title`, 12.5px) | 6.65:1 | 8.02:1 |
| `--deck-ink` on panel (`.lg-box-title`) | 13.68:1 | 16.51:1 |
| page `--bg` vs band (surface separation) | 1.04:1 | 1.14:1 |

**Two lever details had to follow the panel change**, both because they had been tuned against a grey panel that is now near-white:

- `.lg-lever-track` was a literal `#CFCCC4`; it is `var(--deck-line)` now, so re-colouring the band carries the track with it. The track has to stay visible on `--deck-panel` in the deck *and* on white in the flyout rail.
- `.lg-lever.is-mixed .lg-lever-thumb` filled its centre with `--deck-panel` to read as "hollow". With the panel near-white that made the mixed state indistinguishable from the ordinary white thumb — it uses `--deck-bg` (the band tone) now, which is clearly neither white nor the track. Confirmed distinct in the harness at 3x.

**Still cool, still outstanding:** `.pill-tabs` and `.subtabs` keep a `#e6e6e2` grey container, which is now the only cold surface on the page. Out of scope for a request about Custom Pathways; flagged to the user.

### Chart series palette moved onto EU-Calc's own colours

Asked whether we could use the palette from an EU-Calc "Nickel demand" screenshot. The honest first finding, measured rather than eyeballed, was that **we were already using that palette** — ours and theirs matched in hue, saturation and lightness almost pair for pair (their Industry green `#A5E0A0` vs our Buildings `#8FDBA0`; their Other rose `#EC6E85` vs our Agriculture `#F2718D`; their Energy violet `#8B7FD4` vs our Nuclear `#8E8FD8`, and so on). What actually made their chart look cleaner is layout, not colour: one full-width chart with a few big flat bands, against our two side-by-side charts carrying 7-9 stacked bands each in half the width. That was put to the user with three options (fix defects / adopt theirs / re-lay-out the charts); they chose to adopt EU-Calc's hexes, so that is what shipped.

Six sampled anchors: `#A5E0A0` green, `#EC6E85` rose, `#9FC5EE` blue, `#8B7FD4` violet, `#F5A623` orange, `#3C3C3C` near-black. Six colours can't dress 9+ stacked supply series, so the remainder are extensions in the same register (a yellow, teal, cyan, light violet, two greys).

**Assignment keeps the fuel conventions** an energy reader relies on, which the anchors mostly allow anyway: coal darkest, oil orange, gas rose, nuclear violet, hydro blue, bio/others green, solar yellow, wind teal. **One deliberate departure from EU-Calc's own mapping:** they paint *Transport* near-black, but Transport is a thin sliver in their chart and the single largest band in our Energy Demand chart — a near-black block over a third of the plot reads as a hole punched in it. Transport takes the teal extension and the near-black goes to Coal, where a heavy band is both conventional and semantically right.

**The extensions were solved, not picked.** EU-Calc's register is a tight lightness band, and a first eyeballed pass clustered badly — five pairs of series sharing a chart landed within 0.03 relative luminance, i.e. indistinguishable in greyscale or under some colour-vision deficiencies, and *worse than the palette being replaced*. A short search over candidate teals/yellows/cyans/greys maximised the smallest luminance gap between any two series drawn on the same chart:

| | worst co-occurring gap |
|---|---|
| old palette | 0.023 (Agriculture vs Telecom, Natural gas vs Nuclear) |
| first eyeballed pass at the new one | 0.011 |
| **shipped** | **0.053** |

The binding pair is now rose against violet — both EU-Calc anchors — so 0.053 is the floor without abandoning them. Hue and the per-series marker shapes (`SERIES_SHAPE`) carry the rest.

**Three things had to change with it, all of which would otherwise have rotted quietly:**

1. **In-band label colour was a hard-coded list.** `bandLabelPlugin` decided white-vs-black text via `["#6E7681", "#3E9C93", "#57B3A9"].includes(ds.bandColor)` — three hexes from the old palette. Under a new palette every dark band falls off that list and gets black text on a near-black fill, so the label just vanishes. Replaced with `isDarkColor()`, a real WCAG relative-luminance computation (threshold 0.42), so any future palette works. Confirmed in the render: Coal's label comes out white, Industry's black.
2. **The positional fallback `COLORS` still held the old hexes.** Any series `SERIES_COLOR` doesn't name falls back to it, which would have mixed two palettes on the same chart. Rewritten in the new register and ordered so consecutive positions are far apart in luminance.
3. **Six single-colour bar charts passed old hexes inline** (`renderBarChart(..., { color: "#8E8FD8" })` and friends on Emissions/Indicators). Remapped to the new register; a grep confirms no old-palette hex survives anywhere outside the comment that records what was removed.

Verified: full-page render at 1920x1080 with the fit still clean (`chartOverflowPx=0`, no page overflow), and the Energy Supply chart inspected at 2x — the area fill's own alpha gradient (0.95 -> 0.72) softens `#3C3C3C` into a dark slate rather than flat black, which is why the largest band reads as heavy-but-intentional. Flagged to the user that softening Coal is a one-value change if that mass is still too much.

### Whole chrome palette moved onto EU-Calc's white/grey/green/blue — the beige lasted one iteration

Follow-on from the chart-palette change: the user meant the *page*, not just the series colours — "the overall background colour as white as same as EU calculator", and Custom Pathways in their colour too. So the beige ground added earlier the same session was replaced. Worth knowing if you are reading the beige rationale above: it is superseded, not still in force.

EU-Calc's chrome is a white content plane inside light grey framing, with green and blue as its only accents. Mapped onto this layout as: light cool grey **ground**, white **cards**, a slightly deeper grey **deck band** with near-white boxes, neutral dark grey footer, and one blue accent.

| Token | Beige iteration | Now |
|---|---|---|
| `--bg` (ground) | `#F4EFE3` | `#F4F6F7` |
| `--line` | `#e2e2dd` | `#E1E4E7` |
| `--muted` | `#666c78` | `#5F6875` |
| `--accent` | `#1f4bff` | `#29699A` |
| `--deck-bg` | `#E9E0CE` warm sand | `#EAECEE` |
| `--deck-panel` | `#F8F4EC` | `#FAFBFB` |
| `--deck-line` | `#D8CDB8` | `#D8DCE0` |
| `--deck-muted` | `#5D646F` | `#5F6875` |
| footer | `#3F4247` (was navy `#1b1d29`) | neutral dark grey, text `#C3C7CC`, links `#8FC2E8` |

The raised-card relationship in the deck (boxes lighter than the band) was kept — only the hues moved.

**The effort ramp went to their grey/blue/green** rather than staying navy/forest, and this needed solving, not picking:

| | Level 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Before | `#8D96A5` slate | `#4A6B9A` steel | `#234978` navy | `#1C6B57` forest |
| Now | `#9AA2AC` grey | `#5B96C9` light blue | `#29699A` blue | `#25702C` green |

Two measured constraints the values satisfy:

- **Luminance darkens monotonically** (0.357 > 0.283 > 0.129 > 0.122), so the level still reads if colour is lost. A first pass at this register did *not* — grey came out lighter than the blue two steps up, which makes the fill bar unreadable as a scale.
- **`--lvl-3` and `--lvl-4` carry white text** (`.cdh-pathway-btn.active`, the Insights direction badges), so both clear 4.5:1 against white: 5.86:1 and 6.12:1. The obvious brighter picks failed outright — `#2E7EB8` gave 4.38:1 and a `#4E9F4E` green only **3.28:1**, which is what caught it.

Everything else was validated in the same pass (a throwaway script over the real token values): muted on ground 5.20:1, muted on card 5.64:1, deck-muted on band 4.76:1 and on panel 5.44:1, deck-ink-2 on panel 8.48:1, footer text 5.94:1, footer links 5.31:1. No pair regressed.

**Also brought across, so nothing was left in the old register:** the `.pill-tabs` / `.subtabs` / `.year-tabs` containers (`#e6e6e2`, the last warm-grey surface and one flagged twice before), the drawer header, the lever focus ring, `.stat-note-accent`, the Insights card's accent hairline and icon tile tint, and the three `--group-accent` literals for the deck's group dots (`#5C7CFF` / `#6B7FE8` / `#7E8899` -> `var(--lvl-3)` / `var(--lvl-2)` / `var(--lvl-1)`).

**Five comment blocks were rewritten**, not left behind — they described the beige ground, the "warm, not grey" deck and the navy/forest ramp, all in the present tense. Stale comments of exactly that kind have caused real errors in this project twice this session (the `--deck-muted` 4.5:1 claim that measured 3.51:1, and the `LEVEL_FILL` comment arguing for a cyan), so they are corrected with the measured numbers whenever a value moves.

**Deliberately left warm:** `.changed-note` keeps its amber `#a0761f`. It is the only non-grey/blue/green thing on the page now, but it is a status marker whose whole job is to break out of the palette, and it renders rarely.

Verified: full page at 1920x1080 with the fit clean (`chartOverflowPx=0`, no overflow either axis); surfaces sampled from the render (`#EAECEE` band, `#FAFBFB` boxes, `#3F4247` footer) to confirm the tokens actually landed; and the lever harness re-shot to check the ramp across all five levels plus the drag/mixed states, since the live page only shows level 1 at rest.

### Then the grey went too: the page is one white plane

Immediately after the change above, the remaining light grey read as dull ("those subtle grey is making the entire pannel dull"), so the ground and the Custom Pathways band both went to `#FFFFFF`. Nothing separates a card, panel or lever box from the page now except its own 1px border — which is EU-Calc's arrangement as well; their content plane is white throughout.

| Token | Grey iteration | Now |
|---|---|---|
| `--bg` | `#F4F6F7` | `#FFFFFF` |
| `--deck-bg` | `#EAECEE` | `#FFFFFF` |
| `--deck-panel` | `#FAFBFB` | `#FFFFFF` |

Custom Pathways is delimited by its own 2px accent rule (`.control-deck-h::before`) and its heading rather than by a fill.

**`--bg` was quietly doing two jobs**, which only became visible when it went white: it was the page ground *and* the faint fill behind `.menu-btn:hover`, `.drawer-item:hover` and the Insights group-label chip. On a white ground those three become invisible. Split out as **`--surface-2: #F1F3F5`** — a tint for interactive fills that no longer tracks the ground. Any future "make the background X" only has to touch `--bg`.

`.lg-lever.is-mixed`'s thumb centre now points at `--surface-2` too. That fill has had to be re-pointed on *every* deck surface change this session (`--deck-panel` -> `--deck-bg` -> `--surface-2`) because it kept being aimed at whichever surface happened to be off-white at the time; what it actually wants is "a tint that is definitely not white", which is what `--surface-2` names.

Verified: contrast on the new white ground (muted 5.64:1, deck-muted 5.64:1, deck-ink-2 8.80:1 — all improved, since white is the lightest possible ground), the fit still clean, and the rendered surfaces sampled to confirm they are genuinely `#FFFFFF` (ground between the KPI cards, the area above the deck heading, the deck boxes and the cards) rather than merely looking it.

### Deck band back to grey (EU-Calc's control sidebar), row labels made clickable, flyout animation enriched

Three asks in one go, after the all-white pass: Custom Pathways should take the grey of EU-Calc's left control sidebar; a bundled row should open its sub-levers when its **name** is clicked, not only its chevron; and the open/close should feel more animated.

**1. Deck band grey again — and this is not a contradiction of the white ground.** EU-Calc puts its controls on light neutral grey against a white content plane, which is exactly the relationship here: page ground stays `#FFFFFF`, the deck band is `#EDEDED`, and the group boxes stay **white** on it. Neutral greys (equal R/G/B) rather than the cool-tinted ones used earlier, because theirs are neutral and it reads cleaner against pure white. `--deck-line` `#D4D4D4`. Keeping the boxes white also keeps the deck's small print on the lightest surface (5.64:1 rather than 4.82:1 on the band).

**2. `.lg-subcat-title` is now a click target for the flyout.** `initLeverFlyouts()`'s per-chevron handler was extracted into a `toggle()` closure and bound to both the chevron and the row's title; rows with a chevron get an `.is-expandable` class from JS, which CSS hangs the pointer cursor and hover colour off.

Bound to the title specifically, **not the whole row** — the row also carries the lever, and a click there has to reach the slider rather than being intercepted. The chevron stays exactly as it was: it holds `aria-expanded`, it is the keyboard path, and it is what the arrow animates on, so the title adds a pointer affordance without a second tab stop.

**3. Animation.** The rail's width transition eased with `cubic-bezier(.16,.84,.44,1)` over `.34s` (was `.28s ease`), and — since `display` can't be transitioned — the panel now has a real entrance *animation*: fade plus an 8px slide-in, with its rows following in a stagger (`.06s` to `.26s`, capped at six because Renewable Generation has eight levers and a per-row delay would leave the last ones visibly late). The chevron's rotation got the same easing. A `prefers-reduced-motion: reduce` block turns all of it off.

**Verification here is behavioural for the first time this session.** Node 24 ships a global `WebSocket`, so a ~120-line dependency-free Chrome DevTools Protocol driver (`scratchpad/cdp.js`) can launch headless Chrome, click things and read the DOM back — which finally covers the interaction paths that `--dump-dom` and `--screenshot` alone could not. What it confirmed:

- Clicking the **Transport label** (not the chevron): rail opens to 271px, the flyout that opens is `Transport` with its 6 rows, the chevron's `aria-expanded` flips to `true`, and the page gains no horizontal scroll.
- Clicking the same label again closes it — the toggle works both ways.
- Clicking a **chevron** still opens its own row independently (`Buildings`).
- The row is marked `is-expandable` and its title computes `cursor: pointer`.
- The animation genuinely runs rather than snapping: sampled across the transition, panel opacity went `0.66 -> 0.94 -> 1.00` while its transform slid `-2.72px -> -0.49px -> 0`, and the first row trailed it at `0.04 -> 0.58 -> 0.93 -> 1.00` — i.e. the stagger is doing what it claims.
- Band colour verified from the render by tallying a scanline inside the deck: `#EDEDED` dominant, `#D4D4D4` borders, `#FFFFFF` boxes, page ground still white above it.

One honest limit found while measuring: the rail's *width* transition only plays when opening from closed. Switching straight from one open row to another re-adds `is-open` in the same tick, so the rail never collapses in between — arguably the better behaviour, but it means the width easing is not what you see when moving between rows; the panel fade/stagger is.

**This driver is worth reusing.** The "only the All Energy tab was driven automatically" caveat that stands against every other entry in this session is now fixable with it — tab switching, preset buttons and lever drags are all reachable this way.

### Deck de-boxed: headings over plain text rows, all deck text black

Last step on Custom Pathways: drop the white group boxes, keep the group name as a heading with its rows listed plainly beneath, and make every text in the deck black. This is the reference sidebar's own arrangement — heading, then rows, no card chrome.

- `.lg-box` lost its `--deck-panel` fill, its `--deck-line` border and its radius (`background: transparent; border: 0; padding: 2px 2px 4px`), and `.lg-box-head` lost the rule under the heading.
- `.lg-subcat-row` lost its `border-top` separators; spacing alone separates rows now (padding `4px` -> `5px`). Flyout rows deliberately **keep** their rules — those sit on a white popup panel where a list still needs the help.
- Seven text tokens in the deck moved to `--deck-ink`: the group heading, the `avg N.N` badge, the row label, the row count, the chevron, `#status-chip` and `.cdh-pathway-label`. `--deck-ink-2` and `--deck-muted` are no longer painted in the deck at all.
- **The lever track needed a value of its own.** It was `var(--deck-line)` (`#D4D4D4`), which worked while the track sat on a white box; with the boxes gone it sits on the band itself (`#EDEDED`), where `#D4D4D4` was too faint to read as a track. Now `#C9C9C9`, which holds up both on the band and on white in the flyout rail.
- `--deck-panel` still exists and is still painted — by the Predefined-scenarios buttons and the flyout rail, both of which are genuinely controls/popups rather than group containers.

Verified through the CDP driver rather than by eye, since "all text black" is a claim about computed values: all seven elements compute `rgb(20, 22, 26)`, and `.lg-box` reports `background: rgba(0,0,0,0)` with `border-top-width: 0px`, `.lg-subcat-row` `border-top-width: 0px`. A colour tally over the whole deck region confirms it is one plane — `#EDEDED` about 30,000 sampled pixels against 4,700 white (the flyout popup and the preset buttons). Label-click, toggle-closed and chevron-click all still pass, and the fit stays clean (`chartOverflowPx=0`, no overflow); note the fitted scale rose from 1.042 to 1.061, since dropping the box padding made the deck slightly shorter and fitUiScale took up the slack.

### Sub-lever panel and chart containers de-boxed too — which exposed a real overflow bug

**Sub-levers.** `.lg-rail` dropped its white fill, border and radius, `.lg-flyout-head` its bottom rule, `.lg-flyout-row` its separators, and its text moved to `--deck-ink`. The flyout is a genuine 5th column of the lever grid rather than an overlay, so with the card gone it simply reads as one more column on the band.

**Chart containers.** `.panel`, `.card` and `.sankey-card` all lost `background: #fff`, their `--line` border and their radius. On a white page that border was the only thing drawing the box, so the charts now sit directly on the page — title, plot, nothing around them, as the EU-Calc reference presents its own. Padding stays, since it is what keeps a plot off the page inset and off its neighbour. `.chart-duo`/`.chart-grid` gaps went `10px -> 26px`: the borders had been doing the work of separating two side-by-side charts, and the gutter has to take that over.

**The bug this surfaced.** With the boxes gone the deck got shorter, `fitUiScale()` took up the slack (scale 1.042 -> 1.061), and the page lost its spare headroom — at which point opening any sub-lever list pushed the footer off the bottom of the window. Measured: `--ui-scale` fitted against a deck whose lever columns are 186px tall, while `.lg-rail-col`'s own ceiling was **260px**. Opening a flyout therefore grew the deck by the difference and the page overflowed by 61px.

This was latent before today — the rail has always been capped at 260px — but the fit had enough slack to absorb it until the padding came out. It is exactly the class of thing a still screenshot of the default state never shows.

Fixed in `initLeverFlyouts()`: before opening, the rail's `max-height` is set to the tallest non-rail `.lg-col`, so an open flyout can never make the deck taller than it already is. Longer lists scroll inside the rail, which is what `.lg-rail`'s `overflow-y: auto` was always there for. `offsetHeight` is used deliberately rather than `getBoundingClientRect()` — it reports logical (unzoomed) pixels, which is the space a CSS `max-height` is expressed in; a rect would be real pixels and would need dividing by `--ui-scale`, the same trap documented in `sizeChartToContainer()`.

Verified with the CDP driver across four states — nothing open, Transport (6 levers), Renewable Generation (8, the longest list), and closed again: `overflowY: 0` and `footerVisible: true` in every one, with the deck height constant at 267px and the rail capping at 186px. Label-click, toggle-close and chevron-click all still pass.

**Consequences worth knowing:**

- A capped rail clips its last row mid-height when the list is longer than the columns beside it (Buildings' 6 and Renewable Generation's 8 both do). It reads as "there is more, scroll" rather than as a mistake, but it is a half-row.
- The **KPI stat cards** (`.stat-card`) still have their boxes — the request was the graphs, and four naked figures with no separation is a different decision. Same for the **Insights card**, which is a panel in its own column rather than a chart container.

### Hairline under the tab row

Removing the card and panel borders left nothing between the tab row and the data beneath it — the row read as floating above the charts rather than heading them. `.tab-row` now carries `border-bottom: 1px solid var(--line)` with `padding-bottom: 9px` / `margin-bottom: 11px`.

It spans the **main column only**, not the window: the Insights card is a sibling grid column whose top aligns with this row, so a full-bleed rule would cut straight across it. Verified as exactly that — the rule's width equals `.page-main`'s and its right edge stops at or before the card's left edge. The masthead's own `border-bottom` and the deck's accent rule are the same device at the page's other two seams.

Verified on the Electricity tab (the one in the user's screenshot) through the CDP driver: computed `border-bottom` `0.94px rgb(225,228,231)` — 1px logical at the fitted scale — `ruleSpansMainColumn: true`, `ruleStopsBeforeInsights: true`, `overflowY: 0`, footer visible.

**This run also closed a caveat that stood against most of this session's entries.** Driving the tab switch (clicking `Electricity` and re-measuring) exercises the tab-switch refit path for the first time: the fit re-ran to `scale=1.064` with `chartOverflowPx=0` and no overflow on a tab whose chart heights differ from All Energy's. The "only the All Energy tab was driven automatically" limitation is now a matter of running the sweep, not of tooling.

### The tab-row rule gets its own colour: `--rule-accent`, a faded denim

The divider was `var(--line)`, the same neutral grey as every border on the page. It is the one rule that separates navigation from data, so it is allowed to read as deliberate: `--rule-accent: #8FAEC9`, a faded-denim blue related to the blues already in the ramp (`--lvl-2`, `--accent`) without being either, so it looks chosen rather than borrowed.

Kept as a token because this is exactly the kind of value that gets dialled. How much a 1px hairline reads against white, measured:

| | | vs white |
|---|---|---|
| old neutral `--line` | `#E1E4E7` | 1.28:1 |
| a whisper | `#A8C0D8` | 1.88:1 |
| **shipped** | **`#8FAEC9`** | **2.32:1** |
| more presence | `#7396B5` | 3.11:1 |
| `--lvl-2`, for scale | `#5B96C9` | 3.16:1 |

Verified on the rendered page: computed `border-bottom` `0.94px rgb(143, 174, 201)`, still spanning the main column only and stopping before the Insights card, `overflowY: 0`.

**Cleaned up while in there:** `:root` had accumulated *two stacked comment blocks* for the deck tokens, one from the warm/raised-card iteration and one from the EU-Calc grey iteration, and the older one still claimed the deck matched "the relationship the whole top half of the page already uses (white cards on --bg)" — which stopped being true when the cards lost their boxes and the ground went white. Merged into one block that also records what `--deck-panel` is still for (the Predefined-scenarios buttons and the flyout rail) now that the group lists no longer paint it.

### Masthead takes the footer's band colour; logos enlarged and plated

The masthead was white with a `--line` bottom border; it now uses the footer's own `#3F4247`, so the page is bracketed by one dark grey band top and bottom (the same colour the menu drawer's header already used, and the same arrangement EU-Calc has). The bottom border went with it — the colour change is the edge. Title to `#fff` (10.2:1 on the band), logos `26px -> 36px`.

**The menu button had to be re-treated.** It was `color: var(--muted)` with a light-grey hover fill and an `--accent` focus ring, all chosen for a white bar — mid grey on `#3F4247` would have all but vanished. Now `#C3C7CC` with a translucent white wash on hover (`rgba(255,255,255,.14)`, the same treatment the drawer's close button uses on its dark header) and a `#8FC2E8` focus ring.

**Both logos are plated** — a white pad with rounded corners — for two different reasons, and the second one corrected an assumption:

- **NITI**: the mark is `#01238E` navy plus gold (read out of the SVG), which all but disappears on `#3F4247`. Recolouring an official emblem to white via a CSS filter would throw its gold away, so it gets a plate instead.
- **ACPET**: `ACPET_LOGO_White.png` sounds like a white-ink variant cut for exactly this background. It isn't. The PNG header says colour type 2 — **RGB with no alpha channel**, and no `tRNS` chunk — so its white is painted in and it can never be transparent. It rendered as a hard white rectangle on the dark band. Plating it makes that rectangle deliberate and matches the one opposite.

Worth noting the file name misled here in the useful direction: had the header stayed white, that logo would have gone on looking fine while being un-themeable. If a real transparent or white-ink ACPET asset turns up, the plate on that one can come off.

Verified: masthead and footer sample the same `#3F4247` from the render; fit still clean after the taller band (`scale=1.039`, `footerBottom=984` against `clientH=985`, `chartOverflowPx=0`, no overflow in either axis); flyout label-click, toggle and chevron all still pass.

### The deck's top rule became a real GHG gauge

`.control-deck-h::before` was a decorative 2px effort-ramp gradient. It now carries information: the pathway's own 2047 emissions as a blue band with the figure on it, which is what EU-Calc does with its cumulative-emissions bar. Same job as before (it marks where data ends and controls begin) plus a number.

- Markup: `.cdh-emissions` as the deck's first child — `GHG 2047` label, a track with a fill and a value that rides the fill's head, and the scale maximum at the right. Full-bleed via negative margins cancelling the deck's own top and side padding, the same technique `.site-banner` uses against `.page`.
- `renderEmissionsBar(data)` in `dashboard.js`, called from `applyResult()` beside `renderInsights()`, drives it from `data.emissions_2047_total` — the very field the "EMISSIONS 2047" KPI card reads, so the two can't disagree.
- `emissions_2047_total` arrives in **megatonnes** (9635 for the least-effort pathway, shown as 9.6 GtCO2), hence the `/1000`.

**The 0-10 GtCO2 scale is measured, not invented.** Clicking through the four presets gives 9.6 / 5.3 / 2.8 / 2.0 GtCO2, so 10 Gt is the next round number above the worst case the model produces: a do-nothing pathway starts the band nearly full and it empties as ambition rises.

A note on how that figure was established, because the first attempt was wrong: hand-posting `{lv1..lv51: N}` to `/recalc` returned 9.64 / 5.62 / 3.24 / 2.11 — close, but not what the app shows, because a hand-built payload has to guess the lever ids and quietly gets a different vector. Driving the actual preset buttons is what produced the numbers above. Prefer driving the UI over reconstructing its requests.

**Two things the first attempt got wrong, both caught by looking at the render:**

1. The band was a 7px hairline with a 10.5px label inside it. Type taller than its own band spills onto the light track above and below, where white text is simply invisible. The track is 15px now — a band has to be taller than the type it carries.
2. Label placement was `pct > 82`, a guessed percentage. It is measured instead: `trackPx * pct / 100 > label.offsetWidth + 18`. The track's width varies with the window and with `--ui-scale`, so the same percentage is a different number of pixels on different screens — the guess would have flipped the label at the wrong moment on some.

Verified by driving all four preset buttons: the band reads 9.6 / 5.3 / 2.8 / 2.0 GtCO2 at fills of 96.4 / 53.5 / 27.6 / 20.2 %, each **exactly matching the EMISSIONS 2047 KPI card**, with the label inside the fill in every case and `overflowY: 0` throughout. `aria-label` on the container states the value and the scale, since the bar itself is not readable by a screen reader.

Possible follow-on, not done: the fill is a fixed `--accent` blue. It could take the effort ramp instead (green when emissions are low, blue when high), which would make the gauge legible at a glance without reading the number — but the request was specifically a blue line.

### Ranade as the type face, and the GHG gauge recoloured denim-and-green

**Ranade** (Fontshare / Indian Type Foundry) is now the display and body face, loaded from `api.fontshare.com` alongside the existing Google Fonts link. Space Grotesk and IBM Plex Sans stay *behind* it in the stacks rather than being deleted — Fontshare is a second CDN to depend on, and if it is unreachable the UI should fall back to the faces it was tuned against instead of to a system default. **IBM Plex Mono keeps every mono role**: Ranade has no monospace cut, and the deck's small-caps labels and figures rely on fixed advance widths.

Verified it genuinely renders rather than silently falling back, which is the failure mode worth checking with a webfont: all three faces (400/500/700) report `status: loaded`, `document.fonts.check('700 40px Ranade')` is true, and the same string measures **787px in Ranade against 605px in the fallback** — where 605px is also exactly what a `serif` control measures, since unavailable families collapse to identical metrics. That width difference is the proof.

Ranade is wider than Space Grotesk, so the content grew and `fitUiScale()` absorbed it: the fitted scale moved 1.039 -> 1.000. Nothing to do — that is the mechanism working.

**The gauge** is now a denim box with a light-green meter, on the reasoning that the thing being measured is greenhouse gas:

| part | value | why |
|---|---|---|
| box | `--gauge-box` `#C8E1F5` | a light blue (see the note below on why it stopped tracking the denim) |
| meter (fill) | `#A5E0A0` | the chart palette's own green, so the gauge matches the emissions data |
| unfilled track | `#5E82A8` | deeper denim — see below |
| labels + readout | `--deck-ink` | dark, in every position |

Two contrast findings shaped it:

1. **Labels stay dark on the denim.** White on `#8FAEC9` is 2.32:1 — a fail. Dark ink is 7.82:1.
2. **The unfilled track could not stay pale.** With a pale track, light green on pale blue measured **1.17:1** — you could not see how full the meter was, which defeats the object of a meter. Candidates were measured and `#5E82A8` chosen: 2.63:1 against the green fill while still reading as a recess inside the lighter box (1.73:1). The value readout also had to drop its white (which worked on the old blue fill and would have failed on green) — dark ink is 11.9:1 on the meter and 4.5:1 if it lands on the track.

The box was lightened one step after a first pass at full-strength denim: 20% toward white, written as a `color-mix()` against `--rule-accent` rather than a fresh hex, so it keeps tracking that token if the rule colour is dialled. Lightening it improved two things and cost nothing that matters — dark labels on the box went 7.82:1 -> **9.41:1**, and the unfilled track reads more clearly as a recess inside it (1.73:1 -> **2.09:1**). The green-vs-box figure drops to 1.26:1, which is immaterial: the meter is bounded by the track, so it only ever meets the box at the track's rounded ends, and there the two differ by hue rather than luminance.

The box went through two more steps after the full-strength denim. First a lighter tint of it, written as `color-mix(in srgb, var(--rule-accent) 80%, #fff)` (= `#A5BED4`) so it would keep tracking the rule colour. Then asked for a light blue outright — and a mix could not deliver that: taking a *desaturated* denim toward white only ever yields a pale grey-blue, never a light blue that still reads blue. So the box became its own token, `--gauge-box: #C8E1F5`, and deliberately no longer tracks `--rule-accent`. Lightening improved the numbers at each step: dark labels on the box 7.82 -> 9.41 -> **13.41:1**, and the unfilled track reading as a recess inside it 1.73 -> 2.09 -> **2.97:1**.

**Bordered** in the tab rule's own denim (`1px solid var(--rule-accent)`), which ties the page's two blue rules together and, more practically, gives the band a real edge — without it the box's top simply changed colour against the white page with nothing marking the boundary. It reads 1.71:1 against the box it outlines, 2.32:1 against the white above and 1.98:1 against the deck grey below; `#7FA3C4` or `#6E93B8` are recorded in the CSS comment if it ever wants more weight. The side borders land on the window edges, the band being full-bleed.

Verified from the render at each step. The final check was a vertical pixel slice down through the band, which shows the whole intended stack in order: `#FFFFFF` page, then one row of `#8FAEC9` border, then `#C8E1F5` box, then 15 rows of `#A5E0A0` meter, then box again — i.e. every layer landing at its declared colour and height. Alongside that: border computed `1px rgb(143,174,201)` on all four sides, box `rgb(200,225,245)`, track `rgb(94,130,168)`, meter `rgb(165,224,160)`, readout dark, `9.6 GtCO₂` still agreeing with the KPI card, and `overflowY: 0` / `overflowX: 0` with the band still spanning the full window width.

### Files touched this session

`ui/pages/base.py`, `ui/pages/sidebar.py`, `ui/static/css/dashboard.css`, `ui/static/js/dashboard.js`, plus a new `tools/devtools/cdp_driver.js` (headless-Chrome click driver, see Verified). No Python model/engine code, no lever or output logic — nothing in this session touched a number the model produces.

Stale comments were refreshed alongside the code rather than left contradicting it: the `.page-grid` block comment (it described the rail as the *left*, full-bleed column), the top-of-file layout comment (it claimed `.pathway-rail` scrolls internally — it no longer does), and the two comments referring to the footer's resolution note in the present tense.

### Verified

- Headless Chrome (Playwright is not installed in this environment; `chrome.exe --headless=new` with `--dump-dom` and `--screenshot` was used instead) at 3440×1297, 2560×1440, 1920×1080, 1366×768 and 1280×720, several runs each.
- Pass criteria were measured, not eyeballed — `dashboard.js` writes a `data-ui-fit` attribute on `<html>` (kept in the code; it is small and makes this class of bug diagnosable): `scale`, `footerBottom`, `clientH`/`scrollH`, `clientW`/`scrollW`, `chartOverflowPx`. `scrollH == clientH` and `scrollW == clientW` means no scrollbar in that axis; `chartOverflowPx == 0` means no canvas is wider than its card. Final state: clean on all of the above at every size, identical across repeated runs.
- The legend-collision fix was confirmed by drawing marker lines on a screenshot at the *measured* canvas and panel edges, after pixel-reading a downscaled screenshot produced two wrong conclusions in a row. Worth repeating that technique: measure, annotate, then look.
- Blur fix confirmed by A/B of the same region magnified 3× (before: smeared glyph edges; after: crisp) plus the DOM showing a `1490×483` bitmap for a `1172×380` box.
- **Only the All Energy tab was driven automatically.** Tab switching goes through the same `fitUiScale` path but was not clicked through headlessly — worth a manual pass over the other 8 tabs.

### Environment notes (cost real time this session)

- Headless Chrome was initially run **against the user's live Chrome profile**, which crashed the network and GPU processes (`exit_code=-1073741819`) and produced spurious hangs that looked like page bugs. Always pass a throwaway `--user-data-dir`. Leftover headless processes also pile up and starve the machine — clean them up by matching `--headless` in the command line, never by killing `chrome.exe` broadly (the user's own browser was 33 of 35 processes at one point).
- Screenshotting at 3440×1297 remains flaky in this environment even isolated (GPU process dies); `--dump-dom` at that size is reliable, so measurement was done at 3440 and visual review at 1920.
- The "duplicate app.py processes" confusion resurfaced: a single logical server shows as **two** PIDs on this machine, because the Windows Store `python.exe` shim is the parent of the real interpreter. Killing the "non-listening" one kills the server. Check the parent/child relationship before concluding there are duplicates.

### Sankey made interactive: full-route tracing, flow animation, entry reveal

The Sankey was a static render with name-only tooltips. Three additions, in `renderSankey()` plus styles:

**1. Full-route tracing (the substantial one).** Hovering a node lights the *whole chain* it belongs to — everything upstream that feeds it and everything downstream it feeds, walked transitively — and dims everything else to 7% opacity. That is the question this diagram exists to answer: hover "Electricity Grid" and you see every fuel that produced it and every sector that consumed it at once. `trace()` is a breadth-first walk over the `sourceLinks`/`targetLinks` that d3-sankey already hangs on each node, in both directions. Hovering a *link* instead highlights just that link and its two endpoints.

Measured on the real graph: hovering Electricity Grid (20 direct connections) lights **39 of 67 links** and dims 28 — i.e. the transitive walk finds 19 links beyond the node's own, which is the whole point.

**2. Flowing dashes.** Each link has a dashed white overlay copy, invisible until its route is traced, whose `stroke-dashoffset` scrolls via CSS animation — a traced route reads as *running* rather than merely coloured. An overlay rather than dashing the real link, since dashing that would punch gaps in the band itself. Nothing on the page animates until the reader asks by hovering; a permanently shimmering diagram is unreadable.

**3. Richer tooltips.** A link now reports its value *and* its share of the source's throughput ("42% of Coal"); a node reports its throughput and in/out counts.

**4. Entry reveal.** Links draw themselves in left-to-right, staggered by `node.depth`, so the picture builds along the direction the energy flows. Nodes and labels fade in behind them.

#### A bug I introduced, shipped, and nearly reported as working

The first version of the reveal used d3 transitions. **`.transition()` does not exist on this page** — `base.py` loads d3-array, d3-path, d3-shape, d3-selection and d3-sankey, and d3-transition is not among them nor bundled with any of them (confirmed: `typeof d3.select('body').transition === "undefined"`).

The failure was quiet and asymmetric: the TypeError threw on the **first** link inside `.each()`, which left that one link stranded with its reveal dash applied — *invisible* — and aborted the loop before any other element was touched, so the node/label animations never ran either and everything else looked normal. One missing flow out of 67, no visible animation, no obvious breakage.

Worse, my first verification *cited the bug as evidence of success*: I measured "links carrying a `stroke-dashoffset`" and read `1` as "one link mid-reveal", when it was the one stranded link. Two later attempts to fix it (`.on("end interrupt cancel")`, then a `setTimeout` sweep) both failed because both were treating a symptom of a TypeError as a transition-lifecycle problem. Dumping the actual stranded element — `Coal Production -> Coal`, offset equal to its full path length — is what identified it.

**Reimplemented in CSS animations**, which needs no new dependency (pulling in d3-transition would mean five more CDN scripts for its own unbundled deps) and, more importantly, cannot fail this way: `animation-fill-mode: forwards` *declares* the end state, so no interrupted re-render, missed event or thrown handler can leave a flow hidden. In a data diagram an invisible flow is a data-integrity bug, not a cosmetic one, so it is worth designing out rather than guarding against.

One more measurement trap on the way: after the CSS rewrite the same probe reported all 67 links "stranded", because it was reading the `stroke-dashoffset` **attribute** — which stays at full length by design while the animation drives the *computed* value to 0. Verification has to read `getComputedStyle`.

Verified through the CDP driver with real mouse events: 230ms in, all 67 links are partly drawn with a max computed offset of 953 (the reveal genuinely running, confirmed against a screenshot showing flows stopping mid-air); settled, `allRevealed: true` with max offset 0; after deliberately interrupting reveals by switching year four times in 500ms, still `allRevealed: true`; tracing lights 39/dims 28 with 39 flow overlays animating (`animationName: sankey-flow`), traced stroke-opacity 0.68 against dimmed 0.07; moving the pointer away clears every class and hides the tooltip; **zero console errors**.

#### Found, not fixed: Energy Flows overflows the window by 253px

`fitUiScale()` deliberately skips this tab (`#sankeySvg`'s height is viewport-derived, so measuring it would chase a moving target). Nothing else compensates, and the height is `clamp(400px, calc((100vh / var(--ui-scale)) - 300px), 820px)` — where `-300px` is a hard-coded allowance for "everything else on the page". Today's work grew everything else: taller masthead logos, the new GHG gauge band, the tab-row rule, Ranade's larger metrics. The allowance is now wrong by about 250px, so the footer sits off-screen and the deck is clipped on this tab.

The right fix is not a bigger magic number: size the SVG from *measured* sibling heights (masthead + tab row + toolbar + legend + deck + footer subtracted from `clientHeight`) in JS. That also removes the `100vh / --ui-scale` dependency, which is what forced this tab out of the fit in the first place — so the tab could then join it. Left alone here because it touches the fit system rather than the Sankey.

### Two fixes: the "Base state" chip is gone, and the Sankey tooltip no longer gets sliced

**"BASE STATE" removed from Insights.** The idle message was preceded by a group-label chip, which put a heading over a single sentence — and which levers sit where is already legible in the Custom Pathways deck below it. The changed-state groups ("Levers changed" / "Impact on results") keep their labels, because those genuinely separate two lists. Verified: the idle panel now reports zero `.insights-group-label` elements and no "base state" text, with the sentence itself intact.

**The Sankey tooltip was being clipped by its own container.** `.sankey-card` carried `overflow: hidden`, and the tooltip is absolutely positioned *inside* that element — so any hover near an edge had the box sliced off, which is exactly what the user's screenshot showed at the left edge ("full route traced" cut in half).

The `overflow: hidden` was there to clip the Sankey to the card's rounded corners. The card lost both its radius and its background in the de-boxing earlier this session, so the rule had stopped doing anything except cutting up tooltips — removed.

Removing the clip alone would have let the tooltip hang outside the plot instead, so `showTip()` now also clamps it: it is centred on the cursor via `translate(-50%, -120%)`, so the position is constrained to keep the whole box (plus an 8px margin) within the card's width, and it flips to *below* the cursor when there is not room above. `offsetX`/`offsetY` are used deliberately — they are layout (logical) pixels, the same space as the `left`/`top` they are written into, whereas `clientX`/`clientY` would be real pixels and would need dividing by `--ui-scale`.

Verified by driving real mouse events onto the extreme nodes and comparing the tooltip's rect against the card's: at the **leftmost** node (Coal Production, the reported case) it now sits 8px inside the left edge; at the **rightmost** (Losses) 8px inside the right; at the **topmost** it flips below. `fullyInsideCard: true` in all three, and the card computes `overflow: visible`.

### Where this session actually landed (read this first)

This entry records a long UI session in the order things happened, and several decisions were **superseded within it** — the page ground went near-white -> beige -> light grey -> pure white, and the deck band went cool grey -> warm sand -> grey -> white -> grey again. Reading the steps in order will mislead. The final state:

**Sizing.** No `max-width` anywhere on `.page`. `--ui-scale` is a *starting* value only; `fitUiScale()` measures the footer's own bottom edge and scales the whole UI until it meets the bottom of the window, per tab. Charts are `responsive: false` and sized from `sizeChartToContainer()`, including a `devicePixelRatio` multiplied by the scale so canvases stay sharp. **Never give an element a height derived from `--ui-scale`** — it closes a loop with the fit and hangs the page at some window sizes.

**Palette — final values.**

| Role | Token | Value |
|---|---|---|
| Page ground | `--bg` | `#FFFFFF` |
| Interactive tint (hovers, chips) | `--surface-2` | `#F1F3F5` |
| Borders | `--line` | `#E1E4E7` |
| Tab-row rule | `--rule-accent` | `#8FAEC9` denim |
| GHG gauge box | `--gauge-box` | `#C8E1F5` light blue, bordered `--rule-accent` |
| Accent | `--accent` | `#29699A` |
| Effort ramp 1-4 | `--lvl-1..4` | `#9AA2AC` / `#5B96C9` / `#29699A` / `#25702C` |
| Deck band / boxes / lines | `--deck-bg` / `--deck-panel` / `--deck-line` | `#EDEDED` / `#FFFFFF` / `#D4D4D4` |
| Masthead + footer band | (literal) | `#3F4247` |
| Type | `--head` / body / mono | Ranade / Ranade / IBM Plex Mono |

Chart series colours are EU-Calc's own six anchors plus same-register extensions, in `SERIES_COLOR` (`dashboard.js`).

**Structure.** Insights is a card in a right-hand column (not a left rail). The tab row carries a denim bottom rule spanning the main column only. Chart containers (`.panel`, `.card`, `.sankey-card`) and the deck's group boxes and sub-lever panel have **no box chrome** — borders and spacing do the separating; the KPI `.stat-card`s and the Insights card are the only boxes left. The deck's top edge is a working GHG gauge, not a decorative rule. `--deck-panel` survives only for the preset buttons and the flyout rail.

**Two behaviours that are easy to break again.** A bundled lever row's ceiling is `max()` of its members' caps, never `min()`, and `updateLeverRow()` treats a lever pinned at its own cap as *saturated*, not mixed. An open sub-lever flyout is capped to the tallest lever column, or it grows the deck and pushes the footer off-screen.

**Open issue.** Energy Flows overflows the window by ~253px: `#sankeySvg`'s height subtracts a hard-coded 300px allowance for the rest of the page, and the rest of the page grew today. Fix by measuring sibling heights instead — which would also let that tab rejoin `fitUiScale()`. See the Sankey section.

**What is verified and what is not.** Everything visual was checked at 1366x768 / 1920x1080 / 2560x1440 / 3440x1297 by measurement (`data-ui-fit` on `<html>` reports scale, footer position, overflow and chart overhang). Interactions — flyout open/close, preset buttons, tab switching — are verified through `tools/devtools/cdp_driver.js`. **Not verified:** a full sweep of all 9 tabs and both sub-tab groups after the de-boxing and palette changes, and the Sankey on Energy Flows (the one view that opts out of the fit). That sweep is the obvious next task and the driver makes it cheap.
