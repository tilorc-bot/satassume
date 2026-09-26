"""Case splits (phase 3, A4): the linkage pre-test and the shared real-part dummy."""
from sympy import And, Q, arg, floor, log, pi, symbols

from satrefine.identities.core import rewrite as _engine

x, y, z, w = symbols("x y z w")


def test_linked_follows_shared_symbols_through_the_conjuncts():
    groups = [c.free_symbols for c in And.make_args(Q.real(x) & Q.gt(x, y) & Q.positive(w) & Q.lt(y, z))]
    assert _engine._linked(x, groups) == {x, y, z}
    assert _engine._linked(w, groups) == {w}


def test_real_part_dummy_is_one_per_symbol():
    assert _engine._real_part_dummy(x) is _engine._real_part_dummy(x)
    assert _engine._real_part_dummy(x) != _engine._real_part_dummy(y)


def _explorations(monkeypatch, cand, assumptions):
    seen = []
    explore = _engine._explore

    def recording(e, a):
        seen.append(e)
        return explore(e, a)
    monkeypatch.setattr(_engine, "_explore", recording)
    return _engine.case_split(log(x*y), cand, assumptions), seen


def test_split_on_a_symbol_not_linked_to_a_node_is_not_explored(monkeypatch):
    # arg(y) holds no x and nothing links y to x: no sign case of x can collapse it
    # (and symmetrically for y and arg(x)), so neither split is explored
    cand = floor(arg(x)/pi) + arg(y)
    merged, seen = _explorations(monkeypatch, cand, Q.real(x) & Q.real(y))
    assert merged is None and seen == []


def test_a_stated_relation_links_the_symbols(monkeypatch):
    cand = floor(arg(x)/pi) + arg(y)
    merged, seen = _explorations(monkeypatch, cand, Q.real(x) & Q.real(y) & Q.gt(x, y))
    assert seen                             # linked through Q.gt(x, y): the split is tried
