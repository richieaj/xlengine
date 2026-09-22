"""Concurrent load generator for the IESS dashboard.

Stdlib only -- no pip install, so it runs anywhere python does, including
against a deployed URL from a laptop.

Why this exists: the evaluator is single-threaded and every engine call is
serialised behind one process-global MODEL_LOCK (ui/app.py:105). Cache HITS
never touch it and cost ~2 ms; a cache MISS costs ~800 ms and blocks every
other engine call for that time. So the app has two completely different
performance regimes, and "is it fast enough" has no single answer -- it
depends entirely on how much of the traffic is already cached.

Hence --mix:

  warm   Everyone clicks presets and nudges single levers. Every request is
         a pre-computed cache hit. This is what a real demo looks like, and
         it should stay flat no matter how many users you add.

  cold   Every user invents a random 51-lever vector nobody has computed.
         Every request is a cache miss. This is the deliberate
         breaking-point test: throughput is capped at ~1/0.8s no matter how
         many users pile on, and latency grows linearly as they queue. That
         is MODEL_LOCK working correctly, not a bug.

  mixed  90% warm, 10% cold -- closer to a real audience, where most people
         click around and a few go exploring.

Usage:
    python tools/loadtest.py --url http://localhost:8080 --users 30 --seconds 30
    python tools/loadtest.py --url https://... --users 30 --mix cold
"""

import argparse
import json
import random
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

TIMEOUT = 120


def fetch_lever_ids(base):
    """Read the real lever ids out of the served page, so the generated
    vectors are valid for whatever workbook the target is running."""
    html = urllib.request.urlopen(base + "/", timeout=60).read().decode("utf-8", "replace")
    m = re.search(r"leverIds\s*:\s*(\[[^\]]*\])", html)
    if not m:
        raise SystemExit("could not find leverIds in the page -- is this the right URL?")
    return json.loads(m.group(1))


def request(base, path, payload=None):
    """One request. Returns (elapsed_ms, status, pathway_key_or_None).

    A 429 is a normal, expected outcome under load -- it is the app's rate
    limiter doing its job -- so it is returned as a status rather than raised.
    """
    url = base + path
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data, headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read()
            ms = (time.perf_counter() - t0) * 1000
            key = None
            if body[:1] == b"{":
                try:
                    key = json.loads(body).get("pathway_key")
                except Exception:
                    pass
            return ms, r.status, key
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - t0) * 1000, e.code, None
    except Exception:
        return (time.perf_counter() - t0) * 1000, 0, None   # 0 == connection failure


def user_loop(base, ids, mix, stop_at, results, lock, rng):
    """One simulated person: load the page, pick a pathway, then tweak levers
    with a little think-time between actions, the way a human actually does."""
    local = []
    ms, st, _ = request(base, "/")
    local.append(("GET /", ms, st))

    level = rng.choice([1, 2, 3, 4])
    ms, st, key = request(base, "/set_scenario", {"level": level})
    local.append(("set_scenario", ms, st))
    vec = {i: level for i in ids}

    while time.time() < stop_at:
        cold = (mix == "cold") or (mix == "mixed" and rng.random() < 0.10)
        v = dict(vec)
        if cold:
            # A vector nobody has computed: guaranteed cache miss, real engine work.
            for i in ids:
                v[i] = rng.randint(1, 4)
        else:
            # A single-lever nudge from a preset -- exactly what the frontier
            # cache was pre-computed to cover, so this should be a hit.
            v[rng.choice(ids)] = rng.randint(1, 4)

        ms, st, _ = request(base, "/recalc", {"levers": v, "baseline_key": key})
        local.append(("recalc-" + ("cold" if cold else "warm"), ms, st))

        # Occasionally open the Energy Flows tab, which asks for the Sankey.
        if rng.random() < 0.15:
            ms, st, _ = request(base, "/deferred", {"levers": v})
            local.append(("deferred", ms, st))

        time.sleep(rng.uniform(0.3, 1.5))   # human think-time

    with lock:
        results.extend(local)


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
    return s[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--users", type=int, default=30)
    ap.add_argument("--seconds", type=int, default=30)
    ap.add_argument("--mix", choices=["warm", "cold", "mixed"], default="warm")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    base = args.url.rstrip("/")
    print(f"target   {base}")
    ids = fetch_lever_ids(base)
    print(f"levers   {len(ids)} found")
    print(f"load     {args.users} users x {args.seconds}s, mix={args.mix}\n")

    results, lock = [], threading.Lock()
    stop_at = time.time() + args.seconds
    threads = [
        threading.Thread(
            target=user_loop,
            args=(base, ids, args.mix, stop_at, results, lock, random.Random(args.seed + n)),
            daemon=True,
        )
        for n in range(args.users)
    ]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=args.seconds + TIMEOUT)
    wall = time.time() - t0

    if not results:
        raise SystemExit("no results -- could not reach the target")

    codes = Counter(st for _, _, st in results)
    ok = [ms for _, ms, st in results if st == 200]

    print(f"{'request':<16}{'n':>7}{'p50':>9}{'p95':>9}{'p99':>9}{'max':>9}")
    for kind in ("GET /", "set_scenario", "recalc-warm", "recalc-cold", "deferred"):
        v = [ms for k, ms, st in results if k == kind and st == 200]
        if v:
            print(f"{kind:<16}{len(v):>7}{pct(v,50):>9.0f}{pct(v,95):>9.0f}"
                  f"{pct(v,99):>9.0f}{max(v):>9.0f}")
    print(f"\n{'ALL OK':<16}{len(ok):>7}{pct(ok,50):>9.0f}{pct(ok,95):>9.0f}"
          f"{pct(ok,99):>9.0f}{max(ok) if ok else 0:>9.0f}   (ms)")
    print(f"\nthroughput   {len(results)/wall:.1f} req/s over {wall:.1f}s")
    print("status codes " + "  ".join(
        f"{('CONN-FAIL' if c == 0 else c)}={n}" for c, n in sorted(codes.items())))

    rl = codes.get(429, 0)
    fail = codes.get(0, 0)
    print()
    if rl:
        print(f"!! {rl} rate-limited (429). The limiter is per-IP and every one of "
              f"these users shares yours.\n"
              f"   Raise it: docker run -e IESS_RATE_LIMIT_MAX=20000 ...")
    if fail:
        print(f"!! {fail} connection failures -- the server refused or dropped these.")
    if not rl and not fail:
        print("no 429s, no dropped connections.")


if __name__ == "__main__":
    main()
