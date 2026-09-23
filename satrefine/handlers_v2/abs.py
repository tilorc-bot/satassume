"""Handler for ``Abs``.

Rules (``Abs(x)`` is the expression):

A1  ``Abs(x) -> 0`` when ``x`` is zero and ``-> x`` when ``x`` is
    nonnegative (real and ``>= 0``).
A2  ``Abs(x) -> -x`` when ``x`` is negative.
A3  ``Abs(a*b*...) -> Abs`` of each factor, refined separately, with the
    factors that stay under ``Abs`` regrouped into one ``Abs``:
    ``|ab| == |a||b|`` holds for all complex numbers.
A4  ``Abs(b**e)``:
      * ``-> b**e`` when ``b`` is positive and ``e`` is real
        (``b**e > 0``);
      * ``-> Abs(b)**e`` when ``e`` is an integer, or when ``b`` and ``e``
        are both real (``|b**e| == |b|**e`` there; for complex ``e`` the
        modulus also depends on ``arg(b)``).
    ``Abs(b)**e`` then simplifies further through the ``Pow`` rules
    (``Abs(x)**2 -> x**2`` for real ``x``).
A5  ``Abs(sign(x)) -> 1`` when ``x`` is provably nonzero (``|sign(z)| ==
    1`` for every nonzero complex ``z``).
A6  ``Abs(Determinant(X)) -> 1`` when ``X`` is unitary (orthogonal matrices
    are unitary in SymPy's fact system).  The determinant itself is only
    known up to a unit-modulus factor and is left alone.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Mul, Pow
from sympy.core.singleton import S
from sympy.functions.elementary.complexes import Abs, sign
from sympy.matrices.expressions.determinant import Determinant

from .. import _upstream
from .._upstream import handlers_dict
from ._common import Assumptions, holds, is_nonzero


def _refine_abs_product(product: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule A3."""
    outside: list[Basic] = []
    inside: list[Basic] = []
    for factor in product.args:
        refined = _upstream.refine(Abs(factor), assumptions)
        if isinstance(refined, Abs):
            inside.append(refined.args[0])
        else:
            outside.append(refined)
    if not outside:
        return None
    return Mul(*outside) * Abs(Mul(*inside))


def _refine_abs_power(power: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule A4."""
    b, e = power.base, power.exp
    e_real = holds(Q.real(e), assumptions)
    if e_real and holds(Q.positive(b), assumptions):
        return b**e
    if holds(Q.integer(e), assumptions) or (e_real and holds(Q.real(b), assumptions)):
        return Abs(b)**e
    return None


def refine_Abs(expr: Basic, assumptions: Assumptions) -> Basic | None:
    arg = expr.args[0]
    if holds(Q.zero(arg), assumptions):                                 # A1
        return S.Zero
    if holds(Q.nonnegative(arg), assumptions):
        return arg
    if holds(Q.negative(arg), assumptions):                             # A2
        return -arg
    if isinstance(arg, Mul):                                            # A3
        return _refine_abs_product(arg, assumptions)
    if isinstance(arg, Pow):                                            # A4
        return _refine_abs_power(arg, assumptions)
    if isinstance(arg, sign) and is_nonzero(arg.args[0], assumptions):  # A5
        return S.One
    if isinstance(arg, Determinant) and holds(Q.unitary(arg.arg), assumptions):  # A6
        return S.One
    return None


handlers_dict['Abs'] = refine_Abs
