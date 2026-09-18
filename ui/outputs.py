"""
Output computation for the All Energy tab.

All classification sets below are UI-layer groupings over eng.read_flows()
edge names (from/to node strings) — same pattern as demo_app.py's
PRIMARY_SOURCES/DEMAND_SECTOR_GROUPS. No engine code is touched; this module
only calls the public ModelEngine API (read_flows, read_cell).
"""

YEAR_IDX = 6  # index into the 8-value [Base,2022,2027,2032,2037,2042,2047,Target] list -> 2047
CHART_YEAR_LABELS = ["2022", "2027", "2032", "2037", "2042", "2047"]
CHART_YEAR_IDXS = [1, 2, 3, 4, 5, 6]

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

DEMAND_SECTOR_GROUPS = [
    ("Buildings",     {"Residential Buildings", "Commercial Buildings"}),
    ("Industry",      {"Industry"}),
    ("Transport",     {"Passenger Transport", "Freight Transport"}),
    ("Agriculture",   {"Agriculture"}),
    ("Telecom",       {"Telecom"}),
    ("Cooking",       {"Cooking"}),
    ("Miscellaneous", {"Miscellaneous", "Non-energy use", "Refineries"}),
]

# Primary supply broken down by source, for the "Energy Supply" stacked-area
# chart. Per-source breakdown (not bucketed into Renewables/Biomass) and
# ordering matches the reference IESS website layout the user asked us to
# mirror: Solar, Wind, Hydro, Nuclear, Others, Coal, Oil and petroleum
# products, Natural gas, Electricity Import.
SUPPLY_SOURCE_GROUPS = [
    ("Solar",                     {"Solar"}),
    ("Wind",                      {"Wind"}),
    ("Hydro",                     {"Hydro", "Small Hydro"}),
    ("Nuclear",                   {"Nuclear"}),
    ("Others",                    {"Municipal Waste", "Agricultural Waste/ Energy Crops",
                                    "Agricultural Waste/Energy Crops"}),
    ("Coal",                      {"Coal Production", "Coal Imports"}),
    ("Oil and petroleum products", {"Oil Production", "Oil Imports"}),
    ("Natural gas",               {"Gas Production", "Gas Imports"}),
    ("Electricity Import",        {"Electricity Imports"}),
]

# "Import Dependence" line chart (% imports vs. total supply per fuel) — read
# directly from the workbook's own pre-built 'IESS V3 Results' sheet, rows
# 105-111 ("Import Dependence" section), rather than re-derived from
# read_flows(). These are the workbook author's own formulas (already
# lever-reactive, same as every other cell the engine evaluates); we only
# read them, same pattern as compute_population_millions(). Row numbers and
# year->column mapping confirmed by direct inspection of the sheet. "Overall"
# (row 111) is intentionally excluded — the reference chart only shows the
# 4 individual fuels.
IMPORT_DEPENDENCE_ROWS = [
    ("Non-coking Coal", 107),
    ("Coking Coal", 108),
    ("Oil", 109),
    ("Gas", 110),
]
IMPORT_DEPENDENCE_YEAR_COLS = ["E", "F", "G", "H", "I", "J"]  # 2022..2047, same order as CHART_YEAR_LABELS

# "Energy Emissions intensity to GDP" bar chart — 'IESS V3 Results' row 118,
# same sheet/column layout as Import Dependence above.
EMISSIONS_INTENSITY_ROW = 118

# Energy Security tab — "Energy Imports" stacked-area chart. Different sheet
# from everything else this session: 'Intermediate output' is the workbook's
# full energy-balance table, one column per calendar year starting 1970 (unit
# row 4 = "Mtoe / year"). Year columns for our 6 chart years found by
# scanning row 4 for the literal year values: BC=2022, BD=2027, BE=2032,
# BF=2037, BG=2042, BH=2047 (not the D-K layout used by every other sheet
# this session — confirmed directly, not assumed from precedent).
# Row 44 "Coking Coal Imports" + row 45 "Non-coking Coal Imports" verified to
# sum exactly to row 43 "Coal oversupply (imports)" at every year checked —
# confirms these are a real, consistent-unit split of the aggregate coal
# import figure, not an approximation. Oil/Gas import rows (49, 51) are
# already single figures, no split needed.
ENERGY_IMPORTS_SHEET = "Intermediate output"
ENERGY_IMPORTS_YEAR_COLS = ["BC", "BD", "BE", "BF", "BG", "BH"]  # 2022..2047
ENERGY_IMPORTS_ROWS = [
    ("Non-coking coal", 45),
    ("Coking Coal", 44),
    ("Oil", 49),
    ("Gas", 51),
]

