"""The ``matrices`` rule table: every row fires where v3's rule does, agrees
with the input on concrete matrices, and the v3 refusals stay refusals.

The harness cannot decide matrix predicates on explicit matrices
(``ask(Q.symmetric(Matrix(...)))`` is ``None``), so each rule is checked on
witnesses chosen to satisfy its assumptions: ``assert_refinement_valid``
with ``assumptions=True`` and the witnesses as ``values=``, entry by entry
for matrix-valued results.
"""
from __future__ import annotations

from itertools import product

import pytest
from sympy import (Adjoint, Determinant, HadamardProduct, I, Identity, Inverse, MatAdd, MatMul,
                   Matrix, MatrixSymbol, Q, S, Symbol, Trace, Transpose, ZeroMatrix, conjugate,
                   cosh, sinh, sqrt, symbols, zeros)
from sympy.matrices.expressions.matexpr import MatrixElement

from satrefine import refine
from satrefine.harness import assert_refinement_valid

X = MatrixSymbol('X', 2, 2)
Y = MatrixSymbol('Y', 2, 2)
B = MatrixSymbol('B', 2, 3)
B2 = MatrixSymbol('B2', 2, 3)
C = MatrixSymbol('C', 3, 2)
n = Symbol('n')
A = MatrixSymbol('A', n, n)
x = Symbol('x')
i, j, k = symbols('i j k', integer=True)

ROTATION = Matrix([[0, 1], [-1, 0]])
REFLECTION = Matrix([[0, 1], [1, 0]])
ROT_THIRD = Matrix([[S.Half, -sqrt(3)/2], [sqrt(3)/2, S.Half]])
UNITARY = Matrix([[1, I], [I, 1]]) / sqrt(2)
UNITARY2 = Matrix([[1, 1], [I, -I]]) / sqrt(2)
ORTHOGONALS = [ROTATION, REFLECTION, ROT_THIRD]
UNITARIES = [UNITARY, UNITARY2] + ORTHOGONALS
SYMMETRIC = [Matrix([[1, 2], [2, 3]]), Matrix([[I, 5], [5, -1]])]
DIAGONAL = [Matrix([[2, 0], [0, -3]]), Matrix([[I, 0], [0, 7]])]
SINGULAR = [Matrix([[1, 2], [2, 4]]), Matrix([[0, 0], [1, 5]])]
UNIT_TRI = [Matrix([[1, 5], [0, 1]]), Matrix([[1, 0], [-4, 1]])]
INVERTIBLE = [Matrix([[1, 2], [3, 4]]), UNITARY]
GENERIC = [Matrix([[1, 2], [3, 4]]), Matrix([[I, -1], [7, 2]])]
Z22 = zeros(2, 2)
COMPLEX_ORTH = Matrix([[cosh(1), I*sinh(1)], [-I*sinh(1), cosh(1)]])


def each(sym, mats):
    return [{sym: M} for M in mats]


