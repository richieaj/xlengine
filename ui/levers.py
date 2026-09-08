
# Fine-grained row ranges mapped to one of the parent Control Deck groups.
# Group names/order originally came from the "Organic dashboard mockups" v2
# design; those loose mockup files have since been deleted (the live UI has
# diverged from them anyway) and survive only inside
# ../Organic dashboard mockups.zip if the provenance is ever needed.
# Economics and Costs weren't in that mockup at all (it showed 4 groups);
# they're kept as their own groups, appended after, so no lever loses
# coverage. Panel titles shown to users live in pages/sidebar.py's
# GROUP_DISPLAY_NAMES, not here.
CATEGORY_RANGES = [
    ("Economics",                    range(31, 32),                              "Economics"),
    ("Costs",                        range(59, 63),                              "Costs"),
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
                       "Network and systems", "Economics", "Costs"]


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
            limits[r] = int(cell.value)
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
        by_group["Other"].append({"category": "Other", "levers": leftovers})

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
