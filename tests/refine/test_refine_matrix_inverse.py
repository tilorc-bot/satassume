"""Tests for the ``Inverse`` refine handler."""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.abc import x
from sympy.matrices import Matrix
from sympy.matrices.expressions import Adjoint, MatrixSymbol

from satrefine import refine
from satrefine.testing.harness import (
    assert_refines_like_sympy,
    recording_ask,
    stub_ask,
    use_ask,
)

X = MatrixSymbol('X', 2, 2)
Y = MatrixSymbol('Y', 2, 2)


def test_reference_ask_fidelity() -> None:
    assert_refines_like_sympy(X.I, Q.orthogonal(X))
    # X**-1 under Q.unitary(X): see test_unitary_inverse_is_the_conjugate_transpose
    assert_refines_like_sympy(X.I, Q.symmetric(X))
    assert_refines_like_sympy(X.I, True)


def test_local_refinement() -> None:
    assert refine(X.I, Q.orthogonal(X)) == X.T


# The original ``handlers`` package got this wrong (removed in phase 3): X**-1 -> X.conjugate()
# for unitary X; the inverse is X.H
def test_unitary_inverse_is_the_conjugate_transpose() -> None:
    # handlers (and SymPy's refine) give the elementwise conjugate: for the real
    # rotation ROT90, conjugate(U) = U but U**-1 = U.T.  handlers_identities and
    # v3 give Adjoint(X), the conjugate transpose.
    rot90 = Matrix([[0, -1], [1, 0]])
    assert rot90.conjugate() != rot90.inv()
    assert refine(X.I, Q.unitary(X)) == Adjoint(X)


def test_asks_base_matrix() -> None:
    fake, log = recording_ask({str(Q.orthogonal(X)): True})
    with use_ask(fake):
        assert refine(X.I, Q.orthogonal(X)) == X.T
    # The first query is the base matrix; the dispatcher then refines the
    # returned ``X.T``, which asks ``Q.symmetric(X)`` again.
    assert log[0][0] == Q.orthogonal(X)


def test_unmet_assumption_unchanged() -> None:
    assert refine(X.I, Q.symmetric(X)) == X.I
    assert refine(X.I, Q.orthogonal(Y)) == X.I
    assert refine(X.I, Q.real(x)) == X.I


def test_none_answers_unchanged() -> None:
    with use_ask(stub_ask({})):
        assert refine(X.I, Q.orthogonal(X)) == X.I
        assert refine(X.I, Q.unitary(X)) == X.I
        assert refine(X.I, Q.singular(X)) == X.I
