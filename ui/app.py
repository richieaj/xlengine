
import collections
import gzip
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "xlcompiler"))

from flask import Flask, jsonify, request

from compiler.engine import ModelEngine

from levers import load_levers
from outputs import (CHART_YEAR_LABELS, DEFERRABLE_KEYS, SUMMARY_KPI_KEYS,
                     compute_outputs, diff_outputs, kpi_deltas)
from pages.base import render_base
from pages.sidebar import render_sidebar_html
from pages.tabs import render_tabs_html, render_year_buttons_html
from pages import (all_energy, electricity, energy_security, emissions, indicators,
                    costs, energy_flows, land_water, critical_minerals)

PAGE_MODULES = [all_energy, electricity, energy_security, emissions, indicators,
                costs, energy_flows, land_water, critical_minerals]

# Which workbook the backend drives. Overridable with IESS_WORKBOOK so a
# different model file can be swapped in without editing code; the default is
# the CRM-integrated build. Every pathway cache key embeds the workbook's
# content hash (see _workbook_fingerprint), so switching files cannot serve
# answers computed by the other one.
WORKBOOK_PATH = os.environ.get(
    "IESS_WORKBOOK",
    r"D:\ACPET\CRM and IESS integration\IESS2047_CRM.xlsx",
)

# Windows' registry-backed mimetypes database has no .woff2 entry, so Flask's
# static handler served the self-hosted fonts as application/octet-stream.
# Browsers sniff woff2 regardless, but the wrong type means a
# `<link rel=preload as=font>` can be discarded (and the file fetched twice),
# and it fails outright behind X-Content-Type-Options: nosniff — which a
# .gov.in-adjacent deployment is likely to set. Registered here rather than
# left to the host so the answer does not depend on the machine.
mimetypes.add_type("font/woff2", ".woff2")

app = Flask(__name__)

print("Loading model (one-time)...", flush=True)
eng = ModelEngine.load(WORKBOOK_PATH, verbose=False)
eng.set_lever("Target Year Input", "E10", 1)
eng.set_lever("IESS V3 Main Sheet", "E12", 0)

SIDEBAR_GROUPS, ALL_LEVER_ROWS = load_levers(eng)
ALL_LEVER_MAX = {
    item["id"]: item["max"]
    for grp in SIDEBAR_GROUPS
    for sc in grp["subcats"]
    for item in sc["levers"]
}
# Single source of truth for a lever's display name in the "what changed"
# summary — sidebar.py already owns these names for the deck itself, so this
# just flattens the same nested structure rather than keeping a second copy.
LEVER_NAMES = {
    item["id"]: item["name"]
    for grp in SIDEBAR_GROUPS
    for sc in grp["subcats"]
    for item in sc["levers"]
}


baseline_snapshot = None
# The lever vector belonging to baseline_snapshot — every lever at the level
# the last-selected pathway used. Diffed against on every /recalc to drive the
# "what changed since you picked a pathway" summary strip. Like
# baseline_snapshot, this is a diff target (mutable global), not part of the
# cached response.
baseline_levels = None


def lever_changes(levels, baseline):
    """Which real Control-sheet levers differ from the baseline pathway, and
    by how much — the numeric counterpart to diff_outputs()'s booleans, one
    level up (levers, not outputs). Empty list with no baseline yet, same
    convention as diff_outputs(None)."""
    if baseline is None:
        return []
    canon = canonical_levels(levels)
    return [
        {"id": lever_id, "name": LEVER_NAMES[lever_id], "from": baseline[lever_id], "to": canon[lever_id]}
        for lever_id in ALL_LEVER_ROWS
        if canon[lever_id] != baseline.get(lever_id)
    ]


# The evaluator is a correct SINGLE-THREADED design: eval_cell() shares one
# _cache, one _stack (its cycle detector) and one _depth counter across the
# whole engine, and set_override() clears _cache so downstream cells
# recompute. Two Flask worker threads touching the engine concurrently race
# on that shared state — measured directly: two overlapping requests for
# different lever vectors both came back with the SAME wrong answer
# (~349.92) that matches neither vector, because one request's set_override()
# cleared the cache out from under the other mid-eval. Sequential requests for
# the same two vectors are correct (2201.98 and 912.85). MODEL_LOCK serializes
# every read/write of the engine so only one request touches it at a time; the
# client-side request queue (dashboard.js) coalesces bursts of clicks so this
# lock is rarely contended in practice.
MODEL_LOCK = threading.Lock()


