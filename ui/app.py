
import collections
import gzip
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "xlcompiler"))

from flask import Flask, jsonify, request

from compiler.engine import ModelEngine

from cache_gc import prune as prune_cache
from levers import load_levers
from outputs import (CHART_YEAR_LABELS, DEFERRABLE_KEYS, SUMMARY_KPI_KEYS,
                     compute_outputs, diff_outputs, kpi_deltas)
from pages.base import render_base
from pages.sidebar import render_sidebar_html
from pages.tabs import render_tabs_html, render_year_buttons_html
from pages import (all_energy, electricity, energy_security, emissions, indicators,
                    costs, energy_flows, land_water, critical_minerals,
                    mission_life, health)

PAGE_MODULES = [all_energy, electricity, energy_security, emissions, indicators,
                costs, energy_flows, land_water, critical_minerals,
                mission_life, health]

WORKBOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "workbook", "IESS2047_Version_3.0.xlsx")

# Windows' registry-backed mimetypes database has no .woff2 entry, so Flask's
# static handler served the self-hosted fonts as application/octet-stream.
# Browsers sniff woff2 regardless, but the wrong type means a
# `<link rel=preload as=font>` can be discarded (and the file fetched twice),
# and it fails outright behind X-Content-Type-Options: nosniff — which a
# .gov.in-adjacent deployment is likely to set. Registered here rather than
# left to the host so the answer does not depend on the machine.
mimetypes.add_type("font/woff2", ".woff2")

app = Flask(__name__)

# A lever payload is ~51 small ints (well under 2 KB even with the baseline_key
# echoed back). No legitimate request needs anywhere near this; it exists only to
# reject an absurdly large body outright before Flask/Werkzeug buffer all of it into
# memory, which costs nothing for real traffic and closes off one cheap memory-
# pressure angle. Overridable via IESS_MAX_CONTENT_LENGTH if some future page ever
# needs a bigger body for a different route.
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("IESS_MAX_CONTENT_LENGTH", 64 * 1024))

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


# ── Basic per-visitor rate limiting ─────────────────────────────────────────────
# This caps how FAST any one visitor can hit the model, not how MANY visitors the
# site can serve at once — those are two different questions. Total concurrent
# traffic is what the response cache (above) already exists to handle: a request for
# a scenario/lever combination someone has already reached comes back in a few
# milliseconds with no lock involved at all, so lakhs of visitors landing on the same
# handful of popular pathways cost almost nothing regardless of this limiter.
#
# What this DOES guard against: a single client cycling through many distinct,
# never-before-seen lever vectors, each forcing a real ~1-2s computation (the
# evaluator is single-threaded by design — see MODEL_LOCK above), all serialised
# behind that one lock. That queues behind every OTHER visitor's request too, since
# there is one lock for the whole process — the blast radius of one abusive client
# is the whole site, not just their own session. The limit is deliberately generous
# (120 requests / 60s per IP by default) — a real person dragging a lever is already
# throttled far below this by the client's own 250ms debounce and its "one request in
# flight at a time" queue (dashboard.js), so this only ever engages against something
# firing far faster than a human can, e.g. a script.
RATE_LIMIT_MAX = int(os.environ.get("IESS_RATE_LIMIT_MAX", 120))
RATE_LIMIT_WINDOW = float(os.environ.get("IESS_RATE_LIMIT_WINDOW", 60))
_RATE_BUCKETS_MAX = 20000  # distinct IPs tracked at once; oldest evicted first, not by age
_rate_lock = threading.Lock()
_rate_buckets = collections.OrderedDict()  # ip -> [timestamp, ...], oldest first


def _client_ip():
    # X-Forwarded-For is only trustworthy behind a reverse proxy that actually sets
    # it (a bare client can send any value it likes); this dev server has no such
    # proxy in front of it today, so request.remote_addr is what's real here. Reading
    # the header too means this keeps working unchanged the moment one IS added.
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")


def _rate_limited():
    """True if this caller already made RATE_LIMIT_MAX requests to a limited route
    within the last RATE_LIMIT_WINDOW seconds. Fails OPEN on any internal error — a
    bug in the limiter must never be the reason a real request gets refused."""
    try:
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW
        with _rate_lock:
            ip = _client_ip()
            bucket = _rate_buckets.setdefault(ip, [])
            _rate_buckets.move_to_end(ip)
            while len(_rate_buckets) > _RATE_BUCKETS_MAX:
                _rate_buckets.popitem(last=False)
            i = 0
            while i < len(bucket) and bucket[i] < cutoff:
                i += 1
            if i:
                del bucket[:i]
            if len(bucket) >= RATE_LIMIT_MAX:
                return True
            bucket.append(now)
            return False
    except Exception:
        return False


