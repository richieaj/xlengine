"""Critical Minerals tab — mineral demand from the utility solar PV build-out.

The sheet behind this models exactly one chain: utility solar PV capacity (GW)
-> a mix across 8 PV technologies -> mineral demand (tonnes), through a
hardcoded intensity matrix in tonnes per GW. Everything on this page is that
chain, and nothing else is on the sheet.

Three design decisions worth knowing before editing:

1. The mineral chart is a RANKED SINGLE-YEAR bar on a log axis, not the
   stacked time series used everywhere else in this dashboard. 2047 demand
   spans 7.8 orders of magnitude (aluminium 2.98M tonnes, lithium 0.046), so a
   stacked area would be 100% Al+Cu+Si with everything else invisible. A log
   axis handles the spread but cannot plot zero — and seven minerals are
   exactly zero in 2022, appearing only once perovskite enters after 2032.
   Hence one year. The growth story those seven represent is carried by bar
   colour instead of by a second chart.

2. The capacity chart is here to make the tab legible, not to fill the grid.
   It is the only input the tab responds to, so it is what explains an
   unchanged page when a user drags a lever this sheet does not model. (A KPI
   stat strip led with the same capacity figure and was removed; the chart
   carries that job on its own.)

3. The scope and linearity notes are deliverables, not decoration. This is
   solar PV only — no batteries, no wind, no grid copper, no EVs — and demand
   scales linearly with capacity because the mix and intensities are fixed
   inputs. Both facts are much larger than anything shown on screen, and a
   reader who misses them will over-read every number here.
"""


def render():
    return """
    <div class="view" id="view-critical-minerals">

      <p class="view-note">
        Mineral demand from <strong>utility-scale solar PV only</strong> — rooftop solar, wind,
        storage, grid infrastructure and EVs are not modelled on this sheet, so the Solar PV lever
        is the only one that moves these figures. Technology mix and material intensities are fixed
        inputs: demand scales linearly with capacity and assumes no thrifting, substitution or
        recycling.
      </p>

      <div class="chart-grid">
        <div class="card">
          <h3>Mineral Demand in 2047</h3>
          <div class="card-sub">
            Tonnes, log scale — bar length shows rank, the printed figure shows quantity.
            Violet bars are minerals with no demand in 2022, arriving with perovskite and thin-film
            technologies. Lithium appears at 0.05 t: this sheet covers solar PV, not batteries.
          </div>
          <div class="chart-wrap-lg"><canvas id="crmMineralRankChart"></canvas></div>
        </div>
        <div class="card">
          <h3>Solar PV Capacity by Technology</h3>
          <div class="card-sub">
            GW installed — the mix that drives every figure on this tab. Technology shares before
            2025 are extrapolated backwards from the 2025–2030 trend, so 2022 is inferred rather
            than observed.
          </div>
          <div class="chart-wrap-lg"><canvas id="crmCapacityChart"></canvas></div>
        </div>
      </div>

    </div><!-- /view-critical-minerals -->
"""