@app.after_request
def no_cache(resp):
    # /pathway/<key>.json deliberately sets its own long-lived Cache-Control
    # before this runs — don't clobber it back to no-store.
    if "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/")
def index():
    pages_html = "".join(m.render() for m in PAGE_MODULES)
    html = render_base()
    sidebar_html, flyouts_html = render_sidebar_html(SIDEBAR_GROUPS)
    html = html.replace("__SIDEBAR_HTML__", sidebar_html)
    html = html.replace("__LEVER_FLYOUTS_HTML__", flyouts_html)
    html = html.replace("__TABS_HTML__", render_tabs_html())
    html = html.replace("__PAGES_HTML__", pages_html)
    html = html.replace("__YEAR_BUTTONS_HTML__", render_year_buttons_html())
    html = html.replace("__DEFAULT_SANKEY_YEAR__", CHART_YEAR_LABELS[-1])
    html = html.replace("__IDS_JSON__", json.dumps(list(ALL_LEVER_ROWS.keys())))
    # Fail loudly on an unsubstituted token instead of shipping it to the
    # screen. This whole page is assembled by str.replace (see base.py), and
    # the failure mode is silent: a template gains a __TOKEN__ and, until a
    # matching replace lands here, the reader sees the raw token sitting in
    # the interface as if it were copy — which is exactly what happened with
    # __SCALE_NOTE_HTML__ when a server was restarted after base.py gained the
    # token but before app.py gained the line above. A 500 is easier to
    # diagnose than a page that looks like it was left half-written.
    leftover = re.findall(r"__[A-Z0-9_]+__", html)
    if leftover:
        raise RuntimeError("unsubstituted template token(s): " + ", ".join(sorted(set(leftover))))
    return html


@app.route("/set_scenario", methods=["POST"])
def set_scenario():
    level = int(request.get_json()["level"])
    return _set_scenario(level)


def canonical_levels(levels):
    """The full, clamped lever vector for a request.

    Single source of truth for BOTH what gets written to the engine and what the cache
    key hashes, so the two can never disagree — a divergence there would serve one
    pathway's numbers under another pathway's key, which is the worst failure available
    here.

    Every known lever appears in the result. A lever the caller omitted defaults to 1
    rather than inheriting whatever the previous request left in the engine: inheriting
    would make the response depend on request history and therefore uncacheable. The
    browser always sends all 51, so this only hardens the contract.

    Values are clamped to each lever's own Control-sheet max (F column). The deck renders
    four buttons for every row regardless, and seven levers top out elsewhere — rows
    31/40/59/60/61/62 max at 3, row 49 at 5. Clamping in the key too means two requests
    differing only above a lever's max share one entry, which is correct: they compute
    the same answer.
    """
    return {
        lever_id: max(1, min(int(levels.get(lever_id, 1)), ALL_LEVER_MAX[lever_id]))
        for lever_id in ALL_LEVER_ROWS
    }


def _apply_levels(levels):
    """Put the engine into an explicit, fully-specified lever state.

    The result is a pure function of `levels` and never depends on what a previous
    request left behind — see canonical_levels(). Caller must hold MODEL_LOCK.

    E12 is pinned to 0. It used to be set to the preset level as a "Preset mode" switch,
    but the only thing reading 'IESS V3 Main Sheet'!E12 is the `predefined.scenario`
    defined name, and it demonstrably does NOT override lever choices (E12=4 gives three
    different answers for three different lever vectors). Leaving it at the level only
    perturbed level 4 by 3.66 Mtoe (0.34%) through an unrelated path — exactly the
    preset-vs-custom discrepancy this pins shut.
    """
    eng.set_lever("IESS V3 Main Sheet", "E12", 0)
    for lever_id, value in canonical_levels(levels).items():
        eng.set_lever("Control", f"E{ALL_LEVER_ROWS[lever_id]}", value)


