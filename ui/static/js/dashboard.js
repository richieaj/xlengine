const ids = window.APP_CONFIG.leverIds;
/* ── Chart series palette: the Sankey's own register ──────────────────────
   The charts used to carry a separate EU-Calc-sampled palette while the
   Energy Flows Sankey used its own five category colours — two palettes for
   one dataset. The charts now take the Sankey's, so a colour means the same
   thing wherever the reader meets it.

   The five anchors are SANKEY_NODE_COLORS verbatim (see renderSankey):

     #22D3A8 source   #4F9BF2 tech   #F2B84B carrier
     #E05263 loss     #7B6EF6 demand

   THE PROBLEM, and it is a real one: five colours cannot dress fourteen
   stacked bands, and the Sankey's register is a deliberately tight lightness
   band — vivid, all mid-luminance. Adjacent bands on a stacked chart have to
   be separable, including in greyscale and under colour-vision deficiency,
   which is a LUMINANCE property, not a hue one. Measured on the Sankey's raw
   colours: its loss red (L=0.228) and its demand violet (L=0.220) are 0.008
   apart. Fine in the diagram, where the two never touch — they sit in
   different columns — but on the Energy Demand chart Agriculture and Telecom
   would have been indistinguishable bands.

   SO THE LIGHTNESS IS SOLVED, NOT PICKED. Hue and saturation are held at the
   Sankey's values; only lightness moves, and only within ±0.08, by coordinate
   ascent over the 91 colour pairs that actually co-occur on some chart
   (checked against every chart's real series list, not a guess), maximising
   the SMALLEST luminance gap among them. Result: **0.040**, with the binding
   pair CCS vs Distributed Solar PV on the 13- and 14-series capacity/cost
   charts. Per chart: demand 0.046, supply 0.044, electricity supply 0.044,
   land use 0.044, the four-series import charts 0.143.

   Two honest notes on that number:
     - It is BELOW the 0.053 the previous EU-Calc palette reached. That is the
       price of this register, not a mistake: releasing lightness to ±0.25
       does reach 0.057, but it turns the carrier amber into a pale cream and
       the tech blue into a wash — the anchors stop being the Sankey's. ±0.08
       keeps every colour recognisably itself (amber #F2B84B→#F4C56C, loss red
       #E05263→#DD4153) and leans on hue for the rest.
     - Unconstrained optimisation reaches 0.052 but produces a brown amber
       (#8F610A) and a near-white cyan. Do not "improve" the gap by rerunning
       without the leash.

   Assignment keeps the fuel conventions an energy reader expects: coal
   darkest, oil amber, gas red, nuclear violet, hydro blue, bio/other green,
   solar yellow, wind teal. `ink` is pinned dark rather than solved, so coal
   stays the heaviest band. Coal is the one departure from the Sankey itself,
   which has no near-black — a heavy band there is both conventional and
   semantically right, and nothing in the diagram needs that slot. */
const PALETTE = {
  yellow:   "#F9E48B",  // L .775
  ltteal:   "#81E4C9",  // L .644
  amber:    "#F4C56C",  // L .602  <- Sankey carrier #F2B84B
  teal:     "#28DCB0",  // L .548  <- Sankey source  #22D3A8
  lime:     "#79CE3B",  // L .485
  cyan:     "#36C1DD",  // L .441
  blue:     "#6CABF4",  // L .388  <- Sankey tech    #4F9BF2
  slate:    "#949FAD",  // L .341
  pink:     "#EC6A90",  // L .302
  ltviolet: "#8B78F7",  // L .256
  red:      "#DD4153",  // L .198  <- Sankey loss    #E05263
  violet:   "#6252F4",  // L .152  <- Sankey demand  #7B6EF6
  dpblue:   "#275E9B",  // L .108
  ink:      "#2B3038",  // L .029  (pinned: coal stays the heaviest band)
};

// Positional fallback for any series SERIES_COLOR doesn't name. Fourteen
// entries, so the widest charts (capex/opex, 14 series) can no longer wrap and
// repeat a colour, and ordered so consecutive positions are far apart in
// luminance — an unnamed series most often lands next to another unnamed one.
const COLORS = [
  PALETTE.teal, PALETTE.red, PALETTE.blue, PALETTE.amber, PALETTE.violet,
  PALETTE.lime, PALETTE.cyan, PALETTE.yellow, PALETTE.dpblue, PALETTE.pink,
  PALETTE.ltteal, PALETTE.ltviolet, PALETTE.slate, PALETTE.ink,
];

// The same category keeps the same colour on every chart and every tab, so a
// reader who learns "teal = transport" on All Energy carries that to
// Electricity and Emissions. Names are the series labels produced by
// outputs.py's DEMAND_SECTOR_GROUPS / SUPPLY_SOURCE_GROUPS etc. Anything not
// listed falls back to COLORS by position, so a new series still gets a
// palette colour rather than an off-palette one.
//
// Two names may share a colour ONLY if they never appear on one chart — e.g.
// "Waste to Electricity" (capacity) and "Standalone PV for Hydrogen" (capex).
// The co-occurrence check above is what licenses that.
const SERIES_COLOR = {
  // ── demand sectors ────────────────────────────────────────────────────
  "Transport": PALETTE.teal,              // Sankey source teal
  "Passenger Transport": PALETTE.teal,
  "Freight Transport": PALETTE.ltteal,
  "Telecom, Cooking & Transport": PALETTE.teal,
  "Industry": PALETTE.blue,               // Sankey tech blue
  "Heavy Industry": PALETTE.blue,
  "Buildings": PALETTE.lime,
  "Residential Buildings": PALETTE.lime,
  "Commercial Buildings": PALETTE.ltteal,
  "Cooking": PALETTE.amber,               // Sankey carrier amber
  "Agriculture": PALETTE.red,             // Sankey loss red
  "Telecom": PALETTE.violet,              // Sankey demand violet
  "Miscellaneous": PALETTE.slate,
  "Non-energy use": PALETTE.ltviolet,
  // ── primary supply / fuels ────────────────────────────────────────────
  "Coal": PALETTE.ink,                    // heaviest band, by convention
  "Coking Coal": PALETTE.ink,
  "Coking coal": PALETTE.ink,             // the cost sheet's own spelling
  "Non-coking coal": PALETTE.slate,
  "Non-coking Coal": PALETTE.slate,       // import-dependence's spelling
  "Oil and petroleum products": PALETTE.amber,
  "Oil": PALETTE.amber,
  "Crude oil": PALETTE.amber,
  "Natural gas": PALETTE.red,
  "Gas": PALETTE.red,
  "Nuclear": PALETTE.violet,
  "Hydro": PALETTE.blue,
  "Large Hydro": PALETTE.blue,
  "Hydro Power Generation": PALETTE.blue,
  "Small Hydro": PALETTE.dpblue,
  "Solar": PALETTE.yellow,
  "Wind": PALETTE.teal,
  "Others": PALETTE.lime,
  "Bioenergy": PALETTE.lime,
  "Biomass": PALETTE.lime,
  "Bio Energy": PALETTE.lime,
  "Biomass Base Electricity": PALETTE.lime,
  "Electricity Import": PALETTE.cyan,
  "Electricity Imports": PALETTE.cyan,
  "Electricity trade": PALETTE.cyan,
  "Electricity": PALETTE.cyan,
  "CCS": PALETTE.slate,
  "Carbon Capture Storage (CCS)": PALETTE.slate,
  // ── generation technologies (capacity / capex / opex / land / water) ──
  "Coal Power Stations": PALETTE.ink,
  "Gas Power Stations": PALETTE.red,
  "Onshore Wind": PALETTE.teal,
  "Offshore Wind": PALETTE.ltteal,
  "Solar PV": PALETTE.yellow,
  "Solar CSP": PALETTE.amber,
  "Distributed Solar PV": PALETTE.pink,
  "Green Hydrogen": PALETTE.cyan,
  "Renewables": PALETTE.teal,
  "Domestic Fuel production": PALETTE.teal,
  // Never share a chart with each other, so they can share a colour:
  "Waste to Electricity": PALETTE.ltviolet,        // capacity only
  "Standalone PV for Hydrogen": PALETTE.ltviolet,  // capex/opex only
  "Standalone Wind for Hydrogen": PALETTE.cyan,
  // ── emissions by sector ───────────────────────────────────────────────
  "Fuel Production": PALETTE.ink,
  "Refineries": PALETTE.slate,
  // ── PV technologies (Critical Minerals tab) ───────────────────────────
  // Grouped by family so the stack reads as a story rather than a list:
  // crystalline silicon in blues, thin film warm, perovskite violet. These
  // appear on one chart only, so reuse against non-PV series above is safe.
  "Monocrystalline Silicon (mono-Si) PV": PALETTE.dpblue,
  "Polycrystalline Silicon (poly-Si) PV": PALETTE.blue,
  "Heterojunction Silicon (HJT) PV": PALETTE.cyan,
  "CIGS Thin-Film PV": PALETTE.amber,
  "Amorphous Silicon (a-Si) Thin-Film PV": PALETTE.yellow,
  "Cadmium Telluride (CdTe)": PALETTE.pink,
  "Perovskite/Silicon Tandem": PALETTE.ltviolet,
  "Perovskite APT": PALETTE.violet,
  // ── aggregate line ────────────────────────────────────────────────────
  "Total": "#1b1d29",
};

/* Relative luminance (WCAG), used to decide whether a band's in-chart label
   should be white or black. Computed rather than listed, so the palette above
   can change without silently stranding a label on a dark fill. */
function isDarkColor(hex) {
  if (typeof hex !== "string" || hex[0] !== "#" || hex.length < 7) return false;
  const chan = (i) => {
    const c = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * chan(0) + 0.7152 * chan(1) + 0.0722 * chan(2) < 0.42;
}


// The reference draws each band as a soft vertical gradient rather than a flat
// fill — denser at the top of the plot, lighter toward the bottom.
function hexToRgba(hex, alpha) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// Picks readable text color for a filled callout box, rather than assuming
// dark text always works — several series colors (Coal's slate, Transport's
// teal) are dark enough that near-black text on them reads as low-contrast
// clutter. Same perceptual-brightness formula as most WCAG-adjacent checks.
function textOnColor(hex) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness < 140 ? "#ffffff" : "#000000";
}

function areaFill(color) {
  return (context) => {
    const { chart } = context;
    const { chartArea, ctx } = chart;
    if (!chartArea) return hexToRgba(color, 0.88);
    const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, hexToRgba(color, 0.95));
    g.addColorStop(1, hexToRgba(color, 0.72));
    return g;
  };
}
if (window.Chart) {
  // Set again from TYPE further down (the authoritative one, alongside
  // Chart.defaults.font.size); this earlier assignment is kept only because
  // plugins registered above it read defaults at registration time. Both must
  // name the same family — see FONT_SANS.
  Chart.defaults.font.family = '"Roboto", "Helvetica Neue", Arial, system-ui, sans-serif';
  // Every chart canvas on every tab now sits inside a fixed-height
  // .chart-wrap container, so charts size to that container instead of
  // deriving a height from a canvas aspect ratio (which grew with column
  // width and made each tab taller than the viewport).
  Chart.defaults.maintainAspectRatio = false;
}

let baseline = null;
let charts = {};
let recalcTimer = null;

function colorFor(i) { return COLORS[i % COLORS.length]; }

// Semantic colour first, palette position as the fallback.
function colorForSeries(name, i) { return SERIES_COLOR[name] || colorFor(i); }

