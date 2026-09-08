"""Golden-master equivalence harness.

The scaling work (see CLAUDE_CODE_PROJECT_CONTEXT.md, 2026-09-03) makes the model
faster and adds caching in front of it. The hard constraint on all of it is that **not
one output number may change**. This turns that from a promise into a test.

    python tools/golden_master.py capture --profile quick
    python tools/golden_master.py verify  --profile quick

`capture` records the full response payload for a fixed set of lever vectors; `verify`
recomputes and asserts byte-identical output, naming the first differing key path.

Deliberately drives the REAL request path: it imports ui/app.py and calls its own
`_apply_levels()`, so clamping, the E12 pin and lever-writing order are all exercised
exactly as a live request would. If that logic changes in a way that alters results, this
fails — which is the point.

Vector profiles include randomised MIXED states, not just uniform all-N ones. Uniform
states are exactly the ones that hide per-lever bugs: an all-4 request clamps six levers
to 3 identically every time, so a mistake in per-lever handling stays invisible.
"""

import argparse
import io
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "xlcompiler"))
sys.path.insert(0, os.path.join(ROOT, "ui"))

GOLDEN_DIR = os.path.join(ROOT, "tests", "golden")

# Importing app builds the engine and applies the startup mode switches. It is the same
# object a live request uses, so the harness cannot drift from production behaviour.
import app as APP  # noqa: E402
from outputs import compute_outputs  # noqa: E402

LEVER_IDS = sorted(APP.ALL_LEVER_ROWS, key=lambda k: APP.ALL_LEVER_ROWS[k])
MAXES = APP.ALL_LEVER_MAX


def _uniform(level):
    return {lid: level for lid in LEVER_IDS}


def _saved_mix():
    """The workbook's own saved lever values — the historical '1,880.65' state. Some are
    0, which _apply_levels clamps to 1; captured as-requested so the clamp is covered."""
    out = {}
    for lid, row in APP.ALL_LEVER_ROWS.items():
        cell = APP.eng.m.get_cell("Control", row, 5)
        val = getattr(cell, "value", None)
        out[lid] = int(val) if isinstance(val, (int, float)) else 1
    return out


def build_vectors(profile):
    """Deterministic, ordered list of (name, lever_vector)."""
    vectors = []

    # the four example pathways
    for lvl in (1, 2, 3, 4):
        vectors.append((f"uniform-{lvl}", _uniform(lvl)))

    vectors.append(("saved-mix", _saved_mix()))

    # boundary coverage for every lever whose max is not 4 (rows 31/40/59/60/61/62 max
    # at 3, row 49 at 5) plus a plain 1 and a deliberately over-range request that must
    # clamp identically before and after any change
    odd = [lid for lid in LEVER_IDS if MAXES[lid] != 4]
    for lid in odd:
        v = _uniform(2)
        v[lid] = MAXES[lid]
        vectors.append((f"max-{lid}", v))
        v2 = _uniform(2)
        v2[lid] = 9  # over range on purpose
        vectors.append((f"over-{lid}", v2))
    vectors.append(("all-min", _uniform(1)))
    vectors.append(("all-over", {lid: 9 for lid in LEVER_IDS}))

    n_random = {"quick": 4, "standard": 40, "full": 200}[profile]
    rng = random.Random(20260903)
    for i in range(n_random):
        vectors.append((
            f"mixed-{i:03d}",
            {lid: rng.randint(1, max(1, MAXES[lid])) for lid in LEVER_IDS},
        ))

    if profile == "quick":
        # keep the fast loop genuinely fast: presets + saved mix + a couple of boundary
        # cases + the random mixed ones
        keep = {"uniform-1", "uniform-4", "saved-mix", "all-over",
                "max-lv31", "max-lv49"}
        vectors = [(n, v) for n, v in vectors
                   if n in keep or n.startswith("mixed-")]
    return vectors