# Emissions tab — "Energy-related GHG Emissions" by sector. Same
# 'Intermediate output' sheet/year-columns as Energy Imports above (rows
# 174-192, "Emissions by sector" block, numbered I-XVII with roman-numeral
# codes in column C). Grouped honestly by what the sheet actually contains,
# not force-fit to any external legend: "Electricity" sums every
# generation-technology row (I-VII: Hydrocarbon fuel power, Nuclear, Hydro,
# National renewable, Bioenergy, Waste, Electricity storage — verified only
# row I/Hydrocarbon is ever nonzero in practice, since the other 6 are
# zero-carbon by construction, but summed for correctness under any future
# scenario). "Refineries" folds together three rows: IX "Stress" and X
# "Buildings" (both confirmed zero-valued in every scenario tested — kept for
# completeness under any future scenario, not dropped) and XVII "Transfer",
# which is the only nonzero one of the three. The sheet's own label for row
# XVII is just "Transfer" with no clean single-word meaning on its own — this
# was left as an unconfirmed, generic "Other" bucket until the reference IESS
# website (a separate, earlier version of this same model/data lineage) was
# checked independently and showed a distinctly-labeled "Refineries" line at
# the same order of magnitude — renamed to match once confirmed externally,
# not guessed. row 192 "Total Emissions in MT CO2" verified (not assumed) to
# equal the sum of every row I-XVII at every year checked (e.g. 2022: 2745.24
# both ways) — also cross-validated against 'IESS V3 Results' row 116 "Total
# energy GHG Emissions", which matches to the last decimal.
EMISSIONS_SECTOR_GROUPS = [
    ("Electricity", [175, 176, 177, 178, 179, 180, 181]),
    ("Industry", [185]),
    ("Transport", [186]),
    ("Cooking", [187]),
    ("Agriculture", [188]),
    ("Fuel Production", [189]),
    ("Telecom", [190]),
    ("Refineries", [183, 184, 191]),
]
EMISSIONS_TOTAL_ROW = 192

# "Per Capita GHG Emissions" bar chart — 'IESS V3 Results' row 117, same
# sheet/column layout (E-J) as Import Dependence/Emissions Intensity.
PER_CAPITA_EMISSIONS_ROW = 117

# Indicators tab, "Energy Emissions Intensity of GDP" sub-tab — second chart
# "Energy intensity of GDP" (MJ/INR). 'IESS V3 Results' row 49 "Energy
# Intensity", same sheet/column layout as everything else sourced from this
# sheet. The first chart on this sub-tab reuses the existing
# emissions_intensity_chart (row 118) — same data already shown on the All
# Energy tab, just rendered again here per the reference image.
ENERGY_INTENSITY_ROW = 49

# Indicators tab, "Per Capita Indicators" sub-tab. "Per Capita GHG Emissions"
# reuses per_capita_emissions_chart (row 117) already computed above.
# "Per Capita Primary Energy Supply" (toe/person) is not a pre-computed row
# anywhere in the workbook (searched — no match for "per capita" + "primary"
# or "toe/person" text across every sheet) — derived here the same way
# per_capita_demand (a KPI, not a chart) is already derived in
# compute_outputs(): Total Primary Supply (row 48, Mtoe) divided by
# Population (row 3, millions) at each year. Mtoe / million-people = toe/
# person exactly by unit cancellation (10^6 toe / 10^6 people) — no
# conversion factor needed, unlike the MJ/person KPI which needs MTOE_TO_MJ.
PRIMARY_SUPPLY_ROW = 48
POPULATION_ROW = 3

# Indicators tab, "Electricity Indicators" sub-tab — "Installed Capacity"
# stacked-area chart. Same 12 technology sheets as GENERATION_ROWS above,
# but reading each sheet's own "Cumulative Installed Capacity (in GW)" row
# instead of the generation row — found via the same per-sheet search
# pattern, confirmed present in all 12 (row numbers differ per sheet; same
# D-J year-column layout already verified per-sheet for GENERATION_ROWS).
# "Waste to Electricity" (sheet 'VI') has no such row — that module tracks
# capacity in its own differently-laid-out trajectory-choice table instead
# (a "Chosen" row selecting among 4 lever-driven trajectories, same pattern
# used throughout the workbook for lever-selected values) — confirmed by
# directly searching 'VI' for "cumulative" (zero matches) and finding the
# actual capacity-trajectory table at row 56 under its own header "Waste to
# electricity capacity deployed (GW)" (row 49). That table's year columns
# are I-N (2022-2047), not the D-J layout used everywhere else — confirmed
# directly per-sheet, not assumed.
CAPACITY_ROWS = {
    "Gas Power Stations": [("I.a", 295)],
    "Coal Power Stations": [("I.b", 465)],
    "CCS": [("I.c", 336)],
    "Nuclear": [("II", 368)],
    "Large Hydro": [("III", 198)],
    "Solar PV": [("IV.a", 225)],
    "Solar CSP": [("IV.b", 291)],
    "Onshore Wind": [("IV.c.1", 203)],
    "Offshore Wind": [("IV.c.2", 137)],
    "Small Hydro": [("IV.d", 177)],
    "Distributed Solar PV": [("IV.e", 220)],
    "Biomass": [("V.a", 223)],
}
CAPACITY_ORDER = [
    "Gas Power Stations", "Coal Power Stations", "CCS", "Nuclear", "Large Hydro",
    "Solar PV", "Solar CSP", "Onshore Wind", "Offshore Wind", "Small Hydro",
    "Distributed Solar PV", "Biomass",
]
WASTE_CAPACITY_SHEET = "VI"
WASTE_CAPACITY_ROW = 56
WASTE_CAPACITY_YEAR_COLS = ["I", "J", "K", "L", "M", "N"]  # 2022..2047, this table's own layout

# "Demand Electrification" (%) — not a pre-computed row anywhere either;
# derived from read_flows() edges the same way the (now-removed)
# fuel-consumption chart worked earlier this session: share of final demand
# met by the "Electricity Grid" node vs. every other carrier reaching
# FINAL_DEMAND_SECTORS.

