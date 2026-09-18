"""Precompute the pathways real traffic actually asks for.

The full lever space is 9.0e29 states, so it cannot be enumerated. But the states a
visitor reaches in their first few clicks are few: the four example pathways, and any
one lever moved off one of them. That frontier is 592 states — about 4 MB gzipped —
and it covers every landing view, every preset click and every first tweak.

    python tools/precompute_pathways.py --workers 4
    python tools/precompute_pathways.py --dry-run          # just count

Writes into the same cache directory the server reads (IESS_CACHE_DIR, default
cache/pathways/), using the server's own pathway_key() and cache_put(), so there is no
second key algorithm that could drift out of step.

Idempotent and resumable: a state already on disk is skipped, so it is safe to
interrupt and re-run. Each worker process loads its own engine (~1.4 s, ~312 MB), so
keep --workers within the RAM available; the work is CPU-bound, so beyond the core
count there is nothing to gain.
"""

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "xlcompiler"))
sys.path.insert(0, os.path.join(ROOT, "ui"))

_APP = None


def _app():
    """Import ui/app.py lazily and once per process.

    Deliberately not a module-level import: this file is also imported by each worker
    process under Windows' spawn start method, and loading the workbook eagerly in the
    parent would pay the cost twice.
    """
    global _APP
    if _APP is None:
        import app as APP
        _APP = APP
    return _APP


def enumerate_frontier():
    """The 4 example pathways plus every single-lever deviation from each.

    Now just app.py's own definition — see it there for the reasoning
    (deduplication by pathway_key, etc.). Kept as a thin wrapper here rather than
    inlined at call sites so this script doesn't have to change if a caller imports
    it as `precompute_pathways.enumerate_frontier`.
    """
    return _app().enumerate_frontier()


def _compute_one(item):
    """Compute and cache one state. Runs in a worker process."""
    key, vec = item
    APP = _app()
    if APP.cache_get(key) is not None:
        return key, 0.0, True
    t0 = time.perf_counter()
    # compute_pathway writes into the cache itself, using the same key, so the server
    # and this script can never disagree about where an entry lives.
    APP.compute_pathway(vec)
    # the deferred bundle (Emissions chart + Sankey) is nearly free right now: this
    # process's evaluator cache is still warm for exactly this lever state
    dkey = "deferred-" + key
    if APP.cache_get(dkey) is None:
        full = APP.compute_outputs(APP.eng)
        APP.cache_put(dkey, {k: full[k] for k in APP.DEFERRABLE_KEYS if k in full})
    return key, time.perf_counter() - t0, False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="stop after N states (testing)")
    args = p.parse_args()

    APP = _app()
    states = enumerate_frontier()
    if args.limit:
        states = states[:args.limit]
    print(f"frontier: {len(states)} distinct states")
    print(f"cache dir: {os.path.abspath(APP.CACHE_DIR)}")
    print(f"workbook : {APP.WORKBOOK_FP}")
    todo = [s for s in states if APP.cache_get(s[0]) is None]
    print(f"already cached: {len(states) - len(todo)}   to compute: {len(todo)}")
    if args.dry_run or not todo:
        return

    t_all = time.perf_counter()
    done = skipped = 0
    if args.workers <= 1:
        results = map(_compute_one, todo)
    else:
        ex = ProcessPoolExecutor(max_workers=args.workers)
        results = ex.map(_compute_one, todo, chunksize=1)
    for key, dt, was_cached in results:
        done += 1
        skipped += was_cached
        if done % 25 == 0 or done == len(todo):
            el = time.perf_counter() - t_all
            rate = done / el if el else 0
            eta = (len(todo) - done) / rate if rate else 0
            print(f"  {done:>4}/{len(todo)}  {el:6.1f}s elapsed  "
                  f"{rate:4.2f}/s  eta {eta/60:5.1f} min")
    el = time.perf_counter() - t_all
    size = sum(os.path.getsize(os.path.join(APP.CACHE_DIR, f))
               for f in os.listdir(APP.CACHE_DIR)) if os.path.isdir(APP.CACHE_DIR) else 0
    print(f"done: {done} states in {el:.1f}s ({el/60:.1f} min), {skipped} already cached")
    print(f"cache on disk: {size/1048576:.1f} MB across "
          f"{len(os.listdir(APP.CACHE_DIR))} files")


if __name__ == "__main__":
    main()
