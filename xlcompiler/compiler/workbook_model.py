"""
workbook_model.py — in-memory model of the entire workbook

Loads the xlsx ONCE with openpyxl, captures everything the evaluator needs:
  - every cell's formula AND cached value
  - every named Excel table (ListObject): name, sheet, range, columns
  - workbook-level named ranges
  - worksheet-scoped named ranges (this.year, Year.Matrix, etc.)

This is pure structure extraction — no evaluation happens here.
"""

import openpyxl
from openpyxl.utils import get_column_letter, column_index_from_string, range_boundaries
from dataclasses import dataclass, field


@dataclass
class TableModel:
    """A named Excel table (ListObject)."""
    name:        str
    sheet:       str
    min_col:     int
    min_row:     int
    max_col:     int
    max_row:     int
    columns:     dict          # column_name → absolute column index
    header_row:  int

    def column_range(self, col_name: str) -> tuple | None:
        """Return (sheet, col_idx, first_data_row, last_data_row) for a column."""
        col_idx = self.columns.get(col_name)
        if col_idx is None:
            # Try case-insensitive / stripped match
            for k, v in self.columns.items():
                if str(k).strip().lower() == str(col_name).strip().lower():
                    col_idx = v
                    break
        if col_idx is None:
            return None
        return (self.sheet, col_idx, self.header_row + 1, self.max_row)


@dataclass
class NameModel:
    """A named range — workbook or worksheet scoped."""
    name:       str
    sheet:      str | None       # None = workbook-level
    refers_to:  str              # raw refers_to string
    is_error:   bool = False


@dataclass
class CellModel:
    """One cell: its formula (if any) and cached value."""
    sheet:   str
    row:     int
    col:     int
    formula: str | None
    value:   object              # cached value from the workbook