# Costs tab, "Annual Import & Energy Costs" sub-tab. 'Cost - Import +
# Production' sheet — a dedicated cost-calculation sheet with 3 price
# scenarios (HIGH/POINT/LOW) for both import and domestic-production costs;
# POINT (the central estimate) used throughout, same convention a dashboard
# would default to. Same D-J year-column layout as everywhere else.
COST_SHEET_IMPORT_PROD = "Cost - Import + Production"
IMPORT_COST_ROWS = [
    ("Non-coking coal", 25),
    ("Coking coal", 26),
    ("Crude oil", 27),
    ("Gas", 28),
]
IMPORT_COST_TOTAL_ROW = 29
PRODUCTION_COST_ROWS = [
    ("Coal", 83),
    ("Oil", 84),
    ("Gas", 85),
]
PRODUCTION_COST_TOTAL_ROW = 86

# Costs tab, "Power Sector Cost" sub-tab. 'Cost - Power Sector and H2' sheet
# — same 14-technology breakdown for both charts (the 12 generation-tech
# sheets from GENERATION_ROWS/CAPACITY_ROWS, plus Standalone PV/Wind for
# Hydrogen — no separate "Waste to Electricity" row in this cost table,
# confirmed by its absence from the sheet's own technology list, not
# dropped by us). POINT scenario used for both, same convention as above.
#
# "Power Sector capex" is genuinely five-yearly, not annual — its own
# column headers read '2020-2022', '2022-27', ... '2042-47' (row 52),
# confirmed directly rather than assumed from the D-J pattern used
# everywhere else. "Annual Operating Costs" uses the standard D-J annual
# year layout.
COST_SHEET_POWER = "Cost - Power Sector and H2"
CAPEX_ROWS_5YR = [
    ("Gas Power Stations", 71),
    ("Coal Power Stations", 72),
    ("Carbon Capture Storage (CCS)", 73),
    ("Nuclear", 74),
    ("Hydro Power Generation", 75),
    ("Solar PV", 76),
    ("Solar CSP", 77),
    ("Onshore Wind", 78),
    ("Offshore Wind", 79),
    ("Small Hydro", 80),
    ("Distributed Solar PV", 81),
    ("Biomass Base Electricity", 82),
    ("Standalone PV for Hydrogen", 83),
    ("Standalone Wind for Hydrogen", 84),
]
CAPEX_TOTAL_ROW = 85
CAPEX_PERIOD_COLS = ["E", "F", "G", "H", "I", "J"]
CAPEX_PERIOD_LABELS = ["2020-2022", "2022-2027", "2027-2032", "2032-2037", "2037-2042", "2042-2047"]

OPEX_ROWS = [
    ("Gas Power Stations", 138),
    ("Coal Power Stations", 139),
    ("Carbon Capture Storage (CCS)", 140),
    ("Nuclear", 141),
    ("Hydro Power Generation", 142),
    ("Solar PV", 143),
    ("Solar CSP", 144),
    ("Onshore Wind", 145),
    ("Offshore Wind", 146),
    ("Small Hydro", 147),
    ("Distributed Solar PV", 148),
    ("Biomass Base Electricity", 149),
    ("Standalone PV for Hydrogen", 150),
    ("Standalone Wind for Hydrogen", 151),
]
OPEX_TOTAL_ROW = 152

# Land & Water tab. Two dedicated sheets, 'Land Use' and 'Water Use' —
# neither shares the D-J or BC-BH layouts used elsewhere; each has its own
# column offset, confirmed directly by reading each sheet's own year-header
# row (row 4) rather than assumed. Land Use: K=2022..P=2047. Water Use:
# J=2022..O=2047.
#
# Both charts mix individual-technology rows with the sheet's own
# pre-aggregated bucket rows (e.g. "Renewables" on Land Use is already a
# sum of Solar PV/CSP/Onshore Wind/Small Hydro in the sheet itself, not
# something we summed) — chosen to match the two reference charts' own
# category lists exactly, both of which mix specific technologies with
# broader buckets.
#
# Unit note: Land Use's own section header (row 36) reads "Area in M ha"
# (million hectares) — the reference chart's stated axis unit "Hectares"
# with tick labels like "1.6M" is consistent with this if read as shorthand
# for "1.6 million Hectares", i.e. the same M-ha figures. Labeled our chart
# "Million Hectares" rather than bare "Hectares" to stay unit-honest without
# needing a custom large-number tick formatter. Water Use's raw rows and its
# own later "Water in MCM" summary section (row 30) are numerically
# equivalent to the reference's "Billion Litres" unit (1 MCM = 1,000,000 m³
# = 1,000,000,000 L = 1 billion litres exactly) — no conversion needed.
LAND_USE_SHEET = "Land Use"
LAND_USE_YEAR_COLS = ["K", "L", "M", "N", "O", "P"]  # 2022..2047
LAND_USE_ROWS = [
    ("Gas Power Stations", 6),
    ("Coal Power Stations", 7),
    ("CCS", 8),
    ("Nuclear", 9),
    ("Hydro Power Generation", 10),
    ("Renewables", 16),
    ("Bio Energy", 21),
    ("Green Hydrogen", 22),
]
LAND_USE_TOTAL_ROW = 23

