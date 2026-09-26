"""Fixed in phase 3 (ri/fixes).  The needs test said: ``(-1)**((-1)**x/2 + c)`` for integer ``x`` is not reduced to ``(-1)**x`` or ``(-1)**(x + 1)``.  Owner: handlers_identities (power_exp_log).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
The constant ``c`` is reduced modulo 2 but the result is not; SymPy's own
``test_pow1``/``test_pow2`` expect the final form.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets it too);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Q, S
from sympy.abc import x

from satrefine import refine

CASES = [
    ((-1)**((-1)**x/2 - S.Half), (-1)**x),
    ((-1)**((-1)**x/2 + S.Half), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 + 5*S.Half), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 - 7*S.Half), (-1)**(x + 1)),
    ((-1)**((-1)**x/2 - 9*S.Half), (-1)**x),
]


@pytest.mark.parametrize("expr, expected", CASES, ids=[str(c[0]) for c in CASES])
def test_reduced_to_a_power_of_x(expr, expected):
    assert refine(expr, Q.integer(x)) == expected
