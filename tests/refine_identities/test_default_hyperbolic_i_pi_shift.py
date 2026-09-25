"""Fixed in phase 3 (ri/fixes).  The needs test said: ``sinh``/``cosh``/``sech``/``csch`` of ``x + n*I*pi`` for integer ``n`` (parity unknown).  Owner: handlers_identities (hyperbolic).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``f(x + n*I*pi) = (-1)**n*f(x)`` for these four; ``handlers`` does it, v3 does not.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import I, Q, cosh, csch, pi, sech, sinh
from sympy.abc import n, x

from satrefine import refine


@pytest.mark.parametrize("f", [sinh, cosh, sech, csch], ids=lambda f: f.__name__)
def test_integer_multiple_of_i_pi(f):
    assert refine(f(x + n*I*pi), Q.integer(n)) == (-1)**n*f(x)
