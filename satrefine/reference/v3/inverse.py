"""Refine handlers for the inverse trigonometric and hyperbolic functions.

Registry keys: ``asin``, ``acos``, ``atan``, ``atan2``, ``asinh``, ``acosh``,
``atanh``, ``acoth``, ``asech``, ``acsch``.

Every rule here undoes a forward function on its principal branch, so each
one is guarded by the exact set of real inputs on which SymPy's principal
value of the inverse returns the argument (or its reflection):

============================  =====================================  ==========
expression                    condition on ``t``                     result
============================  =====================================  ==========
``asin(sin(t))``              ``-pi/2 <= t <= pi/2``                 ``t``
``asin(sin(t))``              ``pi/2 <= t <= 3*pi/2``                ``pi - t``
``asin(sin(t))``              ``-3*pi/2 <= t <= -pi/2``              ``-pi - t``
``asin(cos(t))``              ``0 <= t <= pi``                       ``pi/2 - t``
``acos(cos(t))``              ``0 <= t <= pi``                       ``t``
``acos(cos(t))``              ``-pi <= t <= 0``                      ``-t``
``acos(cos(t))``              ``pi <= t <= 2*pi``                    ``2*pi - t``
``acos(sin(t))``              ``-pi/2 <= t <= pi/2``                 ``pi/2 - t``
``atan(tan(t))``              ``-pi/2 < t < pi/2``                   ``t``
``atan(tan(t))``              ``pi/2 < t < 3*pi/2``                  ``t - pi``
``atan(tan(t))``              ``-3*pi/2 < t < -pi/2``                ``t + pi``
``atan(cot(t))``              ``0 < t < pi``                         ``pi/2 - t``
``asinh(sinh(t))``            ``t`` real                             ``t``
``atanh(tanh(t))``            ``t`` real                             ``t``
``acosh(cosh(t))``            ``t >= 0`` / ``t <= 0`` / ``t`` real   ``t`` / ``-t`` / ``Abs(t)``
``asech(sech(t))``            ``t >= 0`` / ``t <= 0`` / ``t`` real   ``t`` / ``-t`` / ``Abs(t)``
``acoth(coth(t))``            ``t`` real and nonzero                 ``t``
``acsch(csch(t))``            ``t`` real and nonzero                 ``t``
``atan2(y, x)``               signs of ``x`` and ``y``               see :func:`refine_atan2`
============================  =====================================  ==========

Bounds are established with the relational predicates (``Q.ge(t, -pi/2)``
and friends), answered by SymPy's ``ask``; when a bound is not answered
directly, a unary sign fact that implies it (``Q.nonnegative(t)`` implies
``t >= -pi/2``) is tried.  The ordering relations are only defined on real
numbers (``Ge(I, 0)`` raises), so a bound that ``ask`` confirms is taken to
carry realness with it.

Off the real line none of the ``f⁻¹(f(t)) = t`` rules survive in general
(``asinh(sinh(1 + 3*I)) = -1 + (3 - pi)*I``), and even inside the vertical
strip where ``asin(sin(t)) = t`` holds for complex ``t`` the boundary fails
(``asin(sin(pi/2 + 3*I)) = pi/2 - 3*I``), so nothing fires without a real
argument.  ``asin(-x) = -asin(x)`` and the other odd/even symmetries are
SymPy's own automatic evaluation and are not repeated here.
"""
from __future__ import annotations

from typing import Any

from sympy.assumptions import Q
from sympy.assumptions.assume import AppliedPredicate
from sympy.core import S
from sympy.core.basic import Basic
from sympy.core.expr import Expr
from sympy.core.numbers import pi
from sympy.functions.elementary.complexes import Abs, sign
from sympy.functions.elementary.hyperbolic import (
    cosh, coth, csch, sech, sinh, tanh,
)
from sympy.functions.elementary.trigonometric import atan, cos, cot, sin, tan
from sympy.logic.boolalg import And

from ...identities.compat import upstream as _upstream
from ...identities.compat.upstream import handlers_dict


