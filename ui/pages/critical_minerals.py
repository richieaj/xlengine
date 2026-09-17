"""Critical Minerals tab — mineral demand from the utility solar PV build-out.

Layout deliberately mirrors energy_security.py exactly: .chart-grid > two
.card blocks, each a terse one-line unit caption over a .chart-wrap-lg canvas.
Keep it that way — the two tabs are meant to be the same size on screen.

The sheet behind this models one chain: utility solar PV capacity (GW) -> a mix
across 8 PV technologies -> mineral demand (tonnes), through a hardcoded
intensity matrix in tonnes per GW.

Context that is NOT on the page, and matters when reading these numbers:

- Scope is utility solar PV only. Rooftop solar, wind, storage, grid and EVs
  are not on this sheet, so Control!E13 (Solar Photovoltaic) is the only lever
  that moves anything here — verified: every other lever leaves these figures
  bit-identical. A user dragging a wind lever will see a static tab.
- Demand scales linearly with capacity. The technology mix and material
  intensities are fixed inputs, so there is no thrifting, substitution or
  recycling in these figures.
- The 2022 column is backward-extrapolated: the technology-share source table
  starts at 2025, so 2022 runs the 2025-2030 trend in reverse and is inferred
  rather than observed.

The mineral chart is a ranked single-year bar on a log axis rather than the
stacked time series used elsewhere, because 2047 demand spans 7.8 orders of
magnitude (aluminium 2.98M t, lithium 0.046 t) and a stack would be 100%
Al+Cu+Si. A log axis cannot plot zero, and seven minerals are exactly zero in
2022 until perovskite enters after 2032 — hence one year, with those seven in
a second colour to carry the emergence story.
"""


def render():
    return """
    <div class="view" id="view-critical-minerals">
      <div class="chart-grid">
        <div class="card">
          <h3>Mineral Demand in 2047</h3>
          <div class="card-sub">Tonnes — log scale, ranked</div>
          <div class="chart-wrap-lg"><canvas id="crmMineralRankChart"></canvas></div>
        </div>
        <div class="card">
          <h3>Solar PV Capacity by Technology</h3>
          <div class="card-sub">GW — stacked area 2022–2047</div>
          <div class="chart-wrap-lg"><canvas id="crmCapacityChart"></canvas></div>
        </div>
      </div>
    </div><!-- /view-critical-minerals -->
"""
