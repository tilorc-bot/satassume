"""Needs: powers of powers: ``sqrt(1/x)`` for positive ``x``, ``(x**y)**z`` for even ``y``.  Owner: handlers_identities (power_exp_log).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``sqrt(1/x) -> 1/sqrt(x)`` is in SymPy's ``test_pow1``; ``(x**y)**z ->
Abs(x)**(y*z)`` (real ``x``, even ``y``) is ``handlers``' nested-power rule
(v3 declines it too).
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets the first);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Abs, Q, sqrt
from sympy.abc import x, y, z

from satrefine import refine


def test_sqrt_of_reciprocal_of_positive():
    assert refine(sqrt(1/x), Q.positive(x)) == 1/sqrt(x)


def test_power_of_even_power_of_real():
    assert refine((x**y)**z, Q.real(x) & Q.even(y)) == Abs(x)**(y*z)
