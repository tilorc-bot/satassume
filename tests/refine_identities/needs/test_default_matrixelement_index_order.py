"""Needs: ``X[i, j]`` under ``Q.symmetric``/``Q.diagonal`` keeps its index order; ``Q.ne(i, j)`` does not zero it.  Owner: handlers_identities (matrices).

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
SymPy's ``test_matrixelement`` expects the symmetric swap to the sorted
order ``x[j, i]``; ``Q.diagonal(A) & Q.ne(i, j)`` makes an off-diagonal
element 0.  (The phase-3 plan lists the index order as undecidable by ``ask``.)
Each case is a ``tests/refine`` expectation that ``handlers`` meets and
``handlers_identities`` does not (v3 meets the swaps);
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


def test_symmetric_swaps_to_sorted_order():
    assert refine(x[ip, jp], Q.symmetric(x)) == x[jp, ip]      # SymPy's test_matrixelement


def test_diagonal_swaps_to_sorted_order():
    assert refine(A[i, j], Q.diagonal(A)) == A[j, i]
    assert refine(A[i, 0], Q.diagonal(A)) == A[0, i]


def test_diagonal_off_diagonal_element_is_zero():
    assert refine(A[i, j], Q.diagonal(A) & Q.ne(i, j)) == S.Zero
