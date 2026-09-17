"""SUPERSEDED by tools/excel_parity.py (2026-09-17).

This compares engine output against Excel's cached values for ONE sheet
("Flows"), ONE column (L, the 2047 year), ~120 rows, at a fixed 0.5 absolute
tolerance, with a hardcoded default path into a D:/2047-old/ tree that no
longer exists. excel_parity.py does the same comparison across every sheet and
every formula cell, with relative+absolute tolerances and a defect taxonomy:

    python tools/excel_parity.py --sheet Flows

Kept only because the "78/78 flow edges match Excel within 0.5 Mtoe" headline
in CLAUDE_CODE_PROJECT_CONTEXT.md came from this script. Prefer the new tool.
"""

import sys
sys.path.insert(0, '.')
from compiler.engine import ModelEngine
from compiler.evaluator import Evaluator
from openpyxl.utils import column_index_from_string

path = sys.argv[1] if len(sys.argv) > 1 else 'D:/2047-old/compiler/workbook/IESS2047_Version_3.0.xlsx'
eng = ModelEngine.load(path, verbose=False)

m = eng.m
ev = Evaluator(m)
ev.MAX_DEPTH = 200
FROM_C = column_index_from_string('C')
TO_C = column_index_from_string('D')
YEAR_COLS = [column_index_from_string(x) for x in ('F','G','H','I','J','K','L','M')]

edges = []
for r in range(6,126):
    frm = ev.eval_cell('Flows', r, FROM_C)
    to = ev.eval_cell('Flows', r, TO_C)
    if (not frm or str(frm).strip() == '') and (not to or str(to).strip() == ''):
        continue
    vals = [ev.eval_cell('Flows', r, yc) for yc in YEAR_COLS]
    edges.append((r, frm, to, vals))

checks = 0
mism = 0
nonzero = 0
rows = []
for r, frm, to, vals in edges:
    comp = vals[6] if len(vals) > 6 and isinstance(vals[6], (int, float)) else 0
    if abs(comp) > 1e-12:
        nonzero += 1
    cc = m.get_cell('Flows', r, 12)
    cached = cc.value if cc else None
    if isinstance(cached, (int, float)):
        checks += 1
        if abs(cached - comp) >= 0.5:
            mism += 1
        else:
            rows.append(r)
print('edges_total=', len(edges))
print('checks_numeric_cached=', checks)
print('matches=', checks - mism)
print('mismatches=', mism)
print('nonzero_compiler_2047=', nonzero)
print('rows_matching=', rows)