WATER_USE_SHEET = "Water Use"
WATER_USE_YEAR_COLS = ["J", "K", "L", "M", "N", "O"]  # 2022..2047
WATER_USE_ROWS = [
    ("Gas Power Stations", 6),
    ("Coal Power Stations", 7),
    ("Solar CSP", 10),
    ("Nuclear", 8),
    ("Domestic Fuel production", 16),
    ("Green Hydrogen", 12),
]
WATER_USE_TOTAL_ROW = 17
# above. Demand-side rows (55-63) are per-sector; grouped here to the closest
# real breakdown available (Residential+Commercial -> Buildings; Hydrogen +
# Refineries folded into Miscellaneous, since the sheet doesn't split them
# further). Supply-side rows (87-91) are only pre-aggregated into 4 buckets
# in this sheet (Coal/Gas/CCS are combined into one "Thermal Generation" node
# everywhere in the model, including read_flows()) — confirmed with the user
# this coarser real breakdown is acceptable rather than tracing the 6+
# separate per-technology sheets (II, III, IV.a-IV.e) for a finer split.
ELECTRICITY_DEMAND_GROUPS = [
    ("Industry", [55]),
    ("Buildings", [56, 57]),
    ("Agriculture", [58]),
    ("Telecom, Cooking & Transport", [59]),
    ("Miscellaneous", [60, 61, 62]),
]
ELECTRICITY_DEMAND_TOTAL_ROW = 63

ELECTRICITY_SUPPLY_TOTAL_ROW = 91

# Full 9-category generation breakdown (Gas/Coal/CCS/Nuclear/Hydro/Solar/Wind/
# Bioenergy/Electricity trade), traced per the user's request into each
# technology's own module sheet — the coarse 4-bucket version above
# ('IESS V3 Results' rows 87-90) combines Coal/Gas/CCS into one "Thermal
# Generation" figure and can't be split further; this can.
#
# Each technology sheet follows the same author's template: a "Trajectory
# choice" block, then a year-header row (2020/2022/2027/2032/2037/2042/2047
# in columns D-J), then a "Annual Generation from Existing Capacity (in GWh)"
# row holding that technology's total annual generation (Old + New capacity
# combined — verified directly: for every sheet checked, this row's value
# equals the sum of the adjacent "...from Old Capacity" and "...from New
# Capacity" rows). Coal (I.b) is the one exception: its own equivalent row is
# labelled "Annual Generation from Total Capacity (in GWh)" and sits in
# column B instead of C, but uses the same D-J year columns as every other
# sheet — confirmed by direct inspection, not assumed from the pattern.
# Sheet/row pairs and technology identity were both confirmed by reading each
# sheet's own title cells (e.g. IV.b row 2 = "Solar CSP"), not guessed from
# naming convention.
GENERATION_ROWS = {
    "Gas": [("I.a", 300)],
    "Coal": [("I.b", 470)],
    "CCS": [("I.c", 341)],
    "Nuclear": [("II", 373)],
    "Hydro": [("III", 203), ("IV.d", 182)],            # Hydro Power + Small Hydro
    "Solar": [("IV.a", 230), ("IV.b", 296), ("IV.e", 225)],  # Solar PV + Solar CSP + Distributed Solar PV
    "Wind": [("IV.c.1", 208), ("IV.c.2", 142)],         # Onshore + Offshore
    "Bioenergy": [("V.a", 228)],                        # Biomass Based Electricity
}
GENERATION_ORDER = ["Gas", "Coal", "CCS", "Nuclear", "Hydro", "Solar", "Wind", "Bioenergy"]
GWH_TO_TWH = 1000.0

# "Electricity trade" isn't a technology sheet — it's the same net imports
# figure already used in the coarse breakdown, read straight from
# 'IESS V3 Results' row 90 (already in TWh, no conversion needed).
ELECTRICITY_TRADE_ROW = 90

MTOE_TO_MJ = 41_868_000_000  # 1 Mtoe = 41,868,000,000 MJ
EPS = 1e-6

# Sankey node categories — UI-layer classification over read_flows() node
# names, used only for color-coding. LOSS_NODES/TECH_NODES are disjoint from
# PRIMARY_SOURCES/FINAL_DEMAND_SECTORS above; anything unmatched (energy
# carriers like Coal/Solid/Liquid/Electricity Grid) falls into "carrier".
LOSS_NODES = {"Losses", "T&D Losses", "Over Generation/Exports"}
TECH_NODES = {
    "Solar PV", "Solar CSP", "Distributed Solar PV", "Onshore Wind",
    "Offshore Wind", "Off Grid Renewables", "Green Hydrogen", "Thermal Generation",
}
SANKEY_YEARS = list(zip(CHART_YEAR_LABELS, CHART_YEAR_IDXS))
SANKEY_MIN_VALUE = 0.05  # Mtoe — hide noise edges from the diagram


def _node_category(name):
    if name in PRIMARY_SOURCES:
        return "source"
    if name in FINAL_DEMAND_SECTORS:
        return "demand"
    if name in LOSS_NODES:
        return "loss"
    if name in TECH_NODES:
        return "tech"
    return "carrier"


