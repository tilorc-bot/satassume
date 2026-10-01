"""The combined backend's guard on SymPy's ``orthogonal -> unitary`` fact (issue #67).

SymPy's matrix fact base states ``Implies(Q.orthogonal(x), Q.unitary(x))``,
true only for real matrices: ``Matrix([[5/4, 3*I/4], [-3*I/4, 5/4]])`` is
orthogonal (``A.T*A == I``) and not unitary.  Matrix queries go to SymPy, so
``refine(Adjoint(X)*X, Q.orthogonal(X))`` gave ``I``.  While the combined
backend asks SymPy, the fact base has ``Q.orthogonal & Q.real_elements ->
Q.unitary`` instead (``satrefine/identities/compat/backend.py``).
"""
from __future__ import annotations

import pytest
from sympy import Adjoint, I, Identity, Matrix, MatrixSymbol, Q, Rational, eye
from sympy.assumptions.ask import ask as sympy_ask

from satrefine import refine
from satrefine.identities.compat import backend
from satrefine.identities.compat.backend import ask

X = MatrixSymbol('X', 2, 2)


def test_the_counterexample():
    c, s = Rational(5, 4), Rational(3, 4)
    A = Matrix([[c, I*s], [-I*s, c]])
    assert A.T*A == eye(2) and A.H*A != eye(2)


def test_adjoint_product_of_orthogonal_is_unchanged():
    with backend.using("combined"):
        assert refine(Adjoint(X)*X, Q.orthogonal(X)) == Adjoint(X)*X


def test_adjoint_product_of_unitary_is_identity():
    with backend.using("combined"):
        assert refine(Adjoint(X)*X, Q.unitary(X)) == Identity(2)


def test_transpose_product_of_orthogonal_is_identity():
    with backend.using("combined"):
        assert refine(X.T*X, Q.orthogonal(X)) == Identity(2)


def test_adjoint_product_of_real_orthogonal_is_identity():
    with backend.using("combined"):
        assert refine(Adjoint(X)*X, Q.orthogonal(X) & Q.real_elements(X)) == Identity(2)


def test_differential_case():
    # differential, matrix mode, seed 2, case 1439: gave I + X.T
    e = X**(-1) + X*Adjoint(X)
    with backend.using("combined"):
        assert refine(e, Q.orthogonal(X)) != Identity(2) + X.T


# (proposition, assumptions, SymPy's answer, the guarded answer); the comments
# name the SymPy path that derived the wrong True
CASES = [
    (Q.unitary(X), Q.orthogonal(X), True, None),            # _ask_single_fact
    (Q.normal(X), Q.orthogonal(X), True, None),             # through unitary
    (Q.unitary(X.T), Q.orthogonal(X), True, None),          # a handler's _ask_recursive
    (Q.unitary(X*X), Q.orthogonal(X), True, None),
    (Q.unitary(X), Q.orthogonal(X) & Q.invertible(X), True, None),   # satask
    (Q.unitary(X), Q.orthogonal(X) & Q.real_elements(X), True, True),
    (Q.unitary(X), Q.unitary(X), True, True),
    (Q.invertible(X), Q.orthogonal(X), True, True),
    # consistent for a complex orthogonal matrix; SymPy raises "inconsistent"
    (Q.unitary(X), Q.orthogonal(X) & ~Q.unitary(X), ValueError, False),
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


def test_only_the_orthogonal_entry_changes():
    # the corrected single-fact table equals a full regeneration from the
    # corrected matrix facts
    from sympy import And, Symbol
    from sympy.assumptions.ask_generated import get_known_facts_dict
    from sympy.assumptions.assume import AppliedPredicate
    from sympy.assumptions.facts import generate_known_facts_dict, get_matrix_facts
    x = Symbol('x')
    pairs = backend._orthogonal_corrections()
    wrong = {w for w, _ in pairs}
    facts = And(*[a for a in get_matrix_facts(x).args if a not in wrong],
                *[r for _, r in pairs])
    regenerated = generate_known_facts_dict(sorted(facts.atoms(AppliedPredicate), key=str), facts)
    corrected = backend._corrected_facts_dict(get_known_facts_dict())
    for key, entry in regenerated.items():
        assert corrected[key] == entry, key
