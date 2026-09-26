"""Tests for the ``matrices`` family of ``handlers_v3``.

Each rewrite is checked symbolically and then on concrete matrices: the
MatrixSymbols are replaced by explicit ``Matrix`` values satisfying the
assumptions and both sides are evaluated with ``.doit()``.
"""
from __future__ import annotations

import pytest
from sympy import (
    Adjoint, Determinant, HadamardProduct, I, Identity, Inverse, Matrix,
    MatrixSymbol, Q, S, Symbol, Trace, Transpose, ZeroMatrix, conjugate,
    simplify, sqrt, symbols, zeros, cosh, sinh,
)
from sympy.matrices.expressions.matexpr import MatrixElement

from satrefine.identities.compat import upstream as _upstream
from satrefine.identities.compat.upstream import refine
from satrefine.reference.v3 import matrices

X = MatrixSymbol('X', 2, 2)
Y = MatrixSymbol('Y', 2, 2)
B = MatrixSymbol('B', 2, 3)
C = MatrixSymbol('C', 3, 2)
n = Symbol('n')
A = MatrixSymbol('A', n, n)
x = Symbol('x')
i, j, k = symbols('i j k', integer=True)

# Concrete witnesses.
ROTATION = Matrix([[0, 1], [-1, 0]])          # orthogonal, det 1
REFLECTION = Matrix([[0, 1], [1, 0]])         # orthogonal, det -1
ROT_THIRD = Matrix([[S.Half, -sqrt(3)/2], [sqrt(3)/2, S.Half]])
UNITARY = Matrix([[1, I], [I, 1]]) / sqrt(2)  # complex unitary, not orthogonal
# UNITARY is symmetric, so conjugate(UNITARY) == UNITARY.H; UNITARY2 is not,
# and is the witness that separates conjugate from adjoint.
UNITARY2 = Matrix([[1, 1], [I, -I]]) / sqrt(2)
ORTHOGONALS = [ROTATION, REFLECTION, ROT_THIRD]
UNITARIES = [UNITARY, UNITARY2] + ORTHOGONALS
SYMMETRIC = [Matrix([[1, 2], [2, 3]]), Matrix([[I, 5], [5, -1]])]
DIAGONAL = [Matrix([[2, 0], [0, -3]]), Matrix([[I, 0], [0, 7]])]
SINGULAR = [Matrix([[1, 2], [2, 4]]), Matrix([[0, 0], [1, 5]])]
UNIT_TRI = [Matrix([[1, 5], [0, 1]]), Matrix([[1, 0], [-4, 1]])]
INVERTIBLE = [Matrix([[1, 2], [3, 4]]), UNITARY]
GENERIC = [Matrix([[1, 2], [3, 4]]), Matrix([[I, -1], [7, 2]])]
ZERO22 = zeros(2, 2)


def value(expr, subs):
    out = expr.subs(subs).doit()
    if hasattr(out, 'applyfunc'):
        return out.applyfunc(simplify)
    return simplify(out)


def same_value(e1, e2, subs):
    v1, v2 = value(e1, subs), value(e2, subs)
    if hasattr(v1, 'shape') or hasattr(v2, 'shape'):
        v1, v2 = Matrix(v1), Matrix(v2)
        return v1.shape == v2.shape and (v1 - v2).applyfunc(simplify).is_zero_matrix
    return simplify(v1 - v2) == 0


def check(expr, assumptions, expected, witnesses):
    result = refine(expr, assumptions)
    assert result == expected, (expr, result)
    assert witnesses, "every rule needs a concrete check"
    for subs in witnesses:
        assert same_value(expr, result, subs), (expr, result, subs)
    return result


def unchanged(expr, assumptions):
    assert refine(expr, assumptions) == expr


# ------------------------------------------------------------ witnesses sanity