def canonical(payload):
    """Stable serialisation so a byte comparison is meaningful."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute(vector):
    """Exactly what a /recalc request does, minus Flask."""
    with APP.MODEL_LOCK:
        APP._apply_levels(vector)
        return compute_outputs(APP.eng)


def first_difference(a, b, path="", allow_new=False):
    """Report the first differing key path between two payloads.

    `allow_new` permits keys that did not exist at capture time: a key nothing read
    before cannot change any displayed number, so additive keys are safe. Every key
    that DID exist must still match exactly, and a key that has gone MISSING is always
    a failure — that is the direction which breaks a consumer.
    """
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} -> {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                if allow_new:
                    continue
                return f"{path}/{k}: missing before, present now"
            if k not in b:
                return f"{path}/{k}: present before, MISSING now"
            d = first_difference(a[k], b[k], f"{path}/{k}", allow_new)
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} -> {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    if a != b:
        return f"{path}: {a!r} -> {b!r}"
    return None


def cmd_capture(args):
    vectors = build_vectors(args.profile)
    out_dir = os.path.join(GOLDEN_DIR, args.profile)
    os.makedirs(out_dir, exist_ok=True)
    print(f"capturing {len(vectors)} vectors -> {out_dir}")
    t_all = time.perf_counter()
    for i, (name, vec) in enumerate(vectors, 1):
        t0 = time.perf_counter()
        payload = compute(vec)
        dt = time.perf_counter() - t0
        rec = {"name": name, "levers": vec, "payload": payload}
        with io.open(os.path.join(out_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            f.write(canonical(rec))
        print(f"  [{i:>3}/{len(vectors)}] {name:<16} {dt:6.2f}s")
    gaps = len(APP.eng.ev._unevaluated)
    with io.open(os.path.join(out_dir, "_meta.json"), "w", encoding="utf-8") as f:
        f.write(canonical({"profile": args.profile, "count": len(vectors),
                           "engine_gaps": gaps}))
    print(f"done in {time.perf_counter()-t_all:.1f}s; engine gaps: {gaps}")


def cmd_verify(args):
    out_dir = os.path.join(GOLDEN_DIR, args.profile)
    if not os.path.isdir(out_dir):
        sys.exit(f"no baseline for profile '{args.profile}' — run capture first")
    vectors = build_vectors(args.profile)
    print(f"verifying {len(vectors)} vectors against {out_dir}")
    failures = []
    t_all = time.perf_counter()
    for i, (name, vec) in enumerate(vectors, 1):
        path = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(path):
            failures.append((name, "no baseline file"))
            continue
        with io.open(path, encoding="utf-8") as f:
            base = json.loads(f.read())
        if base["levers"] != vec:
            failures.append((name, "vector definition changed since capture"))
            continue
        t0 = time.perf_counter()
        got = compute(vec)
        dt = time.perf_counter() - t0
        diff = first_difference(base["payload"], got, allow_new=args.allow_new)
        # The J116 shortcut must equal the chart total it replaces, on EVERY vector --
        # this is the assertion that validates it for mixed lever states, which uniform
        # all-N states cannot.
        eq = None
        chart = got.get("emissions_by_sector_chart")
        if chart and "emissions_2047_total" in got:
            a, b = round(chart["total"][-1], 2), got["emissions_2047_total"]
            if abs(a - b) > 0.005:
                eq = f"emissions_2047_total {b} != chart total {a}"
        if diff is None and eq is None:
            print(f"  [{i:>3}/{len(vectors)}] {name:<16} {dt:6.2f}s  OK")
        else:
            msg = diff or eq
            failures.append((name, msg))
            print(f"  [{i:>3}/{len(vectors)}] {name:<16} {dt:6.2f}s  MISMATCH")
            print(f"        {msg}")

    gaps = len(APP.eng.ev._unevaluated)
    print(f"\nengine gaps: {gaps} (must be 0)")
    if gaps:
        failures.append(("engine", f"{gaps} unevaluated formula cells"))
    print(f"elapsed {time.perf_counter()-t_all:.1f}s")
    if failures:
        print(f"\nFAILED — {len(failures)} problem(s):")
        for n, d in failures:
            print(f"  {n}: {d}")
        sys.exit(1)
    print(f"\nPASS — all {len(vectors)} payloads byte-identical")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("capture", cmd_capture), ("verify", cmd_verify)):
        s = sub.add_parser(name)
        s.add_argument("--profile", default="quick",
                       choices=("quick", "standard", "full"))
        s.add_argument("--allow-new", action="store_true",
                       help="permit keys added since capture (they cannot change any "
                            "previously-read value); pre-existing keys must still match")
        s.set_defaults(func=fn)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
