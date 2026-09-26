#!/usr/bin/env python
"""Check ``satrefine.refine`` against SymPy's OLD assumption system.

``satrefine.refine`` consumes ``Q.*`` assumptions.  SymPy's old assumption
system (``Symbol('x', positive=True)``) is a structurally different
implementation of the same facts: it drives automatic evaluation, the
``_eval_is_*`` methods and the old-system simplifiers.  This tool uses it as
an oracle for the refine handlers, in two modes.

Mode A, "old-system oracle"
    A fixed, hand-written list of expression shapes per handler key, crossed
    with lists of assumption sets per symbol.  For each case the plain
    symbols are replaced by old-style symbols carrying the equivalent
    declared assumptions (automatic evaluation happens), then SymPy's
    assumption-aware simplifiers (``simplify``, ``powdenest``,
    ``expand_complex``, ``sqrtdenest``, ``trigsimp``, ``expand_log``,
    ``logcombine``, ``powsimp``, ``gammasimp``, ``doit`` and a natural
    ``rewrite`` per key) are tried; ``refine`` is never used on this side.
    The simplest result that is (a) produced with the declared assumptions
    and (b) simpler than what the same simplifiers make of the plain
    expression is the "old-system result".  It is mapped back to plain
    symbols and compared with ``satrefine.refine(expr, Q...)`` and with
    SymPy's own ``refine``.

    Matrix keys have no old-system equivalent except ``ZeroMatrix`` and
    ``Identity``; for them the oracle substitutes explicit 2x2 instances of
    the predicate (symbolic entries for symmetric/diagonal/triangular/...,
    exact rational or Gaussian-rational matrices for orthogonal/unitary/
    invertible/...), checks every refine result against the instances, and
    searches a small fixed candidate list for the simplest equal expression.

Mode B, "SymPy test-suite corpus"
    SymPy test modules are parsed with ``ast``; each ``test_*`` function body
    is replayed statement by statement twice, once as written and once with
    every assumption keyword stripped from ``Symbol``/``symbols``/``Dummy``
    calls.  For every ``assert L == R`` (or ``is``) whose unevaluated
    plain-symbol side has a handler key as head and whose symbols carry
    declared assumptions, that side is refined under the equivalent
    ``Q``-assumptions and the result is compared with the asserted value.

Soundness is always checked numerically against the ORIGINAL expression
evaluated at exact points (integers, rationals, surds, Gaussian rationals)
chosen by the old system's own ``is_*`` facts to satisfy the declared
assumptions, plus an attempt to prove ``simplify(result - expr) == 0`` with
old-assumption symbols.

Usage::

    PYTHONPATH=.:/path/to/sympy .venv/bin/python -m satrefine.tools.refine_oracle \
        [--mode a|b|both] [--handlers handlers_identities|handlers_v3] \
        [--show gaps|unsound|all] [--keys log,Pow] [--jobs 4] [--json out.json]

The exit status is always 0: this is a measurement.
"""
from __future__ import annotations

import argparse
import ast
import collections
import importlib
import itertools
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# argument parsing happens before satrefine is imported (handler package env)
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--mode", choices=("a", "b", "both"), default="both")
    p.add_argument("--handlers", default=os.environ.get("SATREFINE_HANDLERS", "handlers_identities"),
                   help="handler package inside satrefine (sets SATREFINE_HANDLERS)")
    p.add_argument("--backend", default="combined")
    p.add_argument("--show", choices=("gaps", "unsound", "all"), default="unsound")
    p.add_argument("--keys", default="", help="comma-separated handler keys (mode A filter)")
    p.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    p.add_argument("--limit", type=int, default=0, help="cap on mode A cases (0: all)")
    p.add_argument("--json", default="", help="write every classified case to this file")
    p.add_argument("--max-show", type=int, default=40,
                   help="max listed cases per key and category (unsound cases are never capped)")
    return p.parse_args(argv)


ARGS = None
if __name__ == "__main__":
    from satrefine.tools.lib.select import select
    ARGS = parse_args()
    select(handlers=ARGS.handlers, backend=ARGS.backend)

sys.setrecursionlimit(10000)

import sympy  # noqa: E402
from sympy import (  # noqa: E402
    Abs, Add, And, Basic, Dummy, E, Expr, FallingFactorial, Float, I, Identity,
    Integer, KroneckerDelta, Matrix, MatrixSymbol, Max, Min, Mod, Mul, Piecewise,
    Pow, Q, Rational, RisingFactorial, S, Symbol, ZeroMatrix, acos, acosh,
    acot, acoth, acsch, arg, asech, asin, asinh, atan, atan2, atanh, binomial,
    ceiling, conjugate, cos, cosh, cot, coth, count_ops, csc, csch, exp,
    expand_complex, expand_log, factorial, floor, frac, gamma, gammasimp, im,
    log, logcombine, nan, oo, pi, powdenest, powsimp, re, sec, sech, sign,
    simplify, sin, sinc, sinh, sqrt, sqrtdenest, tan, tanh, trigsimp, zoo,
)
from sympy.functions import DiracDelta, Heaviside  # noqa: E402
from sympy.functions.elementary.integers import frac as _frac  # noqa: E402,F401
from sympy.matrices.expressions import (  # noqa: E402
    Determinant, HadamardProduct, Inverse, MatAdd, MatMul, Trace, Transpose,
)
from sympy.assumptions.refine import refine as sympy_refine  # noqa: E402
from sympy.core.relational import Relational  # noqa: E402

import satrefine  # noqa: E402
from satrefine.identities.compat import backend as sat_backend  # noqa: E402
from satrefine.identities.compat import upstream as _upstream  # noqa: E402
from satrefine.tools.lib.report import table  # noqa: E402
from satrefine.tools.lib.workers import Timeout, attempt, install_timeouts, run_forked, timed  # noqa: E402
from satrefine.tools.lib.workers import outer_expired as _outer_expired  # noqa: E402

HANDLER_KEYS = sorted(_upstream.handlers_dict)


# ---------------------------------------------------------------------------
# timeouts
# ---------------------------------------------------------------------------

install_timeouts()     # Timeout, timed and attempt: satrefine.tools.lib.workers


# ---------------------------------------------------------------------------
# assumption specs: {symbol name: {predicate: bool}}
# ---------------------------------------------------------------------------

def q_of(spec_items, sym_by_name):
    conj = []
    for name, preds in spec_items:
        s = sym_by_name[name]
        for p, v in preds:
            atom = getattr(Q, p)(s)
            conj.append(atom if v else ~atom)
    return And(*conj) if conj else S.true


def old_symbol(sym, preds):
    kw = {p: v for p, v in preds}
    if isinstance(sym, Dummy):
        return Dummy(sym.name, **kw)
    return Symbol(sym.name, **kw)


def spec_text(spec_items):
    parts = []
    for name, preds in spec_items:
        if preds:
            parts.append(name + ":" + "+".join(p if v else "~" + p for p, v in preds))
    return ", ".join(parts) or "(none)"


# ---------------------------------------------------------------------------
# numeric evaluation at exact points chosen by the old system
# ---------------------------------------------------------------------------

NUMS = [S(0), S(1), S(-1), S(2), S(-2), S(3), S(-3), S(4), S(-5), S(7), S(-6), S(10),
        Rational(1, 2), Rational(-1, 3), Rational(5, 2), Rational(-7, 2),
        Rational(3, 10), Rational(9, 5), Rational(-9, 4), sqrt(2), -sqrt(3), 1 + sqrt(5),
        I, -I, 3 * I / 2, -2 * I / 3, 2 * I, 1 + I, Rational(-3, 2) + I / 2,
        Rational(1, 2) - 2 * I, -2 - 3 * I / 2, Rational(1, 3) + 3 * I, -1 + I / 5]


def values_for(preds):
    out = []
    for v in NUMS:
        ok = True
        for p, want in preds:
            got = getattr(v, "is_" + p, None)
            if got is None:
                ok = False  # could not decide on a number: avoid
                break
            if got is not want:
                ok = False
                break
        if ok:
            out.append(v)
    return out


def sample_points(spec_items, plain_by_name, npoints=18, seed=0):
    lists = []
    names = []
    for name, preds in spec_items:
        vals = values_for(preds)
        if not vals:
            return []
        lists.append(vals)
        names.append(name)
    if not lists:
        return [{}]
    combos = list(itertools.product(*lists))
    if len(combos) > npoints:
        rng = random.Random(seed * 7919 + len(combos))
        combos = rng.sample(combos, npoints)
    return [{plain_by_name[n]: v for n, v in zip(names, c)} for c in combos]


