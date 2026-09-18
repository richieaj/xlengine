"""cache_gc.py — disk housekeeping for the on-disk pathway cache (cache/pathways/).

The response cache (see app.py's "Response cache" section) is content-addressed and
purely an optimisation: every entry can be recomputed from its lever vector, so nothing
here is ever the only copy of anything, and deleting an entry can never produce a wrong
answer — only a slower one, once, for whoever asks for it next. Two things pile up
there without bound if nobody prunes them:

  1. Dead entries — files whose fingerprint prefix (workbook content hash + output-schema
     hash, see app.py's WORKBOOK_FP/OUTPUT_FP) doesn't match the CURRENTLY RUNNING
     server. Editing the workbook, or adding/renaming a single output field, changes that
     prefix and instantly orphans every existing entry: pathway_key() can never produce
     the old prefix again, so those files can never be served again from the moment the
     server restarts. Confirmed live in this project's own cache directory the day this
     module was written: 1,264 of 1,304 files on disk (97%) were already dead from a
     retired output-schema fingerprint, with nothing ever removing them.
  2. Live-but-cold entries — real ad hoc lever combinations real visitors reached under
     the CURRENT fingerprint, that haven't been asked for again in a while. Cheap to
     lose (a miss just recomputes, ~1-2s) and unbounded in number (the lever space is
     9e29 states), so these are the actual "piling up in normal operation" risk — not the
     precomputed frontier (~600 states, tools/precompute_pathways.py's
     enumerate_frontier()), which callers can ask this module to keep regardless of age
     so the always-fast presets/first-tweak frontier never itself goes cold from routine
     pruning.

Pure filesystem logic, no import of app.py or the model — kept that way so this module
has no circular-import risk and no reason to ever touch MODEL_LOCK. Called two ways:
  - ui/app.py runs prune() once at startup and once a day thereafter in a background
    thread, so the cache is bounded automatically for as long as the server process
    lives, no external scheduler required.
  - tools/prune_cache.py is a CLI wrapper around the same function, for anyone who'd
    rather drive it from Windows Task Scheduler / cron, or run it once by hand.
"""

import os
import time


def prune(cache_dir, keep_prefix, max_age_seconds, keep_keys=None, dry_run=False,
          tmp_max_age_seconds=3600):
    """Delete stale/cold entries from `cache_dir`.

    keep_prefix: the current fingerprint (e.g. app.py's WORKBOOK_FP + OUTPUT_FP). A
    file whose name doesn't CONTAIN it (not "start with" — deliberately a substring
    check, see below) is from a retired workbook or output schema and is deleted
    unconditionally, regardless of age — it can never be served again under the
    currently running server.

    Substring, not prefix: cache_put() is also used for keys with a prefix of their
    OWN ahead of the fingerprint — e.g. app.py's "deferred-" + pathway_key() — so the
    fingerprint does not always sit at position 0. Using startswith() here shipped as a
    real bug once already: every "deferred-*" entry (the Sankey + emissions-by-sector
    bundle) doesn't start with the fingerprint even though it fully matches the current
    workbook/schema, so a startswith() check flagged all 596 of them as "dead" and
    deleted the whole bundle on the very first scheduled run. A 20-hex-char fingerprint
    is astronomically unlikely to appear as a false-positive substring elsewhere, so
    `in` is safe and — unlike startswith() — correct for any future key naming that
    puts its own prefix or suffix around the fingerprint.

    keep_keys: an optional set of cache keys (a pathway_key(), or "deferred-" + one) to
    keep regardless of age even when they DO match keep_prefix — e.g. the precompute
    frontier, so it survives routine pruning rather than going cold and having to be
    recomputed on the next visitor.

    tmp_max_age_seconds: cache_put() writes via a *.tmp-<pid>-<tid> temp file then
    os.replace()'s it into place; a crashed write can leave the temp file behind
    forever otherwise. Cleaned up once it's old enough that it can't still be a write
    genuinely in flight.

    Returns {"kept": int, "deleted": int, "deleted_bytes": int}. Never raises — a
    filesystem race (another process deleting the same file, e.g. two workers pruning
    at once) is silently treated as "already gone", matching cache_put()'s own
    never-fail-a-request-for-a-cache-op posture.
    """
    result = {"kept": 0, "deleted": 0, "deleted_bytes": 0}
    if not os.path.isdir(cache_dir):
        return result

    keep_keys = keep_keys or set()
    now = time.time()

    for name in os.listdir(cache_dir):
        path = os.path.join(cache_dir, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        if not os.path.isfile(path):
            continue

        if ".tmp-" in name:
            if now - st.st_mtime > tmp_max_age_seconds:
                _remove(path, dry_run, st.st_size, result)
            else:
                result["kept"] += 1
            continue

        if not name.endswith(".json.gz"):
            continue  # not one of ours (e.g. a .gitkeep) — leave it alone

        if keep_prefix not in name:
            # Dead: from a retired workbook/output-schema fingerprint. Age is
            # irrelevant — it is unreachable the instant the fingerprint changed.
            _remove(path, dry_run, st.st_size, result)
            continue

        key = name[:-len(".json.gz")]
        if key in keep_keys or (now - st.st_mtime) < max_age_seconds:
            result["kept"] += 1
            continue

        _remove(path, dry_run, st.st_size, result)

    return result


def _remove(path, dry_run, size, result):
    if not dry_run:
        try:
            os.remove(path)
        except OSError:
            return  # already gone (e.g. a concurrent prune) — not an error here
    result["deleted"] += 1
    result["deleted_bytes"] += size
