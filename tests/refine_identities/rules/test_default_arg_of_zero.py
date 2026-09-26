"""Fixed in phase 3 (ri/fixes).  The needs test said: ``arg(x)`` under ``Q.zero(x)`` stays ``arg(x)``; SymPy's ``arg(0)`` is ``nan``.  Owner: handlers_identities (complex_parts).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Q, arg, nan
from sympy.abc import x

from satrefine import refine


def test_arg_of_zero_is_nan():
    assert refine(arg(x), Q.zero(x)) is nan
