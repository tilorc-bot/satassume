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
    ``h(y)`` for a head ``h`` with range rows (:data:`RANGES`: ``arg``,
    ``atan``, ``acot``, ``asin``, ``acos``, stated by their families), or
    any expression whose bounds
    the assumptions state as conjuncts (:func:`..core.bounds.stated_bounds`: ``Q.ge(u,
    -pi/2)``, ``Q.lt(1, u)``, ``Q.positive(u + pi)``, ... read affinely,
    and the sign facts ``Q.positive(u)``, ``Q.nonnegative(u)``, ... by
    asking).  A row states a fixed condition; this is interval arithmetic
    over whatever bounds are stated (the constant depends on them), which
    no finite set of rows expresses.  :func:`floor_two_valued` is the case
    where the floor is constant except at one closed endpoint of the
    interval (the engine's endpoint split).
``Piecewise``
    conditions are decided by the engine (:func:`..core.prove.decide`), a
    branch decided false is dropped, one decided true ends the list, and
    the other branches are refined under the assumptions plus their own
    condition.  A row cannot add a branch's condition to the assumptions
    the right side is refined under.
"""
from __future__ import annotations

from typing import Any

from typing import Iterator

from sympy import Abs, And, Piecewise, S, arg, ceiling, floor, im
from sympy.core import Basic

from ... import _upstream
from ..core.bounds import _affine, _stated_sides, full_bounds

RANGES: dict = {}
"""``head -> [(head(y), interval, condition), ...]``: the range rows of bounded heads,
stated by the family that owns the head (``complex_parts`` for ``arg``, ``inverse``
for ``atan``, ``acot``, ``asin``, ``acos``) and registered with :func:`register_ranges`.
The first row whose condition is provable gives the range of ``head(y)``."""


def register_ranges(rows: list) -> None:
    """Add range rows ``(head(y), interval, condition)`` (``y`` a symbol) to :data:`RANGES`."""
    for row in rows:
        RANGES.setdefault(row[0].func, []).append(row)


def _range(node: Any, assumptions: Any) -> tuple | None:
    """``(lo, hi, lo_open, hi_open)``: the range of a bounded head applied to its argument, or ``None``."""
    from ..core.prove import provable
    for lhs, interval, cond in RANGES.get(node.func, ()):
        if provable(cond.xreplace({lhs.args[0]: node.args[0]}), assumptions) is True:
            return interval.start, interval.end, interval.left_open, interval.right_open
    return None


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


def _images(inner: Any, assumptions: Any) -> Iterator[tuple]:
    """``(a, c, range, u)`` for every bounded quantity ``u`` that ``inner`` is affine in."""
    for node in (inner.atoms(*RANGES) if RANGES else ()):
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
    :data:`RANGES`, or an expression with stated bounds)."""
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
    by the engine (:func:`..core.prove.decide`: relations from signs and stated
    relations, never from a relation ``ask`` about a known infinite argument).
    A condition decided false drops its branch, one decided true ends the list.
    The dispatcher leaves the arguments to this handler (:data:`..core.hooks.own_args`):
    SymPy refines a condition with a bare ``ask`` (weak on relations, raising on
    sign facts, wrong at ``-oo``)."""
    from ..core.driver import refine
    from ..core.prove import decide
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
    fallbacks (:data:`..core.hooks.fallback`), so a family module that registers
    one of the keys later still gets them after its own table declines; and set
    the head roles of :mod:`..core.hooks` the engine reads."""
    from ..core import hooks
    hooks.own_args.add("Piecewise")
    for key, handler in SIMPLE_RULES.items():
        handlers_dict[key] = handler
    hooks.fallback.update(FALLBACK_RULES)
    hooks.opaque = (floor, im, arg)
    hooks.conditional = Piecewise
    hooks.modulus = Abs
    hooks.step = floor
    hooks.two_valued = floor_two_valued