# ── Response cache ────────────────────────────────────────────────────────────
# The model is a pure, deterministic function of the clamped lever vector (verified:
# identical payload -> identical response, independent of request history), so the same
# scenario asked twice can be computed once. That is the difference between needing
# ~28,000 workers at launch peak and needing a handful.
#
# Two layers: a small in-process dict for the states this worker just served, and a
# directory of gzipped JSON shared by every worker (and pre-filled by
# tools/precompute_pathways.py). The directory is deliberately plain files so this works
# unchanged on a laptop, on a shared volume, or behind an object store — Redis can slot
# in later without touching callers.
CACHE_DIR = os.environ.get(
    "IESS_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "cache", "pathways"))
MEM_CACHE_MAX = 512

_mem_cache = collections.OrderedDict()
_cache_lock = threading.Lock()
_inflight = {}
_inflight_lock = threading.Lock()
CACHE_STATS = collections.Counter()


def _mem_put(key, data):
    with _cache_lock:
        _mem_cache[key] = data
        _mem_cache.move_to_end(key)
        while len(_mem_cache) > MEM_CACHE_MAX:
            _mem_cache.popitem(last=False)


def cache_get(key):
    """In-process dict first, then the shared gzipped-JSON directory (populated
    by another worker, or by tools/precompute_pathways.py). A disk hit is
    promoted back into the in-process dict so it's a plain dict lookup next
    time this worker is asked for it."""
    with _cache_lock:
        hit = _mem_cache.get(key)
        if hit is not None:
            _mem_cache.move_to_end(key)
    if hit is not None:
        CACHE_STATS["mem_hit"] += 1
        return hit
    path = _disk_path(key)
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return None
    CACHE_STATS["disk_hit"] += 1
    _mem_put(key, data)
    return data


def cache_put(key, data):
    _mem_put(key, data)
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = _disk_path(key) + f".tmp-{os.getpid()}-{threading.get_ident()}"
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _disk_path(key))
    except OSError:
        pass                     # cache is an optimisation; never fail a request for it


