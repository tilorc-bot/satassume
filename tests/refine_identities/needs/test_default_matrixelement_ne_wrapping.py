"""Needs: ``A[i, j]`` under ``Q.diagonal(A) & Q.ne(i, j)`` is not zeroed.  Owner: handlers_identities (matrices).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
``handlers`` makes ``A[i, j]`` 0 under ``Q.diagonal(A) & Q.ne(i, j)``.
``handlers_identities`` refuses on purpose: SymPy keeps a negative index
(``A[-1, 0]`` stays ``MatrixElement(A, -1, 0)`` and means the last row once
``A`` is explicit), so ``i != j`` does not make the element off-diagonal
(``i = -1, j = 2`` for a 3x3 ``A``).  The row needs both indices of one sign
or ``i - j != +-3``.  Left open (2026-09-25, ri/matfixes): meeting it needs a
decision that symbolic indices are nonnegative, not an engine change.  (The
index-order swaps from this file now pass:
rows "default: MatrixElement index order" of
``tests/refine_identities/regressions.py``.)
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not;
the original test is a strict xfail under ``handlers_identities`` that points
here.
"""
from __future__ import annotations

import pytest
from sympy import MatrixSymbol, Q, S, Symbol

from satrefine import refine

x = MatrixSymbol("x", 3, 3)
A = MatrixSymbol("A", 3, 3)
i, j = Symbol("i"), Symbol("j")
ip, jp = Symbol("i", positive=True), Symbol("j", positive=True)


def test_diagonal_off_diagonal_element_is_zero():
    assert refine(A[i, j], Q.diagonal(A) & Q.ne(i, j)) == S.Zero
