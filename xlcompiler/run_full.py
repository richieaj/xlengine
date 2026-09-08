"""
run_full.py — load, print all years, run custom lever test, AND report
any formula constructs the engine could not evaluate (self-diagnosis).
"""
import sys, time
sys.path.insert(0, ".")
from compiler.engine import ModelEngine

PATH = sys.argv[1] if len(sys.argv) > 1 else "D:/2047-old/compiler/workbook/IESS2047_Version_3.0.xlsx"

print("Loading model...", flush=True)
t = time.time()
eng = ModelEngine.load(PATH, verbose=True)
print(f"Loaded in {time.time()-t:.1f}s\n", flush=True)

YEAR_LABELS = ["Base","2022","2027","2032","2037","2042","2047","Target"]

def read_flows():
    return eng.read_flows(flows_sheet="Flows", from_col="C", to_col="D",
        year_cols=("F","G","H","I","J","K","L","M"), first_row=6, max_rows=120)

print("="*104)
print("ALL YEARS — every Flows edge")
print("="*104)
edges = read_flows()
hdr = f"{'From':<22}{'To':<20}" + "".join(f"{y:>9}" for y in YEAR_LABELS)
print(hdr); print("-"*len(hdr))
for e in edges:
    line = f"{e['from'][:21]:<22}{e['to'][:19]:<20}"
    for v in e['values']:
        line += f"{v:>9.2f}" if isinstance(v,(int,float)) else f"{'#GAP':>9}"
    print(line)

# ── ENGINE SELF-DIAGNOSIS ─────────────────────────────────────────────────────
print("\n" + "="*104)
print("ENGINE GAP REPORT (formula constructs the engine could not evaluate)")
print("="*104)
print(eng.ev.report_gaps())
print("\nDONE. Paste the gap report back — it names the constructs to fix.")