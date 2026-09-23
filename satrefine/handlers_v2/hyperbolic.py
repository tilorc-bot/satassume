"""Handlers for ``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch``.

Rules:

H1  ``f(x) -> f(0)`` when ``x`` is zero.
H2  Shift by a half-integer multiple of ``pi*I`` whose parity is known
    (``x == rem + k*pi*I/2``, ``k`` a provably even or odd integer).  From
    ``sinh(r + I*t) == sinh(r)*cos(t) + I*cosh(r)*sin(t)`` and
    ``cosh(r + I*t) == cosh(r)*cos(t) + I*sinh(r)*sin(t)``:

    ========  ===============================  ====================================
    function  ``k`` even                       ``k`` odd
    ========  ===============================  ====================================
    sinh      ``(-1)**(k/2) * sinh(rem)``      ``I*(-1)**((k-1)/2) * cosh(rem)``
    cosh      ``(-1)**(k/2) * cosh(rem)``      ``I*(-1)**((k-1)/2) * sinh(rem)``
    sech      ``(-1)**(k/2) * sech(rem)``      ``-I*(-1)**((k-1)/2) * csch(rem)``
    csch      ``(-1)**(k/2) * csch(rem)``      ``-I*(-1)**((k-1)/2) * sech(rem)``
    tanh      ``tanh(rem)``                    ``coth(rem)``
    coth      ``coth(rem)``                    ``tanh(rem)``
    ========  ===============================  ====================================

    Exact identities of the complex functions; nothing is assumed about
    ``rem``.
"""
from __future__ import annotations

from sympy.core import S
from sympy.core.numbers import I, pi
from sympy.functions.elementary.hyperbolic import cosh, coth, csch, sech, sinh, tanh

from .._upstream import handlers_dict
from ._common import first_of, zero_argument
from ._shift import even_case, odd_case, shift_rule

_UNIT = pi * I

refine_sinh = first_of(zero_argument, shift_rule(_UNIT, even_case(sinh), odd_case(cosh, -1, I)))
refine_cosh = first_of(zero_argument, shift_rule(_UNIT, even_case(cosh), odd_case(sinh, -1, I)))
refine_sech = first_of(zero_argument, shift_rule(_UNIT, even_case(sech), odd_case(csch, -1, -I)))
refine_csch = first_of(zero_argument, shift_rule(_UNIT, even_case(csch), odd_case(sech, -1, -I)))
refine_tanh = first_of(zero_argument,
                       shift_rule(_UNIT, even_case(tanh, sign_power=False),
                                  odd_case(coth, None, S.One)))
refine_coth = first_of(zero_argument,
                       shift_rule(_UNIT, even_case(coth, sign_power=False),
                                  odd_case(tanh, None, S.One)))

handlers_dict['sinh'] = refine_sinh
handlers_dict['cosh'] = refine_cosh
handlers_dict['sech'] = refine_sech
handlers_dict['csch'] = refine_csch
handlers_dict['tanh'] = refine_tanh
handlers_dict['coth'] = refine_coth
