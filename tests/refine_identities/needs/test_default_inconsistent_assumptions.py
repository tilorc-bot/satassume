"""Needs: inconsistent assumptions no longer raise ``ValueError``.  Owner: handlers_identities (dispatcher).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
With ``handlers`` every backend's ``ask`` raises ``ValueError('inconsistent
assumptions ...')`` and ``refine`` propagates it; ``handlers_identities`` returns
the expression unchanged.  v3 raises too.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets it);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Abs, Q, conjugate
from sympy.abc import x

from satrefine import refine


@pytest.mark.parametrize("expr, assumptions", [
    (conjugate(x), Q.infinite(x) & Q.real(x)),
    (Abs(x), Q.positive(x) & Q.negative(x)),
], ids=["conjugate-infinite-real", "abs-positive-negative"])
def test_raises(expr, assumptions):
    with pytest.raises(ValueError, match="(?i)inconsistent assumptions"):
        refine(expr, assumptions)
