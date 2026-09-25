"""Needs: odd multiples of ``pi/2`` inside sin/cos/sec/csc give a doubled sign form.  Owner: handlers_identities (trig).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
The values are right; the form is ``-(-1)**(n/2 + 3/2)`` where SymPy, ``handlers``
and v3 give ``(-1)**((n + 1)/2)`` (one power of ``-1``, no leading minus).
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets it too);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Q, Symbol, cos, csc, pi, sec, sin
from sympy.abc import x

from satrefine import refine

n, m, k = Symbol("n"), Symbol("m"), Symbol("k")
CASES = [
    (cos(x + n*pi/2), Q.odd(n), (-1)**((n + 1)/2)*sin(x)),
    (sec(x + n*pi/2), Q.odd(n), (-1)**((n + 1)/2)*csc(x)),
    (sec(x + (2*n + 1)*pi/2), Q.integer(n), (-1)**(n + 1)*csc(x)),
    (cos(x + n*pi + m*pi/2), Q.integer(n) & Q.odd(m), (-1)**(n + (m + 1)/2)*sin(x)),
    (sec(x + n*pi + m*pi/2), Q.integer(n) & Q.odd(m), (-1)**(n + (m + 1)/2)*csc(x)),
    (cos(x + n*pi + k*pi/2 + m*pi/2), Q.integer(n) & Q.odd(k) & Q.integer(m), (-1)**(n + (k + 1)/2)*sin(x + m*pi/2)),
    (sin(x + n*pi + k*pi/2 + m*pi/2), Q.integer(n) & Q.odd(k) & Q.integer(m), (-1)**(n + (k + 3)/2)*cos(x + m*pi/2)),
    (cos(x + n*pi/2 + k*pi/2 + m*pi/2), Q.odd(n) & Q.odd(k) & Q.integer(m), (-1)**((n + k)/2)*cos(x + m*pi/2)),
]


@pytest.mark.parametrize("expr, assumptions, expected", CASES, ids=[str(c[0]) for c in CASES])
def test_one_power_of_minus_one(expr, assumptions, expected):
    assert refine(expr, assumptions) == expected