// Formats a raw number as a compact "804k" / "1.09M" style string, for
// charts whose underlying values are large raw counts (e.g. Land Use in
// hectares, Water Use in litres) rather than an already-small unit like
// Mtoe/TWh. Falls back to a plain fixed-2 string for values too small to
// need a suffix, so small numbers (e.g. a chart's early years) don't render
// as "0" or an empty string.
function formatCompact(value) {
  if (value == null || isNaN(value)) return "0";
  if (Math.abs(value) < 1000) return value.toFixed(value % 1 === 0 ? 0 : 2);
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function setStatus(text, cls) {
  const chip = document.getElementById("status-chip");
  chip.textContent = text;
  chip.className = cls || "";
}

/* No per-series "changed" styling here any more. A series whose values moved
   since the baseline used to be redrawn with a 3px amber dashed stroke
   (`borderColor: "#a0761f", borderWidth: 3, borderDash: [4, 2]`), which meant
   that moving any lever scribbled a dotted line across the band it affected —
   over the data, on the chart you were trying to read, and on every recalc.
   The card-level "CHANGED SINCE BASELINE" badge (.changed-note, driven by
   opts.changedCardId in renderStackedChart) already says which chart moved
   without drawing on top of it, so the information isn't lost.

   `changedSeries` is consequently no longer a parameter of this function —
   renderStackedChart still receives it for that badge. */
function stackedAreaDatasets(chartData) {
  const names = Object.keys(chartData.series);
  const datasets = names.map((name, i) => {
    const color = colorForSeries(name, i);
    return {
      label: name, data: chartData.series[name], fill: true,
      backgroundColor: areaFill(color), borderColor: color,
      borderWidth: 0.5,
      // Carried for the legend swatch, the tooltip and the in-band label, all
      // of which need the flat colour rather than the gradient function.
      bandColor: color,
      // The legend key is the same small colour box the tooltip draws beside
      // this series' value. Rendered into a canvas rather than left to
      // Chart.js's own legend box because `backgroundColor` here is the area
      // gradient function — the key has to be the flat series colour.
      pointStyle: swatchCanvas(color, 11),
      stack: "s", tension: 0, pointRadius: 0, order: 1,
    };
  });
  // "Total" overlay line — matches the reference charts' black line-with-dots
  // on top of the stacked area, drawn from the chart data's own total series
  // rather than summed client-side, so it always matches the workbook's own
  // authoritative total row.
  if (chartData.total) {
    datasets.push({
      label: "Total", data: chartData.total, fill: false, stack: undefined,
      borderColor: "#1b1d29", backgroundColor: "#1b1d29", borderWidth: 2,
      // "line" in the legend, so the aggregate reads as a line and the bands
      // read as dots — the reference's own distinction.
      pointStyle: "line",
      tension: 0, pointRadius: 3, pointBackgroundColor: "#1b1d29", order: 0,
    });
  }
  return { names, datasets };
}

// Shared hover/tooltip behavior for every chart: hovering anywhere on the
// x-axis shows every series' value at that point in one combined tooltip
// (Chart.js "index" mode), rather than requiring the cursor to land exactly
// on one line/segment.
const INDEX_INTERACTION = { mode: "index", intersect: false };

const AXIS_TEXT = "#000000";

/* ---------- Type, for everything drawn rather than laid out ----------
   Canvas and SVG do not inherit the stylesheet's font stack, so the family
   and the scale steps have to be restated here — these are the same steps as
   dashboard.css's --t-* tokens.

   Two canvas-specific notes:
   - Canvas 2D cannot request tabular figures at all (no font-feature-settings
     on a 2D context). It does not need to: Roboto's digits are equal-advance,
     measured at 1151/2048 units for every digit and asserted by
     tools/build_fonts.py, so axis ticks and tooltip values cannot jitter as
     values change. Any future display face must be checked the same way
     before it is used for canvas numerics — the previous one, Instrument
     Serif, had proportional digits (249-460 units) and was kept out of the
     charts for precisely that reason.
   - Sizes here are pre-zoom logical px, the same space the CSS is authored
     in, so they match the scale without dividing by --ui-scale. */
// One family for everything, mirroring --font-roboto in dashboard.css. Canvas
// and SVG do not inherit the stylesheet, so the stack has to be restated here;
// keep the two in step. FONT_MONO is retained as a name because the numeric
// readouts still declare themselves as such, but it resolves to the same
// family — safe because Roboto's digits are equal-advance (asserted by
// tools/build_fonts.py), which is the only property a canvas number needs.
const FONT_SANS = '"Roboto", "Helvetica Neue", Arial, system-ui, sans-serif';
const FONT_MONO = FONT_SANS;
const TYPE = {
  axis:  { family: FONT_SANS, size: 11, weight: 400 },   // --t-axis
  label: { family: FONT_SANS, size: 13, weight: 400 },   // --t-label
  body:  { family: FONT_SANS, size: 14, weight: 400 },   // --t-body
};
// Chart.js reads its default family/size from here, so any option that does
// not spell out a font still lands inside the scale instead of on Chart.js's
// own Helvetica 12.
if (window.Chart) {
  Chart.defaults.font.family = FONT_SANS;
  Chart.defaults.font.size = TYPE.axis.size;
}
// Shared axis look for every chart: hairline horizontal rules, no vertical
// grid and no axis line, matching the reference chart. yAxis()/xAxis() are
// used by the bar and single-line renderers; renderStackedChart spells the
// same thing out inline because it also sets stacking and min.
function axisCommon(titleText) {
  return {
    title: { display: true, text: titleText, color: AXIS_TEXT, font: TYPE.axis },
    ticks: { color: AXIS_TEXT, font: TYPE.axis },
    border: { display: false },
  };
}
function yAxis(titleText, extra) {
  return Object.assign(axisCommon(titleText), { grid: { color: "#EDEDE8", drawTicks: false } }, extra || {});
}
function xAxis(titleText, extra) {
  return Object.assign(axisCommon(titleText), { grid: { display: false } }, extra || {});
}

// Writes each series' name inside its own band, the way the reference chart
// does — so the stack can be read without hopping down to the legend. The
// label goes at the band's thickest point, and is skipped entirely where the
// band is too thin to hold text, which is why the legend still has to exist.
// Text colour flips to white on the dark fills (coal, charcoal) so it stays
// legible on both.
const bandLabelPlugin = {
  id: "bandLabels",
  afterDatasetsDraw(chart) {
    if (!chart.options.plugins.bandLabels || !chart.options.plugins.bandLabels.display) return;
    const { ctx } = chart;
    ctx.save();
    ctx.font = '600 11px "Roboto", "Helvetica Neue", Arial, system-ui, sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Each series picks its own "thickest point" independently, with no idea
    // where any other series' label landed — usually fine since bands are
    // wide apart, but at some lever combinations two thin, adjacent bands
    // (e.g. Hydro sitting right against Coal) can each compute a label
    // position that lands almost exactly on top of the other, garbling both.
    // Placed labels are tracked here so a later one skips it if it overlaps
    // an earlier one, rather than drawing two texts on the same pixels.
    const placed = [];
    const overlaps = (a, b) => a.l < b.r && a.r > b.l && a.t < b.b && a.b > b.t;

    chart.data.datasets.forEach((ds, di) => {
      if (ds.label === "Total" || ds.fill === false) return;
      const meta = chart.getDatasetMeta(di);
      if (meta.hidden) return;
      const pts = meta.data;
      if (!pts || !pts.length) return;

      // Thickest point of this band = biggest gap between its own top edge
      // and the top edge of whatever it is stacked on. Only the middle of the
      // series is considered: every series here grows toward 2047, so a plain
      // global maximum put every label on the last point, stacked against the
      // right edge and fighting the legend. The reference sits its labels in
      // the body of the chart, which is what this window reproduces.
      const lo = Math.floor(pts.length * 0.18);
      const hi = Math.max(lo + 1, Math.ceil(pts.length * 0.72));
      let best = -1, bestGap = 0;
      for (let i = lo; i < Math.min(hi, pts.length); i++) {
        const below = di > 0 ? chart.getDatasetMeta(di - 1).data[i] : null;
        const floor = below ? below.y : chart.chartArea.bottom;
        const gap = floor - pts[i].y;
        if (gap > bestGap) { bestGap = gap; best = i; }
      }
      if (best < 0 || bestGap < 20) return;

      const below = di > 0 ? chart.getDatasetMeta(di - 1).data[best] : null;
      const floor = below ? below.y : chart.chartArea.bottom;
      const y = pts[best].y + (floor - pts[best].y) / 2;
      let x = pts[best].x;

      // Keep the text inside the plot area rather than clipped at an edge.
      const half = ctx.measureText(ds.label).width / 2;
      x = Math.min(Math.max(x, chart.chartArea.left + half + 4), chart.chartArea.right - half - 4);
      if (half * 2 > chart.chartArea.right - chart.chartArea.left - 8) return;

      const rect = { l: x - half - 3, r: x + half + 3, t: y - 8, b: y + 8 };
      if (placed.some((p) => overlaps(p, rect))) return;
      placed.push(rect);

      // Computed from the band's own colour, not matched against a list. This
      // used to be `["#6E7681", "#3E9C93", "#57B3A9"].includes(...)` — three
      // hard-coded hexes that got white text while everything else got black.
      // That silently rots the moment the palette changes: a new dark band not
      // on the list gets black text on a near-black fill, and the label just
      // disappears. isDarkColor() measures instead, so any palette works.
      ctx.fillStyle = isDarkColor(ds.bandColor) ? "rgba(255,255,255,.95)" : "#000000";
      ctx.fillText(ds.label, x, y);
    });
    ctx.restore();
  },
};
if (window.Chart) Chart.register(bandLabelPlugin);

/* ---------- Series key: one small colour box ----------------------------
   A series is identified by its colour and nothing else. There used to be a
   second channel here — a (shape x solid/hollow) marker per series, ten
   combinations resolved per chart so no two bands on one plot shared a glyph.
   It was removed on request: five shapes in two fills is a second legend the
   reader has to learn, and the bands themselves are already read by colour,
   so the glyph only mattered inside the tooltip it appeared in.

   The colour box is drawn by ONE function used in both places it appears —
   the legend key and the tooltip — so the key beside a value is literally the
   same mark as the key in the legend. Colour separation across the widest
   charts is the palette's own job (see the SERIES_COLOR note above: the
   shipped palette holds a 0.053 minimum luminance gap between any two series
   that share a plot).

   `size` is the box's full width in px, not a radius. */
function drawSwatch(ctx, x, y, color, size) {
  const s = (size || 10) / 2;
  ctx.save();
  roundRect(ctx, x - s, y - s, s * 2, s * 2, 2);   // begins its own path
  ctx.fillStyle = color;
  ctx.fill();
  ctx.restore();
}

/* The legend key is that same box, rendered once into a small canvas and
   handed to Chart.js as `pointStyle`.

   Not left to Chart.js's own legend box, because these datasets carry the area
   GRADIENT as `backgroundColor` — the built-in box would paint the legend key
   with a gradient sampled at legend coordinates, which is why an image-backed
   pointStyle is used even now that the mark is a plain square.
   Drawn at 2x and scaled down via width/height so it stays crisp under both
   devicePixelRatio and the page's own `zoom`. */
const SWATCH_CANVAS_CACHE = new Map();
function swatchCanvas(color, size) {
  const px = size || 11;
  const key = color + "|" + px;
  const hit = SWATCH_CANVAS_CACHE.get(key);
  if (hit) return hit;
  const scale = 2;
  const pad = 2;
  const cv = document.createElement("canvas");
  cv.width = (px + pad * 2) * scale;
  cv.height = (px + pad * 2) * scale;
  const c = cv.getContext("2d");
  c.scale(scale, scale);
  drawSwatch(c, px / 2 + pad, px / 2 + pad, color, px);
  // Chart.js draws an image pointStyle at the image's own pixel size, so the
  // backing store is halved back to CSS px here.
  cv.style.width = px + pad * 2 + "px";
  cv.style.height = px + pad * 2 + "px";
  SWATCH_CANVAS_CACHE.set(key, cv);
  return cv;
}

/* Value text for a tooltip box.

   The rules are the reference's, and each one is a real case in this data:
     - two decimals, so 0.4 and 0.42 do not both read as "0.4";
     - thousands separators from four digits up (Energy Supply's total passes
       1,000 Mtoe);
     - a TRUE minus (U+2212), not a hyphen, for negatives — the emissions
       chart has negative sinks, and a hyphen at this size reads as a dash
       between the name and the number;
     - exact zero as "0", not "0.00", because a band that is simply absent in
       a given year should not look like a rounded-away quantity.
   The unit is appended to the VALUE, never to the series name, so the name
   column stays scannable. */
function formatSeriesValue(v, unit) {
  const suffix = unit ? " " + unit : "";
  if (v == null || isNaN(v)) return "–";
  if (v === 0) return "0" + suffix;
  const neg = v < 0;
  const fixed = Math.abs(v).toFixed(2);
  const dot = fixed.indexOf(".");
  const intPart = fixed.slice(0, dot);
  const decPart = fixed.slice(dot);
  const grouped = intPart.length >= 4 ? Number(intPart).toLocaleString("en-US") : intPart;
  return (neg ? "−" : "") + grouped + decPart + suffix;
}

/* Vertical placement for the tooltip cluster: keep the reading order, keep a
   gap, and move boxes as little as possible.

   This is Highcharts' distribute() problem. The naive fix — walk down the list
   pushing each box below its predecessor — is what this replaced, and it drags
   the whole cluster downward from the first collision onward, so a chart where
   the top two bands are close ends up with every box displaced and every
   connector line slanted.
   The cluster-averaging pass below is the standard solution: boxes that
   collide are merged into a group and the group is centred on the MEAN of its
   members' targets, which is the placement minimising total squared
   displacement subject to order and spacing. Groups then merge transitively,
   and only the final group positions are clamped into the plot. */
function distributeBoxes(items, top, bottom, boxH, gap) {
  if (!items.length) return;
  const pitch = boxH + gap;
  const groups = [];
  items.forEach((it) => {
    groups.push({ items: [it], sum: it.target, n: 1 });
    while (groups.length > 1) {
      const b = groups[groups.length - 1];
      const a = groups[groups.length - 2];
      const aFirst = a.sum / a.n - ((a.n - 1) * pitch) / 2;
      const bFirst = b.sum / b.n - ((b.n - 1) * pitch) / 2;
      if (bFirst >= aFirst + a.n * pitch) break;   // no overlap: leave both
      a.items = a.items.concat(b.items);
      a.sum += b.sum;
      a.n += b.n;
      groups.pop();
    }
  });
  groups.forEach((g) => {
    let first = g.sum / g.n - ((g.n - 1) * pitch) / 2;
    const min = top + boxH / 2;
    const max = bottom - boxH / 2 - (g.n - 1) * pitch;
    first = Math.min(Math.max(first, min), Math.max(min, max));
    g.items.forEach((it, i) => { it.y = first + i * pitch; });
  });
}

// Chart.js's own tooltip is disabled (tooltip.enabled:false in
// renderStackedChart); `external` is the documented hook for a fully custom
// tooltip and is used here only to capture the live hover state, never to
// draw. The drawing happens in the plugin's afterDraw, on the same canvas as
// the chart, which is what lets the symbols and connectors sit in the plot's
// own coordinate space.
function crosshairExternal(context) {
  context.chart._crosshair = context.tooltip;
}

const crosshairTooltipPlugin = {
  id: "crosshairTooltip",
  afterDraw(chart) {
    const opts = chart.options.plugins.crosshairTooltip;
    if (!opts || !opts.display) return;
    const tt = chart._crosshair;
    if (!tt || !tt.opacity || !tt.dataPoints || !tt.dataPoints.length) return;
    const { ctx, chartArea } = chart;
    const x = tt.dataPoints[0].element.x;
    const dataIndex = tt.dataPoints[0].dataIndex;
    const unit = opts.unit || "";

    ctx.save();

    /* ── The hovered column, lightened ──────────────────────────────────
       A band, not a hairline, and deliberately NOT a dim of everything
       else: the reader is comparing this column against its neighbours, so
       the neighbours have to stay fully readable. (The Sankey on the Energy
       Flows tab does dim its surroundings — that is a different question,
       "what connects to this node", and the two interactions are meant to
       stay distinguishable.)
       Column width comes from the spacing between adjacent categories, so it
       lines up with the band boundaries at any chart width. */
    const meta0 = chart.getDatasetMeta(0);
    const pts = (meta0 && meta0.data) || [];
    let colW = (chartArea.right - chartArea.left) / Math.max(1, (chart.data.labels || []).length);
    if (pts.length > 1) {
      const step = Math.abs(pts[1].x - pts[0].x);
      if (step > 0) colW = step;
    }
    ctx.fillStyle = "rgba(255,255,255,.30)";
    ctx.fillRect(x - colW / 2, chartArea.top, colW, chartArea.bottom - chartArea.top);
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.fillRect(x - 1, chartArea.top, 2, chartArea.bottom - chartArea.top);

    /* ── One box per series ─────────────────────────────────────────────── */
    const entries = tt.dataPoints
      .filter((dp) => dp.parsed && dp.parsed.y != null)
      .map((dp) => {
        return {
          text: dp.dataset.label + ": " + formatSeriesValue(dp.parsed.y, unit),
          color: dp.dataset.bandColor || dp.dataset.borderColor,
          // The aggregate line keeps its coloured border but gets no colour
          // box — it is not one of the stacked bands and has no band to key.
          isTotal: dp.dataset.label === "Total",
          trueY: dp.element.y,   // the real data position; never modified
          target: dp.element.y,  // what distributeBoxes() tries to honour
          y: dp.element.y,       // where the box actually lands
        };
      })
      // Top-to-bottom in VISUAL stack order at this x, which is what the
      // reader sees, rather than dataset declaration order.
      .sort((a, b) => a.trueY - b.trueY);
    if (!entries.length) { ctx.restore(); return; }

    const padX = 6, padY = 6, radius = 4, distance = 16, keyGutter = 15, gap = 4;
    ctx.font = "400 " + TYPE.label.size + "px " + TYPE.label.family;
    entries.forEach((e) => { e.boxW = Math.ceil(ctx.measureText(e.text).width) + padX * 2; });

    /* The category callout is drawn just above the axis with its tail
       touching it, so the cluster's own floor stops short of that zone. */
    const tagH = TYPE.label.size + padY * 2 - 2;
    const tailH = 5;
    let boxH = TYPE.label.size + padY * 2;
    const usableTop = chartArea.top + 1;
    const usableBottom = chartArea.bottom - tagH - tailH - gap;

    // If N boxes cannot fit the plot even packed solid (Energy Supply's ten
    // in a short chart), shrink the box height rather than let the cluster
    // overflow the plot or overlap itself.
    const needed = (entries.length - 1) * (boxH + gap) + boxH;
    const avail = usableBottom - usableTop;
    if (entries.length > 1 && needed > avail && avail > 0) {
      boxH = Math.max(13, boxH * (avail / needed));
    }
    distributeBoxes(entries, usableTop, usableBottom, boxH, gap);

    /* Side selection. The cluster sits to the LEFT of the crosshair by
       default and flips as one unit, never per box, so the reading order
       survives. The flip is driven by whether the widest box in the cluster
       actually fits on the left — measured, not assumed from a percentage,
       because the boxes carry series names of very different lengths ("Oil
       and petroleum products: 1,234.56 Mtoe" is more than twice "Wind: 0").
       The ~35% mark the reference uses falls out of this on our charts and
       is used as the tie-break when both sides fit. */
    const widest = entries.reduce((m, e) => Math.max(m, e.boxW), 0);
    const keySpace = keyGutter;
    const fitsLeft = x - distance - widest - keySpace >= chartArea.left;
    const inRightZone = x > chartArea.left + (chartArea.right - chartArea.left) * 0.65;
    const openRight = !fitsLeft || (!inRightZone && x < chartArea.left + (chartArea.right - chartArea.left) * 0.35);

    entries.forEach((e) => {
      e.boxX = openRight
        ? Math.min(x + distance + keySpace, chartArea.right - e.boxW)
        : Math.max(x - distance - e.boxW, chartArea.left + keySpace);
      // Colour box immediately outside the value box on its left, vertically
      // centred on the BOX (not on the data point) — it keys the box.
      e.keyX = e.boxX - keyGutter / 2 - 1;
    });

    /* Connectors first, so a box painted afterwards covers the line's own end
       rather than the line crossing over a neighbouring box. Only drawn where
       the box was actually displaced — an undisplaced box is already beside
       its point and a connector would just be noise. */
    entries.forEach((e) => {
      if (Math.abs(e.y - e.trueY) < 1.5) return;
      ctx.beginPath();
      ctx.strokeStyle = e.color;
      ctx.lineWidth = 1;
      ctx.moveTo(x, e.trueY);
      ctx.lineTo(openRight ? e.boxX - keyGutter : e.boxX + e.boxW, e.y);
      ctx.stroke();
    });

    entries.forEach((e) => {
      const boxY = e.y - boxH / 2;
      // Near-white at 95%, so the faint chart detail behind still shows
      // through while the text stays fully legible. Colour lives in the
      // border and the colour box — never in the text, which is one dark
      // neutral for every series so the values can be compared as a column.
      roundRect(ctx, e.boxX, boxY, e.boxW, boxH, radius);
      ctx.fillStyle = "rgba(255,255,255,0.95)";
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = e.color;
      ctx.stroke();

      if (!e.isTotal) drawSwatch(ctx, e.keyX, e.y, e.color, 10);

      ctx.fillStyle = "#2b2b2b";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(e.text, e.boxX + padX, boxY + boxH / 2 + 0.5);
    });

    /* ── Category callout ───────────────────────────────────────────────
       A separate box for the x value, darker-bordered and bold so it reads
       as the axis rather than as another series, with a tail pointing down
       to the axis line it belongs to. Clamped inside the plot width. */
    const year = String(chart.data.labels[dataIndex]);
    ctx.font = "600 " + TYPE.label.size + "px " + TYPE.label.family;
    const tagW = Math.ceil(ctx.measureText(year).width) + padX * 3;
    const tagX = Math.min(Math.max(x - tagW / 2, chartArea.left), chartArea.right - tagW);
    const tagY = chartArea.bottom - tagH - tailH;
    roundRect(ctx, tagX, tagY, tagW, tagH, radius);
    ctx.fillStyle = "rgba(255,255,255,0.95)";
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#333333";
    ctx.stroke();
    // The tail: a small triangle hanging off the box's bottom edge, its point
    // on the axis line. Filled and stroked to match the box, with the shared
    // edge painted over so the two read as one shape.
    const tailX = Math.min(Math.max(x, tagX + radius + 5), tagX + tagW - radius - 5);
    ctx.beginPath();
    ctx.moveTo(tailX - 5, tagY + tagH);
    ctx.lineTo(tailX, tagY + tagH + tailH);
    ctx.lineTo(tailX + 5, tagY + tagH);
    ctx.closePath();
    ctx.fillStyle = "rgba(255,255,255,0.95)";
    ctx.fill();
    ctx.strokeStyle = "#333333";
    ctx.stroke();
    ctx.beginPath();
    ctx.strokeStyle = "rgba(255,255,255,0.95)";
    ctx.lineWidth = 1.6;
    ctx.moveTo(tailX - 4.4, tagY + tagH);
    ctx.lineTo(tailX + 4.4, tagY + tagH);
    ctx.stroke();

    ctx.fillStyle = "#2b2b2b";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "600 " + TYPE.label.size + "px " + TYPE.label.family;
    ctx.fillText(year, tagX + tagW / 2, tagY + tagH / 2 + 0.5);

    // Exposed for tests: the plugin's own computed layout, rather than
    // reaching into canvas pixels to verify hover behaviour.
    chart._crosshairLayout = {
      x: x, dataIndex: dataIndex, openRight: openRight, boxH: boxH,
      boxes: entries.map((e) => ({
        text: e.text, color: e.color,
        y: e.y, trueY: e.trueY, boxX: e.boxX, boxW: e.boxW, keyX: e.keyX,
        displaced: Math.abs(e.y - e.trueY) >= 1.5, isTotal: e.isTotal,
      })),
      tag: { x: tagX, y: tagY, w: tagW, h: tagH, text: year },
    };
    ctx.restore();
  },
};
if (window.Chart) Chart.register(crosshairTooltipPlugin);

function renderStackedChart(canvasId, chartData, changedSeries, opts) {
  opts = opts || {};
  const unit = opts.unit || "Mtoe";
  const { datasets } = stackedAreaDatasets(chartData);
  const ctx = document.getElementById(canvasId);
  if (!charts[canvasId]) {
    const yTicks = opts.compact ? { callback: (v) => formatCompact(v) } : {};
    // Legend defaults stay bottom-aligned so the other eight tabs render
    // exactly as before; the All Energy pair opts into a vertical legend on
    // the right. `totalFirst` reorders only the legend, not the datasets —
    // "Total" has to stay last in draw order so its line paints on top of
    // the stack, but it reads first as the headline series.
    // Each key is a small colour box (swatchCanvas, via the dataset's own
    // pointStyle) — the same mark the tooltip draws beside that series' value.
    // The Total dataset overrides pointStyle to "line", since it is drawn as a
    // line over the stack rather than as a band.
    const legend = {
      position: opts.legendPosition || "bottom",
      labels: {
        boxWidth: 15, boxHeight: 15, usePointStyle: true,
        font: TYPE.label, color: "#000000", padding: 12,
      },
    };
    if (opts.totalFirst) {
      legend.labels.sort = (a, b) =>
        (a.text === "Total" ? -1 : 0) - (b.text === "Total" ? -1 : 0);
    }
    charts[canvasId] = newSizedChart(canvasId, ctx, {
      type: "line",
      data: { labels: chartData.years, datasets },
      options: {
        // responsive:false is deliberate — see resizeChartsToContainers.
        responsive: false,
        maintainAspectRatio: opts.maintainAspectRatio !== undefined ? opts.maintainAspectRatio : false,
        interaction: INDEX_INTERACTION,
        plugins: {
          legend: legend,
          // The built-in tooltip box is off — crosshairTooltipPlugin below
          // draws the whole hover interaction itself (crosshair + one callout
          // per series). `external` is the documented hook for fully custom
          // tooltips: it only hands us the live hover state, nothing paints
          // here.
          tooltip: { ...INDEX_INTERACTION, enabled: false, external: crosshairExternal },
          crosshairTooltip: { display: true, compact: !!opts.compact, unit: unit },
          // Names written inside the bands, as the reference does. Off for
          // charts too small to hold them (the delta-style compact ones).
          bandLabels: { display: opts.bandLabels !== false },
        },
        // min:0 keeps the axis clean even though a series (e.g. Electricity
        // trade, net imports) can dip slightly negative — Chart.js's "nice
        // number" tick rounding would otherwise pad a whole extra -500/-1000
        // gridline band for a dip of only a few units out of a multi-thousand
        // scale. The tiny negative sliver still renders below the y=0 line,
        // it just no longer drags the visible axis range down with it.
        scales: {
          y: {
            stacked: true, min: 0,
            title: { display: true, text: unit, color: "#000000", font: TYPE.axis },
            ticks: { ...yTicks, color: "#000000", font: TYPE.axis },
            // Hairline horizontal rules only — the reference has no axis line
            // and no vertical grid, so the bands carry the shape.
            grid: { color: "#EDEDE8", drawTicks: false, drawBorder: false },
            border: { display: false },
          },
          x: {
            title: { display: true, text: "Year", color: "#000000", font: TYPE.axis },
            ticks: { color: "#000000", font: TYPE.axis },
            grid: { display: false },
            border: { display: false },
          },
        },
      },
    });
  } else {
    // A lever change reassigns brand-new dataset objects and animates the
    // stack to its new shape. The crosshair plugin's cached hover state
    // (chart._crosshair) points at the *old* elements/positions and won't
    // get a fresh one until the next real mousemove — so if the cursor sat
    // still through a recalculation, it would otherwise keep drawing last
    // hover's boxes, frozen, on top of the newly-animating bands. Clearing
    // it here just hides the tooltip cluster for that one update instead.
    charts[canvasId]._crosshair = null;
    charts[canvasId].data.labels = chartData.years;
    charts[canvasId].data.datasets = datasets;
    charts[canvasId].update();
  }
  if (opts.changedCardId) {
    const anyChanged = changedSeries && Object.values(changedSeries).some(arr => arr.some(Boolean));
    document.getElementById(opts.changedCardId).classList.toggle("changed", !!anyChanged);
  }
}

// Stacked bar variant of renderStackedChart — used where the x-axis is
// genuinely discrete buckets (e.g. Power Sector capex's five-year periods)
// rather than a continuous year series, so a stacked area would misleadingly
// imply interpolation between buckets. No "changed"/delta support (not
// needed by anything using this yet); add if a future chart needs it.
function renderStackedBarChart(canvasId, chartData, opts) {
  opts = opts || {};
  const unit = opts.unit || "";
  const names = Object.keys(chartData.series);
  const datasets = names.map((name, i) => {
    const color = colorForSeries(name, i);
    return {
      label: name, data: chartData.series[name], backgroundColor: color,
      // Same colour-box key as the stacked-area charts, so the legend reads
      // identically across chart types.
      pointStyle: swatchCanvas(color, 11),
      stack: "s", borderRadius: 2,
    };
  });
  if (chartData.total) {
    datasets.push({
      label: "Total", data: chartData.total, type: "line", fill: false,
      borderColor: "#1b1d29", backgroundColor: "#1b1d29", borderWidth: 2,
      tension: 0, pointRadius: 3, pointBackgroundColor: "#1b1d29", order: 0,
    });
  }
  const ctx = document.getElementById(canvasId);
  const data = { labels: chartData.years, datasets };
  if (!charts[canvasId]) {
    charts[canvasId] = newSizedChart(canvasId, ctx, {
      type: "bar",
      data,
      options: {
        // responsive:false is deliberate — see resizeChartsToContainers.
        responsive: false,
        interaction: INDEX_INTERACTION,
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 15, boxHeight: 15, usePointStyle: true, font: TYPE.label },
          },
          tooltip: INDEX_INTERACTION,
        },
        scales: { y: yAxis(unit, { stacked: true, min: 0 }), x: xAxis("Period", { stacked: true }) },
      },
    });
  } else {
    charts[canvasId].data = data;
    charts[canvasId].update();
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Draws a "Name | value" callout box at the last point of each line, in the
// series' own color — mirrors the reference IESS website's endpoint-label
// style for the Import Dependence chart.
const endpointLabelPlugin = {
  id: "endpointLabels",
  afterDatasetsDraw(chart) {
    // Opt-in only (Import Dependence chart sets plugins.endpointLabels:true).
    // Chart.js auto-populates an empty {} for every REGISTERED plugin's
    // options on every chart (so a plugin can always safely read its own
    // config), so `!chart.options.plugins.endpointLabels` is falsy even when
    // unset — an explicit `=== true` check is required, not a truthiness one.
    if (chart.options.plugins.endpointLabels !== true) return;
    const { ctx } = chart;
    chart.data.datasets.forEach((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      if (!meta.data.length) return;
      const point = meta.data[meta.data.length - 1];
      const value = ds.data[ds.data.length - 1];
      if (value == null) return;
      const label = `${ds.label} | ${value.toFixed(2)}`;
      ctx.save();
      // Roboto, like everything else. Safe for a numeric callout because its
      // digits are equal-advance — see FONT_MONO.
      ctx.font = '600 10px "Roboto", "Helvetica Neue", Arial, system-ui, sans-serif';
      const padX = 6, boxH = 16;
      const boxW = ctx.measureText(label).width + padX * 2;
      const x = point.x + 8, y = point.y - boxH / 2;
      ctx.fillStyle = ds.borderColor;
      roundRect(ctx, x, y, boxW, boxH, 4);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.textBaseline = "middle";
      ctx.fillText(label, x + padX, y + boxH / 2 + 0.5);
      ctx.restore();
    });
  },
};
if (window.Chart) Chart.register(endpointLabelPlugin);

function renderImportDependenceChart(canvasId, chartData) {
  const names = Object.keys(chartData.series);
  const datasets = names.map((name, i) => ({
    label: name, data: chartData.series[name], fill: false,
    borderColor: colorForSeries(name, i), backgroundColor: colorForSeries(name, i),
    borderWidth: 2, tension: 0, pointRadius: 0,
  }));
  const ctx = document.getElementById(canvasId);
  const data = { labels: chartData.years, datasets };
  if (!charts[canvasId]) {
    charts[canvasId] = newSizedChart(canvasId, ctx, {
      type: "line",
      data,
      options: {
        // responsive:false is deliberate — see resizeChartsToContainers.
        responsive: false,
        interaction: INDEX_INTERACTION,
        layout: { padding: { right: 90 } },
        plugins: { legend: { display: false }, tooltip: INDEX_INTERACTION, endpointLabels: true },
        scales: { y: yAxis("%"), x: xAxis("Year") },
      },
    });
  } else {
    charts[canvasId].data = data;
    charts[canvasId].update();
  }
}

function renderBarChart(canvasId, chartData, opts) {
  opts = opts || {};
  const color = opts.color || COLORS[0];
  const ctx = document.getElementById(canvasId);
  const values = chartData.series ? chartData.series[Object.keys(chartData.series)[0]] : chartData.values;
  const data = {
    labels: chartData.years,
    datasets: [{ label: opts.unit || "", data: values, backgroundColor: color, borderRadius: 3 }],
  };
  if (!charts[canvasId]) {
    charts[canvasId] = newSizedChart(canvasId, ctx, {
      type: "bar",
      data,
      options: {
        // responsive:false is deliberate — see resizeChartsToContainers.
        responsive: false,
        interaction: INDEX_INTERACTION,
        plugins: { legend: { display: false }, tooltip: INDEX_INTERACTION },
        scales: { y: yAxis(opts.unit || "", { min: 0 }), x: xAxis("Year") },
      },
    });
  } else {
    charts[canvasId].data = data;
    charts[canvasId].update();
  }
}

// Ranked horizontal bars on a LOG axis. renderBarChart above can't be reused:
// it takes chartData.years as labels, titles the x-axis "Year", and pins a
// linear y to min 0.
//
// Log is not a stylistic choice here. 2047 mineral demand runs from 2.98M
// tonnes (aluminium) to 0.046 t (lithium) — 7.8 orders of magnitude. On a
// linear axis every mineral below copper is a zero-width bar. The cost is that
// bar LENGTH is no longer proportional to quantity, so the value is printed at
// the end of every bar: the number is the quantity, the bar is only the rank.
//
// Two colours encode `emergent` — minerals with no demand at all in 2022, which
// appear only once perovskite and thin-film technologies enter the mix. That
// carries the growth story a single-year snapshot would otherwise lose.
function renderRankedBarChart(canvasId, chartData, opts) {
  opts = opts || {};
  const unit = opts.unit || "";
  const base = opts.color || PALETTE.blue;
  const emergentColor = opts.emergentColor || PALETTE.violet;
  const emergent = chartData.emergent || [];
  const ctx = document.getElementById(canvasId);
  const data = {
    labels: chartData.labels,
    datasets: [{
      label: unit,
      data: chartData.values,
      backgroundColor: chartData.values.map((_, i) => (emergent[i] ? emergentColor : base)),
      borderRadius: 3,
      // Chart.js clamps a log bar's base to the lowest positive value; without
      // a floor a mineral at 0 would silently vanish rather than read as zero.
      minBarLength: 2,
    }],
  };
  const config = {
    type: "bar",
    data,
    options: {
      // responsive:false is deliberate — see resizeChartsToContainers.
      responsive: false,
      indexAxis: "y",
      layout: { padding: { right: 72 } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            // The emergent cohort is sourced entirely from the two perovskite
            // rows of the intensity matrix, whose figures are ~65-2200x lower
            // per GW than the six established technologies (aluminium: 0.9 and
            // 0 t/GW against a flat 7,200 everywhere else). Until those inputs
            // are re-derived on the same basis, these values carry a caveat
            // rather than a bare number.
            label: (c) => formatSeriesValue(c.parsed.x, unit) +
              (emergent[c.dataIndex] ? "  (none in 2022; provisional input)" : ""),
          },
        },
        rankedValueLabels: true,
      },
      scales: {
        x: xAxis(unit ? `Demand (${unit}, log scale)` : "log scale", {
          type: "logarithmic",
          grid: { display: true, color: "#EDEDE8", drawTicks: false },
          ticks: {
            color: AXIS_TEXT,
            font: TYPE.axis,
            autoSkip: false,
            // Decades only. Chart.js's log scale otherwise emits every
            // "nice" value it can fit (0.01, 0.03, 0.06, 0.08, 0.1, 0.2 ...),
            // which across eight orders of magnitude collides into an
            // unreadable smear. Powers of ten are also the only gridlines a
            // reader can actually use on a log axis.
            callback: (v) => {
              const l = Math.log10(v);
              return Math.abs(l - Math.round(l)) < 1e-9 ? formatCompact(v) : "";
            },
          },
        }),
        y: yAxis("", { grid: { display: false } }),
      },
    },
    plugins: [rankedValueLabelPlugin],
  };
  if (!charts[canvasId]) {
    charts[canvasId] = newSizedChart(canvasId, ctx, config);
  } else {
    charts[canvasId].data = data;
    charts[canvasId].update();
  }
}

