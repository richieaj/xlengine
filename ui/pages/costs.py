"""Costs tab — 2 inline subtabs: import/energy costs, power sector cost."""


def render():
    return """
    <div class="view" id="view-costs">
      <div class="subtabs">
        <span class="subtab active" data-subview="import-energy-costs">Annual Import &amp; Energy Costs</span>
        <span class="subtab" data-subview="power-sector-cost">Power Sector Cost</span>
      </div>

      <div class="subview active" id="subview-import-energy-costs">
        <div class="chart-grid">
          <div class="card">
            <h3>Annual Import Costs (Nominal)</h3>
            <div class="card-sub">Billion INR — 2022–2047</div>
            <div class="chart-wrap"><canvas id="importCostChart"></canvas></div>
          </div>
          <div class="card">
            <h3>Annual Production Costs (Nominal)</h3>
            <div class="card-sub">Billion INR — 2022–2047</div>
            <div class="chart-wrap"><canvas id="productionCostChart"></canvas></div>
          </div>
        </div>
      </div>

      <div class="subview" id="subview-power-sector-cost">
        <div class="chart-grid">
          <div class="card">
            <h3>Power Sector capex</h3>
            <div class="card-sub">Billion INR — five-year periods</div>
            <div class="chart-wrap"><canvas id="capexChart"></canvas></div>
          </div>
          <div class="card">
            <h3>Annual Operating Costs</h3>
            <div class="card-sub">Billion INR — 2022–2047</div>
            <div class="chart-wrap"><canvas id="opexChart"></canvas></div>
          </div>
        </div>
      </div>
    </div><!-- /view-costs -->
"""