# ---------------------------------------------------------------------------
# asking
# ---------------------------------------------------------------------------

def _ask(proposition: Basic, assumptions: Any) -> bool:
    """``True`` only when the backend answers ``True``.

    Relation queries are answered by SymPy's ``ask`` alone, which may raise
    ``ValueError('inconsistent assumptions')`` when the two sides carry
    different unary facts, or ``TypeError('Invalid comparison of
    non-real ...')`` from the LRA theory when a side is a non-real number.
    Either exception counts as "not established".
    """
    try:
        return _upstream.ask(proposition, assumptions) is True
    except (ValueError, TypeError):
        return False


_ORDER_RELATIONS = (Q.ge, Q.gt, Q.le, Q.lt)


def _has_order_relation(assumptions: Any) -> bool:
    """Whether ``assumptions`` mention ``Q.ge``/``Q.gt``/``Q.le``/``Q.lt`` at all.

    A bound with a nonzero constant (``t <= pi/2``) can only be established
    from such an assumption; the unary sign facts that also imply a bound
    are tried separately.  Skipping the relation queries when no relation
    was assumed avoids SymPy's slow LRA search for an answer that cannot
    exist, and can only make the handler fire less.
    """
    if not isinstance(assumptions, Basic):
        return False
    return any(atom.function in _ORDER_RELATIONS
               for atom in assumptions.atoms(AppliedPredicate))


def _conjunct_bounds(t: Expr, assumptions: Any) -> list[tuple[str, Expr]]:
    """Numeric bounds on ``t`` stated as top-level conjuncts of ``assumptions``.

    Returns ``(kind, c)`` pairs with ``kind`` in ``'ge'``, ``'gt'``, ``'le'``,
    ``'lt'`` meaning ``t <kind> c`` for a real number ``c``.  Only conjuncts
    of an ``And`` (or a lone predicate) are read, never atoms under ``Or`` or
    ``Not``; those are left to ``ask``.  This is a fast path for what SymPy's
    ask cannot do with a constant like ``pi/2`` (its LRA theory treats ``pi``
    as an opaque symbol, so ``Q.ge(x, pi/2)`` does not answer
    ``Q.ge(x, -pi/2)``), and it can only add ``True`` answers that are
    arithmetically immediate.
    """
    if not isinstance(assumptions, Basic):
        return []
    flipped = {'ge': 'le', 'gt': 'lt', 'le': 'ge', 'lt': 'gt'}
    bounds = []
    for conjunct in And.make_args(assumptions):
        if not (isinstance(conjunct, AppliedPredicate)
                and conjunct.function in _ORDER_RELATIONS):
            continue
        kind = conjunct.function.name
        lhs, rhs = conjunct.arguments
        if lhs == t and rhs.is_number and rhs.is_extended_real:
            bounds.append((kind, rhs))
        elif rhs == t and lhs.is_number and lhs.is_extended_real:
            bounds.append((flipped[kind], lhs))
    return bounds


def _stated_ge(t: Expr, a: Expr, strict: bool, assumptions: Any) -> bool | None:
    """``t >= a`` (``t > a`` when ``strict``) from a stated lower bound.

    ``True`` when a stated bound settles it, ``None`` when no numeric lower
    bound on ``t`` is stated at all, ``False`` when bounds are stated but
    none of them is enough.
    """
    found = False
    for kind, c in _conjunct_bounds(t, assumptions):
        if kind not in ('ge', 'gt'):
            continue
        found = True
        diff = c - a
        if diff.is_positive or (diff.is_zero and (kind == 'gt' or not strict)):
            return True
    return False if found else None


def _stated_le(t: Expr, b: Expr, strict: bool, assumptions: Any) -> bool | None:
    """``t <= b`` (``t < b`` when ``strict``) from a stated upper bound."""
    found = False
    for kind, c in _conjunct_bounds(t, assumptions):
        if kind not in ('le', 'lt'):
            continue
        found = True
        diff = b - c
        if diff.is_positive or (diff.is_zero and (kind == 'lt' or not strict)):
            return True
    return False if found else None