// Prints each bar's actual value at its end. Mandatory for the log chart above,
// not decoration: on a log axis a bar twice as long is not twice the value, so
// the printed number is the only honest statement of quantity.
const rankedValueLabelPlugin = {
  id: "rankedValueLabels",
  afterDatasetsDraw(chart, _args, pluginOpts) {
    if (!pluginOpts) return;
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    const values = chart.data.datasets[0].data;
    ctx.save();
    ctx.font = `${TYPE.axis.size}px ${FONT_SANS}`;
    ctx.fillStyle = AXIS_TEXT;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    meta.data.forEach((bar, i) => {
      const v = values[i];
      const text = v >= 1000 ? formatCompact(v) : (v >= 1 ? v.toFixed(0) : v.toFixed(3));
      ctx.fillText(text, bar.x + 6, bar.y);
    });
    ctx.restore();
  },
};

// ---------- Request queue: at most one model request in flight at a time.
// Rapid lever clicks or preset switches queue their *intent*, not a request —
// a newer intent replaces whatever was waiting, so a burst of clicks costs
// one round trip, not one per click, and the response that lands always
// reflects the most recent lever state, never a stale intermediate one. ----------
let modelBusy = false;
let queuedTask = null;

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("request failed: " + res.status);
  return res.json();
}

