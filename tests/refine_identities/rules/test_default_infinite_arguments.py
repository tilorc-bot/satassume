"""Fixed in phase 3 (ri/fixes).  The needs test said: ``factorial``, ``Max`` and ``Min`` of an argument known to be ``oo`` or ``-oo``.  Owner: handlers_identities (combinatorial, minmax_deltas).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
v3 declines these too.  ``Max``/``Min`` take extended-real arguments, so
``Max(x, y) = x`` when ``x`` is ``oo`` and ``= y`` when ``x`` is ``-oo``.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Max, Min, Q, S, factorial
from sympy.abc import n, x, y

from satrefine import refine

CASES = [
    (factorial(n), Q.positive_infinite(n), S.Infinity),
    (Max(x, y), Q.positive_infinite(x), x),
    (Max(x, y), Q.positive_infinite(y), y),
    (Max(x, y), Q.negative_infinite(x), y),
    (Max(x, y), Q.negative_infinite(y), x),
    (Min(x, y), Q.negative_infinite(x), x),
    (Min(x, y), Q.negative_infinite(y), y),
    (Min(x, y), Q.positive_infinite(x), y),
    (Min(x, y), Q.positive_infinite(y), x),
]


@pytest.mark.parametrize("expr, assumptions, expected", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_infinite_argument(expr, assumptions, expected):
    assert refine(expr, assumptions) == expected
