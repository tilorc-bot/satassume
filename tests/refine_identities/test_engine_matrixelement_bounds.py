"""Moved from ``needs/test_matfuzz_matrixelement_bounds_crash.py``; fixed in
``_simple._affine`` (no scalar substituted for a matrix: the bound is unknown).

Matrix fuzz finding (``satrefine/tools/refine_fuzz.py --matrices``, seed 1; 30 of
1,458 cases), for the engine: refining a scalar expression that contains
matrix elements crashes with ``TypeError: First argument of MatrixElement
should be a matrix``.

The traceback runs ``_engine.provable`` -> ``_from_bounds`` ->
``_simple.stated_bounds`` -> ``_affine``, which does ``d.xreplace({u: t})``
with ``u`` a ``MatrixSymbol`` inside a ``MatrixElement`` and ``t`` a scalar
symbol; ``MatrixElement`` refuses a non-matrix first argument.  v3 refines
the same inputs without crashing.  The request: ``stated_bounds``/``_affine``
should not substitute a scalar for a matrix (skip matrix symbols, or catch the
rebuild error and treat the bound as unknown).
"""
from __future__ import annotations

from sympy import MatrixSymbol, Q, Symbol, conjugate

from satrefine import refine

X = MatrixSymbol('X', 3, 3)
X2 = MatrixSymbol('X', 2, 2)
i = Symbol('i')


def test_conjugate_of_an_element_of_a_symmetric_unitary_matrix():
    e = conjugate(X[-1, -2])
    assert refine(e, Q.symmetric(X) & Q.unitary(X)) is not None


def test_row_norm_of_an_orthogonal_matrix():
    e = conjugate(X2[i, 0])*X2[i, 0] + conjugate(X2[i, 1])*X2[i, 1]
    assert refine(e, Q.integer(i) & Q.nonnegative(i) & Q.orthogonal(X2) & Q.symmetric(X2)) is not None
