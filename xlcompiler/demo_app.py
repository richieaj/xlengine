"""
demo_app.py — local web UI to prove the IESS2047 compiler recalculates live
when ANY of the workbook's real "Custom Pathway" levers move, with no Excel
and no precomputed JSON.

Every slider release calls eng.set_lever(...) and re-evaluates the workbook
live through ModelEngine/Evaluator — the same engine used by count_flows.py
and run_full.py. The lever list is read directly from the Control sheet
(name, current value, level limit), not hardcoded — whatever levers exist in
the workbook show up here.

Run:
    python demo_app.py
Then open http://127.0.0.1:5000/
"""
import sys
sys.path.insert(0, ".")
from flask import Flask, jsonify, request

from compiler.engine import ModelEngine

PATH = "../workbook/IESS2047_Version_3.0.xlsx"

app = Flask(__name__)

print("Loading model (one-time)...", flush=True)
eng = ModelEngine.load(PATH, verbose=False)

# Put the workbook into "Custom Pathway, lever-driven" mode. Without these
# two switches the Control sheet sliders have no effect (the workbook would
# be using a preset scenario or direct numeric drivers instead).
eng.set_lever("Target Year Input", "E10", 1)   # 1: Pre-defined trajectories (lever-driven)
eng.set_lever("IESS V3 Main Sheet", "E12", 0)  # 0: None (Custom Pathway, not a preset)

# ── Build the full lever list straight from the Control sheet ───────────────
# Column D = lever name, column E = current "YOUR CHOICE" value, column F = LIMIT.
# Rows with no value in column E are section headers in the sheet, not levers.
CATEGORY_RANGES = [
    ("Economics",                    range(31, 32)),
    ("Costs",                        range(59, 63)),
    ("Demand — Transport",           range(33, 40)),
    ("Demand — Buildings",           range(40, 46)),
    ("Demand — Industry",            range(46, 50)),
    ("Demand — Cooking",             range(50, 52)),
    ("Demand — Agriculture & Telecom", range(52, 56)),
    ("Supply — Conventional Energy", list(range(5, 8)) + list(range(9, 11))),
    ("Supply — Renewable & Clean Energy", range(11, 19)),
    ("Supply — Bioenergy",           range(21, 26)),
    ("Supply — Fossil Fuel Production", range(27, 30)),
    ("Supply — T&D / Trade / Storage", [19, 57, 58]),
]


def _load_levers():
    names, limits, vals = {}, {}, {}
    for (sheet, r, c), cell in eng.m.cells.items():
        if sheet != "Control":
            continue
        if c == 4 and isinstance(cell.value, str) and cell.value.strip():
            names[r] = cell.value.strip()
        if c == 6 and isinstance(cell.value, (int, float)):
            limits[r] = int(cell.value)
        if c == 5 and isinstance(cell.value, (int, float)):
            vals[r] = int(cell.value)

    categories = []
    seen_rows = set()
    for cat_name, rows in CATEGORY_RANGES:
        items = []
        for r in rows:
            if r in vals and r in names:
                items.append({
                    "row": r,
                    "id": f"lv{r}",
                    "name": names[r],
                    "value": vals[r],
                    "max": limits.get(r, 4),
                })
                seen_rows.add(r)
        if items:
            categories.append({"category": cat_name, "levers": items})

    # Anything with a real value that wasn't placed in a category — surface
    # it anyway so "whatever levers exist" are always all present.
    leftovers = [
        {"row": r, "id": f"lv{r}", "name": names[r], "value": vals[r], "max": limits.get(r, 4)}
        for r in sorted(vals)
        if r in names and r not in seen_rows
    ]
    if leftovers:
        categories.append({"category": "Other", "levers": leftovers})
    return categories


LEVER_CATEGORIES = _load_levers()
ALL_LEVER_ROWS = {item["id"]: item["row"] for cat in LEVER_CATEGORIES for item in cat["levers"]}

# ── Output classification (2047 = index 6 of the 8-year value list) ────────
YEAR_IDX = 6

