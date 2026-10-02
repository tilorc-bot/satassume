"""Review tests for #97 P3 (branch ``issue-97/p3-theory-scope`` at 26c3d3e).

Each test pins a claim of the P3 report or of a comment in the diff that the
review found to be false on the reviewed head; they are expected to fail
there (see ``reports/p3-review.md``).
"""
from sympy import Q, S, Symbol, symbols
from sympy.assumptions import Predicate

from satassume import extensions as X
from satassume.engine import CONSISTENT, DictCache, Engine
from satassume.formula import Implies, P
from satassume.sympy_api import _formula, ask

x, y, z = symbols("x y z")


def eng():
    return Engine(cache=DictCache(), relevance=False)


def F(e):
    return _formula(e, True, True)


# A plain unary set with a sign atom on a sum: consistent, and its check
# says so when the session has no glue.
A = Q.real(x) & Q.real(y) & Q.positive(x + y - 1)


def test_set_verdict_does_not_depend_on_the_query_scope():
    """``_build_context``'s comment and the P3 report: "the set's check
    assumes only the set's own glue, so its verdict is a function of the
    set whatever the query's scope".  With the glue present at construction
    the check exhausts LRA's branch budget (``Engine._exhausted``) and the
    verdict is UNKNOWN instead of CONSISTENT."""
    e = eng()
    s0, _ = e._build_context(F(A))
    s1, _ = e._build_context(F(A), _formula(Q.lt(0, z), True))
    assert s0.verdict is CONSISTENT
    assert s1.verdict is s0.verdict


def test_set_verdict_does_not_depend_on_a_transfer_scope_either():
    """The same with a query whose scope engages predicate transfer at
    construction (``scope.transfer``): the check still sees only the set
    (P3-fix1)."""
    e = eng()
    s0, _ = e._build_context(F(A))
    s1, _ = e._build_context(F(A), _formula(Q.eq(x, z), True))
    assert s0.verdict is CONSISTENT
    assert s1.verdict is s0.verdict
    assert s1.xfer is not None and s1.relations.linked


def test_the_query_still_gets_the_set_links_after_the_check():
    """Deferring the set's links to after the check (``Session.link_set``)
    loses no answer: the set's sum is linked for the query (P3-fix1)."""
    e = eng()
    assert ask(Q.lt(0, x + y), A, e) is True
    assert ask(Q.positive(x + y), A, e) is True
    assert e.stats["scope_misses"] == 0


def test_verdict_memo_is_not_history_dependent():
    """``Engine.verdict(a)`` after a relational query under ``a`` must equal
    the verdict a fresh engine computes (the memo is "a function of the
    set")."""
    e = eng()
    assert ask(Q.lt(0, x + y), A, e) is True
    assert e.verdict(F(A)) is eng().verdict(F(A)) is CONSISTENT


def test_extension_relation_atom_is_covered_by_the_scope():
    """``Session._custom``'s comment: the fallback creation of ``Relations``
    is "never on Engine.ask's path".  An extension fact that brings a
    relation atom (spec open point 2) reaches it from ``Engine.ask``."""
    Qm = Predicate("mersenne")
    X.register("mersenne", Symbol)(lambda s: Implies(P("mersenne", s), P("lt", (S.One, s))))
    try:
        e = eng()
        assert ask(Qm(x), Qm(x), e) is True
        assert e.stats["scope_misses"] == 0
    finally:
        X.unregister("mersenne")
