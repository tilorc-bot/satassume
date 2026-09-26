"""The inverse trigonometric and hyperbolic functions as tables.

Rows: 11 facts, 2 rules, 1 shared zero row; ``handlers_v3/inverse.py`` is
610 lines.

Every fact undoes a forward function up to the branch bookkeeping of the
inverse, written out with the wraps of :mod:`._wraps`: ``asin(sin t)`` is
the reflection of ``t`` onto ``[-pi/2, pi/2]``, ``acos(cos t)`` onto
``[0, pi]``, ``atan(tan t)`` the sawtooth of period ``pi``; the cofunction
forms follow by ``cos t = sin(pi/2 - t)`` and ``cot t = tan(pi/2 - t)``.
Under bounds on ``t`` stated as relations (``Q.ge(t, -pi/2) & Q.le(t,
pi/2)``, ``Q.positive(t) & Q.lt(t, pi)``, numeric intervals, ...) the
``floor`` inside the wrap collapses (the simple layer's floor of a bounded
quantity), and every interval row of v3 is a specialization; a closed
interval whose endpoint sits on the jump of the floor is the engine's
endpoint split (both floor values give the same result there).  The
``atan`` facts hold off the poles of ``tan`` and ``cot`` only (``atan(zoo)``
is not the wrap's value), so their domains exclude ``t/pi + 1/2`` and
``t/pi`` being integers, which stated bounds refute on an open interval
and not on a closed one: ``atan(tan t)`` fires on ``(-pi/2, pi/2)`` and
not on ``[-pi/2, pi/2)``.

The hyperbolic inverses wrap in the imaginary direction (``asinh(sinh z)``
reflects ``im z`` onto ``[-pi/2, pi/2]``, ``atanh(tanh z)`` is the sawtooth
of ``im z`` with period ``pi``), which is why they collapse under
``Q.real`` alone: ``im z`` is zero and ``floor(1/2)`` is ``0``.  ``acosh
(cosh t)`` and ``asech(sech t)`` are ``Abs(t)`` for real ``t`` (rules; the
``Abs`` then refines by sign).  ``atan2(y, x)`` is one row whose right side
is the sign table as a ``Piecewise``; SymPy's own ``Piecewise`` refinement
decides its conditions and the row fires when one branch is selected.

Where the facts fire and v3 does not (each exact): an interval spanning
two of v3's branches, ``acos(cos t)`` on ``[-pi/2, pi/2]`` is ``Abs(t)``
and ``asin(cos t)`` on ``[pi, 2*pi]`` is ``t - 3*pi/2``; and the
hyperbolic inverses under a one-sided bound (``Q.ge(t, 0)``), which
proves only extended realness: ``asinh``, ``atanh``, ``acoth``, ``acosh``
and ``asech`` of their functions are stated over the extended reals, since
they hold at ``+-oo`` (``acoth(coth(oo)) = acoth(1) = oo``, ``asech(sech(oo))
= asech(0) = oo``); ``acsch`` is not (``acsch(csch(oo)) = acsch(0) = zoo``).

Not covered (and why): bounds derived rather than stated (``Q.ge(t, y) &
Q.ge(y, 0)``: SymPy's relation ``ask`` would have to be consulted for
every candidate bound, which v3 does and this table does not), and
``acoth(coth(x))`` under ``Q.real(x)`` alone (``coth(0)`` is ``zoo``; v3
also declines).
Checked (adversarial pass, 2026-09-24): every fact at exact points on the
lines ``im z = k*pi/2`` and at real points, every interval row on 11
intervals x 4 open/closed combinations with the endpoints themselves as
sample points (multiples of ``pi/4``), one-sided bounds, spans of two
branches, shifted and scaled arguments, bounds on another symbol, and the
live and generated tables through ``python -m satrefine.tools.refine_differential`` (seeds
2, 3, 7).  Found: the four hyperbolic facts were stated with domain
``true`` (``~Q.zero`` for acoth/acsch) but fail on the lines ``im z = (k +
1/2)*pi`` for one sign of ``re z`` (SymPy's value on the branch cut:
``atanh(tanh(-1 - I*pi/2)) = -1 + I*pi/2``), reached through bounds on
``im z`` (``atanh(tanh(x + I*y))`` under ``Q.ge(y, -pi/2) & Q.lt(y, pi/2)``
gave ``x + I*y``); their domains now exclude the lines
(``_OFF_CUT_LINES``).  The real-argument facts, the endpoint split and
the ``atan`` pole exclusions held everywhere tried.
"""
from __future__ import annotations

from sympy import (Abs, I, Interval, Piecewise, Q, S, acos, acosh, acot, acoth, acsch, asech, asin, asinh, atan,
                   atan2, atanh, cos, cosh, cot, coth, csch, floor, im, nan, pi, sech, sign, sin, sinh, symbols, tan,
                   tanh, true)

from ._tables import ZERO, Family, Identities, Row, Rules, node_measure
from ._wraps import reflect_full, reflect_half, sawtooth

t, z, x, y = symbols('t z x y')


def _reflect_half_imag(z):
    """``z`` with ``im z`` reflected onto ``[-pi/2, pi/2]``: ``asinh(sinh z)``."""
    k = floor(im(z)/pi + S.Half)
    return (-1)**k*(z - I*pi*k)


