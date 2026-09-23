"""Rules of :mod:`satrefine.handlers_v2.matrices`, checked against explicit
matrices: a rotation (orthogonal, ``det = 1``), a reflection (orthogonal,
``det = -1``), a unitary matrix that is *not* orthogonal, and a singular one."""
from __future__ import annotations

from sympy import (Adjoint, Determinant, HadamardProduct, I, Identity, Inverse, MatAdd,
                   Matrix, MatrixSymbol, Q, Trace, Transpose, ZeroMatrix)
from sympy.abc import i, j

from satrefine import refine

X = MatrixSymbol("X", 2, 2)
Y = MatrixSymbol("Y", 2, 2)
ROTATION = Matrix([[0, -1], [1, 0]])
REFLECTION = Matrix([[0, 1], [1, 0]])
UNITARY = Matrix([[0, I], [1, 0]])
SINGULAR = Matrix([[1, 2], [2, 4]])
UNIT_TRIANGULAR = Matrix([[1, 5], [0, 1]])


def explicit(expr, matrix):
    return expr.subs(X, matrix).doit()


class TestDeterminant:
    def test_T1_T3(self):
        assert refine(Determinant(X), Q.singular(X)) == 0
        assert explicit(Determinant(X), SINGULAR) == 0
        assert refine(Determinant(X), Q.unit_triangular(X)) == 1
        assert explicit(Determinant(X), UNIT_TRIANGULAR) == 1
        assert refine(Determinant(Inverse(X)), Q.invertible(X)) == 1 / Determinant(X)
        assert explicit(Determinant(Inverse(X)), ROTATION) == 1 / ROTATION.det()

    def test_orthogonal_and_unitary_determinants_are_not_simplified(self):
        assert refine(Determinant(X), Q.orthogonal(X)) == Determinant(X)
        assert refine(Determinant(X), Q.unitary(X)) == Determinant(X)
        assert REFLECTION.det() == -1 and REFLECTION * REFLECTION.T == Matrix.eye(2)
        assert UNITARY.det() == -I and UNITARY * UNITARY.H == Matrix.eye(2)


class TestInverse:
    def test_N1_orthogonal(self):
        assert refine(Inverse(X), Q.orthogonal(X)) == Transpose(X)
        assert refine(X**-1, Q.orthogonal(X)) == X.T
        for m in (ROTATION, REFLECTION):
            assert m.inv() == m.T

    def test_N2_unitary_is_the_conjugate_transpose(self):
        assert refine(Inverse(X), Q.unitary(X)) == Adjoint(X)
        assert UNITARY.inv() == UNITARY.H
        assert UNITARY.inv() != UNITARY.T and UNITARY.inv() != UNITARY.conjugate()

    def test_does_not_fire(self):
        assert refine(Inverse(X), Q.invertible(X)) == Inverse(X)
        assert refine(Inverse(X), Q.singular(X)) == Inverse(X)


class TestTransposeTrace:
    def test_R1(self):
        assert refine(Transpose(X), Q.symmetric(X)) == X
        assert refine(Transpose(X), Q.diagonal(X)) == X
        assert refine(X.T, Q.orthogonal(X)) == X.T
        assert refine(X + X.T, Q.symmetric(X)) == MatAdd(X, X)

    def test_C1_C2(self):
        assert refine(Trace(X), Q.zero(X)) == 0
        assert refine(Trace(X), Q.unit_triangular(X)) == 2
        assert UNIT_TRIANGULAR.trace() == 2
        assert refine(Trace(X), Q.symmetric(X)) == Trace(X)


class TestProductsAndSums:
    def test_A1(self):
        assert refine(X + Y, Q.zero(Y)) == X
        assert refine(X + Y, Q.zero(X) & Q.zero(Y)) == ZeroMatrix(2, 2)
        assert refine(X + Y, Q.symmetric(Y)) == X + Y

    def test_M1(self):
        assert refine(X * Y, Q.zero(Y)) == ZeroMatrix(2, 2)
        assert refine(HadamardProduct(X, Y), Q.zero(X)) == ZeroMatrix(2, 2)
        assert refine(HadamardProduct(X, Y), Q.symmetric(X)) == HadamardProduct(X, Y)

    def test_M2_orthogonal(self):
        assert refine(X * X.T, Q.orthogonal(X)) == Identity(2)
        assert refine(X.T * X, Q.orthogonal(X)) == Identity(2)
        assert refine(Y * X * X.T, Q.orthogonal(X)) == Y
        assert refine(X * X.T, Q.unitary(X)) == X * X.T
        assert UNITARY * UNITARY.T != Matrix.eye(2)

    def test_M2_unitary_uses_the_adjoint(self):
        assert refine(X * Adjoint(X), Q.unitary(X)) == Identity(2)
        assert refine(Adjoint(X) * X, Q.unitary(X)) == Identity(2)
        assert refine(X * X.conjugate(), Q.unitary(X)) == X * X.conjugate()
        assert UNITARY * UNITARY.conjugate() != Matrix.eye(2)
        assert UNITARY * UNITARY.H == Matrix.eye(2)

    def test_M2_inverse(self):
        assert refine(X * Inverse(X), Q.invertible(X)) == Identity(2)
        assert refine(Inverse(X) * X * Y, Q.invertible(X)) == Y
        assert refine(X * Inverse(X), Q.singular(X)) == X * Inverse(X)


class TestMatrixElement:
    def test_E1_E4(self):
        assert refine(X[i, j], Q.zero(X)) == 0
        assert refine(X[i, j], Q.diagonal(X) & Q.nonzero(i - j)) == 0
        assert refine(X[0, 1], Q.diagonal(X)) == 0
        assert refine(X[1, 0], Q.upper_triangular(X)) == 0
        assert refine(X[0, 1], Q.lower_triangular(X)) == 0
        assert refine(X[i, i], Q.unit_triangular(X)) == 1
        assert refine(X[0, 1], Q.upper_triangular(X)) == X[0, 1]
        assert UNIT_TRIANGULAR[1, 0] == 0 and UNIT_TRIANGULAR[1, 1] == 1

    def test_E5_symmetric_canonical_order(self):
        assert refine(X[1, 0], Q.symmetric(X)) == X[0, 1]
        assert refine(X[0, 1], Q.symmetric(X)) == X[0, 1]
        assert refine(X[j, i], Q.symmetric(X)) == refine(X[i, j], Q.symmetric(X))
        assert refine(X[i, j], Q.orthogonal(X)) == X[i, j]
