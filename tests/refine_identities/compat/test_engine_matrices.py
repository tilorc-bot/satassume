"""Matcher forms the ``matrices`` table needs from the engine.

Today ``bindings`` falls back to SymPy's ``match`` with ``Wild`` symbols put
in place of a ``MatrixSymbol``: it binds any expression and not the shape,
some matrix constructors reject the ``Wild`` (``MatAdd`` and
``HadamardProduct`` raise ``TypeError``), and a ``MatMul`` pattern never
matches.
"""
from __future__ import annotations

from sympy import (Adjoint, HadamardProduct, Identity, MatMul,
                   MatrixSymbol, Q, S, Transpose, ZeroMatrix, symbols)

from satrefine.identities.core.rewrite import rule_handler

c, i, j, m, q, s, x = symbols('c i j m q s x')
A = MatrixSymbol('A', m, m)
Z = MatrixSymbol('Z', m, q)
R = MatrixSymbol('R', m, q)
W = MatrixSymbol('W', q, s)
X = MatrixSymbol('X', 2, 2)
Y = MatrixSymbol('Y', 2, 2)
B = MatrixSymbol('B', 2, 3)
C = MatrixSymbol('C', 3, 2)


def test_matrix_pattern_binds_an_atom_and_its_shape():
    """A ``MatrixSymbol`` pattern binds a ``MatrixSymbol`` and its shape
    symbols bind that matrix's shape (``ZeroMatrix(q, m)`` on the right).
    It binds atoms only: ``ask`` wrongly calls ``X*Y`` symmetric for
    symmetric ``X``, ``Y``, so ``Transpose(A) -> A`` must not see products."""
    rule = rule_handler([(Transpose(Z), ZeroMatrix(q, m), Q.zero(Z))])
    assert rule(Transpose(B), Q.zero(B)) == ZeroMatrix(3, 2)
    sym = rule_handler([(Transpose(A), A, Q.symmetric(A))])
    assert sym(Transpose(X*Y), Q.symmetric(X) & Q.symmetric(Y)) is None


def test_one_term_and_the_rest_of_a_matrix_sum_or_hadamard_product():
    """``Z + R``: ``Z`` binds one term (an atom), ``R`` the sum of the others,
    whatever it is (a single term is itself, not ``MatAdd(term)``)."""
    W2 = MatrixSymbol('W2', 2, 2)
    rule = rule_handler([(Z + R, R, Q.zero(Z))])
    assert rule(X + Y + W2, Q.zero(X)) == Y + W2
    had = rule_handler([(HadamardProduct(Z, R), ZeroMatrix(m, q), Q.zero(Z))])
    assert had(HadamardProduct(X, Y), Q.zero(Y)) == ZeroMatrix(2, 2)


def test_scalar_factor_and_the_rest_of_a_product():
    """``c*Z`` over a ``MatMul``: ``c`` binds one scalar factor, ``Z`` the
    product of everything else (with its shape)."""
    rule = rule_handler([(c*Z, ZeroMatrix(m, q), Q.zero(c))])
    assert rule(x*X*Y, Q.zero(x)) == ZeroMatrix(2, 2)


def test_adjacent_run_in_a_product():
    """A ``MatMul`` pattern of matrix factors matches any run of adjacent
    factors; the right side replaces the run, scalars and the other factors
    stay in order, and the result is ``doit(deep=False)``'d so identities and
    zero matrices are absorbed."""
    orth = rule_handler([(A*Transpose(A), Identity(m), Q.orthogonal(A))])
    assert orth(2*X*X.T*Y, Q.orthogonal(X)) == 2*Y
    zero = rule_handler([(Z*W, ZeroMatrix(m, s), Q.zero(Z))])
    assert zero(B*C, Q.zero(B)) == ZeroMatrix(2, 2)
    uni = rule_handler([(Adjoint(A)*A, Identity(m), Q.unitary(A))])
    assert uni(MatMul(3, Y, Adjoint(X), X), Q.unitary(X)) == 3*Y
