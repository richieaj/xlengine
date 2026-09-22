"""Entry point for a real WSGI server (gunicorn), as opposed to `python ui/app.py`.

Gunicorn does not run a script -- it imports a module and looks for a WSGI
application object inside it. The Dockerfile's CMD ends with `wsgi:app`, which
means "import the module `wsgi`, then serve the object named `app`". That is
this file, and the object is re-exported at the bottom.

Two jobs, and the second one is the reason this file has to exist at all.
"""

import os
import sys

# ── Job 1: make `import app` work from the repository root ───────────────────
# ui/app.py is written to be run from inside ui/ (it does its own
# sys.path.insert for ../xlcompiler, relative to its own __file__, so that part
# keeps working wherever it is imported from). What it cannot do is put itself
# on the path, so we do that here.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "ui"))

from app import app, start_cache_janitor  # noqa: E402  (must follow the path setup)

# ── Job 2: start the cache janitor, which otherwise never runs ───────────────
# ui/app.py calls start_cache_janitor() only from its `if __name__ ==
# "__main__"` block, and that is deliberate -- tools/precompute_pathways.py and
# tools/prune_cache.py both `import app` purely to borrow its already-loaded
# engine, and that import must not have the side effect of deleting cache
# files. (The comment in app.py records finding exactly that: a --dry-run that
# reported "would delete: 0" right after startup had already deleted 1,264.)
#
# The consequence is that under ANY WSGI server __name__ != "__main__", so the
# startup prune and the daily background thread never happen and the cache
# grows without bound. Calling it explicitly here restores that, and keeps the
# "importing app.py is side-effect free" property intact for the CLI tools.
#
# Safe with the pre-baked cache the image ships: prune() is passed
# keep_keys=_frontier_keep_keys(), so the presets and every single-lever
# deviation are kept regardless of age. It only collects stray ad-hoc entries
# and anything left under a retired workbook/schema fingerprint.
start_cache_janitor()


# ── Job 3: teach THIS worker the four preset pathway keys ────────────────────
# Measured, not theoretical: a fresh 4-worker container lost the baseline on
# 28 of 40 concurrent /recalc requests, which blanks the Insights panel
# ("What you changed" / "What it did") for whoever hits an unlucky worker.
#
# The cause is that _levels_by_key (app.py:358) is per-process. /recalc needs
# BOTH cache_get(baseline_key) -- which is the shared disk cache, so it
# resolves anywhere -- and _recall_levels(baseline_key), which does not. A
# worker that never served that key returns (None, None), and note the `or` in
# _baseline_state: losing `levels` discards the `data` too, so `changed`,
# `lever_changes` AND `kpi_deltas` all come back empty together.
#
# What makes this cheap to fix rather than needing shared state: the baseline a
# browser sends is ALWAYS a preset. dashboard.js sets myBaselineKey only from
# the /set_scenario response, never from /recalc. So there are exactly four
# keys any client can ever present, and compute_pathway() calls
# _remember_levels() on every call INCLUDING a cache hit. Resolving the four
# presets here therefore populates this worker's memo with every key it could
# be asked about, at a cost of four disk-cache reads (~2 ms each, no model
# work) because the image ships those pathways pre-computed.
#
# Run per worker, because gunicorn imports this module once per worker process.
# Failure is deliberately non-fatal: without it the panel degrades to its
# documented "no baseline yet" state, which is not worth refusing to boot over.
try:
    for _level in (1, 2, 3, 4):
        app_module = sys.modules["app"]
        _levels = {lid: _level for lid in app_module.ALL_LEVER_ROWS}
        app_module.compute_pathway(_levels)
    print(f"baseline warm: 4 preset keys memoised in pid {os.getpid()}", flush=True)
except Exception as _e:                                    # noqa: BLE001
    print(f"baseline warm skipped ({_e!r}) -- Insights diff may be "
          f"unavailable until a pathway is picked", flush=True)

# What gunicorn actually serves. Re-exported explicitly so the name is not
# mistaken for an unused import.
__all__ = ["app"]