class WorkbookModel:
    def __init__(self):
        self.cells:        dict[tuple, CellModel] = {}    # (sheet,row,col) → CellModel
        self.tables:       dict[str, TableModel]  = {}    # lower(name) → TableModel
        self.names:        dict[str, NameModel]   = {}    # workbook-level
        self.sheet_names:  dict[str, dict]        = {}    # sheet → {lower(name): NameModel}
        self.sheets:       list[str]              = []

    # ── Loading ───────────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: str, verbose: bool = True, use_cache: bool = True):
        """
        Load a workbook. On first load, parses the xlsx (slow) and caches the
        result to <path>.compiled.pkl. Subsequent loads read the cache (fast)
        unless the xlsx is newer than the cache.
        """
        import os, pickle

        cache_path = path + ".compiled.pkl"
        if use_cache and os.path.exists(cache_path):
            xlsx_mtime  = os.path.getmtime(path)
            cache_mtime = os.path.getmtime(cache_path)
            if cache_mtime >= xlsx_mtime:
                if verbose: print(f"Loading cached model from {cache_path} ...")
                try:
                    with open(cache_path, "rb") as f:
                        m = pickle.load(f)
                    if verbose:
                        print(f"  {len(m.cells)} cells, {len(m.tables)} tables (from cache)")
                    return m
                except Exception as e:
                    if verbose: print(f"  cache load failed ({e}), reparsing ...")

        m = cls._parse(path, verbose)

        if use_cache:
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(m, f)
                if verbose: print(f"  cached model → {cache_path}")
            except Exception as e:
                if verbose: print(f"  cache save failed ({e})")

        return m

    @classmethod
    def _parse(cls, path: str, verbose: bool = True):
        m = cls()

        if verbose: print(f"Opening {path} ...")
        # Two passes: formulas, then cached values
        wb_f = openpyxl.load_workbook(path, data_only=False, read_only=False)
        wb_v = openpyxl.load_workbook(path, data_only=True,  read_only=True)

        m.sheets = wb_f.sheetnames
        if verbose: print(f"  {len(m.sheets)} sheets")

        # ── Cells ──────────────────────────────────────────────────────────────
        # IMPORTANT: wb_v is read_only. Calling ws_v.cell() repeatedly re-parses
        # the sheet XML every time (accidentally O(n^2) and effectively hangs on
        # large sheets). Instead we iterate each value-sheet ONCE into a dict.
        cell_count = 0
        n_sheets = len(wb_f.sheetnames)
        for si, sheet in enumerate(wb_f.sheetnames):
            ws_f = wb_f[sheet]

            # Build cached-value lookup for this sheet in ONE pass
            value_lookup = {}
            if sheet in wb_v.sheetnames:
                ws_v = wb_v[sheet]
                for vrow in ws_v.iter_rows():
                    for vc in vrow:
                        if vc.value is not None:
                            value_lookup[(vc.row, vc.column)] = vc.value

            sheet_cells = 0
            for row in ws_f.iter_rows():
                for c in row:
                    if c.value is None:
                        continue
                    is_formula = isinstance(c.value, str) and c.value.startswith("=")
                    cached = value_lookup.get((c.row, c.column))
                    m.cells[(sheet, c.row, c.column)] = CellModel(
                        sheet=sheet, row=c.row, col=c.column,
                        formula=c.value if is_formula else None,
                        value=cached if is_formula else c.value,
                    )
                    cell_count += 1
                    sheet_cells += 1
            if verbose:
                print(f"    [{si+1}/{n_sheets}] {sheet:<28} {sheet_cells:>6} cells "
                      f"(total {cell_count})", flush=True)
        if verbose: print(f"  {cell_count} non-empty cells")

        # ── Tables (ListObjects) ────────────────────────────────────────────────
        tables_found = 0
        for sheet in wb_f.sheetnames:
            ws = wb_f[sheet]
            for tbl in getattr(ws, "tables", {}).values():
                ref = tbl.ref                       # e.g. "C192:O195"
                min_col, min_row, max_col, max_row = range_boundaries(ref)
                # Column headers are in the header row (min_row)
                columns = {}
                for col in range(min_col, max_col + 1):
                    hdr = ws.cell(row=min_row, column=col).value
                    if hdr is not None:
                        columns[str(hdr)] = col
                m.tables[tbl.name.lower()] = TableModel(
                    name=tbl.name, sheet=sheet,
                    min_col=min_col, min_row=min_row,
                    max_col=max_col, max_row=max_row,
                    columns=columns, header_row=min_row,
                )
                tables_found += 1

        # FALLBACK: if openpyxl returned no tables (happens in some load modes),
        # read the table definitions straight from the xlsx zip. This is general —
        # it parses the OOXML table parts that every .xlsx contains.
        if tables_found == 0:
            tables_found = m._load_tables_from_zip(path, verbose)

        if verbose: print(f"  {len(m.tables)} named tables")

        # ── Workbook-level names ─────────────────────────────────────────────────
        for name, defn in wb_f.defined_names.items():
            refers = defn.value or ""
            is_err = "#REF" in refers or "#NAME" in refers
            m.names[name.lower()] = NameModel(
                name=name, sheet=None, refers_to=refers, is_error=is_err,
            )

        # ── Worksheet-scoped names ───────────────────────────────────────────────
        for sheet in wb_f.sheetnames:
            ws = wb_f[sheet]
            local = {}
            for name, defn in getattr(ws, "defined_names", {}).items():
                refers = defn.value or ""
                is_err = "#REF" in refers or "#NAME" in refers
                local[name.lower()] = NameModel(
                    name=name, sheet=sheet, refers_to=refers, is_error=is_err,
                )
            if local:
                m.sheet_names[sheet] = local
        if verbose:
            total_local = sum(len(v) for v in m.sheet_names.values())
            print(f"  {len(m.names)} workbook names, {total_local} worksheet-scoped names")

        wb_f.close()
        wb_v.close()
        return m

    # ── Accessors ─────────────────────────────────────────────────────────────
    def _load_tables_from_zip(self, path, verbose=False):
        """
        Read table (ListObject) definitions directly from the xlsx zip.
        General OOXML parsing — independent of openpyxl's load mode.
        Maps table → sheet → range, resolving header names from loaded cells.
        """
        import zipfile, re
        from xml.etree import ElementTree as ET

        count = 0
        try:
            z = zipfile.ZipFile(path)
        except Exception as e:
            if verbose: print(f"    zip table fallback failed to open: {e}")
            return 0

        names = z.namelist()
        sheet_file_to_name = {}
        try:
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            wbxml = ET.fromstring(z.read("xl/workbook.xml"))
            wbrels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rid_to_target = {rel.get("Id"): rel.get("Target") for rel in wbrels}
            for sh in wbxml.find("m:sheets", ns):
                nm = sh.get("name")
                rid = sh.get(R)
                target = rid_to_target.get(rid, "")
                fname = target.split("/")[-1]
                sheet_file_to_name[fname] = nm
        except Exception as e:
            if verbose: print(f"    zip table fallback: workbook map failed: {e}")

        for relname in [n for n in names if re.match(r"xl/worksheets/_rels/sheet\d+\.xml\.rels", n)]:
            sheet_file = relname.split("/")[-1].replace(".rels", "")
            sheet_name = sheet_file_to_name.get(sheet_file)
            if not sheet_name:
                continue
            try:
                rels = ET.fromstring(z.read(relname))
            except Exception:
                continue
            for rel in rels:
                tgt = rel.get("Target", "")
                if "tables/" not in tgt:
                    continue
                tbl_file = "xl/tables/" + tgt.split("tables/")[-1]
                if tbl_file not in names:
                    continue
                try:
                    tdef = ET.fromstring(z.read(tbl_file))
                except Exception:
                    continue
                tname = tdef.get("displayName") or tdef.get("name")
                ref = tdef.get("ref")
                if not tname or not ref:
                    continue
                min_col, min_row, max_col, max_row = range_boundaries(ref)
                columns = {}
                for col in range(min_col, max_col + 1):
                    cell = self.cells.get((sheet_name, min_row, col))
                    if cell is not None and cell.value is not None:
                        columns[str(cell.value)] = col
                self.tables[tname.lower()] = TableModel(
                    name=tname, sheet=sheet_name,
                    min_col=min_col, min_row=min_row,
                    max_col=max_col, max_row=max_row,
                    columns=columns, header_row=min_row,
                )
                count += 1

        z.close()
        if verbose: print(f"    zip fallback recovered {count} tables")
        return count

    def get_cell(self, sheet: str, row: int, col: int) -> CellModel | None:
        return self.cells.get((sheet, row, col))

    def get_table(self, name: str) -> TableModel | None:
        return self.tables.get(name.lower())

    def get_name(self, name: str, sheet: str | None = None) -> NameModel | None:
        # Worksheet-scoped first, then workbook-level. `key` is computed once: this is
        # called ~200k times per model pass and used to lower() twice per call.
        key = name.lower()
        if sheet and sheet in self.sheet_names:
            n = self.sheet_names[sheet].get(key)
            if n: return n
        return self.names.get(key)