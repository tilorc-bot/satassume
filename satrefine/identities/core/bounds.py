"""Bounds the assumptions state on a quantity: intervals from relations and sign facts.

A conjunct ``Q.ge(l, r)``, ``Q.gt``, ``Q.le``, ``Q.lt`` or a sign fact is a bound
on ``u`` when its difference is affine in ``u`` with numeric coefficients
(:func:`stated_bounds`); :func:`stated_finite` also says whether the same
conjuncts prove ``u`` finite, :func:`full_bounds` completes an unstated side by
asking the sign facts.  An empty interval (contradictory facts) proves
nothing (:func:`_checked`).  The prover (:func:`.prove._from_bounds`) and the
``floor`` handler (:mod:`..rules._simple`) read them.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from sympy import And, Dummy, Q, S, expand_mul
from sympy.assumptions import AppliedPredicate
from sympy.core import Basic

from ... import _upstream


_RELATIONS = (Q.ge, Q.gt, Q.le, Q.lt)
_SIGNS = (Q.positive, Q.nonnegative, Q.negative, Q.nonpositive)


@lru_cache(maxsize=4096)
def _affine(d: Any, u: Any) -> tuple | None:
    """``(a, c)`` with ``d == a*u + c`` for real numbers ``a != 0`` and ``c``, else ``None``."""
    t = Dummy("t")
    try:
        e = d.xreplace({u: t})
    except (TypeError, ValueError):     # u is a matrix inside a MatrixElement: no scalar stands for it
        return None
    if not e.has(t):
        return None
    e = expand_mul(e)
    a = e.coeff(t)
    c = (e - a*t).expand()
    if a == 0 or c.has(t) or not (a.is_number and c.is_number and a.is_extended_real and c.is_extended_real):
        return None
    return a, c


def _tighter(current: tuple | None, bound: Any, strict: bool, lower: bool) -> tuple:
    if current is None:
        return bound, strict
    diff = bound - current[0]
    if (diff.is_positive if lower else diff.is_negative) or (diff.is_zero and strict):
        return bound, strict
    return current


def _empty(lo: Any, hi: Any, lo_open: bool, hi_open: bool) -> bool:
    """Whether the interval is provably empty (``lo > hi``, or ``lo == hi`` with an open side)."""
    if lo is None or hi is None:
        return False
    gap = lo - hi
    return bool(gap.is_positive or (gap.is_zero and (lo_open or hi_open)))


def _checked(bounds: tuple | None) -> tuple | None:
    """``bounds``, or ``None`` when they are provably empty.

    An empty interval means the stated facts contradict each other
    (``Q.negative(k) & Q.gt(k, pi/2)``); every predicate would follow from it,
    ``Q.positive(k)`` and ``Q.negative(k)`` alike, and rows conditioned on
    opposite signs would undo each other forever (issue #10, B9).  Under
    inconsistent assumptions any result is correct, so the bounds prove
    nothing and the engine is left with what ``ask`` answers."""
    return None if bounds is None or _empty(*bounds[:4]) else bounds


def stated_bounds(u: Any, assumptions: Any) -> tuple | None:
    """``(lo, hi, lo_open, hi_open)`` for ``u`` from the conjuncts of ``assumptions``.

    A conjunct ``Q.ge(l, r)``, ``Q.gt``, ``Q.le``, ``Q.lt`` or a sign fact
    ``Q.positive(d)``, ``Q.nonnegative(d)``, ``Q.negative(d)``,
    ``Q.nonpositive(d)`` whose difference ``d`` is affine in ``u`` with
    numeric coefficients is a bound on ``u``; the tightest of each side is
    kept and an unstated side is ``None``.  When nothing bounds ``u``
    itself but ``u`` is affine in a bounded quantity ``v`` (``x - 2*pi``
    under ``Q.le(x, 2*pi)``), the bounds of ``v`` are mapped.  ``None``
    when nothing is stated, or when the stated bounds are contradictory
    (an empty interval, :func:`_checked`).

    The interval is one of the *extended* reals: a relation allows an
    infinite value (``Q.gt(x, 1)`` holds at ``x = oo``), so an unstated or
    infinite side does not bound ``u`` away from infinity; see
    :func:`stated_finite` for when the bounds prove ``u`` finite.
    """
    found = _stated(u, assumptions)
    return None if found is None else found[:4]


def stated_finite(u: Any, assumptions: Any) -> tuple | None:
    """``(bounds, finite)``: :func:`stated_bounds` and whether the same conjuncts
    prove ``u`` finite, without looking at the interval's endpoints.

    A sign fact ``Q.positive(d)`` (and the other three) holds only for a
    finite ``d``, so a bound read from one makes ``u`` finite; a relation
    (``Q.gt(u, 1)``, and ``Q.ge(u, oo)``, which forces ``u = oo``) does not.
    Whether an endpoint excludes infinity is left to the caller
    (:func:`._engine._from_bounds`)."""
    found = _stated(u, assumptions)
    return None if found is None else (found[:4], found[4])


def _stated(u: Any, assumptions: Any) -> tuple | None:
    """``(lo, hi, lo_open, hi_open, finite)``: see :func:`stated_bounds` and :func:`stated_finite`.

    The bounds stated on ``u`` itself come first; while they leave a side
    open (and no sign fact makes ``u`` finite), the bounds of each quantity
    ``v`` that ``u`` is affine in are mapped and the tightest side kept
    (``t - 2*pi`` under ``Q.le(t, 2*pi) & Q.ge(t, pi)``: the upper side is
    stated on ``t - 2*pi``, the lower one on ``t``)."""
    if not isinstance(assumptions, Basic):
        return None
    found = _checked(_direct_bounds(u, assumptions))
    if u.is_Symbol or found is not None and (found[4] or (found[0] is not None and found[1] is not None)):
        return found
    for v in _stated_sides(assumptions) + sorted(u.free_symbols, key=str):
        if v == u or not u.has(v):
            continue
        aff = _affine(u, v)
        rng = _checked(_direct_bounds(v, assumptions)) if aff else None
        if rng is None:
            continue
        a, c = aff
        lo, hi, lo_open, hi_open, finite = rng
        lo, hi = (None if lo is None else a*lo + c), (None if hi is None else a*hi + c)
        if a < 0:
            lo, hi, lo_open, hi_open = hi, lo, hi_open, lo_open
        mapped = (lo, hi, lo_open, hi_open, bool(finite and a.is_finite and c.is_finite))
        found = mapped if found is None else _merged(found, mapped)
        if found is None or found[4] or (found[0] is not None and found[1] is not None):
            return found
    return found


def _merged(one: tuple, other: tuple) -> tuple | None:
    """The intersection of two ``(lo, hi, lo_open, hi_open, finite)`` intervals of one quantity."""
    sides = []
    for i, lower in ((0, True), (1, False)):
        side = None
        for b in (one, other):
            if b[i] is not None:
                side = _tighter(side, b[i], b[i + 2], lower)
        sides.append(side)
    lo, hi = sides
    return _checked((lo[0] if lo else None, hi[0] if hi else None, bool(lo and lo[1]), bool(hi and hi[1]),
                     one[4] or other[4]))


def _direct_bounds(u: Any, assumptions: Any) -> tuple | None:
    """The bounds stated on ``u`` itself, and whether a sign fact among them makes
    ``u`` finite (see :func:`_stated`)."""
    lo = hi = None
    finite = False
    for conj in And.make_args(assumptions):
        if not isinstance(conj, AppliedPredicate):
            continue
        f = conj.function
        if f in _RELATIONS:
            l, r = conj.arguments
            d, lower, strict = l - r, f in (Q.ge, Q.gt), f in (Q.gt, Q.lt)
        elif f in _SIGNS:
            d, lower, strict = conj.arguments[0], f in (Q.positive, Q.nonnegative), f in (Q.positive, Q.negative)
        else:
            continue
        aff = _affine(d, u)
        if aff is None:
            continue
        a, c = aff
        bound = -c/a
        finite |= f in _SIGNS and bool(a.is_finite and c.is_finite)   # a sign fact's argument is finite
        if (a > 0) == lower:
            lo = _tighter(lo, bound, strict, True)
        else:
            hi = _tighter(hi, bound, strict, False)
    if lo is None and hi is None:
        return None
    return (lo[0] if lo else None, hi[0] if hi else None, bool(lo and lo[1]), bool(hi and hi[1]), finite)


def full_bounds(u: Any, assumptions: Any) -> tuple | None:
    """:func:`stated_bounds` completed by asking the sign facts for an unstated side
    (``None`` when that makes the interval empty, as in :func:`_checked`)."""
    lo, hi, lo_open, hi_open = stated_bounds(u, assumptions) or (None, None, False, False)
    ask = _upstream.ask
    if lo is None:
        if ask(Q.positive(u), assumptions):
            lo, lo_open = S.Zero, True
        elif ask(Q.nonnegative(u), assumptions):
            lo, lo_open = S.Zero, False
    if hi is None:
        if ask(Q.negative(u), assumptions):
            hi, hi_open = S.Zero, True
        elif ask(Q.nonpositive(u), assumptions):
            hi, hi_open = S.Zero, False
    if lo is None or hi is None:
        return None
    return _checked((lo, hi, lo_open, hi_open))


def _stated_sides(assumptions: Any) -> list:
    """The non-numeric sides of the stated relations and sign facts, and each side without its constant term."""
    out: list = []
    if not isinstance(assumptions, Basic):
        return out
    for conj in And.make_args(assumptions):
        if not isinstance(conj, AppliedPredicate) or conj.function not in _RELATIONS + _SIGNS:
            continue
        for side in conj.arguments:
            if side.is_number:
                continue
            out.append(side)
            _c, rest = side.as_coeff_Add()
            if rest is not side:
                out.append(rest)
    return out
