"""Tab bar (top nav) and the Energy Flows tab's year-selector buttons."""

from outputs import CHART_YEAR_LABELS

TABS = ["All Energy", "Electricity", "Energy Security", "Emissions",
        "Indicators", "Costs", "Energy Flows", "Land & Water", "Critical Minerals"]

CLICKABLE_TABS = {
    "All Energy": "all-energy",
    "Electricity": "electricity",
    "Energy Security": "energy-security",
    "Emissions": "emissions",
    "Indicators": "indicators",
    "Costs": "costs",
    "Energy Flows": "energy-flows",
    "Land & Water": "land-water",
    "Critical Minerals": "critical-minerals",
}

ACTIVE_TAB = "All Energy"


def render_tabs_html():
    items = []
    for t in TABS:
        if t in CLICKABLE_TABS:
            cls = "pill-tab active" if t == ACTIVE_TAB else "pill-tab"
            items.append(f'<span class="{cls}" data-view="{CLICKABLE_TABS[t]}">{t}</span>')
        else:
            items.append(f'<span class="pill-tab disabled" title="Coming soon">{t}</span>')
    return "".join(items)


def render_year_buttons_html():
    items = []
    for y in CHART_YEAR_LABELS:
        cls = "year-btn active" if y == CHART_YEAR_LABELS[-1] else "year-btn"
        items.append(f'<button class="{cls}" data-year="{y}">{y}</button>')
    return "".join(items)
