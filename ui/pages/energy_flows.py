"""Energy Flows tab — Sankey diagram of national energy flow, source to end use.

Uses render_year_buttons_html() from pages/tabs.py for the year-tab toolbar,
substituted into __YEAR_BUTTONS_HTML__ by app.py the same way it is today.
The one tab that gets a very visible, big dedicated space — see #sankeySvg's
own sizing in dashboard.css — since it's the headline view of the whole site.
"""


def render():
    return """
    <div class="view" id="view-energy-flows">
      <div class="sankey-toolbar">
        <div class="year-tabs" id="year-tabs">__YEAR_BUTTONS_HTML__</div>
        <div class="sankey-total" id="sankey-total">Total primary supply: <b>–</b> Mtoe</div>
      </div>

      <div class="sankey-card">
        <svg id="sankeySvg"></svg>
        <div class="sankey-tooltip" id="sankey-tooltip"></div>
      </div>

      <div class="sankey-legend">
        <span><i class="dot" style="background:#22d3a8;color:#22d3a8"></i>Primary Source</span>
        <span><i class="dot" style="background:#4f9bf2;color:#4f9bf2"></i>Generation / Technology</span>
        <span><i class="dot" style="background:#f2b84b;color:#f2b84b"></i>Energy Carrier</span>
        <span><i class="dot" style="background:#e05263;color:#e05263"></i>Losses / Exports</span>
        <span><i class="dot" style="background:#7b6ef6;color:#7b6ef6"></i>Demand Sector</span>
      </div>
    </div><!-- /view-energy-flows -->
"""
