"""Indicators tab — 3 inline subtabs: emissions intensity, per-capita, electricity indicators."""


def render():
    return """
    <div class="view" id="view-indicators">
      <div class="subtabs">
        <span class="subtab active" data-subview="emissions-intensity">Energy Emissions Intensity of GDP</span>
        <span class="subtab" data-subview="per-capita">Per Capita Indicators</span>
        <span class="subtab" data-subview="electricity-indicators">Electricity Indicators</span>
      </div>

      <div class="subview active" id="subview-emissions-intensity">
        <div class="chart-grid">
          <div class="card">
            <h3>Energy Emissions Intensity of GDP</h3>
            <div class="card-sub">kg CO2e / 1000 INR — 2022–2047</div>
            <div class="chart-wrap"><canvas id="indEmissionsIntensityChart"></canvas></div>
          </div>
          <div class="card">
            <h3>Energy intensity of GDP</h3>
            <div class="card-sub">MJ/INR — 2022–2047</div>
            <div class="chart-wrap"><canvas id="indEnergyIntensityChart"></canvas></div>
          </div>
        </div>
      </div>

      <div class="subview" id="subview-per-capita">
        <div class="chart-grid">
          <div class="card">
            <h3>Per Capita GHG Emissions</h3>
            <div class="card-sub">tonne CO2e/person — 2022–2047</div>
            <div class="chart-wrap"><canvas id="indPerCapitaEmissionsChart"></canvas></div>
          </div>
          <div class="card">
            <h3>Per Capita Primary Energy Supply</h3>
            <div class="card-sub">toe/person — 2022–2047</div>
            <div class="chart-wrap"><canvas id="perCapitaSupplyChart"></canvas></div>
          </div>
        </div>
      </div>

      <div class="subview" id="subview-electricity-indicators">
        <div class="chart-grid">
          <div class="card">
            <h3>Installed Capacity</h3>
            <div class="card-sub">GW — stacked area 2022–2047</div>
            <div class="chart-wrap"><canvas id="capacityChart"></canvas></div>
          </div>
          <div class="card">
            <h3>Demand Electrification</h3>
            <div class="card-sub">% of final demand met by electricity — 2022–2047</div>
            <div class="chart-wrap"><canvas id="demandElectrificationChart"></canvas></div>
          </div>
        </div>
      </div>
    </div><!-- /view-indicators -->
"""
