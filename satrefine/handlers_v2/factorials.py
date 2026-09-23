"""Handlers for ``factorial``, ``gamma``, ``binomial``, ``RisingFactorial``
and ``FallingFactorial``.

``factorial`` rules:

K1  ``factorial(n) -> 1`` when ``n`` is zero.
K2  ``factorial(n) -> zoo`` when ``n`` is a negative integer (SymPy's value,
    ``gamma`` has poles there).

``gamma`` rules:

Y1  ``gamma(x) -> zoo`` when ``x`` is a nonpositive integer (pole).
Y2  ``gamma(x) -> factorial(x - 1)`` when ``x`` is a positive integer.

``binomial`` rules (SymPy's ``binomial(n, k)``: for integer ``k`` it is
``0`` for ``k < 0`` and ``n(n-1)...(n-k+1)/k!`` for ``k >= 0``; e.g.
``binomial(-1, -1) == 0``, so ``binomial(n, n) -> 1`` needs ``n >= 0``):

B1  ``binomial(n, k) -> 1`` when ``k`` is zero.
B2  ``binomial(n, k) -> 0`` when ``k`` is a negative integer.
B3  ``binomial(n, k) -> 0`` when ``n`` is a nonnegative integer, ``k`` an
    integer and ``n - k`` negative.
B4  ``binomial(n, k) -> 1`` when ``n`` is a nonnegative integer and
    ``n - k`` is zero.

``RisingFactorial(x, k) == gamma(x + k)/gamma(x)`` and
``FallingFactorial(x, k) == gamma(x + 1)/gamma(x - k + 1)`` rules:

P1  ``-> 1`` when ``k`` is zero.
P2  ``-> 0`` when ``x`` is zero and ``k`` a positive integer (the product
    starts with the factor ``x``).
P3  ``RisingFactorial(x, k) -> factorial(k)`` when ``x - 1`` is zero
    (SymPy evaluates ``RisingFactorial(1, k)`` so for every ``k``).
P4  ``FallingFactorial(x, k) -> factorial(k)`` when ``x - k`` is zero and
    ``k`` is a nonnegative integer (``k(k-1)...1``).
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, S
from sympy.functions.combinatorial.factorials import factorial

from .._upstream import handlers_dict
from ._common import Assumptions, holds


def _nonnegative_integer(x: Basic, assumptions: Assumptions) -> bool:
    return holds(Q.integer(x), assumptions) and holds(Q.nonnegative(x), assumptions)


def _positive_integer(x: Basic, assumptions: Assumptions) -> bool:
    return holds(Q.integer(x), assumptions) and holds(Q.positive(x), assumptions)


def refine_factorial(expr: Basic, assumptions: Assumptions) -> Basic | None:
    n = expr.args[0]
    if holds(Q.zero(n), assumptions):                                   # K1
        return S.One
    if holds(Q.integer(n), assumptions) and holds(Q.negative(n), assumptions):  # K2
        return S.ComplexInfinity
    return None


def refine_gamma(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.integer(x), assumptions):
        if holds(Q.nonpositive(x), assumptions):                        # Y1
            return S.ComplexInfinity
        if holds(Q.positive(x), assumptions):                           # Y2
            return factorial(x - 1)
    return None


def refine_binomial(expr: Basic, assumptions: Assumptions) -> Basic | None:
    n, k = expr.args
    if holds(Q.zero(k), assumptions):                                   # B1
        return S.One
    if holds(Q.integer(k), assumptions) and holds(Q.negative(k), assumptions):  # B2
        return S.Zero
    if _nonnegative_integer(n, assumptions):
        if holds(Q.integer(k), assumptions) and holds(Q.negative(n - k), assumptions):  # B3
            return S.Zero
        if holds(Q.zero(n - k), assumptions):                           # B4
            return S.One
    return None


def _refine_pochhammer(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rules P1 and P2, shared by both Pochhammer symbols."""
    x, k = expr.args
    if holds(Q.zero(k), assumptions):                                   # P1
        return S.One
    if holds(Q.zero(x), assumptions) and _positive_integer(k, assumptions):  # P2
        return S.Zero
    return None


def refine_RisingFactorial(expr: Basic, assumptions: Assumptions) -> Basic | None:
    shared = _refine_pochhammer(expr, assumptions)
    if shared is not None:
        return shared
    x, k = expr.args
    if holds(Q.zero(x - 1), assumptions):                               # P3
        return factorial(k)
    return None


def refine_FallingFactorial(expr: Basic, assumptions: Assumptions) -> Basic | None:
    shared = _refine_pochhammer(expr, assumptions)
    if shared is not None:
        return shared
    x, k = expr.args
    if holds(Q.zero(x - k), assumptions) and _nonnegative_integer(k, assumptions):  # P4
        return factorial(k)
    return None


handlers_dict['factorial'] = refine_factorial
handlers_dict['gamma'] = refine_gamma
handlers_dict['binomial'] = refine_binomial
handlers_dict['RisingFactorial'] = refine_RisingFactorial
handlers_dict['FallingFactorial'] = refine_FallingFactorial
