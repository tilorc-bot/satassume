"""Needs: ``Rem(p, q)`` under ``Q.zero(p)`` is not reduced to 0.  Owner: handlers_identities (integer_funcs).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``Rem(0, q) = 0`` for every ``q != 0``; ``Rem(0, 0)`` raises in SymPy, so
the rule needs no ``q`` guard (``handlers`` has none; v3 declines).
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Q, Rem, S
from sympy.abc import p, q

from satrefine import refine


def test_zero_dividend():
    assert refine(Rem(p, q), Q.zero(p)) is S.Zero
