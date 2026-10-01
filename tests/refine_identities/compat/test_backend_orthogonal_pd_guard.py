"""The combined backend's guard on SymPy's ``orthogonal -> positive_definite`` fact (issue #82).

SymPy's matrix fact base states ``Implies(Q.orthogonal(x),
Q.positive_definite(x))``, false even for real matrices: ``-eye(2)`` is
orthogonal and not positive definite.  While the combined backend asks SymPy,
the fact base has ``Q.orthogonal -> Q.invertible`` instead
(``satrefine/identities/compat/backend.py``).
"""
from __future__ import annotations

import pytest
from sympy import MatrixSymbol, Q, eye
from sympy.assumptions.ask import ask as sympy_ask

from satrefine.identities.compat import backend
from satrefine.identities.compat.backend import ask

X = MatrixSymbol('X', 2, 2)


def test_the_counterexample():
    A = -eye(2)
    assert A.T*A == eye(2) and not A.is_positive_definite


def test_combined_backend_ask():
    with backend.using("combined"):
        assert ask(Q.positive_definite(X), Q.orthogonal(X)) is None
        assert ask(Q.invertible(X), Q.orthogonal(X)) is True


# (proposition, assumptions, SymPy's answer, the guarded answer)
CASES = [
    (Q.positive_definite(X), Q.orthogonal(X), True, None),               # _ask_single_fact
    (Q.positive_definite(X.T), Q.orthogonal(X), True, None),             # _ask_recursive
    (Q.positive_definite(X), Q.orthogonal(X) & Q.invertible(X), True, None),   # satask
    (Q.positive_definite(X), Q.orthogonal(X) & Q.real_elements(X), True, None),
    (Q.invertible(X), Q.orthogonal(X), True, True),
    (Q.fullrank(X), Q.orthogonal(X), True, True),
    (Q.square(X), Q.orthogonal(X), True, True),
    (Q.singular(X), Q.orthogonal(X), False, False),
    (Q.unitary(X), Q.orthogonal(X) & Q.real_elements(X), True, True),
    (Q.positive_definite(X), Q.positive_definite(X), True, True),
    # consistent for -eye(2); SymPy raises "inconsistent"
    (Q.positive_definite(X), Q.orthogonal(X) & ~Q.positive_definite(X), ValueError, False),
]


@pytest.mark.parametrize("prop, assumptions, sympy_answer, guarded", CASES)
def test_guarded_answers(prop, assumptions, sympy_answer, guarded):
    assert backend._guarded_sympy_ask(prop, assumptions) is guarded
    # the guard is scoped to the combined backend: plain SymPy is unchanged
    if sympy_answer is ValueError:
        with pytest.raises(ValueError, match="inconsistent"):
            sympy_ask(prop, assumptions)
    else:
        assert sympy_ask(prop, assumptions) is sympy_answer


def test_corrected_orthogonal_entry():
    from sympy.assumptions.ask_generated import get_known_facts_dict
    implied, rejected = backend._corrected_facts_dict(get_known_facts_dict())[Q.orthogonal]
    assert Q.positive_definite not in implied and Q.unitary not in implied
    assert {Q.invertible, Q.fullrank, Q.square} <= implied and Q.singular in rejected
