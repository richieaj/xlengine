"""Outer page shell, top to bottom: a full-bleed masthead band (product name
centred, menu button right), then a two-column grid — an Insights rail on
the left, the tab row + active tab's content in the remaining column on the
right — then Custom Pathways (the old "control deck") full-width again
below that grid, exactly like the masthead, and finally the site footer.

The rail only runs alongside the tab row/KPI cards/charts, not Custom
Pathways below it — it's `position:sticky` and scrolls internally if its
own content outgrows the viewport, while the main column (just the tab row
+ active tab's content now) is normal in-flow content and scrolls with the
page. The rail's height is no longer coupled to the active tab's chart
height the way `.change-sidebar` used to be.

Each sub-sector in the deck is one flat row (name + 1..4 buttons); a row
bundling more than one real lever also gets a chevron that opens that group's
individual levers (rendered once via __LEVER_FLYOUTS_HTML__, one block per
multi-lever sub-sector) inside the deck's own slide-out rail — a 5th
lever-grid column that animates from 0 width, so the three lever columns
visibly make room for it rather than it floating over the charts above.
(Unrelated to the page-level "rail" above other than sharing the name.)

The rail's Insights block is persistent across every tab and permanently
rendered (no button/toggle) — a plain-language readout of global lever
state, the same underlying data the pathway chip summarises at a glance:
`data.lever_changes` / `data.kpi_deltas` on every recalc response, turned
into prose by dashboard.js's renderInsights(). The rail is hidden on the
Energy Flows tab only, so the Sankey gets the extra width.

Content is assembled by app.py via the same str.replace() token-substitution
pattern already used in this project (never %-formatting — see the historical
note in CLAUDE_CODE_PROJECT_CONTEXT.md about the width:100% bug).
"""


