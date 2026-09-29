"""Wrong answers of SymPy's own ``ask`` that the rule tables do not work around.

The rows are the plain identities (``KroneckerDelta(i, j)`` is its definition,
``Adjoint(U)*U = I`` for unitary ``U``), so where SymPy's ``ask`` proves a false
hypothesis, ``refine`` gives a wrong answer.  Each test states the right answer
and is a strict xfail: when SymPy is fixed it passes, and the xfail must go.
"""
from __future__ import annotations

import pytest
from sympy import I, Matrix, MatrixSymbol, Q, Rational, ask, eye, oo, symbols

i, j = symbols('i j')
X = MatrixSymbol('X', 2, 2)

SYMPY_EQ_AT_NEG_OO = ("SymPy's ask proves Q.eq(i, j) for i = -oo and j <= 0, "
                      "though j = -3 is allowed and -oo != -3")
SYMPY_ORTHOGONAL_IS_UNITARY = ("SymPy's ask derives Q.unitary from Q.orthogonal, "
                               "false for a complex orthogonal matrix")
SYMPY_EQ_INCONSISTENT = ("SymPy's ask raises 'inconsistent assumptions' for Q.eq(i, j) under "
                         "Q.negative_infinite(i) & Q.nonpositive(j), which are consistent")


@pytest.mark.xfail(strict=True, reason=SYMPY_EQ_AT_NEG_OO)
def test_eq_is_not_proved_at_negative_infinity():
    assert ask(Q.eq(-oo, -3)) is False           # the case j = -3 of the assumptions below
    assert ask(Q.eq(i, j), Q.negative_infinite(i) & Q.extended_nonpositive(j)) is None


@pytest.mark.xfail(strict=True, reason=SYMPY_ORTHOGONAL_IS_UNITARY)
def test_orthogonal_does_not_imply_unitary():
    c, s = Rational(5, 4), Rational(3, 4)       # c**2 - s**2 = 1
    A = Matrix([[c, I*s], [-I*s, c]])
    assert A.T*A == eye(2) and A.H*A != eye(2)  # orthogonal, not unitary
    assert ask(Q.unitary(X), Q.orthogonal(X)) is None


@pytest.mark.xfail(strict=True, raises=ValueError, reason=SYMPY_EQ_INCONSISTENT)
def test_eq_under_an_infinite_and_a_finite_index_is_answered():
    assert ask(Q.real(j), Q.negative_infinite(i) & Q.nonpositive(j)) is True   # consistent
    assert ask(Q.eq(i, j), Q.negative_infinite(i) & Q.nonpositive(j)) is False
