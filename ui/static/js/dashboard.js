const ids = window.APP_CONFIG.leverIds;
// Positional fallback for any series SERIES_COLOR doesn't name — same EU-Calc
// register as SERIES_COLOR itself, and ordered so consecutive positions are
// far apart in luminance (an unnamed series most often lands next to another
// unnamed one). These were left on the previous palette's hexes when
// SERIES_COLOR was restyled, which would have mixed two registers on any
// chart carrying a series the map doesn't list.
const COLORS = [
  "#A5E0A0", // green      (EUCALC)
  "#EC6E85", // rose       (EUCALC)
  "#9FC5EE", // blue       (EUCALC)
  "#F5A623", // orange     (EUCALC)
  "#8B7FD4", // violet     (EUCALC)
  "#F7E48F", // yellow
  "#5CB8AB", // teal
  "#A8E6EC", // cyan
  "#D5DAE0", // light grey
  "#3C3C3C", // near-black (EUCALC)
];

// The same category keeps the same colour on every chart and every tab, so a
// reader who learns "teal = transport" on All Energy carries that to
// Electricity and Emissions. Names are the series labels produced by
// outputs.py's DEMAND_SECTOR_GROUPS / SUPPLY_SOURCE_GROUPS etc. Anything not
// listed falls back to COLORS by position, so a new series still gets a
// palette colour rather than an off-palette one.
/* Series palette, in the EU-Calc register (the reference tool this project is
   modelled on) — its own sampled colours are the anchors, marked (EUCALC)
   below:

     #A5E0A0 green   #EC6E85 rose   #9FC5EE blue
     #8B7FD4 violet  #F5A623 orange #3C3C3C near-black

   Six colours can't dress 9+ stacked supply series, so the rest are
   extensions built in the same register (same lightness band, comparable
   saturation) rather than borrowed from elsewhere: a yellow, a teal, a cyan,
   a light violet and two greys.

   Assignment keeps the fuel conventions an energy reader expects, which the
   EU-Calc anchors mostly allow anyway: coal darkest, oil orange, gas red,
   nuclear violet, hydro blue, bio/other green, solar yellow, wind teal.

   The extension values are not eyeballed. EU-Calc's register is a tight
   lightness band, so a first pass at these clustered badly — five pairs of
   series that share a chart landed within 0.03 relative luminance of each
   other, i.e. indistinguishable in greyscale or to some colour-vision
   deficiencies, and worse than the palette this replaced. They were solved
   instead, by searching candidates for the arrangement that maximises the
   SMALLEST luminance gap between any two series drawn on the same chart:
   0.053, up from 0.023 in the old palette. The binding pair is now
   Agriculture/Natural gas (rose) against Telecom/Nuclear (violet) — both
   EU-Calc anchors, so that is the floor without abandoning them. Hue and the
   per-series marker shapes (SERIES_SHAPE) carry the rest of the distinction.

   ONE deliberate departure from EU-Calc's own assignment: they paint
   Transport near-black, but Transport is a thin sliver in their chart and the
   single largest band in our Energy Demand chart — a near-black block over a
   third of the plot reads as a hole in it. Transport takes the teal
   extension; near-black goes to Coal, where a heavy band is both
   conventional and semantically right. */