def _workbook_fingerprint():
    """Content hash of the workbook, embedded in every cache key.

    Without this, replacing the workbook would silently serve answers computed by the
    previous model — the one way caching could produce genuinely wrong numbers.
    """
    h = hashlib.sha256()
    with open(WORKBOOK_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


WORKBOOK_FP = _workbook_fingerprint()

# Fingerprint of the SHAPE of a cached payload, alongside the workbook's own.
# The workbook hash catches "the model changed"; this catches "the set of
# outputs changed", which is a different way to serve a wrong answer and was
# not covered. Adding kpis.clean_share demonstrated it: every cached entry had
# been written before that field existed, so a hit came back without it, and
# kpi_deltas() read the missing baseline as 0 and would have reported a clean
# share rising from 0% — a number the model never produced.
# Derived from the payload's own key names rather than hand-bumped, so adding
# or renaming an output invalidates the cache by construction and nobody has
# to remember to change a version number here.
def _output_schema_fingerprint():
    keys = sorted(set(SUMMARY_KPI_KEYS))
    with MODEL_LOCK:
        sample = compute_outputs(eng, defer=DEFERRABLE_KEYS)
    keys += sorted(sample.keys()) + sorted(sample.get("kpis", {}).keys())
    return hashlib.sha256("|".join(keys).encode()).hexdigest()[:8]


OUTPUT_FP = _output_schema_fingerprint()


def pathway_key(levels):
    """Content-addressed key for a lever vector under the current workbook AND
    the current output schema (see _output_schema_fingerprint)."""
    canon = canonical_levels(levels)
    body = ";".join(f"{k}={canon[k]}" for k in sorted(canon))
    return f"{WORKBOOK_FP}{OUTPUT_FP}-" + hashlib.sha256(body.encode()).hexdigest()[:24]


def _disk_path(key):
    return os.path.join(CACHE_DIR, key + ".json.gz")


def compute_pathway(levels, defer=DEFERRABLE_KEYS):
    """Model outputs for a lever vector, cached, with one computation per key.

    Returns (key, data). `data` deliberately excludes "changed": that mask is a diff
    against the mutable baseline_snapshot, not a function of the lever vector, so it
    must be recomputed per request rather than cached alongside the payload.

    Single-flight: concurrent callers wanting the same uncached key elect one leader to
    compute while the rest wait for it. Without this, a scenario that suddenly becomes
    popular is computed once per waiting request and stalls the whole pool exactly when
    it is busiest.
    """
    key = pathway_key(levels)
    hit = cache_get(key)
    if hit is not None:
        return key, hit

    with _inflight_lock:
        event = _inflight.get(key)
        leader = event is None
        if leader:
            event = threading.Event()
            _inflight[key] = event

    if not leader:
        CACHE_STATS["coalesced"] += 1
        event.wait(timeout=300)
        hit = cache_get(key)
        if hit is not None:
            return key, hit
        # leader failed or timed out — fall through and compute it ourselves

    try:
        CACHE_STATS["computed"] += 1
        with MODEL_LOCK:
            _apply_levels(levels)
            data = compute_outputs(eng, defer=defer)
        cache_put(key, data)
        return key, data
    finally:
        if leader:
            with _inflight_lock:
                _inflight.pop(key, None)
            event.set()


def _set_scenario(level):
    """An example pathway is simply every lever at that effort level.

    This is now the SAME code path as /recalc — one model state, one answer —
    so "pathway 3" and "set every lever to 3 by hand" can no longer disagree.
    Previously this computed display data from E12=level while leaving the
    Control rows at whatever the last interaction left, then the browser set
    every button to `level`. The screen therefore claimed "all levers at N"
    while the numbers came from stale values, and the error was large: preset 4
    read 1255.53 with level-1 levers underneath versus 1074.24 with the right
    ones. It also made the result depend on click history.

    Note this reassigns what "Least Effort" reports: 1,880.65 was the
    workbook's own saved lever mix (mostly 2s and 3s — {0:3, 1:3, 2:21, 3:23,
    4:1}), not level 1. All-levers-at-1 is 2,201.98, and the four pathways now
    form a monotonic ladder: 2201.98 / 1564.93 / 1225.04 / 1070.58.

    Takes no lock itself: compute_pathway() acquires MODEL_LOCK around the model, and
    assigning baseline_snapshot is a single atomic rebind. Acquiring it here as well
    self-deadlocked, MODEL_LOCK being a plain non-reentrant Lock.
    """
    global baseline_snapshot, baseline_levels
    levels = {lever_id: level for lever_id in ALL_LEVER_ROWS}
    key, data = compute_pathway(levels)

    # The chosen pathway IS the baseline that later lever tweaks are diffed against, so
    # it's the same data rather than a second "what-if" computation — which also makes
    # picking a pathway about twice as fast, as it no longer computes the model twice.
    baseline_snapshot = data
    baseline_levels = canonical_levels(levels)
    out = dict(data)
    out["changed"] = diff_outputs(data, None)
    out["lever_changes"] = []  # a fresh pathway has no drift from itself yet
    out["kpi_deltas"] = {}
    out["pathway_key"] = key
    return jsonify(out)


@app.route("/pathway/<key>.json")
def pathway_by_key(key):
    """Content-addressed GET for an already-computed pathway.

    The key embeds the workbook fingerprint and the clamped lever vector, so the body
    for a given URL can never change — which is what makes it safe to cache in a CDN or
    reverse proxy essentially forever. That is the tier that lets lakhs of concurrent
    users be served without Python running at all.

    A miss is a 404 rather than a computation: the key alone does not carry the lever
    vector, so there is nothing to compute from. The client falls back to POST /recalc.
    """
    data = cache_get(key)
    if data is None:
        CACHE_STATS["get_miss"] += 1
        return jsonify({"error": "not cached"}), 404
    out = dict(data)
    out["changed"] = diff_outputs(data, baseline_snapshot)
    out["pathway_key"] = key
    resp = jsonify(out)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    resp.headers["X-Pathway-Cache"] = "hit"
    return resp


@app.route("/deferred", methods=["POST"])
def deferred():
    """The Emissions-by-sector chart and the Sankey — deferred out of the default
    payload (compute_pathway's default `defer`) since most tab loads never touch
    them, fetched on demand the moment a tab that does need them activates."""
    levers = request.get_json()
    key = "deferred-" + pathway_key(levers)
    hit = cache_get(key)
    if hit is not None:
        return jsonify(hit)
    with MODEL_LOCK:
        _apply_levels(levers)
        full = compute_outputs(eng)
    out = {k: full[k] for k in DEFERRABLE_KEYS if k in full}
    cache_put(key, out)
    return jsonify(out)


@app.route("/recalc", methods=["POST"])
def recalc():
    levers = request.get_json()
    key, data = compute_pathway(levers)
    # "changed"/lever_changes/kpi_deltas are all diffs against the current baseline,
    # which is mutable global state rather than a function of the lever vector — so
    # they're attached per request and never stored in the cache. dict(data) keeps
    # the cached object pristine.
    out = dict(data)
    out["changed"] = diff_outputs(data, baseline_snapshot)
    out["lever_changes"] = lever_changes(levers, baseline_levels)
    out["kpi_deltas"] = kpi_deltas(data, baseline_snapshot)
    out["pathway_key"] = key
    return jsonify(out)


@app.route("/cache_stats")
def cache_stats():
    return jsonify(dict(CACHE_STATS))


if __name__ == "__main__":
    app.run(debug=False, port=5051)