def render_base():
    return """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IESS 2047 — India Energy Security Scenarios</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/css/dashboard.css">
</head>
<body>
<main class="page">
  <header class="site-banner">
    <span class="site-banner-side">
      <img class="site-banner-logo" src="/static/img/niti-aayog-logo-vector.svg" alt="NITI Aayog">
    </span>
    <span class="site-banner-title">India Energy Security Scenarios</span>
    <span class="site-banner-side site-banner-actions">
      <img class="site-banner-logo" src="/static/img/ACPET_LOGO_White.png" alt="ACPET">
      <button type="button" class="menu-btn" id="app-menu-btn"
              aria-label="Menu" aria-haspopup="true" aria-expanded="false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M4 7h16M4 12h16M4 17h16"/>
        </svg>
      </button>
    </span>
  </header>

  <!-- Right-hand slide-in drawer. Destinations are placeholders (href="#")
       until the real URLs land; FEEDBACK needs a real mailbox address. -->
  <div class="drawer" id="app-menu" role="dialog" aria-modal="true" aria-label="Site menu">
    <div class="drawer-head">
      <button type="button" class="drawer-close" id="app-menu-close" aria-label="Close menu">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18"/>
        </svg>
      </button>
    </div>
    <nav class="drawer-nav">
      <a class="drawer-item" href="#">How-to</a>
      <a class="drawer-item" href="#">Videos<svg class="drawer-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-8 8"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>
      <a class="drawer-item" href="#">Project<svg class="drawer-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-8 8"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>
      <a class="drawer-item" href="#">Science<svg class="drawer-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-8 8"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg></a>
      <a class="drawer-item" href="#">Feedback<svg class="drawer-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg></a>
      <a class="drawer-item" href="#">Legal</a>
    </nav>
  </div>

  <div class="page-grid">
    <!-- Full-height rail: sticky within the viewport, own internal scroll if
         its content outgrows it. Hidden on Energy Flows only (dashboard.js
         also collapses .page-grid's own rail column via .rail-hidden), same
         as .change-sidebar used to be. Insights only now — no separate
         Pathway Impact block; renderInsights() (dashboard.js) already
         covers the same underlying lever/KPI data in prose form. -->
    <aside class="pathway-rail" id="pathway-rail">
      <div class="rail-insights">
        <div class="rail-insights-head">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.5 1 2.5h6c0-1 .4-1.9 1-2.5A6 6 0 0 0 12 3Z"/>
          </svg>
          Insights
        </div>
        <div class="rail-insights-body" id="insights-panel-body"></div>
      </div>
    </aside>

    <div class="page-main">
      <div class="tab-row">
        <div class="pill-tabs">__TABS_HTML__</div>
        <span class="pathway-chip" data-level="1" title="The pathway currently loaded across every lever">
          <span class="pathway-chip-dot" aria-hidden="true"></span>
          <span class="pathway-chip-label">Pathway</span>
          <span class="pathway-chip-value" id="pathway-name">Custom pathway</span>
        </span>
      </div>

      <div class="main-col">
        __PAGES_HTML__
        <div id="error"></div>
      </div>
    </div>
  </div>

  <!-- Full-width again, outside .page-grid: the rail (Insights) only ever
       covers the tab row + KPI cards + charts above, so it ends where they
       end instead of running down alongside this too. -->
  <section class="control-deck-h">
    <div class="cdh-head">
      <div class="cdh-head-text">
        <span class="cr-title">Custom Pathways</span>
      </div>
      <span id="status-chip">live</span>
      <!-- Predefined scenarios: one merged, all-clickable control — used to
           be a static Key legend (labels, no click) plus a separate bare
           1..4 "Example pathway" selector (click, no labels). Each button
           now carries both: the level's own name as its label (setScenario
           in dashboard.js reads data-level, unchanged) and a small dot in
           that level's ramp color (the same colors .lg-lever/LEVEL_FILL
           use), so there's one place to both see what each level means and
           pick one. -->
      <div class="cdh-pathway">
        <span class="cdh-pathway-label">Predefined scenarios</span>
        <div class="cdh-pathway-buttons" id="scenario">
          <button type="button" class="cdh-pathway-btn active" data-level="1">
            <span class="cdh-pathway-btn-dot" style="background:#9AA3B2"></span>Least effort
          </button>
          <button type="button" class="cdh-pathway-btn" data-level="2">
            <span class="cdh-pathway-btn-dot" style="background:#5468DC"></span>Determined effort
          </button>
          <button type="button" class="cdh-pathway-btn" data-level="3">
            <span class="cdh-pathway-btn-dot" style="background:#3B62FF"></span>Aggressive effort
          </button>
          <button type="button" class="cdh-pathway-btn" data-level="4">
            <span class="cdh-pathway-btn-dot" style="background:#00C08B"></span>Heroic effort
          </button>
        </div>
      </div>
    </div>
    <!-- Costs now renders as its own column here (see sidebar.py's
         DECK_COLUMNS), in the slot the Key box used to occupy. -->
    <div class="lever-grid" id="lever-grid">
      __SIDEBAR_HTML__
      <div class="lg-col lg-rail-col" id="lg-rail-col">
        <div class="lg-rail" id="lg-rail">__LEVER_FLYOUTS_HTML__</div>
      </div>
    </div>
  </section>

  <footer class="site-footer">
    &copy; 2023 NITI AAYOG | DESE ACPET |
    (Best viewed in 1920 x 1080 resolution, scale: 100%) |
    DOWNLOADS: <a href="#">ONE PAGER DOCS</a> | <a href="#">IESS V3.0 EXCEL</a> | <a href="#">VIDEO</a>
  </footer>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-array@3"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-path@3"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-shape@3"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-selection@3"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12"></script>
<script>
  window.APP_CONFIG = { leverIds: __IDS_JSON__, defaultSankeyYear: "__DEFAULT_SANKEY_YEAR__" };
</script>
<script src="/static/js/dashboard.js"></script>
</body>
</html>
"""