function pumpModel() {
  if (modelBusy || !queuedTask) return;
  const task = queuedTask;
  queuedTask = null;
  modelBusy = true;
  setStatus("recalculating…", "recalculating");
  const run = task.kind === "scenario" ? runSetScenario(task.level) : runRecalc();
  run.then(() => {
    modelBusy = false;
    if (queuedTask) pumpModel();
    // Idle says nothing. This used to print "live · 7:09:17 PM" — a wall clock,
    // ticking to the second, next to a projection that ends in 2047. It looked
    // like telemetry from a running system and was really just the time the
    // last fetch returned. The chip now only speaks when there is something
    // true to say: recalculating, or failed.
    else setStatus("", "");
  }).catch((err) => {
    console.error(err);
    modelBusy = false;
    setStatus("error", "error");
    document.getElementById("error").textContent = "Recalculation failed — try again.";
    if (queuedTask) pumpModel();
  });
}

function requestModel(task) {
  queuedTask = task;
  pumpModel();
}

async function runSetScenario(level) {
  const lvl = parseInt(level, 10);
  const data = await postJSON("/set_scenario", { level: lvl });
  for (const id of ids) setLeverLevel(id, lvl);
  updateAllSubcatQuickButtons();
  applyResult(data);
}

async function runRecalc() {
  // Levers are read at send time, not when the click happened, so a request
  // that waited in the queue picks up every click made while it waited.
  const levers = {};
  for (const id of ids) levers[id] = document.getElementById(id).value;
  applyResult(await postJSON("/recalc", levers));
}

function setScenario(level) { requestModel({ kind: "scenario", level: level }); }

function scheduleRecalc() {
  clearTimeout(recalcTimer);
  recalcTimer = setTimeout(() => requestModel({ kind: "recalc" }), 250);
}

const scenarioSelect = document.getElementById("scenario-select");
if (scenarioSelect) {
  scenarioSelect.addEventListener("change", () => {
    if (scenarioSelect.value) setScenario(scenarioSelect.value);
  });
}

// Sets one lever's hidden-input value — the single source of truth read
// by recalc()/setScenario(). The visible control is the sub-sector's
// shared draggable lever (updateLeverRow), not a per-lever widget, so
// there's no per-lever DOM to refresh here.
function setLeverLevel(id, level) {
  const hidden = document.getElementById(id);
  const max = parseInt(hidden.dataset.max, 10);
  hidden.value = Math.min(level, max);
}

// PATHWAY_NAMES lived here, mapping a level to its display name for the chip's
// own text. The chip is the <select> itself now, so the names come from its
// options — one source instead of two that could disagree on wording (they
// already did: "Least Effort" here against "Least effort" in the markup).

// Which preset, if any, the current lever vector IS.
//
// The old test was `values.every(v => v === values[0])` — every lever on the
// identical level — and it was wrong for every pathway above 3, because
// seven levers cannot reach 4: rows 31/40/59-62 stop at 3 and the model
// clamps them. So choosing "Heroic effort" wrote the heroic vector and the
// interface then reported "Custom pathway" and un-highlighted the button you
// had just pressed.
// A pathway is level N when every lever is at min(N, its own ceiling), which
// is exactly what /set_scenario writes and the same saturation rule
// updateLeverRow uses to decide whether a row is in step.
function matchingPreset() {
  const hiddens = ids.map((id) => document.getElementById(id));
  for (const level of [1, 2, 3, 4]) {
    const matches = hiddens.every((h) =>
      parseInt(h.value, 10) === Math.min(level, parseInt(h.dataset.max, 10)));
    if (matches) return level;
  }
  return null;
}

// Reflects the loaded lever vector into the pathway chip. The select IS the
// readout — setting its value is what displays the name, including the
// disabled "Custom pathway" option (value "") when no preset matches — so
// there is no separate text node to keep in step any more.
function updatePathwayName() {
  const preset = matchingPreset();
  // The dot carries the effort level, so the chip shows how ambitious the
  // loaded pathway is without reading the name.
  const chip = document.querySelector(".pathway-chip");
  if (chip) chip.dataset.level = preset ? String(preset) : "custom";
  if (scenarioSelect) scenarioSelect.value = preset ? String(preset) : "";
}

// updateGroupAvg()/updateAllGroupAvgs() lived here and are gone with the
// group-head badge they wrote into. The badge went through "avg N.N" and then
// "21 levers · L3-4" and neither justified the space: a group's state is
// legible from its own rows' sliders, and the loaded pathway is named in the
// deck's select and in the chip beside the tabs. Nothing else read
// .lg-box[data-lever-ids], so that attribute is gone from the markup too.

// Paints one lever's fill/thumb from its CURRENT numeric value (1-based
// index into data-fills, the same LEVEL_FILL ramp sidebar.py renders the
// track with) — shared by drag (initLevers' own input handler) and by every
// external sync below (recalc, pathway button, flyout edit on a bundled row).
function paintLever(lever, value, max, spread) {
  const fills = lever.dataset.fills.split(",");
  const color = fills[Math.min(value - 1, fills.length - 1)];
  const at = (v) => (max > 1 ? ((v - 1) / (max - 1)) * 100 : 0);
  const pct = at(value);
  // Sets the one CSS custom property the track/fill/thumb/glow all read
  // (--lg-lever-color in dashboard.css) rather than painting each element's
  // background directly, so the thumb's radial-gradient + glow ring stay
  // intact instead of being flattened to a solid color on every drag.
  lever.style.setProperty("--lg-lever-color", color);
  lever.querySelector(".lg-lever-fill").style.width = pct + "%";
  lever.querySelector(".lg-lever-thumb").style.left = pct + "%";

  // The spread band: where this row's levers actually sit when they don't all
  // sit together. A group row drives several real levers with different
  // Control-sheet ceilings, so "Buildings" on the heroic pathway is genuinely
  // five levers at 4 and one (lv40, capped at 3) at 3 — one handle at the
  // rounded average was reporting a level no lever was on. The band shows the
  // real low-to-high extent and the handle keeps marking the average within
  // it; with every lever on the same level there is nothing to show and the
  // band stays hidden.
  const band = lever.querySelector(".lg-lever-band");
  if (!band) return;
  if (!spread || spread.lo === spread.hi) {
    band.style.display = "none";
    return;
  }
  band.style.display = "block";
  band.style.left = at(spread.lo) + "%";
  band.style.width = (at(spread.hi) - at(spread.lo)) + "%";
}

// Reflects one sub-sector's row: if every lever inside it is currently at
// the same level, the lever snaps to and highlights that level; otherwise
// it shows the rounded average with a "mixed" ring (mirrors the level-box
// behavior this project used before the v2 redesign, adapted from N
// discrete buttons to one continuous lever).
function updateLeverRow(row) {
  const leverIds = row.dataset.leverIds.split(",").filter(Boolean);
  const hiddens = leverIds.map((id) => document.getElementById(id));
  const lever = row.querySelector(".lg-lever");
  if (!lever || !hiddens.length) return;
  const values = hiddens.map((h) => parseInt(h.value, 10));
  const caps = hiddens.map((h) => parseInt(h.dataset.max, 10));
  const max = parseInt(lever.dataset.max, 10);
  // The row reads as the HIGHEST level any of its levers reached, not their
  // average: a lever pinned at its own lower ceiling must not drag the row's
  // position back down (Buildings' "Growth of floorspace" stops at 3 while
  // its five siblings go to 4, so an average would park that row at 4 by
  // luck here and mis-report it as soon as a row has more capped levers).
  const target = Math.max.apply(null, values);
  // "Agreeing" has to account for saturation. A lever sitting at its own cap
  // while its siblings sit higher is NOT a mixed row — it is as far as that
  // lever goes — so only report mixed when some lever is below the target
  // AND below its own cap, i.e. genuinely out of step because it was edited
  // individually in the flyout. Without this, every Buildings row at level 4
  // would wear the mixed ring permanently.
  const inStep = values.every((v, i) => v === Math.min(target, caps[i]));
  const shown = inStep
    ? target
    : Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  lever.querySelector(".lg-lever-input").value = shown;
  lever.classList.toggle("is-mixed", !inStep);
  // The band draws the row's real low-to-high extent whenever its levers are
  // not all on one level — including the saturated case, which is the case
  // that actually occurs on the presets. `inStep ? null : ...` was tried
  // first and meant the band never appeared at all on any preset: on the
  // heroic pathway Buildings is five levers at 4 and one (lv40, capped at 3)
  // at 3, which inStep correctly calls "in step" — but "in step" is a
  // statement about the THUMB (the row is set as high as it goes, so no
  // hollow mixed thumb) and it is not a statement about where the levers
  // sit. Those are different questions and the answer to the second one is
  // 3-to-4. paintLever hides the band on lo === hi, so a genuinely uniform
  // row still draws nothing.
  const lo = Math.min.apply(null, values);
  const hi = Math.max.apply(null, values);
  paintLever(lever, shown, max, { lo: lo, hi: hi });
  // Said in words too, so a row is readable without dragging it. Three
  // distinct states, because "in step" and "all on one level" are not the
  // same thing: a saturated row IS in step (nothing is out of place) while
  // still spanning two levels, and a sentence claiming "6 levers at level 4"
  // next to a band drawn across 3–4 contradicted its own control.
  //
  // A data attribute, NOT `lever.title`. As a native title it was a second
  // tooltip: the browser's own dark box appeared over the row at the same
  // time as the deck's white popup, in a different place and a different
  // style, saying a different half of the same thing. This is now the state
  // line INSIDE that one popup (initLeverTooltip's renderGroup reads it), so
  // there is exactly one thing on screen when you hover a lever.
  if (!inStep) {
    lever.dataset.rowState = leverIds.length + " levers out of step, across levels " + lo + "–" + hi + " of " + max;
  } else if (lo !== hi) {
    lever.dataset.rowState = leverIds.length + " levers, each as high as it goes — levels " + lo + "–" + hi + " of " + max;
  } else {
    lever.dataset.rowState = leverIds.length > 1
      ? "All " + leverIds.length + " levers at level " + target + " of " + max
      : "Level " + values[0] + " of " + max;
  }
}

