"""Tests for the ``MatMul`` refine handler."""
from __future__ import annotations

import pytest

from sympy.assumptions import Q
from sympy.abc import x
from sympy.matrices import Matrix, eye
from sympy.matrices.expressions import Identity, MatMul, MatrixSymbol

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
    # X.T*X under Q.orthogonal(X): test_local_refinement (handlers_identities gives
    # Identity(2), SymPy the one-factor MatMul(Identity(2)); the same matrix).
    # conjugate(X)*X under Q.unitary(X): test_unitary_conjugate_times_matrix_is_not_identity.
    assert_refines_like_sympy(X.T * Y, Q.orthogonal(X) & Q.orthogonal(Y))
    assert_refines_like_sympy(X.T * X, True)


def test_local_refinement() -> None:
    # Upstream returns the one-factor ``MatMul(Identity(2))`` wrapper (it
    # does not auto-collapse in this SymPy pin); ``doit`` reaches ``I``.
    # handlers_identities (and v3) give Identity(2) itself.
    assert refine(X.T * X, Q.orthogonal(X)) in (MatMul(Identity(2)), Identity(2))
    assert refine(X.T * X, Q.orthogonal(X)).doit() == Identity(2)


@pytest.mark.original_wrong("conjugate(X)*X -> I for unitary X; that is X.H*X")
def test_unitary_conjugate_times_matrix_is_not_identity() -> None:
    # handlers (and SymPy's refine) cancel conjugate(X)*X; for the real rotation
    # ROT90 it is ROT90**2 = -I.  handlers_identities and v3 leave it.
    rot90 = Matrix([[0, -1], [1, 0]])
    assert rot90.conjugate() * rot90 == -eye(2)
    assert refine(X.conjugate() * X, Q.unitary(X)) == X.conjugate() * X


def test_scalar_factor_preserved() -> None:
    assert refine(2 * X.T * X, Q.orthogonal(X)) == 2 * Identity(2)


@pytest.mark.handlers("handlers")
def test_asks_factor() -> None:
    fake, log = recording_ask({
        str(Q.symmetric(X)): None,
        str(Q.orthogonal(X)): True,
    })
    with use_ask(fake):
        assert refine(X.T * X, Q.orthogonal(X)) == MatMul(Identity(2))
    assert Q.orthogonal(X) in [entry[0] for entry in log]


def test_non_cancelling_product_unchanged() -> None:
    assert refine(X.T * Y, Q.orthogonal(X) & Q.orthogonal(Y)) == X.T * Y


def test_unmet_assumption_unchanged() -> None:
    assert refine(X.T * X, Q.unitary(X)) == X.T * X
    assert refine(X.T * X, Q.real(x)) == X.T * X


def test_none_answers_unchanged() -> None:
    with use_ask(stub_ask({})):
        assert refine(X.T * X, Q.orthogonal(X)) == X.T * X
        assert refine(X.conjugate() * X, Q.unitary(X)) == X.conjugate() * X
