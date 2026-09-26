"""Numeric values and comparison of a rewrite with its input, and SymPy's conventions at infinity.

Scalar family: :func:`numeric` evaluates at 20 digits to a complex or a
failure label ("error", "unevaluated", "nan", "inf"); :func:`agree` compares
with a relative tolerance of 1e-7; :func:`compare` checks two expressions at
given points and :func:`check` (``refine_fuzz``'s own check) draws random
satisfying points itself.  A point where both sides fail is skipped.

Extended family (:func:`ext_value`, :func:`ext_compare`): a value is a finite
complex; ("inf", direction) for a signed or directed infinity; "zoo"; "nan"
(nan or an AccumBounds: no value); or "unevaluated"/"error".
``KroneckerDelta`` is decided by ``Eq``, each ``Piecewise`` condition on its
own.  A point where the input has no value ("nan") is skipped and counted;
so is one where a side cannot be evaluated.  A mismatch is excused, and
counted per label, when it comes from a SymPy convention
(:func:`ext_convention`):

* "zoo vs signed infinity (1/0 = zoo | log(0) = zoo)": one side is zoo, the
  other a signed infinity, and an exact 1/0 or log(0) produced the zoo (zoo
  from a function's own pole, such as acsch(0), is reported);
* "log of a non-positive infinity": a side takes log at -oo or oo*I (SymPy
  gives oo and drops the imaginary part);
* "atan2 of two infinities": atan2(oo, oo) = 0 etc. are arbitrary.

Every other mismatch is a counterexample: at a finite point, at an infinite
point, or "undefined output" (the input has a value, the output is nan).
A mismatch is evidence, not proof: a removable singularity or a pole of the
input can show up as one, so read the counterexample.
"""
from __future__ import annotations

from collections import Counter

from sympy import (Add, Eq, KroneckerDelta, Mul, N, Piecewise, Pow, S, atan2, log, nan, oo, zoo)
from sympy.calculus.accumulationbounds import AccumBounds
from sympy.core.basic import Basic
from sympy.core.expr import Expr

from . import assumptions as A
from .workers import NO_SWALLOW

FAILED = ("error", "unevaluated", "nan", "inf")


def numeric(e):
    try:
        v = N(e, 20)
    except Exception:
        return "error"
    if not isinstance(v, Expr):
        return "unevaluated"
    if v.has(nan) or v is nan: return "nan"
    if v.has(zoo) or v.has(oo): return "inf"
    try:
        return complex(v)
    except Exception:
        return "unevaluated"


