"""Handler for ``Pow``.

Rules (``b**e`` is the expression; every rule needs its precondition to be
*proved* by ``ask``):

P1  ``b**e -> 1`` when ``e`` is zero.  SymPy defines ``0**0 == 1`` and
    ``zoo**0 == 1``, so this agrees with evaluation everywhere.
P2  ``b**e -> 0`` when ``b`` is zero and ``e`` is positive.
P3  ``Abs(x)**e -> x**e`` when ``x`` is real and ``e`` is an even integer
    (``|x|**(2m) == x**(2m)`` for real ``x``; false for complex ``x``).
P4  ``b**e`` with ``b`` a *negative number*: ``-> Abs(b)**e`` for even
    integer ``e`` and ``-> sign(b)*Abs(b)**e`` for odd integer ``e``.
P5  Nested powers ``(x**a)**e``:
      * ``-> x**(a*e)`` when ``x`` is positive and ``a`` is real, or ``x``
        is nonnegative and ``a`` is positive (for ``x > 0``, ``log(x**a) ==
        a*log(x)`` exactly when ``a`` is real);
      * ``-> Abs(x)**(a*e)`` when ``x`` is real and ``a`` is an even
        integer (then ``x**a == Abs(x)**a`` is a nonnegative real and the
        previous item applies).
    Nothing is done for ``(x**3)**(1/3)`` with merely real ``x``: it is not
    ``x`` for negative ``x``.  This replaces the vendored rewrite
    ``(x**a)**b -> Abs(x)**(a*b)`` which only checked ``x**a`` to be real
    and is wrong (``sqrt(x**2)`` for ``x = I``).
P6  ``(p*z)**e -> p**e * z**e`` for provably positive factors ``p`` of a
    product base (``log(p*z) == log(p) + log(z)`` for ``p > 0``).
P7  ``sign(x)**e`` with ``x`` real and nonzero: ``-> 1`` for even integer
    ``e`` and ``-> sign(x)`` for odd integer ``e``.
P8  ``Determinant(X)**e -> 1`` for orthogonal ``X`` and even integer ``e``:
    the determinant is ``+1`` or ``-1``.  (It is *not* simplified to 1 on
    its own; unitary determinants are only known to lie on the unit circle
    so they are left alone.)
P9  Powers of ``-1`` with an ``Add`` exponent.  Since ``(-1)**z ==
    exp(I*pi*z)`` for every complex ``z``, ``(-1)**(a + b) == (-1)**a *
    (-1)**b`` holds unconditionally, and so every provably even term can be
    dropped, every pair of odd terms can be dropped, a single odd term
    becomes ``1`` and the rational constant is reduced modulo 2.  A
    remaining exponent ``(m + (-1)**n)/2`` with integer ``n`` becomes
    ``(-1)**(n + (m + 1)/2)`` (and the ``(m + 1)/2`` part is reduced by
    parity when known).  The same algorithm as SymPy's, kept because the
    trigonometric handlers rely on its normal form.

The ``(-1)**e`` normaliser is exported as :func:`minus_one_power` for the
trigonometric and hyperbolic handlers.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Add, Basic, Mul, Pow, S
from sympy.functions.elementary.complexes import Abs, sign
from sympy.matrices.expressions.determinant import Determinant

from .._upstream import handlers_dict
from ._common import Assumptions, holds, known_parity, positive_factors


def minus_one_power(exponent: Basic, assumptions: Assumptions) -> Basic:
    """``(-1)**exponent`` in the normal form of rule P9 (or P4)."""
    power = S.NegativeOne**exponent
    if not (isinstance(power, Pow) and power.base is S.NegativeOne):
        return power
    refined = refine_Pow(power, assumptions)
    return power if refined is None else refined


def _reduce_minus_one_exponent(exponent: Basic, assumptions: Assumptions) -> Basic:
    """Rule P9 on the exponent of ``(-1)**exponent``; returns the exponent."""
    coefficient, terms = exponent.as_coeff_add()
    kept: list[Basic] = []
    odd_count = 0
    for term in terms:
        parity = known_parity(term, assumptions)
        if parity is True:
            continue
        if parity is False:
            odd_count += 1
            continue
        kept.append(term)
    new_coefficient = (coefficient + odd_count) % 2
    return Add(new_coefficient, *kept)


def _continue_minus_one(exponent: Basic, assumptions: Assumptions) -> Basic | None:
    """The ``(-1)**((m + (-1)**n)/2)`` continuation of rule P9."""
    doubled = 2 * exponent
    if holds(Q.even(doubled), assumptions) and doubled.could_extract_minus_sign():
        # (-1)**(-m) == (-1)**m for an integer m.
        doubled = -doubled
    if not doubled.is_Add:
        return None
    rest, power = doubled.as_two_terms()
    if not (isinstance(power, Pow) and power.base is S.NegativeOne):
        return None
    if not holds(Q.integer(power.exp), assumptions):
        return None
    half = (rest + 1) / 2
    parity = known_parity(half, assumptions)
    if parity is True:
        return S.NegativeOne**power.exp
    if parity is False:
        return S.NegativeOne**(power.exp + 1)
    return S.NegativeOne**(power.exp + half)


def _refine_minus_one(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule P9 for ``expr == (-1)**Add``."""
    exponent = _reduce_minus_one_exponent(expr.exp, assumptions)
    reduced = S.NegativeOne**exponent
    continued = _continue_minus_one(exponent, assumptions)
    if continued is not None:
        return continued
    if reduced != expr:
        return reduced
    return None


