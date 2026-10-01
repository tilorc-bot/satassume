"""Provenance writeback (#53 stage 3): the fact cache stays a memo of
``Engine.is_``.  ``Solver.provenance`` on a small reason DAG; facts derived
with a clause from outside their node's cone are not written (a clause the
solver shortened with a foreign root fact included); facts of a node whose
cone does not fit the discovery budget are not written; the
``"root-only"`` policy (the default: no provenance bookkeeping); a query
over the discovery budget is None, whatever is cached, and writes
nothing."""
import pytest

from satassume import Engine, DictCache, P, Implies, Not, And, Or, allargs
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


def test_root_only_is_the_default_and_keeps_no_provenance():
    eng = Engine(templates=templates, cache=DictCache())
    assert eng.writeback == "root-only"
    s = eng._fresh_session()
    assert not s.track and not s.solver.track_owners
    eng, cache = _engine("root-only")
    node = ('add', 'y', 'z')
    s = eng._fresh_session()
    s.ensure(node)
    s.escalate()
    s.query_literal(s.base[node], search=True)
    sv = s.solver
    assert sv.owner is BOTTOM
    assert not sv._cowner and not sv._uowner and not sv._cante
    # a complete session within the budget: written with no cone test
    assert eng.is_(node, 'positive') is True
    assert cache.get(node, 'real') is True
    assert eng.stats["writeback_budget"] == 0


def test_unknown_writeback_policy_raises():
    with pytest.raises(ValueError):
        Engine(templates=templates, writeback="sometimes")


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_query_over_the_budget_is_none_whatever_is_cached(policy):
    # the cone of node (3 nodes) outweighs the budget: None before any
    # session work (#53 task 6), although a cached fact of node decides it
    node = ('add', ('add', 'x', 'w'), 'y')
    cache = DictCache()
    cache.put(node, 'positive', True)
    eng = Engine(templates=templates, cache=cache, discovery_budget=1, writeback=policy)
    assert eng.is_(node, 'real') is None
    assert eng.last_budget_limited is True
    assert eng.stats["budget_limited"] == 1 and eng.stats["sessions"] == 0
    # so is a cached question: the answer is a function of the query
    assert eng.is_(node, 'positive') is None and eng.last_budget_limited
    assert eng.ask(P('real', node)) is None and eng.last_budget_limited
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
    eng = Engine(writeback="provenance")
    for e in (x * y + sympy.acos(x) - 1, sympy.exp(x) / (y ** 2 + 1)):
        s = eng._fresh_session()
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


# --------------------------------------------------------------------------
# retry 1 of the reviews: shortened clauses, and the budget of a fresh is_
# --------------------------------------------------------------------------

def _not_memos(eng, mk):
    """The cached facts of ``eng`` that a fresh engine (``mk()``) answers
    otherwise, or answers only budget-limited: ``[(node, pred, cached,
    fresh, fresh budget-limited)]``."""
    bad = []
    for node, facts in list(eng.cache.store.items()):
        for pred, v in facts.items():
            fresh = mk()
            r = fresh.is_(node, pred)
            if r is not v or fresh.last_budget_limited:
                bad.append((node, pred, v, r, fresh.last_budget_limited))
    return bad


# r1 (opus-high review): F's template speaks about c; D's clause
# ~zero(c) | ~real(e) | positive(D) is added once zero(c) is true at root,
# so the solver stores real(e) -> positive(D), owned by D; F is not in
# cone(D), and the fresh is_(D, positive) is None.
F1 = ('f', 'c')
D1 = ('d', 'c', 'e')


def _r1_templates(node):
    if node == F1:
        return [Implies(Not(P('nonzero', F1)), P('zero', 'c'))]
    if node == D1:
        return [Implies(And(P('zero', 'c'), P('real', 'e')), P('positive', D1))]
    return []