function updateAllSubcatQuickButtons() {
  document.querySelectorAll(".lg-subcat-row").forEach(updateLeverRow);
}

// Clean share is now computed in outputs.py (kpis.clean_share) rather than
// here. It had to move: it is one of the four headline cards, so the Insights
// panel has to report its before/after alongside the other three, and
// kpi_deltas() can only diff values the model actually emits. This reader
// keeps the rounding in one place and falls back to the old client-side
// formula only if an older cached payload arrives without the field.
function cleanSharePct(data) {
  if (data.kpis && typeof data.kpis.clean_share === "number") return Math.round(data.kpis.clean_share);
  return data.total_supply ? Math.round((data.renewables + data.nuclear) / data.total_supply * 100) : 0;
}
function emissionsGt(data) {
  // emissions_2047_total is 'IESS V3 Results'!J116 (Million tonne CO2e) — the
  // workbook's own total row, equal to emissions_by_sector_chart.total's last entry on
  // every golden-master vector. Reading it directly means the landing tab no longer
  // builds a 102-cell chart (~1.1s) just to reach this one number. /1000 -> GtCO2.
  return typeof data.emissions_2047_total === "number" ? data.emissions_2047_total / 1000 : null;
}

// "9.6 GtCO₂" with a real <sub>, not U+2082.
//
// The KPI figure is set in Instrument Serif, and Instrument Serif contains no
// subscript-two glyph — checked against the upstream TTF, not guessed (see
// tools/build_fonts.py). With the literal character, that one glyph came from
// a fallback serif in the largest text on the page, which is the most visible
// place a mismatch can happen. <sub> subscripts the display face's own "2".
// Built with DOM nodes rather than innerHTML because the number is
// interpolated.
function setEmissionsFigure(el, gt) {
  el.textContent = "";
  if (gt == null || isNaN(gt)) { el.textContent = "–"; return; }
  el.appendChild(document.createTextNode(gt.toFixed(1) + " GtCO"));
  const sub = document.createElement("sub");
  sub.textContent = "2";
  el.appendChild(sub);
}

// The emissions card is gone from the KPI row (see all_energy.py) — the GHG
// gauge above Custom Pathways is the same number from the same field, so this
// no longer writes it. setEmissionsFigure() is still used, by the gauge.
function renderOverviewKpis(data) {
  const demandEl = document.getElementById("stat-demand-value");
  if (!demandEl) return; // not every tab has the KPI row (All Energy only)
  demandEl.textContent = data.total_demand.toLocaleString() + " Mtoe";
  document.getElementById("stat-demand-note").textContent = data.kpis.per_capita_demand.toLocaleString() + " MJ/person";
  document.getElementById("stat-clean-value").textContent = cleanSharePct(data) + "%";
  document.getElementById("stat-imports-value").textContent = data.kpis.import_dependence + "%";
}

// Display metadata for the KPI keys app.py's kpi_deltas() can return — one
// flat lookup shared by the change-strip and the Insights panel so a KPI's
// label/unit/scale is defined in exactly one place. emissions_2047_total is
// server-side "Million tonne CO2e"; /1000 matches the stat card's own GtCO2.
const KPI_LABELS = {
  total_demand: { label: "Final demand", unit: "Mtoe", scale: 1 },
  total_supply: { label: "Total supply", unit: "Mtoe", scale: 1 },
  per_capita_demand: { label: "Per-capita demand", unit: "MJ/person", scale: 1 },
  import_dependence: { label: "Imported fuel share", unit: "%", scale: 1 },
  clean_share: { label: "Clean share", unit: "%", scale: 1 },
  emissions_2047_total: { label: "Emissions (2047)", unit: "GtCO₂", scale: 1 / 1000 },
};

// The four KPI cards, in the order the cards themselves are laid out — the two
// headline figures first, then the supporting pair (see all_energy.py). The
// Insights panel walks this list so "the resulting change in the four KPIs"
// is literally the four cards on screen, in their own order, rather than
// whatever order kpi_deltas() happened to return.
const CARD_KPI_KEYS = ["total_demand", "emissions_2047_total", "clean_share", "import_dependence"];
function fmtKpi(key, value) {
  const meta = KPI_LABELS[key];
  const v = value * meta.scale;
  // minimumFractionDigits matches the maximum below 100, so a before → after
  // pair reads "2.0 GtCO₂ → 2.1 GtCO₂" rather than "2 GtCO₂ → 2.1 GtCO₂" —
  // the same quantity should not change its number of decimals mid-sentence.
  const digits = Math.abs(v) >= 100 ? 0 : 1;
  const num = v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return meta.unit === "%" ? num + "%" : num + " " + meta.unit;
}

// Templated plain-language impact summary — built entirely from the same
// two fields the strip itself shows, just turned into short lines with a
// small direction badge each (the "little graphics" — a lightweight visual
// cue, not a chart, so it can't itself be wrong about what the numbers say).
// No model call, no external service: deterministic and always in sync with
// the numbers already on screen.
//
// `segments` is an array of strings (plain text) or {strong: "..."} objects
// (the changed figure itself, bolded for emphasis) — built via DOM methods
// rather than innerHTML since these get concatenated with lever/KPI names,
// so nothing here ever gets parsed as markup.
// `direction` is "up" | "down" | null. It used to be the glyph itself ("▲" /
// "▼"), which the badge then string-compared to pick its class — and Roboto
// contains no triangles (nor any arrow), so the glyph would have fallen back
// to whatever the OS had, inside a coloured chip. The triangle is drawn in
// CSS now (.insights-arrow-up/-down), so passing a direction rather than a
// character is both the fix and the clearer contract.
function addInsightsLine(body, direction, segments) {
  const row = document.createElement("div");
  row.className = "insights-line";
  if (direction) {
    const badge = document.createElement("span");
    badge.className = "insights-arrow insights-arrow-" + direction;
    badge.setAttribute("aria-hidden", "true");
    row.appendChild(badge);
  }
  const text = document.createElement("span");
  segments.forEach((seg) => {
    if (typeof seg === "string") {
      text.appendChild(document.createTextNode(seg));
    } else if (seg.arrow) {
      text.appendChild(arrowEl());
    } else {
      const strong = document.createElement("strong");
      strong.textContent = seg.strong;
      text.appendChild(strong);
    }
  });
  row.appendChild(text);
  body.appendChild(row);
}

/* The "→" in "9.6 GtCO₂ → 8.5 GtCO₂", as an inline SVG rather than U+2192.
   Roboto has no arrows at all (U+2190-2193 absent from all 927 of its
   codepoints — checked against the upstream TTF, see tools/build_fonts.py),
   so the character would have been served by a system fallback: one glyph in
   a different face, mid-sentence, in the one panel whose whole job is to be
   read. A drawn arrow cannot fall back.
   Sized in `em` and stroked in `currentColor`, so it tracks the font size and
   colour of whatever line it sits in — including the --ui-scale zoom. */
const ARROW_PATH = "M4 12h15M13 6l6 6-6 6";
function arrowEl() {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "in-arrow");
  svg.setAttribute("viewBox", "0 0 24 24");
  // Labelled, NOT aria-hidden. The character it replaces was announced
  // ("rightwards arrow"); hiding the shape would leave a screen reader with
  // "Final demand 2,202 Mtoe 2,059 Mtoe" and no relationship between the two
  // figures. "to" is what the arrow means here.
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "to");
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", ARROW_PATH);
  p.setAttribute("fill", "none");
  p.setAttribute("stroke", "currentColor");
  p.setAttribute("stroke-width", "2.4");
  p.setAttribute("stroke-linecap", "round");
  p.setAttribute("stroke-linejoin", "round");
  svg.appendChild(p);
  return svg;
}
// Same arrow for the one place that builds its content as an HTML string (the
// Sankey link tooltip, "Coal → Solid"). Same path data, so the two cannot
// drift apart.
const ARROW_SVG = '<svg class="in-arrow" viewBox="0 0 24 24" role="img" aria-label="to">' +
  '<path d="' + ARROW_PATH + '" fill="none" stroke="currentColor" stroke-width="2.4" ' +
  'stroke-linecap="round" stroke-linejoin="round"/></svg>';

// addInsightsGroupLabel() lived here — a small-caps label + rule ahead of each
// group of insight lines, back when the panel showed two lists ("Levers
// changed", then "Effect on the four KPIs"). The lever list is gone (see
// renderInsights), so there is one list and nothing left to separate.

// Always rendered into the rail's permanent Insights block (called from
// applyResult on every recalc) — no open/close state, unlike the
// popup/docked-flyout this used to be. Takes `data` directly (the same
// recalc response applyResult already has) rather than the old stash-on-
// the-rail-then-reread dance, which only ever had this one caller.
// What matters here is which levers moved and what that did — not a KPI
// snapshot the stat cards above already show — so the idle/base state
// (nothing moved yet) is just a one-line status, not a repeat of those
// numbers.
/* The GHG gauge along the deck's top edge (see .cdh-emissions).
   EMISSIONS_SCALE_GT is a real reference, not a guess: clicking through the
   four preset buttons gives 9.6 / 5.3 / 2.8 / 2.0 GtCO2 for 2047, so 10 Gt is
   the next round number above the worst case the model produces. A pathway
   therefore starts the bar nearly full and empties it as it gets more
   ambitious. (Measured through the UI, not by hand-posting a lever vector to
   /recalc — a hand-built payload has to guess the lever ids and quietly gets
   different answers.)
   emissions_2047_total arrives in MEGAtonnes (9635.32 for the least-effort
   pathway, which the KPI card shows as 9.6 GtCO2) — hence the /1000. */
const EMISSIONS_SCALE_GT = 10;

function renderEmissionsBar(data) {
  const fill = document.getElementById("cdh-emissions-fill");
  const value = document.getElementById("cdh-emissions-value");
  if (!fill || !value) return;
  const mt = data.emissions_2047_total;
  if (mt == null || isNaN(mt)) return;

  const gt = mt / 1000;
  const pct = Math.max(0, Math.min(100, (gt / EMISSIONS_SCALE_GT) * 100));
  fill.style.width = pct + "%";
  value.style.left = pct + "%";
  setEmissionsFigure(value, gt);
  // Inside the fill (white) whenever the fill is genuinely wide enough to hold
  // the text, otherwise just outside it in dark ink. Measured in pixels rather
  // than guessed from the percentage: the track's width varies with the window
  // and with --ui-scale, so the same percentage is a different number of
  // pixels on different screens.
  const trackPx = fill.parentElement.clientWidth || 0;
  value.classList.toggle("is-inside", (trackPx * pct) / 100 > value.offsetWidth + 18);

  const wrap = document.getElementById("cdh-emissions");
  if (wrap) {
    wrap.setAttribute("role", "img");
    wrap.setAttribute("aria-label",
      `Greenhouse gas emissions in 2047: ${gt.toFixed(1)} of ${EMISSIONS_SCALE_GT} gigatonnes CO2 on the scale shown`);
  }
}

/* The base state's own content. "Nothing has been changed yet" described the
   reader's click history, not the pathway — an empty state standing in for a
   fact the payload already contains. These are read straight out of the
   result on screen:

   - Coal's share of 2047 primary supply, from supply_chart's own Coal series
     over its own total. One source, so the share cannot disagree with the
     Energy Supply chart it is describing.
   - Where final demand ends up relative to 2022, from demand_chart.total's
     first and last years.

   Both are properties of the loaded pathway, so they change when you pick a
   different one — which is the point: the panel says something different
   about Least Effort than about Heroic Effort before you touch a lever. */
function lastOf(arr) { return Array.isArray(arr) && arr.length ? arr[arr.length - 1] : null; }

function renderBaseStateFacts(body, data) {
  const supply = data.supply_chart;
  const coal2047 = supply && supply.series ? lastOf(supply.series["Coal"]) : null;
  const supply2047 = supply ? lastOf(supply.total) : null;
  if (coal2047 != null && supply2047) {
    const pct = Math.round((coal2047 / supply2047) * 100);
    addInsightsLine(body, null, [
      "Coal still carries ", { strong: pct + "%" },
      ` of primary supply in 2047 (${Math.round(coal2047).toLocaleString()} of ${Math.round(supply2047).toLocaleString()} Mtoe).`,
    ]);
  }

  const demand = data.demand_chart;
  const first = demand && Array.isArray(demand.total) ? demand.total[0] : null;
  const last = demand ? lastOf(demand.total) : null;
  if (first && last) {
    const growth = Math.round(((last - first) / first) * 100);
    addInsightsLine(body, null, [
      "Final demand goes from ", { strong: Math.round(first).toLocaleString() + " Mtoe" },
      " in 2022 to ", { strong: Math.round(last).toLocaleString() + " Mtoe" },
      ` in 2047 — ${growth > 0 ? "up" : "down"} ${Math.abs(growth)}% over the period.`,
    ]);
  }

  addInsightsLine(body, null, [
    "Move any lever in Custom Pathways below and this panel reports what it did.",
  ]);
}

function renderInsights(data) {
  const body = document.getElementById("insights-panel-body");
  body.innerHTML = "";

  const leverChanges = data.lever_changes || [];
  const kpiChanges = data.kpi_deltas || {};

  // `leverChanges` is still read, but only to decide WHETHER anything has
  // moved. The list of moved levers is deliberately not printed: which lever
  // sits where is already shown, live, by the Custom Pathways deck below —
  // every moved row's handle is visibly off its neighbours' position — so
  // restating it here filled the panel with rows the reader had just set
  // themselves and pushed the KPI effects, the one thing the deck cannot
  // show, below the fold. This panel now answers exactly one question: what
  // did that do to the results?
  if (!leverChanges.length) {
    // No "Base state" chip either: labelling the idle message put a heading
    // over a single sentence and nothing else.
    renderBaseStateFacts(body, data);
    return;
  }

  // The four cards, in card order, each with its own before → after. A card
  // that did not move is stated as unchanged rather than dropped: "emissions
  // held still while demand fell" is a real result, and silently omitting it
  // reads as an oversight.
  //
  // No group label over these. It marked a second list back when the lever
  // list was the first one; with that gone there is one list, and the panel's
  // own "Insights" heading already sits directly above it.
  CARD_KPI_KEYS.forEach((key) => {
    const meta = KPI_LABELS[key];
    const d = kpiChanges[key];
    if (!d) {
      addInsightsLine(body, null, [meta.label + " ", { strong: "unchanged" }]);
      return;
    }
    const pct = d.pct != null ? ` (${d.delta > 0 ? "+" : "−"}${Math.abs(d.pct)}%)` : "";
    // The before/after arrow is a drawn element between two bolded figures,
    // not a character inside one string — see arrowEl().
    addInsightsLine(body, d.delta > 0 ? "up" : "down", [
      meta.label + " ",
      { strong: fmtKpi(key, d.from) }, { arrow: true }, { strong: fmtKpi(key, d.to) },
      pct,
    ]);
  });
}

