"""``refine(MatAdd(X), ...)`` raised ``TypeError`` (fixed 2026-09-25, ri/matfixes:
``Z + R`` needs a non-empty rest, and a row ``MatAdd(Z) -> 0`` for zero ``Z``).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
A one-term ``MatAdd`` crashes: ``TypeError: GenericZeroMatrix does not have a
specified shape``, with or without assumptions.  ``handlers`` returns ``X``
for ``True`` and ``0`` for ``Q.zero(X)``; v3 returns ``X`` and ``0`` too.
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets it);
the ``tests/refine`` expectation keeps ``MatAdd(X)`` when nothing is known.
"""
from __future__ import annotations

import pytest
from sympy import MatAdd, MatrixSymbol, Q, ZeroMatrix

from satrefine import refine

X = MatrixSymbol("X", 2, 2)


def test_single_term_no_assumptions():
    assert refine(MatAdd(X), True) == MatAdd(X)


def test_single_term_zero():
    assert refine(MatAdd(X), Q.zero(X)) == ZeroMatrix(2, 2)
