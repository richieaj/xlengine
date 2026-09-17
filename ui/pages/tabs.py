"""Tab bar (top nav) and the Energy Flows tab's year-selector buttons.

The nine tabs are not nine equal modules, and the flat evenly-spaced row said
they were. They fall into three kinds, separable by what each one actually
puts on screen:

  Energy      — the physical system in energy units (Mtoe, GW). All Energy is
                the whole system, Electricity is the one sector deep-dive,
                Energy Flows is the same flow data drawn as a Sankey.
  Impacts     — what the pathway does to something other than energy:
                tonnes of CO2e, % import reliance, hectares, litres, minerals.
  Economy     — money and ratios: Billion INR, and the intensity indicators.

Critical Minerals is also the one tab with no model behind it yet (its page is
a "coming soon" note), so it is marked as upcoming rather than sitting in the
row looking like the other eight.
"""

from outputs import CHART_YEAR_LABELS

# (group label, [(tab label, view id or None if unbuilt)]) — declaration order
# is render order.
TAB_GROUPS = [
    ("Energy", [
        ("All Energy", "all-energy"),
        ("Electricity", "electricity"),
        ("Energy Flows", "energy-flows"),
    ]),
    ("Impacts", [
        ("Emissions", "emissions"),
        ("Energy Security", "energy-security"),
        ("Land & Water", "land-water"),
        ("Critical Minerals", "critical-minerals"),
    ]),
    ("Economy", [
        ("Costs", "costs"),
        ("Indicators", "indicators"),
    ]),
]

# Tabs whose page is a placeholder. Kept clickable (the page says so itself)
# but visually marked, because "there is nothing here yet" is real structure.
UPCOMING_TABS = {"Critical Minerals"}

# The Sankey is the one purpose-built view (full-bleed, own control strip —
# see energy_flows.py) and its tab is allowed to say so.
FEATURED_TABS = {"Energy Flows"}

ACTIVE_TAB = "All Energy"

TABS = [label for _, items in TAB_GROUPS for label, _ in items]
CLICKABLE_TABS = {label: view for _, items in TAB_GROUPS for label, view in items if view}


def render_tabs_html():
    groups = []
    for group_label, items in TAB_GROUPS:
        tabs = []
        for label, view in items:
            classes = ["pill-tab"]
            if label == ACTIVE_TAB:
                classes.append("active")
            if label in UPCOMING_TABS:
                classes.append("upcoming")
            if label in FEATURED_TABS:
                classes.append("featured")
            if not view:
                classes.append("disabled")
                tabs.append(f'<span class="{" ".join(classes)}" title="Coming soon">{label}</span>')
                continue
            tabs.append(f'<span class="{" ".join(classes)}" data-view="{view}">{label}</span>')
        groups.append(
            f'<span class="pill-group">'
            f'<span class="pill-group-label">{group_label}</span>'
            f'<span class="pill-group-tabs">{"".join(tabs)}</span>'
            f'</span>')
    return "".join(groups)


def render_year_buttons_html():
    items = []
    for y in CHART_YEAR_LABELS:
        cls = "year-btn active" if y == CHART_YEAR_LABELS[-1] else "year-btn"
        items.append(f'<button class="{cls}" data-year="{y}">{y}</button>')
    return "".join(items)
