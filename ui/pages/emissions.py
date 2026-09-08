"""Emissions tab — GHG emissions by sector and per-capita emissions."""


def render():
    return """
    <div class="view" id="view-emissions">
      <div class="chart-grid">
        <div class="card">
          <h3>Energy-related GHG Emissions</h3>
          <div class="card-sub">Million tonne CO2e — stacked area 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="emissionsBySectorChart"></canvas></div>
        </div>
        <div class="card">
          <h3>Per Capita GHG Emissions (Energy-related)</h3>
          <div class="card-sub">tonne CO2e per person — 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="perCapitaEmissionsChart"></canvas></div>
        </div>
      </div>
    </div><!-- /view-emissions -->
"""