def test_witnesses_have_the_claimed_properties():
    assert REFLECTION.det() == -1 and ROTATION.det() == 1
    for M in ORTHOGONALS:
        assert (M.T * M).applyfunc(simplify) == Matrix.eye(2)
    for U in UNITARIES:
        assert (U.H * U).applyfunc(simplify) == Matrix.eye(2)
        assert (U * U.H).applyfunc(simplify) == Matrix.eye(2)
    # the complex unitaries are not orthogonal, and conj(U)*U is not I
    assert (UNITARY.T * UNITARY).applyfunc(simplify) != Matrix.eye(2)
    assert (UNITARY2.T * UNITARY2).applyfunc(simplify) != Matrix.eye(2)
    assert (UNITARY2.conjugate() * UNITARY2).applyfunc(simplify) != Matrix.eye(2)
    assert UNITARY2.conjugate() != UNITARY2.H
    for M in SINGULAR:
        assert M.det() == 0


# ------------------------------------------------------------ Transpose

def test_transpose_symmetric():
    check(X.T, Q.symmetric(X), X, [{X: M} for M in SYMMETRIC])


def test_transpose_diagonal_is_symmetric():
    check(X.T, Q.diagonal(X), X, [{X: M} for M in DIAGONAL])


def test_transpose_zero_nonsquare():
    check(B.T, Q.zero(B), ZeroMatrix(3, 2), [{B: zeros(2, 3)}])


def test_transpose_unchanged():
    unchanged(X.T, True)
    unchanged(X.T, Q.orthogonal(X))
    unchanged(X.T, Q.unitary(X))


# ------------------------------------------------------------ Inverse

def test_inverse_orthogonal():
    check(X.I, Q.orthogonal(X), X.T, [{X: M} for M in ORTHOGONALS])


def test_inverse_orthogonal_symbolic_size():
    assert refine(A.I, Q.orthogonal(A)) == A.T


def test_inverse_of_transpose_orthogonal():
    check(Inverse(X.T), Q.orthogonal(X), X, [{X: M} for M in ORTHOGONALS])


def test_inverse_unitary_is_adjoint_not_conjugate():
    r = check(X.I, Q.unitary(X), Adjoint(X), [{X: M} for M in UNITARIES])
    assert r != conjugate(X)


def test_inverse_unchanged():
    unchanged(X.I, True)
    unchanged(X.I, Q.invertible(X))
    unchanged(X.I, Q.symmetric(X))


def test_inverse_singular_does_not_raise():
    unchanged(X.I, Q.singular(X))


# ------------------------------------------------------------ Determinant

def test_determinant_singular():
    check(Determinant(X), Q.singular(X), S.Zero, [{X: M} for M in SINGULAR])


def test_determinant_zero_matrix():
    check(Determinant(X), Q.zero(X), S.Zero, [{X: ZERO22}])


def test_determinant_zero_symbolic_size_unchanged():
    # a 0x0 zero matrix has determinant 1
    unchanged(Determinant(A), Q.zero(A))


def test_determinant_unit_triangular():
    check(Determinant(X), Q.unit_triangular(X), S.One, [{X: M} for M in UNIT_TRI])


def test_determinant_orthogonal_unchanged():
    unchanged(Determinant(X), Q.orthogonal(X))
    unchanged(Determinant(X), Q.orthogonal(X) & Q.real_elements(X))
    unchanged(Determinant(X), Q.unitary(X))
    # the reason: the reflection is orthogonal with determinant -1
    assert value(Determinant(X), {X: REFLECTION}) == -1


def test_determinant_unchanged():
    unchanged(Determinant(X), True)
    unchanged(Determinant(X), Q.invertible(X))


# ------------------------------------------------------------ Trace

def test_trace_zero():
    check(Trace(X), Q.zero(X), S.Zero, [{X: ZERO22}])


def test_trace_unchanged():
    unchanged(Trace(X), True)
    unchanged(Trace(X), Q.orthogonal(X))
    unchanged(Trace(X), Q.symmetric(X))


def test_trace_of_sum_drops_zero_term():
    check(Trace(X + Y), Q.zero(Y), Trace(X), [{X: M, Y: ZERO22} for M in GENERIC])


# ------------------------------------------------------------ MatAdd

def test_matadd_drops_zero_term():
    check(X + Y, Q.zero(X), Y, [{X: ZERO22, Y: M} for M in GENERIC])


