"""All Energy tab — the landing view, and the one that answers "how big does
the energy system get, and what does it cost the atmosphere".

The four KPI cards are NOT four equal cards. Two of them are the answer to
that question (Final Demand 2047, Emissions 2047) and two are supporting
detail (Clean Share, Imported Fuel), so the layout says so: the headline pair
runs at roughly double width with display-sized figures, the supporting pair
is a narrow stack beside them at caption size. An equal four-up grid gave the
same visual weight to the number the whole model exists to project and to a
percentage derived from it.

The two headline charts are not twins either. Energy Supply carries ten legend
entries (nine source groups plus Total) against Energy Demand's eight, and one
of them — "Oil and petroleum products" — is the longest label on the page and
was being clipped in the equal-width duo. Supply therefore gets the wider
track (.chart-duo-supply-wide), sized to what its legend actually needs rather
than to a symmetric grid.

Populated by dashboard.js's renderOverviewKpis / applyResult.
"""


def render():
    return """
    <div class="view active" id="view-all-energy">
    <div class="stat-row">
      <!-- One grey tray (.stat-row) holding three white blocks. These were
           three separate cards each with its own accent colour and background
           wash (amber demand, green clean share, blue imports) — three
           readings of one scenario that looked like three unrelated widgets.
           The tray groups them; the gap and the tone step separate them, so
           there is no per-block colour and no divider. Each block lifts
           slightly on hover with its figure going accent blue. See the
           .stat-row block in dashboard.css. The .stat-demand / .stat-clean /
           .stat-imports classes are kept as hooks but style nothing. -->
      <div class="stat-card stat-card-lead stat-demand">
        <div class="stat-label">Final Demand 2047</div>
        <div class="stat-value" id="stat-demand-value">–</div>
        <div class="stat-note" id="stat-demand-note">–</div>
      </div>
      <!-- The "Emissions 2047" card stood here. Removed: the GHG gauge along
           the top of Custom Pathways is the same figure, live, on the same
           0-10 GtCO2 scale and reading from the same `emissions_2047_total`
           field — two readouts of one number on one screen. The gauge says
           more than the card did (it shows where the value sits on the scale),
           and the Insights panel still reports emissions before -> after,
           which is the one thing neither the card nor the gauge shows. -->
      <div class="stat-stack">
        <div class="stat-card stat-card-min stat-clean">
          <div class="stat-label">Clean Share</div>
          <div class="stat-min-figure">
            <span class="stat-value" id="stat-clean-value">–</span>
            <span class="stat-note stat-note-accent">renewables, hydro, nuclear</span>
          </div>
        </div>
        <div class="stat-card stat-card-min stat-imports">
          <div class="stat-label">Imported Fuel</div>
          <div class="stat-min-figure">
            <span class="stat-value" id="stat-imports-value">–</span>
            <span class="stat-note">of primary energy</span>
          </div>
        </div>
      </div>
    </div>

    <div class="chart-duo">
      <div class="panel" id="card-demand">
        <div class="panel-head">
          <h2>Energy Demand<span class="changed-note">CHANGED</span></h2>
          <span class="panel-unit">Mtoe</span>
        </div>
        <div class="chart-wrap-duo"><canvas id="demandChart"></canvas></div>
      </div>
      <div class="panel chart-duo-supply-wide" id="card-supply">
        <div class="panel-head">
          <h2>Energy Supply<span class="changed-note">CHANGED</span></h2>
          <span class="panel-unit">Mtoe</span>
        </div>
        <div class="chart-wrap-duo"><canvas id="supplyChart"></canvas></div>
      </div>
    </div>
    </div><!-- /view-all-energy -->
"""
