"""Electricity tab — demand/supply as an equal-width duo, same panel layout
as All Energy's but using .chart-wrap-duo-lg (taller than All Energy's own
.chart-wrap-duo) — this tab has no KPI row above the charts, so its chart
needs to be taller to make .main-col come out to the same total height as
All Energy's, which is what keeps the change sidebar (stretched to match)
reading at the same size on both tabs. The old bar/delta charts
(electricityDemandDeltaChart / electricitySupplyDeltaChart) were removed —
the stacked-area charts already carry the "changed" highlight across every
year, not just 2047."""


def render():
    return """
    <div class="view" id="view-electricity">
      <div class="chart-duo">
        <div class="panel" id="card-elec-demand">
          <div class="panel-head">
            <h2>Electricity Demand (Including Captive)<span class="changed-note">CHANGED</span></h2>
            <span class="panel-unit">TWh</span>
          </div>
          <div class="chart-wrap-duo-lg"><canvas id="electricityDemandChart"></canvas></div>
        </div>
        <div class="panel" id="card-elec-supply">
          <div class="panel-head">
            <h2>Electricity Supply (Utility)<span class="changed-note">CHANGED</span></h2>
            <span class="panel-unit">TWh</span>
          </div>
          <div class="chart-wrap-duo-lg"><canvas id="electricitySupplyChart"></canvas></div>
        </div>
      </div>
    </div><!-- /view-electricity -->
"""
