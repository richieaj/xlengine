"""Land & Water Use tab."""


def render():
    return """
    <div class="view" id="view-land-water">
      <div class="chart-grid">
        <div class="card">
          <h3>Land Use</h3>
          <div class="card-sub">Hectares — stacked area 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="landUseChart"></canvas></div>
        </div>
        <div class="card">
          <h3>Water use</h3>
          <div class="card-sub">Litres — stacked area 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="waterUseChart"></canvas></div>
        </div>
      </div>
    </div><!-- /view-land-water -->
"""
