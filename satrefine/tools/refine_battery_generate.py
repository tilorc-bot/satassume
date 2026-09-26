"""Generate ``tests/refine_identities/battery_v3.py`` from captured v3 test calls.

Usage: ``SATREFINE_HANDLERS=handlers_v3 PYTHONPATH=.:/path/to/sympy python
satrefine/tools/refine_battery_generate.py CAPTURE_DIR OUTPUT`` after recording with
``satrefine/tools/refine_battery_capture.py``.  Every expression is emitted as code that
rebuilds it exactly (checked by ``srepr``), ``evaluate=False`` only where the
test built an unevaluated node; the expected value is ``handlers_v3``'s
dispatcher-level result computed on the rebuilt objects.  Calls under a
patched ``ask`` go to ``SKIPPED``; a case repeated within one test function is
kept once.
"""
import collections
import json
import os
import re
import sys

if "satrefine" in sys.modules:               # python -m: satrefine is loaded already
    from satrefine.tools import rerun_with
    rerun_with(handlers="handlers_v3")
os.environ["SATREFINE_HANDLERS"] = "handlers_v3"
import sympy
from sympy import AccumBounds
from sympy import Basic, MatrixSymbol, Symbol, srepr
from sympy.assumptions.assume import AppliedPredicate
from sympy.assumptions.relation.binrel import AppliedBinaryRelation
from sympy.core.symbol import Str
from sympy.matrices.expressions.matexpr import MatrixElement
from sympy.printing.str import StrPrinter

from satrefine import refine as v3_refine

CAP = sys.argv[1]
OUT = sys.argv[2]
FILES = ["trig", "hyperbolic", "inverse", "power_exp_log", "complex_parts", "integer_funcs", "combinatorial", "minmax_deltas", "matrices"]

BASE_NS = {k: getattr(sympy, k) for k in dir(sympy) if not k.startswith("_")}
EXTRA = {"AppliedPredicate": AppliedPredicate, "AppliedBinaryRelation": AppliedBinaryRelation,
         "MatrixElement": MatrixElement, "Str": Str, "AccumulationBounds": AccumBounds}
BASE_NS.update(EXTRA)


from sympy.core.parameters import evaluate as _evaluate


def load(s):
    v = eval(s, dict(BASE_NS))
    if isinstance(v, Basic) and srepr(v) != s:
        with _evaluate(False):
            v = eval(s, dict(BASE_NS))
        if srepr(v) != s:
            raise ValueError("no faithful load for " + s)
    return v


# ---- read records -------------------------------------------------------
records = []
for f in FILES:
    for r in json.load(open(os.path.join(CAP, f + ".json"))):
        if "kind" in r:
            r["file"] = f
            records.append(r)

# ---- symbol naming ------------------------------------------------------
variants = collections.defaultdict(set)   # name -> set of srepr
symobjs = {}
for r in records:
    for key in ("expr", "assumptions", "result"):
        if r.get(key) is None:
            continue
        v = load(r[key])
        if isinstance(v, Basic):
            def walk(n):
                if isinstance(n, (Symbol, MatrixSymbol)):
                    yield n
                    return
                for c in getattr(n, "args", ()):
                    yield from walk(c)
            for a in set(walk(v)):
                if isinstance(a, Symbol) or isinstance(a, MatrixSymbol):
                    variants[str(a.name)].add(srepr(a))
                    symobjs[srepr(a)] = a

varname = {}
for name, vs in variants.items():
    for s in sorted(vs):
        a = symobjs[s]
        if len(vs) == 1 or isinstance(a, MatrixSymbol):
            vn = name
        else:
            asm = a._assumptions_orig if hasattr(a, "_assumptions_orig") else {}
            if not asm:
                vn = name
            else:
                vn = name + "_" + "_".join(("" if val else "non") + key for key, val in sorted(asm.items()))
        varname[s] = vn
assert len(set(varname.values())) == len(varname), varname

used_names = set()


class P(StrPrinter):
    def _print_Symbol(self, e):
        return varname[srepr(e)]
    _print_Dummy = _print_Symbol

    def _print_MatrixSymbol(self, e):
        return varname[srepr(e)]


    def _print_Float(self, e):
        return srepr(e)

    def _print_Rational(self, e):
        if e.q == 1:
            return str(e.p)
        return f"S({e.p})/{e.q}"