def numval(e, pt):
    """complex, 'nan', 'inf', 'accum' or None (not decidable numerically)."""
    try:
        v = e.xreplace(pt) if isinstance(e, Basic) else sympy.sympify(e)
        if v.has(sympy.AccumBounds):
            return "accum"
        if v.has(nan):
            return "nan"
        if v.has(zoo, oo, -oo, S.ComplexInfinity):
            if v in (zoo, oo, -oo) or v.is_infinite:
                return "inf"
        v = v.evalf(30)
        if v.has(nan):
            return "nan"
        if v.has(zoo, oo, -oo):
            return "inf"
        if v.free_symbols or not v.is_number:
            return None
        z = complex(v)
        if z != z:
            return "nan"
        if abs(z) == float("inf") or abs(z) > 1e200:
            return "inf"
        return z
    except Timeout:
        raise
    except Exception:  # noqa: BLE001
        return None


def close(a, b):
    if isinstance(a, complex) and isinstance(b, complex):
        return abs(a - b) <= 1e-10 * (1 + max(abs(a), abs(b)))
    return a == b


class NumVerdict:
    __slots__ = ("ok", "bad", "sing", "unknown", "example")

    def __init__(self):
        self.ok = self.bad = self.sing = self.unknown = 0
        self.example = None

    @property
    def unsound(self):
        return self.bad > 0

    def as_text(self):
        return f"ok={self.ok} bad={self.bad} singular-mismatch={self.sing} undecided={self.unknown}"


def numeric_compare(candidate, truth_expr, points, budget=6.0):
    """Compare candidate with the original expression at every point."""
    verdict = NumVerdict()

    def run():
        for pt in points:
            t = numval(truth_expr, pt)
            c = numval(candidate, pt)
            if t is None or c is None or t == "accum" or c == "accum":
                verdict.unknown += 1
                continue
            if isinstance(t, complex) and isinstance(c, complex):
                if close(t, c):
                    verdict.ok += 1
                else:
                    verdict.bad += 1
                    if verdict.example is None:
                        verdict.example = (pt, t, c)
            elif isinstance(t, complex) or isinstance(c, complex):
                verdict.sing += 1
                if verdict.example is None:
                    verdict.example = (pt, t, c)
            else:
                verdict.ok += 1  # both non-finite

    try:
        timed(run, budget)
    except Timeout:
        if _outer_expired():
            raise
        verdict.unknown += 1
    except Exception:  # noqa: BLE001
        verdict.unknown += 1
    return verdict


def fmt_point(pt):
    return "{" + ", ".join(f"{k}={v}" for k, v in sorted(pt.items(), key=lambda kv: str(kv[0]))) + "}"


def fmt_num(v):
    if isinstance(v, complex):
        if abs(v.imag) < 1e-12:
            return f"{v.real:.10g}"
        return f"{v.real:.10g}{v.imag:+.10g}j"
    return str(v)


# ---------------------------------------------------------------------------
# complexity and old-system candidate generation
# ---------------------------------------------------------------------------

def nodes(e):
    try:
        return sum(1 for _ in sympy.preorder_traversal(e))
    except Exception:  # noqa: BLE001
        return 10 ** 6


def cx(e):
    try:
        ops = int(count_ops(e))
    except Exception:  # noqa: BLE001
        ops = nodes(e)
    return (ops, nodes(e))


REWRITE_TARGETS = {
    "sec": [cos], "csc": [sin], "cot": [cos, sin], "tan": [sin, cos], "sinc": [sin],
    "sech": [cosh], "csch": [sinh], "coth": [exp], "tanh": [exp],
    "frac": [floor], "Mod": [floor], "binomial": [factorial],
    "RisingFactorial": [gamma], "FallingFactorial": [gamma],
    "Min": [Piecewise], "Max": [Piecewise], "Heaviside": [Piecewise],
    "KroneckerDelta": [Piecewise], "sign": [Piecewise], "Abs": [Piecewise],
    "DiracDelta": [Piecewise], "arg": [atan2], "asin": [log], "acos": [log],
    "atan": [log], "asinh": [log], "acosh": [log], "atanh": [log],
}


def old_candidates(e, key, secs=4.0):
    """The old-system simplifiers applied to e (which already auto-evaluated)."""
    out = [("auto", e)]
    fns = [
        ("simplify", lambda z: simplify(z)),
        ("powdenest", lambda z: powdenest(z, force=False)),
        ("expand_complex", expand_complex),
        ("sqrtdenest", sqrtdenest),
        ("trigsimp", trigsimp),
        ("expand_log", lambda z: expand_log(z, force=False)),
        ("logcombine", lambda z: logcombine(z, force=False)),
        ("powsimp", powsimp),
        ("gammasimp", gammasimp),
        ("doit", lambda z: z.doit()),
    ]
    for target in REWRITE_TARGETS.get(key, []):
        fns.append((f"rewrite({target.__name__})", lambda z, t=target: z.rewrite(t)))
        fns.append((f"simplify(rewrite({target.__name__}))",
                    lambda z, t=target: simplify(z.rewrite(t))))
    for name, fn in fns:
        v, err = attempt(fn, 8.0 if "simplify" in name else secs, e)
        if err is None and isinstance(v, Basic):
            out.append((name, v))
    return out


def provably_equal(a, b, old_map, secs=5.0):
    """True if a == b structurally, or simplify proves it with old symbols."""
    if a == b:
        return True
    def go():
        d = (a - b).xreplace(old_map)
        if d == 0:
            return True
        return simplify(d) == 0
    v, err = attempt(go, secs)
    return bool(v) if err is None else False


# ---------------------------------------------------------------------------
# handler-step logging (to attribute an unsound rewrite to a handler file)
# ---------------------------------------------------------------------------

STEP_LOG: list | None = None


def install_step_logging():
    def wrap(key, fn):
        mod = getattr(fn, "__module__", "?")

        def wrapped(expr, assumptions, _fn=fn):
            new = _fn(expr, assumptions)
            if STEP_LOG is not None and new is not None and new != expr:
                STEP_LOG.append((f"{key} -> {mod}.{_fn.__name__}", expr, new))
            return new
        wrapped.__wrapped__ = fn
        return wrapped

    for key, fn in list(_upstream.handlers_dict.items()):
        if not hasattr(fn, "__wrapped__"):
            _upstream.handlers_dict[key] = wrap(key, fn)

    for cls in (sympy.Pow, sympy.exp):
        orig = cls.__dict__.get("_eval_refine")
        if orig is None or hasattr(orig, "__wrapped__"):
            continue

        def hook(self, assumptions, _orig=orig, _cls=cls):
            new = _orig(self, assumptions)
            if STEP_LOG is not None and new is not None and new != self:
                STEP_LOG.append((f"{_cls.__name__}._eval_refine (sympy core)", self, new))
            return new
        hook.__wrapped__ = orig
        setattr(cls, "_eval_refine", hook)


def logged_refine(expr, assumptions):
    global STEP_LOG
    STEP_LOG = []
    try:
        r = satrefine.refine(expr, assumptions)
        return r, list(STEP_LOG)
    finally:
        STEP_LOG = None


def blame(steps, points):
    """The first handler step whose output differs numerically from its input."""
    for name, inp, out in steps:
        v = numeric_compare(out, inp, points, budget=3.0)
        if v.bad or v.sing:
            return f"{name}: {inp}  ->  {out}"
    return "no single step is numerically wrong (combination / undecided)"


# ---------------------------------------------------------------------------
# Mode A: templates
# ---------------------------------------------------------------------------

x, y, z, n, m, a, b = (Symbol(s) for s in "xyznmab")
PLAIN = {s.name: s for s in (x, y, z, n, m, a, b)}

T = lambda *p: tuple((q, True) for q in p)  # noqa: E731
FULL = [T(), T("real"), T("positive"), T("negative"), T("nonnegative"), T("nonpositive"),
        T("nonzero"), T("integer"), T("even"), T("odd"), T("imaginary"), T("complex"),
        T("zero"), T("rational"), T("positive", "integer"), T("negative", "integer"),
        T("nonnegative", "integer"), T("positive", "odd"), T("negative", "odd"),
        T("positive", "even")]
SMALL = [T(), T("real"), T("positive"), T("negative"), T("integer"), T("imaginary"), T("nonzero")]
SIGN = [T(), T("real"), T("positive"), T("negative"), T("zero"), T("nonnegative"),
        T("nonpositive"), T("nonzero"), T("imaginary")]
INT = [T(), T("integer"), T("even"), T("odd"), T("zero"), T("positive", "integer"),
       T("negative", "integer"), T("nonnegative", "integer"), T("positive", "odd"),
       T("negative", "odd"), T("positive", "even"), T("real"), T("positive")]
