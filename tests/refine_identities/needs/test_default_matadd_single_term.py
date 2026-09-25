"""Needs: ``refine(MatAdd(X), ...)`` raises ``TypeError``.  Owner: handlers_identities (matrices / dispatcher).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
A one-term ``MatAdd`` crashes: ``TypeError: GenericZeroMatrix does not have a
specified shape``, with or without assumptions.  ``handlers`` returns ``X``
for ``True`` and ``0`` for ``Q.zero(X)``; v3 returns ``X`` and ``0`` too.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets it);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import MatAdd, MatrixSymbol, Q, ZeroMatrix

from satrefine import refine

X = MatrixSymbol("X", 2, 2)


def test_single_term_no_assumptions():
    assert refine(MatAdd(X), True) in (X, MatAdd(X))


def test_single_term_zero():
    assert refine(MatAdd(X), Q.zero(X)) == ZeroMatrix(2, 2)
