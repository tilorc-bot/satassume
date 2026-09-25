"""Needs: a scalar between matrix factors blocks cancellation and is not moved to the front.  Owner: handlers_identities (matrices).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``MatMul(X.T, 2, X)`` under ``Q.orthogonal(X)`` stays unchanged (``handlers``:
``2*I``); ``MatMul(X, 2, Y)`` stays unevaluated where SymPy's ``refine`` and
``handlers`` give ``2*X*Y``.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 does not either);
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import Identity, MatMul, MatrixSymbol, Q

from satrefine import refine

X = MatrixSymbol("X", 2, 2)
Y = MatrixSymbol("Y", 2, 2)


def test_scalar_between_cancelling_factors():
    assert refine(MatMul(X.T, 2, X), Q.orthogonal(X)).doit() == 2*Identity(2)


def test_scalar_moved_to_front():
    assert refine(MatMul(X, 2, Y), True) == 2*X*Y
