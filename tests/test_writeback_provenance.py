"""Provenance writeback (#53 stage 3): the fact cache stays a memo of
``Engine.is_``.  ``Solver.provenance`` on a small reason DAG; facts derived
with a clause from outside their node's cone are not written; the
``"root-only"`` policy; a budget-truncated session writes nothing."""
import pytest

from satassume import Engine, DictCache, P, Implies, Not, allargs
from satassume.solver import BOTTOM, BlockOwner, Solver


def test_solver_provenance_through_a_reason_dag():
    s = Solver()
    for v in range(1, 7):
        s.new_var()
    s.owner = "B"
    s.add_clause([-1, 2])           # 1 -> 2, owned by B
    s.owner = "C"
    s.add_clause([-2, -5, 3])       # 2 & 5 -> 3, owned by C
    s.owner = BOTTOM
    s.add_clause([-3, 4])           # glue: unowned
    s.owner = "E"
    s.add_clause([5])               # a unit owned by E
    s.owner = "A"
    s.add_clause([1])               # a unit owned by A: propagates 2, 3, 4
    s.owner = "F"
    s.add_clause([-1, 6])           # 1 is true at root: the unit 6, shortened by -1
    s.owner = BOTTOM
    assert s.root_trail() == [5, 1, 2, 3, 4, 6]
    memo = {}
    assert s.provenance(1, memo) == {"A"}
    assert s.provenance(2, memo) == {"A", "B"}
    assert s.provenance(3, memo) == {"A", "B", "C", "E"}
    assert BOTTOM in s.provenance(4, memo)
    assert s.provenance(6, memo) == {"A", "F"}
    assert s.root_step(4) is None
    assert s.root_step(2) == ("B", [1])
    assert s.root_step(6) == ("F", [1])
    # the memo is the caller's, and reusable
    assert memo[3] == {"A", "B", "C", "E"}


def test_solver_provenance_unknown_unit_is_bottom():
    s = Solver()
    s.new_var()
    s.add_clause([1])               # no owner set
    assert s.provenance(1, {}) == {BOTTOM}


# nodes: 'x' (a leaf), ('sq', a) or ('add', a, b, ...): ~nonzero(sq) ->
# zero(a) is the parent's template speaking about its child (family C: a
# parent's structural fact)
def templates(node):
    if isinstance(node, tuple):
        kind, *args = node
        if kind == 'sq':
            return [Implies(Not(P('nonzero', node)), P('zero', args[0]))]
        if kind == 'add':
            return [Implies(allargs('positive', args), P('positive', node)),
                    Implies(allargs('real', args), P('real', node))]
    return []


def _engine(writeback="provenance", **kw):
    cache = DictCache()
    cache.put(('sq', 'x'), 'zero', True)
    cache.put('y', 'positive', True)
    cache.put('z', 'positive', True)
    return Engine(templates=templates, cache=cache, writeback=writeback, **kw), cache


def test_fact_from_a_foreign_clause_is_not_written_back():
    eng, cache = _engine()
    assert eng.is_(('sq', 'x'), 'nonzero') is False
    # zero(x) was derived at root by the parent's template: not x's own cone
    assert cache.get('x', 'zero', 'missing') == 'missing'
    assert eng.stats["writeback_refused"] >= 1
    # the parent's own facts are written
    assert cache.get(('sq', 'x'), 'nonzero') is False
    # and the same question agrees with a fresh engine
    fresh, _ = _engine()
    assert eng.is_('x', 'zero') is fresh.is_('x', 'zero') is None


def test_writeback_all_is_the_old_history_dependent_behaviour():
    eng, cache = _engine("all")
    eng.is_(('sq', 'x'), 'nonzero')
    assert cache.get('x', 'zero') is True
    assert eng.is_('x', 'zero') is True        # a fresh engine says None


def test_child_facts_of_its_own_cone_are_written():
    eng, cache = _engine()
    assert eng.is_(('add', 'y', 'z'), 'positive') is True
    assert cache.get('y', 'nonzero') is True     # y's own cached fact and rule block
    assert eng.stats["writeback_refused"] == 0


def test_root_only_writes_only_the_queried_node():
    eng, cache = _engine("root-only")
    assert eng.is_(('add', 'y', 'z'), 'positive') is True
    assert cache.get(('add', 'y', 'z'), 'positive') is True
    assert cache.get(('add', 'y', 'z'), 'real') is True    # the node's own facts
    assert cache.get('y', 'nonzero', 'missing') == 'missing'
    assert cache.get('x', 'zero', 'missing') == 'missing'
    eng.is_(('sq', 'x'), 'nonzero')
    assert cache.get('x', 'zero', 'missing') == 'missing'
    # contextual sessions write nothing
    assert eng.ask(P('real', 'w'), P('positive', 'w')) is True
    assert cache.facts('w') is None


def test_unknown_writeback_policy_raises():
    with pytest.raises(ValueError):
        Engine(templates=templates, writeback="sometimes")


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_truncated_session_writes_nothing(policy):
    node = ('add', ('add', 'x', 'w'), 'y')
    cache = DictCache()
    cache.put(node, 'positive', True)
    eng = Engine(templates=templates, cache=cache, discovery_budget=1, writeback=policy)
    assert eng.is_(node, 'real') is True      # the cached unit, by the rule block
    assert eng.last_budget_limited is True
    assert eng.stats["budget_limited"] == 1
    # neither the closure of the cached fact nor the answer is cached
    assert cache.facts(node) == {'positive': True}
    assert cache.facts('y') is None
    eng2 = Engine(templates=templates, cache=DictCache(), writeback=policy)
    eng2.is_(node, 'real')
    assert eng2.last_budget_limited is False


def test_home_shortcut_implies_provenance_in_cone():
    """Every fact the O(1) shortcut (Session._home_of) assigns a home to
    passes the exact provenance test (the walk) for that home."""
    sympy = pytest.importorskip("sympy")
    from satassume.engine import _FOREIGN
    x = sympy.Symbol('x', positive=True)
    y = sympy.Symbol('y', integer=True)
    eng = Engine()
    for e in (x * y + sympy.acos(x) - 1, sympy.exp(x) / (y ** 2 + 1)):
        s = eng._fresh_session()
        s.subject = e
        s.ensure(e)
        s.escalate()
        b = s.base[e]
        s.query_literal(b, search=False)
        assert not s.truncated
        n = 0
        for lit in s.solver.root_trail():
            v = abs(lit)
            slot = s.table.slots[v]
            h = s._home.get(v, _FOREIGN)
            if h is _FOREIGN:
                continue
            prov = s.solver.provenance(v, {})
            assert BOTTOM not in prov
            if type(slot) is tuple:
                assert h == slot[0]
                n += 1
            for o in prov:
                if type(o) is BlockOwner:
                    o = s.table.slots[o.base][0]
                assert o == h or s._in_cone(h, o)
        assert n > 0
