"""Assumption-driven refinement of ``Pow``, ``exp`` and ``log``.

Every rule below is an identity over the complex numbers for SymPy's
principal branches (``log`` with imaginary part in ``(-pi, pi]``,
``x**a = exp(a*log(x))``, ``(-1)**z = exp(I*pi*z)``) under the stated
precondition; nothing fires without its precondition being answered
``True`` (or, where noted, ``False``) by :func:`satrefine._upstream.ask`.

``Pow`` (registry key ``Pow``)
==============================

``E**x`` (an unevaluated ``Pow`` with base ``E``)
    Treated as ``exp(x)`` and refined with the ``exp`` rules.

``exp(a)**b -> exp(a*b)``
    when ``b`` is an integer, or when ``a`` is real (then ``log(exp(a))
    == a``).

``Abs(x)**n``
    ``n`` even:  ``x**n`` when ``x`` is real;
    ``(-1)**(n/2) * x**n`` when ``x`` is imaginary (``(I*t)**n =
    (-1)**(n/2) * t**n``).

``(x**a)**b``
    ``x**(a*b)`` when ``b`` is an integer (any ``x``, ``a``);
    ``x**(a*b)`` when ``x`` is positive and ``a`` is real, or ``x`` is
    nonnegative and ``a`` is positive (``a*log(x)`` is then real, so no
    branch wraps);
    ``a`` even and ``x`` real, provided ``a`` is positive or ``x`` is
    nonzero (``(0**a)**b`` for negative ``a`` is ``zoo**b``, which SymPy
    does not evaluate like ``0**(a*b)`` for complex ``b``): ``x**(a*b)``
    if ``x`` is nonnegative, ``(-x)**(a*b)`` if ``x`` is nonpositive, else
    ``Abs(x)**(a*b)`` (``x**a == Abs(x)**a`` and ``Abs(x) >= 0``);
    ``a`` even and ``x`` imaginary: ``Abs(x)**(a*b)`` when ``a/2`` is
    even, ``(-1)**b * Abs(x)**(a*b)`` when ``a/2`` is odd (then ``x**a ==
    -Abs(x)**a`` and ``(-r)**b == (-1)**b * r**b`` for ``r > 0``).
    In particular ``sqrt(x**2)`` gives ``Abs(x)`` (real), ``x``
    (nonnegative), ``-x`` (nonpositive) and ``I*Abs(x)`` (imaginary).
    The vendored rewrite ``(x**a)**b -> Abs(x)**(a*b)`` for every rational
    ``b`` and real ``x**a`` is *not* used: it is wrong for odd ``a``
    (``sqrt(x**3)`` at ``x = -1``) and for imaginary ``x``
    (``sqrt(x**2)`` at ``x = 2*I``).

``c**n`` for a negative finite real number ``c``
    ``Abs(c)**n`` when ``n`` is even, ``-Abs(c)**n`` when ``n`` is odd;
    so ``(-1)**n`` becomes ``1`` or ``-1``.  Zero bases are left alone
    (``0**n`` with ``n < 0`` is ``zoo``, not ``sign(0)*0**n``).

``(-1)**(sum of terms)``
    Delegated to the vendored handler: even terms are dropped, pairs of
    odd terms cancel, a single odd term becomes ``+1``, an integer
    constant is reduced mod 2, and ``(-1)**((-1)**n/2 + m/2)`` with ``n``
    integer is reduced.  All of these are exact because ``(-1)**z =
    exp(I*pi*z)`` splits over sums and is ``2``-periodic in ``z``.  When
    every symbolic term has a known parity the sum is reduced here instead,
    with the ``exp`` rules (``(-1)**(n + 1/2)`` with ``n`` even is ``I``):
    the vendored handler crashes on that case.

``exp`` (registry key ``exp``)
==============================

``exp(rest + k*pi*I)``
    Every term ``t`` of ``k`` that is an integer contributes a factor
    ``(-1)**t``, i.e. ``1`` when even, ``-1`` when odd, and a rational
    constant ``c`` in ``k`` is reduced mod 2, contributing ``1``, ``-1``,
    ``I`` or ``-I`` when ``c mod 2`` is ``0``, ``1``, ``1/2`` or ``3/2``.
    The rest stays inside ``exp``.  Exact because ``exp`` splits over
    sums and ``exp(I*pi*t) == (-1)**t`` for integer ``t``.
    ``exp(log(x))`` is already ``x`` in SymPy for every ``x``.

``log`` (registry key ``log``)
==============================

``log(exp(x)) -> x``
    when ``x`` is real (needs ``im(x)`` in ``(-pi, pi]``).

``log(x**a)``
    ``a*log(x)`` when ``x`` is positive and ``a`` real, or ``x``
    nonnegative and ``a`` positive;
    ``a*log(Abs(x))`` when ``x`` is real and ``a`` is even, provided ``a``
    or ``x`` is nonzero (``log(0**0)`` is ``log(1) = 0`` in SymPy, but
    ``0*log(Abs(0))`` is ``nan``);
    ``a*log(-x) + I*pi`` when ``x`` is negative and ``a`` is odd;
    ``a*log(Abs(x))`` (``a/2`` even) or ``a*log(Abs(x)) + I*pi`` (``a/2``
    odd) when ``x`` is imaginary and ``a`` is even;
    ``log(1/x) -> -log(x)`` when ``x`` is finite and known not to be
    negative (``ask(Q.negative(x))`` is ``False``: positive, imaginary,
    zero, ...); the identity fails exactly on the negative real axis, and
    at infinity in SymPy's arithmetic (``log(1/oo) = zoo`` but ``-log(oo)
    = -oo``).

``log(c * p1 * ... * n1 * ... * u1 * ...)``
    with ``p_i`` positive, ``n_j`` negative and ``u_k`` of unknown sign:
    ``log(p_i)`` and ``log(-n_j)`` are split off (plus ``log(c)`` for the
    positive part of the numeric coefficient); the sign ``(-1)**(number of
    negative factors, counting a negative coefficient)`` is absorbed into
    the unknown product (``log(-u1*...)``) or, when there is none,
    contributes ``I*pi`` if odd.  Exact because ``log(p*z) == log(p) +
    log(z)`` for ``p > 0``.  Fires only when at least one symbolic factor
    has a known sign, so ``log(2*x)`` is left alone.

``log(x) -> log(-x) + I*pi``
    when ``x`` is negative (fallback for any argument form).
"""
from __future__ import annotations

