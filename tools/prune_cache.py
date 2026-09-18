"""Prune the on-disk pathway cache (cache/pathways/ by default).

Deletes:
  - entries whose fingerprint (workbook content hash + output-schema hash) doesn't
    match the workbook this script loads — dead weight from a retired workbook edit
    or a changed output schema, deleted regardless of age since they can never be
    served again under the currently running server.
  - entries matching the current fingerprint that are older than --max-age-days (5 by
    default) AND are not one of the states tools/precompute_pathways.py's
    enumerate_frontier() would recompute anyway (those are kept regardless of age, so
    the always-fast presets/first-tweak frontier never goes cold from routine pruning).

ui/app.py already runs this exact same logic once at startup and once a day in a
background thread for as long as the server process lives, so most deployments don't
need this script at all. It exists for anyone who'd rather drive pruning externally
(Windows Task Scheduler, cron) or run it once by hand — either way it calls the same
ui/cache_gc.py `prune()` function app.py uses, so the two can never disagree about what
counts as prunable.

    python tools/prune_cache.py                        # prune with the defaults
    python tools/prune_cache.py --max-age-days 2 --dry-run
    python tools/prune_cache.py --no-keep-frontier      # also prune the frontier if old
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "xlcompiler"))
sys.path.insert(0, os.path.join(ROOT, "ui"))


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-age-days", type=float, default=5.0,
                    help="delete entries under the current fingerprint older than this (default 5)")
    p.add_argument("--dry-run", action="store_true", help="report what would be deleted, delete nothing")
    p.add_argument("--no-keep-frontier", action="store_true",
                    help="don't exempt tools/precompute_pathways.py's frontier from age-based pruning")
    args = p.parse_args()

    # Loads the workbook (the same ~1-2s / ~300MB cost as ui/app.py itself) so the
    # fingerprint and frontier are computed exactly the way the live server computes
    # them, rather than a second implementation that could drift out of step.
    import app as APP
    from cache_gc import prune

    keep_keys = None
    if not args.no_keep_frontier:
        keep_keys = set()
        for key, _vec in APP.enumerate_frontier():
            keep_keys.add(key)
            keep_keys.add("deferred-" + key)

    result = prune(
        APP.CACHE_DIR, APP.WORKBOOK_FP + APP.OUTPUT_FP,
        max_age_seconds=args.max_age_days * 86400,
        keep_keys=keep_keys,
        dry_run=args.dry_run,
    )

    tag = "would delete" if args.dry_run else "deleted"
    print(f"cache dir : {os.path.abspath(APP.CACHE_DIR)}")
    print(f"fingerprint: {APP.WORKBOOK_FP}{APP.OUTPUT_FP}")
    print(f"kept: {result['kept']}   {tag}: {result['deleted']} "
          f"({result['deleted_bytes'] / 1048576:.1f} MB)")


if __name__ == "__main__":
    main()
