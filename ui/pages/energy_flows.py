"""Energy Flows tab — Sankey diagram of national energy flow, source to end use.

This is the one view built around a single question ("where does the energy
actually go?"), and it is laid out for that question rather than for the
page's shared grid:

  - Full-bleed. The view cancels the page inset (.flows-view) so the diagram
    spans the whole window. A Sankey's readability is a direct function of its
    horizontal extent — five node columns and ~40 links — so width is not
    decoration here, it is the difference between legible and not.
  - No card chrome. The plot sits on the page ground with no border, radius or
    panel background; there is nothing to separate it FROM, since it is the
    only thing on the tab.
  - Its own control strip: one dark full-bleed band carrying the year
    selector, the total-supply readout and the node-colour key together,
    because all three are controls/legend for this one diagram rather than
    page furniture. The Insights rail is hidden on this tab (dashboard.js), so
    the strip is where this view's own context lives.

Uses render_year_buttons_html() from pages/tabs.py for the year tabs,
substituted into __YEAR_BUTTONS_HTML__ by app.py.
"""


def render():
    return """
    <div class="view flows-view" id="view-energy-flows">
      <div class="flows-strip">
        <div class="flows-strip-main">
          <span class="flows-strip-label">Flow year</span>
          <div class="year-tabs" id="year-tabs">__YEAR_BUTTONS_HTML__</div>
          <div class="sankey-total" id="sankey-total">Total primary supply: <b>–</b> Mtoe</div>
        </div>
        <div class="sankey-legend">
          <span><i class="dot" style="background:#22d3a8;color:#22d3a8"></i>Primary Source</span>
          <span><i class="dot" style="background:#4f9bf2;color:#4f9bf2"></i>Generation / Technology</span>
          <span><i class="dot" style="background:#f2b84b;color:#f2b84b"></i>Energy Carrier</span>
          <span><i class="dot" style="background:#e05263;color:#e05263"></i>Losses / Exports</span>
          <span><i class="dot" style="background:#7b6ef6;color:#7b6ef6"></i>Demand Sector</span>
        </div>
      </div>

      <div class="sankey-card">
        <svg id="sankeySvg"></svg>
        <div class="sankey-tooltip" id="sankey-tooltip"></div>
      </div>
    </div><!-- /view-energy-flows -->
"""
