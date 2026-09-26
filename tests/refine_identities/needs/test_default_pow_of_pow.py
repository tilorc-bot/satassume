"""Needs: powers of powers: ``(x**y)**z`` for even ``y`` (``sqrt(1/x)`` for positive ``x`` is met since phase 3: row "default: pow of pow, positive base" of tests/refine_identities/regressions.py).  Owner: handlers_identities (power_exp_log).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``sqrt(1/x) -> 1/sqrt(x)`` is in SymPy's ``test_pow1``; ``(x**y)**z ->
Abs(x)**(y*z)`` (real ``x``, even ``y``) is ``handlers``' nested-power rule
(v3 declines it too).
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets the first);
the original test is a strict xfail under ``handlers_identities`` that points
here.

Left open in phase 3 (ri/fixes): the rule ``(b**a)**e -> Abs(b)**(a*e)`` for real
``b`` and even ``a`` is exact except at ``b = 0`` with ``a < 0`` and ``e = oo``, where
SymPy evaluates the left side ``zoo**oo`` to ``0`` and the right side ``0**(-oo)`` to
``zoo``.  So the row keeps its guard ``Q.positive(a) | ~Q.zero(b)``; firing here needs
one of ``x != 0``, ``y > 0`` or a finite ``z`` (or SymPy's ``zoo**oo`` changed).
"""
from __future__ import annotations

import pytest
from sympy import Abs, Q
from sympy.abc import x, y, z

from satrefine import refine


def test_power_of_even_power_of_real():
    assert refine((x**y)**z, Q.real(x) & Q.even(y)) == Abs(x)**(y*z)