from typing import Any

from sympy.assumptions import Q
from sympy.core import Add, Mul, Pow, S
from sympy.core.expr import Expr
from sympy.core.numbers import I, pi
from sympy.functions.elementary.complexes import Abs
from sympy.functions.elementary.exponential import exp, log

from ...identities.compat import upstream as _upstream
from ...identities.compat.upstream import handlers_dict
from ._common import is_integer, parity, split_shift


# ---------------------------------------------------------------------------
# Pow
# ---------------------------------------------------------------------------

def _pow_of_exp(arg: Expr, b: Expr, assumptions: Any) -> Expr | None:
    """``exp(arg)**b -> exp(arg*b)`` for integer ``b`` or real ``arg``."""
    if is_integer(b, assumptions) or _upstream.ask(Q.real(arg), assumptions):
        return exp(arg * b)
    return None


def _pow_of_abs(x: Expr, n: Expr, assumptions: Any) -> Expr | None:
    """``Abs(x)**n`` for even ``n`` and real or imaginary ``x``."""
    if parity(n, assumptions) != "even":
        return None
    if _upstream.ask(Q.real(x), assumptions):
        return Pow(x, n)
    if _upstream.ask(Q.imaginary(x), assumptions):
        return Pow(S.NegativeOne, n / 2) * Pow(x, n)
    return None


