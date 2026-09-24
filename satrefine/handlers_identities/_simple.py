"""The procedural remainder of the base layer: ``floor`` of a bounded quantity, ``Piecewise``.

Registered by the package ``__init__`` on ``floor``, ``ceiling`` and
``Piecewise`` before the family modules load, and as the dispatcher's
fallbacks for those keys: a family module that registers one of them
(``integer_funcs`` registers ``floor`` and ``ceiling``) overrides the
handler, and the dispatcher tries the simple rule after the family's
table declines.  Each rule chains to the vendored handler when it does
not apply.  Everything else the branch bookkeeping reduces through
(``re``/``im`` of exponentials, logarithms, sums and products; ``arg``
and ``Abs`` under sign facts) is a row of :mod:`.complex_parts`.

Why these two are procedures and not rows:

``floor``/``ceiling`` of a bounded quantity
    ``floor(a*u + c)`` with numeric ``a``, ``c`` is a constant when the
    floor is constant over the interval ``u`` is known to lie in: ``u`` is
    ``h(y)`` for a head ``h`` in :data:`BOUNDS` (``arg``, ``atan``,
    ``acot``, ``asin``, ``acos``; ``arg`` is open at ``pi`` when ``y`` is
    provably off the negative real axis), or any expression whose bounds
    the assumptions state as conjuncts (:func:`stated_bounds`: ``Q.ge(u,
    -pi/2)``, ``Q.lt(1, u)``, ``Q.positive(u + pi)``, ... read affinely,
    and the sign facts ``Q.positive(u)``, ``Q.nonnegative(u)``, ... by
    asking).  A row states a fixed condition; this is interval arithmetic
    over whatever bounds are stated (the constant depends on them), which
    no finite set of rows expresses.  :func:`floor_two_valued` is the case
    where the floor is constant except at one closed endpoint of the
    interval (the engine's endpoint split).
``Piecewise``
    conditions are decided by the engine (:func:`._engine.decide`), a
    branch decided false is dropped, one decided true ends the list, and
    the other branches are refined under the assumptions plus their own
    condition.  A row cannot add a branch's condition to the assumptions
    the right side is refined under.
"""
from __future__ import annotations

from typing import Any

from functools import lru_cache
from typing import Iterator

from sympy import And, Dummy, Piecewise, Q, S, acos, acot, arg, asin, atan, ceiling, expand_mul, floor, im, pi, re
from sympy.assumptions import AppliedPredicate
from sympy.core import Basic

from .. import _upstream

# head -> (lo, hi, lo_open, hi_open) of its range on real (nonzero for arg) arguments
BOUNDS: dict = {
    arg:  (-pi, pi, True, False),
    atan: (-pi/2, pi/2, True, True),
    acot: (-pi/2, pi/2, True, False),
    asin: (-pi/2, pi/2, False, False),
    acos: (S.Zero, pi, False, False),
}


def _range(node: Any, assumptions: Any) -> tuple | None:
    """The range of a bounded head applied to its argument, or ``None``."""
    head = node.func
    if head not in BOUNDS:
        return None
    lo, hi, lo_open, hi_open = BOUNDS[head]
    y = node.args[0]
    if head is arg:
        ask = _upstream.ask
        if (ask(Q.extended_negative(y), assumptions) is False       # arg(-oo) is pi too
                or ask(Q.nonnegative(re(y)), assumptions) or ask(~Q.zero(im(y)), assumptions) is True):
            hi_open = True                       # off the negative real axis
    elif head in (asin, acos):
        if _upstream.ask(Q.real(node), assumptions) is not True:
            return None
    elif _upstream.ask(Q.real(y), assumptions) is not True:
        return None
    return lo, hi, lo_open, hi_open


