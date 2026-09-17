"""Outer page shell, top to bottom: a full-bleed masthead band (product name
centred, menu button right), then a two-column grid — the tab row + active
tab's content, with the Insights card in a column to their right — then
Custom Pathways (the old "control deck") full-width again below that grid,
exactly like the masthead, and finally the site footer.

The Insights card only runs alongside the tab row/KPI cards/charts, not
Custom Pathways below it. It is `position:sticky` and sized by its own
content (never stretched to match the charts beside it), while the main
column is normal in-flow content that scrolls with the page. Its height is
not coupled to the active tab's chart height the way `.change-sidebar` used
to be — and must never be coupled to `--ui-scale` either, see the warning
in dashboard.css above `.pathway-rail`.

Each sub-sector in the deck is one flat row (name + 1..4 buttons); a row
bundling more than one real lever also gets a chevron that opens that group's
individual levers (rendered once via __LEVER_FLYOUTS_HTML__, one block per
multi-lever sub-sector) inside the deck's own slide-out rail — a further
column that animates from 0 width inside the fixed-width lever region
(.lg-cols), so the three lever columns visibly make room for it rather than
it floating over the charts above or shunting Insights sideways.
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
<!-- The font is self-hosted (ui/static/fonts, built by tools/build_fonts.py)
     and declared in dashboard.css. There is deliberately no font CDN here:
     this site sits next to a .gov.in domain, and the two <link>s that used to
     occupy these lines put Fontshare and Google Fonts in the critical render
     path of every page load and handed both a request from every visitor.

     ONE subsetted variable woff2, 42.7 KB, from our own origin — it replaced
     six static files totalling 102 KB when the interface went to Roboto for
     every role. One file also means the preload question disappears: there is
     no longer a judgement call about which faces draw first-paint text, and
     no second preload competing with the first.
     `crossorigin` is required even same-origin: font fetches are CORS-mode,
     and without it the preload is discarded and fetched a second time. -->
<link rel="preload" href="/static/fonts/roboto-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/static/css/dashboard.css">
</head>
<body>
<main class="page">
  <header class="site-banner">
    <span class="site-banner-side">
      <!-- Both logos are plated (white pad + rounded corners) on the dark
           band, for two different reasons:
             - NITI: the mark's ink is #01238E navy plus gold, which all but
               disappears against #3F4247, and recolouring an official emblem
               to white would throw its gold away.
             - ACPET: despite the file name, ACPET_LOGO_White.png is not a
               white-ink variant — it is RGB with NO alpha channel, i.e. a
               white background painted in. Verified from the PNG header. It
               can never be transparent, so on a dark band it is a white
               rectangle whether we like it or not; plating it just makes that
               rectangle deliberate and matched to the one opposite. -->
      <img class="site-banner-logo site-banner-logo-plated" src="/static/img/niti-aayog-logo-vector.svg" alt="NITI Aayog">
    </span>
    <span class="site-banner-title">India Energy Security Scenarios</span>
    <span class="site-banner-side site-banner-actions">
      <img class="site-banner-logo site-banner-logo-plated" src="/static/img/ACPET_LOGO_White.png" alt="ACPET">
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
    <div class="page-main">
      <div class="tab-row">
        <div class="pill-tabs">__TABS_HTML__</div>
        <!-- Pathway: one control, both readout and chooser.
             The predefined-scenario <select> used to live in the Custom
             Pathways head while this chip sat here naming the loaded pathway
             — two controls for one fact, in two places, and dashboard.js was
             already writing the same answer into both (updatePathwayName set
             the chip's text AND the select's value). Merging them removes the
             redundancy and puts the choice where the reader looks for the
             current state.
             A native <select>, deliberately: the four presets are mutually
             exclusive states of one thing, it gets the platform's own
             keyboard/touch behaviour for free, and it can display the "Custom
             pathway" state without inventing anything. That option is
             disabled because it is a state you reach by moving a lever, not
             one you can pick. The dot keeps the effort level readable as
             colour, on the same ramp as the levers themselves. -->
        <div class="pathway-chip" data-level="1">
          <span class="pathway-chip-dot" aria-hidden="true"></span>
          <label class="pathway-chip-label" for="scenario-select">Pathway</label>
          <select class="pathway-chip-select" id="scenario-select"
                  title="The pathway currently loaded across every lever. Moving any lever puts it into Custom pathway.">
            <option value="1">Least effort</option>
            <option value="2">Determined effort</option>
            <option value="3">Aggressive effort</option>
            <option value="4">Heroic effort</option>
            <option value="" disabled>Custom pathway</option>
          </select>
        </div>
      </div>

      <div class="main-col">
        __PAGES_HTML__
        <div id="error"></div>
      </div>
    </div>

  </div>

  <section class="control-deck-h">
    <!-- The deck's top edge used to be a purely decorative 2px gradient rule
         (.control-deck-h::before). It is a real gauge now: the pathway's own
         2047 GHG emissions, driven from the same emissions_2047_total the
         "EMISSIONS 2047" KPI card reads, on a fixed 0-10 GtCO2 scale.
         The scale is not invented — driving the four preset buttons gives
         9.6 / 5.3 / 2.8 / 2.0 GtCO2, so 10 Gt is the next round number above
         the worst case the model produces and the bar empties as a pathway
         gets more ambitious. dashboard.js's renderEmissionsBar()
         updates it on every recalc. -->
    <div class="cdh-emissions" id="cdh-emissions">
      <span class="cdh-emissions-label">GHG 2047</span>
      <div class="cdh-emissions-track">
        <div class="cdh-emissions-fill" id="cdh-emissions-fill"></div>
        <span class="cdh-emissions-value" id="cdh-emissions-value">&mdash;</span>
      </div>
      <span class="cdh-emissions-max">10 GtCO<sub>2</sub></span>
    </div>
    <div class="cdh-head">
      <!-- Title only. A one-line note explaining the sliders' endpoints used
           to sit under this; it went with the variable track widths it was
           half there to explain. The ends are legible from the control itself
           (level 1 at rest, ticks to the ceiling) and each row's own title
           attribute states its range in words. -->
      <div class="cdh-head-text">
        <span class="cr-title">Custom Pathways</span>
      </div>
      <!-- Empty until there is something true to report. It used to render
           "live" and then tick "live · 7:09:17 PM" once a second — a wall
           clock beside a projection that ends in 2047, which read as
           telemetry from a running system and was really the timestamp of the
           last fetch. dashboard.js's setStatus now only fills it while a
           recalculation is in flight, or when one failed; it is
           display:none while empty. -->
      <span id="status-chip"></span>
      <!-- The "Predefined scenarios" select lived here. It is the pathway
           chip beside the tabs now (see .pathway-chip in the tab row): that
           chip already named the loaded pathway, so a chooser here and a
           readout there were two controls reporting one fact. This head is
           the section title and the status chip. -->
    </div>
    <!-- Costs now renders as its own column here (see sidebar.py's
         DECK_COLUMNS), in the slot the Key box used to occupy. -->
    <div class="lever-grid" id="lever-grid">
      <!-- The lever region. Wrapping the columns and the rail in one box is
           what lets the levers "shrink and expand within their confined
           space": this box is a fixed width, so opening a sub-sector's rail
           narrows the three columns rather than displacing everything to its
           right. See .lg-cols in dashboard.css for the arithmetic. -->
      <div class="lg-cols" id="lg-cols">
        __SIDEBAR_HTML__
        <div class="lg-col lg-rail-col" id="lg-rail-col">
          <div class="lg-rail" id="lg-rail">__LEVER_FLYOUTS_HTML__</div>
        </div>
      </div>
      <!-- Insights, as the deck's right-hand column.
           It was a card in a second column of .page-grid, beside the charts.
           Two things were wrong with that: it squeezed every chart on every
           tab by ~270px of width for a panel holding three or four short
           lines, and the deck below already had that much unused space to the
           right of its lever columns — those are their own width and cluster
           left, so the band simply ran out of content.
           Moving it here fills that gap and gives the charts the whole page.
           It also belongs here by subject: it reports what the levers did, and
           the levers are in this band. It sits directly against the lever
           region rather than being flung to the window's right edge (the
           history is on .lg-insights-col), and carries the same navy rule the
           lever columns use between them, so the segregation reads the same
           way. -->
      <aside class="lg-insights-col" id="pathway-rail" aria-label="Insights">
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
    </div>
  </section>

  <!-- The "(Best viewed in 1920 x 1080 resolution, scale: 100%)" note that
       used to sit here is gone: the UI now measures the window and scales
       itself to fit (dashboard.js's fitUiScale), so there is no blessed
       resolution left to advise. -->
  <footer class="site-footer">
    &copy; 2026 NITI AAYOG | ACPET |
    DOWNLOADS: <a href="#">ONE PAGER DOCS</a> | <a href="#">IESS V3.0 EXCEL</a>
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