def test_matadd_all_zero():
    check(X + Y, Q.zero(X) & Q.zero(Y), ZeroMatrix(2, 2), [{X: ZERO22, Y: ZERO22}])


def test_matadd_symmetric_difference_collects():
    check(X - X.T, Q.symmetric(X), ZeroMatrix(2, 2), [{X: M} for M in SYMMETRIC])


def test_matadd_unchanged():
    unchanged(X + Y, True)
    unchanged(X + Y, Q.orthogonal(X))


# ------------------------------------------------------------ HadamardProduct

def test_hadamard_zero_factor():
    check(HadamardProduct(X, Y), Q.zero(Y), ZeroMatrix(2, 2),
          [{X: M, Y: ZERO22} for M in GENERIC])


def test_hadamard_zero_factor_nonsquare():
    B2 = MatrixSymbol('B2', 2, 3)
    check(HadamardProduct(B, B2), Q.zero(B), ZeroMatrix(2, 3),
          [{B: zeros(2, 3), B2: Matrix([[1, 2, 3], [4, 5, 6]])}])


def test_hadamard_unchanged():
    unchanged(HadamardProduct(X, Y), True)
    unchanged(HadamardProduct(X, Y), Q.diagonal(X))


# ------------------------------------------------------------ MatMul

@pytest.mark.parametrize('expr', [X.T * X, X * X.T])
def test_matmul_orthogonal_both_orders(expr):
    check(expr, Q.orthogonal(X), Identity(2), [{X: M} for M in ORTHOGONALS])


def test_matmul_orthogonal_symbolic_size():
    assert refine(A.T * A, Q.orthogonal(A)) == Identity(n)
    assert refine(A * A.T, Q.orthogonal(A)) == Identity(n)


def test_matmul_orthogonal_keeps_scalars_and_neighbours():
    check(2 * X * X.T * Y, Q.orthogonal(X), 2 * Y,
          [{X: M, Y: G} for M in ORTHOGONALS for G in GENERIC])
    check(x * Y * X.T * X, Q.orthogonal(X), x * Y,
          [{X: M, Y: G, x: 3} for M in ORTHOGONALS for G in GENERIC])


def test_matmul_orthogonal_chain():
    check(X * X.T * X, Q.orthogonal(X), X, [{X: M} for M in ORTHOGONALS])
    check(X.T * X * X.T * X, Q.orthogonal(X), Identity(2), [{X: M} for M in ORTHOGONALS])


def test_matmul_orthogonal_through_inverse():
    # X**-1 -> X.T, so X*(X**-1).T is X*X
    check(X * X.I.T, Q.orthogonal(X), X**2, [{X: M} for M in ORTHOGONALS])
    check(X.I * X.T.T, Q.orthogonal(X), Identity(2), [{X: M} for M in ORTHOGONALS])


@pytest.mark.parametrize('expr', [Adjoint(X) * X, X * Adjoint(X)])
def test_matmul_unitary_both_orders(expr):
    check(expr, Q.unitary(X), Identity(2), [{X: M} for M in UNITARIES])


def test_matmul_unitary_keeps_scalars():
    check(3 * Y * Adjoint(X) * X, Q.unitary(X), 3 * Y,
          [{X: M, Y: G} for M in UNITARIES for G in GENERIC])


def test_matmul_conjugate_unitary_unchanged():
    unchanged(conjugate(X) * X, Q.unitary(X))
    unchanged(X * conjugate(X), Q.unitary(X))
    assert not same_value(conjugate(X) * X, Identity(2), {X: UNITARY2})


def test_matmul_transpose_unitary_unchanged():
    unchanged(X.T * X, Q.unitary(X))
    assert not same_value(X.T * X, Identity(2), {X: UNITARY})


def test_matmul_adjoint_orthogonal_needs_real():
    # SymPy derives unitary from orthogonal, which is only right for real X
    unchanged(Adjoint(X) * X, Q.orthogonal(X))
    check(Adjoint(X) * X, Q.orthogonal(X) & Q.real_elements(X), Identity(2),
          [{X: M} for M in ORTHOGONALS])