// renderSupplySplit() and computeImportRelianceSeries() lived here. Both
// went with the "Primary supply split" bar and the All Energy import-reliance
// chart they fed: supply_chart is now drawn in full by the Energy Supply
// stacked-area chart (every year, not just 2047's shares), and import
// reliance is the Energy Security tab's Import Dependence chart plus the
// Imported fuel KPI card. supply_chart itself is still computed and still
// diffed — only these two view-layer renderers are gone.

let deferredCacheKey = null;

function applyResult(data) {
  // The deferred keys belong to a lever state; a fresh result may be a different one.
  deferredCacheKey = null;
  renderOverviewKpis(data);
  renderInsights(data);
  renderEmissionsBar(data);
  updatePathwayName();
  updateAllSubcatQuickButtons();
  // All Energy's two headline charts: same renderer, same live lever
  // reaction, vertical legend on the right with Total first.
  const duoOpts = { unit: "Mtoe", maintainAspectRatio: false, legendPosition: "right", totalFirst: true };
  if (document.getElementById("demandChart")) {
    renderStackedChart("demandChart", data.demand_chart, data.changed && data.changed.demand_chart && data.changed.demand_chart.series,
      { ...duoOpts, changedCardId: "card-demand" });
  }
  if (document.getElementById("supplyChart")) {
    renderStackedChart("supplyChart", data.supply_chart, data.changed && data.changed.supply_chart && data.changed.supply_chart.series,
      { ...duoOpts, changedCardId: "card-supply" });
  }
  if (data.import_dependence_chart) {
    renderImportDependenceChart("esImportDependenceChart", data.import_dependence_chart);
  }
  if (data.energy_imports_chart) {
    renderStackedChart("energyImportsChart", data.energy_imports_chart, null, { unit: "Mtoe", legendPosition: "right" });
  }
  if (data.emissions_by_sector_chart) {
    renderStackedChart("emissionsBySectorChart", data.emissions_by_sector_chart, null, { unit: "Mt CO₂e", legendPosition: "right" });
  }
  if (data.per_capita_emissions_chart) {
    renderBarChart("perCapitaEmissionsChart", data.per_capita_emissions_chart, { unit: "tonne CO2e per person", color: PALETTE.red });
    renderBarChart("indPerCapitaEmissionsChart", data.per_capita_emissions_chart, { unit: "tonne CO2e/person", color: PALETTE.red });
  }
  if (data.emissions_intensity_chart) {
    renderBarChart("indEmissionsIntensityChart", data.emissions_intensity_chart, { unit: "kg CO2e / 1000 INR", color: PALETTE.red });
  }
  if (data.energy_intensity_chart) {
    renderBarChart("indEnergyIntensityChart", data.energy_intensity_chart, { unit: "MJ/INR", color: PALETTE.blue });
  }
  if (data.per_capita_supply_chart) {
    renderBarChart("perCapitaSupplyChart", data.per_capita_supply_chart, { unit: "toe/person", color: PALETTE.teal });
  }
  if (data.capacity_chart) {
    renderStackedChart("capacityChart", data.capacity_chart, null, { unit: "GW", legendPosition: "right" });
  }
  if (data.demand_electrification_chart) {
    renderBarChart("demandElectrificationChart", data.demand_electrification_chart, { unit: "%", color: PALETTE.cyan });
  }
  if (data.import_cost_chart) {
    renderStackedChart("importCostChart", data.import_cost_chart, null, { unit: "Billion INR", legendPosition: "right" });
  }
  if (data.production_cost_chart) {
    renderStackedChart("productionCostChart", data.production_cost_chart, null, { unit: "Billion INR", legendPosition: "right" });
  }
  if (data.capex_chart) {
    renderStackedBarChart("capexChart", data.capex_chart, { unit: "Billion INR" });
  }
  if (data.opex_chart) {
    renderStackedChart("opexChart", data.opex_chart, null, { unit: "Billion INR", legendPosition: "right" });
  }
  if (data.land_use_chart) {
    renderStackedChart("landUseChart", data.land_use_chart, null, { unit: "Hectares", compact: true, legendPosition: "right" });
  }
  if (data.water_use_chart) {
    renderStackedChart("waterUseChart", data.water_use_chart, null, { unit: "Litres", compact: true, legendPosition: "right" });
  }
  if (data.crm_capacity_chart) {
    renderStackedChart("crmCapacityChart", data.crm_capacity_chart, null, { unit: "GW", legendPosition: "right" });
  }
  if (data.crm_mineral_rank_chart) {
    renderRankedBarChart("crmMineralRankChart", data.crm_mineral_rank_chart, { unit: "t" });
  }
  if (data.electricity_demand_chart) {
    renderStackedChart("electricityDemandChart", data.electricity_demand_chart,
      data.changed && data.changed.electricity_demand_chart && data.changed.electricity_demand_chart.series,
      { ...duoOpts, changedCardId: "card-elec-demand" });
  }
  if (data.electricity_supply_chart) {
    renderStackedChart("electricitySupplyChart", data.electricity_supply_chart,
      data.changed && data.changed.electricity_supply_chart && data.changed.electricity_supply_chart.series,
      { ...duoOpts, changedCardId: "card-elec-supply" });
  }

  // Any chart created just now was sized by Chart.js, which measures its
  // container wrongly whenever --ui-scale isn't 1 (see
  // resizeChartsToContainers) — too small below 1, over its card above it.
  // Correcting here, where charts are actually built, is what makes this
  // reliable: hanging it off the fit's own timers instead meant a recalc that
  // took longer than the last timer left its charts uncorrected, overflowing
  // the page sideways.
  requestAnimationFrame(resizeChartsToContainers);

  // ...and re-fit, because this call is what puts the Insights panel's content
  // on the page. Insights is a Custom Pathways column now, so its height is
  // part of the deck's height and therefore part of what fitUiScale measures —
  // but the panel is empty until the first /set_scenario response lands, which
  // is after the load-time fit has already run. The result was a page that
  // settled 16px past the bottom of the window on first paint and only came
  // right once a tab was clicked. Not a loop: the fit changes the zoom, and
  // the zoom does not change what renderInsights emits.
  requestAnimationFrame(() => fitUiScale());
}

/* ---------- Tab switching ---------- */
document.querySelectorAll(".pill-tab[data-view]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".pill-tab[data-view]").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + tab.dataset.view).classList.add("active");
    // Insights used to be hidden on Energy Flows, because it sat in a column
    // beside the charts and the Sankey is the one view that really wants that
    // width. It lives in the Custom Pathways band now, where it takes space
    // no chart was using — so it stays visible on every tab, including this
    // one. It also reads better there: it describes the pathway, and the
    // pathway controls are in that band.
    const isEnergyFlows = tab.dataset.view === "energy-flows";
    if (isEnergyFlows || tab.dataset.view === "emissions") {
      ensureDeferredData();
    }
    if (isEnergyFlows && sankeyDataByYear) {
      // Re-render (not just resize) because the Sankey's own layout is
      // computed from its measured container width at render time — hiding
      // the sidebar just above changed that width synchronously.
      renderSankey(sankeyDataByYear[currentSankeyYear]);
    }
  });
});

/* ---------- Sub-tab switching (e.g. Indicators tab) ---------- */
document.querySelectorAll(".subtab:not(.disabled)").forEach((st) => {
  st.addEventListener("click", () => {
    const container = st.closest(".subtabs");
    container.querySelectorAll(".subtab").forEach((t) => t.classList.remove("active"));
    st.classList.add("active");
    const parentView = st.closest(".view");
    parentView.querySelectorAll(".subview").forEach((v) => v.classList.remove("active"));
    document.getElementById("subview-" + st.dataset.subview).classList.add("active");
  });
});

/* ---------- Sub-sector rows: draggable lever (sets every real lever
   underneath that row's sub-sector to the dragged/clicked/arrow-keyed
   level). Flyout rows (one lever each, see initLeverFlyouts below) share
   this same class and markup shape, so a single-lever edit made inside a
   flyout is wired up by this exact loop too — no separate handler needed.
   Re-syncing with updateAllSubcatQuickButtons() (rather than just this row)
   is what keeps the bundled parent row's position correct after an
   individual-lever edit inside its flyout desyncs it from "all levers at
   N". `input` (not `change`) fires continuously while dragging, which is
   what makes the lever feel live rather than only snapping on release. ---------- */
document.querySelectorAll(".lg-subcat-row").forEach((row) => {
  const leverIds = row.dataset.leverIds.split(",").filter(Boolean);
  const lever = row.querySelector(".lg-lever");
  if (!lever) return;
  const input = lever.querySelector(".lg-lever-input");
  const max = parseInt(lever.dataset.max, 10);

  input.addEventListener("input", () => {
    const level = parseInt(input.value, 10);
    lever.classList.remove("is-mixed");
    paintLever(lever, level, max);
    leverIds.forEach((id) => setLeverLevel(id, level));
    updateAllSubcatQuickButtons();
    // Re-derive the pathway readout from the levers immediately, rather than
    // blanking the preset control and waiting for the recalc to come back:
    // dragging a lever to the level the preset already had leaves the vector
    // ON that preset, and eagerly clearing it claimed a custom pathway that
    // the very next response then contradicted. matchingPreset() answers this
    // from the hidden inputs, which are already up to date on this line.
    updatePathwayName();
    scheduleRecalc();
  });
  input.addEventListener("pointerdown", () => lever.classList.add("is-dragging"));
  window.addEventListener("pointerup", () => lever.classList.remove("is-dragging"));
});

/* ---------- Lever tooltip -------------------------------------------------
   Hovering or focusing a lever row shows ONE popup, and it stays inside the
   Custom Pathways band. Two shapes, matching the two kinds of row:

   - A row that drives ONE Control-sheet lever (every flyout row, and the
     single-lever deck rows like "Growth of the Economy") shows that lever's
     own name, where it sits, and the Control sheet's ambition note for that
     level, straight out of data-descs.

   - A BUNDLED deck row ("Buildings · 6") describes ITSELF: what this one
     control does and where it currently sits. It used to dump one line per
     member lever, each with that lever's own note — six or eight notes in a
     panel tall enough to cover the charts, which is what the user rejected on
     sight, and rightly: hovering a control should say what THAT control does.
     The per-lever notes are not lost, they moved to where they belong — open
     the row and hover any lever in the flyout, which is the single-lever case
     above. So the deck answers "what does this row do" and the flyout answers
     "what does this lever do", instead of the deck trying to answer both.

   The state line is not invented here: updateLeverRow() already derives the
   row's three honest states (all on one level / each as high as it goes /
   genuinely out of step) and leaves the sentence on data-row-state.

   PLACEMENT — the popup is clamped to `.control-deck-h`, never the window.
   It is a control's tooltip and the controls are all in that band, so it has
   no business over the charts; before this it was positioned against the
   viewport alone and a tall one ended up top-left of the page, next to
   nothing it described. Preferred above the control, below it when that would
   cross the band's top edge, and clamped inside the band either way.

   Coordinates are converted real px -> logical px. `body` carries
   `zoom: var(--ui-scale)`, and this box is a `position:fixed` child of body,
   so a length set here is multiplied by the zoom on the way to the screen,
   while getBoundingClientRect() reports post-zoom real pixels. Mixing the two
   put the popup progressively further off-target the further --ui-scale was
   from 1 — the same trap documented in sizeChartToContainer(). offsetWidth /
   offsetHeight are already logical, so they need no conversion.

   Re-rendered on every `input` so the text tracks the thumb while dragging
   instead of freezing on whatever level was under the pointer when the hover
   started. ---------- */
(function initLeverTooltip() {
  const tip = document.createElement("div");
  tip.className = "lever-tooltip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  let shown = null;

  const descsOf = (el) => {
    try { return el && el.dataset.descs ? JSON.parse(el.dataset.descs) : {}; }
    catch { return {}; }
  };

  function part(cls, text) {
    const n = document.createElement("div");
    n.className = cls;
    n.textContent = text;
    return n;
  }

  /* The row's own name, in full. Worth a line of its own precisely because
     the row can't always show it: `.lg-subcat-title` and `.lg-flyout-name`
     both ellipsise, and the flyout's names are cut hard at the rail's width
     ("Growth of fl…"). The trailing " · 6" count is stripped — it is a
     property of the row, and the head says the count in words already. */
  function nameOf(row) {
    const t = row.querySelector(".lg-subcat-title, .lg-flyout-name");
    return t ? t.textContent.replace(/\s*·\s*\d+\s*$/, "").trim() : "";
  }

  /* One Control-sheet lever: what this lever is set to, and what that means. */
  function renderSingle(row, lever) {
    const input = lever.querySelector(".lg-lever-input");
    const note = descsOf(lever)[input.value];
    tip.innerHTML = "";
    tip.appendChild(part("lever-tip-head", nameOf(row)));
    tip.appendChild(part("lever-tip-state", "Level " + input.value + " of " + lever.dataset.max));
    // 7 of the 49 levers have columns H-K empty on the Control sheet and 4
    // more have gaps at some levels, so a missing note is normal and is not a
    // reason to show nothing: the name and the level are still the answer to
    // "what am I hovering", and a control that silently refuses to respond
    // reads as broken. (The old code returned false here and rendered
    // nothing at all.)
    if (note) tip.appendChild(part("lever-tip-note", note));
    return true;
  }

  /* A bundled row: what this ONE control does, not what its members say. */
  function renderGroup(row, lever, count) {
    tip.innerHTML = "";
    tip.appendChild(part("lever-tip-head", nameOf(row)));
    tip.appendChild(part("lever-tip-state", lever.dataset.rowState || ""));
    tip.appendChild(part("lever-tip-sub", "One control for all " + count + " levers in this group."));
    tip.appendChild(part("lever-tip-hint", "Open the row to set each lever on its own."));
    return true;
  }

  function render(row) {
    const lever = row.querySelector(".lg-lever");
    if (!lever) return false;
    // A flyout row carries data-lever-ids too, with exactly one id — so the
    // test is the COUNT, not the presence of the attribute.
    const ids = (row.dataset.leverIds || "").split(",").filter(Boolean);
    const ok = ids.length > 1 ? renderGroup(row, lever, ids.length) : renderSingle(row, lever);
    tip.hidden = !ok;
    if (!ok) return false;
    place(lever);
    return true;
  }

  function place(lever) {
    const scale = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--ui-scale")) || 1;
    const px = (v) => v / scale;               // real px -> logical px
    const a = lever.getBoundingClientRect();
    const deck = document.querySelector(".control-deck-h");
    const band = deck ? deck.getBoundingClientRect()
                      : { top: 0, bottom: window.innerHeight, left: 0, right: window.innerWidth };
    const w = tip.offsetWidth, h = tip.offsetHeight;
    const PAD = 10;

    const minL = px(band.left) + PAD, maxL = px(band.right) - w - PAD;
    let left = px(a.left + a.width / 2) - w / 2;
    // Math.max on the ceiling too: on a narrow window the band can be
    // narrower than the popup, and a max below its own min would otherwise
    // pin the box off the left edge.
    left = Math.min(Math.max(left, minL), Math.max(minL, maxL));

    const minT = px(band.top) + PAD, maxT = px(band.bottom) - h - PAD;
    let top = px(a.top) - h - 10;
    if (top < minT) top = px(a.bottom) + 10;
    top = Math.min(Math.max(top, minT), Math.max(minT, maxT));

    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
  }

  function show(row) { shown = render(row) ? row : null; }
  function hide() { tip.hidden = true; shown = null; }

  // Bound to the ROW, not to the lever alone: the name, the count and the
  // chevron are all part of the same control, and hovering a truncated label
  // to find out what it says is the obvious move. It also replaces the
  // native `title` that used to sit on the label (sidebar.py) — one popup for
  // the whole row rather than the browser's box over the name and ours over
  // the track.
  document.addEventListener("mouseover", (e) => {
    const row = e.target.closest(".lg-subcat-row");
    if (row) show(row);
  });
  document.addEventListener("mouseout", (e) => {
    const row = e.target.closest(".lg-subcat-row");
    if (row && !row.contains(e.relatedTarget)) hide();
  });
  document.addEventListener("focusin", (e) => {
    const row = e.target.closest(".lg-subcat-row");
    if (row) show(row);
  });
  document.addEventListener("focusout", (e) => {
    if (e.target.closest(".lg-subcat-row")) hide();
  });
  // Dragging fires `input` on the same row repeatedly — re-render the still-
  // open popup so its text and position track the thumb live. A bundled row
  // needs this because its state line is rewritten by updateLeverRow() as the
  // row is dragged.
  document.addEventListener("input", (e) => {
    if (shown && e.target.closest(".lg-subcat-row") === shown) render(shown);
  });
  // The rail slides the rows sideways, so a popup left open across the
  // animation would be pointing at nothing.
  document.addEventListener("click", (e) => {
    if (e.target.closest(".lg-expand-btn, .lg-subcat-title, .lg-flyout-close")) hide();
  }, true);
  window.addEventListener("scroll", hide, true);
})();