def _bound(t: Expr, stated: bool | None, relation: Basic, assumptions: Any) -> bool:
    """Combine the stated-bound scan with the relation query.

    When a numeric bound in this direction is stated but does not settle
    the question, the query is skipped: SymPy's ask could only answer it by
    arithmetic on ``pi``, which its LRA theory does not do, and the search
    for that answer is slow.  Without any stated bound the question is
    asked, since ``ask`` may derive it (``Q.ge(t, y) & Q.ge(y, 0)`` gives
    ``t >= 0``).
    """
    if stated:
        return True
    if stated is None:
        return _ask(relation, assumptions)
    return False


def _ge(t: Expr, a: Expr, assumptions: Any, relations: bool) -> bool:
    """``t >= a`` for a concrete real ``a``, by relation or by a sign fact."""
    if relations and _bound(t, _stated_ge(t, a, False, assumptions), Q.ge(t, a), assumptions):
        return True
    # t >= 0 >= a
    return bool(a.is_nonpositive) and _ask(Q.nonnegative(t), assumptions)


def _gt(t: Expr, a: Expr, assumptions: Any, relations: bool) -> bool:
    """``t > a`` for a concrete real ``a``."""
    if relations and _bound(t, _stated_ge(t, a, True, assumptions), Q.gt(t, a), assumptions):
        return True
    # t >= 0 > a, or t > 0 >= a
    if a.is_negative and _ask(Q.nonnegative(t), assumptions):
        return True
    return bool(a.is_nonpositive) and _ask(Q.positive(t), assumptions)


def _le(t: Expr, b: Expr, assumptions: Any, relations: bool) -> bool:
    """``t <= b`` for a concrete real ``b``."""
    if relations and _bound(t, _stated_le(t, b, False, assumptions), Q.le(t, b), assumptions):
        return True
    # t <= 0 <= b
    return bool(b.is_nonnegative) and _ask(Q.nonpositive(t), assumptions)


def _lt(t: Expr, b: Expr, assumptions: Any, relations: bool) -> bool:
    """``t < b`` for a concrete real ``b``."""
    if relations and _bound(t, _stated_le(t, b, True, assumptions), Q.lt(t, b), assumptions):
        return True
    # t <= 0 < b, or t < 0 <= b
    if b.is_positive and _ask(Q.nonpositive(t), assumptions):
        return True
    return bool(b.is_nonnegative) and _ask(Q.negative(t), assumptions)


def _in_closed(t: Expr, a: Expr, b: Expr, assumptions: Any) -> bool:
    """``a <= t <= b`` (which also makes ``t`` real)."""
    relations = _has_order_relation(assumptions)
    return _ge(t, a, assumptions, relations) and _le(t, b, assumptions, relations)


def _in_open(t: Expr, a: Expr, b: Expr, assumptions: Any) -> bool:
    """``a < t < b`` (which also makes ``t`` real)."""
    relations = _has_order_relation(assumptions)
    return _gt(t, a, assumptions, relations) and _lt(t, b, assumptions, relations)


def _real(t: Expr, assumptions: Any) -> bool:
    return _ask(Q.real(t), assumptions)


def _real_nonzero(t: Expr, assumptions: Any) -> bool:
    return _ask(Q.nonzero(t), assumptions) and _real(t, assumptions)


# ---------------------------------------------------------------------------
# inverse trigonometric
# ---------------------------------------------------------------------------