SMALLINT = [T(), T("integer"), T("even"), T("odd"), T("positive", "integer"),
            T("negative", "integer"), T("nonnegative", "integer")]
X3 = [T(), T("real"), T("positive")]
EXPS = [T(), T("integer"), T("real"), T("positive"), T("rational"), T("even")]

TEMPLATES: list[tuple[str, Expr, dict]] = []


def add(key, expr, **pools):
    # file the case under the head the plain expression actually has (automatic
    # evaluation can change it, e.g. Abs(exp(x)) -> exp(re(x)))
    head = type(expr).__name__
    if head != key:
        DROPPED.append((key, expr))  # auto-evaluated away from the intended head
        return
    TEMPLATES.append((key, expr, pools))


DROPPED: list = []


def build_templates():
    h = Rational(1, 2)
    # Abs
    for e in (Abs(x), Abs(x ** 2), Abs(exp(x)), Abs(-x), Abs(I * x), Abs(1 / x), Abs(x ** 3),
              Abs(sqrt(x)), Abs(2 * x), Abs(x - 1), Abs(x * conjugate(x)), Abs(log(x))):
        add("Abs", e, x=FULL)
    add("Abs", Abs(x * y), x=SMALL, y=SMALL)
    add("Abs", Abs(x + y), x=SMALL, y=SMALL)
    add("Abs", Abs(x ** y), x=SMALL, y=SMALL)
    add("Abs", Abs(x ** n), x=SMALL, n=SMALLINT)
    # Pow
    for e in (sqrt(x ** 2), (x ** 3) ** Rational(1, 3), (x ** 2) ** Rational(3, 2),
              (x ** 4) ** Rational(1, 4), (x ** -2) ** h, Abs(x) ** 2, Abs(x) ** 3,
              Abs(x) ** 4, (x ** 3) ** h, (x ** Rational(2, 3)) ** 3, sqrt(x) ** 3,
              (x ** 2) ** Rational(-1, 2), (-x) ** h):
        add("Pow", e, x=FULL)
    add("Pow", (x ** a) ** b, x=SMALL, a=EXPS, b=EXPS)
    add("Pow", Abs(x) ** n, x=SMALL, n=SMALLINT)
    add("Pow", (-x) ** n, x=SMALL, n=SMALLINT)
    add("Pow", (-1) ** n, n=INT)
    add("Pow", (-1) ** (n + 1), n=INT)
    add("Pow", (-1) ** (n / 2), n=INT)
    add("Pow", (-1) ** (n + m), n=SMALLINT, m=SMALLINT)
    add("Pow", (-1) ** (n * m), n=SMALLINT, m=SMALLINT)
    add("Pow", (x * y) ** h, x=SMALL, y=SMALL)
    add("Pow", (x ** 2) ** y, x=SMALL, y=EXPS)
    add("Pow", (1 / x) ** y, x=SMALL, y=EXPS)
    add("Pow", exp(x) ** y, x=SMALL, y=EXPS)
    add("Pow", (x ** (2 * n)) ** h, x=SMALL, n=SMALLINT)
    # exp
    add("exp", exp(n * pi * I), n=INT)
    add("exp", exp(n * pi * I / 2), n=INT)
    add("exp", exp(x + n * pi * I), x=X3, n=INT)
    add("exp", exp(x + 2 * n * pi * I), x=X3, n=INT)
    add("exp", exp(I * pi * (n + h)), n=INT)
    add("exp", exp(x * log(y)), x=SMALL, y=SMALL)
    add("exp", exp(I * arg(x)), x=FULL)
    # log
    for e in (log(exp(x)), log(x ** 2), log(1 / x), log(2 * x), log(-x), log(I * x),
              log(Abs(x)), log(sqrt(x)), log(x ** 3), log(exp(I * x)), log(x ** h), log(x)):
        add("log", e, x=FULL)
    add("log", log(x * y), x=SMALL, y=SMALL)
    add("log", log(x ** y), x=SMALL, y=SMALL)
    add("log", log(x / y), x=SMALL, y=SMALL)
    add("log", log(exp(x) * y), x=SMALL, y=SMALL)
    add("log", log(x ** n), x=SMALL, n=SMALLINT)
    # trig
    for f in (sin, cos, tan, cot, sec, csc):
        k = f.__name__
        add(k, f(x), x=FULL)
        add(k, f(x + n * pi), x=X3, n=INT)
        add(k, f(x + n * pi / 2), x=X3, n=INT)
        add(k, f(x + 2 * n * pi), x=X3, n=INT)
        add(k, f(n * pi), n=INT)
        add(k, f(n * pi / 2), n=INT)
        add(k, f(n * pi + pi / 2), n=INT)
        add(k, f(x + n * pi + m * pi), x=[T()], n=SMALLINT, m=SMALLINT)
    add("sinc", sinc(x), x=FULL)
    add("sinc", sinc(n * pi), n=INT)
    add("sinc", sinc(x + n * pi), x=X3, n=INT)
    # hyperbolic
    for f in (sinh, cosh, tanh, coth, sech, csch):
        k = f.__name__
        add(k, f(x), x=FULL)
        add(k, f(x + n * pi * I), x=X3, n=INT)
        add(k, f(x + n * pi * I / 2), x=X3, n=INT)
        add(k, f(n * pi * I), n=INT)
        add(k, f(n * pi * I / 2), n=INT)
    # inverse trig / hyperbolic
    for f, g in ((asin, sin), (acos, cos), (atan, tan), (asinh, sinh), (acosh, cosh),
                 (atanh, tanh), (acoth, coth), (asech, sech), (acsch, csch)):
        add(f.__name__, f(g(x)), x=FULL)
        add(f.__name__, f(x), x=FULL)
        add(f.__name__, f(g(x + y)), x=X3, y=X3)
    # arg, sign, re, im, conjugate
    for f in (arg, sign, re, im, conjugate):
        k = f.__name__
        for e in (f(x), f(x ** 2), f(exp(x)), f(I * x), f(-x), f(1 / x), f(sqrt(x)),
                  f(log(x)), f(exp(I * x)), f(Abs(x))):
            add(k, e, x=FULL)
        add(k, f(x * y), x=SMALL, y=SMALL)
        add(k, f(x + y), x=SMALL, y=SMALL)
        add(k, f(x ** n), x=SMALL, n=SMALLINT)
        add(k, f(x ** y), x=SMALL, y=SMALL)
    # Mul (conjugate pairs)
    add("Mul", x * conjugate(x), x=FULL)
    add("Mul", x * y * conjugate(x), x=SMALL, y=SMALL)
    add("Mul", x ** 2 * conjugate(x), x=FULL)
    add("Mul", conjugate(x) * conjugate(y) * x, x=SMALL, y=SMALL)
    # atan2
    add("atan2", atan2(y, x), x=SIGN, y=SIGN)
    add("atan2", atan2(y, x ** 2), x=SMALL, y=SIGN)
    # Heaviside, DiracDelta
    for f in (Heaviside, DiracDelta):
        for e in (f(x), f(x ** 2), f(-x), f(x + 1), f(Abs(x)), f(exp(x))):
            add(f.__name__, e, x=FULL)
        add(f.__name__, f(x * y), x=SMALL, y=SMALL)
        add(f.__name__, f(x - y), x=SIGN, y=SIGN)
    # KroneckerDelta
    add("KroneckerDelta", KroneckerDelta(n, m), n=INT, m=SMALLINT)
    add("KroneckerDelta", KroneckerDelta(n, 0), n=INT)
    add("KroneckerDelta", KroneckerDelta(n, n + 1), n=INT)
    add("KroneckerDelta", KroneckerDelta(x, y), x=SIGN, y=SIGN)
    # floor, ceiling, frac
    for f in (floor, ceiling, frac):
        k = f.__name__
        for e in (f(x), f(-x), f(x / 2), f(2 * x), f(x + h), f(x ** 2), f(I * x)):
            add(k, e, x=FULL)
        add(k, f(x + n), x=SMALL, n=SMALLINT)
        add(k, f(x + y), x=SMALL, y=SMALL)
        add(k, f(x * n), x=SMALL, n=SMALLINT)
        add(k, f(x + I * y), x=SMALL, y=SMALL)
        add(k, f(n / 2 + m / 2), n=SMALLINT, m=SMALLINT)
    # Mod, Rem
    from sympy import Rem
    for f in (Mod, Rem):
        k = f.__name__
        for e in (f(x, 2), f(2 * x, 2), f(x + 1, 2), f(x, 1), f(x ** 2, 2), f(x, 4),
                  f(x, -2), f(-x, 3), f(x, h), f(3 * x, 3)):
            add(k, e, x=FULL)
        add(k, f(n, m), n=INT, m=SMALLINT)
        add(k, f(x, y), x=SMALL, y=SMALL)
        add(k, f(n * m, m), n=SMALLINT, m=SMALLINT)
        add(k, f(x + n, n), x=SMALL, n=SMALLINT)
    # factorial, gamma, binomial, RF, FF
    for e in (factorial(x), factorial(x + 1), factorial(x - 1), factorial(2 * x),
              factorial(-x), factorial(x / 2)):
        add("factorial", e, x=FULL)
    for e in (gamma(x), gamma(x + 1), gamma(-x), gamma(x / 2), gamma(1 - x), gamma(x + h)):
        add("gamma", e, x=FULL)
    add("binomial", binomial(n, m), n=INT, m=INT)
    add("binomial", binomial(x, n), x=SMALL, n=SMALLINT)
    add("binomial", binomial(n, n + 1), n=INT)
    add("binomial", binomial(n, n - 1), n=INT)
    add("binomial", binomial(n, 2 * n), n=INT)
    for f in (RisingFactorial, FallingFactorial):
        add(f.__name__, f(x, n), x=SMALL, n=SMALLINT)
        add(f.__name__, f(n, m), n=INT, m=SMALLINT)
        add(f.__name__, f(n, n), n=INT)
        add(f.__name__, f(x, x), x=FULL)
        add(f.__name__, f(x, n + 1), x=SMALL, n=SMALLINT)
    # Min, Max
    for f in (Min, Max):
        k = f.__name__
        add(k, f(x, y), x=SIGN, y=SIGN)
        for e in (f(x, 0), f(x, -x), f(x, x + 1), f(x, 1), f(x ** 2, 0), f(Abs(x), 0),
                  f(x, 2 * x), f(exp(x), 0), f(x, -1)):
            add(k, e, x=FULL)
        add(k, f(x, y, 0), x=SMALL, y=SMALL)
        add(k, f(n, m), n=SMALLINT, m=SMALLINT)


