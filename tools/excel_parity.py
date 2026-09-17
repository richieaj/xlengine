"""excel_parity.py — does the engine reproduce Excel's own saved numbers?

An .xlsx stores, for every formula cell, BOTH the formula and the value Excel
last computed for it. That is a free oracle: evaluate the formula ourselves and
compare. This tool does that across the whole workbook.

    python tools/excel_parity.py --sheet "Critical Minerals"
    python tools/excel_parity.py --json out.json --baseline tests/parity/baseline.json

WHY THIS EXISTS, AND WHY IT IS NOT golden_master.py
---------------------------------------------------
golden_master asserts engine-now == engine-at-capture. It is a REGRESSION gate
and it cannot catch a formula that was always wrong — if the engine has been
returning a confident zero since the day the sheet was written, the golden
baseline records that zero and stays green forever.

This asserts engine == EXCEL. Different claim, different failure caught.
CLAUDE_CODE_PROJECT_CONTEXT.md:110 already draws the distinction: "'0 engine
gaps' and 'matches Excel' are two different claims — a formula can evaluate
without error and still be numerically wrong." This is the tool for the second.

The bug that prompted it: workbook_model detected formulas with
`isinstance(c.value, str)`, but openpyxl returns ARRAY formulas as an
ArrayFormula object. 87 cells on 'Critical Minerals' were filed as literal data
holding a Python object, their formulas never ran, and downstream SUM() over a
non-numeric contributed 0. An entire mineral-demand block returned zeros with
zero exceptions and zero engine gaps. Nothing that asked "did it error?" could
have found it.

Supersedes xlcompiler/count_flows.py (one sheet, one column, ~120 rows).
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "xlcompiler"))

from openpyxl.utils import get_column_letter  # noqa: E402

from compiler.engine import ModelEngine  # noqa: E402
from compiler.evaluator import ERROR  # noqa: E402

DEFAULT_WORKBOOK = os.environ.get(
    "IESS_WORKBOOK",
    os.path.join(ROOT, "workbook", "IESS2047_Version_3.0.xlsx"),
)
DEFAULT_BASELINE = os.path.join(ROOT, "tests", "parity", "baseline.json")

# Excel's own error values, stored as strings in the cached-value stream. A cell
# where EXCEL itself failed is a workbook defect, not an engine defect — it gets
# its own category and never gates the exit code. (This is how the broken C46 on
# 'Critical Minerals' presented before it was fixed in the sheet.)
EXCEL_ERRORS = frozenset({
    "#VALUE!", "#REF!", "#N/A", "#DIV/0!", "#NUM!", "#NAME?", "#NULL!",
    "#GETTING_DATA", "#SPILL!", "#CALC!",
})

# Categories that mean the ENGINE is wrong. Everything else is informational.
DEFECT = (
    "ZERO_COLLAPSE", "TYPE_MISMATCH", "NUMERIC_MISMATCH", "SIGN_FLIP",
    "STRING_MISMATCH", "ENGINE_GAP",
)
INFO = (
    "EXCEL_ERROR", "CIRCULAR_SEEDED", "BOOL_COERCION", "STRING_WHITESPACE",
    "SKIPPED",
)
ALL_CATEGORIES = ("MATCH",) + DEFECT + INFO


def classify(excel, engine, rel_tol, abs_tol, circular_seed=0):
    """Compare one cell. Returns (category, rel_err_or_None).

    ORDER MATTERS in this function; each early return exists for a reason.

    The ERROR sentinel (evaluator.py:36-46) defines __bool__ -> False and
    __float__ -> 0.0. So `if not engine`, `engine == 0`, or float(engine) would
    all silently file an engine gap as a legitimate zero — the exact silent-zero
    failure this tool exists to catch, one level up. It is therefore tested
    FIRST and with `is`.
    """
    # 1. Excel itself failed here. Workbook defect, not ours.
    if isinstance(excel, str) and excel.strip().upper() in EXCEL_ERRORS:
        return "EXCEL_ERROR", None

    # 2. Engine gap. `is`, before anything that could coerce it.
    if engine is ERROR:
        return "ENGINE_GAP", None

    # 3. Booleans BEFORE numerics: in Python True == 1, so a bool/int mix would
    #    otherwise pass the numeric comparison and hide a real type difference.
    e_bool, g_bool = isinstance(excel, bool), isinstance(engine, bool)
    if e_bool or g_bool:
        if e_bool and g_bool:
            return ("MATCH", None) if excel == engine else ("STRING_MISMATCH", None)
        other = engine if e_bool else excel
        if isinstance(other, (int, float)):
            ref = excel if e_bool else engine
            return ("BOOL_COERCION", None) if bool(other) == ref else ("TYPE_MISMATCH", None)
        return "TYPE_MISMATCH", None

    excel_num = isinstance(excel, (int, float))
    engine_num = isinstance(engine, (int, float))

    # 4. Excel produced a number, the engine did not. This is the shape an
    #    ArrayFormula-style regression takes (engine returns None or an object).
    if excel_num and not engine_num:
        return "TYPE_MISMATCH", None

    if excel_num and engine_num:
        # 5. The headline case: Excel had a real value, engine collapsed to
        #    exactly zero. Called out separately from NUMERIC_MISMATCH because
        #    it is the signature of a dropped formula rather than a precision
        #    or algorithm difference.
        if engine == 0 and abs(excel) > abs_tol:
            return "ZERO_COLLAPSE", 1.0

        # Circular chains: the engine seeds them deterministically, Excel with
        # iterative calc saved a converged number. Neither a match nor our bug.
        if engine == circular_seed and abs(excel) > abs_tol and circular_seed != 0:
            return "CIRCULAR_SEEDED", None

        diff = abs(excel - engine)
        scale = max(abs(excel), abs(engine))
        # BOTH tolerances are required. Values here span 0.008 (technology
        # shares) to 4.7e8 (mineral demand in kg): a relative-only test is
        # meaningless near zero, an absolute-only test meaningless at 1e8.
        if diff <= max(abs_tol, rel_tol * scale):
            return "MATCH", 0.0
        rel = diff / scale if scale else float("inf")
        if (excel > 0) != (engine > 0) and diff > abs_tol:
            return "SIGN_FLIP", rel
        return "NUMERIC_MISMATCH", rel

    # 6. Engine produced a number where Excel did not.
    if engine_num and not excel_num:
        return "TYPE_MISMATCH", None

    if excel is None and engine is None:
        return "MATCH", None

    if isinstance(excel, str) and isinstance(engine, str):
        if excel == engine:
            return "MATCH", None
        if excel.strip() == engine.strip():
            return "STRING_WHITESPACE", None
        return "STRING_MISMATCH", None

    if excel is None or engine is None:
        return "TYPE_MISMATCH", None

    return "SKIPPED", None


def iter_target_cells(model, sheets, exclude, sample, seed):
    """Every cell that HAS something to compare: a formula we can run, and a
    value Excel left behind. That filter is the sheet selector — no hardcoded
    sheet list, so a newly added sheet is covered automatically."""
    cells = [
        c for c in model.cells.values()
        if c.formula is not None and c.value is not None
        and (not sheets or c.sheet in sheets)
        and c.sheet not in exclude
    ]
    cells.sort(key=lambda c: (c.sheet, c.row, c.col))
    if sample and sample < len(cells):
        cells = random.Random(seed).sample(cells, sample)
        cells.sort(key=lambda c: (c.sheet, c.row, c.col))
    return cells


def compare(eng, cells, rel_tol, abs_tol, progress=True):
    per_sheet = defaultdict(Counter)
    defects = []
    seed = getattr(eng.ev, "_circular_seed", 0)
    last_sheet = None
    t0 = time.time()

    for c in cells:
        if progress and c.sheet != last_sheet:
            if last_sheet is not None:
                print(f"    {last_sheet:<30} done ({time.time()-t0:.1f}s)",
                      file=sys.stderr, flush=True)
            last_sheet = c.sheet
        a1 = f"{get_column_letter(c.col)}{c.row}"
        try:
            engine_value = eng.read_cell(c.sheet, a1)
        except Exception as e:  # a raise here is itself a finding, not a crash
            per_sheet[c.sheet]["ENGINE_GAP"] += 1
            defects.append({
                "sheet": c.sheet, "ref": a1, "category": "ENGINE_GAP",
                "formula": c.formula, "excel": c.value,
                "engine": f"raised {type(e).__name__}: {e}", "rel_err": None,
            })
            continue

        cat, rel = classify(c.value, engine_value, rel_tol, abs_tol, seed)
        per_sheet[c.sheet][cat] += 1
        if cat in DEFECT:
            defects.append({
                "sheet": c.sheet, "ref": a1, "category": cat,
                "formula": c.formula, "excel": c.value,
                "engine": repr(engine_value) if not isinstance(engine_value, (int, float, str)) else engine_value,
                "rel_err": rel,
            })

    if progress and last_sheet is not None:
        print(f"    {last_sheet:<30} done ({time.time()-t0:.1f}s)", file=sys.stderr, flush=True)
    return per_sheet, defects


def cell_key(d):
    return f"{d['sheet']}!{d['ref']}"


def formula_hash(formula):
    return hashlib.sha1((formula or "").encode("utf8")).hexdigest()[:12]


def render_table(per_sheet):
    cols = ["MATCH", "ZERO_COLLAPSE", "TYPE_MISMATCH", "NUMERIC_MISMATCH",
            "SIGN_FLIP", "ENGINE_GAP", "EXCEL_ERROR", "CIRCULAR_SEEDED", "SKIPPED"]
    head = ["zero-col", "type", "numeric", "sign", "gap", "xl-err", "circ", "skip"]
    print(f"\n{'sheet':<32}{'compared':>9}{'match':>9}" + "".join(f"{h:>9}" for h in head))
    print("-" * (32 + 18 + 9 * len(head)))
    rows = sorted(per_sheet.items(),
                  key=lambda kv: (-sum(kv[1][c] for c in DEFECT), kv[0]))
    totals = Counter()
    for sheet, counts in rows:
        totals.update(counts)
        compared = sum(counts.values())
        if sum(counts[c] for c in DEFECT) == 0 and len(rows) > 12:
            continue  # keep the table readable; clean sheets fold into TOTAL
        print(f"{sheet[:31]:<32}{compared:>9}{counts['MATCH']:>9}" +
              "".join(f"{counts[c]:>9}" for c in cols[1:]))
    compared = sum(totals.values())
    print("-" * (32 + 18 + 9 * len(head)))
    print(f"{'TOTAL':<32}{compared:>9}{totals['MATCH']:>9}" +
          "".join(f"{totals[c]:>9}" for c in cols[1:]))
    return totals


def render_top(defects, top):
    if not defects:
        return
    rank = {c: i for i, c in enumerate(DEFECT)}
    worst = sorted(defects, key=lambda d: (rank.get(d["category"], 99),
                                           -(d["rel_err"] or 0)))[:top]
    print(f"\nworst {len(worst)} of {len(defects)} defects:")
    for d in worst:
        f = (d["formula"] or "")[:72]
        print(f"  {d['sheet']}!{d['ref']}  [{d['category']}]")
        print(f"      {f}")
        rel = f"  rel_err={d['rel_err']:.3e}" if d["rel_err"] else ""
        print(f"      excel={d['excel']!r}   engine={d['engine']!r}{rel}")


def main():
    p = argparse.ArgumentParser(
        description="Compare engine output against the values Excel saved in the workbook.",
        epilog="NOTE: --sample reduces REPORT VOLUME, not work — dependencies are "
               "evaluated regardless. --sheet is the flag that actually reduces work.")
    p.add_argument("workbook", nargs="?", default=DEFAULT_WORKBOOK)
    p.add_argument("--sheet", action="append", default=[])
    p.add_argument("--exclude-sheet", action="append", default=[])
    p.add_argument("--sample", type=int)
    p.add_argument("--seed", type=int, default=20260917)
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--rel-tol", type=float, default=1e-6)
    p.add_argument("--abs-tol", type=float, default=1e-9)
    p.add_argument("--json")
    p.add_argument("--baseline", nargs="?", const=DEFAULT_BASELINE)
    p.add_argument("--update-baseline", action="store_true")
    p.add_argument("--fail-on", choices=["none", "new", "any"], default="new")
    p.add_argument("--as-app", action="store_true",
                   help="Apply ui/app.py's presentation-mode switches. Differences "
                        "under this flag are NOT evidence of an engine bug.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    if not os.path.exists(args.workbook):
        print(f"workbook not found: {args.workbook}", file=sys.stderr)
        return 2
    if args.baseline and args.sample:
        print("--baseline is meaningless with --sample (the cell set must be stable)",
              file=sys.stderr)
        return 2

    mode = calc_mode(args.workbook)
    if mode == "manual":
        print("\n" + "!" * 78)
        print("WARNING: this workbook is saved with calcMode=\"manual\".")
        print("Excel's cached values are only as fresh as the last full recalculation,")
        print("so NUMERIC_MISMATCH below may mean the WORKBOOK is stale, not the engine.")
        print("To get a trustworthy comparison: open it in Excel, press Ctrl+Alt+F9")
        print("(full rebuild), save, and re-run. ZERO_COLLAPSE and TYPE_MISMATCH stay")
        print("meaningful regardless — a dropped formula is a dropped formula.")
        print("!" * 78)

    print(f"loading {args.workbook} ...", file=sys.stderr)
    eng = ModelEngine.load(args.workbook, verbose=False)

    # NO OVERRIDES. The evaluator computes purely from the workbook's saved
    # constants, which is exactly the state Excel was in when it wrote the
    # cached values — so any difference is attributable to the engine, which is
    # the entire value of this tool. Applying lever levels would make downstream
    # cells differ LEGITIMATELY and drown the real findings in noise. Do not
    # "helpfully" add golden_master._saved_mix() here: those levels are already
    # what the formulas read off the sheet.
    if args.as_app:
        print("WARNING: --as-app applies presentation-mode switches; differences "
              "below are not necessarily engine defects.", file=sys.stderr)
        eng.set_lever("Target Year Input", "E10", 1)
        eng.set_lever("IESS V3 Main Sheet", "E12", 0)

    cells = iter_target_cells(eng.m, set(args.sheet), set(args.exclude_sheet),
                              args.sample, args.seed)
    print(f"comparing {len(cells)} formula cells with cached values ...", file=sys.stderr)

    t0 = time.time()
    per_sheet, defects = compare(eng, cells, args.rel_tol, args.abs_tol,
                                 progress=not args.quiet)
    elapsed = time.time() - t0

    totals = render_table(per_sheet)
    render_top(defects, args.top)

    # Cross-check our ENGINE_GAP count against the evaluator's own tally. These
    # count different things (we only touch cells that have a cached value), so
    # they need not be equal — but a wild divergence means one of them is wrong.
    print(f"\nengine-reported gaps: {len(eng.ev._unevaluated)}   "
          f"parity ENGINE_GAP: {totals['ENGINE_GAP']}")
    print(f"elapsed {elapsed:.1f}s")

    defect_total = sum(totals[c] for c in DEFECT)
    current = {cell_key(d): formula_hash(d["formula"]) for d in defects}

    status, new_keys, fixed_keys = "clean", [], []
    if args.baseline and os.path.exists(args.baseline) and not args.update_baseline:
        with open(args.baseline) as f:
            base = json.load(f)
        known = base.get("known", {})
        if base.get("workbook_sha256") and base["workbook_sha256"] != _sha(args.workbook):
            print("\nWARNING: baseline was captured against a DIFFERENT workbook.",
                  file=sys.stderr)
        # Per-cell keys plus a formula hash, deliberately not just counts: counts
        # alone let one new regression cancel one fix and stay green, which is
        # precisely the failure this tool exists to prevent. A changed formula at
        # a known-bad address lapses its waiver.
        new_keys = sorted(k for k, h in current.items() if known.get(k) != h)
        fixed_keys = sorted(k for k in known if k not in current)
        print(f"\nbaseline: {len(known)} known  |  NEW {len(new_keys)}  |  IMPROVED {len(fixed_keys)}")
        for k in new_keys[:args.top]:
            print(f"   NEW      {k}")
        for k in fixed_keys[:args.top]:
            print(f"   IMPROVED {k}")
        if fixed_keys and not new_keys:
            print("   (run --update-baseline to record the improvement)")
        status = "new-defects" if new_keys else "baselined"

    if args.update_baseline:
        path = args.baseline or DEFAULT_BASELINE
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "workbook": os.path.basename(args.workbook),
                "workbook_sha256": _sha(args.workbook),
                "calc_mode": mode,
                "captured": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "rel_tol": args.rel_tol, "abs_tol": args.abs_tol,
                "per_sheet": {s: dict(c) for s, c in per_sheet.items()},
                "known": current,
            }, f, indent=2, sort_keys=True)
        print(f"\nbaseline written → {path} ({len(current)} known defects)")
        return 0

    if args.json:
        with open(args.json, "w") as f:
            json.dump({
                "workbook": args.workbook, "workbook_sha256": _sha(args.workbook),
                "calc_mode": mode,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "rel_tol": args.rel_tol, "abs_tol": args.abs_tol,
                "elapsed_s": round(elapsed, 2),
                "per_sheet": {s: dict(c) for s, c in per_sheet.items()},
                "defects": defects, "status": status,
                "new": new_keys, "improved": fixed_keys,
            }, f, indent=2, sort_keys=True, default=repr)
        print(f"json → {args.json}")

    if args.fail_on == "any" and defect_total:
        print(f"\nFAIL — {defect_total} defect(s)")
        return 1
    if args.fail_on == "new" and new_keys:
        print(f"\nFAIL — {len(new_keys)} NEW defect(s) not in baseline")
        return 1
    if args.fail_on == "new" and not args.baseline and defect_total:
        print(f"\nFAIL — {defect_total} defect(s) and no baseline to compare against")
        return 1
    print("\nPASS")
    return 0


def calc_mode(path):
    """Excel's calculation mode, read from the raw OOXML.

    This decides whether the oracle can be trusted at all. Under
    calcMode="manual" the cached values are only as fresh as the last time
    somebody pressed F9 — any cell whose inputs changed since then holds a
    STALE number, and comparing against it says nothing about the engine.
    Both IESS workbooks ship as "manual", so this is the normal case here, not
    an edge case. Reported loudly rather than buried, because a parity report
    read without this caveat will indict the engine for the workbook's staleness.
    """
    try:
        import zipfile
        with zipfile.ZipFile(path) as z:
            wb = z.read("xl/workbook.xml").decode("utf8", "ignore")
        import re as _re
        m = _re.search(r'calcMode="([^"]+)"', wb)
        return m.group(1) if m else "auto"
    except Exception:
        return "unknown"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


if __name__ == "__main__":
    sys.exit(main())
