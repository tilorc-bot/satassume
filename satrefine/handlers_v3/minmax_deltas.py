"""Refine handlers for ``Min``, ``Max``, ``DiracDelta``, ``KroneckerDelta``
and ``Heaviside``.

Every predicate question goes through ``_upstream.ask``.  Relation queries
(``Q.le``, ``Q.lt``, ``Q.eq``, ``Q.ne``) are answered by SymPy's ``ask`` only,
which may raise ``ValueError("inconsistent assumptions")``; such an error is
read as "unknown" (see :func:`_ask_relation`).

Rules
=====

``Min(a1, ..., an)`` / ``Max(a1, ..., an)``
    An argument is dropped when another argument is known to dominate it
    (for ``Max``: ``a <= b`` drops ``a``; for ``Min``: ``b <= a`` drops
    ``a``); if one argument dominates all others the result is that
    argument.  ``a <= b`` is known when

    1. ``a`` is extended_nonpositive and ``b`` is extended_nonnegative
       (covers negative vs nonnegative, nonpositive vs positive, zero vs a
       signed argument, and -oo/+oo against signed arguments);
    2. ``b`` is +oo (infinite and extended_nonnegative) and ``a`` is
       extended_real;
    3. ``a`` is -oo (infinite and extended_nonpositive) and ``b`` is
       extended_real;
    4. neither argument is known infinite and
       ``Q.le(a, b) | Q.lt(a, b) | Q.eq(a, b)`` holds (one relation query
       per ordered pair; SymPy's ask derives neither ``le`` from ``lt`` nor
       from ``eq``, hence the disjunction; the ``Q.eq`` disjunct makes
       ``Min(x, y)`` under ``Q.eq(x, y)`` collapse to one argument, and is
       included only when the assumptions contain a ``Q.eq``/``Eq`` fact,
       see :func:`_mentions_eq`).  The
       query is skipped for infinite arguments because SymPy answers it
       unsoundly there (``Q.eq(y, x)`` is "True" for ``x = -oo`` and
       ``y`` extended_nonpositive).

    Unary facts are asked at most once per argument (lazily, and only the
    ones a rule needs); each ordered pair gets at most one relation query.
    When two arguments dominate each other (equal), only one is dropped.

``DiracDelta(x)`` / ``DiracDelta(x, k)``
    * ``x`` nonzero (``Q.nonzero``: real and not zero) -> ``0`` for every
      derivative order ``k`` (the distribution and its derivatives vanish
      away from the origin; SymPy's own ``eval`` does the same for
      ``x.is_nonzero``).  A shift ``DiracDelta(x - a)`` is covered by this
      rule only when ``x - a`` itself is known nonzero.
    * ``k == 0`` and ``x = c*r`` (as a ``Mul``) where ``c`` is the product of
      the factors known nonzero, ``c != 1`` and the rest ``r`` is known
      real -> ``DiracDelta(r)/Abs(c)``.  This is the convention of
      ``DiracDelta(x*y).expand(diracdelta=True, wrt=x) == DiracDelta(x)/Abs(y)``.
      Derivatives (``k > 0``) are left alone (they pick up ``sign(c)**k``).

``KroneckerDelta(i, j[, range])``
    * ``i - j`` known nonzero (e.g. a nonzero integer), or
      ``Q.ne(i, j) | Q.ne(j, i) | Q.lt(i, j) | Q.lt(j, i)`` -> ``0``.
    * ``i - j`` known zero, or ``Q.eq(i, j) | Q.eq(j, i)`` (asked only when
      the assumptions contain a ``Q.eq``/``Eq`` fact) -> ``1``; only without
      a ``range`` argument (with one, SymPy returns ``0`` for equal indices
      outside the range, which the assumptions do not rule out).
    The cheap unary queries on ``i - j`` go first; each spelling pair of a
    relation is asked as one disjunctive query.  The relation queries are
    skipped when an index is known infinite (SymPy answers ``Q.eq(x, y)``
    True for ``x = -oo`` and ``y`` extended_nonpositive).

``Heaviside(x, H0)``
    * ``x`` extended_positive (includes +oo) -> ``1``;
    * ``x`` extended_negative (includes -oo) -> ``0``;
    * ``x`` zero -> ``H0`` (SymPy's convention; ``Heaviside(0) == 1/2``).
    This is the vendored ``_upstream.refine_Heaviside`` extended to the
    infinite endpoints, matching ``Heaviside.eval``, and returning ``None``
    instead of ``expr`` when nothing applies.
"""
from __future__ import annotations

