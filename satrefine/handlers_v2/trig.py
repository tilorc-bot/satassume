"""Handlers for ``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc`` and
``sinc``.

Rules common to the six trigonometric functions:

T1  ``f(x) -> f(0)`` when ``x`` is zero.
T2  Shift by a half-integer multiple of ``pi`` whose parity is known
    (``x == rem + k*pi/2``, ``k`` a provably even or odd integer; see
    :mod:`satrefine.handlers_v2._shift`):

    ========  ===============================  ================================
    function  ``k`` even                       ``k`` odd
    ========  ===============================  ================================
    sin       ``(-1)**(k/2) * sin(rem)``       ``(-1)**((k-1)/2) * cos(rem)``
    cos       ``(-1)**(k/2) * cos(rem)``       ``(-1)**((k+1)/2) * sin(rem)``
    sec       ``(-1)**(k/2) * sec(rem)``       ``(-1)**((k+1)/2) * csc(rem)``
    csc       ``(-1)**(k/2) * csc(rem)``       ``(-1)**((k-1)/2) * sec(rem)``
    tan       ``tan(rem)``                     ``-cot(rem)``
    cot       ``cot(rem)``                     ``-tan(rem)``
    ========  ===============================  ================================

    These are the exact quarter-period identities of the complex functions;
    no assumption on ``rem`` is needed.  Terms ``n*pi/2`` with ``n`` an
    integer of *unknown* parity stay in ``rem``.
T3  ``sin(x)``, ``cos(x)`` ``-> AccumBounds(-1, 1)`` when ``x`` is an
    infinite extended real (SymPy's value of ``sin(oo)``).

``sinc`` rules:

N1  ``sinc(x) -> 1`` when ``x`` is zero.
N2  ``sinc(x) -> sin(x)/x`` when ``x`` is provably nonzero (the definition
    away from the removable singularity); ``sinc(n*pi)`` with a nonzero
    integer ``n`` then becomes ``0`` through the ``sin`` rules.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.calculus.accumulationbounds import AccumBounds
from sympy.core import Basic, S
from sympy.core.numbers import pi
from sympy.functions.elementary.trigonometric import cos, cot, csc, sec, sin, tan

from .._upstream import handlers_dict
from ._common import Assumptions, first_of, holds, is_nonzero, zero_argument
from ._shift import even_case, odd_case, shift_rule


def _bounded_at_infinity(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule T3."""
    x = expr.args[0]
    if holds(Q.infinite(x), assumptions) and holds(Q.extended_real(x), assumptions):
        return AccumBounds(-1, 1)
    return None


def refine_sinc(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.zero(x), assumptions):                                   # N1
        return S.One
    if is_nonzero(x, assumptions):                                      # N2
        return sin(x) / x
    return None


refine_sin = first_of(zero_argument, _bounded_at_infinity,
                      shift_rule(pi, even_case(sin), odd_case(cos, -1)))
refine_cos = first_of(zero_argument, _bounded_at_infinity,
                      shift_rule(pi, even_case(cos), odd_case(sin, +1)))
refine_sec = first_of(zero_argument, shift_rule(pi, even_case(sec), odd_case(csc, +1)))
refine_csc = first_of(zero_argument, shift_rule(pi, even_case(csc), odd_case(sec, -1)))
refine_tan = first_of(zero_argument,
                      shift_rule(pi, even_case(tan, sign_power=False),
                                 odd_case(cot, None, S.NegativeOne)))
refine_cot = first_of(zero_argument,
                      shift_rule(pi, even_case(cot, sign_power=False),
                                 odd_case(tan, None, S.NegativeOne)))

handlers_dict['sin'] = refine_sin
handlers_dict['cos'] = refine_cos
handlers_dict['sec'] = refine_sec
handlers_dict['csc'] = refine_csc
handlers_dict['tan'] = refine_tan
handlers_dict['cot'] = refine_cot
handlers_dict['sinc'] = refine_sinc