def _r1_engine(policy="provenance"):
    cache = DictCache()
    cache.put('e', 'real', True)
    cache.put(F1, 'nonzero', False)
    return Engine(templates=_r1_templates, cache=cache, writeback=policy)


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_shortened_clause_keeps_its_foreign_antecedent(policy):
    eng = _r1_engine(policy)
    # one session that visits F before D
    assert eng.ask(Or(P('nonzero', F1), P('positive', D1))) is True
    assert eng.cache.get(D1, 'positive', 'missing') == 'missing'
    if policy == "provenance":
        assert eng.stats["writeback_refused"] > 0
    assert eng.is_(D1, 'positive') is None
    assert _r1_engine(policy).is_(D1, 'positive') is None
    assert _not_memos(eng, lambda: _r1_engine(policy)) == []


def _chain_engine(budget, policy="provenance"):
    cache = DictCache()
    cache.put('y', 'positive', True)
    return Engine(templates=templates, cache=cache, discovery_budget=budget, writeback=policy)


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_reused_session_past_the_budget_writes_only_facts_of_cones_that_fit(policy):
    """a_chain (fable review), with the budget a test on the query's cone
    (#53 task 6): the same assumptions reuse one contextual session, one
    node larger per call; a query whose cone (with the assumptions')
    outweighs the budget is None before any session work, warm as fresh,
    and the facts of a node whose cone does not fit are never written."""
    eng = _chain_engine(4, policy)
    e = 'y'
    for k in range(4):
        e = ('add', e)
        r = eng.ask(P('positive', e), P('real', 'w'))
        over = k + 3 > 4                    # cone(e): k + 2 nodes, and w
        assert r is (None if over else True)
        assert eng.last_budget_limited is over
        fresh = _chain_engine(4, policy)
        assert fresh.ask(P('positive', e), P('real', 'w')) is r
        assert fresh.last_budget_limited is over
    if policy == "provenance":
        assert eng.cache.get(('add', 'y'), 'positive') is True      # cone of 2 fits
    assert eng.cache.facts(('add', ('add', ('add', ('add', 'y'))))) is None   # 5 does not
    assert _not_memos(eng, lambda: _chain_engine(4, policy)) == []
    fresh = _chain_engine(4, policy)
    assert fresh.is_(e, 'positive') is None and fresh.last_budget_limited
    assert eng.is_(e, 'positive') is None and eng.last_budget_limited


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_reused_session_past_the_budget_sympy(policy):
    """a_final (fable review), on SymPy nodes: exp(exp(exp(x))) has a cone
    of 4 nodes, the budget is 3; warm and fresh agree on every answer and
    on ``last_budget_limited`` (DESIGN.md 2.5 (i) is gone)."""
    sympy = pytest.importorskip("sympy")
    x = sympy.Symbol('x', positive=True)
    y = sympy.Symbol('y')
    eng = Engine(discovery_budget=3, writeback=policy)
    e = x
    for _ in range(3):
        e = sympy.exp(e)
        r = eng.ask(P('positive', e), P('real', y))     # a reused session
        fresh = Engine(discovery_budget=3, writeback=policy)
        assert fresh.ask(P('positive', e), P('real', y)) is r
        assert fresh.last_budget_limited is eng.last_budget_limited
    assert eng.last_budget_limited
    assert eng.cache.get(e, 'positive', 'missing') == 'missing'
    assert _not_memos(eng, lambda: Engine(discovery_budget=3, writeback=policy)) == []
    fresh = Engine(discovery_budget=3, writeback=policy)
    r = fresh.is_(e, 'positive')
    assert r is None and fresh.last_budget_limited
    # the warm is_ is the fresh one: over the budget, whatever is cached
    w = eng.is_(e, 'positive')
    assert w is None and eng.last_budget_limited
    assert eng.cache.get(e, 'positive', 'missing') == 'missing'


