"""Handlers for ``exp`` and ``log``.

``exp`` rules:

E1  ``exp(x) -> 1`` when ``x`` is zero.
E2  Every additive term ``c*pi*I`` of the argument whose coefficient ``c``
    (or an additive part of it) is a provable integer ``n`` is pulled out as
    a factor ``(-1)**n``: ``exp(n*pi*I + r) == (-1)**n * exp(r)``.  This
    extends the vendored rule, which only accepts arguments that are a
    single multiple of ``pi*I``, to sums such as ``x + 2*pi*I*n``.

``log`` rules (SymPy's ``log`` is the principal branch, imaginary part in
``(-pi, pi]``):

L1  ``log(x) -> zoo`` when ``x`` is zero.
L2  ``log(exp(x)) -> x`` when ``x`` is real (then ``im(x) == 0`` lies in
    the principal strip).
L3  ``log(b**e) -> e*log(b)`` when ``b`` is positive and ``e`` is real:
    ``b**e == exp(e*log(b))`` with ``e*log(b)`` real.
L4  ``log(b**e) -> e*log(Abs(b))`` when ``b`` is real and ``e`` is an even
    integer: then ``b**e == Abs(b)**e`` and L3 applies to ``Abs(b)``
    (``b == 0`` gives ``zoo`` on both sides).
L5  ``log(p*z) -> log(p) + log(z)`` for provably positive factors ``p`` of
    a product, fired only when at least one such factor is not a number:
    ``log(p*z) == log(p) + log(z)`` for ``p > 0`` because multiplying by a
    positive real leaves ``arg`` unchanged.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Add, Basic, Mul, Pow, S
from sympy.core.numbers import I, pi
from sympy.functions.elementary.complexes import Abs
from sympy.functions.elementary.exponential import exp, log

from .._upstream import handlers_dict
from ._common import Assumptions, holds, positive_factors, term_coefficient, zero_argument


def _integer_pi_i_multiples(arg: Basic, assumptions: Assumptions,
                            ) -> tuple[Basic, Basic] | None:
    """Rule E2: return ``(n, rest)`` with ``arg == n*pi*I + rest``."""
    integers: list[Basic] = []
    rest: list[Basic] = []
    for term in Add.make_args(arg):
        coefficient = term_coefficient(term, pi * I)
        if coefficient is None:
            rest.append(term)
            continue
        for part in Add.make_args(coefficient):
            if holds(Q.integer(part), assumptions):
                integers.append(part)
            else:
                rest.append(part * pi * I)
    if not integers:
        return None
    return Add(*integers), Add(*rest)


def refine_exp(expr: Basic, assumptions: Assumptions) -> Basic | None:
    at_zero = zero_argument(expr, assumptions)                          # E1
    if at_zero is not None:
        return at_zero
    split = _integer_pi_i_multiples(expr.args[0], assumptions)         # E2
    if split is None:
        return None
    n, rest = split
    return S.NegativeOne**n * exp(rest)


def _refine_log_power(power: Basic, assumptions: Assumptions) -> Basic | None:
    """Rules L3 and L4."""
    b, e = power.base, power.exp
    if holds(Q.positive(b), assumptions) and holds(Q.real(e), assumptions):
        return e * log(b)
    if holds(Q.real(b), assumptions) and holds(Q.even(e), assumptions):
        return e * log(Abs(b))
    return None


def refine_log(expr: Basic, assumptions: Assumptions) -> Basic | None:
    at_zero = zero_argument(expr, assumptions)                          # L1
    if at_zero is not None:
        return at_zero
    x = expr.args[0]
    if isinstance(x, exp) and holds(Q.real(x.args[0]), assumptions):    # L2
        return x.args[0]
    if isinstance(x, Pow):                                              # L3, L4
        return _refine_log_power(x, assumptions)
    if isinstance(x, Mul):                                              # L5
        positives, rest = positive_factors(x, assumptions)
        if any(not p.is_number for p in positives):
            return Add(*[log(p) for p in positives]) + (log(Mul(*rest)) if rest else S.Zero)
    return None


handlers_dict['exp'] = refine_exp
handlers_dict['log'] = refine_log