POSITIVE = [  # (expr, assumptions, expected, witnesses satisfying the assumptions)
    # Transpose
    (X.T, Q.symmetric(X), X, each(X, SYMMETRIC)),
    (X.T, Q.diagonal(X), X, each(X, DIAGONAL)),
    (B.T, Q.zero(B), ZeroMatrix(3, 2), each(B, [zeros(2, 3)])),
    (Transpose(X*Y*X), Q.symmetric(X) & Q.symmetric(Y), X*Y*X,
     [{X: SYMMETRIC[0], Y: Matrix([[0, 5], [5, 1]])}]),
    (Transpose(X.T*Y*X), Q.symmetric(Y), X.T*Y*X, [{X: GENERIC[0], Y: SYMMETRIC[0]}]),
    (Transpose(X*Y), Q.diagonal(X) & Q.diagonal(Y), X*Y, [{X: DIAGONAL[0], Y: DIAGONAL[1]}]),
    # Inverse
    (X.I, Q.orthogonal(X), X.T, each(X, ORTHOGONALS)),
    (Inverse(X.T), Q.orthogonal(X), X, each(X, ORTHOGONALS)),
    (X.I, Q.unitary(X), Adjoint(X), each(X, UNITARIES)),
    (Inverse(X*Y), Q.unitary(X) & Q.unitary(Y), Adjoint(Y)*Adjoint(X),
     [{X: UNITARY, Y: UNITARY2}]),
    # Determinant
    (Determinant(X), Q.singular(X), S.Zero, each(X, SINGULAR)),
    (Determinant(X), Q.zero(X), S.Zero, each(X, [Z22])),
    (Determinant(X), Q.unit_triangular(X), S.One, each(X, UNIT_TRI)),
    # Trace
    (Trace(X), Q.zero(X), S.Zero, each(X, [Z22])),
    (Trace(X + Y), Q.zero(Y), Trace(X), [{X: M, Y: Z22} for M in GENERIC]),
    # MatAdd
    (X + Y, Q.zero(X), Y, [{X: Z22, Y: M} for M in GENERIC]),
    (X + Y, Q.zero(X) & Q.zero(Y), ZeroMatrix(2, 2), [{X: Z22, Y: Z22}]),
    (X - X.T, Q.symmetric(X), ZeroMatrix(2, 2), each(X, SYMMETRIC)),
    # HadamardProduct
    (HadamardProduct(X, Y), Q.zero(Y), ZeroMatrix(2, 2), [{X: M, Y: Z22} for M in GENERIC]),
    (HadamardProduct(B, B2), Q.zero(B), ZeroMatrix(2, 3),
     [{B: zeros(2, 3), B2: Matrix([[1, 2, 3], [4, 5, 6]])}]),
    # MatMul
    (X.T*X, Q.orthogonal(X), Identity(2), each(X, ORTHOGONALS)),
    (X*X.T, Q.orthogonal(X), Identity(2), each(X, ORTHOGONALS)),
    (2*X*X.T*Y, Q.orthogonal(X), 2*Y, [{X: M, Y: G} for M in ORTHOGONALS for G in GENERIC]),
    (x*Y*X.T*X, Q.orthogonal(X), x*Y, [{X: M, Y: G, x: 3} for M in ORTHOGONALS for G in GENERIC]),
    (X*X.T*X, Q.orthogonal(X), X, each(X, ORTHOGONALS)),
    (X.T*X*X.T*X, Q.orthogonal(X), Identity(2), each(X, ORTHOGONALS)),
    (X*X.I.T, Q.orthogonal(X), X**2, each(X, ORTHOGONALS)),
    (X.I*X.T.T, Q.orthogonal(X), Identity(2), each(X, ORTHOGONALS)),
    (Adjoint(X)*X, Q.unitary(X), Identity(2), each(X, UNITARIES)),
    (X*Adjoint(X), Q.unitary(X), Identity(2), each(X, UNITARIES)),
    (3*Y*Adjoint(X)*X, Q.unitary(X), 3*Y, [{X: M, Y: G} for M in UNITARIES for G in GENERIC]),
    (Adjoint(X)*X, Q.orthogonal(X) & Q.real_elements(X), Identity(2), each(X, ORTHOGONALS)),
    (X*Adjoint(X), Q.orthogonal(X) & Q.real_elements(X), Identity(2), each(X, ORTHOGONALS)),
    (MatMul(Inverse(X), X), Q.invertible(X), Identity(2), each(X, INVERTIBLE)),
    (MatMul(X, Inverse(X)), Q.invertible(X), Identity(2), each(X, INVERTIBLE)),
    (X.T*X, Q.symmetric(X), X**2, each(X, SYMMETRIC)),
    (B*C, Q.zero(B), ZeroMatrix(2, 2), [{B: zeros(2, 3), C: Matrix([[1, 2], [3, 4], [5, 6]])}]),
    (C*B, Q.zero(B), ZeroMatrix(3, 3), [{B: zeros(2, 3), C: Matrix([[1, 2], [3, 4], [5, 6]])}]),
    (x*X*Y, Q.zero(x), ZeroMatrix(2, 2), [{x: 0, X: G, Y: G} for G in GENERIC]),
    # MatrixElement
    (X[0, 1], Q.zero(X), S.Zero, each(X, [Z22])),
    (X[i, j], Q.zero(X), S.Zero, [{X: Z22, i: 1, j: 0}]),
    (X[0, 1], Q.diagonal(X), S.Zero, each(X, DIAGONAL)),
    (X[1, 0], Q.diagonal(X), S.Zero, each(X, DIAGONAL)),
    (X[i, j], Q.diagonal(X) & Q.ne(i, j) & Q.nonnegative(i) & Q.nonnegative(j), S.Zero,
     [{X: M, i: 0, j: 1} for M in DIAGONAL] + [{X: M, i: 1, j: 0} for M in DIAGONAL]),
    (X[0, -1], Q.diagonal(X), S.Zero, each(X, DIAGONAL)),
    (X[k + 1, k], Q.diagonal(X), S.Zero, [{X: M, k: 0} for M in DIAGONAL]),
    (X[1, 0], Q.symmetric(X), X[0, 1], each(X, SYMMETRIC)),
]