def _constant_over(fn: Any, a: Any, c: Any, rng: tuple) -> Any | None:
    """``fn`` (floor or ceiling) of ``a*t + c`` when it is constant for ``t`` in ``rng``."""
    lo, hi, lo_open, hi_open = rng
    L, U = a*lo + c, a*hi + c
    if a < 0:
        L, U, lo_open, hi_open = U, L, hi_open, lo_open
    if fn is floor:
        at_low = floor(L)
        at_high = U - 1 if (hi_open and U.is_integer) else floor(U)
    else:
        at_low = L + 1 if (lo_open and L.is_integer) else ceiling(L)
        at_high = ceiling(U)
    if at_low.is_number and at_high.is_number and at_low == at_high:
        return at_low
    return None


_RELATIONS = (Q.ge, Q.gt, Q.le, Q.lt)
_SIGNS = (Q.positive, Q.nonnegative, Q.negative, Q.nonpositive)


@lru_cache(maxsize=4096)
def _affine(d: Any, u: Any) -> tuple | None:
    """``(a, c)`` with ``d == a*u + c`` for real numbers ``a != 0`` and ``c``, else ``None``."""
    t = Dummy("t")
    e = d.xreplace({u: t})
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


def stated_bounds(u: Any, assumptions: Any) -> tuple | None:
    """``(lo, hi, lo_open, hi_open)`` for ``u`` from the conjuncts of ``assumptions``.

    A conjunct ``Q.ge(l, r)``, ``Q.gt``, ``Q.le``, ``Q.lt`` or a sign fact
    ``Q.positive(d)``, ``Q.nonnegative(d)``, ``Q.negative(d)``,
    ``Q.nonpositive(d)`` whose difference ``d`` is affine in ``u`` with
    numeric coefficients is a bound on ``u``; the tightest of each side is
    kept and an unstated side is ``None``.  When nothing bounds ``u``
    itself but ``u`` is affine in a bounded quantity ``v`` (``x - 2*pi``
    under ``Q.le(x, 2*pi)``), the bounds of ``v`` are mapped.  ``None``
    when nothing is stated.
    """
    if not isinstance(assumptions, Basic):
        return None
    direct = _direct_bounds(u, assumptions)
    if direct is not None or u.is_Symbol:
        return direct
    for v in _stated_sides(assumptions) + sorted(u.free_symbols, key=str):
        if v == u or not u.has(v):
            continue
        aff = _affine(u, v)
        rng = _direct_bounds(v, assumptions) if aff else None
        if rng is None:
            continue
        a, c = aff
        lo, hi, lo_open, hi_open = rng
        lo, hi = (None if lo is None else a*lo + c), (None if hi is None else a*hi + c)
        if a < 0:
            lo, hi, lo_open, hi_open = hi, lo, hi_open, lo_open
        return lo, hi, lo_open, hi_open
    return None


def _direct_bounds(u: Any, assumptions: Any) -> tuple | None:
    """The bounds stated on ``u`` itself (see :func:`stated_bounds`)."""
    lo = hi = None
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
        if (a > 0) == lower:
            lo = _tighter(lo, bound, strict, True)
        else:
            hi = _tighter(hi, bound, strict, False)
    if lo is None and hi is None:
        return None
    return (lo[0] if lo else None, hi[0] if hi else None, bool(lo and lo[1]), bool(hi and hi[1]))


def full_bounds(u: Any, assumptions: Any) -> tuple | None:
    """:func:`stated_bounds` completed by asking the sign facts for an unstated side."""
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
    return lo, hi, lo_open, hi_open


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


def _images(inner: Any, assumptions: Any) -> Iterator[tuple]:
    """``(a, c, range, u)`` for every bounded quantity ``u`` that ``inner`` is affine in."""
    for node in inner.atoms(*BOUNDS):
        aff = _affine(inner, node)
        rng = _range(node, assumptions) if aff else None
        if rng is not None:
            yield aff[0], aff[1], rng, node
    seen: set = set()
    for u in _stated_sides(assumptions) + sorted(inner.free_symbols, key=str):
        if u in seen or not inner.has(u):
            continue
        seen.add(u)
        aff = _affine(inner, u)
        rng = full_bounds(u, assumptions) if aff else None
        if rng is not None:
            yield aff[0], aff[1], rng, u