def _sankey_for_year(edges, year_idx):
    links_raw = []
    for e in edges:
        if not e["from"] or not e["to"]:
            continue
        vals = e["values"]
        v = vals[year_idx] if len(vals) > year_idx else 0.0
        if v is None or v <= SANKEY_MIN_VALUE:
            continue
        links_raw.append((e["from"], e["to"], round(v, 3)))

    order, seen = [], set()
    for f, t, _ in links_raw:
        for n in (f, t):
            if n not in seen:
                seen.add(n)
                order.append(n)
    idx = {n: i for i, n in enumerate(order)}

    nodes = [{"name": n, "category": _node_category(n)} for n in order]
    links = [{"source": idx[f], "target": idx[t], "value": v} for f, t, v in links_raw]
    return {"nodes": nodes, "links": links}


def compute_sankey(edges):
    return {label: _sankey_for_year(edges, yi) for label, yi in SANKEY_YEARS}


def _series_over_years(edges, node_set, by="from", to_demand_only=False):
    out = []
    for yi in CHART_YEAR_IDXS:
        total = 0.0
        for e in edges:
            key = e[by]
            if key not in node_set:
                continue
            if to_demand_only and e["to"] not in FINAL_DEMAND_SECTORS:
                continue
            vals = e["values"]
            total += vals[yi] if len(vals) > yi else 0.0
        out.append(round(total, 2))
    return out


def compute_demand_chart(edges):
    series = {name: _series_over_years(edges, to_set, by="to") for name, to_set in DEMAND_SECTOR_GROUPS}
    total = [round(sum(series[s][i] for s, _ in DEMAND_SECTOR_GROUPS), 2) for i in range(len(CHART_YEAR_IDXS))]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_supply_chart(edges):
    series = {name: _series_over_years(edges, from_set, by="from") for name, from_set in SUPPLY_SOURCE_GROUPS}
    total = [round(sum(series[s][i] for s, _ in SUPPLY_SOURCE_GROUPS), 2) for i in range(len(CHART_YEAR_IDXS))]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_import_dependence_chart(eng):
    series = {}
    for name, row in IMPORT_DEPENDENCE_ROWS:
        series[name] = [
            round((eng.read_cell("IESS V3 Results", f"{col}{row}") or 0.0) * 100, 2)
            for col in IMPORT_DEPENDENCE_YEAR_COLS
        ]
    return {"years": CHART_YEAR_LABELS, "series": series}


def compute_energy_imports_chart(eng):
    series = {
        name: [round(eng.read_cell(ENERGY_IMPORTS_SHEET, f"{col}{row}") or 0.0, 2) for col in ENERGY_IMPORTS_YEAR_COLS]
        for name, row in ENERGY_IMPORTS_ROWS
    }
    total = [round(sum(series[name][i] for name, _ in ENERGY_IMPORTS_ROWS), 2) for i in range(len(ENERGY_IMPORTS_YEAR_COLS))]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_emissions_intensity_chart(eng):
    values = [
        round(eng.read_cell("IESS V3 Results", f"{col}{EMISSIONS_INTENSITY_ROW}") or 0.0, 1)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "values": values}