def refine_asin(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``asin``.

    ``asin`` has range ``[-pi/2, pi/2]`` on ``[-1, 1]``; ``asin(sin(t))`` is
    ``t`` there, ``pi - t`` on the next half-period to the right
    (``sin(t) = sin(pi - t)``) and ``-pi - t`` on the one to the left.
    ``asin(cos(t)) = pi/2 - t`` for ``t`` in ``[0, pi]``.

    Examples
    ========

    >>> from sympy import Q, asin, sin, cos, pi
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(asin(sin(x)), Q.ge(x, -pi/2) & Q.le(x, pi/2))
    x
    >>> refine(asin(sin(x)), Q.ge(x, pi/2) & Q.le(x, 3*pi/2))
    pi - x
    >>> refine(asin(cos(x)), Q.nonnegative(x) & Q.le(x, pi))
    -x + pi/2
    >>> refine(asin(sin(x)), Q.real(x))
    asin(sin(x))
    """
    arg = expr.args[0]
    if isinstance(arg, sin):
        t = arg.args[0]
        if _in_closed(t, -pi/2, pi/2, assumptions):
            return t
        if _in_closed(t, pi/2, 3*pi/2, assumptions):
            return pi - t
        if _in_closed(t, -3*pi/2, -pi/2, assumptions):
            return -pi - t
    elif isinstance(arg, cos):
        t = arg.args[0]
        if _in_closed(t, S.Zero, pi, assumptions):
            return pi/2 - t
    return None


def refine_acos(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``acos``.

    ``acos`` has range ``[0, pi]`` on ``[-1, 1]``; ``acos(cos(t))`` is ``t``
    there, ``-t`` on ``[-pi, 0]`` and ``2*pi - t`` on ``[pi, 2*pi]``.
    ``acos(sin(t)) = pi/2 - t`` for ``t`` in ``[-pi/2, pi/2]``.

    Examples
    ========

    >>> from sympy import Q, acos, cos, sin, pi
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(acos(cos(x)), Q.nonnegative(x) & Q.le(x, pi))
    x
    >>> refine(acos(cos(x)), Q.ge(x, -pi) & Q.nonpositive(x))
    -x
    >>> refine(acos(sin(x)), Q.ge(x, -pi/2) & Q.le(x, pi/2))
    -x + pi/2
    >>> refine(acos(cos(x)), Q.real(x))
    acos(cos(x))
    """
    arg = expr.args[0]
    if isinstance(arg, cos):
        t = arg.args[0]
        if _in_closed(t, S.Zero, pi, assumptions):
            return t
        if _in_closed(t, -pi, S.Zero, assumptions):
            return -t
        if _in_closed(t, pi, 2*pi, assumptions):
            return 2*pi - t
    elif isinstance(arg, sin):
        t = arg.args[0]
        if _in_closed(t, -pi/2, pi/2, assumptions):
            return pi/2 - t
    return None


def refine_atan(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``atan``.

    ``atan`` has range ``(-pi/2, pi/2)``; ``atan(tan(t))`` is ``t`` on that
    open interval (``tan`` has poles at the endpoints, where SymPy leaves
    ``atan(zoo)`` unevaluated) and ``t -+ pi`` on the neighbouring open
    periods.  ``atan(cot(t)) = pi/2 - t`` for ``t`` in ``(0, pi)``.

    Examples
    ========

    >>> from sympy import Q, atan, tan, cot, pi
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(atan(tan(x)), Q.gt(x, -pi/2) & Q.lt(x, pi/2))
    x
    >>> refine(atan(tan(x)), Q.positive(x) & Q.lt(x, pi/2))
    x
    >>> refine(atan(tan(x)), Q.gt(x, pi/2) & Q.lt(x, 3*pi/2))
    x - pi
    >>> refine(atan(cot(x)), Q.positive(x) & Q.lt(x, pi))
    -x + pi/2
    >>> refine(atan(tan(x)), Q.ge(x, -pi/2) & Q.le(x, pi/2))
    atan(tan(x))
    """
    arg = expr.args[0]
    if isinstance(arg, tan):
        t = arg.args[0]
        if _in_open(t, -pi/2, pi/2, assumptions):
            return t
        if _in_open(t, pi/2, 3*pi/2, assumptions):
            return t - pi
        if _in_open(t, -3*pi/2, -pi/2, assumptions):
            return t + pi
    elif isinstance(arg, cot):
        t = arg.args[0]
        if _in_open(t, S.Zero, pi, assumptions):
            return pi/2 - t
    return None


def refine_atan2(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``atan2(y, x)``.

    Reproduces the cases of the vendored ``_upstream.refine_atan2`` (all of
    which are sound) and adds the three that it misses: ``y`` zero with ``x``
    positive is ``0``; ``y`` merely nonnegative with ``x`` negative is still
    ``atan(y/x) + pi`` (the ``y = 0`` endpoint gives ``pi``, as
    ``atan2(0, negative)`` does); ``x`` zero with ``y`` real and nonzero is
    ``sign(y)*pi/2``.  ``y`` nonpositive with ``x`` negative is deliberately
    *not* ``atan(y/x) - pi``: at ``y = 0`` that would give ``-pi``.

    Examples
    ========

    >>> from sympy import Q, atan2
    >>> from sympy.abc import x, y
    >>> from satrefine import refine
    >>> refine(atan2(y, x), Q.real(y) & Q.positive(x))
    atan(y/x)
    >>> refine(atan2(y, x), Q.zero(y) & Q.positive(x))
    0
    >>> refine(atan2(y, x), Q.nonnegative(y) & Q.negative(x))
    atan(y/x) + pi
    >>> refine(atan2(y, x), Q.negative(y) & Q.negative(x))
    atan(y/x) - pi
    >>> refine(atan2(y, x), Q.zero(y) & Q.negative(x))
    pi
    >>> refine(atan2(y, x), Q.positive(y) & Q.zero(x))
    pi/2
    >>> refine(atan2(y, x), Q.negative(y) & Q.zero(x))
    -pi/2
    >>> refine(atan2(y, x), Q.nonzero(y) & Q.zero(x))
    pi*sign(y)/2
    >>> refine(atan2(y, x), Q.zero(y) & Q.zero(x))
    nan
    >>> refine(atan2(y, x), Q.nonpositive(y) & Q.negative(x))
    atan2(y, x)
    """
    y, x = expr.args
    if _ask(Q.positive(x), assumptions):
        if _ask(Q.zero(y), assumptions):
            return S.Zero
        if _real(y, assumptions):
            return atan(y / x)
        return None
    if _ask(Q.negative(x), assumptions):
        if _ask(Q.zero(y), assumptions):
            return pi
        if _ask(Q.nonnegative(y), assumptions):
            return atan(y / x) + pi
        if _ask(Q.negative(y), assumptions):
            return atan(y / x) - pi
        return None
    if _ask(Q.zero(x), assumptions):
        if _ask(Q.positive(y), assumptions):
            return pi/2
        if _ask(Q.negative(y), assumptions):
            return -pi/2
        if _ask(Q.zero(y), assumptions):
            return S.NaN
        if _real_nonzero(y, assumptions):
            return sign(y) * pi/2
        return None
    return None


# ---------------------------------------------------------------------------
# inverse hyperbolic
# ---------------------------------------------------------------------------

def refine_asinh(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``asinh``: ``asinh(sinh(t)) = t`` for real ``t``.

    Examples
    ========

    >>> from sympy import Q, asinh, sinh
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(asinh(sinh(x)), Q.real(x))
    x
    >>> refine(asinh(sinh(x)), Q.complex(x))
    asinh(sinh(x))
    """
    arg = expr.args[0]
    if isinstance(arg, sinh):
        t = arg.args[0]
        if _real(t, assumptions):
            return t
    return None


def refine_atanh(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``atanh``: ``atanh(tanh(t)) = t`` for real ``t``.

    Examples
    ========

    >>> from sympy import Q, atanh, tanh
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(atanh(tanh(x)), Q.real(x))
    x
    >>> refine(atanh(tanh(x)), Q.imaginary(x))
    atanh(tanh(x))
    """
    arg = expr.args[0]
    if isinstance(arg, tanh):
        t = arg.args[0]
        if _real(t, assumptions):
            return t
    return None


def _refine_even_inverse(expr: Basic, forward: type, assumptions: Any) -> Basic | None:
    """``inv(forward(t))`` for an even ``forward`` whose inverse is ``>= 0``.

    ``cosh`` and ``sech`` are even, and ``acosh`` on ``[1, oo)`` and
    ``asech`` on ``(0, 1]`` return nonnegative reals, so the composition is
    ``Abs(t)`` for every real ``t``: ``t`` when ``t >= 0``, ``-t`` when
    ``t <= 0``.
    """
    arg = expr.args[0]
    if isinstance(arg, forward):
        t = arg.args[0]
        if _ask(Q.nonnegative(t), assumptions):
            return t
        if _ask(Q.nonpositive(t), assumptions):
            return -t
        if _real(t, assumptions):
            return Abs(t)
    return None


def refine_acosh(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``acosh``: ``acosh(cosh(t))`` is ``t`` for ``t >= 0``, ``-t``
    for ``t <= 0`` and ``Abs(t)`` for any real ``t``.

    Examples
    ========

    >>> from sympy import Q, acosh, cosh
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(acosh(cosh(x)), Q.nonnegative(x))
    x
    >>> refine(acosh(cosh(x)), Q.negative(x))
    -x
    >>> refine(acosh(cosh(x)), Q.real(x))
    Abs(x)
    >>> refine(acosh(cosh(x)), Q.complex(x))
    acosh(cosh(x))
    """
    return _refine_even_inverse(expr, cosh, assumptions)


def refine_asech(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``asech``: ``asech(sech(t))`` is ``t`` for ``t >= 0``, ``-t``
    for ``t <= 0`` and ``Abs(t)`` for any real ``t``.

    Examples
    ========

    >>> from sympy import Q, asech, sech
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(asech(sech(x)), Q.positive(x))
    x
    >>> refine(asech(sech(x)), Q.nonpositive(x))
    -x
    >>> refine(asech(sech(x)), Q.real(x))
    Abs(x)
    """
    return _refine_even_inverse(expr, sech, assumptions)


def _refine_odd_inverse_with_pole(expr: Basic, forward: type, assumptions: Any) -> Basic | None:
    """``inv(forward(t)) = t`` for real nonzero ``t``.

    ``coth`` and ``csch`` are odd bijections from each of ``(-oo, 0)`` and
    ``(0, oo)`` onto ``(-oo, -1)``/``(1, oo)`` and ``(-oo, 0)``/``(0, oo)``,
    where ``acoth`` and ``acsch`` are their real inverses.  At ``t = 0`` the
    forward function has a pole (SymPy gives ``zoo`` and then
    ``acoth(zoo) = acsch(zoo) = 0``, which happens to agree), but the rule is
    only claimed away from it.
    """
    arg = expr.args[0]
    if isinstance(arg, forward):
        t = arg.args[0]
        if _real_nonzero(t, assumptions):
            return t
    return None


def refine_acoth(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``acoth``: ``acoth(coth(t)) = t`` for real nonzero ``t``.

    Examples
    ========

    >>> from sympy import Q, acoth, coth
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(acoth(coth(x)), Q.nonzero(x))
    x
    >>> refine(acoth(coth(x)), Q.negative(x))
    x
    >>> refine(acoth(coth(x)), Q.real(x))
    acoth(coth(x))
    """
    return _refine_odd_inverse_with_pole(expr, coth, assumptions)


def refine_acsch(expr: Basic, assumptions: Any) -> Basic | None:
    """
    Handler for ``acsch``: ``acsch(csch(t)) = t`` for real nonzero ``t``.

    Examples
    ========

    >>> from sympy import Q, acsch, csch
    >>> from sympy.abc import x
    >>> from satrefine import refine
    >>> refine(acsch(csch(x)), Q.positive(x))
    x
    >>> refine(acsch(csch(x)), Q.real(x))
    acsch(csch(x))
    """
    return _refine_odd_inverse_with_pole(expr, csch, assumptions)


handlers_dict['asin'] = refine_asin
handlers_dict['acos'] = refine_acos
handlers_dict['atan'] = refine_atan
handlers_dict['atan2'] = refine_atan2
handlers_dict['asinh'] = refine_asinh
handlers_dict['acosh'] = refine_acosh
handlers_dict['atanh'] = refine_atanh
handlers_dict['acoth'] = refine_acoth
handlers_dict['asech'] = refine_asech
handlers_dict['acsch'] = refine_acsch