# ---------------------------------------------------------------------------
# Mode A: scalar case analysis
# ---------------------------------------------------------------------------

def spec_items_for(expr, pools, choice):
    items = []
    for name in sorted(pools):
        if PLAIN[name] in expr.free_symbols:
            items.append((name, choice[name]))
    return tuple(items)


def classify(r, err, expr, old_best, old_changed, old_all, old_map, points, sat_cx_base):
    """Category of one refine result against the oracle, plus soundness."""
    info = {"result": None if r is None else str(r)}
    if err is not None:
        info["category"] = "timeout" if err == "timeout" else "error"
        info["error"] = err
        return info
    changed = r != expr
    info["changed"] = changed
    verdict = None
    if changed:
        verdict = numeric_compare(r, expr, points)
        info["num"] = verdict.as_text()
        if verdict.bad or verdict.sing:
            pt, t, c = verdict.example
            info["evidence"] = f"at {fmt_point(pt)}: original={fmt_num(t)}, refined={fmt_num(c)}"
        info["unsound"] = verdict.bad > 0
        info["singular"] = verdict.bad == 0 and verdict.sing > 0
        if not verdict.bad and not verdict.ok:
            info["proved"] = provably_equal(r, expr, old_map)
    if not changed and not old_changed:
        cat = "both-unchanged"
    elif not changed:
        cat = "gap"
    elif verdict is not None and verdict.bad:
        cat = "disagree-sat-wrong" if old_changed else "unsound-alone"
    elif not old_changed:
        cat = "sat-further"
    else:
        if any(r == c for c in old_all):
            cat = "agree"
        else:
            rc, oc = cx(r), cx(old_best)
            if rc < oc:
                cat = "sat-further"
            elif oc < rc:
                cat = "old-further"
            else:
                cat = "agree"
    info["category"] = cat
    return info


def analyze_template(task):
    """task = (template index, [choice dicts]); returns list of result dicts."""
    ti, choices = task
    key, expr, pools = TEMPLATES[ti]
    results = []
    # baseline: the same simplifiers on the plain expression (no assumptions)
    base_cx = {name: c for name, c in old_candidates(expr, key)}
    for ci, choice in enumerate(choices):
        items = spec_items_for(expr, pools, choice)
        try:
            results.append(timed(analyze_case, 90.0, key, expr, items, base_cx, ti * 1000 + ci))
        except Timeout:
            results.append({"key": key, "expr": str(expr), "spec": spec_text(items),
                            "sat": {"category": "error", "error": "case timeout"},
                            "up": {"category": "error", "error": "case timeout"}})
        except Exception as e:  # noqa: BLE001
            results.append({"key": key, "expr": str(expr), "spec": spec_text(items),
                            "sat": {"category": "error", "error": repr(e)[:200]},
                            "up": {"category": "error", "error": repr(e)[:200]}})
    return results


SLACK = 2  # an expansion may be up to this many operations bigger than the input
EXPANDERS = {"expand_log", "powdenest", "powsimp", "logcombine"}


def analyze_case(key, expr, items, base_cx, seed):
    syms = {nm: PLAIN[nm] for nm, _ in items}
    qa = q_of(items, syms)
    old_map = {syms[nm]: old_symbol(syms[nm], preds) for nm, preds in items if preds}
    back = {v: k for k, v in old_map.items()}
    points = sample_points(items, syms, seed=seed)
    rec = {"key": key, "expr": str(expr), "spec": spec_text(items), "q": str(qa)}

    # the old system
    cands = []
    try:
        old_auto = expr.xreplace(old_map)
    except Timeout:
        raise
    except Exception as e:  # noqa: BLE001
        # the old system rejects the input itself (Max of imaginary symbols,
        # Heaviside of a non-real argument, ...): no oracle value, refine still runs
        rec["old_error"] = f"{type(e).__name__}: {e}"[:120]
        old_auto = None
    limit = cx(expr)[0] + SLACK
    for name, c in (old_candidates(old_auto, key) if old_auto is not None else []):
        cp = c.xreplace(back)
        if cp == expr:
            continue
        # assumption-driven: automatic evaluation, or a simplifier whose output
        # differs from what it makes of the plain expression (and is not much bigger)
        if name.startswith(("rewrite(Piecewise", "simplify(rewrite(Piecewise")) and cp.has(Piecewise):
            continue  # a Piecewise whose conditions the old system could not decide
        if cp == base_cx.get(name):
            continue  # the simplifier does the same without assumptions
        # expansions may grow a little (log(x*y) -> log(x) + log(y)); every other
        # simplifier or rewrite must make the expression strictly smaller, so a
        # mere change of representation (sec(x) -> 1/cos(x)) is not an oracle win
        if name == "auto" or (name in EXPANDERS and cx(cp)[0] <= limit) or cx(cp) < cx(expr):
            cands.append((name, cp))
    # drop old candidates that are themselves numerically wrong (oracle bugs)
    old_wrong = []
    good = []
    seen = set()
    for name, cp in sorted(cands, key=lambda t: cx(t[1])):
        if cp in seen:
            continue
        seen.add(cp)
        v = numeric_compare(cp, expr, points, budget=4.0)
        if v.bad:
            pt, t, c = v.example
            old_wrong.append(f"{name}: {cp}  at {fmt_point(pt)} original={fmt_num(t)} old={fmt_num(c)}")
        else:
            good.append((name, cp))
    old_changed = bool(good)
    old_best = good[0][1] if good else expr
    rec["old"] = str(old_best)
    rec["old_via"] = good[0][0] if good else ""
    if old_wrong:
        rec["old_wrong"] = old_wrong
    old_all = [c for _, c in good]

    r, err = attempt(logged_refine, 20.0, expr, qa)
    steps = []
    if err is None:
        r, steps = r
    rec["sat"] = classify(r, err, expr, old_best, old_changed, old_all, old_map, points, base_cx)
    if rec["sat"].get("unsound") or rec["sat"].get("singular"):
        rec["sat"]["blame"] = blame(steps, points)
    ru, erru = attempt(sympy_refine, 20.0, expr, qa)
    rec["up"] = classify(ru, erru, expr, old_best, old_changed, old_all, old_map, points, base_cx)
    rec["same_as_sympy"] = (err is None and erru is None and r == ru)
    return rec


# ---------------------------------------------------------------------------
# Mode A: matrix keys
# ---------------------------------------------------------------------------

X = MatrixSymbol("X", 2, 2)
Y = MatrixSymbol("Y", 2, 2)