PRIMARY_SOURCES = {
    "Coal Production", "Coal Imports", "Oil Production", "Oil Imports",
    "Gas Production", "Gas Imports", "Municipal Waste", "Solar", "Wind",
    "Small Hydro", "Hydro", "Nuclear", "Electricity Imports",
    "Agricultural Waste/ Energy Crops", "Agricultural Waste/Energy Crops",
}
FINAL_DEMAND_SECTORS = {
    "Passenger Transport", "Freight Transport", "Industry", "Cooking",
    "Residential Buildings", "Commercial Buildings", "Agriculture",
    "Telecom", "Miscellaneous", "Non-energy use", "Refineries",
}
DOMESTIC_PRODUCTION_ROWS = {"Coal Production", "Oil Production", "Gas Production"}
IMPORT_ROWS = {"Coal Imports", "Oil Imports", "Gas Imports"}
RENEWABLE_SOURCES = {"Solar", "Wind", "Small Hydro", "Hydro", "Municipal Waste",
                      "Agricultural Waste/ Energy Crops", "Agricultural Waste/Energy Crops"}

# Demand-side sector grouping (matches the reference "Energy Demand" stacked
# chart: Buildings, Industry, Transport, Agriculture, Telecom, Cooking,
# Miscellaneous). Computed across every year column, not just 2047.
DEMAND_SECTOR_GROUPS = [
    ("Buildings",     {"Residential Buildings", "Commercial Buildings"}),
    ("Industry",      {"Industry"}),
    ("Transport",     {"Passenger Transport", "Freight Transport"}),
    ("Agriculture",   {"Agriculture"}),
    ("Telecom",       {"Telecom"}),
    ("Cooking",       {"Cooking"}),
    ("Miscellaneous", {"Miscellaneous", "Non-energy use", "Refineries"}),
]
CHART_YEAR_LABELS = ["2022", "2027", "2032", "2037", "2042", "2047"]
CHART_YEAR_IDXS = [1, 2, 3, 4, 5, 6]  # indices into the 8-value Base..Target list


def compute_outputs():
    edges = eng.read_flows()
    val = {e["row"]: (e["values"][YEAR_IDX] if len(e["values"]) > YEAR_IDX else 0.0) for e in edges}

    total_supply = sum(val[e["row"]] for e in edges if e["from"] in PRIMARY_SOURCES)
    total_demand = sum(val[e["row"]] for e in edges if e["to"] in FINAL_DEMAND_SECTORS)
    domestic_production = sum(val[e["row"]] for e in edges if e["from"] in DOMESTIC_PRODUCTION_ROWS)
    imports = sum(val[e["row"]] for e in edges if e["from"] in IMPORT_ROWS)
    renewables = sum(val[e["row"]] for e in edges if e["from"] in RENEWABLE_SOURCES)
    nuclear = sum(val[e["row"]] for e in edges if e["from"] == "Nuclear")

    return {
        "total_supply": round(total_supply, 2),
        "total_demand": round(total_demand, 2),
        "balance": round(total_supply - total_demand, 2),
        "domestic_production": round(domestic_production, 2),
        "imports": round(imports, 2),
        "renewables": round(renewables, 2),
        "nuclear": round(nuclear, 2),
        "demand_chart": compute_demand_chart(edges),
    }


def compute_demand_chart(edges):
    series = {}
    for sector_name, to_set in DEMAND_SECTOR_GROUPS:
        series[sector_name] = [
            round(sum(e["values"][yi] for e in edges if e["to"] in to_set), 2)
            for yi in CHART_YEAR_IDXS
        ]
    total = [round(sum(series[s][i] for s, _ in DEMAND_SECTOR_GROUPS), 2)
             for i in range(len(CHART_YEAR_IDXS))]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


