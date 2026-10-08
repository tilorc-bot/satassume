"""An inconsistent assumption set raises even when propagation settles the query.

``Session.query_literal`` answers from unit propagation first.  Propagation
need not find the conflict of an inconsistent set (since the basis encoding,
the Add-with-``oo`` rules distribute derived premises, so a set that is
inconsistent only through them and the relation glue propagates cleanly), so
an answer that propagation settled is returned only after the assumptions are
confirmed consistent (``Solver.consistent``), as ``Solver.entails`` does.
``ask_ref`` (the specification) raises for all of these.
"""
import pytest
from sympy import Not, Q, Symbol, oo, symbols

from satassume.ref import ref_outcome
from satassume.solver import Solver
from satassume.sympy_api import ask

x, y, z, w = symbols("x y z w")
n = Symbol("n", integer=True)

CASES = [
    # propagation settles gt(...) to True from extended_positive
    (Q.gt(x + z + oo, 0), Q.extended_positive(x + z + oo) & Q.finite(x + z + oo)),
    (Q.integer(n) | Q.ge(w, z), Q.positive(x + y + z + oo)),
    (~Q.noninteger(n) | ~Q.ge(w * z, z), Q.positive(2 * x + y + z + oo)),
    (Q.ge(w, z), Q.extended_positive(x + z + oo) & Q.finite(x + z + oo)),
]


@pytest.mark.parametrize("p, a", CASES)
def test_inconsistent_set_raises(p, a):
    assert ref_outcome(p, a) == "ValueError"
    with pytest.raises(ValueError):
        ask(p, a)


def test_same_answers_as_ref_under_the_set():
    # the set is inconsistent only with the relation glue of a query that
    # mentions a relation (cone(p) | cone(A)): the others answer, as in ask_ref
    a = Q.extended_positive(x + z + oo) & Q.finite(x + z + oo)
    for p in (Q.gt(x + z + oo, 0), Q.ge(w, z), Q.extended_positive(x + z + oo),
              Q.finite(x + z + oo), Not(Q.finite(x + z + oo)), Q.real(w)):
        try:
            r = str(ask(p, a))
        except ValueError:
            r = "ValueError"
        assert r == ref_outcome(p, a), p


def test_solver_consistent_beyond_propagation():
    # q is implied by c through propagation; the clauses over a, b are
    # unsatisfiable, which propagation does not see
    s = Solver()
    for c in ([-3, 4], [1, 2], [1, -2], [-1, 2], [-1, -2]):
        s.add_clause(c)
    assert 4 in s.implied([3])
    assert s.consistent([3]) is False
    with pytest.raises(ValueError):
        s.entails(4, [3])


def test_solver_consistent_satisfiable():
    s = Solver()
    for c in ([-3, 4], [1, 2], [-1, -2]):
        s.add_clause(c)
    assert s.consistent([3]) is True
    assert s.consistent([3, -4]) is False
    assert s.entails(4, [3]) is True