def _gen(prefix, **kw):
    return [[Symbol(f"{prefix}{i}{j}", **kw) for j in range(2)] for i in range(2)]


def matrix_instances(pred):
    g = _gen("x")
    s = Symbol
    if pred == "none":
        return [Matrix(g)], True
    if pred == "symmetric":
        return [Matrix([[s("p"), s("q")], [s("q"), s("r")]])], True
    if pred == "diagonal":
        return [Matrix([[s("p"), 0], [0, s("r")]])], True
    if pred == "upper_triangular":
        return [Matrix([[s("p"), s("q")], [0, s("r")]])], True
    if pred == "lower_triangular":
        return [Matrix([[s("p"), 0], [s("q"), s("r")]])], True
    if pred == "triangular":
        return [Matrix([[s("p"), s("q")], [0, s("r")]]), Matrix([[s("p"), 0], [s("q"), s("r")]])], True
    if pred == "hermitian":
        pr, rr, q = s("p", real=True), s("r", real=True), s("q")
        return [Matrix([[pr, q], [conjugate(q), rr]])], True
    if pred == "real_elements":
        return [Matrix(_gen("x", real=True))], True
    if pred == "integer_elements":
        return [Matrix(_gen("x", integer=True))], True
    if pred == "zero":
        return [Matrix.zeros(2, 2)], True
    if pred == "identity":
        return [Matrix.eye(2)], True
    c, sn = Rational(3, 5), Rational(4, 5)
    rot = Matrix([[c, -sn], [sn, c]])
    refl = Matrix([[c, sn], [sn, -c]])
    if pred == "orthogonal":
        return [rot, refl, Matrix.eye(2)], False
    if pred == "unitary":
        return [rot, Matrix([[c, 4 * I / 5], [4 * I / 5, c]]), Matrix([[I, 0], [0, 1]])], False
    if pred in ("invertible", "fullrank"):
        return [Matrix([[1, 2], [3, 4]]), Matrix([[2, I], [1, 5]])], False
    if pred == "singular":
        return [Matrix([[1, 2], [3, 6]]), Matrix([[1, I], [I, -1]]), Matrix.zeros(2, 2)], False
    if pred == "positive_definite":
        # the last one is positive definite in the x^T M x > 0 sense but not symmetric
        return [Matrix([[2, 1], [1, 3]]), Matrix([[5, 2], [2, 1]]), Matrix([[2, 1], [-1, 2]])], False
    if pred == "normal":
        return [rot, Matrix([[1, 2], [2, 1]])], False
    raise KeyError(pred)


MATRIX_PREDS = ["none", "symmetric", "diagonal", "zero", "orthogonal", "unitary",
                "invertible", "singular", "upper_triangular", "lower_triangular", "triangular",
                "positive_definite", "hermitian", "real_elements", "integer_elements",
                "normal", "fullrank"]

MATRIX_TEMPLATES = [
    ("Transpose", lambda: Transpose(X)), ("Transpose", lambda: Transpose(X * Y)),
    ("Transpose", lambda: Transpose(X + Y)),
    ("Inverse", lambda: Inverse(X)), ("Inverse", lambda: Inverse(Transpose(X))),
    ("Inverse", lambda: Inverse(X * Y)),
    ("Determinant", lambda: Determinant(X)), ("Determinant", lambda: Determinant(X * Y)),
    ("Determinant", lambda: Determinant(Transpose(X))),
    ("Trace", lambda: Trace(X)), ("Trace", lambda: Trace(X * Y)), ("Trace", lambda: Trace(Transpose(X))),
    ("MatrixElement", lambda: X[0, 1]), ("MatrixElement", lambda: X[1, 0]),
    ("MatrixElement", lambda: X[0, 0]),
    ("MatMul", lambda: MatMul(X, Transpose(X))), ("MatMul", lambda: MatMul(Transpose(X), X)),
    ("MatMul", lambda: MatMul(X, Y)), ("MatMul", lambda: MatMul(X, X.adjoint())),
    ("MatMul", lambda: MatMul(Y, X)),
    ("MatAdd", lambda: MatAdd(X, Y)), ("MatAdd", lambda: MatAdd(X, -Transpose(X))),
    ("MatAdd", lambda: MatAdd(X, Transpose(X))),
    ("HadamardProduct", lambda: HadamardProduct(X, Y)),
    ("HadamardProduct", lambda: HadamardProduct(X, Identity(2))),
    ("HadamardProduct", lambda: HadamardProduct(X, Transpose(X))),
]


def matrix_candidates():
    Z = ZeroMatrix(2, 2)
    Id = Identity(2)
    mats = [X, X.T, X.conjugate(), X.adjoint(), X.I, Id, Z, Y, Y.T, X * Y, Y * X, X.T * Y.T,
            Y.T * X.T, Y.I * X.I, X.T.I, 2 * X, X + Y, X * X, X.T * X, X * X.T, Y * X.T,
            X.T * Y, -X, HadamardProduct(X, Y), -Y, Y.I, X.I * Y.I, Y.I * X.T]
    scal = [S.Zero, S.One, S.NegativeOne, Trace(X), Determinant(X), X[0, 1], X[1, 0], X[0, 0],
            Determinant(Y), Trace(Y), Determinant(X) * Determinant(Y), X[0, 0] + X[1, 1],
            Trace(X * Y), Trace(Y * X), X[0, 0] * X[1, 1], S(2), Trace(X * X.T)]
    return mats, scal


def mat_eval(e, xi, yi):
    v = e.xreplace({X: sympy.ImmutableMatrix(xi), Y: sympy.ImmutableMatrix(yi)})
    v = v.doit()
    if hasattr(v, "as_explicit") and getattr(v, "is_Matrix", False):
        v = v.as_explicit()
    return v


def mat_equal(e1, e2, insts):
    """True / False / None on all instances."""
    yi = Matrix(_gen("y"))
    for xi in insts:
        try:
            v1 = mat_eval(e1, xi, yi)
            v2 = mat_eval(e2, xi, yi)
        except Timeout:
            raise
        except Exception:  # noqa: BLE001
            return None
        if getattr(v1, "is_Matrix", False) != getattr(v2, "is_Matrix", False):
            return False
        if getattr(v1, "is_Matrix", False):
            if v1.shape != v2.shape:
                return False
            d = (v1 - v2).applyfunc(lambda t: simplify(sympy.expand(t)))
            if not d.is_zero_matrix:
                if any(t.is_number and t != 0 for t in d):
                    return False
                return None if d.is_zero_matrix is None else False
        else:
            if v1.has(nan, zoo) or v2.has(nan, zoo):
                if v1 != v2:
                    return None
                continue
            d = simplify(sympy.expand(v1 - v2))
            if d != 0:
                return False if d.is_number else None
    return True


def analyze_matrix(task):
    ti, pred = task
    key, mk = MATRIX_TEMPLATES[ti]
    expr = mk()
    qa = S.true if pred == "none" else getattr(Q, pred)(X)
    rec = {"key": key, "expr": str(expr), "spec": f"X:{pred}", "q": str(qa)}
    try:
        insts, _symbolic = matrix_instances(pred)
    except KeyError:
        return rec
    ismat = getattr(expr, "is_Matrix", False)

    def run():
        # "old system": ZeroMatrix/Identity substitution, then candidate search
        cands = []
        if pred == "zero":
            cands.append(expr.xreplace({X: ZeroMatrix(2, 2)}).doit())
        if pred == "identity":
            cands.append(expr.xreplace({X: Identity(2)}).doit())
        mats, scal = matrix_candidates()
        cands += mats if ismat else scal
        general, _ = matrix_instances("none")
        good = []
        for c in cands:
            if c == expr or getattr(c, "is_Matrix", False) != ismat:
                continue
            if cx(c) >= cx(expr) and c not in cands[:1]:
                continue
            if mat_equal(c, expr, insts) and (pred == "none" or mat_equal(c, expr, general) is not True):
                good.append(c)  # true under the predicate, not an identity for every matrix
        if pred == "none":
            good = []  # without an assumption nothing is assumption-driven
        good.sort(key=cx)
        old_best = good[0] if good else expr
        rec["old"] = str(old_best)
        for tag, fn in (("sat", satrefine.refine), ("up", sympy_refine)):
            if tag == "sat":
                rr, err = attempt(logged_refine, 20.0, expr, qa)
                steps = rr[1] if err is None else []
                r = rr[0] if err is None else None
            else:
                r, err = attempt(fn, 20.0, expr, qa)
            info = {"result": str(r)}
            if err is not None:
                info.update(category="timeout" if err == "timeout" else "error", error=err)
            else:
                changed = r != expr
                if changed:
                    eq = mat_equal(r, expr, insts)
                    info["num"] = f"instances-equal={eq}"
                    info["unsound"] = eq is False
                    if eq is False:
                        info["evidence"] = f"differs from the original on an explicit {pred} 2x2 instance"
                        if tag == "sat":
                            info["blame"] = "; ".join(f"{s[0]}: {s[1]} -> {s[2]}" for s in steps) or "?"
                if not changed and not good:
                    cat = "both-unchanged"
                elif not changed:
                    cat = "gap"
                elif info.get("unsound"):
                    cat = "disagree-sat-wrong" if good else "unsound-alone"
                elif not good:
                    cat = "sat-further"
                elif r in good or cx(r) == cx(old_best):
                    cat = "agree"
                else:
                    cat = "sat-further" if cx(r) < cx(old_best) else "old-further"
                info["category"] = cat
            rec[tag] = info
        rec["same_as_sympy"] = rec["sat"].get("result") == rec["up"].get("result")

    try:
        timed(run, 120.0)
    except Timeout:
        rec.setdefault("sat", {"category": "error", "error": "timeout"})
        rec.setdefault("up", {"category": "error", "error": "timeout"})
    except Exception as e:  # noqa: BLE001
        rec.setdefault("sat", {"category": "error", "error": repr(e)[:200]})
        rec.setdefault("up", {"category": "error", "error": repr(e)[:200]})
    return [rec]