from typing import Any

from sympy import Abs, Mul, S
from sympy.assumptions import Q
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.basic import Basic
from sympy.core.traversal import preorder_traversal
from sympy.core.relational import Equality
from sympy.functions import DiracDelta, KroneckerDelta

from .. import _upstream
from .._upstream import handlers_dict


def _mentions_eq(assumptions: Any) -> bool:
    """Whether ``assumptions`` contains a ``Q.eq`` fact (or an ``Eq``).

    SymPy's ask only derives ``Q.eq`` from such facts in practice, and a
    ``Q.eq`` query it cannot decide costs seconds (it is by far the slowest
    relation query), so it is asked only when this returns True.  Skipping
    it never changes a result's correctness, only its completeness.
    """
    if not isinstance(assumptions, Basic):
        return False
    return any(
        isinstance(node, Equality)
        or (isinstance(node, AppliedPredicate) and node.function == Q.eq)
        for node in preorder_traversal(assumptions))


def _ask_relation(proposition: Any, assumptions: Any) -> bool | None:
    """``_upstream.ask`` for relational queries, with SymPy's
    ``ValueError("inconsistent assumptions")`` read as ``None``."""
    try:
        return _upstream.ask(proposition, assumptions)
    except ValueError:
        return None


class _Facts:
    """Lazily asked, cached unary facts about one argument."""

    __slots__ = ("arg", "assumptions", "_cache")

    def __init__(self, arg: Basic, assumptions: Any):
        self.arg = arg
        self.assumptions = assumptions
        self._cache: dict[str, bool | None] = {}

    def _get(self, name: str) -> bool | None:
        if name not in self._cache:
            self._cache[name] = _upstream.ask(getattr(Q, name)(self.arg), self.assumptions)
        return self._cache[name]

    def nonpos(self) -> bool | None:
        return self._get("extended_nonpositive")

    def nonneg(self) -> bool | None:
        return self._get("extended_nonnegative")

    def ext_real(self) -> bool | None:
        return self._get("extended_real")

    def infinite(self) -> bool:
        return bool(self._get("infinite"))

    def pos_inf(self) -> bool:
        return self.infinite() and bool(self.nonneg())

    def neg_inf(self) -> bool:
        return self.infinite() and bool(self.nonpos())


def _make_le(assumptions: Any):
    """Return a cached ``le(fa, fb)``: True when ``fa.arg <= fb.arg`` is known."""
    cache: dict[tuple[Basic, Basic], bool] = {}
    check_eq = _mentions_eq(assumptions)

    def le(fa: _Facts, fb: _Facts) -> bool:
        key = (fa.arg, fb.arg)
        if key in cache:
            return cache[key]
        a, b = fa.arg, fb.arg
        if fa.nonpos() and fb.nonneg():
            result = True
        elif fb.pos_inf() and fa.ext_real():
            result = True
        elif fa.neg_inf() and fb.ext_real():
            result = True
        elif fa.infinite() or fb.infinite():
            # SymPy's relation ask is unsound here: it answers
            # Q.eq(y, x) True for x = -oo and y extended_nonpositive.
            result = False
        else:
            proposition = Q.le(a, b) | Q.lt(a, b)
            if check_eq:
                proposition |= Q.eq(a, b)
            result = bool(_ask_relation(proposition, assumptions))
        cache[key] = result
        return result

    return le


def _refine_minmax(expr: Basic, assumptions: Any, keep_larger: bool) -> Basic | None:
    """Drop dominated arguments of ``Max`` (``keep_larger``) or ``Min``."""
    le = _make_le(assumptions)
    # dominated(x, by): x can be dropped because ``by`` is kept.
    if keep_larger:
        def dominated(x: _Facts, by: _Facts) -> bool:
            return le(x, by)
    else:
        def dominated(x: _Facts, by: _Facts) -> bool:
            return le(by, x)

    survivors: list[_Facts] = []
    for arg in expr.args:
        cand = _Facts(arg, assumptions)
        if any(dominated(cand, s) for s in survivors):
            continue
        survivors = [s for s in survivors if not dominated(s, cand)]
        survivors.append(cand)
    if len(survivors) == len(expr.args):
        return None
    return expr.func(*[s.arg for s in survivors])


