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
anything authored here.

Only SINGLE-lever rows carry a data-descs attribute. A bundled row's tooltip
is built by dashboard.js from the flyout rows for that sub-sector instead: it
lists one line per lever, each showing the level that lever is actually on and
that lever's own note. The notes are therefore emitted once, not twice."""

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
    # "Economics" -> "Economy" and "Costs" were top-level groups here. They are
    # sub-categories of "Other" now (see levers.py), where the row label comes
    # from the sub-category, not from this map: "Costs · 4", and — since
    # Economics holds exactly one lever — that lever's own Control-sheet name,
    # "Growth of the Economy". Neither needs an entry.
}

# One placement class per group, purely for its accent color in CSS.
GROUP_CLASSES = {
    "Demand side": "lg-box-demand",
    "Clean build-out": "lg-box-clean",
    "Conventional supply": "lg-box-conv",
    "Network and systems": "lg-box-network",
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
# The last column used to be Costs + Economics, two one-row groups stacked as
# two separate panels (the Key legend had been there before that, and was
# folded into the predefined-scenario control — which itself now lives in the
# pathway chip beside the tabs, see .pathway-chip in base.py). Both are
# sub-categories of "Other" now: one heading over Hydrogen Production, Costs
# and Growth of the Economy.
# "Other" sits UNDER "Network and systems" in the third column rather than
# taking a fourth of its own — Network is a single row, so a column each left
# one heading over one row beside one heading over three, and pushed Other up
# level with the other groups' headings as if it ranked with them. Stacked, the
# third column reads as one column of the smaller groups.
# Any group not listed here is appended to the LAST named column, so a new
# group would land beside Other — which is what "Other" means. Every group is
# listed explicitly anyway.
# Balanced by box height (rows + header), not by group count, so no single
# column drives the deck taller than it needs to be: Demand alone is 5 rows,
# Clean + Conventional are 2 each, Network is 1 and Other 3.
DECK_COLUMNS = [
    ["Demand side"],
    ["Clean build-out", "Conventional supply"],
    ["Network and systems", "Other"],
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


# Level 1 is the workbook's own "no new action" case and the top of each
# lever's F-column range is as far as the model will go, so those are the two
# things a track's ends actually mean. The ceiling word is per-LEVER, not
# global: rows 31/40/59-62 stop at 3 and row 49 runs to 5, so the same visual
# right-hand end is a different ambition depending on the row, and saying
# "maximum ambition" everywhere would flatten a real difference.
ENDPOINT_MIN = "business as usual"
CEILING_WORDS = {3: "aggressive", 4: "maximum ambition", 5: "maximum ambition (5)"}

# Track width is NOT set here — it is `.lg-lever-cell` in dashboard.css, and
# there is one width for every track.
#
# It was briefly a function of the row's lever count (64 + 11n, giving
# 75-152px) so that a row's reach into the model was visible in its control.
# The encoding was real but it read as raggedness: twelve tracks of twelve
# lengths, ending on twelve different x positions, with nothing lining up
# down the column. Reverted on the user's call — a control grid you scan
# down beats a second data channel nobody asked for. The lever count is
# still on the row (the "- 6" after its name) where it is a fact rather than
# a shape.
#
# A LEVER_TRACK_PX constant survived that revert here, rendered by nothing and
# free to drift out of step with the stylesheet that actually decides the
# width — which it duly did. Removed rather than kept in sync by hand.


def _lever_html(value, max_n, descs=None, lever_count=1):
    """A draggable lever: a native `<input type=range>` (drag the thumb,
    click anywhere on the track, or arrow-key it while focused — all built
    in, no pointer-math needed) overlaid on a styled track+fill, with tick
    marks for each level 1..max_n. The input drives everything via its own
    `input` event (dashboard.js's initLevers); this function renders the
    current value, and dashboard.js's updateLeverRow re-renders it (including
    the spread band, below) from the real lever values on every change.

    Every track is the same width (`.lg-lever-cell`, dashboard.css) and every
    track starts on the same x in its column, so the deck reads as one grid
    of controls.

    `max_n` still sets the tick count and the right-hand endpoint's label,
    because a row that stops at 3 genuinely does not reach the same ambition
    as one that runs to 5 — that is the model's own range, not a style
    choice, and the ticks are the snap positions the slider actually has.

    The endpoint words are NOT here — they are one note in the deck head, see
    scale_note_html.

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
    ceiling = CEILING_WORDS.get(max_n, f"level {max_n}")
    # The band is the row's real spread: empty (display:none) while every
    # lever underneath sits on the same level, and stretched from the lowest
    # to the highest as soon as they don't — which is the normal state on any
    # pathway above 1, since the levers have different ceilings.
    return (
        f'<span class="lg-lever-cell">'
        f'<div class="lg-lever" data-max="{max_n}" data-fills="{fills}" '
        f'data-levers="{lever_count}" data-ceiling="{ceiling}"{descs_attr}>'
        f'<div class="lg-lever-track"><div class="lg-lever-fill"></div>'
        f'<div class="lg-lever-band"></div>{ticks}'
        f'<div class="lg-lever-thumb"></div></div>'
        f'<input type="range" class="lg-lever-input" min="1" max="{max_n}" step="1" '
        f'value="{value}" aria-label="Ambition level, {ENDPOINT_MIN} to {ceiling}">'
        f'</div></span>')


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
        # lever_count=1 by definition here: a flyout row IS one Control-sheet
        # lever, so every track in the rail is the narrowest width. That the
        # rail's tracks are visibly shorter than the group row that opened it
        # is the point — the group row moves all of them at once.
        lever = _lever_html(lv["value"], lv["max"], lv.get("descs", {}), lever_count=1)
        rows.append(f"""
          <div class="lg-flyout-row lg-subcat-row" data-lever-ids="{lv['id']}">
            <span class="lg-flyout-name">{lv['name']}</span>
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
    group_slug = grp["group"].lower().replace(" ", "-")
    for idx, sc in enumerate(grp["subcats"]):
        levers = sc["levers"]
        avg_val = round(sum(lv["value"] for lv in levers) / len(levers)) if levers else 1
        lever_ids = ",".join(lv["id"] for lv in levers)
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
        # data-descs only for a single-lever row. A bundled row's dot is one
        # position over levers whose OWN level-N notes may not agree, so there
        # is no single honest sentence for it — and the answer is NOT to hand
        # the row all of them. Its tooltip describes the control itself (what
        # it moves, where it sits); the individual notes are read one at a time
        # by hovering the levers in that row's flyout, which is where each note
        # sits beside the lever it belongs to. See initLeverTooltip.
        row_descs = levers[0].get("descs", {}) if len(levers) == 1 else {}
        lever = _lever_html(avg_val, row_max, row_descs, lever_count=len(levers))
        count_hint = f" &middot; {len(levers)}" if len(levers) > 1 else ""
        label = _subcat_label(sc["category"], levers)
        # No `title` on the label any more. Long names are still ellipsised by
        # CSS, but a native title here meant TWO tooltips on one row: the
        # browser's own dark box over the name and the deck's white popup over
        # the track, in different places, in different styles, each saying half
        # of it. The popup is bound to the whole row now (initLeverTooltip) and
        # its first line is the full name, so hovering a truncated label still
        # reads it — in the one box that also says where the row sits.
        # A single-lever row has no flyout to open, so no chevron — but it
        # still reserves the chevron's slot. Without it the row's label (and
        # therefore its slider, which starts where the label ends) sat 19px
        # left of every expandable row's, so the tracks in a column with a
        # mix of both — Network and Systems, Costs/Economy — did not line up
        # with each other.
        expand_btn = '<span class="lg-expand-spacer" aria-hidden="true"></span>'
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
            <span class="lg-subcat-title">{label}<span class="lg-subcat-count">{count_hint}</span></span>
            {lever}
          </div>""")
    # No badge on the group head at all. It has now been three things and none
    # of them earned the space: "avg N.N" (an average of levels, which has no
    # unit and read "1.0" in all six boxes at once), then "21 levers - L3-4"
    # (real, but a lever COUNT is not something the reader is deciding
    # anything with, and six of them across the deck head was noise the user
    # called out directly). What the group is doing is legible from the rows
    # themselves — that is what the sliders are for — and the loaded pathway
    # is named twice already, in the deck's own select and in the chip beside
    # the tabs. So the head is just the group's name.
    place_cls = GROUP_CLASSES.get(grp["group"], "")
    title = GROUP_DISPLAY_NAMES.get(grp["group"], grp["group"])
    return f"""
      <div class="lg-box {place_cls}">
        <div class="lg-box-head">
          <span class="lg-box-title">{title}</span>
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
