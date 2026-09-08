"""Renders the lever grid — a row of rounded boxes (one per Control-sheet
group), each listing its sub-sectors as a single flat row: name on the left,
a draggable 1..N "ambition level" lever on the right (a native range input
styled as a track + filled bar + round thumb, with a tick per level — drag
the thumb, click the track, or arrow-key it while focused). A sub-sector
bundling more than one real lever also gets a chevron opening that group's
individual levers in the deck's slide-out rail (see render_sidebar_html).
Each row still drives every real Control-sheet row underneath it (via
hidden inputs) — moving the lever snaps all of them together.

Hovering (or focusing) a lever shows the Control sheet's own ambition-level
note for its CURRENT value (dashboard.js's lever-tooltip) — real model
documentation (columns H-K on the Control sheet, read by levers.py), not
anything authored here. Only single-lever rows carry descriptions: a
multi-lever sub-sector's shared lever is an AVERAGE across levers that may
each mean something different at that level, so no one description could
honestly describe it."""

import html
import json

# Effort-level ramp, index 0 = level 1, reading minimum-action -> all-out
# effort. dashboard.js re-reads it per lever via data-fills (see _lever_html)
# on every drag/update.
#
# The comment that used to sit here argued for level 1 being a cyan rather
# than a grey, on the grounds that a slate level 1 read as "unset" — but the
# deck it was written for was dark, and it is a light panel now. On this
# panel the cyan just looked out of place, and it never matched the level-1
# slate used by the pathway dots/chip anyway.
#
# The effort ramp is defined once, in dashboard.css's :root (--lvl-1..5).
# These emit references rather than hex so the two can't drift apart the way
# they had: level 1 here used to be a cyan (#29B6C7) that matched nothing
# else in the interface. paintLever() in dashboard.js drops the chosen entry
# straight into the --lg-lever-color custom property, and a custom property
# is allowed to hold a var() reference, so this resolves at use.
LEVEL_FILL = ["var(--lvl-1)", "var(--lvl-2)", "var(--lvl-3)", "var(--lvl-4)", "var(--lvl-5)"]

# Panel titles use the reference IESS site's own vocabulary rather than the
# internal group keys from levers.py — the officials reading this screen
# know these terms. Keys stay untouched so levers.py/app.py are unaffected.
GROUP_DISPLAY_NAMES = {
    "Demand side": "Demand",
    "Clean build-out": "Supply &mdash; Renewable and Clean Energy",
    "Conventional supply": "Supply &mdash; Conventional Energy",
    "Network and systems": "Network and Systems",
    "Economics": "Economy",
    "Costs": "Costs",
}

# One placement class per group, purely for its accent color in CSS.
GROUP_CLASSES = {
    "Demand side": "lg-box-demand",
    "Clean build-out": "lg-box-clean",
    "Conventional supply": "lg-box-conv",
    "Network and systems": "lg-box-network",
    "Economics": "lg-box-econ",
    "Costs": "lg-box-costs",
    "Other": "lg-box-other",
}

# Which deck column each group stacks into. Groups are emitted inside
# explicit column wrappers rather than placed on a shared CSS grid, because
# grid rows span all columns: a 5-sub-sector group (Demand) next to a
# 2-sub-sector one (Clean build-out) forced every following box down past
# the tall one and left a large void. Flex stacks per column let each column
# pack independently, which is what keeps the deck dense — and dense is the
# point, since the deck is fixed-height and the charts above get whatever
# vertical space it doesn't take.
#
# Costs + Economics now share the last column (it used to be Key's slot —
# the Key legend itself was folded into the "Predefined scenarios" buttons
# next to the heading, see .cdh-pathway-btn in base.py). Any group not
# listed here is appended to the last NAMED column below (Network and
# systems), not to Costs/Economics, so a future group can't silently land
# in that column — that's why "Other" is listed explicitly rather than
# left to the fallback.
# Balanced by box height (rows + header), not by group count, so no single
# column drives the deck taller than it needs to be: Demand alone is 5 rows,
# Clean + Conventional are 2 each, the rest are 1 apiece.
DECK_COLUMNS = [
    ["Demand side"],
    ["Clean build-out", "Conventional supply"],
    ["Network and systems", "Other"],
    ["Costs", "Economics"],
]