def refine_Max(expr: Basic, assumptions: Any) -> Basic | None:
    """``Max`` without its arguments known to be dominated by another one.

    >>> from sympy import Q, Max
    >>> from sympy.abc import x, y
    >>> refine_Max(Max(x, y), Q.positive(x) & Q.negative(y))
    x
    """
    return _refine_minmax(expr, assumptions, keep_larger=True)


def refine_Min(expr: Basic, assumptions: Any) -> Basic | None:
    """``Min`` without its arguments known to dominate another one.

    >>> from sympy import Q, Min
    >>> from sympy.abc import x, y
    >>> refine_Min(Min(x, y), Q.positive(x) & Q.negative(y))
    y
    """
    return _refine_minmax(expr, assumptions, keep_larger=False)


def refine_DiracDelta(expr: Basic, assumptions: Any) -> Basic | None:
    """``0`` off the origin; scale out a nonzero real factor (order 0 only).

    >>> from sympy import Q, DiracDelta
    >>> from sympy.abc import x, k
    >>> refine_DiracDelta(DiracDelta(x), Q.positive(x))
    0
    >>> refine_DiracDelta(DiracDelta(k*x), Q.nonzero(k) & Q.real(x))
    DiracDelta(x)/Abs(k)
    """
    arg = expr.args[0]
    if _upstream.ask(Q.nonzero(arg), assumptions):
        return S.Zero
    if len(expr.args) > 1 and expr.args[1] != 0:
        return None
    if not isinstance(arg, Mul):
        return None
    scale, rest = [], []
    for factor in arg.args:
        (scale if _upstream.ask(Q.nonzero(factor), assumptions) else rest).append(factor)
    if not scale:
        return None
    r = Mul(*rest)
    if not _upstream.ask(Q.real(r), assumptions):
        return None
    return DiracDelta(r) / Abs(Mul(*scale))


def refine_KroneckerDelta(expr: Basic, assumptions: Any) -> Basic | None:
    """``1`` for indices known equal, ``0`` for indices known different.

    >>> from sympy import Q, KroneckerDelta
    >>> from sympy.abc import i, j
    >>> refine_KroneckerDelta(KroneckerDelta(i, j), Q.eq(i, j))
    1
    >>> refine_KroneckerDelta(KroneckerDelta(i, j), Q.ne(i, j))
    0
    """
    i, j = expr.args[0], expr.args[1]
    has_range = len(expr.args) > 2
    diff = i - j
    if _upstream.ask(Q.nonzero(diff), assumptions):
        return S.Zero
    if not has_range and _upstream.ask(Q.zero(diff), assumptions):
        return S.One
    # SymPy's relation ask is unsound for infinite indices: it answers
    # Q.eq(x, y) True for x = -oo and y extended_nonpositive.
    if (_upstream.ask(Q.infinite(i), assumptions)
            or _upstream.ask(Q.infinite(j), assumptions)):
        return None
    if (not has_range and _mentions_eq(assumptions)
            and _ask_relation(Q.eq(i, j) | Q.eq(j, i), assumptions)):
        return S.One
    if _ask_relation(Q.ne(i, j) | Q.ne(j, i) | Q.lt(i, j) | Q.lt(j, i), assumptions):
        return S.Zero
    return None


def refine_Heaviside(expr: Basic, assumptions: Any) -> Basic | None:
    """``1`` / ``0`` / ``H0`` for a positive / negative / zero argument.

    >>> from sympy import Q, Heaviside, oo
    >>> from sympy.abc import x
    >>> refine_Heaviside(Heaviside(x), Q.negative_infinite(x))
    0
    >>> refine_Heaviside(Heaviside(x), Q.zero(x))
    1/2
    """
    arg = expr.args[0]
    if _upstream.ask(Q.extended_positive(arg), assumptions):
        return S.One
    if _upstream.ask(Q.extended_negative(arg), assumptions):
        return S.Zero
    if _upstream.ask(Q.zero(arg), assumptions):
        return expr.args[1] if len(expr.args) > 1 else S.Half
    return None


handlers_dict['Min'] = refine_Min
handlers_dict['Max'] = refine_Max
handlers_dict['DiracDelta'] = refine_DiracDelta
handlers_dict['KroneckerDelta'] = refine_KroneckerDelta
handlers_dict['Heaviside'] = refine_Heaviside
