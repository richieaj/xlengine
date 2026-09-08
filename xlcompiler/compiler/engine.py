"""
engine.py — high-level API: load workbook, set levers, read outputs

Usage:
    from compiler.engine import ModelEngine
    eng = ModelEngine.load("IESS2047_Version_3.0.xlsx")
    eng.set_lever("User-defined drivers", "I70", 549.10)   # custom solar
    flows = eng.read_flows()                                 # all Flows edges
"""

from .workbook_model import WorkbookModel
from .evaluator import Evaluator, RangeRef
from openpyxl.utils import column_index_from_string
import re


class ModelEngine:
    def __init__(self, model):
        self.m = model
        self.ev = Evaluator(model)

    @classmethod
    def load(cls, path, verbose=True):
        model = WorkbookModel.load(path, verbose=verbose)
        return cls(model)

    def _a1(self, a1):
        a1 = a1.replace("$","")
        mt = re.match(r"^([A-Z]+)(\d+)$", a1)
        return int(mt.group(2)), column_index_from_string(mt.group(1))

    def set_lever(self, sheet, a1, value):
        r, c = self._a1(a1)
        self.ev.set_override(sheet, r, c, value)

    def clear_levers(self):
        self.ev.clear_overrides()

    def scoped_levers(self):
        """Context manager: any set_lever() calls made inside are undone
        automatically on exit, leaving the engine exactly as it was before —
        use for "what-if" computations that must not leak into later calls.
        Usage: `with eng.scoped_levers(): eng.set_lever(...); ...`"""
        return self.ev.scoped_overrides()

    def read_cell(self, sheet, a1):
        r, c = self._a1(a1)
        return self.ev.eval_cell(sheet, r, c)

    def read_flows(self, flows_sheet="Flows", from_col="C", to_col="D",
                   year_cols=("F","G","H","I","J","K","L","M"),
                   first_row=6, max_rows=200):
        """Read all Flows edges. Returns list of {from,to,values}."""
        fc = column_index_from_string(from_col)
        tc = column_index_from_string(to_col)
        ycs = [column_index_from_string(y) for y in year_cols]

        edges = []
        for r in range(first_row, first_row + max_rows):
            frm = self.ev.eval_cell(flows_sheet, r, fc)
            to  = self.ev.eval_cell(flows_sheet, r, tc)
            if not frm or str(frm).strip() == "":
                if not to or str(to).strip() == "":
                    continue
            vals = [self.ev.eval_cell(flows_sheet, r, yc) for yc in ycs]
            edges.append({
                "row": r,
                "from": str(frm).strip() if frm else "",
                "to": str(to).strip() if to else "",
                "values": [round(float(v),6) if isinstance(v,(int,float)) else 0.0 for v in vals],
            })
        return edges