def compute_emissions_by_sector_chart(eng):
    series = {
        name: [
            round(sum(eng.read_cell(ENERGY_IMPORTS_SHEET, f"{col}{r}") or 0.0 for r in rows), 2)
            for col in ENERGY_IMPORTS_YEAR_COLS
        ]
        for name, rows in EMISSIONS_SECTOR_GROUPS
    }
    total = [
        round(eng.read_cell(ENERGY_IMPORTS_SHEET, f"{col}{EMISSIONS_TOTAL_ROW}") or 0.0, 2)
        for col in ENERGY_IMPORTS_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_per_capita_emissions_chart(eng):
    values = [
        round(eng.read_cell("IESS V3 Results", f"{col}{PER_CAPITA_EMISSIONS_ROW}") or 0.0, 2)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "values": values}


def compute_energy_intensity_chart(eng):
    values = [
        round(eng.read_cell("IESS V3 Results", f"{col}{ENERGY_INTENSITY_ROW}") or 0.0, 4)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "values": values}


def compute_per_capita_supply_chart(eng):
    values = []
    for col in IMPORT_DEPENDENCE_YEAR_COLS:
        supply = eng.read_cell("IESS V3 Results", f"{col}{PRIMARY_SUPPLY_ROW}") or 0.0
        population = eng.read_cell("IESS V3 Results", f"{col}{POPULATION_ROW}") or 0.0
        values.append(round(supply / population, 3) if population else 0.0)
    return {"years": CHART_YEAR_LABELS, "values": values}


def compute_capacity_chart(eng):
    # Sheet I.b's year columns are shifted one column earlier than every other
    # technology sheet here — the same fact already established for its
    # generation row (see _IB_SHEET_YEAR_COLS below, and the comment there for
    # how it was confirmed). It's a property of the whole sheet's year-header
    # row, not just the one cell that was checked first: row 465 (Coal Power
    # Stations' own "Cumulative Installed Capacity" row) follows the identical
    # D..I layout — confirmed directly, I.b!J465 is blank (0) exactly like
    # I.b!J470 is, and I.b!D465 through I.b!I465 hold six real, smoothly
    # increasing values where the un-shifted E..J read was quietly handing back
    # 2047 as 0 (a blank cell) and every other year as the next year's figure.
    # This function was missed when that fix was applied to the generation
    # chart, so Coal Power Stations was the one series in Installed Capacity
    # silently reading one year ahead of every other series in the same chart.
    series = {}
    for name in CAPACITY_ORDER:
        vals = []
        for i, col in enumerate(IMPORT_DEPENDENCE_YEAR_COLS):
            total_gw = 0.0
            for sheet, row in CAPACITY_ROWS[name]:
                read_col = _IB_SHEET_YEAR_COLS[i] if sheet == "I.b" else col
                total_gw += eng.read_cell(sheet, f"{read_col}{row}") or 0.0
            vals.append(round(total_gw, 3))
        series[name] = vals
    series["Waste to Electricity"] = [
        round(eng.read_cell(WASTE_CAPACITY_SHEET, f"{col}{WASTE_CAPACITY_ROW}") or 0.0, 3)
        for col in WASTE_CAPACITY_YEAR_COLS
    ]
    total = [round(sum(series[name][i] for name in series), 3) for i in range(len(CHART_YEAR_LABELS))]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_demand_electrification_chart(edges):
    values = []
    for yi in CHART_YEAR_IDXS:
        elec_to_demand = sum(
            e["values"][yi] for e in edges
            if e["from"] == "Electricity Grid" and e["to"] in FINAL_DEMAND_SECTORS and len(e["values"]) > yi
        )
        total_demand = sum(
            e["values"][yi] for e in edges if e["to"] in FINAL_DEMAND_SECTORS and len(e["values"]) > yi
        )
        values.append(round(elec_to_demand / total_demand * 100, 2) if total_demand else 0.0)
    return {"years": CHART_YEAR_LABELS, "values": values}


def compute_import_cost_chart(eng):
    series = {
        name: [round(eng.read_cell(COST_SHEET_IMPORT_PROD, f"{col}{row}") or 0.0, 1) for col in IMPORT_DEPENDENCE_YEAR_COLS]
        for name, row in IMPORT_COST_ROWS
    }
    total = [
        round(eng.read_cell(COST_SHEET_IMPORT_PROD, f"{col}{IMPORT_COST_TOTAL_ROW}") or 0.0, 1)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_production_cost_chart(eng):
    series = {
        name: [round(eng.read_cell(COST_SHEET_IMPORT_PROD, f"{col}{row}") or 0.0, 1) for col in IMPORT_DEPENDENCE_YEAR_COLS]
        for name, row in PRODUCTION_COST_ROWS
    }
    total = [
        round(eng.read_cell(COST_SHEET_IMPORT_PROD, f"{col}{PRODUCTION_COST_TOTAL_ROW}") or 0.0, 1)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_capex_chart(eng):
    series = {
        name: [round(eng.read_cell(COST_SHEET_POWER, f"{col}{row}") or 0.0, 1) for col in CAPEX_PERIOD_COLS]
        for name, row in CAPEX_ROWS_5YR
    }
    total = [round(eng.read_cell(COST_SHEET_POWER, f"{col}{CAPEX_TOTAL_ROW}") or 0.0, 1) for col in CAPEX_PERIOD_COLS]
    return {"years": CAPEX_PERIOD_LABELS, "series": series, "total": total}


def compute_opex_chart(eng):
    series = {
        name: [round(eng.read_cell(COST_SHEET_POWER, f"{col}{row}") or 0.0, 1) for col in IMPORT_DEPENDENCE_YEAR_COLS]
        for name, row in OPEX_ROWS
    }
    total = [
        round(eng.read_cell(COST_SHEET_POWER, f"{col}{OPEX_TOTAL_ROW}") or 0.0, 1)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}



# Land Use / Water Use sheets store their raw values already scaled down (Land
# Use in "M ha" per its own row-36 section header, Water Use equivalent to
# "Billion Litres" per its own MCM summary section — see the sheet-layout
# notes above). Read directly, those come out as small decimals (e.g. 0.804),
# which reads poorly compared to a plain hectare/litre count with a k/M
# suffix (what a reference chart in this space would show). Multiplying back
# to the raw unit here — and letting the frontend's compact-number formatter
# handle the k/M/B suffix — keeps the underlying calculation identical while
# fixing the display; no engine or workbook-value change involved.
LAND_USE_SCALE = 1_000_000       # sheet's "M ha" -> raw hectares
WATER_USE_SCALE = 1_000_000_000  # sheet's "Billion Litres" -> raw litres


def compute_land_use_chart(eng):
    series = {
        name: [round((eng.read_cell(LAND_USE_SHEET, f"{col}{row}") or 0.0) * LAND_USE_SCALE, 1) for col in LAND_USE_YEAR_COLS]
        for name, row in LAND_USE_ROWS
    }
    total = [round((eng.read_cell(LAND_USE_SHEET, f"{col}{LAND_USE_TOTAL_ROW}") or 0.0) * LAND_USE_SCALE, 1) for col in LAND_USE_YEAR_COLS]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_water_use_chart(eng):
    series = {
        name: [round((eng.read_cell(WATER_USE_SHEET, f"{col}{row}") or 0.0) * WATER_USE_SCALE, 1) for col in WATER_USE_YEAR_COLS]
        for name, row in WATER_USE_ROWS
    }
    total = [round((eng.read_cell(WATER_USE_SHEET, f"{col}{WATER_USE_TOTAL_ROW}") or 0.0) * WATER_USE_SCALE, 1) for col in WATER_USE_YEAR_COLS]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def _sum_rows(eng, rows, col):
    return sum(eng.read_cell("IESS V3 Results", f"{col}{r}") or 0.0 for r in rows)


def compute_electricity_demand_chart(eng):
    series = {
        name: [round(_sum_rows(eng, rows, col), 2) for col in IMPORT_DEPENDENCE_YEAR_COLS]
        for name, rows in ELECTRICITY_DEMAND_GROUPS
    }
    total = [
        round(eng.read_cell("IESS V3 Results", f"{col}{ELECTRICITY_DEMAND_TOTAL_ROW}") or 0.0, 2)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


# Sheet I.b (Coal generation) lays its year columns out one column earlier
# than every other technology sheet in GENERATION_ROWS — confirmed directly
# against the workbook: I.b!D470 holds the 2022 figure (matches the golden
# Coal[0] value), not I.b!E470 as the shared IMPORT_DEPENDENCE_YEAR_COLS
# mapping would read. Every other sheet here uses the standard E..J layout.
_IB_SHEET_YEAR_COLS = ["D", "E", "F", "G", "H", "I"]


def compute_electricity_supply_chart(eng):
    series = {}
    for name in GENERATION_ORDER:
        vals_by_col = []
        for i, col in enumerate(IMPORT_DEPENDENCE_YEAR_COLS):
            total_gwh = 0.0
            for sheet, row in GENERATION_ROWS[name]:
                read_col = _IB_SHEET_YEAR_COLS[i] if sheet == "I.b" else col
                total_gwh += eng.read_cell(sheet, f"{read_col}{row}") or 0.0
            vals_by_col.append(round(total_gwh / GWH_TO_TWH, 2))
        series[name] = vals_by_col

    series["Electricity trade"] = [
        round(eng.read_cell("IESS V3 Results", f"{col}{ELECTRICITY_TRADE_ROW}") or 0.0, 2)
        for col in IMPORT_DEPENDENCE_YEAR_COLS
    ]
    # Total is the sum of the 9 series above, not IESS V3 Results' own
    # separate "Net Electricity Generation" row (ELECTRICITY_SUPPLY_TOTAL_ROW).
    # That row is a differently-sourced, pre-aggregated figure (from the
    # coarse 4-bucket version this chart used to be) that can diverge sharply
    # from the sum of the fine per-technology sheet reads under lever-driven
    # scenarios (confirmed: a ~1,053 TWh / ~20% gap at 2047 under one tested
    # scenario) — a chart whose own stack doesn't add up to its own total
    # line is misleading regardless of which number is more "official".
    n_years = len(IMPORT_DEPENDENCE_YEAR_COLS)
    total = [round(sum(series[name][i] for name in series), 2) for i in range(n_years)]
    return {"years": CHART_YEAR_LABELS, "series": series, "total": total}


def compute_population_millions(eng):
    # "IESS V3 Results" row 3 = Population (Millions), col J (10) = year 2047.
    return eng.read_cell("IESS V3 Results", "J3")


DEFERRABLE_KEYS = ("emissions_by_sector_chart", "sankey")


def compute_emissions_2047_total(eng):
    return eng.read_cell("IESS V3 Results", "J116")


def compute_outputs(eng, defer=()):
    edges = eng.read_flows()
    val = {e["row"]: (e["values"][YEAR_IDX] if len(e["values"]) > YEAR_IDX else 0.0) for e in edges}

    total_supply = sum(val[e["row"]] for e in edges if e["from"] in PRIMARY_SOURCES)
    total_demand = sum(val[e["row"]] for e in edges if e["to"] in FINAL_DEMAND_SECTORS)
    domestic_production = sum(val[e["row"]] for e in edges if e["from"] in DOMESTIC_PRODUCTION_ROWS)
    imports = sum(val[e["row"]] for e in edges if e["from"] in IMPORT_ROWS)
    renewables = sum(val[e["row"]] for e in edges if e["from"] in RENEWABLE_SOURCES)
    nuclear = sum(val[e["row"]] for e in edges if e["from"] == "Nuclear")

    population_millions = compute_population_millions(eng)
    per_capita_mj = (total_demand * MTOE_TO_MJ / (population_millions * 1_000_000)
                      if population_millions else 0.0)
    import_dependence_pct = (imports / total_supply * 100) if total_supply else 0.0
    # Clean share of primary supply. Computed here rather than in the browser
    # (which is where it used to live, as dashboard.js's cleanSharePct) for one
    # reason: it is one of the four headline KPI cards, so the Insights panel
    # has to be able to report its before/after the same way it reports the
    # other three — and kpi_deltas() can only diff what compute_outputs()
    # actually produces. Same formula, one home.
    clean_share_pct = ((renewables + nuclear) / total_supply * 100) if total_supply else 0.0
    emissions_2047 = compute_emissions_2047_total(eng)

    out = {
        "kpis": {
            "total_demand": round(total_demand, 2),
            "total_supply": round(total_supply, 2),
            "per_capita_demand": round(per_capita_mj, 0),
            "import_dependence": round(import_dependence_pct, 1),
            "clean_share": round(clean_share_pct, 1),
        },
        "total_supply": round(total_supply, 2),
        "total_demand": round(total_demand, 2),
        "balance": round(total_supply - total_demand, 2),
        "domestic_production": round(domestic_production, 2),
        "imports": round(imports, 2),
        "renewables": round(renewables, 2),
        "nuclear": round(nuclear, 2),
        "emissions_2047_total": round(emissions_2047 or 0.0, 2),
        "demand_chart": compute_demand_chart(edges),
        "supply_chart": compute_supply_chart(edges),
        "import_dependence_chart": compute_import_dependence_chart(eng),
        "energy_imports_chart": compute_energy_imports_chart(eng),
        "per_capita_emissions_chart": compute_per_capita_emissions_chart(eng),
        "energy_intensity_chart": compute_energy_intensity_chart(eng),
        "per_capita_supply_chart": compute_per_capita_supply_chart(eng),
        "capacity_chart": compute_capacity_chart(eng),
        "demand_electrification_chart": compute_demand_electrification_chart(edges),
        "import_cost_chart": compute_import_cost_chart(eng),
        "production_cost_chart": compute_production_cost_chart(eng),
        "capex_chart": compute_capex_chart(eng),
        "opex_chart": compute_opex_chart(eng),
        "land_use_chart": compute_land_use_chart(eng),
        "water_use_chart": compute_water_use_chart(eng),
        "emissions_intensity_chart": compute_emissions_intensity_chart(eng),
        "electricity_demand_chart": compute_electricity_demand_chart(eng),
        "electricity_supply_chart": compute_electricity_supply_chart(eng),
    }
    if "emissions_by_sector_chart" not in defer:
        out["emissions_by_sector_chart"] = compute_emissions_by_sector_chart(eng)
    if "sankey" not in defer:
        out["sankey"] = compute_sankey(edges)
    return out


def _diff_scalar(a, b):
    return abs((a or 0) - (b or 0)) > EPS

# Stacked-area charts that get the dashed "changed" border highlight on any
# series that moved off the scenario baseline. Adding a chart here is the only
# step needed to wire that up. (These also used to feed a "Δ vs baseline" bar
# chart on the Electricity tab; that chart and its compute_chart_deltas()
# producer were removed — the area charts show the same movement across every
# year, not just 2047.)
DIFFABLE_CHARTS = ["demand_chart", "supply_chart", "electricity_demand_chart", "electricity_supply_chart"]


def diff_outputs(current, baseline):
    """Return a same-shape structure of booleans: True where current differs
    from baseline beyond EPS. Built entirely in this UI layer — the engine
    has no concept of 'changed since baseline'."""
    if baseline is None:
        return {
            "kpis": {k: False for k in current["kpis"]},
            **{
                chart: {"series": {k: [False] * len(v) for k, v in current[chart]["series"].items()}}
                for chart in DIFFABLE_CHARTS
            },
        }

    kpis_changed = {k: _diff_scalar(current["kpis"][k], baseline["kpis"].get(k)) for k in current["kpis"]}

    def chart_diff(cur_chart, base_chart):
        cur_series = cur_chart["series"]
        base_series = base_chart.get("series", {}) if base_chart else {}
        return {
            name: [
                _diff_scalar(cur_series[name][i], (base_series.get(name) or [None] * len(cur_series[name]))[i])
                for i in range(len(cur_series[name]))
            ]
            for name in cur_series
        }

    return {
        "kpis": kpis_changed,
        **{
            chart: {"series": chart_diff(current[chart], baseline.get(chart))}
            for chart in DIFFABLE_CHARTS
        },
    }


# KPI cards the "what changed" summary strip / Insights panel can headline.
# emissions_2047_total lives at the top level (see compute_outputs), not
# inside "kpis", because it's the landing tab's 4th stat card computed from
# one cell rather than a whole chart — kept alongside the other three here so
# callers get one flat set of deltas rather than two differently-shaped ones.
SUMMARY_KPI_KEYS = ["total_demand", "total_supply", "per_capita_demand",
                    "import_dependence", "clean_share", "emissions_2047_total"]


def kpi_deltas(current, baseline):
    """Numeric before/after/delta/pct for each summary KPI that moved beyond
    EPS since the baseline pathway — the same before/after idea as
    diff_outputs()'s booleans, except carrying the actual numbers, which is
    what the change-strip and Insights panel need to say anything concrete.
    Empty dict with no baseline yet (mirrors diff_outputs(None))."""
    if baseline is None:
        return {}

    def get(d, key):
        return d["kpis"][key] if key in d["kpis"] else d.get(key)

    out = {}
    for key in SUMMARY_KPI_KEYS:
        cur = get(current, key)
        base = get(baseline, key)
        # A key absent from EITHER side is skipped rather than read as 0.
        # `or 0` used to coerce it, which turns "this payload predates the
        # field" into a delta from zero — e.g. a clean share "rising" from 0%
        # to 24% when nothing about the pathway's clean share had moved.
        # Reachable whenever a baseline was computed under a different output
        # schema than the current result (see app.py's OUTPUT_FP, which now
        # makes that rare rather than impossible).
        if cur is None or base is None:
            continue
        if not _diff_scalar(cur, base):
            continue
        out[key] = {
            "from": base, "to": cur, "delta": round(cur - base, 2),
            "pct": round((cur - base) / base * 100, 1) if base else None,
        }
    return out
