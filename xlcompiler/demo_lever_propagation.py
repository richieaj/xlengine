"""
demo_lever_propagation.py — proves the Control sheet's "Custom Pathway" lever
panel (Level of Ambition 1-4 sliders, as shown in the workbook UI) actually
drives the compiler's outputs, with no Excel involved.

Two switches must be set for the lever panel to be "live":
  - 'Target Year Input'!E10 = 1   ("Pre-defined trajectories" / lever-driven method,
                                    as opposed to 2 = direct numeric entry on the
                                    User-defined drivers sheet)
  - 'IESS V3 Main Sheet'!E12 = 0  ("0: None" = Custom Pathway, as opposed to a
                                    preset 1-4 "Example Pathway")

Each lever lives in the Control sheet's "YOUR CHOICE" column (E), one row per
named lever (e.g. row 13 = Solar Photovoltaic, row 15 = Onshore Wind). Moving
a lever from level 1 to level 4 should change that technology's downstream
Flow output — this script proves it does, for a sample of levers across
different categories.

Usage:
    python demo_lever_propagation.py "../workbook/IESS2047_Version_3.0.xlsx"
"""
import sys
sys.path.insert(0, ".")
from compiler.engine import ModelEngine

PATH = sys.argv[1] if len(sys.argv) > 1 else "workbook/IESS2047_Version_3.0.xlsx"

YEAR_LABELS = ["Base", "2022", "2027", "2032", "2037", "2042", "2047", "Target"]

# (Control sheet row, lever name, Flow row to watch, Flow description)
LEVERS = [
    (13, "Solar Photovoltaic",       15, "Solar -> Solar PV"),
    (15, "Onshore Wind",             22, "Wind -> Onshore Wind"),
    (27, "Domestic Gas Production",  10, "Gas Production -> Natural Gas"),
    (28, "Domestic Coal Production",  6, "Coal Production -> Coal"),
]


def flow_row(eng, row):
    edges = eng.read_flows()
    for e in edges:
        if e["row"] == row:
            return e["values"]
    return None


def main():
    print("Loading model...", flush=True)
    eng = ModelEngine.load(PATH, verbose=False)

    # Put the workbook into "Custom Pathway, lever-driven" mode.
    eng.set_lever("Target Year Input", "E10", 1)     # 1: Pre-defined trajectories
    eng.set_lever("IESS V3 Main Sheet", "E12", 0)     # 0: None (Custom Pathway)

    print("\n" + "=" * 100)
    print("LEVER PROPAGATION CHECK — Level 1 vs Level 4 on the Control sheet")
    print("=" * 100)

    all_ok = True
    for ctrl_row, lever_name, flow_row_idx, flow_desc in LEVERS:
        eng.set_lever("Control", f"E{ctrl_row}", 1)
        v1 = flow_row(eng, flow_row_idx)

        eng.set_lever("Control", f"E{ctrl_row}", 4)
        v4 = flow_row(eng, flow_row_idx)

        changed = any(abs((a or 0) - (b or 0)) > 1e-6 for a, b in zip(v1, v4))
        status = "OK  (lever changes output)" if changed else "FAIL (no change detected)"
        all_ok = all_ok and changed

        print(f"\nLever: {lever_name} (Control!E{ctrl_row})  ->  watching: {flow_desc} (Flows row {flow_row_idx})")
        print(f"  [{status}]")
        hdr = "    " + "".join(f"{y:>10}" for y in YEAR_LABELS)
        print(hdr)
        print("    Level 1 " + "".join(f"{v:>10.2f}" for v in v1))
        print("    Level 4 " + "".join(f"{v:>10.2f}" for v in v4))

    print("\n" + "=" * 100)
    print("RESULT:", "ALL LEVERS PROPAGATE CORRECTLY" if all_ok else "SOME LEVERS DID NOT PROPAGATE — investigate")
    print("=" * 100)


if __name__ == "__main__":
    main()