def test_matmul_inverse_invertible():
    check(X.I.T * X.T, Q.invertible(X), Identity(2), [{X: M} for M in INVERTIBLE])


def test_matmul_non_adjacent_unchanged():
    unchanged(X.T * Y * X, Q.orthogonal(X))
    unchanged(X * Y * X.T, Q.orthogonal(X))


def test_matmul_unchanged():
    unchanged(X * Y, True)
    unchanged(X.T * X, True)
    check(X.T * X, Q.symmetric(X), X**2, [{X: M} for M in SYMMETRIC])
    unchanged(X * X, Q.orthogonal(X))


def test_matmul_zero_factor_shape():
    check(B * C, Q.zero(B), ZeroMatrix(2, 2),
          [{B: zeros(2, 3), C: Matrix([[1, 2], [3, 4], [5, 6]])}])
    check(C * B, Q.zero(B), ZeroMatrix(3, 3),
          [{B: zeros(2, 3), C: Matrix([[1, 2], [3, 4], [5, 6]])}])


def test_matmul_zero_scalar():
    check(x * X * Y, Q.zero(x), ZeroMatrix(2, 2), [{x: 0, X: G, Y: G} for G in GENERIC])


# ------------------------------------------------------------ MatrixElement

def test_element_zero():
    check(X[0, 1], Q.zero(X), S.Zero, [{X: ZERO22}])
    check(X[i, j], Q.zero(X), S.Zero, [{X: ZERO22, i: 1, j: 0}])


def test_element_diagonal_literal_indices():
    check(X[0, 1], Q.diagonal(X), S.Zero, [{X: M} for M in DIAGONAL])
    check(X[1, 0], Q.diagonal(X), S.Zero, [{X: M} for M in DIAGONAL])


def test_element_diagonal_ne():
    facts = Q.diagonal(X) & Q.ne(i, j) & Q.nonnegative(i) & Q.nonnegative(j)
    check(X[i, j], facts, S.Zero,
          [{X: M, i: 0, j: 1} for M in DIAGONAL] + [{X: M, i: 1, j: 0} for M in DIAGONAL])


def test_element_diagonal_negative_indices_wrap():
    # SymPy wraps negative indices: X[0, -2] of a 2x2 X is X[0, 0], and
    # X[0, -1] of a 1x1 is its only entry, so i != j alone proves nothing.
    D = DIAGONAL[0]
    assert value(X[0, -2], {X: D}) == 2
    X1 = MatrixSymbol('X1', 1, 1)
    cases = [(X[0, -2], {}), (X[1, -1], {}), (X[i, i - 2], {i: 1}),
             (X[i, j], {i: 0, j: -2})]
    for e, idx in cases:
        facts = Q.diagonal(X) & Q.ne(i, j)
        r = refine(e, facts)
        assert r != 0
        for M in DIAGONAL:
            assert same_value(e, r, {X: M, **idx})
    assert refine(X1[0, -1], Q.diagonal(X1)) != 0
    assert value(X[i, j], {X: D, i: 0, j: -2}) != 0
    # wrapped but still off the diagonal
    check(X[0, -1], Q.diagonal(X), S.Zero, [{X: M} for M in DIAGONAL])


def test_element_diagonal_offset():
    check(X[k + 1, k], Q.diagonal(X), S.Zero, [{X: M, k: 0} for M in DIAGONAL])


def test_element_diagonal_plain_symbols_not_zeroed():
    r = refine(X[i, j], Q.diagonal(X))
    assert r != 0
    # diagonal => symmetric, so only the vendored index canonicalisation may apply
    assert r in (X[i, j], X[j, i])
    assert refine(X[i, i], Q.diagonal(X)) == X[i, i]
    assert same_value(X[i, j], X[j, i], {X: DIAGONAL[0], i: 0, j: 0})
    assert value(X[i, j], {X: DIAGONAL[0], i: 0, j: 0}) != 0


