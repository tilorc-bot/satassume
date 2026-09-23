"""Refine handlers for the combinatorial family: ``factorial``, ``binomial``,
``RisingFactorial``, ``FallingFactorial`` and ``gamma``.

Every rule below agrees with SymPy's own definitions (``eval`` and numeric
evaluation) at every point allowed by its precondition, including 0,
negative integers and poles (where both sides are ``zoo``).  "``a == b``"
means structurally equal after expansion, or ``Q.zero(a - b)``, or the
relation ``Q.eq(a, b)``; order conditions are asked both as a sign
predicate on the difference and as a relation (relation asks are answered
by SymPy only and are wrapped, since they may raise on inconsistent input).

factorial(n)
    * ``n == 0`` or ``n == 1``                          -> 1
    * n a negative integer                              -> zoo
    (``factorial(n) -> gamma(n + 1)`` is not a simplification: not done.)

binomial(n, k)
    * ``k == 0``                                        -> 1
    * ``k == 1``                                        -> n
    * k a negative integer (any n; SymPy's convention)  -> 0
    * ``k == n`` and (n nonnegative or n not an integer) -> 1
    * ``k == n - 1`` and (n nonnegative or n not an integer) -> n
      (for a negative integer n both are 0 under SymPy's convention,
      e.g. ``binomial(-1, -1) == 0``, so the precondition is required)
    * n a nonnegative integer, k an integer, ``n < k``   -> 0
    * n a negative integer, k not an integer            -> zoo
    (``binomial(n, n - k)`` symmetry and the factorial/gamma form are not
    simplifications: not done.)

RisingFactorial(x, k)
    * ``k == 0``                                        -> 1
    * ``k == 1``                                        -> x
    * ``x == 1`` (any k: ``rf(1, k) = gamma(k + 1)``)   -> factorial(k)
    * x a nonpositive integer, k an integer, ``x + k > 0`` -> 0
      (the product x (x+1) ... (x+k-1) contains the factor 0)
    * x a negative integer, k not an integer            -> 0 (SymPy's eval)
    * x positive, or x not an integer                  -> gamma(x + k)/gamma(x)
      (gamma(x) is then finite and nonzero; never done for a nonpositive
      integer x, where e.g. ``rf(-2, 2) = 2`` but the ratio is undefined)

FallingFactorial(x, k)
    * ``k == 0``                                        -> 1
    * ``k == 1``                                        -> x
    * ``x == k`` with k an integer                      -> factorial(k)
      (at negative integers both sides are zoo)
    * x a nonnegative integer, k an integer, ``k > x``  -> 0
    * x a nonnegative integer, k an integer, ``k <= x`` -> factorial(x)/factorial(x - k)
      (``k <= x`` also covers negative k: ``ff(3, -2) = 1/20 = 3!/5!``)

gamma(x)
    * x a positive integer                              -> factorial(x - 1)
      (so ``gamma(n + 1)`` with n a nonnegative integer -> factorial(n))
    * x a nonpositive integer                           -> zoo
    (half-integers ``n + 1/2`` are left alone.)
"""
from __future__ import annotations

from typing import Any

from sympy import S, factorial
from sympy.assumptions import Q
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.traversal import preorder_traversal
from sympy.core.basic import Basic
from sympy.functions.special.gamma_functions import gamma

from .. import _upstream
from .._upstream import handlers_dict


def _ask(prop: Any, assumptions: Any) -> bool | None:
    return _upstream.ask(prop, assumptions)


_RELATIONS = (Q.eq, Q.ne, Q.gt, Q.ge, Q.lt, Q.le)


def _has_relations(assumptions: Any) -> bool:
    """Whether ``assumptions`` mention a relation at all.

    Relation queries go to SymPy's relational solver, which is slow (about a
    second each); without a relation among the assumptions they cannot be
    decided beyond what the sign predicates already answered, so skip them.
    """
    if not isinstance(assumptions, Basic):
        return False
    return any(isinstance(a, AppliedPredicate) and a.function in _RELATIONS
               for a in preorder_traversal(assumptions))


def _ask_rel(prop: Any, assumptions: Any) -> bool | None:
    """Ask a relation; SymPy may raise on inconsistent relation queries."""
    if not _has_relations(assumptions):
        return None
    try:
        return _upstream.ask(prop, assumptions)
    except (ValueError, TypeError):
        return None


def _is_zero(e: Basic, assumptions: Any) -> bool:
    if e.expand() == 0:
        return True
    return _ask(Q.zero(e), assumptions) is True