# ---------------------------------------------------------------------------
# worker plumbing
# ---------------------------------------------------------------------------

def worker_init(backend_name):
    sat_backend.set_backend(backend_name)
    install_step_logging()
    if not TEMPLATES:
        build_templates()


def run_task(task):
    kind, payload = task
    try:
        if kind == "scalar":
            return analyze_template(payload)
        return analyze_matrix(payload)
    except Exception as e:  # noqa: BLE001
        return [{"key": "?", "expr": str(payload), "spec": "",
                 "sat": {"category": "error", "error": repr(e)[:200]},
                 "up": {"category": "error", "error": repr(e)[:200]}}]


def mode_a_tasks(keys, limit):
    build_templates()
    tasks = []
    total = 0
    for ti, (key, expr, pools) in enumerate(TEMPLATES):
        if keys and key not in keys:
            continue
        names = sorted(nm for nm in pools if PLAIN[nm] in expr.free_symbols)
        combos = [dict(zip(names, c)) for c in itertools.product(*[pools[nm] for nm in names])]
        # de-duplicate choices that give the same spec
        seen, uniq = set(), []
        for c in combos:
            k = tuple((nm, c[nm]) for nm in names)
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        if limit and total + len(uniq) > limit:
            uniq = uniq[: max(0, limit - total)]
        if not uniq:
            continue
        total += len(uniq)
        for i in range(0, len(uniq), 10):
            tasks.append(("scalar", (ti, uniq[i:i + 10])))
    for ti, (key, _) in enumerate(MATRIX_TEMPLATES):
        if keys and key not in keys:
            continue
        for pred in MATRIX_PREDS:
            tasks.append(("matrix", (ti, pred)))
    return tasks


def _error_records(task, e):
    return [{"key": "?", "expr": str(task), "spec": "",
             "sat": {"category": "error", "error": repr(e)[:200]},
             "up": {"category": "error", "error": repr(e)[:200]}}]


def _a_timeout(task, why):
    kind, payload = task
    if kind == "scalar":
        ti, choices = payload
        key, expr, pools = TEMPLATES[ti]
        return [{"key": key, "expr": str(expr), "spec": spec_text(spec_items_for(expr, pools, c)),
                 "sat": {"category": "timeout", "error": why},
                 "up": {"category": "timeout", "error": why}} for c in choices]
    ti, pred = payload
    key, mk = MATRIX_TEMPLATES[ti]
    return [{"key": key, "expr": str(mk()), "spec": f"X:{pred}",
             "sat": {"category": "timeout", "error": why}, "up": {"category": "timeout", "error": why}}]


def run_parallel(tasks, jobs, backend_name, label):
    worker_init(backend_name)
    return run_forked(tasks, jobs, run_task, label, 180.0, _a_timeout, _error_records)


# ---------------------------------------------------------------------------
# Mode B: SymPy test-suite corpus
# ---------------------------------------------------------------------------

MODE_B_MODULES = [
    "sympy/functions/elementary/tests/test_complexes.py",
    "sympy/functions/elementary/tests/test_exponential.py",
    "sympy/functions/elementary/tests/test_trigonometric.py",
    "sympy/functions/elementary/tests/test_hyperbolic.py",
    "sympy/functions/elementary/tests/test_integers.py",
    "sympy/functions/elementary/tests/test_miscellaneous.py",
    "sympy/functions/elementary/tests/test_piecewise.py",
    "sympy/functions/combinatorial/tests/test_comb_factorials.py",
    "sympy/functions/special/tests/test_gamma_functions.py",
    "sympy/functions/special/tests/test_delta_functions.py",
    "sympy/functions/special/tests/test_tensor_functions.py",
    "sympy/core/tests/test_power.py",
    "sympy/core/tests/test_arit.py",
    "sympy/core/tests/test_complex.py",
    "sympy/core/tests/test_evalf.py",
    "sympy/simplify/tests/test_simplify.py",
    "sympy/simplify/tests/test_powsimp.py",
    "sympy/matrices/expressions/tests/test_transpose.py",
    "sympy/matrices/expressions/tests/test_inverse.py",
    "sympy/matrices/expressions/tests/test_determinant.py",
    "sympy/matrices/expressions/tests/test_trace.py",
    "sympy/matrices/expressions/tests/test_matmul.py",
    "sympy/matrices/expressions/tests/test_matadd.py",
    "sympy/matrices/expressions/tests/test_hadamard.py",
    "sympy/matrices/expressions/tests/test_indexing.py",
    "sympy/matrices/expressions/tests/test_matexpr.py",
]

DECL_FUNCS = {"Symbol", "symbols", "Dummy", "var"}
KEEP_KW = {"cls", "seq", "commutative"}


class StripAssumptions(ast.NodeTransformer):
    """Remove assumption keywords from Symbol/symbols/Dummy calls."""

    def __init__(self):
        self.changed = False

    def visit_Call(self, node):
        self.generic_visit(node)
        fname = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else None)
        if fname in DECL_FUNCS:
            kept = []
            for kw in node.keywords:
                if kw.arg is None or kw.arg in KEEP_KW:
                    kept.append(kw)
                else:
                    self.changed = True
            node.keywords = kept
        return node


def strip(stmt):
    tr = StripAssumptions()
    new = tr.visit(ast.fix_missing_locations(ast.parse(ast.unparse(stmt)).body[0]))
    return ast.fix_missing_locations(new), tr.changed


def _exec(stmt, ns, secs=10.0):
    code = compile(ast.Module(body=[stmt], type_ignores=[]), "<oracle>", "exec")
    _, err = attempt(exec, secs, code, ns)
    return err


def _eval(src_node, ns, secs=10.0):
    code = compile(ast.Expression(body=src_node), "<oracle>", "eval")
    return attempt(eval, secs, code, ns)


def _flatten_syms(v):
    if isinstance(v, (Symbol,)):
        return [v]
    if isinstance(v, (tuple, list)):
        out = []
        for t in v:
            out.extend(_flatten_syms(t))
        return out
    return []


def record_pairs(stmt, ns_old, ns_plain, pairs):
    names = []
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
    for nm in names:
        if nm in ns_old and nm in ns_plain:
            o, p = _flatten_syms(ns_old[nm]), _flatten_syms(ns_plain[nm])
            if len(o) == len(p):
                for so, sp in zip(o, p):
                    if so is not sp and so.name == sp.name and so._assumptions_orig:
                        pairs[sp] = so


PURE_BUILTINS = {"abs", "S", "Rational", "Integer", "Float", "sqrt", "root", "cbrt"}


