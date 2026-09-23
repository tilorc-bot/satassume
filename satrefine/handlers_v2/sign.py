"""Handler for ``sign``.

Rules (SymPy's ``sign(z) == z/Abs(z)`` for nonzero ``z``, ``sign(0) == 0``):

S1  ``sign(x) -> 0`` when ``x`` is zero.
S2  ``sign(x) -> 1`` when ``x`` is positive.
S3  ``sign(x) -> -1`` when ``x`` is negative.
S4  ``sign(x) -> I`` (``-I``) when ``x`` is imaginary with positive
    (negative) imaginary part.
S5  ``sign(p*z) -> sign(z)`` for provably positive factors ``p``.

Unlike the vendored handler, the real/imaginary gates are asked *with* the
assumptions, so ``refine(sign(x), Q.positive(x))`` works for a plain symbol.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Mul, S
from sympy.functions.elementary.complexes import sign

from .._upstream import handlers_dict
from ._common import Assumptions, holds, positive_factors
from .arg import imaginary_axis_sign


def refine_sign(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.zero(x), assumptions):                                   # S1
        return S.Zero
    if holds(Q.positive(x), assumptions):                               # S2
        return S.One
    if holds(Q.negative(x), assumptions):                               # S3
        return S.NegativeOne
    axis = imaginary_axis_sign(x, assumptions)                          # S4
    if axis is True:
        return S.ImaginaryUnit
    if axis is False:
        return -S.ImaginaryUnit
    if isinstance(x, Mul):                                              # S5
        positives, rest = positive_factors(x, assumptions)
        if positives and rest:
            return sign(Mul(*rest))
    return None


handlers_dict['sign'] = refine_sign
