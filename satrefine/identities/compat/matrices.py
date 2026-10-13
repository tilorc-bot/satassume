"""``Determinant``, ``HadamardProduct``, ``Inverse``, ``MatAdd``, ``MatMul``, ``MatrixElement``, ``Trace`` and ``Transpose``."""
from __future__ import annotations

from sympy import (Adjoint, Determinant, HadamardProduct, Identity, Inverse,
                   MatAdd, MatMul, MatrixSymbol, Q, S, Trace, Transpose,
                   ZeroMatrix, symbols)
from sympy.matrices.expressions.matexpr import MatrixElement

from ..rules._tables import add_rules
from .matrix_order import _Index, _SwappedOrder

c, zero, i, j, m, n, l, h = symbols('c zero i j m n l h')
A = MatrixSymbol('A', m, m)
S_ = MatrixSymbol('S', m, m)
D = MatrixSymbol('D', m, m)
E = MatrixSymbol('E', m, m)
O = MatrixSymbol('O', m, m)
U = MatrixSymbol('U', m, m)
V = MatrixSymbol('V', m, m)
G = MatrixSymbol('G', m, m)
T = MatrixSymbol('T', m, m)
Zs = MatrixSymbol('Zs', m, m)
M = MatrixSymbol('M', l, l)
N = MatrixSymbol('N', l, m)
X = MatrixSymbol('X', m, n)
R = MatrixSymbol('R', m, n)
Z = MatrixSymbol('Z', m, n)
Y = MatrixSymbol('Y', m, n)
W = MatrixSymbol('W', n, h)
ii, jj = _Index('i'), _Index('j')

TRANSPOSE = add_rules({Q.zero(Z), Q.symmetric(S_), Q.symmetric(M), Q.diagonal(D), Q.diagonal(E)}, [
    (Transpose(Z), ZeroMatrix(n, m)),
    (Transpose(S_), S_),
    (Transpose(S_*M*S_), S_*M*S_),
    (Transpose(N.T*M*N), N.T*M*N),
    (Transpose(D*E), D*E),
])

INVERSE = (
    add_rules({Q.orthogonal(O), Q.unitary(U)}, [
        (Inverse(O), O.T),
        (Inverse(O.T), O),
        (Inverse(U), Adjoint(U)),
    ])
    + add_rules({Q.unitary(U), Q.unitary(V)}, [
        (Inverse(U*V), Adjoint(V)*Adjoint(U)),
    ])
)

DETERMINANT = (
    add_rules({Q.singular(A) | (Q.zero(A) & Q.positive(m))}, [
        (Determinant(A), S.Zero),
    ])
    + add_rules({Q.unit_triangular(T)}, [
        (Determinant(T), S.One),
    ])
)

TRACE = add_rules({Q.zero(Zs)}, [
    (Trace(Zs), S.Zero),
])

MATADD = add_rules({Q.zero(Z), Q.zero(Y)}, [
    (Z + Y, ZeroMatrix(m, n)),
    (Z + R, R),
    (MatAdd(X, -X), ZeroMatrix(m, n)),
    (MatAdd(Z), ZeroMatrix(m, n)),
])

HADAMARD = add_rules({Q.zero(Z)}, [
    (HadamardProduct(Z, R), ZeroMatrix(m, n)),
])

MATMUL = (
    add_rules({Q.zero(zero)}, [
        (zero*X, ZeroMatrix(m, n)),
    ])
    + add_rules({Q.zero(X) | Q.zero(W)}, [
        (X*W, ZeroMatrix(m, h)),
    ])
    + add_rules({Q.orthogonal(O)}, [
        (O.T*O, Identity(m)),
        (O*O.T, Identity(m)),
    ])
    + add_rules({Q.unitary(U)}, [
        (Adjoint(U)*U, Identity(m)),
        (U*Adjoint(U), Identity(m)),
    ])
    + add_rules({Q.invertible(G)}, [
        (MatMul(Inverse(G), G), Identity(m)),
        (MatMul(G, Inverse(G)), Identity(m)),
        (MatMul(A, A), A**2),
        (c*X, c*X),
    ])
)

MATRIXELEMENT = (
    add_rules({Q.zero(Z)}, [
        (MatrixElement(Z, i, j), S.Zero),
    ])
    + add_rules({Q.diagonal(D),
                 Q.ne(i, j) | Q.nonzero(i - j),
                 (Q.nonnegative(i) & Q.nonnegative(j)) | (Q.negative(i) & Q.negative(j))
                 | (Q.nonzero(i - j - m) & Q.nonzero(i - j + m))}, [
        (MatrixElement(D, i, j), S.Zero),
    ])
    + add_rules({Q.symmetric(S_), _SwappedOrder(ii, jj)}, [
        (MatrixElement(S_, ii, jj), MatrixElement(S_, jj, ii)),
    ])
)

RULES: list[tuple] = (TRANSPOSE + INVERSE + DETERMINANT + TRACE + MATADD
                      + HADAMARD + MATMUL + MATRIXELEMENT)