def _refine_nested(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule P5 for ``expr == (x**a)**e``."""
    inner, e = expr.base, expr.exp
    x, a = inner.base, inner.exp
    if holds(Q.positive(x), assumptions) and holds(Q.real(a), assumptions):
        return x**(a * e)
    if holds(Q.nonnegative(x), assumptions) and holds(Q.positive(a), assumptions):
        return x**(a * e)
    if holds(Q.real(x), assumptions) and holds(Q.even(a), assumptions):
        return Abs(x)**(a * e)
    return None


def _refine_unit_base(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rules P7 and P8 (bases whose value is ``+1``/``-1``/``0``)."""
    base, e = expr.base, expr.exp
    if isinstance(base, sign):
        x = base.args[0]
        if holds(Q.real(x), assumptions) and holds(Q.nonzero(x), assumptions):
            parity = known_parity(e, assumptions)
            if parity is True:
                return S.One
            if parity is False:
                return base
    if isinstance(base, Determinant):
        if holds(Q.orthogonal(base.arg), assumptions) and holds(Q.even(e), assumptions):
            return S.One
    return None


def refine_Pow(expr: Basic, assumptions: Assumptions) -> Basic | None:
    base, e = expr.base, expr.exp

    if holds(Q.zero(e), assumptions):                                   # P1
        return S.One
    if holds(Q.zero(base), assumptions) and holds(Q.positive(e), assumptions):  # P2
        return S.Zero

    if isinstance(base, Abs):                                            # P3
        x = base.args[0]
        if holds(Q.real(x), assumptions) and holds(Q.even(e), assumptions):
            return x**e

    if base.is_number and base.is_negative:                              # P4
        parity = known_parity(e, assumptions)
        if parity is True:
            return Abs(base)**e
        if parity is False:
            return sign(base) * Abs(base)**e

    if isinstance(base, Pow):                                            # P5
        nested = _refine_nested(expr, assumptions)
        if nested is not None:
            return nested

    if isinstance(base, Mul):                                            # P6
        positives, rest = positive_factors(base, assumptions)
        if any(not p.is_number for p in positives):
            return Mul(*[p**e for p in positives]) * Mul(*rest)**e

    unit = _refine_unit_base(expr, assumptions)                          # P7, P8
    if unit is not None:
        return unit

    if base is S.NegativeOne and e.is_Add:                               # P9
        return _refine_minus_one(expr, assumptions)
    return None


handlers_dict['Pow'] = refine_Pow