/* ---------- Lever rail: chevron on a multi-lever sub-sector row opens that
   sub-sector's individual levers in the deck's own slide-out rail. The rail
   is a single shared flex item (.lg-rail-col) that dashboard.js relocates —
   via .after() — to sit immediately next to whichever lever column holds
   the clicked chevron, before widening it, so it always opens right beside
   the control you clicked rather than always in the same fixed spot (which
   read as unrelated to the row you'd actually clicked when that row wasn't
   in the last column). Only one sub-sector's block is shown at a time. ---------- */
(function initLeverFlyouts() {
  const chevrons = document.querySelectorAll(".lg-expand-btn");
  const railCol = document.getElementById("lg-rail-col");
  if (!chevrons.length || !railCol) return;
  let openFlyout = null;
  let openChevron = null;

  function closeFlyout() {
    if (!openFlyout) return;
    railCol.classList.remove("is-open");
    openFlyout.classList.remove("is-open");
    openChevron.setAttribute("aria-expanded", "false");
    openFlyout = openChevron = null;
  }

  chevrons.forEach((chevron) => {
    const flyout = document.getElementById(chevron.dataset.flyout);
    if (!flyout) return;

    function toggle(e) {
      e.stopPropagation();
      const alreadyOpen = flyout === openFlyout;
      closeFlyout();
      if (!alreadyOpen) {
        // Move the rail next to this chevron's own column before opening it,
        // so "which lever is this attached to" is never ambiguous.
        const col = chevron.closest(".lg-col");
        if (col) col.after(railCol);
        // Cap the rail to the tallest lever column before opening it, so an
        // open flyout can never make the deck taller than it already is.
        // Without this the rail's own 260px ceiling exceeded the tallest
        // column (198px), the deck grew by the difference, and the page ended
        // up 61px taller than the window — the footer scrolled out of sight
        // the moment you opened a sub-lever list. The flyout scrolls inside
        // itself instead (.lg-rail is overflow-y:auto), which is what that
        // overflow was always there for.
        //
        // offsetHeight, not getBoundingClientRect(): it reports logical
        // (unzoomed) pixels, which is the space a CSS max-height is expressed
        // in. A rect here would be real pixels and would need dividing by
        // --ui-scale — the same trap documented in sizeChartToContainer().
        const cols = [...railCol.parentElement.querySelectorAll(".lg-col:not(.lg-rail-col)")];
        const tallest = Math.max(0, ...cols.map((el) => el.offsetHeight));
        if (tallest) railCol.style.maxHeight = tallest + "px";
        railCol.classList.add("is-open");
        flyout.classList.add("is-open");
        chevron.setAttribute("aria-expanded", "true");
        openFlyout = flyout;
        openChevron = chevron;
      }
    }

    chevron.addEventListener("click", toggle);

    // The row's LABEL opens it too. Reaching for a 15px chevron was the only
    // way in before. Bound to .lg-subcat-title rather than the whole row on
    // purpose: the row also carries the lever, and a click there has to reach
    // the slider rather than being intercepted. The chevron keeps the
    // aria-expanded state and the keyboard path, so the title stays a plain
    // pointer affordance and adds no second tab stop.
    const row = chevron.closest(".lg-subcat-row");
    const title = row && row.querySelector(".lg-subcat-title");
    if (row && title) {
      row.classList.add("is-expandable");   // CSS hangs the hover/cursor off this
      title.addEventListener("click", toggle);
    }

    const closeBtn = flyout.querySelector(".lg-flyout-close");
    if (closeBtn) closeBtn.addEventListener("click", closeFlyout);
  });

  document.addEventListener("click", (e) => {
    if (openFlyout && !openFlyout.contains(e.target) && !railCol.parentElement.contains(e.target)) closeFlyout();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeFlyout();
  });
  window.addEventListener("resize", closeFlyout);
  document.querySelectorAll(".pill-tab[data-view]").forEach((tab) => tab.addEventListener("click", closeFlyout));
})();

/* ---------- Masthead menu: right-hand slide-in drawer ---------- */
(function initAppMenu() {
  const btn = document.getElementById("app-menu-btn");
  const drawer = document.getElementById("app-menu");
  const closeBtn = document.getElementById("app-menu-close");
  if (!btn || !drawer || !closeBtn) return;

  const isOpen = () => drawer.classList.contains("is-open");
  let lastFocused = null;

  function open() {
    lastFocused = document.activeElement;
    drawer.classList.add("is-open");
    btn.setAttribute("aria-expanded", "true");
  }
  function close() {
    drawer.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
    if (lastFocused) lastFocused.focus();
  }

  btn.addEventListener("click", (e) => { e.stopPropagation(); isOpen() ? close() : open(); });
  closeBtn.addEventListener("click", close);
  document.addEventListener("click", (e) => {
    if (isOpen() && !drawer.contains(e.target) && !btn.contains(e.target)) close();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && isOpen()) close(); });
})();

/* ---------- Energy Flows: Sankey diagram (d3-sankey) ---------- */
let sankeyDataByYear = null;
let currentSankeyYear = window.APP_CONFIG.defaultSankeyYear;
let deferredLastLeverSignature = null;

function leverSignature() {
  return ids.map((id) => document.getElementById(id).value).join(",");
}

// The Emissions-by-sector chart and the Sankey are deferred out of the
// default /recalc payload (most tabs never need them) — fetched once per
// distinct lever state, the moment a tab that does need them activates.
async function ensureDeferredData() {
  const sig = leverSignature();
  if (deferredCacheKey === sig && sankeyDataByYear) return;
  const levers = {};
  for (const id of ids) levers[id] = document.getElementById(id).value;
  const data = await postJSON("/deferred", levers);
  deferredCacheKey = sig;
  if (data.sankey) sankeyDataByYear = data.sankey;
  if (data.emissions_by_sector_chart) {
    renderStackedChart("emissionsBySectorChart", data.emissions_by_sector_chart, null, { unit: "Mt CO₂e", legendPosition: "right" });
  }
  if (sankeyDataByYear && document.getElementById("view-energy-flows").classList.contains("active")) {
    renderSankey(sankeyDataByYear[currentSankeyYear]);
  }
}

document.querySelectorAll(".year-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".year-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentSankeyYear = btn.dataset.year;
    if (sankeyDataByYear) renderSankey(sankeyDataByYear[currentSankeyYear]);
  });
});

/* The five category colours. These are the ANCHORS the chart palette is built
   from (see PALETTE at the top) and are deliberately left exactly as they are:
   the diagram is the one place where all five appear together and none of them
   are adjacent bands, so it needs no lightness spreading. The chart palette's
   copies differ by at most ±0.08 lightness — near-identical for amber and red,
   a little deeper for teal and violet. */
const SANKEY_NODE_COLORS = {
  source: "#22d3a8", tech: "#4f9bf2", carrier: "#f2b84b", loss: "#e05263", demand: "#7b6ef6",
};

