"""Fixed in phase 3 (ri/fixes).  The needs test said: floor/ceiling of an infinite argument, and of a sum of floors/ceilings.  Owner: handlers_identities (integer_funcs).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
From SymPy's ``test_floor_ceiling`` (v3 declines these too).  ``floor(oo)``,
``floor(-oo)`` and ``floor(zoo)`` are the argument, so ``floor(x) -> x`` under
``Q.infinite(x)`` is sound; a floor/ceiling of an integer-valued term moves out.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Q, ceiling, floor
from sympy.abc import x, y, z

from satrefine import refine

CASES = [
    (floor(x), Q.infinite(x), x),
    (ceiling(x), Q.infinite(x), x),
    (ceiling(ceiling(x) + y + floor(z)), True, ceiling(x) + ceiling(y) + floor(z)),
    (floor(floor(x) + floor(y)), True, floor(x) + floor(y)),
    (ceiling(ceiling(x) - ceiling(y)), True, ceiling(x) - ceiling(y)),
]


@pytest.mark.parametrize("expr, assumptions, expected", CASES, ids=[str(c[0]) for c in CASES])
def test_floor_ceiling(expr, assumptions, expected):
    assert refine(expr, assumptions) == expected