SYMBOLIC_SIZE = [  # fires without a numeric size
    (A.I, Q.orthogonal(A), A.T),
    (A.T*A, Q.orthogonal(A), Identity(n)),
    (A*A.T, Q.orthogonal(A), Identity(n)),
]

X1 = MatrixSymbol('X1', 1, 1)
NEGATIVE = [  # v3's refusals
    (X.T, True), (X.T, Q.orthogonal(X)), (X.T, Q.unitary(X)),
    (X.I, True), (X.I, Q.invertible(X)), (X.I, Q.symmetric(X)), (X.I, Q.singular(X)),
    (Determinant(A), Q.zero(A)),                         # a 0x0 zero matrix has determinant 1
    (Determinant(X), Q.orthogonal(X)),                   # det is +-1, not 1
    (Determinant(X), Q.orthogonal(X) & Q.real_elements(X)),
    (Determinant(X), Q.unitary(X)),
    (Determinant(X), True), (Determinant(X), Q.invertible(X)),
    (Trace(X), True), (Trace(X), Q.orthogonal(X)), (Trace(X), Q.symmetric(X)),
    (X + Y, True), (X + Y, Q.orthogonal(X)),
    (HadamardProduct(X, Y), True), (HadamardProduct(X, Y), Q.diagonal(X)),
    (conjugate(X)*X, Q.unitary(X)),                      # the inverse is the adjoint
    (X*conjugate(X), Q.unitary(X)),
    (X.T*X, Q.unitary(X)),
    (Adjoint(X)*X, Q.orthogonal(X)),                     # complex orthogonal is not unitary
    (X.T*Y*X, Q.orthogonal(X)), (X*Y*X.T, Q.orthogonal(X)),   # not adjacent
    (X*Y, True), (X.T*X, True),
    (X[0, 1], True), (X[1, 0], Q.orthogonal(X)), (X[1, 0], Q.upper_triangular(X)),
    (X[i, j], Q.diagonal(X)), (X[i, i], Q.diagonal(X)),
    (X[i, j], Q.diagonal(X) & Q.ne(i, j)),
    # ask's wrong answers on compound arguments never reach a row
    (Inverse(X*Y), Q.orthogonal(X) & Q.unitary(Y)),
    (Inverse(-X), Q.orthogonal(X)),
    (Inverse(X[:1, :1]), Q.orthogonal(X)), (Inverse(X[:1, :1]), Q.unitary(X)),
    (Adjoint(X[:1, :1])*X[:1, :1], Q.orthogonal(X)), (Adjoint(X[:1, :1])*X[:1, :1], Q.unitary(X)),
    (Transpose(X*Y), Q.symmetric(X) & Q.symmetric(Y)),
    (Transpose(X + Y*X), Q.symmetric(X) & Q.symmetric(Y)),
    (MatrixElement(X*Y, 1, 0), Q.symmetric(X) & Q.symmetric(Y)),
]