function renderSankey(yearData) {
  if (!yearData || !window.d3 || !window.d3.sankey) return;
  const svgEl = document.getElementById("sankeySvg");
  const width = svgEl.clientWidth || svgEl.parentElement.clientWidth;
  const height = svgEl.clientHeight || 500;
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${width} ${height}`);
  svg.selectAll("*").remove();

  // outputs.py's compute_sankey references nodes by their ARRAY INDEX (not
  // name) in each link's source/target — d3-sankey's default nodeId is
  // exactly "index in the nodes array", so this only works as long as
  // nodeId is left at its default and the nodes array isn't reordered.
  const nodes = yearData.nodes.map((n) => ({ ...n }));
  const links = yearData.links
    .filter((l) => l.value > 0)
    .map((l) => ({ source: l.source, target: l.target, value: l.value }));

  const totalSupply = links
    .filter((l) => nodes[l.source] && nodes[l.source].category === "source")
    .reduce((sum, l) => sum + l.value, 0);
  const totalEl = document.getElementById("sankey-total");
  if (totalEl) totalEl.innerHTML = `Total primary supply: <b>${totalSupply.toFixed(1)}</b> Mtoe`;

  const sankeyGen = d3.sankey()
    .nodeWidth(14)
    .nodePadding(Math.max(4, Math.min(16, height / (nodes.length || 1))))
    .extent([[1, 5], [width - 1, height - 5]]);

  let graph;
  try {
    graph = sankeyGen({ nodes: nodes.map((d) => ({ ...d })), links: links.map((d) => ({ ...d })) });
  } catch (e) {
    console.error("sankey layout failed", e);
    return;
  }

  const tooltip = document.getElementById("sankey-tooltip");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const linkPath = d3.sankeyLinkHorizontal();

  /* ---- Flow tracing -------------------------------------------------------
     Hovering a node lights the WHOLE chain it belongs to, not just the links
     touching it: everything upstream that feeds it and everything downstream
     it feeds, walked transitively. That is the interesting question on this
     diagram - hover Electricity and you see every fuel that produced it and
     every sector that consumed it, in one look.
     d3-sankey gives each node its own sourceLinks/targetLinks, so the walk is
     a plain breadth-first search over those. A sankey layout cannot contain a
     cycle, but `seen` guards the traversal regardless. */
  function trace(startNode) {
    const litLinks = new Set();
    const litNodes = new Set([startNode]);
    const walk = (node, direction) => {
      const queue = [node];
      const seen = new Set([node]);
      while (queue.length) {
        const cur = queue.shift();
        const edges = direction === "up" ? cur.targetLinks : cur.sourceLinks;
        for (const edge of edges || []) {
          litLinks.add(edge);
          const next = direction === "up" ? edge.source : edge.target;
          litNodes.add(next);
          if (!seen.has(next)) { seen.add(next); queue.push(next); }
        }
      }
    };
    walk(startNode, "up");
    walk(startNode, "down");
    return { litLinks, litNodes };
  }

  const throughput = (n) => {
    const inSum = (n.targetLinks || []).reduce((t, l) => t + l.value, 0);
    const outSum = (n.sourceLinks || []).reduce((t, l) => t + l.value, 0);
    return Math.max(inSum, outSum);
  };

  const gLinks = svg.append("g");
  const gFlow = svg.append("g").attr("pointer-events", "none");
  const gNodes = svg.append("g");

  const link = gLinks.selectAll("path")
    .data(graph.links)
    .join("path")
    .attr("class", "sankey-link")
    .attr("d", linkPath)
    .attr("fill", "none")
    .attr("stroke", (d) => SANKEY_NODE_COLORS[d.source.category] || "#c3c6d4")
    .attr("stroke-opacity", 0.35)
    .attr("stroke-width", (d) => Math.max(1, d.width));

  /* A second, dashed copy of every link, invisible until traced. Its dashes
     scroll (CSS animation on stroke-dashoffset), which is what makes a traced
     route read as flowing rather than merely coloured. An overlay rather than
     dashing the real link, because dashing that would punch gaps in the band
     itself. */
  const flow = gFlow.selectAll("path")
    .data(graph.links)
    .join("path")
    .attr("class", "sankey-flow")
    .attr("d", linkPath)
    .attr("fill", "none")
    .attr("stroke", "#fff")
    .attr("stroke-width", (d) => Math.max(1, d.width))
    .attr("stroke-dasharray", "10 26");

  const node = gNodes.selectAll("g").data(graph.nodes).join("g");

  const rect = node.append("rect")
    .attr("class", "sankey-node")
    .attr("x", (d) => d.x0)
    .attr("y", (d) => d.y0)
    .attr("width", (d) => d.x1 - d.x0)
    .attr("height", (d) => Math.max(1, d.y1 - d.y0))
    .attr("fill", (d) => SANKEY_NODE_COLORS[d.category] || "#9aa0b3");

  const label = node.append("text")
    .attr("class", "sankey-label")
    .attr("x", (d) => (d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6))
    .attr("y", (d) => (d.y0 + d.y1) / 2)
    .attr("dy", "0.35em")
    .attr("text-anchor", (d) => (d.x0 < width / 2 ? "start" : "end"))
    .attr("font-size", TYPE.label.size)
    .attr("font-family", FONT_SANS)
    .attr("fill", "var(--ink)")
    .text((d) => d.name);

  function clearHighlight() {
    link.classed("is-traced", false).classed("is-dimmed", false);
    flow.classed("is-on", false);
    rect.classed("is-dimmed", false);
    label.classed("is-dimmed", false);
  }

  function highlight(litLinks, litNodes) {
    link.classed("is-traced", (d) => litLinks.has(d))
        .classed("is-dimmed", (d) => !litLinks.has(d));
    flow.classed("is-on", (d) => !reduceMotion && litLinks.has(d));
    rect.classed("is-dimmed", (d) => !litNodes.has(d));
    label.classed("is-dimmed", (d) => !litNodes.has(d));
  }

  /* The tooltip is centred over the cursor and sits above it
     (transform: translate(-50%, -120%)), so near an edge it used to hang off
     the card and get sliced by its overflow. The card no longer clips (see
     .sankey-card), and the position is clamped here so the box stays whole
     inside the plot even when the pointer is right at the boundary.
     offsetX/offsetY are deliberate: they are layout (logical) pixels, the
     same space as the left/top they are written into. clientX/clientY would
     be real pixels and would need dividing by --ui-scale. */
  const showTip = (event, html) => {
    tooltip.innerHTML = html;
    tooltip.classList.add("show");
    const card = tooltip.parentElement;
    const margin = 8;
    const halfW = tooltip.offsetWidth / 2;
    const cardW = card ? card.clientWidth : 0;
    let x = event.offsetX;
    if (cardW > tooltip.offsetWidth + margin * 2) {
      x = Math.max(halfW + margin, Math.min(cardW - halfW - margin, x));
    }
    // Flipped below the cursor when there is not room above for it, rather
    // than letting it run off the top of the plot.
    const needsAbove = tooltip.offsetHeight * 1.2 + margin;
    tooltip.classList.toggle("is-below", event.offsetY < needsAbove);
    tooltip.style.left = x + "px";
    tooltip.style.top = event.offsetY + "px";
  };

  link
    .on("mousemove", (event, d) => {
      const src = throughput(d.source);
      const share = src ? (d.value / src) * 100 : 0;
      showTip(event, "<b>" + d.source.name + " " + ARROW_SVG + " " + d.target.name + "</b><br>" +
        d.value.toFixed(2) + " Mtoe<br>" + share.toFixed(0) + "% of " + d.source.name);
    })
    .on("mouseenter", (event, d) => highlight(new Set([d]), new Set([d.source, d.target])))
    .on("mouseleave", () => { tooltip.classList.remove("show"); clearHighlight(); });

  rect
    .on("mousemove", (event, d) => {
      const ins = (d.targetLinks || []).length;
      const outs = (d.sourceLinks || []).length;
      showTip(event, "<b>" + d.name + "</b><br>" + throughput(d).toFixed(2) + " Mtoe<br>" +
        ins + " in · " + outs + " out — full route traced");
    })
    .on("mouseenter", (event, d) => { const t = trace(d); highlight(t.litLinks, t.litNodes); })
    .on("mouseleave", () => { tooltip.classList.remove("show"); clearHighlight(); });

  /* ---- Entry animation ----------------------------------------------------
     Links draw themselves in, staggered by how deep they sit in the diagram,
     so the picture builds along the direction the energy flows rather than
     appearing all at once. Standard dash-reveal: offset the path by its own
     length, then run that offset to zero.

     Driven by CSS animations, NOT d3 transitions, for two reasons:

     1. `.transition()` does not exist here. base.py loads d3-array, d3-path,
        d3-shape, d3-selection and d3-sankey — d3-transition is not among
        them, and it does not come bundled with any of those. A first pass at
        this used it and threw a TypeError on the first link, which left that
        link stranded with its reveal dash applied (i.e. INVISIBLE) and
        aborted the .each() before any other element was touched. Pulling
        d3-transition in would mean five more CDN scripts, since its own
        dependencies (d3-color/-dispatch/-ease/-interpolate/-timer) are not
        bundled either.
     2. A CSS animation with `forwards` cannot fail into a hidden link. The
        end state is declared, not applied by a callback, so no interrupted
        re-render, missed event or thrown handler can leave a flow invisible.
        That failure mode is a data-integrity bug in a diagram like this, not
        a cosmetic one, so it is worth designing out rather than guarding.

     Skipped wholesale under prefers-reduced-motion. */
  if (!reduceMotion) {
    const maxDepth = Math.max(1, ...graph.nodes.map((n) => n.depth || 0));
    const stagger = (d) => (((d.depth || 0) / maxDepth) * 260).toFixed(0) + "ms";
    link.each(function (d) {
      let len = 0;
      try { len = this.getTotalLength(); } catch (e) { len = 0; }
      if (!len) return;
      this.setAttribute("stroke-dasharray", len + " " + len);
      this.setAttribute("stroke-dashoffset", len);
      this.style.animationDelay = stagger(d.source);
      this.classList.add("sankey-reveal");
    });
    rect.each(function (d) { this.style.animationDelay = stagger(d); this.classList.add("sankey-fade-in"); });
    label.each(function (d) {
      this.style.animationDelay = (parseFloat(stagger(d)) + 140).toFixed(0) + "ms";
      this.classList.add("sankey-fade-in");
    });
  }
}

/* ---------- Fit the whole UI to the window ----------
   dashboard.css is px-based end to end — every chart height in it is a fixed
   number tuned against a ~1080p window — and `--ui-scale` (`zoom` on body) is
   the single knob that resizes the lot. Left at one static value, the
   interface renders at that same physical size on every monitor: on a large
   one the content stopped well short of the bottom of the window and left a
   band of dead page background under the footer — which is what the footer's
   old "best viewed in 1920 x 1080" note was really admitting to (that note is
   gone now that the UI fits itself to the window instead).

   So measure instead of assuming. The footer is .page's last child and .page
   is a flex column packed to the top, so the footer's own bottom edge IS the
   content's bottom edge (.page's min-height stretches the container, never
   the footer's position). Scale until that edge meets the bottom of the
   window and the dead band is gone by construction — at whatever size the
   window happens to be, rather than at one blessed resolution.

   Widths are deliberately left alone: every column in the layout is already
   fluid and fills what it's given, so only the vertical axis was ever short.

   getBoundingClientRect() is the right measurement here (not offsetTop /
   offsetHeight): it reports real, post-zoom pixels, the same coordinate space
   as documentElement.clientHeight, so the ratio between them is unit-agnostic
   and needs no correction for how `zoom` rescales the logical grid underneath
   (<html> itself is not zoomed — the zoom is on body). Reflowing at a new
   scale shifts the content height a little (text re-wraps against a different
   logical width), so this iterates to converge rather than trusting one pass.

   The target is documentElement.clientHeight, NOT window.innerHeight:
   innerHeight counts the space a horizontal scrollbar occupies, so fitting to
   it lands the content a scrollbar's width too tall, which raises a vertical
   scrollbar, which steals width, which raises a horizontal one — the two feed
   each other and the page ends up scrolling in both directions. clientHeight
   is the real content box, so the fit converges instead. */
const UI_SCALE_MIN = 0.7;
const UI_SCALE_MAX = 1.8;

function fitUiScale() {
  const footer = document.querySelector(".site-footer");
  if (!footer) return;
  // Energy Flows is the deliberate exception: #sankeySvg's own height is
  // already viewport-derived (a clamp() on 100vh), so its content grows to
  // fill the window on its own. Measuring it here would chase a target that
  // moves with the scale and just run the whole UI up to UI_SCALE_MAX.
  if (document.getElementById("view-energy-flows").classList.contains("active")) return;

  const root = document.documentElement;
  let scale = parseFloat(getComputedStyle(root).getPropertyValue("--ui-scale")) || 1;

  for (let pass = 0; pass < 6; pass++) {
    const bottom = footer.getBoundingClientRect().bottom;
    if (bottom <= 0) return;  // not laid out yet (hidden tab, pre-paint)
    // The 0.995 leaves the fitted content a hair inside the window: land it
    // exactly on the edge and rounding can hand us a scrollbar anyway.
    const ratio = (root.clientHeight * 0.995) / bottom;
    if (Math.abs(ratio - 1) < 0.004) break;
    const next = Math.min(UI_SCALE_MAX, Math.max(UI_SCALE_MIN, scale * ratio));
    if (next === scale) break;  // clamped — no point iterating further
    scale = next;
    root.style.setProperty("--ui-scale", String(scale));
  }

  // Re-drive the canvases (see resizeChartsToContainers) — never inline here,
  // where the `zoom` change has not been reflowed and the container still
  // measures at its old size. Three passes, because there are three moments
  // that can leave a canvas mis-sized: the frame after the change, whenever
  // Chart.js's own ResizeObserver answers the resize we just did, and later
  // still when a chart is first built from model data that has only just
  // arrived. Each pass is idempotent, so the cost of the extra ones is a
  // measurement.
  requestAnimationFrame(() => finishFit(scale));
  clearTimeout(fitUiScale._settle);
  clearTimeout(fitUiScale._settleLate);
  fitUiScale._settle = setTimeout(() => finishFit(scale), 150);
  fitUiScale._settleLate = setTimeout(() => finishFit(scale), 600);
}

/* Size the canvases, then check our work one frame later. Chart.js answers our
   resize with a ResizeObserver callback of its own, and that callback can
   re-apply its real-vs-logical mis-measurement on top of what we just set, so
   the second call is what makes the size that survives ours. Idempotent when
   nothing moved. */
function finishFit(scale) {
  resizeChartsToContainers();
  requestAnimationFrame(() => {
    resizeChartsToContainers();
    reportUiFit(scale);
  });
}

/* ---------- Chart sizing under --ui-scale ----------
   Every chart is created with `responsive: false` and sized from here instead,
   because Chart.js's own sizing is wrong whenever --ui-scale isn't 1: it reads
   the container in real (post-zoom) pixels and then writes that number as the
   canvas's CSS width, which is in logical ones. The error is exactly the scale
   factor — a 1727px-wide card got a 1554px canvas at 0.9 (1727 x 0.9).

   That went unnoticed for as long as the scale was fixed at 0.9, because a
   canvas that is too SMALL just leaves a margin inside its card. Above 1.0 the
   same error inverts: the canvas is wider than the card, and since .panel is
   min-width:0 it doesn't stretch the card, it paints over the chart next to it
   and drags the page's scrollWidth out past the window.

   Leaving `responsive: true` and merely correcting afterwards was not enough.
   Chart.js's ResizeObserver answers every size change — including ours — so it
   would re-apply its own mis-measurement on top of the correction, and which
   of the two landed last came down to timing (roughly one load in five went
   out overflowing). With its observer off there is no competing writer.

   The target is the wrapper's getBoundingClientRect() divided by the scale,
   not its clientWidth/clientHeight: both nominally give the logical size, but
   clientWidth read in the same turn as a `zoom` change can still answer from
   the pre-change layout — 1727 for a card that was really 1181, sizing the
   canvas 546px over its card. The rect stays correct across the change. */
function sizeChartToContainer(id) {
  const chart = charts[id];
  const canvas = document.getElementById(id);
  if (!chart || !canvas || typeof chart.resize !== "function") return;
  const wrap = canvas.parentElement;
  if (!wrap) return;
  const rect = wrap.getBoundingClientRect();
  if (!rect.width || !rect.height) return;  // hidden tab — nothing to size yet
  const scale = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--ui-scale")
  ) || 1;
  // A canvas's bitmap has to be sized in DEVICE pixels, and `zoom` is a
  // multiplier on top of devicePixelRatio that Chart.js cannot see: it asks
  // the platform for window.devicePixelRatio, gets 1 on an ordinary display,
  // and allocates a bitmap 1:1 with the canvas's logical width — which the
  // browser then stretches over (width x scale) real pixels. Below 1.0 that
  // downscales and looks fine (it is effectively supersampled), which is why
  // the old fixed 0.9 never showed it; above 1.0 it is a visibly soft chart.
  // Multiplying the ratio by the scale allocates the bitmap at the size the
  // chart is really painted at.
  if (chart.options) {
    chart.options.devicePixelRatio = (window.devicePixelRatio || 1) * scale;
  }
  chart.resize(rect.width / scale, rect.height / scale);
}

function resizeChartsToContainers() {
  Object.keys(charts).forEach(sizeChartToContainer);
}

/* Create a chart and give it its size in the same turn. With responsive:false
   Chart.js would otherwise keep the canvas's default 300x150 attribute size;
   sizing here, before anything paints, means there is no wrong first frame. */
function newSizedChart(id, ctx, config) {
  const chart = new Chart(ctx, config);
  charts[id] = chart;
  sizeChartToContainer(id);
  return chart;
}

/* Readable from devtools (or --dump-dom) as data-ui-fit on <html>: the scale
   that was settled on and the measurements behind it. scrollH/scrollW over
   clientH/clientW is the overflow check — equal means the page needs no
   scrollbar in that axis — and each canvas is reported against the card it
   has to stay inside. */
function reportUiFit(scale) {
  const root = document.documentElement;
  const footer = document.querySelector(".site-footer");
  let worst = 0;
  Object.keys(charts).forEach((id) => {
    const cv = document.getElementById(id);
    if (!cv || !cv.parentElement || !cv.parentElement.clientWidth) return;
    worst = Math.max(worst, cv.clientWidth - cv.parentElement.clientWidth);
  });
  root.dataset.uiFit = [
    "scale=" + scale.toFixed(3),
    "footerBottom=" + Math.round(footer.getBoundingClientRect().bottom),
    "clientH=" + root.clientHeight,
    "scrollH=" + root.scrollHeight,
    "clientW=" + root.clientWidth,
    "scrollW=" + root.scrollWidth,
    "chartOverflowPx=" + worst,
  ].join(" ");
}

/* Each tab carries its own chart height (.chart-wrap-duo vs -duo-lg vs -lg vs
   plain .chart-wrap), so the content's natural height — and therefore the
   scale that fits it — changes with the active tab, not just with the
   window. */
function refitViewport() {
  fitUiScale();
  if (sankeyDataByYear && document.getElementById("view-energy-flows").classList.contains("active")) {
    renderSankey(sankeyDataByYear[currentSankeyYear]);
  }
}

window.addEventListener("resize", refitViewport);

// Tabs and sub-tabs refit too, but without refitViewport's Sankey re-render:
// these listeners are registered after the switching ones above, so the view
// has already changed by the time they run, and the Energy Flows handler up
// there re-renders the Sankey itself. Switching TO Energy Flows leaves the
// scale alone (fitUiScale skips that view), and switching away from it leaves
// a hidden Sankey that its own handler redraws next time it is shown.
[".pill-tab:not(.disabled)", ".subtab:not(.disabled)"].forEach((sel) => {
  document.querySelectorAll(sel).forEach((el) => {
    el.addEventListener("click", fitUiScale);
  });
});

/* ---------- Initial load ---------- */
setScenario(1);

// Fit on first paint so the layout is right immediately, then again once the
// webfonts land, since a font swapping in changes the measured text height
// and with it the scale that fits. Both passes re-drive the chart sizes, so
// the second one correcting the first is expected, not a race.
requestAnimationFrame(refitViewport);
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(refitViewport);
}
