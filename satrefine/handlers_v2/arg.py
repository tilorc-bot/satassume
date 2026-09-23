"""Handler for the complex argument ``arg``.

Rules (SymPy's ``arg`` takes values in ``(-pi, pi]``):

G1  ``arg(x) -> nan`` when ``x`` is zero (``arg(0)`` is ``nan`` in SymPy).
G2  ``arg(x) -> 0`` when ``x`` is positive.
G3  ``arg(x) -> pi`` when ``x`` is negative.
G4  ``arg(x) -> pi/2`` (``-pi/2``) when ``x`` is imaginary with a positive
    (negative) imaginary part.  The imaginary part is taken from
    ``x.as_real_imag()`` so a user can state ``Q.positive(im(x))``.
G5  ``arg(p*z) -> arg(z)`` for provably positive factors ``p``: scaling by
    a positive real does not move the argument.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Mul, S
from sympy.functions.elementary.complexes import arg as complex_arg

from .._upstream import handlers_dict
from ._common import Assumptions, holds, positive_factors


def imaginary_axis_sign(x: Basic, assumptions: Assumptions) -> bool | None:
    """For an imaginary ``x``: ``True`` if ``im(x) > 0``, ``False`` if
    ``im(x) < 0``, ``None`` when unknown or ``x`` is not imaginary."""
    if not holds(Q.imaginary(x), assumptions):
        return None
    _, imaginary_part = x.as_real_imag()
    if holds(Q.positive(imaginary_part), assumptions):
        return True
    if holds(Q.negative(imaginary_part), assumptions):
        return False
    return None


def refine_arg(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.zero(x), assumptions):                                   # G1
        return S.NaN
    if holds(Q.positive(x), assumptions):                               # G2
        return S.Zero
    if holds(Q.negative(x), assumptions):                               # G3
        return S.Pi
    axis = imaginary_axis_sign(x, assumptions)                          # G4
    if axis is True:
        return S.Pi / 2
    if axis is False:
        return -S.Pi / 2
    if isinstance(x, Mul):                                              # G5
        positives, rest = positive_factors(x, assumptions)
        if positives and rest:
            return complex_arg(Mul(*rest))
    return None


handlers_dict['arg'] = refine_arg
