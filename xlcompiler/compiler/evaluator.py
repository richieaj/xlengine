"""
evaluator.py — formula evaluator for the IESS workbook

Handles the constructs found in the audit:
  - INDIRECT(string)  → resolves structured table refs AND 'sheet'!range refs
  - structured table refs: TableName[Column], TableName[Vector], TableName[#Headers]
  - INDEX(array, row, [col])
  - MATCH(value, array, 0)
  - IFERROR(expr, fallback)
  - CHOOSE(n, a, b, ...)
  - IF, SUM, SUMIF, SUMIFS, AND, OR, MAX, MIN, ABS, AVERAGE, EXP, LN, etc.
  - string concatenation with &
  - worksheet-scoped names (this.year, Year.Matrix, ...)
  - workbook-level names (Unit.mtoe, predefined.scenario, ...)

Strategy: this is a recursive-descent evaluator over a tokenized formula.
It evaluates lazily — when a cell is requested, it evaluates that cell's
formula, recursing into dependencies, with memoization.
"""

import re
import math
import contextlib
from functools import lru_cache
from openpyxl.utils import (
    get_column_letter, column_index_from_string, range_boundaries
)


class EvalError(Exception):
    pass


# Sentinel for a formula the engine could not evaluate.
# Distinct from a real 0 — lets us find engine gaps instead of hiding them.
class _Error:
    _inst = None
    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst
    def __repr__(self): return "#ENGINE_GAP"
    def __bool__(self): return False
    def __float__(self): return 0.0

ERROR = _Error()


_A1_RE = re.compile(r"^([A-Z]+)(\d+)$")
# Matched on every identifier token (~200k times per request); was an uncompiled
# inline pattern paying a re-module cache lookup per call.
_CELLREF_RE = re.compile(r"^\$?[A-Za-z]{1,3}\$?\d+$")


@lru_cache(maxsize=None)
def _a1_to_rc_pure(a1):
    """A1 string -> (row, col). Pure in `a1` — it reads no cell values and no override
    state, so memoising it cannot carry a computed value across a lever change. ~132k
    calls per request over a small alphabet of distinct strings."""
    a1 = a1.replace("$", "")
    mt = _A1_RE.match(a1)
    c = column_index_from_string(mt.group(1))
    r = int(mt.group(2))
    return r, c


# Ranges above this many cells are built directly rather than cached: whole-column
# references on the big sheets (Grid_Balance_V2 alone is 184k cells) would otherwise
# dominate memory for no benefit.
_RANGE_CACHE_MAX_CELLS = 4096


@lru_cache(maxsize=None)
def _range_cells_pure(sheet, r1, c1, r2, c2):
    """Immutable cell tuple for a range — pure in the coordinates. Held as a tuple so
    it can never be mutated in place; callers receive a fresh list copy, which keeps
    RangeRef.cells a list as every consumer expects."""
    return tuple(
        (sheet, r, c)
        for r in range(min(r1, r2), max(r1, r2) + 1)
        for c in range(min(c1, c2), max(c1, c2) + 1)
    )


# A range result: list of (sheet, row, col) cells, plus shape
class RangeRef:
    def __init__(self, cells, nrows, ncols):
        self.cells = cells      # flat list of (sheet,row,col)
        self.nrows = nrows
        self.ncols = ncols