# b_trunc (fable review): facts written by an earlier writeback of a session
# whose later escalation truncates; the cone rule does not depend on the
# session's own truncation
def _bt_templates(node):
    if isinstance(node, tuple):
        kind, *args = node
        if kind == 'f':
            return [Implies(P('positive', args[0]), P('positive', node)),
                    Implies(P('real', args[0]), P('real', node))]
        if kind == 'add':
            return [Implies(allargs('positive', args), P('positive', node)),
                    Implies(allargs('real', args), P('real', node)),
                    Implies(allargs('integer', args), P('integer', node))]
    return []


def _bt_engine(budget):
    cache = DictCache()
    for s in 'abcdefg':
        cache.put(s, 'positive', True)
    cache.put('a', 'integer', True)
    return Engine(templates=_bt_templates, cache=cache, discovery_budget=budget)


@pytest.mark.parametrize("budget", [2, 3, 4, 6])
def test_cache_stays_a_memo_when_sessions_truncate(budget):
    eng = _bt_engine(budget)
    wide = ('add', ('f', 'a'), ('f', 'b'), ('f', 'c'), ('f', 'd'), ('f', 'e'))
    seq = [(wide, 'integer'), (wide, 'positive'), (('f', wide), 'real'),
           (('add', 'a', 'b'), 'integer'), (('f', ('f', ('f', 'a'))), 'real'),
           (('add', ('f', 'a'), 'g'), 'integer')]
    for node, pred in seq:
        eng.is_(node, pred)
        eng.ask(P(pred, node), P('real', 'zz'))
    assert _not_memos(eng, lambda: _bt_engine(budget)) == []


# a node whose query is decided before escalation, with a parked template
# about a long chain: its cone (5 objects) is larger than the budget (2)
# although its session is not truncated
DP = ('p', 'a', ('add', ('add', 'z')))


def _parked_templates(node):
    if node == DP:
        return [Implies(P('positive', 'a'), P('positive', DP)),
                Implies(P('integer', DP[2]), P('integer', DP))]   # parked for positive
    return templates(node)


def _parked_engine(budget, policy):
    cache = DictCache()
    cache.put('a', 'positive', True)
    return Engine(templates=_parked_templates, cache=cache, discovery_budget=budget,
                  writeback=policy)


@pytest.mark.parametrize("policy", ["provenance", "root-only"])
def test_answer_decided_with_work_parked_is_cached_only_if_the_cone_fits(policy):
    # the cone of DP (5 objects) outweighs the budget (2): None, although
    # propagation would decide it before escalation (#53 task 6)
    eng = _parked_engine(2, policy)
    assert eng.is_(DP, 'positive') is None
    assert eng.last_budget_limited is True
    assert eng.cache.facts(DP) is None
    assert _not_memos(eng, lambda: _parked_engine(2, policy)) == []
    eng = _parked_engine(5, policy)
    assert eng.is_(DP, 'positive') is True
    assert eng.cache.get(DP, 'positive') is True
    assert eng.stats["writeback_budget"] == 0


def test_cone_of_a_node_and_the_budget():
    """Session._cone: the cone if its weight fits the budget; a relation
    atom never fits."""
    eng = _chain_engine(3)
    s = eng._fresh_session()
    chain = ('add', ('add', 'y'))
    assert s._cone(chain) == frozenset([chain, ('add', 'y'), 'y'])
    assert s._cone(('add', chain)) is None              # 4 > 3
    assert s._in_cone(chain, 'y') and not s._in_cone(('add', 'y'), chain)
    s2 = eng._fresh_session()
    s2.kids[('r',)] = ({P('lt', ('y', 'w'))}, 1)
    assert s2._cone(('r',)) is None


def test_cache_hit_resets_last_budget_limited():
    eng, cache = _engine(discovery_budget=1)
    eng.is_(('add', ('add', 'x', 'w'), 'y'), 'real')
    assert eng.last_budget_limited is True
    assert eng.is_('y', 'positive') is True               # a cache hit
    assert eng.last_budget_limited is False
