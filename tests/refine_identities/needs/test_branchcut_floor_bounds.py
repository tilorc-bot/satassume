"""Needs (branch-cut author): ``floor`` of a symbol bounded by relations.

The inverse-trigonometric facts (``asin(sin(t)) = reflect_half(t)``, ...)
and ``arg(exp(I*t))`` reduce to ``floor(t/pi + 1/2)``-type terms with ``t``
a plain symbol whose bounds are stated as relations in the assumptions.
The simple layer collapses ``floor`` of a bounded *head*; this asks for
the same with bounds taken from ``Q.ge``/``Q.le``/``Q.gt``/``Q.lt`` on the
symbol (and from sign facts, ``Q.nonnegative(t)`` giving ``t >= 0``).
With it, every interval case of ``handlers_v3/inverse.py`` derives.
"""
from __future__ import annotations

import pytest
from sympy import Q, S, floor, pi, symbols

from satrefine import refine

t = symbols('t')


@pytest.mark.xfail(reason="needs: floor of a symbol bounded by relations", strict=True)
def test_closed_interval():
    assert refine(floor(t/pi + S.Half), Q.ge(t, -pi/2) & Q.le(t, pi/2)) == 0


@pytest.mark.xfail(reason="needs: floor of a symbol bounded by relations", strict=True)
def test_shifted_interval_and_open_bounds():
    assert refine(floor(t/pi + S.Half), Q.ge(t, pi/2) & Q.le(t, 3*pi/2)) == 1
    assert refine(floor(t/pi + S.Half), Q.gt(t, -pi/2) & Q.lt(t, pi/2)) == 0
    assert refine(floor(t/(2*pi) + S.Half), Q.positive(t + pi) & Q.nonpositive(t - pi) & Q.real(t)) == 0