class Evaluator:
    def __init__(self, model):
        self.m = model
        self._cache = {}        # (sheet,row,col) → value
        # Formula text (post "=" strip) → tokens list. Pure/deterministic — a
        # formula's tokens never depend on override/lever state, only on its
        # own text — so this is NEVER cleared by set_override/clear_overrides/
        # scoped_overrides. It only skips re-lexing, never carries a computed
        # value across a lever change, so it can't reintroduce a staleness bug.
        self._token_cache = {}
        self._overrides = {}    # (sheet,row,col) → value  (lever inputs)
        self._stack = set()     # cycle detection
        self._depth = 0         # recursion depth counter
        self.MAX_DEPTH = 200    # hard ceiling — prevents runaway chains
        self._unevaluated = []  # (sheet,row,col,reason) — engine gaps, for reporting
        self._circular_seed = 0 # deterministic seed for circular refs

    def report_gaps(self, limit=40):
        """Return a summary of formulas the engine could not evaluate.
        This is the compiler's self-diagnosis — which constructs need work."""
        if not self._unevaluated:
            return "No engine gaps — every formula evaluated."
        lines = [f"{len(self._unevaluated)} unevaluated formula cells (engine gaps):"]
        # Group by reason to see PATTERNS, not individual cells
        from collections import Counter
        reasons = Counter(r for _,_,_,r in self._unevaluated)
        for reason, n in reasons.most_common(limit):
            lines.append(f"  {n:>5}x  {reason}")
        return "\n".join(lines)

    # ── Public API ──────────────────────────────────────────────────────────
    def set_override(self, sheet, row, col, value):
        """Inject a lever value. Clears cache so downstream recomputes.

        Re-writing the SAME value is a no-op and leaves the cache valid: nothing
        downstream can depend on a write that changed nothing. This guard is not an
        optimisation of the invalidation rule — when a value genuinely changes the full
        clear still happens, exactly as before.

        It matters because callers write every lever on every request to keep results
        independent of request history (see _apply_levels in ui/app.py, which writes all
        51 levers plus E12). Without the guard, a request whose levers are identical to
        the previous one — a tab switch, re-clicking the pathway that is already active,
        the initial setScenario on page load — cleared the cache 52 times and paid a
        measured ~2.9s full recompute instead of ~0.004s.
        """
        key = (sheet, row, col)
        if key in self._overrides and self._overrides[key] == value:
            return
        self._overrides[key] = value
        self._cache.clear()

    def clear_overrides(self):
        self._overrides.clear()
        self._cache.clear()

    @contextlib.contextmanager
    def scoped_overrides(self):
        """Run code that may call set_override/clear_overrides freely, with
        a guarantee that whatever overrides were in effect before this call
        are restored exactly afterward — regardless of what happened inside,
        including exceptions. For "what-if" computations (e.g. a hypothetical
        scenario snapshot used only for diffing) that must never leak into
        the caller's real, persistent lever state. General-purpose: any
        consumer of ModelEngine, for any workbook, can use this — nothing
        here is specific to IESS2047 or to any particular lever."""
        saved = dict(self._overrides)
        try:
            yield
        finally:
            self._overrides = saved
            self._cache.clear()

    def eval_cell(self, sheet, row, col):
        key = (sheet, row, col)
        if key in self._overrides:
            return self._overrides[key]
        if key in self._cache:
            return self._cache[key]
        if key in self._stack:
            return self._circular_seed   # circular — deterministic seed
        if self._depth > self.MAX_DEPTH:
            return self._circular_seed

        cell = self.m.get_cell(sheet, row, col)
        if cell is None:
            return 0

        # DETERMINISTIC RULE:
        #   formula cell  → ALWAYS evaluate the formula. The cached value is
        #                   Excel's last-saved scratch state and is never a
        #                   valid result for a compiler.
        #   no formula    → input/constant. Use the stored value.
        if cell.formula is None:
            return cell.value if cell.value is not None else 0

        self._stack.add(key)
        self._depth += 1
        try:
            result = self._eval_formula(cell.formula, sheet, row, col)
        except EvalError as e:
            # A formula cell that cannot be evaluated is an ENGINE GAP, not a
            # value. Do NOT substitute the stale cache — that would poison the
            # graph with last-saved scratch numbers. Surface it.
            self._unevaluated.append((sheet, row, col, str(e)))
            result = ERROR
        finally:
            self._stack.discard(key)
            self._depth -= 1

        self._cache[key] = result
        return result

    # ── Formula evaluation ────────────────────────────────────────────────────
    def _eval_formula(self, formula, sheet, row, col):
        expr = formula[1:] if formula.startswith("=") else formula
        tokens = self._token_cache.get(expr)
        if tokens is None:
            tokens = self._tokenize(expr)
            self._token_cache[expr] = tokens
        pos = [0]
        val = self._parse_expr(tokens, pos, sheet, row, col)
        return self._scalar(val)

    # ── Tokenizer ───────────────────────────────────────────────────────────
    _TOKEN_RE = re.compile(r"""
        (?P<str>"(?:[^"]|"")*")              |
        (?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?)  |
        (?P<op><=|>=|<>|[-+*/&^<>=])         |
        (?P<percent>%)                        |
        (?P<lparen>\()                        |
        (?P<rparen>\))                        |
        (?P<comma>,)                          |
        (?P<colon>:)                          |
        (?P<sqopen>\[)                        |
        (?P<sqclose>\])                       |
        (?P<bang>!)                           |
        (?P<sheetq>'(?:[^']|'')*')           |
        (?P<cellabs>\$?[A-Z]{1,3}\$?\d+(?![A-Za-z0-9_\.]))  |
        (?P<ident>\#?[A-Za-z_\\.][A-Za-z0-9_\\.]*)
    """, re.VERBOSE)

    def _tokenize(self, expr):
        tokens = []
        i = 0
        while i < len(expr):
            if expr[i] in " \t\n":
                i += 1
                continue
            mt = self._TOKEN_RE.match(expr, i)
            if not mt:
                i += 1
                continue
            kind = mt.lastgroup
            text = mt.group()
            tokens.append((kind, text))
            i = mt.end()
        return tokens

    # ── Recursive descent parser ──────────────────────────────────────────────
    # expr := compare
    # compare := concat (('<'|'>'|...) concat)*
    # concat := add ('&' add)*
    # add := mul (('+'|'-') mul)*
    # mul := pow (('*'|'/') pow)*
    # pow := unary ('^' unary)*
    # unary := '-' unary | primary
    # primary := num | str | func(...) | name | cell | range | '(' expr ')'

    def _peek(self, tokens, pos):
        # Hottest function in the engine (~4M calls per request). The previous form
        # re-evaluated len(tokens) on every call; indexing and catching IndexError is
        # behaviourally identical for the non-negative positions the parser produces,
        # and removes ~4M len() calls per request.
        try:
            return tokens[pos[0]]
        except IndexError:
            return (None, None)

    def _next(self, tokens, pos):
        t = tokens[pos[0]]
        pos[0] += 1
        return t

    def _parse_expr(self, tokens, pos, sheet, row, col):
        return self._parse_compare(tokens, pos, sheet, row, col)

    def _parse_compare(self, tokens, pos, sheet, row, col):
        left = self._parse_concat(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] in ("<",">","<=",">=","=","<>"):
            op = self._next(tokens, pos)[1]
            right = self._parse_concat(tokens, pos, sheet, row, col)
            ls, rs = self._scalar(left), self._scalar(right)
            # ERROR in a comparison → treat as not-equal / false
            if ls is ERROR or rs is ERROR:
                left = (op == "<>")
                continue
            # numeric compare when both look numeric, else string compare
            ln, rn = self._num(ls), self._num(rs)
            both_num = ln is not ERROR and rn is not ERROR and \
                       isinstance(ls,(int,float,bool)) and isinstance(rs,(int,float,bool))
            if both_num:
                l, r = ln, rn
            else:
                l, r = self._to_str(ls).lower(), self._to_str(rs).lower()
            if   op == "<":  left = l <  r
            elif op == ">":  left = l >  r
            elif op == "<=": left = l <= r
            elif op == ">=": left = l >= r
            elif op == "=":  left = l == r
            elif op == "<>": left = l != r
        return left

    def _parse_concat(self, tokens, pos, sheet, row, col):
        left = self._parse_add(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] == "&":
            self._next(tokens, pos)
            right = self._parse_add(tokens, pos, sheet, row, col)
            ctx = (sheet, row, col)
            left = self._to_str(self._scalar(left, ctx)) + self._to_str(self._scalar(right, ctx))
        return left

    def _parse_add(self, tokens, pos, sheet, row, col):
        left = self._parse_mul(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] in ("+","-"):
            op = self._next(tokens, pos)[1]
            right = self._parse_mul(tokens, pos, sheet, row, col)
            l, r = self._numz(left), self._numz(right)
            left = l + r if op == "+" else l - r
        return left

    def _parse_mul(self, tokens, pos, sheet, row, col):
        left = self._parse_pow(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] in ("*","/"):
            op = self._next(tokens, pos)[1]
            right = self._parse_pow(tokens, pos, sheet, row, col)
            l, r = self._numz(left), self._numz(right)
            left = l * r if op == "*" else (l / r if r != 0 else 0)
        return left

    def _parse_pow(self, tokens, pos, sheet, row, col):
        left = self._parse_unary(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] == "^":
            self._next(tokens, pos)
            right = self._parse_unary(tokens, pos, sheet, row, col)
            base, exp = self._numz(left), self._numz(right)
            try:
                v = base ** exp
                # Excel has no complex numbers; guard against them and inf/nan
                if isinstance(v, complex):
                    v = 0
                left = v
            except (ZeroDivisionError, ValueError, OverflowError):
                left = 0
        return left

    def _parse_unary(self, tokens, pos, sheet, row, col):
        if self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] == "-":
            self._next(tokens, pos)
            return -self._numz(self._parse_unary(tokens, pos, sheet, row, col))
        if self._peek(tokens, pos)[0] == "op" and self._peek(tokens, pos)[1] == "+":
            self._next(tokens, pos)
            return self._parse_unary(tokens, pos, sheet, row, col)
        return self._parse_postfix(tokens, pos, sheet, row, col)

    def _parse_postfix(self, tokens, pos, sheet, row, col):
        """Handle postfix operators like % (percentage)."""
        left = self._parse_primary(tokens, pos, sheet, row, col)
        while self._peek(tokens, pos)[0] == "percent":
            self._next(tokens, pos)
            # Percentage: multiply by 1/100
            left = self._numz(left) / 100.0
        return left

    def _parse_primary(self, tokens, pos, sheet, row, col):
        kind, text = self._peek(tokens, pos)

        if kind == "num":
            self._next(tokens, pos)
            return float(text)

        if kind == "str":
            self._next(tokens, pos)
            return text[1:-1].replace('""', '"')

        if kind == "lparen":
            self._next(tokens, pos)
            v = self._parse_expr(tokens, pos, sheet, row, col)
            if self._peek(tokens, pos)[0] == "rparen":
                self._next(tokens, pos)
            return v

        if kind == "sheetq":
            # 'Sheet Name'!ref
            return self._parse_sheet_ref(tokens, pos, sheet, row, col)

        if kind in ("ident", "cellabs"):
            # Could be: function call, cell ref, range, structured table ref, or name
            return self._parse_ident(tokens, pos, sheet, row, col)

        # Unknown — skip
        self._next(tokens, pos)
        return 0

    # ── Identifier handling (functions / cells / names / tables) ──────────────
    FUNCTIONS = {
        "SUM","IF","CHOOSE","INDEX","MATCH","IFERROR","AND","OR","SUMIF","SUMIFS",
        "PMT","AVERAGE","MAX","MIN","SUMPRODUCT","SUBTOTAL","VLOOKUP","TEXT",
        "EXP","LN","ABS","ROUNDDOWN","ROUNDUP","LEFT","FIND","MOD","ROW","INDIRECT",
    }

    def _parse_ident(self, tokens, pos, sheet, row, col):
        kind, text = self._next(tokens, pos)
        upper = text.upper()

        # Function call?
        if self._peek(tokens, pos)[0] == "lparen" and upper in self.FUNCTIONS:
            if upper == "IFERROR":
                # Excel evaluates IFERROR's first argument lazily, trapping any
                # error raised within it. The rest of this parser evaluates
                # function arguments eagerly (in _parse_args), which would let
                # an error from inside arg 0 escape before IFERROR's own
                # dispatch body ever runs. Split the raw tokens first instead.
                self._next(tokens, pos)  # consume '('
                raw_args = self._split_call_args(tokens, pos)
                try:
                    val = self._scalar(self._parse_expr(raw_args[0], [0], sheet, row, col))
                    if val is ERROR:
                        raise EvalError("propagated")
                    return val
                except EvalError:
                    if len(raw_args) > 1:
                        return self._scalar(self._parse_expr(raw_args[1], [0], sheet, row, col))
                    return 0
            if upper == "IF":
                # Excel evaluates only the branch selected by the condition —
                # the other branch is never touched. The parser's default
                # (_parse_args) evaluates every argument eagerly before
                # dispatch, which can force evaluation of a branch Excel would
                # never reach. For self-referential trend/interpolation
                # formulas (common in this workbook: an early-year column's
                # unreached branch references a later-year column, which in
                # turn references the early-year column in ITS unreached
                # branch) eager evaluation manufactures a circular reference
                # that doesn't exist in Excel's own lazy evaluation, silently
                # substituting the evaluator's circular-fallback value. Split
                # raw tokens and evaluate only the selected branch, same
                # technique already used for IFERROR above.
                self._next(tokens, pos)  # consume '('
                raw_args = self._split_call_args(tokens, pos)
                cond = self._scalar(self._parse_expr(raw_args[0], [0], sheet, row, col))
                if cond:
                    if len(raw_args) > 1:
                        return self._scalar(self._parse_expr(raw_args[1], [0], sheet, row, col))
                    return True
                else:
                    if len(raw_args) > 2:
                        return self._scalar(self._parse_expr(raw_args[2], [0], sheet, row, col))
                    return False
            args = self._parse_args(tokens, pos, sheet, row, col)
            return self._call_function(upper, args, sheet, row, col)

        # Structured table ref?  TableName[Column]
        if self._peek(tokens, pos)[0] == "sqopen":
            return self._parse_table_ref(text, tokens, pos, sheet, row, col)

        # Cross-sheet ref?  Sheet!ref  (dotted sheet names like IV.a)
        if self._peek(tokens, pos)[0] == "bang":
            self._next(tokens, pos)  # consume !
            return self._parse_ref_after_sheet(text, tokens, pos, sheet, row, col)

        # Named range takes priority over cell-pattern (some names look like cells)
        nm = self.m.get_name(text, sheet)
        if nm is not None:
            return self._resolve_name(nm, sheet)

        # Plain cell address on current sheet (tokenized as cellabs OR ident)?
        # The tokenizer's `ident` rule can swallow simple refs like N41, so we
        # check both token kinds against the A1 pattern.
        if kind == "cellabs" or (kind == "ident" and _CELLREF_RE.match(text)):
            r, c = self._a1_to_rc(text)
            # Range?
            if self._peek(tokens, pos)[0] == "colon":
                self._next(tokens, pos)
                _, t2 = self._next(tokens, pos)
                r2, c2 = self._a1_to_rc(t2)
                return self._make_range(sheet, r, c, r2, c2)
            return self.eval_cell(sheet, r, c)

        # Unknown identifier — return as string (could be a table token)
        return text

    def _parse_args(self, tokens, pos, sheet, row, col):
        self._next(tokens, pos)  # consume (
        args = []
        if self._peek(tokens, pos)[0] == "rparen":
            self._next(tokens, pos)
            return args
        while True:
            # Omitted argument: Excel allows e.g. INDEX(rng,,2) where the
            # blank slot between commas means "0" (whole row/column).
            if self._peek(tokens, pos)[0] in ("comma", "rparen"):
                args.append(0)
            else:
                args.append(self._parse_expr(tokens, pos, sheet, row, col))
            nk = self._peek(tokens, pos)[0]
            if nk == "comma":
                self._next(tokens, pos)
                continue
            if nk == "rparen":
                self._next(tokens, pos)
                break
            break
        return args

    def _split_call_args(self, tokens, pos):
        """Pos must point just past a call's opening '('. Splits the raw,
        UN-evaluated tokens into one sublist per argument (respecting nested
        parens/brackets) and advances pos past the matching ')'. Used by
        callers (like IFERROR) that need to evaluate arguments lazily."""
        args = []
        cur = []
        depth = 0
        if self._peek(tokens, pos)[0] == "rparen":
            self._next(tokens, pos)
            return args
        while True:
            kind, _ = self._peek(tokens, pos)
            if kind is None:
                break
            if kind in ("lparen", "sqopen"):
                depth += 1
                cur.append(self._next(tokens, pos))
            elif kind == "rparen" and depth == 0:
                self._next(tokens, pos)
                args.append(cur)
                break
            elif kind in ("rparen", "sqclose"):
                depth -= 1
                cur.append(self._next(tokens, pos))
            elif kind == "comma" and depth == 0:
                self._next(tokens, pos)
                args.append(cur)
                cur = []
            else:
                cur.append(self._next(tokens, pos))
        return args

    # ── Structured table refs: TableName[Column] ──────────────────────────────
    def _parse_table_ref(self, table_name, tokens, pos, sheet, row, col):
        self._next(tokens, pos)   # consume outer [

        # Two-part specifier: TableName[[#This Row],[ColumnName]]
        if self._peek(tokens, pos)[0] == "sqopen":
            row_spec = self._read_bracket_spec(tokens, pos)
            col_spec = None
            if self._peek(tokens, pos)[0] == "comma":
                self._next(tokens, pos)
                col_spec = self._read_bracket_spec(tokens, pos)
            if self._peek(tokens, pos)[0] == "sqclose":
                self._next(tokens, pos)
            if row_spec.strip().lower() == "#this row" and col_spec:
                rng = self._resolve_table_column(table_name, col_spec)
                return self._scalar(rng, (sheet, row, col))
            return self._resolve_table_column(table_name, col_spec or row_spec)

        # Single specifier: TableName[Column] / TableName[#Headers] / TableName[]
        # (outer '[' already consumed above)
        col_name = self._read_spec_body(tokens, pos)
        return self._resolve_table_column(table_name, col_name)

    def _read_bracket_spec(self, tokens, pos):
        """Consume a '[...]' span (including the leading '[') and return its
        text, preserving the single space between adjacent word tokens
        (so '#This' 'Row' -> '#This Row')."""
        self._next(tokens, pos)  # consume 
        return self._read_spec_body(tokens, pos)

    def _read_spec_body(self, tokens, pos):
        """Read tokens up to (and consuming) the next ']', joining adjacent
        word tokens with a space. Assumes the opening '[' is already consumed."""
        parts = []
        while self._peek(tokens, pos)[0] not in ("sqclose", None):
            _, t = self._next(tokens, pos)
            if parts and parts[-1][-1].isalnum() and t[0].isalnum():
                parts.append(" " + t)
            else:
                parts.append(t)
        if self._peek(tokens, pos)[0] == "sqclose":
            self._next(tokens, pos)
        return "".join(parts)

    def _resolve_table_column(self, table_name, col_name):
        tbl = self.m.get_table(table_name)
        if tbl is None:
            raise EvalError(f"unknown table {table_name}")
        # Structured-reference specifiers (Excel: #Data, #Headers, #All, #Totals)
        # are not column names — handle them before the per-column lookup.
        # Empty brackets (TableName[]) are how some workbooks serialize a
        # reference to the whole data body, equivalent to #Data here.
        if col_name in ("", "#Data"):
            return self._make_range(tbl.sheet, tbl.min_row + 1, tbl.min_col, tbl.max_row, tbl.max_col)
        if col_name == "#Headers":
            return self._make_range(tbl.sheet, tbl.header_row, tbl.min_col, tbl.header_row, tbl.max_col)
        if col_name == "#All":
            return self._make_range(tbl.sheet, tbl.header_row, tbl.min_col, tbl.max_row, tbl.max_col)
        cr = tbl.column_range(col_name)
        if cr is None:
            raise EvalError(f"unknown column {col_name} in {table_name}")
        tsheet, cidx, r0, r1 = cr
        return self._make_range(tsheet, r0, cidx, r1, cidx)

    # ── Sheet-qualified refs ──────────────────────────────────────────────────
    def _parse_sheet_ref(self, tokens, pos, sheet, row, col):
        _, q = self._next(tokens, pos)   # 'Sheet Name'
        sname = q[1:-1].replace("''", "'")
        if self._peek(tokens, pos)[0] == "bang":
            self._next(tokens, pos)
        return self._parse_ref_after_sheet(sname, tokens, pos, sheet, row, col)

    def _parse_ref_after_sheet(self, sname, tokens, pos, sheet, row, col):
        kind, text = self._peek(tokens, pos)
        if kind == "cellabs":
            self._next(tokens, pos)
            r, c = self._a1_to_rc(text)
            if self._peek(tokens, pos)[0] == "colon":
                self._next(tokens, pos)
                _, t2 = self._next(tokens, pos)
                r2, c2 = self._a1_to_rc(t2)
                return self._make_range(sname, r, c, r2, c2)
            return self.eval_cell(sname, r, c)
        if kind == "ident":
            # Sheet!NamedRange (worksheet-scoped)
            self._next(tokens, pos)
            nm = self.m.get_name(text, sname)
            if nm:
                return self._resolve_name(nm, sname)
        return 0

    # ── Name resolution ─────────────────────────────────────────────────────
    def _resolve_name(self, nm, ctx_sheet):
        if nm.is_error:
            return 0
        refers = nm.refers_to.lstrip("=")
        # refers like '2047'!$E$2  or  IV.a.Outputs  or  'Sheet'!$G$6:$BU$74
        return self._resolve_refers_to(refers, ctx_sheet)

    def _resolve_refers_to(self, refers, ctx_sheet):
        refers = refers.strip()
        # Table reference (no ! and matches a table)?
        if "!" not in refers and self.m.get_table(refers):
            tbl = self.m.get_table(refers)
            return self._make_range(tbl.sheet, tbl.min_row+1, tbl.min_col, tbl.max_row, tbl.max_col)
        # 'Sheet'!$A$1:$B$2  or  Sheet!$A$1
        mt = re.match(r"^'?([^'!]+)'?!(\$?[A-Z]+\$?\d+)(?::(\$?[A-Z]+\$?\d+))?$", refers)
        if mt:
            sname, a1, a2 = mt.group(1), mt.group(2), mt.group(3)
            r, c = self._a1_to_rc(a1)
            if a2:
                r2, c2 = self._a1_to_rc(a2)
                return self._make_range(sname, r, c, r2, c2)
            return self.eval_cell(sname, r, c)
        # Bare scalar?
        try:
            return float(refers)
        except ValueError:
            return refers

    # ── INDIRECT ──────────────────────────────────────────────────────────────
    def _indirect(self, ref_string, ctx_sheet):
        """Resolve an INDIRECT string to a RangeRef or scalar."""
        s = str(ref_string).strip()

        # Structured table ref: TableName[Column]
        mt = re.match(r"^([A-Za-z_][\w\.]*)\[([^\]]+)\]$", s)
        if mt:
            return self._resolve_table_column(mt.group(1), mt.group(2))

        # 'Sheet'!Range or 'Sheet'!Name
        mt = re.match(r"^'?([^'!]+)'?!(.+)$", s)
        if mt:
            sname, rest = mt.group(1), mt.group(2)
            # worksheet-scoped name?
            nm = self.m.get_name(rest, sname)
            if nm:
                return self._resolve_name(nm, sname)
            # cell or range?
            m2 = re.match(r"^(\$?[A-Z]+\$?\d+)(?::(\$?[A-Z]+\$?\d+))?$", rest)
            if m2:
                r, c = self._a1_to_rc(m2.group(1))
                if m2.group(2):
                    r2, c2 = self._a1_to_rc(m2.group(2))
                    return self._make_range(sname, r, c, r2, c2)
                return self.eval_cell(sname, r, c)

        # Bare workbook name (Unit.mtoe, base.year, etc.)
        nm = self.m.get_name(s, ctx_sheet)
        if nm:
            return self._resolve_name(nm, ctx_sheet)

        raise EvalError(f"cannot resolve INDIRECT({s})")

    # ── Function implementations ───────────────────────────────────────────────
    def _call_function(self, name, args, sheet, row, col):
        """Top-level guard: ANY exception in ANY function becomes a logged gap
        returning ERROR, so a single unhandled construct can never crash the
        whole run. This is the systematic safety net."""
        try:
            return self._dispatch_function(name, args, sheet, row, col)
        except EvalError:
            raise
        except Exception as e:
            self._unevaluated.append((sheet, row, col, f"{name}: {type(e).__name__}"))
            return ERROR

    def _dispatch_function(self, name, args, sheet, row, col):
        if name == "INDIRECT":
            return self._indirect(self._scalar(args[0]), sheet)

        if name == "IFERROR":
            try:
                v = self._scalar(args[0])
                if v is None: return self._scalar(args[1])
                return v
            except Exception:
                return self._scalar(args[1]) if len(args) > 1 else 0

        if name == "IF":
            cond = self._scalar(args[0])
            if cond:
                return self._scalar(args[1]) if len(args) > 1 else True
            return self._scalar(args[2]) if len(args) > 2 else False

        if name == "CHOOSE":
            idx = int(self._numz(args[0]))
            if 1 <= idx <= len(args) - 1:
                return self._scalar(args[idx])
            return 0

        if name == "INDEX":
            return self._fn_index(args)

        if name == "MATCH":
            return self._fn_match(args)

        if name == "SUM":
            return sum(self._flatten_nums(args))

        if name == "AVERAGE":
            nums = self._flatten_nums(args)
            return sum(nums) / len(nums) if nums else 0

        if name == "MAX":
            nums = self._flatten_nums(args)
            return max(nums) if nums else 0

        if name == "MIN":
            nums = self._flatten_nums(args)
            return min(nums) if nums else 0

        if name == "ABS":   return abs(self._numz(args[0]))
        if name == "EXP":
            x = self._numz(args[0])
            try:    return math.exp(x)
            except OverflowError: return float('inf')
        if name == "LN":
            x = self._numz(args[0])
            return math.log(x) if x > 0 else 0
        if name == "MOD":
            a, b = self._numz(args[0]), self._numz(args[1])
            return a % b if b != 0 else 0
        if name == "ROUNDDOWN":
            f = 10 ** int(self._numz(args[1]))
            return math.floor(self._numz(args[0]) * f) / f
        if name == "ROUNDUP":
            f = 10 ** int(self._numz(args[1]))
            return math.ceil(self._numz(args[0]) * f) / f
        if name == "AND":   return all(self._scalar(a) for a in args)
        if name == "OR":    return any(self._scalar(a) for a in args)
        if name == "ROW":   return row

        if name == "SUMIF":
            return self._fn_sumif(args)
        if name == "SUMIFS":
            return self._fn_sumifs(args)
        if name == "SUMPRODUCT":
            return self._fn_sumproduct(args)
        if name == "SUBTOTAL":
            return sum(self._flatten_nums(args[1:]))
        if name == "TEXT":
            return self._to_str(self._scalar(args[0]))
        if name == "LEFT":
            s = self._to_str(self._scalar(args[0]))
            n = int(self._num(args[1])) if len(args)>1 else 1
            return s[:n]
        if name == "FIND":
            needle = self._to_str(self._scalar(args[0]))
            hay = self._to_str(self._scalar(args[1]))
            return hay.find(needle)+1
        if name == "PMT":
            return self._fn_pmt(args)
        if name == "VLOOKUP":
            return self._fn_vlookup(args)

        raise EvalError(f"unimplemented function {name}")

    def _fn_index(self, args):
        rng = args[0]
        if not isinstance(rng, RangeRef):
            return self._scalar(rng)
        row_n = int(self._num(args[1])) if len(args) > 1 else 1
        col_n = int(self._num(args[2])) if len(args) > 2 else 1
        # row_num=0 -> whole column col_n; col_num=0 -> whole row row_n
        # (Excel: INDEX(rng,,2) or INDEX(rng,2,)), used as an array for MATCH/SUM etc.
        if row_n == 0 and rng.ncols > 1 and col_n != 0:
            cells = [c for i, c in enumerate(rng.cells) if i % rng.ncols == col_n - 1]
            return RangeRef(cells, len(cells), 1)
        if col_n == 0 and rng.nrows > 1 and row_n != 0:
            start = (row_n - 1) * rng.ncols
            return RangeRef(rng.cells[start:start + rng.ncols], 1, rng.ncols)
        if rng.nrows == 1:
            idx = (col_n - 1) if len(args) <= 2 else (col_n - 1)
            idx = (row_n - 1) if rng.ncols == 1 else idx
            # single row: index by the larger of row/col
            i = max(row_n, col_n) - 1
            if 0 <= i < len(rng.cells):
                s,r,c = rng.cells[i]; return self.eval_cell(s,r,c)
            return 0
        if rng.ncols == 1:
            i = row_n - 1
            if 0 <= i < len(rng.cells):
                s,r,c = rng.cells[i]; return self.eval_cell(s,r,c)
            return 0
        # 2D
        i = (row_n - 1) * rng.ncols + (col_n - 1)
        if 0 <= i < len(rng.cells):
            s,r,c = rng.cells[i]; return self.eval_cell(s,r,c)
        return 0

    def _fn_match(self, args):
        target = self._scalar(args[0])
        rng = args[1]
        if not isinstance(rng, RangeRef):
            return 0
        match_type = int(self._numz(args[2])) if len(args) > 2 else 1

        if match_type == 0:
            ts = self._to_str(target).strip().lower()
            for i, (s,r,c) in enumerate(rng.cells):
                v = self.eval_cell(s,r,c)
                if self._to_str(v).strip().lower() == ts:
                    return i + 1
                try:
                    if float(v) == float(target):
                        return i + 1
                except (ValueError, TypeError):
                    pass
            raise EvalError("no match")

        # Approximate match: 1 = largest value <= target, -1 = smallest value >= target.
        # Excel assumes the array is sorted accordingly and scans linearly, tracking
        # the best candidate seen so far rather than requiring a true sort.
        target_n = self._num(target)
        best_idx = None
        for i, (s, r, c) in enumerate(rng.cells):
            v = self._num(self.eval_cell(s, r, c))
            if v is ERROR or target_n is ERROR:
                continue
            if match_type == 1 and v <= target_n:
                best_idx = i
            elif match_type == -1 and v >= target_n:
                if best_idx is None:
                    best_idx = i
        if best_idx is None:
            raise EvalError("no match")
        return best_idx + 1

    def _fn_sumif(self, args):
        rng = args[0]; crit = self._scalar(args[1])
        sum_rng = args[2] if len(args) > 2 else args[0]
        if not isinstance(rng, RangeRef): return 0
        total = 0
        for i,(s,r,c) in enumerate(rng.cells):
            if self._to_str(self.eval_cell(s,r,c)).strip().lower() == self._to_str(crit).strip().lower():
                if isinstance(sum_rng, RangeRef) and i < len(sum_rng.cells):
                    ss,rr,cc = sum_rng.cells[i]; total += self._num(self.eval_cell(ss,rr,cc))
        return total

    def _fn_sumifs(self, args):
        sum_rng = args[0]
        if not isinstance(sum_rng, RangeRef): return 0
        pairs = [(args[i], self._scalar(args[i+1])) for i in range(1, len(args)-1, 2)]
        total = 0
        for i,(s,r,c) in enumerate(sum_rng.cells):
            ok = True
            for crit_rng, crit_val in pairs:
                if isinstance(crit_rng, RangeRef) and i < len(crit_rng.cells):
                    cs,cr,cc = crit_rng.cells[i]
                    if self._to_str(self.eval_cell(cs,cr,cc)).strip().lower() != self._to_str(crit_val).strip().lower():
                        ok = False; break
            if ok:
                total += self._num(self.eval_cell(s,r,c))
        return total

    def _fn_sumproduct(self, args):
        ranges = [a for a in args if isinstance(a, RangeRef)]
        if not ranges: return 0
        n = len(ranges[0].cells)
        total = 0
        for i in range(n):
            prod = 1
            for rng in ranges:
                if i < len(rng.cells):
                    s,r,c = rng.cells[i]; prod *= self._num(self.eval_cell(s,r,c))
            total += prod
        return total

    def _fn_pmt(self, args):
        rate = self._num(args[0]); nper = self._num(args[1]); pv = self._num(args[2])
        if rate == 0: return -pv/nper if nper else 0
        return -(pv * rate) / (1 - (1+rate)**(-nper))

    def _fn_vlookup(self, args):
        target = self._scalar(args[0]); rng = args[1]
        col_idx = int(self._num(args[2]))
        if not isinstance(rng, RangeRef): return 0
        for i in range(rng.nrows):
            s,r,c = rng.cells[i*rng.ncols]
            if self._to_str(self.eval_cell(s,r,c)).strip().lower() == self._to_str(target).strip().lower():
                s2,r2,c2 = rng.cells[i*rng.ncols + (col_idx-1)]
                return self.eval_cell(s2,r2,c2)
        return 0

    # ── Range construction ─────────────────────────────────────────────────────
    def _make_range(self, sheet, r1, c1, r2, c2):
        nrows, ncols = abs(r2 - r1) + 1, abs(c2 - c1) + 1
        if nrows * ncols <= _RANGE_CACHE_MAX_CELLS:
            # list() over the cached tuple is a C-level copy — far cheaper than
            # rebuilding via nested Python loops, and keeps the cache immutable.
            return RangeRef(list(_range_cells_pure(sheet, r1, c1, r2, c2)), nrows, ncols)
        cells = []
        for r in range(min(r1, r2), max(r1, r2) + 1):
            for c in range(min(c1, c2), max(c1, c2) + 1):
                cells.append((sheet, r, c))
        return RangeRef(cells, nrows, ncols)

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _a1_to_rc(self, a1):
        return _a1_to_rc_pure(a1)

    def _scalar(self, v, ctx=None):
        if v is ERROR: return ERROR
        if isinstance(v, RangeRef):
            if ctx is not None and v.cells:
                # Implicit intersection: Excel intersects a whole-row or
                # whole-column reference (e.g. Table[#Headers]) down to the
                # single cell aligned with the calling formula's row/column
                # when used in a scalar context.
                csheet, crow, ccol = ctx
                s0, r0, c0 = v.cells[0]
                s1, r1, c1 = v.cells[-1]
                if v.nrows == 1 and v.ncols > 1 and s0 == csheet and c0 <= ccol <= c1:
                    s, r, c = v.cells[ccol - c0]
                    return self.eval_cell(s, r, c)
                if v.ncols == 1 and v.nrows > 1 and s0 == csheet and r0 <= crow <= r1:
                    s, r, c = v.cells[crow - r0]
                    return self.eval_cell(s, r, c)
            if v.cells:
                s,r,c = v.cells[0]; return self.eval_cell(s,r,c)
            return 0
        return v

    def _num(self, v):
        v = self._scalar(v)
        if v is ERROR: return ERROR
        if isinstance(v, bool): return 1 if v else 0
        if isinstance(v, (int, float)): return v
        try: return float(v)
        except (ValueError, TypeError): return 0

    def _numz(self, v):
        """num-or-zero: ALWAYS returns a finite float for arithmetic.
        ERROR / None / non-numeric / nan / inf / complex → 0.0.
        This is the single chokepoint all arithmetic flows through, so it
        must never return anything that can crash a +-*/^ operation."""
        v = self._scalar(v)
        if v is ERROR or v is None:
            return 0.0
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            f = float(v)
        else:
            try:
                f = float(v)
            except (ValueError, TypeError):
                return 0.0
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f

    def _to_str(self, v):
        v = self._scalar(v)
        if v is ERROR: return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v) if v is not None else ""

    def _flatten_nums(self, args):
        out = []
        for a in args:
            if isinstance(a, RangeRef):
                for s,r,c in a.cells:
                    n = self._num(self.eval_cell(s,r,c))
                    out.append(n if n is not ERROR else 0)
            else:
                n = self._num(a)
                out.append(n if n is not ERROR else 0)
        return out
