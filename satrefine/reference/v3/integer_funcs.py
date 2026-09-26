"""Refine handlers for ``floor``, ``ceiling``, ``frac``, ``Mod`` and ``Rem``.

Every rule below asks through ``_upstream.ask`` and returns ``None`` when its
precondition is not established; an inconsistency ``ValueError`` from any
ask (contradictory assumptions) is read as "unknown".  Relation queries (``Q.lt`` and friends)
are answered by SymPy's ``ask`` only and may raise ``ValueError``; they are
asked through :func:`_holds_lt`, which treats an exception as "unknown" and
also tries the unary form ``Q.positive(b - a)``.

Definitions used (``floor``/``ceiling``/``frac`` act componentwise on
complex numbers, so a Gaussian integer shifts through them):

* ``Mod(a, b) = a - b*floor(a/b)``: the result has the sign of ``b``.
* ``Rem(a, b) = a - b*trunc(a/b)``: the result has the sign of ``a``.

floor / ceiling  (``F`` stands for either)
    F1. ``F(x) -> x``            if ``Q.integer(x)``.
    F2. ``F(x) -> x``            if ``Q.infinite(x)`` and ``Q.extended_real(x)``.
    F3. ``F(n + x) -> n + F(x)`` for every term ``n`` of an ``Add`` argument
        with ``Q.integer(n)``, or that is itself a ``floor``/``ceiling``
        of a ``Q.finite`` argument (a Gaussian integer).
    F4. ``floor(x) -> 0``        if ``0 <= x < 1``.
        ``ceiling(x) -> 0``      if ``-1 < x <= 0``.
    ``floor(-x)`` is rewritten by SymPy itself and is not duplicated here.

frac
    R1. ``frac(x) -> 0``         if ``Q.integer(x)``.
    R2. ``frac(n + x) -> frac(x)`` for integer (or floor/ceiling of finite)
        terms ``n``.
    R3. ``frac(x) -> x``         if ``0 <= x < 1``.
    ``frac(x)`` for a merely real ``x`` is left alone.

Mod(a, b)
    M1. ``-> 0``                 if ``Q.nonzero(b)`` (real, nonzero) and
                                 ``Q.integer(a/b)``; covers ``Mod(x, 1)``
                                 for integer ``x`` and ``Mod(k*n, n)`` for
                                 integer ``k`` and nonzero ``n``.
    M2. ``b in {2, -2}`` and ``Q.integer(a)``: even ``a`` -> ``0``; odd ``a``
        -> ``1`` for ``b = 2``, ``-1`` for ``b = -2``.
    M3. ``Mod(t + a', b) -> Mod(a', b)`` dropping every term ``t`` of an
        ``Add`` with ``Q.integer(t/b)``, when ``Q.nonzero(b)``; gives
        ``Mod(2*n + 1, 2) -> 1`` for integer ``n``.
    M4. ``-> a``                 if ``0 <= a < b`` or ``b < a <= 0`` (the
                                 relation fixes the sign of ``b``).
    M5. ``-> Rem(a, b)``         if (``a >= 0`` and ``b > 0``) or
                                 (``a <= 0`` and ``b < 0``).
        (Never the reverse, so the two handlers cannot loop.)

Rem(a, b)
    Q1. ``-> 0``                 if ``Q.nonzero(b)`` and ``Q.integer(a/b)``.
    Q2. ``b in {2, -2}`` and ``Q.integer(a)``: even ``a`` -> ``0``; odd ``a``
        -> ``1`` if ``Q.positive(a)``, ``-1`` if ``Q.negative(a)``; an odd
        ``a`` of unknown sign is left alone (``Rem(-3, 2) = -1``).
    Q3. ``-> a``                 if ``-|b| < a < |b|``, established as one of
                                 ``0 <= a < b``, ``0 <= a < -b``,
                                 ``-b < a <= 0``, ``b < a <= 0``, or
                                 ``-b < a < b`` / ``b < a < -b`` with the
                                 sign of ``b`` known (a proven relation
                                 implies ``a`` is real).
    Integer shifts are not pulled out of ``Rem`` (``Rem(a + k*b, b)`` differs
    from ``Rem(a, b)`` when the shift changes the sign of the dividend).
"""
from __future__ import annotations

from typing import Any

from sympy import Add, S
from sympy.assumptions import Q
from sympy.core.expr import Expr
from sympy.core.mod import Mod
from sympy.functions.elementary.integers import ceiling, floor, frac
from sympy.functions.elementary.miscellaneous import Rem

from ...identities.compat import upstream as _upstream
from ...identities.compat.upstream import handlers_dict
from ._common import is_integer as _is_integer_raw


def is_integer(k: Expr, assumptions: Any) -> bool | None:
    """``_common.is_integer`` with an inconsistency error read as "unknown"."""
    try:
        return _is_integer_raw(k, assumptions)
    except ValueError:
        return None


def _ask(proposition: Any, assumptions: Any) -> bool | None:
    """``_upstream.ask`` with an inconsistency error read as "unknown"."""
    try:
        return _upstream.ask(proposition, assumptions)
    except ValueError:
        return None


def _holds_lt(a: Expr, b: Expr, assumptions: Any, strict: bool = True) -> bool:
    """Whether ``a < b`` (``a <= b`` if not ``strict``) is known."""
    rel = Q.lt if strict else Q.le
    unary = Q.positive if strict else Q.nonnegative
    if _ask(rel(a, b), assumptions) is True:
        return True
    return _ask(unary(b - a), assumptions) is True


