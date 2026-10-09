"""VarTable builds node atoms lazily (perf round 3, B2a): the atom of every
variable, and what the memo of ``is_`` holds, are what the eager table gave."""
from sympy import Symbol, symbols

from satassume.knowledge.compile import VarTable
from satassume.engine import Engine
from satassume.sat.formula import P
from satassume.knowledge.rules import BASIS
from satassume.sympy_api import ask
from sympy import Q


def test_atoms_match_eager_layout():
    x, y = symbols("x y")
    t = VarTable()
    bx = t.node_base(x)
    a = t.aux()
    c = t.var(P("my_custom_pred", y))
    by = t.node_base(y)
    assert t.node_base(x) == bx
    expected = [None] + [P(p, x) for p in BASIS] + [None, P("my_custom_pred", y)] \
        + [P(p, y) for p in BASIS]
    assert len(t) == len(expected) - 1
    assert t.atom_of == expected
    for v in range(1, len(expected)):
        assert t.atom(v) == expected[v]
    assert t.atom(a) is None and t.atom(c) == P("my_custom_pred", y)
    assert t.var(P("extended_positive", y)) == by + BASIS.index("extended_positive")
    assert t.lit_name(-(bx + BASIS.index("zero"))) == "~" + repr(P("zero", x))
    assert t.new_nodes == [x, y] and t.new_custom == [P("my_custom_pred", y)]


def test_memo_caches_the_answer_only():
    # was test_writeback_caches_node_facts: the queried node's root facts
    # were written back (writeback="root-only" before #97 P2)
    x = Symbol("x", positive=True)
    eng = Engine()
    assert eng.is_(x + 1, "positive") is True
    # only the answer is memoized, under the queried node: nothing about the
    # argument, and no other fact of x + 1 (its vocabulary is not written)
    assert eng.cache.store == {x + 1: {"positive": True}}
    assert eng.cache.get(x, "positive", "missing") == "missing"
    assert eng.is_(x, "positive") is True
    assert eng.cache.get(x + 1, "positive") is True
    assert eng.cache.get(x + 1, "negative", "missing") == "missing"
    # a fact derived at root while answering is recomputed, then memoized
    hits, sessions = eng.stats["cache_hits"], eng.stats["sessions"]
    assert eng.is_(x + 1, "negative") is False
    assert eng.stats["cache_hits"] == hits and eng.stats["sessions"] == sessions + 1
    assert eng.cache.get(x + 1, "negative") is False
    assert eng.is_(x + 1, "negative") is False
    assert eng.stats["cache_hits"] == hits + 1 and eng.stats["sessions"] == sessions + 1
    assert ask(Q.nonzero(x + 1)) is True