# ── Page ─────────────────────────────────────────────────────────────────────
def _render_categories_html():
    blocks = []
    for cat in LEVER_CATEGORIES:
        rows_html = []
        for lv in cat["levers"]:
            rows_html.append(f"""
              <div class="lever-row">
                <label title="{lv['name']}">{lv['name']}</label>
                <input type="range" min="0" max="{lv['max']}" value="{lv['value']}" id="{lv['id']}">
                <span class="val" id="{lv['id']}-v">{lv['value']}</span>
              </div>""")
        blocks.append(f"""
          <details class="cat" open>
            <summary>{cat['category']} <span class="count">({len(cat['levers'])})</span></summary>
            {''.join(rows_html)}
          </details>""")
    return "".join(blocks)


PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>IESS2047 Compiler — Custom Adjustable Levers</title>
<style>
  body { font-family: -apple-system, Arial, sans-serif; max-width: 820px; margin: 30px auto; color: #222; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  .sub { color: #666; font-size: 13px; margin-bottom: 20px; }
  details.cat { border: 1px solid #e5e5e5; border-radius: 6px; margin: 8px 0; padding: 8px 12px; }
  details.cat summary { cursor: pointer; font-weight: 600; padding: 4px 0; }
  .count { color: #999; font-weight: 400; font-size: 12px; }
  .lever-row { display: flex; align-items: center; gap: 12px; margin: 6px 0; }
  .lever-row label { width: 260px; font-size: 13px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lever-row input[type=range] { flex: 1; }
  .lever-row .val { width: 22px; text-align: right; font-weight: 600; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; margin-top: 8px; }
  th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee; font-size: 14px; }
  th { color: #666; font-weight: 600; }
  #status { font-size: 12px; color: #999; margin-top: 6px; }
  .sticky { position: sticky; top: 0; background: #fff; padding-top: 10px; z-index: 1; }
  .boxes { display: flex; gap: 12px; flex-wrap: wrap; }
  .box { flex: 1; min-width: 220px; border: 1px solid #e5e5e5; border-radius: 6px; padding: 10px 12px; }
  .box h3 { margin: 0 0 4px 0; font-size: 14px; }
  .box table { margin-top: 2px; }
</style>
</head>
<body>
  <div class="sticky">
    <h1>Custom Adjustable Levers</h1>
    <div class="sub">Move any slider — the workbook recalculates live through ModelEngine (no precomputed JSON). All __N_LEVERS__ levers come straight from the Control sheet.</div>
    <h2>Outputs (2047)</h2>
    <div class="boxes">
      <div class="box">
        <h3>Supply</h3>
        <table>
          <tr><td>Total primary energy supply</td><td id="o-supply">-</td></tr>
          <tr><td>Domestic fossil production (coal+oil+gas)</td><td id="o-domestic">-</td></tr>
          <tr><td>Fossil imports (coal+oil+gas)</td><td id="o-imports">-</td></tr>
          <tr><td>Renewables (solar+wind+hydro+waste)</td><td id="o-renew">-</td></tr>
          <tr><td>Nuclear</td><td id="o-nuclear">-</td></tr>
        </table>
      </div>
      <div class="box">
        <h3>Demand</h3>
        <table id="demand-box-table">
          <tr><td>Total final energy demand</td><td id="o-demand">-</td></tr>
        </table>
      </div>
      <div class="box">
        <h3>Balance</h3>
        <table>
          <tr><td>Supply - demand</td><td id="o-balance">-</td></tr>
        </table>
      </div>
    </div>
    <div id="status">recalculating...</div>
    <div id="error" style="color:#c00; font-size:12px;"></div>
  </div>

  <h2>Energy Demand by Sector (2022 - 2047)</h2>
  <canvas id="demandChart" height="260"></canvas>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  __CATEGORIES_HTML__

<script>
const ids = __IDS_JSON__;
let recalcTimer = null;
async function recalc() {
  document.getElementById("status").textContent = "recalculating...";
  document.getElementById("error").textContent = "";
  try {
    const levers = {};
    for (const id of ids) levers[id] = document.getElementById(id).value;
    const res = await fetch("/recalc", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(levers)
    });
    if (!res.ok) throw new Error("server returned " + res.status);
    const data = await res.json();
    document.getElementById("o-supply").textContent = data.total_supply;
    document.getElementById("o-demand").textContent = data.total_demand;
    document.getElementById("o-balance").textContent = data.balance;
    document.getElementById("o-domestic").textContent = data.domestic_production;
    document.getElementById("o-imports").textContent = data.imports;
    document.getElementById("o-renew").textContent = data.renewables;
    document.getElementById("o-nuclear").textContent = data.nuclear;
    updateDemandBox(data.demand_chart);
    updateChart(data.demand_chart);
    document.getElementById("status").textContent = "live — engine recalculated " + new Date().toLocaleTimeString();
  } catch (err) {
    document.getElementById("status").textContent = "FAILED";
    document.getElementById("error").textContent = "Error: " + err.message + " (open browser console for details)";
    console.error(err);
  }
}
function updateDemandBox(chartData) {
  const table = document.getElementById("demand-box-table");
  // keep the "Total final energy demand" row, replace any per-sector rows after it
  while (table.rows.length > 1) table.deleteRow(1);
  const lastIdx = chartData.years.length - 1; // 2047
  for (const [sector, values] of Object.entries(chartData.series)) {
    const row = table.insertRow();
    row.insertCell(0).textContent = sector + " (2047)";
    row.insertCell(1).textContent = values[lastIdx];
  }
}
function scheduleRecalc() {
  clearTimeout(recalcTimer);
  recalcTimer = setTimeout(recalc, 250);
}
for (const id of ids) {
  const slider = document.getElementById(id);
  slider.addEventListener("input", () => {
    document.getElementById(id+"-v").textContent = slider.value;
    scheduleRecalc();
  });
}

let demandChart = null;
const SECTOR_COLORS = {
  "Buildings": "#d2691e", "Industry": "#7b3f9e", "Transport": "#1aa087",
  "Agriculture": "#4caf50", "Telecom": "#e53935", "Cooking": "#c9a227",
  "Miscellaneous": "#90a4ae"
};
function updateChart(chartData) {
  const ctx = document.getElementById("demandChart");
  const datasets = Object.entries(chartData.series).map(([name, values]) => ({
    label: name, data: values, fill: true,
    backgroundColor: SECTOR_COLORS[name] + "cc", borderColor: SECTOR_COLORS[name],
    stack: "demand", tension: 0
  }));
  datasets.push({
    label: "Total", data: chartData.total, fill: false,
    borderColor: "#000", backgroundColor: "#000", pointRadius: 3,
    borderWidth: 1.5, tension: 0
  });
  if (!demandChart) {
    demandChart = new Chart(ctx, {
      type: "line",
      data: { labels: chartData.years, datasets },
      options: {
        responsive: true,
        scales: {
          y: { stacked: true, title: { display: true, text: "Mtoe" } },
          x: { title: { display: true, text: "Year" } }
        }
      }
    });
  } else {
    demandChart.data.labels = chartData.years;
    demandChart.data.datasets = datasets;
    demandChart.update();
  }
}
recalc();
</script>
</body>
</html>
"""


@app.after_request
def no_cache(resp):
    # Demo server — never let the browser serve a stale page or stale JS
    # while the slider/output logic is still being iterated on.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/")
def index():
    import json
    html = PAGE_TEMPLATE
    html = html.replace("__N_LEVERS__", str(len(ALL_LEVER_ROWS)))
    html = html.replace("__CATEGORIES_HTML__", _render_categories_html())
    html = html.replace("__IDS_JSON__", json.dumps(list(ALL_LEVER_ROWS.keys())))
    return html


@app.route("/recalc", methods=["POST"])
def recalc():
    levers = request.get_json()
    for lever_id, row in ALL_LEVER_ROWS.items():
        if lever_id in levers:
            eng.set_lever("Control", f"E{row}", int(levers[lever_id]))
    return jsonify(compute_outputs())


if __name__ == "__main__":
    app.run(debug=False, port=5000)