def _is_gaussian_integer_term(term: Expr, assumptions: Any) -> bool:
    # floor(y) is a Gaussian integer only for finite y: floor(oo) = oo and
    # frac(1/2 + floor(oo)) = AccumBounds(0, 1) != frac(1/2).
    if isinstance(term, (floor, ceiling)):
        return _ask(Q.finite(term.args[0]), assumptions) is True
    return is_integer(term, assumptions) is True


def _split_integer_terms(arg: Expr, assumptions: Any) -> tuple[list[Expr], list[Expr]]:
    ints, rest = [], []
    for term in Add.make_args(arg):
        (ints if _is_gaussian_integer_term(term, assumptions) else rest).append(term)
    return ints, rest


# ---------------------------------------------------------------- floor/ceiling

def refine_floor(expr: Expr, assumptions: Any) -> Expr | None:
    return _refine_floor_ceiling(expr, assumptions)


def refine_ceiling(expr: Expr, assumptions: Any) -> Expr | None:
    return _refine_floor_ceiling(expr, assumptions)


def _refine_floor_ceiling(expr: Expr, assumptions: Any) -> Expr | None:
    arg = expr.args[0]
    if is_integer(arg, assumptions):                                        # F1
        return arg
    if _ask(Q.infinite(arg), assumptions) and _ask(Q.extended_real(arg), assumptions):
        return arg                                                          # F2
    if isinstance(arg, Add):                                                # F3
        ints, rest = _split_integer_terms(arg, assumptions)
        if ints:
            return Add(*ints) + expr.func(Add(*rest))
    if _ask(Q.real(arg), assumptions):                                      # F4
        if isinstance(expr, floor):
            if (_ask(Q.nonnegative(arg), assumptions)
                    and _holds_lt(arg, S.One, assumptions)):
                return S.Zero
        elif (_ask(Q.nonpositive(arg), assumptions)
                and _holds_lt(S.NegativeOne, arg, assumptions)):
            return S.Zero
    return None


# ------------------------------------------------------------------------ frac

def refine_frac(expr: Expr, assumptions: Any) -> Expr | None:
    arg = expr.args[0]
    if is_integer(arg, assumptions):                                        # R1
        return S.Zero
    if isinstance(arg, Add):                                                # R2
        ints, rest = _split_integer_terms(arg, assumptions)
        if ints:
            return frac(Add(*rest))
    if (_ask(Q.nonnegative(arg), assumptions)                               # R3
            and _holds_lt(arg, S.One, assumptions)):
        return arg
    return None


# ------------------------------------------------------------------ Mod / Rem

def _is_multiple(a: Expr, b: Expr, assumptions: Any) -> bool:
    """``a/b`` is an integer and ``b`` is real and nonzero."""
    if not _ask(Q.nonzero(b), assumptions):
        return False
    return is_integer(a / b, assumptions) is True


def _parity(a: Expr, assumptions: Any) -> str | None:
    if a.is_Integer:
        return "even" if int(a) % 2 == 0 else "odd"
    if not is_integer(a, assumptions):
        return None
    if _ask(Q.even(a), assumptions):
        return "even"
    if _ask(Q.odd(a), assumptions):
        return "odd"
    return None


def refine_Mod(expr: Expr, assumptions: Any) -> Expr | None:
    a, b = expr.args
    if _is_multiple(a, b, assumptions):                                     # M1
        return S.Zero
    if b in (S(2), S(-2)):                                                  # M2
        p = _parity(a, assumptions)
        if p == "even":
            return S.Zero
        if p == "odd":
            return S.One if b == 2 else S.NegativeOne
    if isinstance(a, Add) and _ask(Q.nonzero(b), assumptions):             # M3
        kept = [t for t in a.args if not is_integer(t / b, assumptions)]
        if len(kept) < len(a.args):
            return Mod(Add(*kept), b)
    a_nonneg = _ask(Q.nonnegative(a), assumptions)
    a_nonpos = None if a_nonneg else _ask(Q.nonpositive(a), assumptions)
    if a_nonneg and _holds_lt(a, b, assumptions):                           # M4
        return a                         # 0 <= a < b
    if a_nonpos and _holds_lt(b, a, assumptions):
        return a                         # b < a <= 0
    if a_nonneg and _ask(Q.positive(b), assumptions):                       # M5
        return Rem(a, b)
    if a_nonpos and _ask(Q.negative(b), assumptions):
        return Rem(a, b)
    return None


def refine_Rem(expr: Expr, assumptions: Any) -> Expr | None:
    a, b = expr.args
    if _is_multiple(a, b, assumptions):                                     # Q1
        return S.Zero
    if b in (S(2), S(-2)):                                                  # Q2
        p = _parity(a, assumptions)
        if p == "even":
            return S.Zero
        if p == "odd":
            if _ask(Q.positive(a), assumptions):
                return S.One
            if _ask(Q.negative(a), assumptions):
                return S.NegativeOne
            return None
    # Q3: -|b| < a < |b|.  Each branch fixes the sign of b (and so |b|).
    if _ask(Q.nonnegative(a), assumptions):
        if _holds_lt(a, b, assumptions) or _holds_lt(a, -b, assumptions):
            return a
        return None
    if _ask(Q.nonpositive(a), assumptions):
        if _holds_lt(-b, a, assumptions) or _holds_lt(b, a, assumptions):
            return a
        return None
    if _ask(Q.positive(b), assumptions):
        bound = b
    elif _ask(Q.negative(b), assumptions):
        bound = -b
    else:
        return None
    if _holds_lt(-bound, a, assumptions) and _holds_lt(a, bound, assumptions):
        return a
    return None


handlers_dict['floor'] = refine_floor
handlers_dict['ceiling'] = refine_ceiling
handlers_dict['frac'] = refine_frac
handlers_dict['Mod'] = refine_Mod
handlers_dict['Rem'] = refine_Rem