def test_element_symmetric_canonical_order():
    check(X[1, 0], Q.symmetric(X), X[0, 1], [{X: M} for M in SYMMETRIC])
    unchanged(X[0, 1], Q.symmetric(X))
    r1 = refine(X[i, j], Q.symmetric(X))
    r2 = refine(X[j, i], Q.symmetric(X))
    assert r1 == r2
    for M in SYMMETRIC:
        for a in range(2):
            for b in range(2):
                assert same_value(X[i, j], r1, {X: M, i: a, j: b})


def test_element_unchanged():
    unchanged(X[0, 1], True)
    unchanged(X[1, 0], Q.orthogonal(X))
    unchanged(X[1, 0], Q.upper_triangular(X))


# ------------------------------------------------------------ SymPy ask gaps

COMPLEX_ORTH = Matrix([[cosh(1), I*sinh(1)], [-I*sinh(1), cosh(1)]])


def test_complex_orthogonal_witness():
    assert (COMPLEX_ORTH.T * COMPLEX_ORTH).applyfunc(simplify) == Matrix.eye(2)
    assert (COMPLEX_ORTH.H * COMPLEX_ORTH).applyfunc(simplify) != Matrix.eye(2)


def test_unitary_inferred_through_product_of_complex_orthogonal():
    # ask derives Q.unitary(X*Y) and Q.unitary(-X) from Q.orthogonal(X)
    unchanged(Inverse(X * Y), Q.orthogonal(X) & Q.unitary(Y))
    assert not same_value(Inverse(X * Y), Adjoint(Y) * Adjoint(X),
                          {X: COMPLEX_ORTH, Y: UNITARY2})
    unchanged(Inverse(-X), Q.orthogonal(X))
    check(Inverse(X * Y), Q.unitary(X) & Q.unitary(Y), Adjoint(Y) * Adjoint(X),
          [{X: UNITARY, Y: UNITARY2}])


def test_slice_of_orthogonal_is_not_orthogonal():
    # ask calls a diagonal block of an orthogonal/unitary matrix orthogonal/unitary
    s = X[:1, :1]
    assert Matrix(value(s, {X: ROT_THIRD})) == Matrix([[S.Half]])
    for facts in [Q.orthogonal(X), Q.unitary(X)]:
        unchanged(Inverse(s), facts)
        unchanged(Adjoint(s) * s, facts)


def test_product_of_symmetric_is_not_symmetric():
    # ask calls every product of symmetric factors symmetric
    S1, S2 = SYMMETRIC[0], Matrix([[0, 5], [5, 1]])
    facts = Q.symmetric(X) & Q.symmetric(Y)
    for e in [Transpose(X * Y), Transpose(X + Y * X), MatrixElement(X * Y, 1, 0)]:
        unchanged(e, facts)
    assert not same_value(Transpose(X * Y), X * Y, {X: S1, Y: S2})
    # the sound product cases still fire
    check(Transpose(X * Y * X), facts, X * Y * X, [{X: S1, Y: S2}])
    check(Transpose(X.T * Y * X), Q.symmetric(Y), X.T * Y * X,
          [{X: GENERIC[0], Y: S2}])
    check(Transpose(X * Y), Q.diagonal(X) & Q.diagonal(Y), X * Y,
          [{X: DIAGONAL[0], Y: DIAGONAL[1]}])


# ------------------------------------------------------------ registry

def test_registered():
    for key in ['Determinant', 'HadamardProduct', 'Inverse', 'MatAdd', 'MatMul',
                'MatrixElement', 'Trace', 'Transpose']:
        assert _upstream.handlers_dict[key].__module__ == matrices.__name__


def test_handlers_return_none_when_nothing_applies():
    assert matrices.refine_Transpose(X.T, True) is None
    assert matrices.refine_Inverse(X.I, True) is None
    assert matrices.refine_Determinant(Determinant(X), Q.orthogonal(X)) is None
    assert matrices.refine_Trace(Trace(X), True) is None
    assert matrices.refine_MatAdd(X + Y, True) is None
    assert matrices.refine_MatMul(X * Y, True) is None
    assert matrices.refine_HadamardProduct(HadamardProduct(X, Y), True) is None
