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

from sympy import And, Dummy, Piecewise, Q, S, acot, acoth, ceiling, expand_mul, floor
from sympy.assumptions import AppliedPredicate
from sympy.core import Basic

from ... import _upstream

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
    by the engine (:func:`._engine.decide`: relations from signs and stated
    relations, never from a relation ``ask`` about a known infinite argument).
    A condition decided false drops its branch, one decided true ends the list.
    The dispatcher leaves the arguments to this handler (:data:`._dispatch.own_args`):
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


_SIGN_AT_ZERO = (acot, acoth)   # heads whose eval pulls a sign out of an argument that may be zero


def rebuild(func: Any, args: Any, assumptions: Any) -> Basic:
    """``func(*args)``, the node rebuilt from refined children, except that
    ``acot`` and ``acoth`` of a non-numeric argument that may be zero stay
    unevaluated (issue #10, B8).

    SymPy's ``acot.eval`` and ``acoth.eval`` pull a sign out of the argument
    (``acot(-z) -> -acot(z)``, and ``acoth(I*c) -> -I*acot(c)``), which is
    wrong at ``z = 0``: ``acot(0) = pi/2``, ``acoth(0) = I*pi/2``.  A refined
    child often has that shape (``Abs(z) -> -z`` under ``Q.nonpositive(z)``), so
    ``acot(Abs(z))`` would become ``-acot(z)``.  When ``ask`` proves the
    argument nonzero the evaluated form is correct and is kept."""
    if func in _SIGN_AT_ZERO and len(args) == 1 and not args[0].is_number:
        new = func(*args)
        if new.func is not func or new.args != tuple(args):
            try:
                nonzero = _upstream.ask(Q.zero(args[0]), assumptions) is False
            except (ValueError, TypeError, AssertionError):
                nonzero = False
            if not nonzero:
                return func(*args, evaluate=False)
        return new
    return func(*args)


SIMPLE_RULES = {"floor": refine_floor, "ceiling": refine_floor, "Piecewise": refine_piecewise}
"""Handlers for keys no family module registers: the simple rule, then the vendored handler."""

FALLBACK_RULES = {"floor": simple_floor, "ceiling": simple_floor, "Piecewise": refine_piecewise}
"""The simple rules alone: tried by the dispatcher after a family's own table
declines, never the vendored handler (a family's refusals must stand)."""


def install(handlers_dict: dict) -> None:
    """Register the simple rules as the keys' handlers and as the dispatcher's
    fallbacks, so a family module that registers one of the keys later still
    gets them after its own table declines."""
    from ..core.driver import fallback_handlers, own_args
    own_args.add("Piecewise")
    for key, handler in SIMPLE_RULES.items():
        handlers_dict[key] = handler
    fallback_handlers.update(FALLBACK_RULES)
