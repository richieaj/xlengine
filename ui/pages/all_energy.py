"""All Energy tab — 4 KPI stat cards (Final Demand, Clean Share, Imported
Fuel, Emissions 2047 — populated by dashboard.js's renderOverviewKpis) plus
the two headline stacked-area charts (Energy Demand / Energy Supply) as an
equal-width duo, matching the reference site's own top-of-page layout.
"""


def render():
    return """
    <div class="view active" id="view-all-energy">
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-label">Final Demand 2047</div>
        <div class="stat-value" id="stat-demand-value">–</div>
        <div class="stat-note" id="stat-demand-note">–</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Clean Share</div>
        <div class="stat-value" id="stat-clean-value">–</div>
        <div class="stat-note stat-note-accent">renewables, hydro, nuclear</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Imported Fuel</div>
        <div class="stat-value" id="stat-imports-value">–</div>
        <div class="stat-note">of primary energy</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Emissions 2047</div>
        <div class="stat-value" id="stat-emissions-value">–</div>
        <div class="stat-note">energy-related, gross</div>
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
      <div class="panel" id="card-supply">
        <div class="panel-head">
          <h2>Energy Supply<span class="changed-note">CHANGED</span></h2>
          <span class="panel-unit">Mtoe</span>
        </div>
        <div class="chart-wrap-duo"><canvas id="supplyChart"></canvas></div>
      </div>
    </div>
    </div><!-- /view-all-energy -->
"""
