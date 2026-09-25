"""VarTable builds node atoms lazily (perf round 3, B2a): the atom of every
variable, and what writeback caches, are what the eager table gave."""
from sympy import Symbol, symbols

from satassume.compile import VarTable
from satassume.engine import Engine
from satassume.formula import P
from satassume.rules import PREDICATES
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
    expected = [None] + [P(p, x) for p in PREDICATES] + [None, P("my_custom_pred", y)] \
        + [P(p, y) for p in PREDICATES]
    assert len(t) == len(expected) - 1
    assert t.atom_of == expected
    for v in range(1, len(expected)):
        assert t.atom(v) == expected[v]
    assert t.atom(a) is None and t.atom(c) == P("my_custom_pred", y)
    assert t.var(P("positive", y)) == by + PREDICATES.index("positive")
    assert t.lit_name(-(bx + PREDICATES.index("zero"))) == "~" + repr(P("zero", x))
    assert t.new_nodes == [x, y] and t.new_custom == [P("my_custom_pred", y)]


def test_writeback_caches_node_facts():
    x = Symbol("x", positive=True)
    eng = Engine()
    assert eng.is_(x + 1, "positive") is True
    # facts derived at root about the argument are written back under the node
    assert eng.cache.get(x, "positive") is True
    assert eng.cache.get(x + 1, "positive") is True
    assert eng.cache.get(x + 1, "negative") is False
    assert ask(Q.nonzero(x + 1)) is True
