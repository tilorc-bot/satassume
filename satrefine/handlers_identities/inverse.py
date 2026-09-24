"""The inverse trigonometric and hyperbolic functions as tables.

Rows: 11 facts, 2 rules, 1 shared zero row; ``handlers_v3/inverse.py`` is
610 lines.

Every fact undoes a forward function up to the branch bookkeeping of the
inverse, written out with the wraps of :mod:`._wraps`: ``asin(sin t)`` is
the reflection of ``t`` onto ``[-pi/2, pi/2]``, ``acos(cos t)`` onto
``[0, pi]``, ``atan(tan t)`` the sawtooth of period ``pi``; the cofunction
forms follow by ``cos t = sin(pi/2 - t)`` and ``cot t = tan(pi/2 - t)``.
The hyperbolic inverses wrap in the imaginary direction (``asinh(sinh z)``
reflects ``im z`` onto ``[-pi/2, pi/2]``, ``atanh(tanh z)`` is the sawtooth
of ``im z`` with period ``pi``), which is why they collapse under
``Q.real`` alone: ``im z`` is zero and ``floor(1/2)`` is ``0``.  ``acosh
(cosh t)`` and ``asech(sech t)`` are ``Abs(t)`` for real ``t`` (rules; the
``Abs`` then refines by sign).  ``atan2(y, x)`` is one row whose right side
is the sign table as a ``Piecewise``; the simple ``Piecewise`` rule decides
its conditions.

The real-direction wraps collapse only under bounds on ``t`` stated as
relations (``Q.ge(t, -pi/2) & Q.le(t, pi/2)``); that is ``floor`` of a
symbol bounded by relations, filed under ``needs``, so the trigonometric
inverse rows do not fire yet.  ``atan2`` and the hyperbolic rows do.
"""
from __future__ import annotations

from sympy import (Abs, I, Piecewise, Q, S, acos, acosh, acot, acoth, acsch, asech, asin, asinh, atan, atan2,
                   atanh, cos, cosh, cot, coth, csch, floor, im, nan, pi, sech, sign, sin, sinh, symbols,
                   tan, tanh, true, atan as _atan)

from .._upstream import handlers_dict
from ._engine import Row, identity_handler, rule_handler
from ._tables import ZERO, chain, node_measure
from ._wraps import reflect_full, reflect_half, sawtooth

t, z, x, y = symbols('t z x y')


def _reflect_half_imag(z):
    """``z`` with ``im z`` reflected onto ``[-pi/2, pi/2]``: ``asinh(sinh z)``."""
    k = floor(im(z)/pi + S.Half)
    return (-1)**k*(z - I*pi*k)


def _sawtooth_imag(z):
    """``z`` with ``im z`` wrapped onto ``[-pi/2, pi/2)``: ``atanh(tanh z)``."""
    return z - I*pi*floor(im(z)/pi + S.Half)


FACTS: list[Row] = [   # (lhs, rhs, domain)
    (asin(sin(t)), reflect_half(t),            Q.real(t)),   # asin undoes sin up to a reflection
    (asin(cos(t)), reflect_half(pi/2 - t),     Q.real(t)),   # cos t = sin(pi/2 - t)
    (acos(cos(t)), reflect_full(t),            Q.real(t)),   # acos undoes cos up to a reflection
    (acos(sin(t)), reflect_full(pi/2 - t),     Q.real(t)),   # sin t = cos(pi/2 - t)
    (atan(tan(t)), sawtooth(t, pi),            Q.real(t)),   # atan undoes tan up to a period
    (atan(cot(t)), sawtooth(pi/2 - t, pi),     Q.real(t)),   # cot t = tan(pi/2 - t)
    (asinh(sinh(z)), _reflect_half_imag(z),    true),        # asinh undoes sinh up to an imaginary reflection
    (atanh(tanh(z)), _sawtooth_imag(z),        true),        # atanh undoes tanh up to an imaginary period
    (acoth(coth(z)), _sawtooth_imag(z),        ~Q.zero(z)),  # acoth undoes coth likewise (coth(0) is zoo)
    (acsch(csch(z)), _reflect_half_imag(z),    ~Q.zero(z)),  # acsch undoes csch likewise
    (atan2(y, x), Piecewise((_atan(y/x), Q.positive(x) & Q.real(y)),          # atan2 by the signs of x and y
                            (_atan(y/x) + pi, Q.negative(x) & Q.nonnegative(y)),
                            (_atan(y/x) - pi, Q.negative(x) & Q.negative(y)),
                            (sign(y)*pi/2, Q.zero(x) & Q.nonzero(y)),
                            (nan, Q.zero(x) & Q.zero(y)),
                            (atan2(y, x), true)), true),
]

RULES: list[Row] = [   # (lhs, rhs, hypothesis)
    (acosh(cosh(t)), Abs(t), Q.real(t)),   # acosh undoes cosh up to sign, real t
    (asech(sech(t)), Abs(t), Q.real(t)),   # asech undoes sech up to sign, real t
]

_rules = rule_handler([ZERO] + RULES)


def _identity(head, opaque=(floor, im)):
    rows = [row for row in FACTS if row[0].func is head]
    return identity_handler(rows, measure=node_measure((head,)), opaque=opaque)


for _key, _head in (('asin', asin), ('acos', acos), ('atan', atan), ('asinh', asinh),
                    ('atanh', atanh), ('acoth', acoth), ('acsch', acsch)):
    handlers_dict[_key] = chain(_rules, _identity(_head))
handlers_dict['acosh'] = _rules
handlers_dict['asech'] = _rules
handlers_dict['atan2'] = _identity(atan2, opaque=(floor, im, Piecewise))