def _pow_of_pow(x: Expr, a: Expr, b: Expr, assumptions: Any) -> Expr | None:
    """``(x**a)**b`` under the preconditions listed in the module docstring."""
    if is_integer(b, assumptions):
        return Pow(x, a * b)
    if _upstream.ask(Q.positive(x), assumptions) and _upstream.ask(Q.real(a), assumptions):
        return Pow(x, a * b)
    if _upstream.ask(Q.nonnegative(x), assumptions) and _upstream.ask(Q.positive(a), assumptions):
        return Pow(x, a * b)
    if parity(a, assumptions) != "even":
        return None
    if _upstream.ask(Q.real(x), assumptions):
        # 0**a with a < 0 is zoo, and zoo**b need not be 0**(a*b) in SymPy
        # for complex b: skip the zero base unless a is positive.
        if not (_upstream.ask(Q.positive(a), assumptions)
                or _upstream.ask(Q.nonzero(x), assumptions)):
            return None
        if _upstream.ask(Q.nonnegative(x), assumptions):
            return Pow(x, a * b)
        if _upstream.ask(Q.nonpositive(x), assumptions):
            return Pow(-x, a * b)
        return Pow(Abs(x), a * b)
    if _upstream.ask(Q.imaginary(x), assumptions):
        half = parity(a / 2, assumptions)
        if half == "even":
            return Pow(Abs(x), a * b)
        if half == "odd":
            return Pow(S.NegativeOne, b) * Pow(Abs(x), a * b)
    return None


def _pow_of_negative_number(c: Expr, n: Expr, assumptions: Any) -> Expr | None:
    """``c**n`` for a negative finite real number ``c`` and ``n`` of known parity."""
    p = parity(n, assumptions)
    if p == "even":
        return Pow(-c, n)
    if p == "odd":
        return -Pow(-c, n)
    return None


def refine_Pow(expr: Expr, assumptions: Any) -> Expr | None:
    """Handler for ``Pow``; see the module docstring for the rules."""
    base, exponent = expr.base, expr.exp
    if base is S.Exp1:
        refined = _refine_exp_arg(exponent, assumptions)
        return exp(exponent) if refined is None else refined
    if isinstance(base, exp):
        return _pow_of_exp(base.args[0], exponent, assumptions)
    if isinstance(base, Abs):
        return _pow_of_abs(base.args[0], exponent, assumptions)
    if isinstance(base, Pow):
        return _pow_of_pow(base.base, base.exp, exponent, assumptions)
    if (base.is_number and base.is_extended_real and base.is_finite
            and base.is_negative):
        refined = _pow_of_negative_number(base, exponent, assumptions)
        if refined is not None:
            return refined
        if base is S.NegativeOne and exponent.is_Add:
            # When every symbolic term has a known parity the sum reduces to
            # a constant; the vendored handler then rebuilds (-1)**(c mod 2),
            # which auto-evaluates to I or -I, and crashes reading its .exp.
            reduced = _refine_exp_arg(I * pi * exponent, assumptions)
            if reduced is not None and reduced.is_number:
                return reduced
            return _upstream.refine_Pow(expr, assumptions)
    return None


# ---------------------------------------------------------------------------
# exp
# ---------------------------------------------------------------------------

_QUARTER_TURNS = {S.Zero: S.One, S.One: S.NegativeOne, S.Half: I, S(3) / 2: -I}


def _refine_exp_arg(arg: Expr, assumptions: Any) -> Expr | None:
    """``exp(arg)`` with integer and rational multiples of ``pi*I`` pulled out."""
    k, rest = split_shift(arg, pi * I)
    if k is S.Zero:
        return None
    factor = S.One
    changed = False
    leftover = S.Zero
    for term in Add.make_args(k):
        if term.is_Rational:
            reduced = term % 2
            if reduced in _QUARTER_TURNS:
                factor *= _QUARTER_TURNS[reduced]
                changed = True
            else:
                if reduced != term:
                    changed = True
                leftover += reduced
        elif is_integer(term, assumptions):
            changed = True
            p = parity(term, assumptions)
            if p == "even":
                pass
            elif p == "odd":
                factor = -factor
            else:
                factor *= Pow(S.NegativeOne, term)
        else:
            leftover += term
    if not changed:
        return None
    return factor * exp(rest + pi * I * leftover)