const SERIES_COLOR = {
  // demand sectors
  "Buildings": "#9FC5EE",                 // (EUCALC) their "Indirect" blue
  "Residential Buildings": "#9FC5EE",
  "Commercial Buildings": "#C4DCF5",
  "Industry": "#A5E0A0",                  // (EUCALC) their "Industry" green
  "Heavy Industry": "#A5E0A0",
  "Transport": "#5CB8AB",                 // extension: teal — see note above
  "Passenger Transport": "#5CB8AB",
  "Freight Transport": "#8ED2C7",
  "Telecom, Cooking & Transport": "#5CB8AB",
  "Agriculture": "#EC6E85",               // (EUCALC) their "Other" rose
  "Telecom": "#8B7FD4",                   // (EUCALC) their "Energy" violet
  "Cooking": "#F5A623",                   // (EUCALC) their "Electronics" orange
  "Miscellaneous": "#D5DAE0",             // extension: grey
  "Non-energy use": "#E6E9EC",            // extension: lighter grey
  // supply sources
  "Solar": "#F7E48F",                     // extension: yellow (EU-Calc has none)
  "Solar PV": "#F7E48F",
  "Wind": "#5CB8AB",                      // extension: teal
  "Hydro": "#9FC5EE",                     // (EUCALC) blue
  "Small Hydro": "#C4DCF5",
  "Nuclear": "#8B7FD4",                   // (EUCALC) violet
  "Others": "#A5E0A0",                    // (EUCALC) green
  "Bioenergy": "#A5E0A0",
  "Biomass": "#A5E0A0",
  "Coal": "#3C3C3C",                      // (EUCALC) near-black — heaviest band
  "Oil and petroleum products": "#F5A623",// (EUCALC) orange
  "Oil": "#F5A623",
  "Natural gas": "#EC6E85",               // (EUCALC) rose
  "Gas": "#EC6E85",
  "Electricity Import": "#A8E6EC",        // extension: cyan
  "Electricity Imports": "#A8E6EC",
  "Electricity trade": "#A8E6EC",
  "Electricity": "#A79BE0",               // extension: light violet
  "CCS": "#D5DAE0",
  // aggregate line
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

// Marker shape follows the same semantic-name-first, index-fallback pattern as
// colorForSeries(), so a series reads as the same shape on every chart and every
// tab it appears on, not just the same color — a second, colorblind-safe channel
// for telling bands apart, per the reference chart's own use of distinct glyphs.
const SHAPES = ["circle", "triangle", "rect", "rectRot", "star", "crossRot"];
const SERIES_SHAPE = {
  "Buildings": "triangle", "Residential Buildings": "triangle", "Commercial Buildings": "rectRot",
  "Industry": "rect", "Heavy Industry": "rect",
  "Transport": "circle", "Passenger Transport": "circle", "Freight Transport": "star",
  "Telecom, Cooking & Transport": "circle",
  "Agriculture": "rectRot", "Telecom": "star", "Cooking": "crossRot",
  "Miscellaneous": "crossRot", "Non-energy use": "crossRot",
  "Solar": "rect", "Solar PV": "rect", "Wind": "circle",
  "Hydro": "triangle", "Small Hydro": "triangle",
  "Nuclear": "star", "Others": "triangle", "Bioenergy": "triangle", "Biomass": "triangle",
  "Coal": "crossRot", "Oil and petroleum products": "rectRot", "Oil": "rectRot",
  "Natural gas": "rectRot", "Gas": "rectRot",
  "Electricity Import": "star", "Electricity Imports": "star", "Electricity trade": "star",
  "Electricity": "circle", "CCS": "crossRot",
};
function shapeForSeries(name, i) { return SERIES_SHAPE[name] || SHAPES[i % SHAPES.length]; }

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
  Chart.defaults.font.family = "'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif";
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
      // Carried for the legend swatch and the in-band label, which both need
      // the flat colour rather than the gradient function.
      bandColor: color,
      pointStyle: shapeForSeries(name, i),
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
// Shared axis look for every chart: hairline horizontal rules, no vertical
// grid and no axis line, matching the reference chart. yAxis()/xAxis() are
// used by the bar and single-line renderers; renderStackedChart spells the
// same thing out inline because it also sets stacking and min.
function axisCommon(titleText) {
  return {
    title: { display: true, text: titleText, color: AXIS_TEXT, font: { size: 10.5 } },
    ticks: { color: AXIS_TEXT, font: { size: 10.5 } },
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
    ctx.font = "600 11px 'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif";
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

// Draws one of SHAPES at (x, y) — a small self-contained renderer rather than
// reaching into Chart.js's internal point-drawing helpers, so it can't drift if
// the CDN build changes. Mirrors the legend's own pointStyle for the same series
// (see shapeForSeries()), so the marker on the crosshair always matches the glyph
// the reader already learned from the legend.
function drawMarker(ctx, shape, x, y, color, size) {
  const s = size || 4.5;
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.beginPath();
  switch (shape) {
    case "triangle":
      ctx.moveTo(x, y - s); ctx.lineTo(x + s, y + s * 0.8); ctx.lineTo(x - s, y + s * 0.8);
      ctx.closePath(); ctx.fill();
      break;
    case "rect":
      ctx.fillRect(x - s * 0.8, y - s * 0.8, s * 1.6, s * 1.6);
      break;
    case "rectRot":
      ctx.save(); ctx.translate(x, y); ctx.rotate(Math.PI / 4);
      ctx.fillRect(-s * 0.75, -s * 0.75, s * 1.5, s * 1.5);
      ctx.restore();
      break;
    case "star": {
      const spikes = 5, outer = s * 1.15, inner = s * 0.5;
      let rot = -Math.PI / 2;
      ctx.moveTo(x + Math.cos(rot) * outer, y + Math.sin(rot) * outer);
      for (let i = 0; i < spikes; i++) {
        rot += Math.PI / spikes;
        ctx.lineTo(x + Math.cos(rot) * inner, y + Math.sin(rot) * inner);
        rot += Math.PI / spikes;
        ctx.lineTo(x + Math.cos(rot) * outer, y + Math.sin(rot) * outer);
      }
      ctx.closePath(); ctx.fill();
      break;
    }
    case "crossRot":
      ctx.lineWidth = 2;
      ctx.moveTo(x - s, y - s); ctx.lineTo(x + s, y + s);
      ctx.moveTo(x + s, y - s); ctx.lineTo(x - s, y + s);
      ctx.stroke();
      break;
    default: // circle
      ctx.arc(x, y, s * 0.85, 0, Math.PI * 2); ctx.fill();
  }
}

// Reference-style hover interaction for every stacked-area chart: a vertical
// crosshair at the hovered index, plus one small callout box per series
// positioned at that series' true stacked value — not one combined tooltip
// block, which reads poorly once a chart has 8-10 series. Chart.js's built-in
// tooltip box is turned off (tooltip.enabled:false in renderStackedChart) and
// replaced entirely by this plugin's afterDraw; tooltip.external below is only
// used to capture the live hover state (dataPoints + opacity), the documented
// mechanism for a fully custom tooltip — nothing is drawn inside it.
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

    ctx.save();
    // No full-height crosshair line — each card already has its own leader
    // line pointing at its true position, so a dashed line running behind
    // the whole cluster was redundant clutter rather than useful signal.

    // Year tag, echoing the reference's boxed year label. Drawn just inside
    // the plot area's bottom edge rather than below the axis, so it never
    // competes with the tick/title row for the fixed chart-wrap height. Drawn
    // last (see below), on top of the box cluster, and the cluster's own
    // bottom bound is pulled up by tagH so it doesn't want to sit there anyway.
    const year = String(chart.data.labels[dataIndex]);
    ctx.font = "600 10px 'IBM Plex Mono', ui-monospace, Consolas, monospace";
    const tagW = ctx.measureText(year).width + 12, tagH = 15;
    const tagX = Math.min(Math.max(x - tagW / 2, chartArea.left), chartArea.right - tagW);
    const tagY = chartArea.bottom - tagH - 3;

    // One entry per visible series, formatted the same way the old tooltip
    // callbacks did (opts here is renderStackedChart's own opts, stashed on
    // the plugin options below).
    const fmt = (v) => (opts.compact ? formatCompact(v) : (v == null ? "0" : v.toFixed(2)));
    const entries = tt.dataPoints
      .filter((dp) => dp.parsed && dp.parsed.y != null)
      .map((dp) => ({
        label: dp.dataset.label,
        text: `${dp.dataset.label}: ${fmt(dp.parsed.y)}`,
        color: dp.dataset.bandColor || dp.dataset.borderColor,
        shape: dp.dataset.pointStyle,
        trueY: dp.element.y, // the real data position — the marker always stays here
        y: dp.element.y,     // the box's position — this is what the declutter pass below moves
        isTotal: dp.dataset.label === "Total",
      }));
    if (!entries.length) { ctx.restore(); return; }

    ctx.font = "600 11.5px 'IBM Plex Sans', -apple-system, 'Segoe UI', Arial, sans-serif";
    let boxH = 24, gap = 4;
    const padX = 10, markerGutter = 17;
    const laid = entries
      .map((e) => ({ ...e, boxW: ctx.measureText(e.text).width + padX * 2 + markerGutter }))
      .sort((a, b) => a.y - b.y);
    // Reserve the year tag's own zone at the bottom, then, if the cluster
    // can't fit N boxes at the default size in what's left (e.g. Energy
    // Supply's 10 series in a compact chart), shrink box height/gap just
    // enough that it does — better than fighting an unwinnable overlap
    // battle between the tag and the bottom-most box.
    const usableTop = chartArea.top, usableBottom = tagY - gap;
    const neededSpan = (laid.length - 1) * (boxH + gap) + boxH;
    const availSpan = usableBottom - usableTop;
    if (laid.length > 1 && neededSpan > availSpan && availSpan > 0) {
      const scale = availSpan / neededSpan;
      boxH = Math.max(14, boxH * scale);
      gap = Math.max(2, gap * scale);
    }
    // Minimum-gap declutter pass, then anchor the whole cluster to the
    // reserved bottom zone, working back up — trueY is never touched by any
    // of this, so a displaced box can still be traced to its real value via
    // the leader line drawn below.
    for (let i = 1; i < laid.length; i++) {
      const minY = laid[i - 1].y + boxH + gap;
      if (laid[i].y < minY) laid[i].y = minY;
    }
    let floor = usableBottom;
    for (let i = laid.length - 1; i >= 0; i--) {
      if (laid[i].y + boxH / 2 > floor) laid[i].y = floor - boxH / 2;
      floor = laid[i].y - boxH / 2 - gap;
    }

    const openRight = x < chartArea.left + (chartArea.right - chartArea.left) / 2;
    // Leader lines first, so the boxes painted afterward sit cleanly on top of
    // their own line rather than the line crossing over a neighboring box.
    laid.forEach((e) => {
      if (Math.abs(e.y - e.trueY) < 2) return;
      const boxX = openRight
        ? Math.min(x + 10, chartArea.right - e.boxW)
        : Math.max(x - 10 - e.boxW, chartArea.left);
      const nearEdgeX = openRight ? boxX : boxX + e.boxW;
      ctx.beginPath();
      ctx.strokeStyle = e.color; ctx.lineWidth = 1;
      ctx.moveTo(x, e.trueY);
      ctx.lineTo(nearEdgeX, e.y);
      ctx.stroke();
    });
    laid.forEach((e) => {
      const boxX = openRight
        ? Math.min(x + 10, chartArea.right - e.boxW)
        : Math.max(x - 10 - e.boxW, chartArea.left);
      const boxY = e.y - boxH / 2;
      if (e.isTotal) {
        roundRect(ctx, boxX, boxY, e.boxW, boxH, 6);
        ctx.fillStyle = "#fff"; ctx.fill();
        ctx.lineWidth = 1.5; ctx.strokeStyle = e.color; ctx.stroke();
      } else {
        roundRect(ctx, boxX, boxY, e.boxW, boxH, 6);
        ctx.fillStyle = e.color; ctx.fill();
      }
      // The marker always renders at trueY (the real data point), on the
      // crosshair line itself — never at the box's possibly-decluttered y.
      // drawMarker() leaves ctx.fillStyle set to the marker's own color, so
      // the text color has to be (re)applied after it, not before.
      drawMarker(ctx, e.shape, x, e.trueY, e.color, 5.5);
      ctx.fillStyle = e.isTotal ? e.color : textOnColor(e.color);
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.fillText(e.text, boxX + markerGutter, boxY + boxH / 2 + 0.5);
    });

    // Year tag drawn last so it always sits on top of the box cluster.
    roundRect(ctx, tagX, tagY, tagW, tagH, 4);
    ctx.fillStyle = "#1b1d29"; ctx.fill();
    ctx.fillStyle = "#fff"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(year, tagX + tagW / 2, tagY + tagH / 2 + 0.5);

    // Exposed for tests: the plugin's own computed layout, rather than reaching
    // into canvas pixels to verify hover behavior.
    chart._crosshairLayout = { x, dataIndex, boxes: laid };
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
    // Round dot markers and no boxes, per the reference legend; the Total
     // dataset overrides pointStyle to "line" so the aggregate reads as a line.
    const legend = {
      position: opts.legendPosition || "bottom",
      labels: {
        boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyleWidth: 10,
        font: { size: 10.5 }, color: "#000000", padding: 12,
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
          crosshairTooltip: { display: true, compact: !!opts.compact },
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
            title: { display: true, text: unit, color: "#000000", font: { size: 10.5 } },
            ticks: { ...yTicks, color: "#000000", font: { size: 10.5 } },
            // Hairline horizontal rules only — the reference has no axis line
            // and no vertical grid, so the bands carry the shape.
            grid: { color: "#EDEDE8", drawTicks: false, drawBorder: false },
            border: { display: false },
          },
          x: {
            title: { display: true, text: "Year", color: "#000000", font: { size: 10.5 } },
            ticks: { color: "#000000", font: { size: 10.5 } },
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
  const datasets = names.map((name, i) => ({
    label: name, data: chartData.series[name], backgroundColor: colorForSeries(name, i),
    pointStyle: "circle", stack: "s", borderRadius: 2,
  }));
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
          legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } },
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
      ctx.font = "600 10px 'IBM Plex Mono', ui-monospace, Consolas, monospace";
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
    else setStatus("live · " + new Date().toLocaleTimeString(), "");
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

document.querySelectorAll(".cdh-pathway-btn").forEach((btn) => {
  btn.addEventListener("click", () => setScenario(btn.dataset.level));
});

// Sets one lever's hidden-input value — the single source of truth read
// by recalc()/setScenario(). The visible control is the sub-sector's
// shared draggable lever (updateLeverRow), not a per-lever widget, so
// there's no per-lever DOM to refresh here.
function setLeverLevel(id, level) {
  const hidden = document.getElementById(id);
  const max = parseInt(hidden.dataset.max, 10);
  hidden.value = Math.min(level, max);
}

// Mirrors the mockup's activePath check: if every lever sits at the same
// level, name that level's pathway (and highlight that level's top-right
// button); otherwise it's a custom mix and no button is highlighted.
const PATHWAY_NAMES = { 1: "Least Effort", 2: "Determined Effort", 3: "Aggressive Effort", 4: "Heroic Effort" };
function updatePathwayName() {
  const values = ids.map((id) => parseInt(document.getElementById(id).value, 10));
  const first = values[0];
  const allSame = values.every((v) => v === first);
  const named = allSame && PATHWAY_NAMES[first];
  document.getElementById("pathway-name").textContent = named ? PATHWAY_NAMES[first] : "Custom pathway";
  // The indicator dot carries the effort level, so the chip beside the tabs
  // shows how ambitious the loaded pathway is without reading the text.
  const chip = document.querySelector(".pathway-chip");
  if (chip) chip.dataset.level = named ? String(first) : "custom";
  document.querySelectorAll(".cdh-pathway-btn").forEach((btn) => {
    btn.classList.toggle("active", allSame && parseInt(btn.dataset.level, 10) === first);
  });
}

// Recomputes each group box's "avg N.N" badge from its own levers'
// current values — purely a display of the underlying real Control-sheet
// rows, independent of the flattened sub-sector rows shown in the UI.
function updateGroupAvg(box) {
  const leverIds = (box.dataset.leverIds || "").split(",").filter(Boolean);
  const avgEl = box.querySelector(".lg-box-avg");
  if (!leverIds.length || !avgEl) return;
  const values = leverIds.map((id) => parseInt(document.getElementById(id).value, 10));
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  avgEl.textContent = "avg " + avg.toFixed(1);
}

function updateAllGroupAvgs() {
  document.querySelectorAll(".lg-box[data-lever-ids]").forEach(updateGroupAvg);
}

// Paints one lever's fill/thumb from its CURRENT numeric value (1-based
// index into data-fills, the same LEVEL_FILL ramp sidebar.py renders the
// track with) — shared by drag (initLevers' own input handler) and by every
// external sync below (recalc, pathway button, flyout edit on a bundled row).
function paintLever(lever, value, max) {
  const fills = lever.dataset.fills.split(",");
  const color = fills[Math.min(value - 1, fills.length - 1)];
  const pct = max > 1 ? ((value - 1) / (max - 1)) * 100 : 0;
  // Sets the one CSS custom property the track/fill/thumb/glow all read
  // (--lg-lever-color in dashboard.css) rather than painting each element's
  // background directly, so the thumb's radial-gradient + glow ring stay
  // intact instead of being flattened to a solid color on every drag.
  lever.style.setProperty("--lg-lever-color", color);
  lever.querySelector(".lg-lever-fill").style.width = pct + "%";
  lever.querySelector(".lg-lever-thumb").style.left = pct + "%";
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
  paintLever(lever, shown, max);
}

function updateAllSubcatQuickButtons() {
  document.querySelectorAll(".lg-subcat-row").forEach(updateLeverRow);
}

// Shared by the KPI cards and the change-strip's default (no-change)
// sentence, so the two can never quietly disagree about how "clean share"
// or "emissions in GtCO2" is derived.
function cleanSharePct(data) {
  return data.total_supply ? Math.round((data.renewables + data.nuclear) / data.total_supply * 100) : 0;
}
function emissionsGt(data) {
  // emissions_2047_total is 'IESS V3 Results'!J116 (Million tonne CO2e) — the
  // workbook's own total row, equal to emissions_by_sector_chart.total's last entry on
  // every golden-master vector. Reading it directly means the landing tab no longer
  // builds a 102-cell chart (~1.1s) just to reach this one number. /1000 -> GtCO2.
  return typeof data.emissions_2047_total === "number" ? data.emissions_2047_total / 1000 : null;
}

function renderOverviewKpis(data) {
  const gt = emissionsGt(data);
  const demandEl = document.getElementById("stat-demand-value");
  if (!demandEl) return; // not every tab has the KPI row (All Energy only)
  demandEl.textContent = data.total_demand.toLocaleString() + " Mtoe";
  document.getElementById("stat-demand-note").textContent = data.kpis.per_capita_demand.toLocaleString() + " MJ/person";
  document.getElementById("stat-clean-value").textContent = cleanSharePct(data) + "%";
  document.getElementById("stat-imports-value").textContent = data.kpis.import_dependence + "%";
  document.getElementById("stat-emissions-value").textContent = gt != null ? gt.toFixed(1) + " GtCO₂" : "–";
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
  emissions_2047_total: { label: "Emissions (2047)", unit: "GtCO₂", scale: 1 / 1000 },
};
function fmtKpi(key, value) {
  const meta = KPI_LABELS[key];
  const v = value * meta.scale;
  const num = v.toLocaleString(undefined, { maximumFractionDigits: Math.abs(v) >= 100 ? 0 : 1 });
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
function addInsightsLine(body, arrow, segments) {
  const row = document.createElement("div");
  row.className = "insights-line";
  if (arrow) {
    const badge = document.createElement("span");
    badge.className = "insights-arrow " + (arrow === "▲" ? "insights-arrow-up" : "insights-arrow-down");
    badge.textContent = arrow;
    badge.setAttribute("aria-hidden", "true");
    row.appendChild(badge);
  }
  const text = document.createElement("span");
  segments.forEach((seg) => {
    if (typeof seg === "string") {
      text.appendChild(document.createTextNode(seg));
    } else {
      const strong = document.createElement("strong");
      strong.textContent = seg.strong;
      text.appendChild(strong);
    }
  });
  row.appendChild(text);
  body.appendChild(row);
}

// A small caps label + rule ("line of segregation") ahead of each group of
// insight lines, so "what changed" and "what it did to the numbers" read as
// two distinct groups rather than one undifferentiated list.
function addInsightsGroupLabel(body, label) {
  const h = document.createElement("div");
  h.className = "insights-group-label";
  h.textContent = label;
  body.appendChild(h);
}

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
  value.textContent = gt.toFixed(1) + " GtCO₂";
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

function renderInsights(data) {
  const body = document.getElementById("insights-panel-body");
  body.innerHTML = "";

  const leverChanges = data.lever_changes || [];
  const kpiChanges = data.kpi_deltas || {};

  if (!leverChanges.length) {
    // No "Base state" chip: which levers are where is already legible in the
    // Custom Pathways deck itself, so labelling the idle message added a
    // heading over a single sentence and nothing else. The changed-state
    // groups below ("Levers changed" / "Impact on results") keep theirs —
    // those genuinely separate two lists.
    addInsightsLine(body, null, ["This is the base pathway — nothing has been changed yet. Adjust a lever in Custom Pathways below to see its impact."]);
    return;
  }

  const raised = leverChanges.filter((c) => c.to > c.from).map((c) => c.name);
  const lowered = leverChanges.filter((c) => c.to < c.from).map((c) => c.name);
  if (raised.length || lowered.length) {
    addInsightsGroupLabel(body, "Levers changed");
    if (raised.length) addInsightsLine(body, "▲", ["Raised effort on ", { strong: raised.join(", ") }, "."]);
    if (lowered.length) addInsightsLine(body, "▼", ["Lowered effort on ", { strong: lowered.join(", ") }, "."]);
  }

  const kpiEntries = Object.entries(kpiChanges).filter(([key]) => KPI_LABELS[key]);
  if (kpiEntries.length) {
    addInsightsGroupLabel(body, "Impact on results");
    kpiEntries.forEach(([key, d]) => {
      const meta = KPI_LABELS[key];
      const dir = d.delta > 0 ? "increased" : "decreased";
      const pct = d.pct != null ? ` (${Math.abs(d.pct)}%)` : "";
      addInsightsLine(body, d.delta > 0 ? "▲" : "▼",
        [`${meta.label} ${dir}${pct} to `, { strong: fmtKpi(key, d.to) }, "."]);
    });
  }
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
  updateAllGroupAvgs();
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
    renderStackedChart("emissionsBySectorChart", data.emissions_by_sector_chart, null, { unit: "Million tonne CO2e", legendPosition: "right" });
  }
  if (data.per_capita_emissions_chart) {
    renderBarChart("perCapitaEmissionsChart", data.per_capita_emissions_chart, { unit: "tonne CO2e per person", color: "#8B7FD4" });
    renderBarChart("indPerCapitaEmissionsChart", data.per_capita_emissions_chart, { unit: "tonne CO2e/person", color: "#8B7FD4" });
  }
  if (data.emissions_intensity_chart) {
    renderBarChart("indEmissionsIntensityChart", data.emissions_intensity_chart, { unit: "kg CO2e / 1000 INR", color: "#8B7FD4" });
  }
  if (data.energy_intensity_chart) {
    renderBarChart("indEnergyIntensityChart", data.energy_intensity_chart, { unit: "MJ/INR", color: "#F7E48F" });
  }
  if (data.per_capita_supply_chart) {
    renderBarChart("perCapitaSupplyChart", data.per_capita_supply_chart, { unit: "toe/person", color: "#5CB8AB" });
  }
  if (data.capacity_chart) {
    renderStackedChart("capacityChart", data.capacity_chart, null, { unit: "GW", legendPosition: "right" });
  }
  if (data.demand_electrification_chart) {
    renderBarChart("demandElectrificationChart", data.demand_electrification_chart, { unit: "%", color: "#8B7FD4" });
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
}

/* ---------- Tab switching ---------- */
document.querySelectorAll(".pill-tab[data-view]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".pill-tab[data-view]").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.getElementById("view-" + tab.dataset.view).classList.add("active");
    // The Pathway Impact/Insights rail is hidden on Energy Flows only, so
    // the Sankey — the one view that actually wants the extra width — gets
    // the room instead. Grid columns aren't like flex siblings: hiding the
    // rail item alone would leave its 280px column reserved but empty, so
    // .rail-hidden also collapses .page-grid down to a single column.
    const isEnergyFlows = tab.dataset.view === "energy-flows";
    document.getElementById("pathway-rail").hidden = isEnergyFlows;
    document.querySelector(".page-grid").classList.toggle("rail-hidden", isEnergyFlows);
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
    updateAllGroupAvgs();
    document.querySelectorAll(".cdh-pathway-btn").forEach((b) => b.classList.remove("active"));
    scheduleRecalc();
  });
  input.addEventListener("pointerdown", () => lever.classList.add("is-dragging"));
  window.addEventListener("pointerup", () => lever.classList.remove("is-dragging"));
});

/* ---------- Lever tooltip: hovering/focusing a lever that carries
   data-descs (sidebar.py only sets these for single-lever rows — see its
   own comment) shows its CURRENT value's own Control-sheet ambition note,
   re-reading data-descs on every drag so the tooltip tracks the thumb
   instead of freezing on whatever level was under the pointer at hover
   start. One shared floating box repositioned per lever, same
   position:fixed + measured-rect technique the Sankey's own tooltip
   uses, rather than one tooltip element per lever. ---------- */
(function initLeverTooltip() {
  const tip = document.createElement("div");
  tip.className = "lever-tooltip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  let shown = null;

  function render(lever) {
    if (!lever.dataset.descs) return false;
    const input = lever.querySelector(".lg-lever-input");
    const descs = JSON.parse(lever.dataset.descs);
    const desc = descs[input.value];
    if (!desc) { tip.hidden = true; return false; }
    tip.innerHTML = "";
    const strong = document.createElement("strong");
    strong.textContent = `Ambition level ${input.value}: `;
    tip.appendChild(strong);
    tip.appendChild(document.createTextNode(desc));
    tip.hidden = false;

    const r = lever.getBoundingClientRect();
    const tipW = tip.offsetWidth;
    let left = r.left + r.width / 2 - tipW / 2;
    left = Math.max(10, Math.min(left, window.innerWidth - tipW - 10));
    const top = Math.max(10, r.top - tip.offsetHeight - 10);
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(top) + "px";
    return true;
  }
  function show(lever) { shown = render(lever) ? lever : null; }
  function hide() { tip.hidden = true; shown = null; }

  document.addEventListener("mouseover", (e) => {
    const lever = e.target.closest(".lg-lever[data-descs]");
    if (lever) show(lever);
  });
  document.addEventListener("mouseout", (e) => {
    const lever = e.target.closest(".lg-lever[data-descs]");
    if (lever && !lever.contains(e.relatedTarget)) hide();
  });
  document.addEventListener("focusin", (e) => {
    const lever = e.target.closest(".lg-lever[data-descs]");
    if (lever) show(lever);
  });
  document.addEventListener("focusout", (e) => {
    if (e.target.closest(".lg-lever[data-descs]")) hide();
  });
  // Dragging fires `input` on the same lever repeatedly — re-render the
  // still-open tooltip so its text/position track the thumb live.
  document.addEventListener("input", (e) => {
    if (shown && e.target.closest(".lg-lever") === shown) render(shown);
  });
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
    renderStackedChart("emissionsBySectorChart", data.emissions_by_sector_chart, null, { unit: "Million tonne CO2e", legendPosition: "right" });
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
    .attr("font-size", 11)
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
      showTip(event, "<b>" + d.source.name + " → " + d.target.name + "</b><br>" +
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