printer = P({"full_prec": True})


def ns_for_check():
    ns = dict(BASE_NS)
    for s, vn in varname.items():
        ns[vn] = symobjs[s]
    return ns


NS = ns_for_check()


def ok(code, e):
    try:
        v = eval(code, dict(NS))
    except Exception:
        return False
    if e is True or e is False:
        return v is e
    return isinstance(v, Basic) and srepr(v) == srepr(e) or (not isinstance(e, Basic) and v == e)


def emit(e):
    if e is True or e is False:
        return repr(e)
    code = printer.doprint(e)
    if ok(code, e):
        return code
    if isinstance(e, Basic) and ok(f"S({code})", e):
        return f"S({code})"
    name = type(e).__name__
    if e.args and not e.is_Atom:
        parts = [emit(a) for a in e.args]
        for c in (f"{name}({', '.join(parts)}, evaluate=False)", f"{name}({', '.join(parts)})"):
            if ok(c, e):
                return c
    c = srepr(e)
    for s, vn in sorted(varname.items(), key=lambda kv: -len(kv[0])):
        c = c.replace(s, vn)
    if ok(c, e):
        return c
    c = srepr(e)
    assert ok(c, e), (c, e)
    return c


# ---- build cases --------------------------------------------------------
cases = []      # (file, source, expr, assumptions, expected|None, notes)
skipped = []
seen = set()
disagree = []
dup_count = collections.Counter()
for r in records:
    node = r["nodeid"].split("/", 2)[-1]           # test_x.py::...
    func = re.sub(r"\[.*\]$", "", node)
    expr = load(r["expr"]); assm = load(r["assumptions"])
    if r["ask_patched"] and r["ask_name"] != "counting":
        skipped.append((node, f"runs under a patched ask ({r['ask_name']}): "
                        f"{r['kind']}({expr}, {assm}); a battery entry cannot carry a patched ask, and under the real ask the case tests something else"))
        continue
    key = (func, r["expr"], r["assumptions"])
    if key in seen:
        dup_count[r["file"]] += 1
        continue
    seen.add(key)
    expr_code, assm_code = emit(expr), emit(assm)
    expr = eval(expr_code, dict(NS)); assm = eval(assm_code, dict(NS))
    got = v3_refine(expr, assm)
    if r["kind"] == "refine":
        recorded = load(r["result"])
        if srepr(got) != srepr(recorded):
            disagree.append(("refine nondeterministic", node, expr, assm, recorded, got))
    else:
        hres = None if r["result_is_none"] else load(r["result"])
        hlevel = None if hres is None or hres == expr else hres
        dlevel = None if got == expr else got
        if (hlevel is None) != (dlevel is None) or (hlevel is not None and srepr(hlevel) != srepr(dlevel)):
            disagree.append((r["kind"] + " handler vs dispatcher", node, expr, assm, hres, got))
    expected = None if got == expr else got
    note = ""
    if r["kind"] != "refine":
        hres = None if r["result_is_none"] else load(r["result"])
        if hres is None:
            if expected is not None:
                note = "handler returns None; the dispatcher's rebuild gives this"
        elif expected is None or srepr(hres) != srepr(expected):
            note = f"handler-level: {hres}"
    cases.append((r["file"], node, expr_code, assm_code, expected, note))

# ---- emit ---------------------------------------------------------------
lines = []
counts = collections.Counter(c[0] for c in cases)
fires = collections.Counter(c[0] for c in cases if c[4] is not None)
for f in FILES:
    lines.append(f"    # {'-' * 70}\n    # test_{f}.py: {counts[f]} cases, {fires[f]} fire, {counts[f] - fires[f]} unchanged\n    # {'-' * 70}")
    last = None
    for (fl, node, expr, assm, expected, note) in cases:
        if fl != f:
            continue
        func = re.sub(r"\[.*\]$", "", node)
        if func != last:
            lines.append(f"    # {func.split('::', 1)[1]}")
            last = func
        ex = "None" if expected is None else emit(expected)
        lines.append(f"    ({expr}, {assm}, {ex}, {node!r}),"  + (f"  # {note}" if note else ""))

