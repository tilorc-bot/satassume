"""``X[i, j]`` under ``Q.symmetric``/``Q.diagonal`` kept its index order (fixed
2026-09-25, ri/matfixes: the swap row's hypothesis carries
``matrices._SwappedOrder``, SymPy's canonical order evaluated on the bound
indices).  The ``Q.ne(i, j)`` case stays in
``needs/test_default_matrixelement_ne_wrapping.py``.

Found by making ``handlers_identities`` the default (phase 3, track D; see
``agent-reports/2026-09-25-phase3-default-report.md``).
SymPy's ``test_matrixelement`` expects the symmetric swap to the sorted
order ``x[j, i]``; ``Q.diagonal(A) & Q.ne(i, j)`` makes an off-diagonal
element 0.
"""
from __future__ import annotations

import pytest
from sympy import MatrixSymbol, Q, Symbol

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


def test_canonical_order_is_kept():
    assert refine(x[jp, ip], Q.symmetric(x)) == x[jp, ip]
    assert refine(A[i, 2*i], Q.diagonal(A)) == A[i, 2*i]
    assert refine(A[0, i], Q.diagonal(A)) == A[0, i]