def agree(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return a == b or (a in ("error", "unevaluated") or b in ("error", "unevaluated"))
    try:
        return abs(a - b) <= 1e-7 * max(1.0, abs(a), abs(b))
    except OverflowError:
        return True  # both astronomically large: treat as agreeing rather than crash


def check(expr, refined, assumptions, combos, rel, rng, samples=12):
    """``refine_fuzz``'s check at random satisfying points: (n_checked, counterexample or None)."""
    syms = sorted(expr.free_symbols | refined.free_symbols, key=str)
    checked = 0
    for _ in range(200):
        sample = {}
        for s in syms:
            v = A.draw(combos.get(s, ()), rng)
            if v is None: return checked, None
            sample[s] = v
        if rel is not None and A.rel_holds(rel, sample) is not True:
            continue
        try:
            a, b = numeric(expr.subs(sample)), numeric(refined.subs(sample))
        except Exception:
            continue
        if a in FAILED and b in FAILED:
            continue
        if not agree(a, b):
            return checked, (sample, a, b)
        checked += 1
        if checked >= samples: break
    return checked, None


def compare(left, right, points):
    """(n_checked, counterexample or None) comparing two expressions at ``points``."""
    checked = 0
    for pt in points:
        try:
            a, b = numeric(left.subs(pt)), numeric(right.subs(pt))
        except Exception:  # noqa: BLE001, S112 -- a point SymPy cannot substitute is skipped
            continue
        if a in FAILED and b in FAILED:
            continue
        if not agree(a, b):
            return checked, (pt, a, b)
        checked += 1
    return checked, None


def fmt(v):
    """A value of :func:`numeric`, :func:`ext_value` or ``matrices.mat_value`` as text."""
    if isinstance(v, tuple) and v[0] == "inf":  # a directed infinity from ext_value
        return f"oo*({v[1].real:.6g}{v[1].imag:+.6g}j)"
    if isinstance(v, tuple):            # a matrix value from mat_value
        return f"{v[1][0]}x{v[1][1]} matrix [" + ", ".join(fmt(x) for x in v[2]) + "]"
    return v if isinstance(v, str) else f"{v.real:.12g}{v.imag:+.12g}j"


# --- extended family

def _inf_class(v):
    """("inf", unit direction) for a signed or directed infinity, "zoo", or "unevaluated"."""
    if v is zoo:
        return "zoo"
    if v.has(zoo):
        return "unevaluated"
    terms = [t for t in Add.make_args(v) if t.has(oo, -oo)]
    if len(terms) != 1 or any(not t.is_number for t in Add.make_args(v)):
        return "unevaluated"
    t = terms[0]
    if t in (oo, -oo):
        d = S.One if t == oo else S.NegativeOne
    elif isinstance(t, Mul):
        infs = [f for f in t.args if f in (oo, -oo)]
        rest = [f for f in t.args if f not in (oo, -oo)]
        if len(infs) != 1 or any(f.has(oo, -oo, zoo) for f in rest):
            return "unevaluated"
        d = Mul(*rest) * (1 if infs[0] == oo else -1)
    else:
        return "unevaluated"
    try:
        dc = complex(N(d, 20))
    except (TypeError, ValueError):
        return "unevaluated"
    if dc == 0:
        return "unevaluated"
    return ("inf", dc / abs(dc))


class _NoBranch(Exception):
    pass


def _pw_resolve(e, pt):
    """``e`` with every Piecewise replaced by its branch at ``pt``.

    Substituting into a Piecewise rebuilds it through SymPy's argument
    collapse, which can recurse without end (``Ne(2, z**2)`` with a complex
    Float ``z``); here each condition is decided on its own instead.  Raises
    ``_NoBranch`` if no condition holds (the Piecewise has no value).
    """
    if not isinstance(e, Basic) or not e.has(Piecewise):
        return e
    if isinstance(e, Piecewise):
        for expr_, cond in e.args:
            c = S.true if cond is S.true else _pw_resolve(cond, pt).xreplace(pt)
            if c is S.true:
                return _pw_resolve(expr_, pt)
            if c is not S.false:
                raise TypeError("undecided Piecewise condition")
        raise _NoBranch
    return e.func(*[_pw_resolve(a, pt) for a in e.args])


def ext_value(e, pt):
    """The value of ``e`` at ``pt`` (see the module docstring)."""
    try:
        v = _pw_resolve(e, pt).xreplace(pt)
    except _NoBranch:
        return "nan"
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001 -- e.g. a Piecewise condition on a non-real value
        return "error"
    if not isinstance(v, Expr):
        return "unevaluated"
    if v.has(KroneckerDelta):          # SymPy leaves KroneckerDelta(oo, oo) unevaluated; decide it by Eq
        v = v.replace(KroneckerDelta, lambda p, q: {S.true: S.One, S.false: S.Zero}.get(Eq(p, q), KroneckerDelta(p, q)))
    if v.has(nan) or v.has(AccumBounds):
        return "nan"
    if A.is_inf(v):
        return _inf_class(v)
    try:
        w = N(v, 20)
    except NO_SWALLOW:
        raise
    except Exception:  # noqa: BLE001
        return "error"
    return numeric(w)


def ext_agree(a, b):
    if isinstance(a, tuple) or isinstance(b, tuple):
        return isinstance(a, tuple) and isinstance(b, tuple) and abs(a[1] - b[1]) < 1e-9
    if a == "zoo" or b == "zoo":
        return a == b
    return agree(a, b)


def _zero_division(sides, pt):
    """The label of an exact 1/0 or log(0) met while evaluating ``sides`` at ``pt``, or None."""
    for e in sides:
        for sub in e.atoms(log, Pow):
            try:
                if isinstance(sub, log):
                    if sub.args[0].xreplace(pt) == 0:
                        return "log(0) = zoo"
                elif sub.base.xreplace(pt) == 0:
                    ev = ext_value(sub.exp, pt)
                    if isinstance(ev, complex) and ev.real < 0:
                        return "1/0 = zoo"
            except NO_SWALLOW:
                raise
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def ext_convention(sides, pt, a, b):
    """The SymPy convention that explains the mismatch ``a != b`` at ``pt``, or None.

    zoo against a signed infinity is excused only when an exact 1/0 or log(0)
    produced it; zoo from a function's own pole (``acsch(0)``) is reported.
    """
    if (a == "zoo" and isinstance(b, tuple)) or (b == "zoo" and isinstance(a, tuple)):
        lab = _zero_division(sides, pt)
        return f"zoo vs signed infinity ({lab})" if lab else None
    for e in sides:
        for sub in e.atoms(log, atan2, Pow):
            try:
                if isinstance(sub, log):
                    u = ext_value(sub.args[0], pt)
                    if isinstance(u, tuple) and abs(u[1] - 1) > 1e-9:
                        return "log of a non-positive infinity"
                elif isinstance(sub, atan2):
                    if all(A.is_inf(t.xreplace(pt)) for t in sub.args):
                        return "atan2 of two infinities"
            except NO_SWALLOW:
                raise
            except Exception:  # noqa: BLE001, S112
                continue
    return None


def ext_compare(left, right, points, ref=None):
    """(n_checked, counterexample or None, stats) for ``left`` (the input) against ``right``.

    The counterexample is (point, left value, right value, kind), kind one of
    "finite point", "infinite point", "undefined output".  ``stats`` counts the
    points skipped (input undefined, unevaluable), excused per convention label
    and checked at an infinity.  With ``ref`` (the input, when two rewrites are
    compared) a point where ``ref`` has no value is skipped.
    """
    stats = Counter()
    checked = 0
    for pt in points:
        inf_pt = any(A.is_inf(v) for v in pt.values())
        if ref is not None and ext_value(ref, pt) in ("nan", "error", "unevaluated"):
            stats["input undefined"] += 1
            continue
        a, b = ext_value(left, pt), ext_value(right, pt)
        if a == "nan":
            stats["input undefined"] += 1
            continue
        if a in ("error", "unevaluated") or b in ("error", "unevaluated"):
            stats["unevaluable"] += 1
            continue
        if b != "nan" and ext_agree(a, b):
            checked += 1
            if inf_pt:
                stats["checked at an infinity"] += 1
            continue
        conv = ext_convention((left, right), pt, a, b)
        if conv:
            stats["convention: " + conv] += 1
            continue
        kind = "undefined output" if b == "nan" else "infinite point" if inf_pt else "finite point"
        return checked, (pt, a, b, kind), stats
    return checked, None, stats