def _eq(a: Basic, b: Basic, assumptions: Any) -> bool:
    if _is_zero(a - b, assumptions):
        return True
    return _ask_rel(Q.eq(a, b), assumptions) is True


def _lt(a: Basic, b: Basic, assumptions: Any) -> bool:
    """``a < b`` (implies both real).  Both orientations of the difference
    are asked, since the engines do not always relate ``Q.positive(b - a)``
    to ``Q.negative(a - b)``."""
    if _ask(Q.positive(b - a), assumptions) or _ask(Q.negative(a - b), assumptions):
        return True
    return _ask_rel(Q.lt(a, b), assumptions) is True


def _le(a: Basic, b: Basic, assumptions: Any) -> bool:
    """``a <= b`` (implies both real)."""
    if (_ask(Q.nonnegative(b - a), assumptions)
            or _ask(Q.nonpositive(a - b), assumptions)):
        return True
    return _ask_rel(Q.le(a, b), assumptions) is True


def _integer(e: Basic, assumptions: Any) -> bool | None:
    if e.is_Integer:
        return True
    if e.is_Rational:
        return False
    return _ask(Q.integer(e), assumptions)


def _nonneg_int(e: Basic, assumptions: Any) -> bool:
    return bool(_integer(e, assumptions)) and _le(S.Zero, e, assumptions)


def _pos_int(e: Basic, assumptions: Any) -> bool:
    return bool(_integer(e, assumptions)) and _lt(S.Zero, e, assumptions)


def _neg_int(e: Basic, assumptions: Any) -> bool:
    return bool(_integer(e, assumptions)) and _lt(e, S.Zero, assumptions)


def _nonpos_int(e: Basic, assumptions: Any) -> bool:
    return bool(_integer(e, assumptions)) and _le(e, S.Zero, assumptions)


def refine_factorial(expr: Basic, assumptions: Any) -> Basic | None:
    n = expr.args[0]
    if _eq(n, S.Zero, assumptions) or _eq(n, S.One, assumptions):
        return S.One
    if _neg_int(n, assumptions):
        return S.ComplexInfinity
    return None


def refine_binomial(expr: Basic, assumptions: Any) -> Basic | None:
    n, k = expr.args
    if _eq(k, S.Zero, assumptions):
        return S.One
    if _eq(k, S.One, assumptions):
        return n
    if _neg_int(k, assumptions):
        return S.Zero
    n_ok = (_ask(Q.nonnegative(n), assumptions)
            or _integer(n, assumptions) is False)
    if n_ok:
        if _eq(n, k, assumptions):
            return S.One
        if _eq(n - 1, k, assumptions):
            return n
    k_int = _integer(k, assumptions)
    if k_int and _nonneg_int(n, assumptions) and _lt(n, k, assumptions):
        return S.Zero
    if k_int is False and _neg_int(n, assumptions):
        return S.ComplexInfinity
    return None


def refine_RisingFactorial(expr: Basic, assumptions: Any) -> Basic | None:
    x, k = expr.args
    if _eq(k, S.Zero, assumptions):
        return S.One
    if _eq(k, S.One, assumptions):
        return x
    if _eq(x, S.One, assumptions):
        return factorial(k)
    k_int = _integer(k, assumptions)
    if k_int and _nonpos_int(x, assumptions) and _lt(S.Zero, x + k, assumptions):
        return S.Zero
    if k_int is False and _neg_int(x, assumptions):
        return S.Zero
    if _ask(Q.positive(x), assumptions) or _integer(x, assumptions) is False:
        return gamma(x + k) / gamma(x)
    return None


def refine_FallingFactorial(expr: Basic, assumptions: Any) -> Basic | None:
    x, k = expr.args
    if _eq(k, S.Zero, assumptions):
        return S.One
    if _eq(k, S.One, assumptions):
        return x
    k_int = _integer(k, assumptions)
    if not k_int:
        return None
    if _eq(x, k, assumptions):
        return factorial(k)
    if _nonneg_int(x, assumptions):
        if _lt(x, k, assumptions):
            return S.Zero
        if _le(k, x, assumptions):
            return factorial(x) / factorial(x - k)
    return None


def refine_gamma(expr: Basic, assumptions: Any) -> Basic | None:
    x = expr.args[0]
    if _pos_int(x, assumptions):
        return factorial(x - 1)
    if _nonpos_int(x, assumptions):
        return S.ComplexInfinity
    return None


handlers_dict['factorial'] = refine_factorial
handlers_dict['binomial'] = refine_binomial
handlers_dict['RisingFactorial'] = refine_RisingFactorial
handlers_dict['FallingFactorial'] = refine_FallingFactorial
handlers_dict['gamma'] = refine_gamma
