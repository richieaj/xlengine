"""Energy Security tab — import dependence and energy imports."""


def render():
    return """
    <div class="view" id="view-energy-security">
      <div class="chart-grid">
        <div class="card">
          <h3>Import Dependence</h3>
          <div class="card-sub">% of demand met by imports — 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="esImportDependenceChart"></canvas></div>
        </div>
        <div class="card">
          <h3>Energy Imports</h3>
          <div class="card-sub">Mtoe — stacked area 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="energyImportsChart"></canvas></div>
        </div>
      </div>
    </div><!-- /view-energy-security -->
"""