def _sawtooth_imag(z):
    """``z`` with ``im z`` wrapped onto ``[-pi/2, pi/2)``: ``atanh(tanh z)``."""
    return z - I*pi*floor(im(z)/pi + S.Half)


_OFF_CUT_LINES = Q.extended_real(z) | ~Q.integer(im(z)/pi + S.Half)
"""``z`` off the lines ``im z = (k + 1/2)*pi`` (an extended real ``z`` is, and stated bounds
on ``im z`` that exclude the lines refute the integer).  Extended: ``asinh``, ``atanh`` and
``acoth`` of their functions hold at ``+-oo`` (``asinh(sinh(oo)) = oo``, ``atanh(tanh(oo)) =
atanh(1) = oo``, ``acoth(coth(-oo)) = acoth(-1) = -oo``), so a one-sided bound, which proves
only ``Q.extended_real``, fires them (issue #10, B1-B7)."""

FACTS: list[Row] = [   # (lhs, rhs, domain)
    (asin(sin(t)), reflect_half(t),            Q.real(t)),   # asin undoes sin up to a reflection
    (asin(cos(t)), reflect_half(pi/2 - t),     Q.real(t)),   # cos t = sin(pi/2 - t)
    (acos(cos(t)), reflect_full(t),            Q.real(t)),   # acos undoes cos up to a reflection
    (acos(sin(t)), reflect_full(pi/2 - t),     Q.real(t)),   # sin t = cos(pi/2 - t)
    (atan(tan(t)), sawtooth(t, pi),            Q.real(t) & ~Q.integer(t/pi + S.Half)),   # atan undoes tan up to a period, off the poles
    (atan(cot(t)), sawtooth(pi/2 - t, pi),     Q.real(t) & ~Q.integer(t/pi)),            # cot t = tan(pi/2 - t), off the poles
    # The hyperbolic inverses hold off the lines im z = (k + 1/2)*pi, where the forward
    # function lands on the inverse's branch cut and the result depends on the sign of
    # re z (asinh(sinh(1 - I*pi/2)) = -1 - I*pi/2, atanh(tanh(-1 - I*pi/2)) = -1 + I*pi/2).
    (asinh(sinh(z)), _reflect_half_imag(z),    _OFF_CUT_LINES),                # asinh undoes sinh up to an imaginary reflection
    (atanh(tanh(z)), _sawtooth_imag(z),        _OFF_CUT_LINES),                # atanh undoes tanh up to an imaginary period
    (acoth(coth(z)), _sawtooth_imag(z),        ~Q.zero(z) & _OFF_CUT_LINES),   # acoth undoes coth likewise (coth(0) is zoo)
    (acsch(csch(z)), _reflect_half_imag(z),    ~Q.zero(z) & (Q.real(z) | Q.finite(z) & ~Q.integer(im(z)/pi + S.Half))),   # acsch undoes csch likewise
    # (csch(+-oo) = 0 and acsch(0) = zoo: finite z only, so Q.real and not the extended lines;
    # the other three hold at +-oo.  A real z is finite, but im(z) = 0 does not make z real:
    # im(Abs(w)) is 0 for an infinite w, issue #10 B10 and B6)
    (atan2(y, x), Piecewise((atan(y/x), Q.positive(x) & Q.real(y)),          # atan2 by the signs of x and y
                            (atan(y/x) + pi, Q.negative(x) & Q.nonnegative(y)),
                            (atan(y/x) - pi, Q.negative(x) & Q.negative(y)),
                            (sign(y)*pi/2, Q.zero(x) & Q.nonzero(y)),
                            (nan, Q.zero(x) & Q.zero(y)),
                            (atan2(y, x), true)), true),
]

RULES: list[Row] = [   # (lhs, rhs, hypothesis)
    (acosh(cosh(t)), Abs(t), Q.extended_real(t)),   # acosh undoes cosh up to sign, extended real t (acosh(cosh(+-oo)) = oo)
    (asech(sech(t)), Abs(t), Q.extended_real(t)),   # asech undoes sech up to sign, extended real t (asech(0) = oo)
]

RANGES: list = [   # (head(y), range, condition): read by the floor of a bounded quantity (_simple)
    (atan(y), Interval.open(-pi/2, pi/2),  Q.real(y)),
    (acot(y), Interval.Lopen(-pi/2, pi/2), Q.real(y)),
    (asin(y), Interval(-pi/2, pi/2),       Q.real(asin(y))),
    (acos(y), Interval(0, pi),             Q.real(acos(y))),
]

_rules = Rules([ZERO] + RULES)


def _identity(head, opaque=(floor, im)):
    rows = [row for row in FACTS if row[0].func is head]
    return Identities(rows, measure=node_measure((head,)), opaque=opaque)


SPEC = Family({**{head.__name__: (_rules, _identity(head))
                  for head in (asin, acos, atan, asinh, atanh, acoth, acsch)},
               'acosh': _rules, 'asech': _rules,
               'atan2': _identity(atan2, opaque=(floor, im, Piecewise))},
              facts=FACTS, rules=[ZERO] + RULES, ranges=RANGES)