def _rate_limit_response():
    resp = jsonify({"error": "too many requests — please slow down"})
    resp.headers["Retry-After"] = str(int(RATE_LIMIT_WINDOW))
    return resp, 429


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
    # First year, not last. The Sankey opened on 2047 — the end of the
    # projection — so the first thing anyone saw on the tab was a modelled
    # future with no baseline to read it against. 2022 is the actual system,
    # and stepping forward from it is what the year buttons are for.
    # render_year_buttons_html() marks the same year active; keep the two
    # together if either moves.
    html = html.replace("__DEFAULT_SANKEY_YEAR__", CHART_YEAR_LABELS[0])
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
    if _rate_limited():
        return _rate_limit_response()
    body = request.get_json(silent=True) or {}
    try:
        level = int(body.get("level"))
    except (TypeError, ValueError):
        return jsonify({"error": "level must be an integer"}), 400
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

    Tolerant of a malformed `levels` (not a dict, or containing junk values): treated
    the same as "this lever was omitted" (default 1) rather than raising, so a bad
    request body degrades to a defined, cacheable, boring result instead of a 500.
    """
    if not isinstance(levels, dict):
        levels = {}
    out = {}
    for lever_id in ALL_LEVER_ROWS:
        try:
            value = int(levels.get(lever_id, 1))
        except (TypeError, ValueError):
            value = 1
        out[lever_id] = max(1, min(value, ALL_LEVER_MAX[lever_id]))
    return out


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


# ── Per-pathway lever vectors, for the "what changed" diff ─────────────────────
# diff_outputs()/lever_changes() need a BASELINE to compare the current request
# against — "what did you start from before you touched a lever". That baseline used
# to be one pair of mutable globals (baseline_snapshot/baseline_levels) written by
# /set_scenario and read by every later /recalc, which is wrong the moment two
# different visitors are using the site at once: visitor A picks a pathway, visitor B
# picks a different one a moment later, and now A's next /recalc is diffed against B's
# pathway, not their own. The fix is not a bigger lock (the numbers were already
# correct — only this diff was cross-contaminated) — it's to stop keeping a baseline
# on the server AT ALL. Each browser tab already gets a `pathway_key` back from
# /set_scenario/`/recalc`; it holds onto that as ITS OWN baseline (dashboard.js's
# `myBaselineKey`) and sends it back on every later /recalc. The server only needs to
# resolve a key back into (levels, data) on demand — and the `data` side of that is
# already exactly what cache_get(key) does. The `levels` side (the raw per-lever
# vector, needed for lever_changes()'s per-lever "L4 -> L1" list) isn't part of the
# cached response payload, so it's remembered here, keyed the same way.
#
# Deliberately in-memory only, not written to the on-disk cache: it exists purely to
# serve a request that arrives with a baseline_key this same process has seen before.
# If the server restarts, a client's remembered key simply stops resolving a levels
# list — lever_changes() falls back to its already-established "no baseline yet"
# convention ([]) rather than erroring, and diff_outputs(data, None) does the same for
# `changed`. Nothing breaks; the one thing lost is the "which lever moved" detail line
# until the visitor picks a pathway again, which also re-establishes it.
_LEVELS_CACHE_MAX = 2048
_levels_by_key = collections.OrderedDict()
_levels_lock = threading.Lock()


def _remember_levels(key, canon):
    with _levels_lock:
        _levels_by_key[key] = canon
        _levels_by_key.move_to_end(key)
        while len(_levels_by_key) > _LEVELS_CACHE_MAX:
            _levels_by_key.popitem(last=False)


def _recall_levels(key):
    if not key:
        return None
    with _levels_lock:
        v = _levels_by_key.get(key)
        if v is not None:
            _levels_by_key.move_to_end(key)
        return v


def _baseline_state(baseline_key):
    """(levels, data) for a client-remembered baseline pathway_key.

    (None, None) if the key is missing, unrecognised, or this worker never computed
    it (e.g. after a restart) — the same "fresh pathway, no drift yet" convention
    diff_outputs()/lever_changes() already use for a None baseline.
    """
    if not baseline_key:
        return None, None
    data = cache_get(baseline_key)
    levels = _recall_levels(baseline_key)
    if data is None or levels is None:
        return None, None
    return levels, data


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


def enumerate_frontier():
    """The 4 example pathways plus every single-lever deviation from each.

    Deduplicated by pathway_key, because different raw vectors can canonicalise to the
    same state — e.g. requesting level 4 on a lever that maxes at 3.

    The single definition of "the precompute frontier": tools/precompute_pathways.py
    calls this (via `import app as APP`) to know what to compute, and the cache
    janitor below calls it to know what to keep regardless of age, so there is no
    second copy of this enumeration that could drift out of step with either.
    """
    lever_ids = sorted(ALL_LEVER_ROWS, key=lambda k: ALL_LEVER_ROWS[k])
    seen, states = set(), []

    def add(vec):
        key = pathway_key(vec)
        if key not in seen:
            seen.add(key)
            states.append((key, vec))

    for level in (1, 2, 3, 4):
        base = {lid: level for lid in lever_ids}
        add(base)
        for lid in lever_ids:
            for alt in range(1, ALL_LEVER_MAX[lid] + 1):
                vec = dict(base)
                vec[lid] = alt
                add(vec)
    return states


def _disk_path(key):
    return os.path.join(CACHE_DIR, key + ".json.gz")


def compute_pathway(levels, defer=DEFERRABLE_KEYS):
    """Model outputs for a lever vector, cached, with one computation per key.

    Returns (key, data). `data` deliberately excludes "changed": that mask is a diff
    against a per-request baseline (see _baseline_state), not a function of the lever
    vector, so it must be recomputed per request rather than cached alongside the
    payload.

    Also remembers this key's own canonical lever vector (_remember_levels) on every
    call, hit or miss — so any key currently being asked for can be resolved back into
    a lever vector by _baseline_state() a moment later, e.g. when this same response's
    own pathway_key comes back as a later request's baseline_key.

    Single-flight: concurrent callers wanting the same uncached key elect one leader to
    compute while the rest wait for it. Without this, a scenario that suddenly becomes
    popular is computed once per waiting request and stalls the whole pool exactly when
    it is busiest.
    """
    key = pathway_key(levels)
    _remember_levels(key, canonical_levels(levels))
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

    Takes no lock itself: compute_pathway() acquires MODEL_LOCK around the model.

    Returns no server-side baseline assignment — the pathway IS the baseline for
    whatever comes next, but "next" might be a different browser tab entirely doing
    its own thing at the same time, so the client is what remembers it: dashboard.js
    stores this response's own pathway_key as its baseline_key and echoes it back on
    every later /recalc. See the "Per-pathway lever vectors" comment above cache_get()
    for why that replaced a pair of mutable globals here.
    """
    levels = {lever_id: level for lever_id in ALL_LEVER_ROWS}
    key, data = compute_pathway(levels)
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

    Optional `?baseline_key=` query param, same meaning as /recalc's `baseline_key`
    body field (see _baseline_state) — needed because this is a GET with no body to
    carry one otherwise. Note this makes the response no longer a pure function of the
    URL PATH alone if a caller ever varies baseline_key: a CDN/reverse proxy fronting
    this route should key its cache on the full URL including the query string (the
    common default), or the "changed" field specifically could go stale behind a
    path-only cache — the rest of the payload is unaffected either way. Not yet reached
    by the real client (dashboard.js still always POSTs /recalc), so this is dormant
    infrastructure for a future CDN tier, not a currently-exercised path.
    """
    data = cache_get(key)
    if data is None:
        CACHE_STATS["get_miss"] += 1
        return jsonify({"error": "not cached"}), 404
    _levels, baseline_data = _baseline_state(request.args.get("baseline_key"))
    out = dict(data)
    out["changed"] = diff_outputs(data, baseline_data)
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
    if _rate_limited():
        return _rate_limit_response()
    levers = request.get_json(silent=True) or {}
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
    if _rate_limited():
        return _rate_limit_response()
    body = request.get_json(silent=True) or {}
    levers = body.get("levers") or {}
    # "changed"/lever_changes/kpi_deltas are all diffs against THIS REQUEST's own
    # baseline — the pathway_key the client remembers from whenever it last picked a
    # pathway (see _baseline_state) — never a function of the lever vector itself, so
    # they're computed per request and never stored in the cache. dict(data) keeps
    # the cached object pristine.
    baseline_levels, baseline_data = _baseline_state(body.get("baseline_key"))
    key, data = compute_pathway(levers)
    out = dict(data)
    out["changed"] = diff_outputs(data, baseline_data)
    out["lever_changes"] = lever_changes(levers, baseline_levels)
    out["kpi_deltas"] = kpi_deltas(data, baseline_data)
    out["pathway_key"] = key
    return jsonify(out)


@app.route("/cache_stats")
def cache_stats():
    return jsonify(dict(CACHE_STATS))


# ── Cache housekeeping ──────────────────────────────────────────────────────────
# The on-disk cache is pure disk pressure once a workbook edit or an output-schema
# change moves WORKBOOK_FP/OUTPUT_FP: every entry under the old fingerprint becomes
# permanently unreachable (pathway_key() can never produce that prefix again) and just
# sits there forever otherwise — confirmed live in this project's own cache/pathways/
# the day this was added: 1,264 of 1,304 files on disk were already dead from a retired
# output schema, with nothing ever removing them. And even under one unchanged
# fingerprint, ad hoc lever combinations from real traffic are an inexhaustible input
# space, so unpruned "live" entries would also grow without bound.
#
# Pruned automatically so nobody has to remember to run a script or set up a scheduled
# task: once at startup (cheap — a stat() per file, no model work, no MODEL_LOCK) and
# once a day thereafter in a background thread, for as long as this process lives.
# tools/prune_cache.py wraps the exact same prune()/enumerate_frontier() for anyone who
# would rather drive it externally (Windows Task Scheduler, cron) or run it once by
# hand — same function either way, so the two can't drift apart.
CACHE_MAX_AGE_DAYS = float(os.environ.get("IESS_CACHE_MAX_AGE_DAYS", "5"))
CACHE_PRUNE_INTERVAL_SECONDS = float(os.environ.get("IESS_CACHE_PRUNE_INTERVAL_SECONDS", 86400))
_CACHE_KEEP_PREFIX = WORKBOOK_FP + OUTPUT_FP


def _frontier_keep_keys():
    """Every key enumerate_frontier() would (re)compute, kept regardless of age so the
    always-fast presets/first-tweak frontier never itself goes cold from routine
    pruning and has to be recomputed on the next visitor who reaches it."""
    keys = set()
    for key, _vec in enumerate_frontier():
        keys.add(key)
        keys.add("deferred-" + key)
    return keys


def _run_cache_prune():
    try:
        result = prune_cache(
            CACHE_DIR, _CACHE_KEEP_PREFIX,
            max_age_seconds=CACHE_MAX_AGE_DAYS * 86400,
            keep_keys=_frontier_keep_keys(),
        )
        print(f"cache prune: kept {result['kept']}, deleted {result['deleted']} "
              f"({result['deleted_bytes'] / 1048576:.1f} MB)", flush=True)
    except Exception as e:
        # The cache is an optimisation; a prune failure must never take the server
        # down or block a request, the same posture cache_put() already takes.
        print(f"cache prune failed (non-fatal): {e}", flush=True)


def _cache_janitor_loop():
    while True:
        time.sleep(CACHE_PRUNE_INTERVAL_SECONDS)
        _run_cache_prune()


def start_cache_janitor():
    """Run the prune once now, then spawn the daily background thread.

    Deliberately NOT called at module scope. tools/precompute_pathways.py and
    tools/prune_cache.py both `import app` purely to reuse its already-loaded
    engine/config (WORKBOOK_FP, ALL_LEVER_ROWS, enumerate_frontier, ...) — that import
    must not have the side effect of actually deleting cache files itself, or a CLI
    tool's own --dry-run becomes a lie the moment it imports app.py to get at these
    helpers (found exactly this way while testing prune_cache.py: its "would delete: 0"
    dry-run report followed a startup log line that had already deleted 1,264 files).
    Called only from the __main__ guard below, i.e. only when this file is actually
    being run as the server.
    """
    _run_cache_prune()  # once at startup, synchronously — cheap, and means an
                         # operator sees the effect immediately in the startup log
                         # rather than wondering if the background thread is running.
    threading.Thread(target=_cache_janitor_loop, daemon=True).start()


if __name__ == "__main__":
    start_cache_janitor()
    app.run(debug=False, port=5051)
