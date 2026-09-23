
# Fine-grained row ranges mapped to one of the parent Control Deck groups.
# Group names/order originally came from the "Organic dashboard mockups" v2
# design; those loose mockup files have since been deleted (the live UI has
# diverged from them anyway) and survive only inside
# ../Organic dashboard mockups.zip if the provenance is ever needed.
# Economics and Costs weren't in that mockup at all (it showed 4 groups), so
# they were kept as two more top-level groups. They are now sub-categories of
# "Other" instead: each was a whole panel — its own heading, its own accent
# dot — standing over a single row, so the deck carried three headings
# ("Other", "Costs", "Economy") for what is three rows of the same kind of
# thing: the levers that are not demand, not supply and not network. One
# heading over three rows says the same thing with a third of the chrome.
# Panel titles shown to users live in pages/sidebar.py's
# GROUP_DISPLAY_NAMES, not here.
# The highest ambition level the MODEL actually implements, as opposed to the
# highest the Control sheet's LIMIT column advertises.
#
# Exactly one lever disagrees: row 49, "Fuel Switching Choices - Iron and
# Steel", has LIMIT = 5 and a real authored note in Control!L49 ("Increased use
# of Scrap") under a column headed "5 (or E)". But the calculation behind it was
# never written. Driven directly against the engine with every other lever held
# at 2:
#
#     level 1   demand 1588.05   supply 2026.24   emissions 5487.21
#     level 4   demand 1518.71   supply 1930.32   emissions 5080.23
#     level 5   demand 1588.05   supply 2026.24   emissions 5487.21
#
# Level 5 is bit-identical to level 1 across all three, which is what an Excel
# IF/CHOOSE chain does when it handles 1-4 and lets anything else fall through
# to the default branch. Three independent outputs agreeing to the last decimal
# is not coincidence.
#
# So offering level 5 was actively misleading, not merely cosmetic: dragging
# that slider to maximum silently computed the LEAST ambitious case while the
# UI showed the most ambitious. It also pushed the bundled "Industry" row to a
# 5-tick track, since a row's ceiling is the max of its members.
#
# Capped here rather than in the workbook because the workbook is the source of
# truth we read, not one we edit. app.py's ALL_LEVER_MAX derives from this, so
# the cap reaches the slider ticks, canonical_levels()'s clamping and
# enumerate_frontier() together. If the model ever gains a real level 5, raise
# this and the lever's own LIMIT governs again.
MODEL_MAX_LEVEL = 4

CATEGORY_RANGES = [
    # Order within a group follows this list; "Other" also takes the
    # unclassified leftovers, inserted ahead of these two (see load_levers).
    ("Costs",                        range(59, 63),                              "Other"),
    ("Economics",                    range(31, 32),                              "Other"),
    ("Demand — Transport",           range(33, 40),                              "Demand side"),
    ("Demand — Buildings",           range(40, 46),                              "Demand side"),
    ("Demand — Industry",            range(46, 50),                              "Demand side"),
    ("Demand — Cooking",             range(50, 52),                              "Demand side"),
    ("Demand — Agriculture & Telecom", range(52, 56),                            "Demand side"),
    ("Renewable Generation",         range(11, 19),                              "Clean build-out"),
    ("Bioenergy",                    range(21, 26),                              "Clean build-out"),
    ("Power Stations & CCS",         list(range(5, 8)) + list(range(9, 11)),     "Conventional supply"),
    ("Fossil Fuel Production",       range(27, 30),                              "Conventional supply"),
    ("Grid, Trade & Storage",        [19, 57, 58],                               "Network and systems"),
]

SIDEBAR_GROUP_ORDER = ["Demand side", "Clean build-out", "Conventional supply",
                       "Network and systems"]


def load_levers(eng):
    """Scan the Control sheet and return (sidebar_groups, all_lever_rows).

    sidebar_groups: [{"group": "Supply", "subcats": [{"category": ..., "levers": [...]}]}]
    all_lever_rows: {lever_id: row} flat map, used by /recalc.
    """
    # Columns H-K (8-11) hold the Control sheet's own per-level ambition
    # notes ("Ambition level 1: ...", etc, one column per level 1-4) — real
    # model documentation, not anything invented in the UI layer. Powers the
    # lever dot-track's hover tooltip in sidebar.py.
    names, limits, vals, descs = {}, {}, {}, {}
    for (sheet, r, c), cell in eng.m.cells.items():
        if sheet != "Control":
            continue
        if c == 4 and isinstance(cell.value, str) and cell.value.strip():
            names[r] = cell.value.strip()
        if c == 6 and isinstance(cell.value, (int, float)):
            # Capped at MODEL_MAX_LEVEL, because the Control sheet's LIMIT
            # column promises one level the model does not implement — see the
            # constant's own note.
            limits[r] = min(int(cell.value), MODEL_MAX_LEVEL)
        if c == 5 and isinstance(cell.value, (int, float)):
            vals[r] = int(cell.value)
        if c in (8, 9, 10, 11) and isinstance(cell.value, str) and cell.value.strip():
            descs.setdefault(r, {})[c - 7] = " ".join(cell.value.split())

    by_group = {g: [] for g in SIDEBAR_GROUP_ORDER}
    by_group["Other"] = []
    seen_rows = set()

    for cat_name, rows, group in CATEGORY_RANGES:
        items = []
        for r in rows:
            if r in vals and r in names:
                items.append({
                    "row": r,
                    "id": f"lv{r}",
                    "name": names[r],
                    "value": vals[r],
                    "max": limits.get(r, 4),
                    "descs": descs.get(r, {}),
                })
                seen_rows.add(r)
        if items:
            by_group.setdefault(group, []).append({"category": cat_name, "levers": items})

    leftovers = [
        {"row": r, "id": f"lv{r}", "name": names[r], "value": vals[r], "max": limits.get(r, 4),
         "descs": descs.get(r, {})}
        for r in sorted(vals)
        if r in names and r not in seen_rows
    ]
    if leftovers:
        # Ahead of Costs/Economics, not after them. "Other" now holds both the
        # genuinely unclassified rows AND the two small named groups folded
        # into it, and the unclassified ones are what the group is actually
        # named for — so they read first, with the named sub-categories under.
        by_group["Other"].insert(0, {"category": "Other", "levers": leftovers})

    sidebar_groups = []
    for g in SIDEBAR_GROUP_ORDER + ["Other"]:
        subcats = by_group.get(g, [])
        if subcats:
            count = sum(len(sc["levers"]) for sc in subcats)
            sidebar_groups.append({"group": g, "count": count, "subcats": subcats})

    all_lever_rows = {
        item["id"]: item["row"]
        for grp in sidebar_groups
        for sc in grp["subcats"]
        for item in sc["levers"]
    }
    return sidebar_groups, all_lever_rows