def floor_of_bounded(expr: Basic, assumptions: Any) -> Basic | None:
    """``floor``/``ceiling`` of ``a*u + c`` for a bounded quantity ``u`` (a head of
    :data:`BOUNDS`, or an expression with stated bounds)."""
    fn, inner = expr.func, expr.args[0]
    for a, c, rng, _u in _images(inner, assumptions):
        value = _constant_over(fn, a, c, rng)
        if value is not None:
            return value
    return None


def floor_two_valued(expr: Basic, assumptions: Any) -> tuple | None:
    """``(value, u, endpoint, alternative)`` when ``floor(a*u + c)`` is ``value``
    on the interval of ``u`` except at its closed endpoint ``u = endpoint``,
    where the argument is an integer and the floor is ``alternative``
    (``value + 1``); ``None`` otherwise.  Only ``floor`` (the wraps use it)."""
    fn, inner = expr.func, expr.args[0]
    if fn is not floor:
        return None
    for a, c, rng, u in _images(inner, assumptions):
        lo, hi, lo_open, hi_open = rng
        L, U, end = a*lo + c, a*hi + c, hi
        if a < 0:
            L, U, lo_open, hi_open, end = U, L, hi_open, lo_open, lo
        if not hi_open and U.is_integer and floor(L) == U - 1:
            return U - 1, u, end, U
    return None


def refine_floor(expr: Basic, assumptions: Any) -> Basic | None:
    value = floor_of_bounded(expr, assumptions)
    if value is not None:
        return value
    return _upstream.refine_floor_ceiling(expr, assumptions)


def simple_floor(expr: Basic, assumptions: Any) -> Basic | None:
    """The bounds rule alone (the fallback behind a family's floor/ceiling table)."""
    return floor_of_bounded(expr, assumptions)


def refine_piecewise(expr: Basic, assumptions: Any) -> Basic | None:
    """Each branch under the assumptions plus its condition, the conditions decided
    by the engine (:func:`._engine.decide`: relations from signs and stated
    relations, never from a relation ``ask`` about a known infinite argument).
    A condition decided false drops its branch, one decided true ends the list.
    The dispatcher leaves the arguments to this handler (:data:`._dispatch.own_args`):
    SymPy refines a condition with a bare ``ask`` (weak on relations, raising on
    sign facts, wrong at ``-oo``)."""
    from ._dispatch import refine
    from ._engine import decide
    pairs = []
    for value, cond in expr.args:
        decided = decide(cond, assumptions)
        if decided is False:
            continue
        try:
            pairs.append((refine(value, assumptions if decided else And(assumptions, cond)),
                          S.true if decided else cond))
        except ValueError:                       # the branch condition contradicts the assumptions
            continue
        if decided:
            break
    if not pairs:
        return None
    return Piecewise(*pairs)


SIMPLE_RULES = {"floor": refine_floor, "ceiling": refine_floor, "Piecewise": refine_piecewise}
"""Handlers for keys no family module registers: the simple rule, then the vendored handler."""

FALLBACK_RULES = {"floor": simple_floor, "ceiling": simple_floor, "Piecewise": refine_piecewise}
"""The simple rules alone: tried by the dispatcher after a family's own table
declines, never the vendored handler (a family's refusals must stand)."""


def install(handlers_dict: dict) -> None:
    """Register the simple rules as the keys' handlers and as the dispatcher's
    fallbacks, so a family module that registers one of the keys later still
    gets them after its own table declines."""
    from ._dispatch import fallback_handlers, own_args
    own_args.add("Piecewise")
    for key, handler in SIMPLE_RULES.items():
        handlers_dict[key] = handler
    fallback_handlers.update(FALLBACK_RULES)