def refine_exp(expr: Expr, assumptions: Any) -> Expr | None:
    """Handler for ``exp``; see the module docstring for the rules."""
    return _refine_exp_arg(expr.args[0], assumptions)


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

def _log_of_pow(x: Expr, a: Expr, assumptions: Any) -> Expr | None:
    """``log(x**a)`` under the preconditions listed in the module docstring."""
    if _upstream.ask(Q.positive(x), assumptions) and _upstream.ask(Q.real(a), assumptions):
        return a * log(x)
    if _upstream.ask(Q.nonnegative(x), assumptions) and _upstream.ask(Q.positive(a), assumptions):
        return a * log(x)
    p = parity(a, assumptions)
    if p == "even":
        if _upstream.ask(Q.real(x), assumptions):
            # log(0**0) is log(1) = 0 in SymPy, but 0*log(Abs(0)) is nan:
            # one of the two must be known nonzero.
            if (_upstream.ask(Q.nonzero(a), assumptions)
                    or _upstream.ask(Q.nonzero(x), assumptions)):
                return a * log(Abs(x))
            return None
        if _upstream.ask(Q.imaginary(x), assumptions):
            half = parity(a / 2, assumptions)
            if half == "even":
                return a * log(Abs(x))
            if half == "odd":
                return a * log(Abs(x)) + I * pi
    elif p == "odd":
        if _upstream.ask(Q.negative(x), assumptions):
            return a * log(-x) + I * pi
    if (a is S.NegativeOne and _upstream.ask(Q.negative(x), assumptions) is False
            and _upstream.ask(Q.finite(x), assumptions)):
        # log(1/oo) is log(0) = zoo, but -log(oo) is -oo: infinite x is out.
        return -log(x)
    return None


def _log_of_mul(arg: Expr, assumptions: Any) -> Expr | None:
    """Split ``log`` of a product over its factors of known sign."""
    coeff, rest = arg.as_coeff_Mul()
    negatives = 0
    if coeff.is_negative:
        negatives += 1
        coeff = -coeff
    terms: list[Expr] = []
    unknown: list[Expr] = []
    for factor in Mul.make_args(rest):
        if _upstream.ask(Q.positive(factor), assumptions):
            terms.append(log(factor))
        elif _upstream.ask(Q.negative(factor), assumptions):
            terms.append(log(-factor))
            negatives += 1
        else:
            unknown.append(factor)
    if not terms:
        return None
    if coeff is not S.One:
        terms.append(log(coeff))
    odd = negatives % 2 == 1
    if unknown:
        product = Mul(*unknown)
        terms.append(log(-product if odd else product))
    elif odd:
        terms.append(I * pi)
    return Add(*terms)


def refine_log(expr: Expr, assumptions: Any) -> Expr | None:
    """Handler for ``log``; see the module docstring for the rules."""
    if len(expr.args) != 1:
        return None
    arg = expr.args[0]
    refined: Expr | None = None
    if isinstance(arg, exp):
        if _upstream.ask(Q.real(arg.args[0]), assumptions):
            return arg.args[0]
        return None
    if isinstance(arg, Pow):
        refined = _log_of_pow(arg.base, arg.exp, assumptions)
    elif isinstance(arg, Mul):
        refined = _log_of_mul(arg, assumptions)
    if refined is not None:
        return refined
    if _upstream.ask(Q.negative(arg), assumptions):
        return log(-arg) + I * pi
    return None


handlers_dict['Pow'] = refine_Pow
handlers_dict['exp'] = refine_exp
handlers_dict['log'] = refine_log