def pure_side(node, ns):
    """True if the AST only builds an expression: no method calls, no simplifiers.

    Asserts such as ``sign(x).rewrite(Piecewise) == ...`` or
    ``simplify(e) == ...`` test an operation other than automatic evaluation,
    so they are not refine cases.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            if not isinstance(sub.func, ast.Name):
                return False
            name = sub.func.id
            if name in PURE_BUILTINS:
                continue
            obj = ns.get(name)
            if isinstance(obj, type) and issubclass(obj, Basic):
                continue
            if type(obj).__name__ == "UndefinedFunction":
                continue
            mod = getattr(obj, "__module__", "") or ""
            if mod.startswith("sympy.functions") and callable(obj):
                continue
            return False
        if isinstance(sub, (ast.Lambda, ast.ListComp, ast.GeneratorExp, ast.DictComp, ast.SetComp)):
            return False
    return True


def head_key(e):
    name = type(e).__name__
    return name if name in _upstream.handlers_dict else None


def mode_b_case(mod, func, lineno, lhs_node, rhs_node, ns_old, ns_plain, pairs):
    """Classify one ``assert L == R``; returns a record or None if not applicable."""
    L_old, e1 = _eval(lhs_node, ns_old)
    R_old, e2 = _eval(rhs_node, ns_old)
    L_pl, e3 = _eval(lhs_node, ns_plain)
    R_pl, e4 = _eval(rhs_node, ns_plain)
    src = f"{ast.unparse(lhs_node)} == {ast.unparse(rhs_node)}"
    base = {"module": mod, "test": func, "line": lineno, "assert": src}
    if e1 or e2 or e3 or e4:
        return dict(base, status="unreplayable", why=(e1 or e2 or e3 or e4))
    # choose the side that is a handler-headed plain expression built without
    # method calls or simplifiers; the other side is the asserted value
    target, expected = None, None
    if not (pure_side(lhs_node, ns_plain) and pure_side(rhs_node, ns_plain)):
        return None
    for tgt, exp_old, node in ((L_pl, R_old, lhs_node), (R_pl, L_old, rhs_node)):
        if isinstance(node, ast.Name):
            continue  # a variable computed earlier by an unknown operation
        if not (isinstance(tgt, Basic) and head_key(tgt)):
            continue
        if head_key(tgt) == "Mul" and not tgt.has(conjugate):
            continue  # the Mul key only cancels conjugate pairs
        target, expected = tgt, exp_old
        break
    if target is None:
        return None
    fs = target.free_symbols if isinstance(target, Basic) else set()
    declared = [s for s in fs if s in pairs]
    if not declared:
        return None
    base["key"] = head_key(target)
    try:
        holds = bool(L_old == R_old)
    except Exception:  # noqa: BLE001
        holds = False
    if not holds:
        return dict(base, status="assert-fails")
    # assumptions
    items = []
    for s in sorted(declared, key=lambda t: t.name):
        preds = []
        for k, v in sorted(pairs[s]._assumptions_orig.items()):
            if k == "commutative" and v:
                continue
            if not hasattr(Q, k):
                return dict(base, status="unreplayable", why=f"no Q predicate for {k}")
            preds.append((k, v))
        items.append((s, tuple(preds)))
    conj = []
    for s, preds in items:
        for k, v in preds:
            atom = getattr(Q, k)(s)
            conj.append(atom if v else ~atom)
    qa = And(*conj) if conj else S.true
    to_old = {s: pairs[s] for s in declared}
    to_plain = {v: k for k, v in pairs.items()}
    base.update(expr=str(target), q=str(qa), expected=str(expected))
    # sample points: keyed by the plain symbols (Dummies are distinct objects)
    lists = [values_for(preds) for _, preds in items]
    if any(not lst for lst in lists):
        points = []
    else:
        combos = list(itertools.product(*lists))
        if len(combos) > 18:
            combos = random.Random(lineno).sample(combos, 18)
        points = [{s: v for (s, _), v in zip(items, c)} for c in combos]
    undeclared = [s for s in fs if s not in pairs and isinstance(s, Symbol)]
    if undeclared and points:
        extra = [NUMS[22], NUMS[12], NUMS[25]]  # a Gaussian, a rational and a complex value
        points = [dict(pt, **{}) | {s: extra[(i + j) % 3] for j, s in enumerate(undeclared)}
                  for i, pt in enumerate(points)]

    expected_back = expected.xreplace(to_plain) if isinstance(expected, Basic) else expected

    def judge(r, err):
        if err is not None:
            return {"category": "timeout" if err == "timeout" else "error", "error": err}
        info = {"result": str(r)}
        if r == target:
            info["category"] = "trivial" if expected_back == target else "gap"
            return info
        r_old = r.xreplace(to_old) if isinstance(r, Basic) else r
        if r_old == expected or r == expected_back:
            info["category"] = "match"
            return info
        v = numeric_compare(r, target, points)
        info["num"] = v.as_text()
        if v.bad:
            pt, t, c = v.example
            info["evidence"] = f"at {fmt_point(pt)}: original={fmt_num(t)}, refined={fmt_num(c)}"
            info["category"] = "unsound"
            info["unsound"] = True
            return info
        if v.sing:
            pt, t, c = v.example
            info["evidence"] = f"at {fmt_point(pt)}: original={fmt_num(t)}, refined={fmt_num(c)}"
        if provably_equal(r, expected_back, to_old) or (v.ok and not v.sing):
            info["category"] = "equivalent-form"
        else:
            info["category"] = "undecided"
        return info

    rr, err = attempt(logged_refine, 20.0, target, qa)
    r, steps = (rr if err is None else (None, []))
    rec = dict(base, status="replayed")
    rec["sat"] = judge(r, err)
    if rec["sat"].get("unsound"):
        rec["sat"]["blame"] = blame(steps, points)
    ru, erru = attempt(sympy_refine, 20.0, target, qa)
    rec["up"] = judge(ru, erru)
    rec["same_as_sympy"] = err is None and erru is None and r == ru
    # the asserted value itself, checked numerically (oracle sanity)
    if isinstance(expected_back, Basic) and expected_back != target:
        ov = numeric_compare(expected_back, target, points, budget=4.0)
        if ov.bad:
            pt, t, c = ov.example
            rec["old_wrong"] = [f"asserted {expected_back} at {fmt_point(pt)}: "
                                f"original={fmt_num(t)} asserted={fmt_num(c)}"]
    return rec


def walk_body(stmts, mod, func, ns_old, ns_plain, pairs, out):
    for st in stmts:
        if isinstance(st, ast.Assert):
            t = st.test
            if (isinstance(t, ast.Compare) and len(t.ops) == 1
                    and isinstance(t.ops[0], (ast.Eq, ast.Is))):
                try:
                    rec = timed(mode_b_case, 60.0, mod, func, st.lineno, t.left,
                                t.comparators[0], ns_old, ns_plain, pairs)
                except Timeout:
                    rec = {"module": mod, "test": func, "line": st.lineno,
                           "assert": ast.unparse(t), "status": "unreplayable", "why": "timeout"}
                except Exception as e:  # noqa: BLE001
                    rec = {"module": mod, "test": func, "line": st.lineno,
                           "assert": ast.unparse(t), "status": "unreplayable", "why": repr(e)[:120]}
                if rec is not None:
                    out.append(rec)
            continue
        if isinstance(st, ast.With):
            src = ast.unparse(st.items[0].context_expr)
            if "raises" in src:
                continue
            walk_body(st.body, mod, func, ns_old, ns_plain, pairs, out)
            continue
        if isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            _exec(st, ns_old)
            _exec(st, ns_plain)
            continue
        _exec(st, ns_old)
        st2, _ = strip(st)
        _exec(st2, ns_plain)
        if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            record_pairs(st, ns_old, ns_plain, pairs)


def run_mode_b_module(path):
    worker_init(ARGS_BACKEND[0])
    full = Path(sympy.__file__).resolve().parents[1] / path     # the checkout sympy is imported from
    modname = path[:-3].replace("/", ".")
    out = []
    try:
        mod = importlib.import_module(modname)
    except Exception as e:  # noqa: BLE001
        return path, [{"module": path, "status": "unreplayable", "why": f"import: {e}"}]
    tree = ast.parse(full.read_text())
    ns_old_mod = dict(vars(mod))
    ns_plain_mod = dict(vars(mod))
    pairs = {}
    for st in tree.body:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            st2, changed = strip(st)
            if changed:
                _exec(st2, ns_plain_mod)
                record_pairs(st, ns_old_mod, ns_plain_mod, pairs)
    for st in tree.body:
        if isinstance(st, ast.FunctionDef) and st.name.startswith("test"):
            ns_old = dict(ns_old_mod)
            ns_plain = dict(ns_plain_mod)
            p = dict(pairs)
            try:
                walk_body(st.body, path, st.name, ns_old, ns_plain, p, out)
            except Exception as e:  # noqa: BLE001
                out.append({"module": path, "test": st.name, "status": "unreplayable",
                            "why": repr(e)[:120]})
    return path, out


ARGS_BACKEND = ["combined"]


def _b_task(path):
    return run_mode_b_module(path)[1]


def _b_timeout(path, why):
    return [{"module": path, "status": "unreplayable", "why": why}]


def _b_error(path, e):
    return _b_timeout(path, repr(e)[:120])


def run_mode_b(jobs):
    return run_forked(MODE_B_MODULES, jobs, _b_task, "mode B", 1500.0, _b_timeout, _b_error)


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

A_CATS = ["agree", "both-unchanged", "sat-further", "old-further", "gap",
          "disagree-sat-wrong", "unsound-alone", "timeout", "error"]
B_CATS = ["match", "equivalent-form", "gap", "trivial", "unsound", "undecided", "timeout", "error"]


def report_a(recs, show, max_show):
    print("\n=== Mode A: old-system oracle ===")
    print(f"cases: {len(recs)}")
    by_key = collections.defaultdict(list)
    for r in recs:
        by_key[r["key"]].append(r)
    for tag, title in (("sat", "satrefine.refine"), ("up", "sympy.refine (for comparison)")):
        print(f"\n-- {title} vs the old system --")
        rows = []
        tot = collections.Counter()
        for k in sorted(by_key):
            c = collections.Counter(r.get(tag, {}).get("category", "error") for r in by_key[k])
            uns = sum(1 for r in by_key[k] if r.get(tag, {}).get("unsound"))
            sing = sum(1 for r in by_key[k] if r.get(tag, {}).get("singular"))
            c["unsound"] = uns
            c["singular"] = sing
            tot.update(c)
            tot["cases"] += len(by_key[k])
            rows.append([k, len(by_key[k])] + [c[x] for x in A_CATS] + [uns, sing])
        rows.append(["TOTAL", tot["cases"]] + [tot[x] for x in A_CATS] + [tot["unsound"], tot["singular"]])
        table(rows, ["key", "cases"] + A_CATS + ["UNSOUND", "sing-mismatch"], right=True)
    same = sum(1 for r in recs if r.get("same_as_sympy"))
    print(f"\nsatrefine result identical to sympy.refine: {same}/{len(recs)}")
    ow = [r for r in recs if r.get("old_wrong")]
    print(f"cases where an old-system candidate was numerically WRONG (oracle defects, discarded): {len(ow)}")
    oe = collections.Counter(r["key"] for r in recs if r.get("old_error"))
    print("cases the old system rejects outright (no oracle value; counted as old-unchanged): "
          + (", ".join(f"{k}={v}" for k, v in sorted(oe.items())) or "0"))
    _show_cases(recs, show, max_show, "A")
    if ow and show == "all":
        print("\n-- old-system candidates rejected numerically --")
        for r in ow[:max_show]:
            print(f"  {r['expr']}  [{r['spec']}]")
            for w in r["old_wrong"][:2]:
                print(f"      {w}")


def _show_cases(recs, show, max_show, mode):
    uns = [r for r in recs if r.get("sat", {}).get("unsound")]
    print(f"\n-- UNSOUND satrefine rewrites (mode {mode}): {len(uns)} --")
    for r in uns:
        s = r["sat"]
        up = r.get("up", {})
        print(f"* [{r.get('key')}] {r.get('expr')}   assuming {r.get('spec') or r.get('q')}")
        if mode == "B":
            print(f"    source: {r['module']}:{r['line']} ({r['test']})  assert {r['assert']}")
        print(f"    satrefine : {s.get('result')}")
        print(f"    oracle    : {r.get('old', r.get('expected'))}")
        print(f"    sympy     : {up.get('result')}  ({'also unsound' if up.get('unsound') else up.get('category')})")
        print(f"    evidence  : {s.get('evidence')}  [{s.get('num')}]")
        print(f"    blame     : {s.get('blame')}")
    sing = [r for r in recs if r.get("sat", {}).get("singular")]
    if sing:
        print(f"\n-- singular mismatches (finite vs zoo/nan at a pole; mode {mode}): {len(sing)} --")
        for r in sing[:max_show if show != "all" else len(sing)]:
            s = r["sat"]
            print(f"* [{r.get('key')}] {r.get('expr')} assuming {r.get('spec') or r.get('q')}: "
                  f"sat={s.get('result')}; {s.get('evidence')}")
    if show in ("gaps", "all"):
        cats = ("gap", "old-further") if mode == "A" else ("gap",)
        print(f"\n-- coverage gaps (mode {mode}; at most {max_show} per key and category) --")
        by = collections.defaultdict(list)
        for r in recs:
            c = r.get("sat", {}).get("category")
            if c in cats:
                by[(r.get("key"), c)].append(r)
        for (k, c), lst in sorted(by.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            print(f"  [{k}] {c}: {len(lst)}")
            for r in lst[:max_show]:
                if mode == "A":
                    print(f"      {r['expr']}  [{r['spec']}]  sat: {r['sat'].get('result')}  "
                          f"old ({r.get('old_via')}): {r.get('old')}")
                else:
                    print(f"      {r['module'].split('/')[-1]}:{r['line']}  {r['assert']}  "
                          f"[{r.get('q')}]  sat: {r['sat'].get('result')}")
    if show == "all":
        print(f"\n-- satrefine goes further than the oracle (mode {mode}) --")
        for r in recs:
            if r.get("sat", {}).get("category") in ("sat-further", "equivalent-form", "undecided"):
                print(f"      {r.get('expr')}  [{r.get('spec') or r.get('q')}]  sat: {r['sat'].get('result')}"
                      f"  oracle: {r.get('old', r.get('expected'))}  ({r['sat'].get('category')})")


def report_b(recs, show, max_show):
    print("\n=== Mode B: SymPy test-suite corpus ===")
    by_mod = collections.defaultdict(list)
    for r in recs:
        by_mod[r["module"]].append(r)
    for tag, title in (("sat", "satrefine.refine"), ("up", "sympy.refine (for comparison)")):
        print(f"\n-- {title} vs asserted old-system values --")
        rows = []
        tot = collections.Counter()
        for mod in MODE_B_MODULES:
            lst = by_mod.get(mod, [])
            rep = [r for r in lst if r.get("status") == "replayed"]
            c = collections.Counter(r[tag]["category"] for r in rep)
            other = collections.Counter(r.get("status") for r in lst if r.get("status") != "replayed")
            row = [mod.split("sympy/")[-1], len(lst), other["unreplayable"], other["assert-fails"], len(rep)]
            row += [c[x] for x in B_CATS]
            rows.append(row)
            tot["found"] += len(lst)
            tot["unrepl"] += other["unreplayable"]
            tot["fails"] += other["assert-fails"]
            tot["rep"] += len(rep)
            tot.update(c)
        rows.append(["TOTAL", tot["found"], tot["unrepl"], tot["fails"], tot["rep"]] + [tot[x] for x in B_CATS])
        table(rows, ["module", "found", "unreplayable", "assert-fails", "replayed"] + B_CATS, right=True)
    rep = [r for r in recs if r.get("status") == "replayed"]
    kc = collections.Counter(r["key"] for r in rep)
    print("\nreplayed cases by handler key: " + ", ".join(f"{k}={v}" for k, v in sorted(kc.items())))
    ow = [r for r in rep if r.get("old_wrong")]
    print(f"asserted values numerically wrong at our points (oracle/point-set defects): {len(ow)}")
    for r in ow[:max_show]:
        print(f"    {r['module'].split('/')[-1]}:{r['line']} {r['old_wrong'][0]}")
    _show_cases(rep, show, max_show, "B")


def main():
    args = ARGS
    ARGS_BACKEND[0] = args.backend
    print(f"refine_oracle: handlers={args.handlers} backend={args.backend} "
          f"sympy={sympy.__version__} ({Path(sympy.__file__).parent})")
    print(f"handler keys registered: {len(HANDLER_KEYS)}")
    all_recs = {}
    t0 = time.time()
    if args.mode in ("a", "both"):
        keys = {k for k in args.keys.split(",") if k}
        tasks = mode_a_tasks(keys, args.limit)
        recs = run_parallel(tasks, args.jobs, args.backend, "mode A")
        all_recs["a"] = recs
        covered = {r["key"] for r in recs}
        missing = [k for k in HANDLER_KEYS if k not in covered]
        report_a(recs, args.show, args.max_show)
        if missing and not keys:
            print(f"handler keys without mode A templates: {missing}")
        if DROPPED:
            print(f"templates dropped because plain automatic evaluation changed the head: {len(DROPPED)}")
    if args.mode in ("b", "both"):
        recs = run_mode_b(args.jobs)
        all_recs["b"] = recs
        report_b(recs, args.show, args.max_show)
    print(f"\ntotal time {time.time() - t0:.0f}s")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(all_recs, fh, indent=1, default=str)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a measurement never fails
        traceback.print_exc()
    sys.exit(0)
