"""Checker finding (engine): ``refine`` raises ``RefineLoopError`` on
``atan2`` of a power of a nonpositive base.

``atan2(y, x)`` is one identity row whose right side is a ``Piecewise`` by
the signs of ``x`` and ``y``; the simple layer refines every branch under
its condition.  With ``x = n**y + 1`` (or ``n**y`` in live mode) each branch
refines ``n**y`` through the ``Pow`` fact (``exp(y*log(n))``), which splits
``log(n)`` by the sign of ``n`` and folds back, and the handler firings of
one top-level call pass ``MAX_FIRINGS`` (500) although no rewrite repeats:
the last firings are ``arg(n) -> pi`` and ``arg(-n) -> 0`` under ever longer
assumptions.  The differential fuzz shows it as a crash (seeds 3 and 7,
live mode); v3 leaves the input unchanged.  A refusal is the right answer
here: ``y/x`` has no known sign.
"""
from __future__ import annotations

from sympy import Q, S, atan2, symbols

from satrefine import refine
from satrefine.handlers_identities import _dispatch

y, n = symbols('y n')


def test_atan2_of_shifted_power_does_not_exhaust_the_firing_cap():
    expr = atan2(y, n**y + 1)
    assert refine(expr, Q.negative(y) & Q.nonpositive(n)) == expr


def test_atan2_of_power_does_not_exhaust_the_firing_cap_live():
    expr = atan2(y, n**y)
    with _dispatch.live():
        assert refine(expr, Q.negative(y) & Q.nonpositive(n)) == expr


def test_atan2_of_self_power_does_not_exhaust_the_firing_cap_live():
    """Differential seed 3 in live mode on the phase-2 baseline (also before
    the merge of ``main``): the same crash with ``x**x`` as the second
    argument."""
    x, z = symbols('x z')
    expr = atan2(z**(S(1)/2), x**x)
    with _dispatch.live():
        assert refine(expr, Q.even(z) & Q.integer(x) & Q.negative(z)) == expr