def _subcat_label(category, levers):
    """Row label. A sub-category holding exactly one lever shows that
    lever's own Control-sheet name — otherwise a single-lever group renders
    as a box titled "Growth of the Economy" containing a row labelled
    "Economics", which tells the reader nothing twice."""
    if len(levers) == 1:
        return levers[0]["name"]
    if " — " in category:
        return category.split(" — ", 1)[1]
    return category


def _lever_html(value, max_n, descs=None):
    """A draggable lever: a native `<input type=range>` (drag the thumb,
    click anywhere on the track, or arrow-key it while focused — all built
    in, no pointer-math needed) overlaid on a styled track+fill, with tick
    marks for each level 1..max_n. The input drives everything via its own
    `input` event (dashboard.js's initLevers); this function only renders
    the current value.

    `descs`, when given, is {level: ambition-note} from the Control sheet
    (see levers.py) — passed through as one JSON attribute rather than a
    per-level element, since a single slider has no per-level DOM to hang
    a tooltip off; dashboard.js reads the current value back out of it."""
    fills = ",".join(LEVEL_FILL[: min(max_n, len(LEVEL_FILL))])
    descs_attr = ""
    if descs:
        d = {str(n): descs[n] for n in range(1, max_n + 1) if descs.get(n)}
        if d:
            descs_attr = f" data-descs='{html.escape(json.dumps(d))}'"
    ticks = "".join(f'<span class="lg-lever-tick" style="left:{100 * (n - 1) / (max_n - 1) if max_n > 1 else 0}%"></span>'
                    for n in range(1, max_n + 1))
    return (
        f'<div class="lg-lever" data-max="{max_n}" data-fills="{fills}"{descs_attr}>'
        f'<div class="lg-lever-track"><div class="lg-lever-fill"></div>{ticks}'
        f'<div class="lg-lever-thumb"></div></div>'
        f'<input type="range" class="lg-lever-input" min="1" max="{max_n}" step="1" '
        f'value="{value}" aria-label="Ambition level">'
        f'</div>')


def _render_flyout(flyout_id, label, levers):
    """The individual-lever panel for one multi-lever sub-sector, shown one at
    a time inside the deck's slide-out rail (see render_sidebar_html). Reuses
    _lever_html per lever instead of per average, and gives each flyout
    row the same data-lever-ids shape (one id) that updateLeverRow already
    knows how to read — no new highlighting logic needed in JS.
    Each lever gets its OWN max (not a shared one) — unlike the group's quick-
    set row, a flyout row controls exactly one real Control-sheet lever, so
    there's no other lever's lower ceiling to respect."""
    rows = []
    for lv in levers:
        lever = _lever_html(lv["value"], lv["max"], lv.get("descs", {}))
        rows.append(f"""
          <div class="lg-flyout-row lg-subcat-row" data-lever-ids="{lv['id']}">
            <span class="lg-flyout-name" title="{lv['name']}">{lv['name']}</span>
            {lever}
          </div>""")
    return f"""
      <div class="lg-flyout" id="{flyout_id}" role="group" aria-label="{label} — individual levers">
        <div class="lg-flyout-head">
          <span>{label}</span>
          <button type="button" class="lg-flyout-close" data-flyout-close="{flyout_id}" aria-label="Close">&times;</button>
        </div>
        <div class="lg-flyout-rows">{''.join(rows)}</div>
      </div>"""