body = "\n".join(lines)
idents = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b(?!=)", re.sub(r"'[^']*'|\"[^\"]*\"|#[^\n]*", "", body)))
symvars = set(varname.values())
imports_sympy = sorted(n for n in idents if n in dir(sympy) and n not in symvars and n not in ("None", "True", "False"))
imports_extra = sorted(n for n in idents if n in EXTRA and n not in dir(sympy))

sym_lines = []
for s, vn in sorted(varname.items(), key=lambda kv: (isinstance(symobjs[kv[0]], MatrixSymbol), kv[1])):
    a = symobjs[s]
    if isinstance(a, MatrixSymbol):
        line = f"{vn} = MatrixSymbol({str(a.name)!r}, {printer.doprint(a.rows)}, {printer.doprint(a.cols)})"
    else:
        line = f"{vn} = {s}"
    chk = dict(NS); exec(line, chk)
    assert srepr(chk[vn]) == s, line
    sym_lines.append(line)
for n in ("Symbol", "MatrixSymbol"):
    if any(n + "(" in l for l in sym_lines) and n not in imports_sympy and n in dir(sympy):
        imports_sympy.append(n)
imports_sympy = sorted(set(imports_sympy))

skip_lines = "\n".join(f"    ({s!r}, {why!r})," for s, why in skipped)
extra_import = ""
mods = collections.defaultdict(list)
for n in imports_extra:
    mods[EXTRA[n].__module__].append(n)
for m, ns_ in sorted(mods.items()):
    extra_import += f"from {m} import {', '.join(sorted(ns_))}\n"

header = f'''"""Acceptance battery extracted from ``tests/refine_v3`` (the ``handlers_v3`` suite).

Each entry of ``BATTERY`` is ``(expr, assumptions, expected, source)``:

* ``expr`` and ``assumptions`` are exactly what a ``tests/refine_v3`` test
  passed to ``refine`` or to a ``handlers_v3`` handler it called directly
  (``assumptions`` is ``True`` when none were given; symbols keep their
  old-style assumptions, e.g. ``y_real = Symbol('y', real=True)``);
* ``expected`` is what ``handlers_v3`` returns through the dispatcher
  (``satrefine.refine``), or ``None`` when the input comes back unchanged.
  For a directly called handler this is the dispatcher-level answer: a
  handler returning ``None`` is ``None`` here (unchanged);
* ``source`` is ``test_<family>.py::<test>[<parametrization id>]``.

Loops and parametrizations are expanded; computed expected values are
evaluated.  Where a test only constrains the result loosely (``!= expr``,
``in (x, 0)``, ``not refined.has(n)``, a numeric agreement check) the entry
records the value v3 actually produces.  A case repeated inside one test
function (same expr and assumptions, e.g. under parametrizations that only
vary a numeric sample point) is listed once, under its first source; the
same case in two different test functions is listed under each.  Cases that
only make sense under a patched ``ask`` are in ``SKIPPED``.

Generated by recording every outermost ``refine``/handler call made while
the suite ran under ``SATREFINE_HANDLERS=handlers_v3``; checked by
``test_battery.py``.  Imports nothing from ``satrefine``.

Counts: {len(cases)} cases ({sum(fires.values())} fire, {len(cases) - sum(fires.values())} must stay unchanged), {len(skipped)} skipped.
"""
from __future__ import annotations

from sympy import (
{chr(10).join("    " + n + "," for n in imports_sympy)}
)
{extra_import}
'''
text = header + "\n".join(sym_lines) + "\n\n# (expr, assumptions, expected or None for unchanged, source)\nBATTERY = [\n" + body + "\n]\n\n# (source, reason)\nSKIPPED = [\n" + skip_lines + "\n]\n"
open(OUT, "w").write(text)
print("cases", len(cases), "fires", sum(fires.values()), "skipped", len(skipped))
for f in FILES:
    print(f, counts[f], fires[f], "dups-removed", dup_count[f])
print("disagreements:", len(disagree))
for d in disagree:
    print("  ", d)