def _id(row):
    return f"{row[0]}|{row[1]}"


def _check(expr, refined, witnesses):
    for witness in witnesses:
        values = {s: [v] for s, v in witness.items()}
        if getattr(expr, 'is_Matrix', False):
            for r, c in product(range(expr.rows), range(expr.cols)):
                assert_refinement_valid(expr[r, c], True, refined[r, c], samples=1, values=values)
        else:
            assert_refinement_valid(expr, True, refined, samples=1, values=values)


@pytest.mark.parametrize("expr, assumptions, expected, witnesses", POSITIVE, ids=map(_id, POSITIVE))
def test_row_fires(expr, assumptions, expected, witnesses):
    assert refine(expr, assumptions) == expected


@pytest.mark.parametrize("expr, assumptions, expected, witnesses", POSITIVE, ids=map(_id, POSITIVE))
def test_row_is_sound(expr, assumptions, expected, witnesses):
    _check(expr, refine(expr, assumptions), witnesses)


@pytest.mark.parametrize("expr, assumptions, expected", SYMBOLIC_SIZE, ids=map(_id, SYMBOLIC_SIZE))
def test_row_fires_at_symbolic_size(expr, assumptions, expected):
    assert refine(expr, assumptions) == expected


@pytest.mark.parametrize("expr, assumptions", NEGATIVE, ids=map(_id, NEGATIVE))
def test_refusal(expr, assumptions):
    assert refine(expr, assumptions) == expr


@pytest.mark.parametrize("expr, idx", [
    (X[0, -2], {}), (X[1, -1], {}), (X[i, i - 2], {i: 1}), (X[i, j], {i: 0, j: -2})])
def test_wrapped_indices_are_not_zeroed(expr, idx):
    """Negative indices wrap (``X[0, -2]`` of a 2x2 ``X`` is ``X[0, 0]``), so
    ``i != j`` alone does not put an element off the diagonal.  The symmetric
    row may reorder the indices (a diagonal matrix is symmetric)."""
    got = refine(expr, Q.diagonal(X) & Q.ne(i, j))
    assert got != 0
    _check(expr, got, [{X: M, **idx} for M in DIAGONAL])
    assert refine(X1[0, -1], Q.diagonal(X1)) != 0


def test_refusals_are_needed():
    """The witnesses behind the refusals: each refused rewrite is wrong somewhere."""
    _wrong = lambda e, r, w: pytest.raises(AssertionError, _check, e, r, [w])
    _wrong(Determinant(X), S.One, {X: REFLECTION})
    _wrong(conjugate(X)*X, Identity(2), {X: UNITARY2})
    _wrong(Adjoint(X)*X, Identity(2), {X: COMPLEX_ORTH})
    _wrong(Transpose(X*Y), X*Y, {X: SYMMETRIC[0], Y: Matrix([[0, 5], [5, 1]])})
    _wrong(Inverse(X*Y), Adjoint(Y)*Adjoint(X), {X: COMPLEX_ORTH, Y: UNITARY2})


@pytest.mark.xfail(reason="not a row: the canonical index order of a symmetric matrix's "
                          "element is a property of the printed form, not a hypothesis",
                   strict=True)
def test_symmetric_element_symbolic_order():
    assert refine(X[i, j], Q.symmetric(X)) == refine(X[j, i], Q.symmetric(X))


def test_table_size():
    from satrefine.handlers_identities import matrices as mod
    assert len(mod.RULES) == 30