def _render_box(grp, flyouts):
    """One group panel: title + avg badge, then one flat row per sub-sector
    (label + 1..N draggable lever, N usually 4 but sometimes lower — see
    below), plus the hidden inputs that hold every real Control-sheet lever
    value underneath. Sub-sectors with more than one lever also get a
    chevron that opens the deck's slide-out rail (its content appended to
    `flyouts`) listing each individual lever's own control."""
    subcat_rows = []
    hidden_inputs = []
    group_values = []
    group_lever_ids = []
    group_slug = grp["group"].lower().replace(" ", "-")
    for idx, sc in enumerate(grp["subcats"]):
        levers = sc["levers"]
        avg_val = round(sum(lv["value"] for lv in levers) / len(levers)) if levers else 1
        lever_ids = ",".join(lv["id"] for lv in levers)
        group_values.extend(lv["value"] for lv in levers)
        group_lever_ids.extend(lv["id"] for lv in levers)
        for lv in levers:
            hidden_inputs.append(
                f'<input type="hidden" id="{lv["id"]}" value="{lv["value"]}" data-max="{lv["max"]}">')
        # The shared row spans the WIDEST range any of its levers can take,
        # not the narrowest. min() was wrong: Buildings bundles six levers of
        # which only "Growth of floorspace" (lv40) caps at 3, so a min() row
        # stopped at 3 and there was no way to push the other five to 4 from
        # the group control at all. Industry had the same bug pointing the
        # other way — its "Fuel Switching Choices - Iron and Steel" (lv49)
        # goes to 5, and a min() row of 4 could never reach it.
        #
        # Offering a level some member can't take is safe because nothing
        # downstream trusts the row: setLeverLevel() in dashboard.js clamps
        # every lever to its own data-max as it writes, so a row dragged to 4
        # leaves lv40 at 3 and its siblings at 4. updateLeverRow() knows to
        # read that back as a saturated row rather than a mixed one.
        row_max = max((lv["max"] for lv in levers), default=4)
        # Tooltip descriptions only for a single-lever row: a multi-lever
        # row's dot is an average across levers whose OWN level-N notes may
        # not agree with each other, so there's no one honest sentence for
        # the shared dot to show.
        row_descs = levers[0].get("descs", {}) if len(levers) == 1 else {}
        lever = _lever_html(avg_val, row_max, row_descs)
        count_hint = f" &middot; {len(levers)}" if len(levers) > 1 else ""
        label = _subcat_label(sc["category"], levers)
        # Long lever names get ellipsised by CSS, so the tooltip carries the
        # label actually shown plus how many levers it moves — not the parent
        # category, which told you nothing about a truncated row.
        tip = f"{label} ({len(levers)} levers)" if len(levers) > 1 else label
        expand_btn = ""
        if len(levers) > 1:
            flyout_id = f"flyout-{group_slug}-{idx}"
            expand_btn = (
                f'<button type="button" class="lg-expand-btn" aria-expanded="false" '
                f'aria-controls="{flyout_id}" data-flyout="{flyout_id}" '
                f'aria-label="Show individual levers for {label}">'
                f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
                f'stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></button>')
            flyouts.append(_render_flyout(flyout_id, label, levers))
        subcat_rows.append(f"""
          <div class="lg-subcat-row" data-lever-ids="{lever_ids}">
            {expand_btn}
            <span class="lg-subcat-title" title="{tip}">{label}<span class="lg-subcat-count">{count_hint}</span></span>
            {lever}
          </div>""")
    avg_all = round(sum(group_values) / len(group_values), 1) if group_values else 1.0
    place_cls = GROUP_CLASSES.get(grp["group"], "")
    title = GROUP_DISPLAY_NAMES.get(grp["group"], grp["group"])
    return f"""
      <div class="lg-box {place_cls}" data-lever-ids="{','.join(group_lever_ids)}">
        <div class="lg-box-head">
          <span class="lg-box-title">{title}</span>
          <span class="lg-box-avg">avg {avg_all:.1f}</span>
        </div>
        <div class="lg-subcats">{''.join(subcat_rows)}</div>
        {''.join(hidden_inputs)}
      </div>"""


def render_sidebar_html(sidebar_groups):
    """Returns (columns_html, flyouts_html). Flyouts are collected separately
    because they all render inside the deck's one shared slide-out rail (a
    5th lever-grid column in base.py), not as descendants of the individual
    (overflow:hidden) group boxes they belong to."""
    by_name = {grp["group"]: grp for grp in sidebar_groups}
    placed = {name for col in DECK_COLUMNS for name in col}
    columns = [list(col) for col in DECK_COLUMNS]
    # Any group DECK_COLUMNS doesn't mention still has to render somewhere.
    columns[-1].extend(grp["group"] for grp in sidebar_groups if grp["group"] not in placed)

    flyouts = []
    out = []
    for i, col_groups in enumerate(columns, start=1):
        boxes = "".join(_render_box(by_name[name], flyouts) for name in col_groups if name in by_name)
        if boxes:
            out.append(f'<div class="lg-col lg-col-{i}">{boxes}</div>')
    return "".join(out), "".join(flyouts)
