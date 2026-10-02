"""The fact cache is a pure memo of ``Engine.is_`` (issue #97, P2).

``Engine.is_(node, pred)`` memoizes its own answer, True or False, never
None, keyed on the node and the registry epoch; nothing else writes to the
caches (no session writes its root facts back) and no session reads them
(no cached fact is asserted as a unit clause).  The model of every test
here is the harness ``audit`` mode (``harness.checker.audit_cache``): after
any stream of queries, every cached fact is what a fresh engine derives
context-free for the same node.

History: #53 stage 3 added provenance writeback (``writeback="provenance"``
and ``"all"``: every root fact of a session, with owner tracking and a
provenance test per fact, ``Session.writeback``); P2 removed those
policies.  The ``Solver.provenance`` tests stay: the solver's reason DAG
walk is still part of the solver.
"""
import itertools

import pytest

from satassume import Engine, DictCache, P, Implies, Not, And, Or, allargs
from satassume.solver import BOTTOM, Solver


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


# nodes: 'x' (a leaf with no declared fact), 'y' and 'z' (leaves declared
# positive), ('sq', a) (declared zero; ~nonzero(sq) -> zero(a) is the
# parent's template speaking about its child: family C, a parent's
# structural fact) or ('add', a, b, ...).  Declared facts come from the
# templates, as a Symbol's assumptions0 do: a cache given to an engine is
# a memo, never an input to a session.
def templates(node):
    if isinstance(node, tuple):
        kind, *args = node
        if kind == 'sq':
            return [P('zero', node),
                    Implies(Not(P('nonzero', node)), P('zero', args[0]))]
        if kind == 'add':
            return [Implies(allargs('positive', args), P('positive', node)),
                    Implies(allargs('real', args), P('real', node))]
    if node in ('y', 'z'):
        return [P('positive', node)]
    return []


POLICIES = ["root-only", "none"]


def _engine(writeback="root-only", **kw):
    cache = DictCache()
    return Engine(templates=templates, cache=cache, writeback=writeback, **kw), cache


def _not_memos(eng, mk):
    """The cached facts of ``eng`` (both caches) that are not what a fresh
    engine (``mk()``) answers, or that it answers only budget-limited, or
    that are not True or False: ``[(node, pred, cached, fresh, fresh
    budget-limited)]``.  The harness ``audit`` mode, on one engine."""
    bad = []
    for cache in (eng.cache, eng.custom_cache):
        for node, facts in list(cache.store.items()):
            for pred, v in facts.items():
                fresh = mk()
                r = fresh.is_(node, pred)
                if v not in (True, False) or r is not v or fresh.last_budget_limited:
                    bad.append((node, pred, v, r, fresh.last_budget_limited))
    return bad


# --------------------------------------------------------------------------
# what is memoized: the answer of is_, and nothing else
# --------------------------------------------------------------------------

def test_memo_holds_the_answer_of_is_only():
    eng, cache = _engine()
    node = ('add', 'y', 'z')
    assert eng.is_(node, 'positive') is True
    # the session derived real(node), positive(y), nonzero(y), ... at the
    # root: none of it is a memo of is_, so none of it is written
    assert cache.store == {node: {'positive': True}}
    assert cache.get(node, 'real', 'missing') == 'missing'
    assert cache.facts('y') is None and cache.facts('z') is None
    assert eng.is_(node, 'real') is True
    assert eng.is_('y', 'nonzero') is True
    assert cache.store == {node: {'positive': True, 'real': True}, 'y': {'nonzero': True}}
    assert _not_memos(eng, lambda: _engine()[0]) == []


def test_child_fact_derived_by_the_parent_is_not_memoized():
    eng, cache = _engine()
    assert eng.is_(('sq', 'x'), 'nonzero') is False
    # zero(x) was derived at the root by the parent's template (not x's own
    # cone): a fresh is_('x', 'zero') is None, and so is this engine's
    assert cache.store == {('sq', 'x'): {'nonzero': False}}
    fresh, _ = _engine()
    assert eng.is_('x', 'zero') is fresh.is_('x', 'zero') is None
    assert cache.facts('x') is None
    assert _not_memos(eng, lambda: _engine()[0]) == []


def test_memo_never_holds_none():
    eng, cache = _engine()
    assert eng.is_('x', 'zero') is None          # nothing is known about x
    assert eng.is_('x', 'positive') is None
    assert cache.facts('x') is None
    assert eng.stats["cache_hits"] == 0
    # a second ask is computed again, and again not stored
    assert eng.is_('x', 'zero') is None
    assert eng.stats["cache_hits"] == 0 and cache.store == {}


@pytest.mark.parametrize("policy", POLICIES)
def test_sessions_write_nothing(policy):
    eng, cache = _engine(policy)
    # a context-free ask runs in a fresh session, not through is_
    assert eng.ask(P('positive', ('add', 'y', 'z'))) is True
    assert eng.ask(P('zero', 'x'), P('real', 'w')) is None
    assert eng.ask(P('real', 'w'), P('positive', 'w')) is True
    assert cache.store == {} and eng.custom_cache.store == {}


def test_sessions_read_nothing():
    """A cache given to an engine is a memo of is_ (is_ serves it), never
    an input to a session: a fact in it that the templates do not give is
    not asserted as a unit clause, so a contextual or context-free ask of
    the same question answers as a fresh engine with an empty cache."""
    eng, cache = _engine()
    cache.put('x', 'zero', True)
    eng.custom_cache.put('x', 'mine', True)
    assert eng.is_('x', 'zero') is True                   # the memo
    assert eng.is_('x', 'mine') is True
    assert eng.stats["cache_hits"] == 2 and eng.stats["sessions"] == 0
    fresh, _ = _engine()
    assert eng.ask(P('zero', 'x')) is fresh.ask(P('zero', 'x')) is None
    assert eng.ask(P('mine', 'x')) is fresh.ask(P('mine', 'x')) is None
    assert eng.ask(P('nonzero', ('sq', 'x')), P('real', 'w')) is \
        fresh.ask(P('nonzero', ('sq', 'x')), P('real', 'w')) is False
    # a cached fact that contradicts the templates is not an inconsistency
    # of any session (it never enters one)
    cache.put('y', 'positive', False)
    assert eng.ask(P('positive', 'y')) is True
    assert eng.ask(P('real', 'y'), P('positive', 'y')) is True
    assert eng.ask(P('positive', 'y'), P('real', 'w')) is True


def test_memo_is_keyed_on_the_registry_epoch():
    from satassume.epoch import EPOCH, bump
    eng, cache = _engine()
    assert eng.is_(('add', 'y', 'z'), 'positive') is True
    assert cache.store and cache._epoch == EPOCH[0]
    bump()
    assert eng.is_('y', 'nonzero') is True              # drops the stale memo
    assert cache._epoch == EPOCH[0]
    assert cache.store == {'y': {'nonzero': True}}
    assert eng.stats["version_clears"] == 1


# --------------------------------------------------------------------------
# the writeback setting
# --------------------------------------------------------------------------

def test_root_only_is_the_default_and_sessions_track_no_owners():
    eng = Engine(templates=templates, cache=DictCache())
    assert eng.writeback == "root-only"
    s = eng._fresh_session()
    assert not hasattr(s, "track") and not s.solver.track_owners
    eng, cache = _engine()
    node = ('add', 'y', 'z')
    s = eng._fresh_session()
    s.ensure(node)
    s.escalate()
    s.query_literal(s.base[node], search=True)
    sv = s.solver
    assert sv.owner is BOTTOM
    assert not sv._cowner and not sv._uowner and not sv._cante
    assert not hasattr(s, "writeback") and not hasattr(s, "_home_of")
    assert eng.is_(node, 'positive') is True
    assert cache.get(node, 'positive') is True
    assert not any(k.startswith("writeback") for k in eng.stats)


def test_none_memoizes_nothing():
    eng, cache = _engine("none")
    node = ('add', 'y', 'z')
    assert eng.is_(node, 'positive') is True
    assert eng.is_(node, 'positive') is True
    assert cache.store == {} and eng.stats["cache_hits"] == 0 and eng.stats["sessions"] == 2
    # the setting drops the caches on a change, like every setting
    eng.writeback = "root-only"
    assert eng.is_(node, 'positive') is True
    assert cache.store == {node: {'positive': True}}
    eng.writeback = "none"
    assert cache.store == {}
    assert eng.is_(node, 'positive') is True and cache.store == {}


def test_unknown_writeback_policy_raises():
    with pytest.raises(ValueError):
        Engine(templates=templates, writeback="sometimes")


@pytest.mark.parametrize("policy", ["provenance", "all"])
def test_removed_writeback_policies_raise(policy):
    with pytest.raises(ValueError, match="removed"):
        Engine(templates=templates, writeback=policy)
    eng = Engine(templates=templates)
    with pytest.raises(ValueError, match="#97"):
        eng.writeback = policy
    assert eng.writeback == "root-only"


# --------------------------------------------------------------------------
# the discovery budget: None before any session work, nothing memoized
# --------------------------------------------------------------------------

@pytest.mark.parametrize("policy", POLICIES)
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


# r1 (opus-high review): F's template speaks about c; D's clause
# ~zero(c) | ~real(e) | positive(D) is added once zero(c) is true at root,
# so the solver stores real(e) -> positive(D); F is not in cone(D), and
# the fresh is_(D, positive) is None.
F1 = ('f', 'c')
D1 = ('d', 'c', 'e')


def _r1_templates(node):
    if node == F1:
        return [Not(P('nonzero', F1)), Implies(Not(P('nonzero', F1)), P('zero', 'c'))]
    if node == D1:
        return [Implies(And(P('zero', 'c'), P('real', 'e')), P('positive', D1))]
    if node == 'e':
        return [P('real', 'e')]
    return []


def _r1_engine(policy="root-only"):
    return Engine(templates=_r1_templates, cache=DictCache(), writeback=policy)


@pytest.mark.parametrize("policy", POLICIES)
def test_fact_from_a_shortened_clause_is_not_memoized(policy):
    eng = _r1_engine(policy)
    # one session that visits F before D
    assert eng.ask(Or(P('nonzero', F1), P('positive', D1))) is True
    assert eng.ask(P('positive', D1), P('real', F1)) is True
    assert eng.cache.facts(D1) is None
    assert eng.is_(D1, 'positive') is None
    assert _r1_engine(policy).is_(D1, 'positive') is None
    assert _not_memos(eng, lambda: _r1_engine(policy)) == []


def _chain_engine(budget, policy="root-only"):
    return Engine(templates=templates, cache=DictCache(), discovery_budget=budget,
                  writeback=policy)


@pytest.mark.parametrize("policy", POLICIES)
def test_queries_past_the_budget_memoize_nothing(policy):
    """a_chain (fable review), with the budget a test on the query's cone
    (#53 task 6): the same assumptions, one node larger per call; a query
    whose cone (with the assumptions') outweighs the budget is None before
    any session work, warm as fresh; contextual queries memoize nothing,
    and is_ memoizes only within the budget."""
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
    assert eng.cache.store == {}
    assert eng.is_(('add', 'y'), 'positive') is True        # cone of 2 fits
    assert eng.cache.facts(('add', 'y')) == ({'positive': True} if policy == "root-only"
                                             else None)
    assert eng.cache.facts(e) is None                        # 5 does not
    assert _not_memos(eng, lambda: _chain_engine(4, policy)) == []
    fresh = _chain_engine(4, policy)
    assert fresh.is_(e, 'positive') is None and fresh.last_budget_limited
    assert eng.is_(e, 'positive') is None and eng.last_budget_limited


@pytest.mark.parametrize("policy", POLICIES)
def test_queries_past_the_budget_sympy(policy):
    """a_final (fable review), on SymPy nodes: exp(exp(exp(x))) has a cone
    of 4 nodes, the budget is 3; warm and fresh agree on every answer and
    on ``last_budget_limited``."""
    sympy = pytest.importorskip("sympy")
    x = sympy.Symbol('x', positive=True)
    y = sympy.Symbol('y')
    eng = Engine(discovery_budget=3, writeback=policy)
    e = x
    for _ in range(3):
        e = sympy.exp(e)
        r = eng.ask(P('positive', e), P('real', y))
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


# b_trunc (fable review): a stream of is_ and contextual asks over nodes
# whose cones fit or do not fit the budget; the memo stays fresh
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
    if node in 'abcdefg':
        return [P('positive', node)] + ([P('integer', node)] if node == 'a' else [])
    return []


def _bt_engine(budget):
    return Engine(templates=_bt_templates, cache=DictCache(), discovery_budget=budget)


@pytest.mark.parametrize("budget", [2, 3, 4, 6])
def test_cache_stays_a_memo_across_budgets(budget):
    eng = _bt_engine(budget)
    wide = ('add', ('f', 'a'), ('f', 'b'), ('f', 'c'), ('f', 'd'), ('f', 'e'))
    seq = [(wide, 'integer'), (wide, 'positive'), (('f', wide), 'real'),
           (('add', 'a', 'b'), 'integer'), (('f', ('f', ('f', 'a'))), 'real'),
           (('add', ('f', 'a'), 'g'), 'integer')]
    for node, pred in seq:
        r = eng.is_(node, pred)
        assert r is _bt_engine(budget).is_(node, pred)
        eng.ask(P(pred, node), P('real', 'zz'))
    assert _not_memos(eng, lambda: _bt_engine(budget)) == []
    for facts in eng.cache.store.values():
        assert all(v in (True, False) for v in facts.values())


# a node whose query is decided before escalation, with a parked template
# about a long chain: its cone (5 objects) is larger than the budget (2)
# although its session is not truncated
DP = ('p', 'a', ('add', ('add', 'z')))


def _parked_templates(node):
    if node == DP:
        return [Implies(P('positive', 'a'), P('positive', DP)),
                Implies(P('integer', DP[2]), P('integer', DP))]   # parked for positive
    if node == 'a':
        return [P('positive', 'a')]
    return templates(node)


def _parked_engine(budget, policy):
    return Engine(templates=_parked_templates, cache=DictCache(), discovery_budget=budget,
                  writeback=policy)


@pytest.mark.parametrize("policy", POLICIES)
def test_answer_decided_with_work_parked_is_memoized_within_the_budget(policy):
    # the cone of DP (5 objects) outweighs the budget (2): None, although
    # propagation would decide it before escalation (#53 task 6)
    eng = _parked_engine(2, policy)
    assert eng.is_(DP, 'positive') is None
    assert eng.last_budget_limited is True
    assert eng.cache.facts(DP) is None
    assert _not_memos(eng, lambda: _parked_engine(2, policy)) == []
    eng = _parked_engine(5, policy)
    assert eng.is_(DP, 'positive') is True
    assert eng.cache.store == ({DP: {'positive': True}} if policy == "root-only" else {})
    assert _not_memos(eng, lambda: _parked_engine(5, policy)) == []


def test_cone_of_a_node_and_the_budget():
    """Engine._cone_info: the cone if its weight fits the budget, and
    whether it holds a relation atom (the budget test of is_ and ask)."""
    eng = _chain_engine(3)
    chain = ('add', ('add', 'y'))
    c, w, rel = eng._cone_info(chain)
    assert c == frozenset([chain, ('add', 'y'), 'y']) and w == 3 and not rel
    assert eng._cone_info(('add', chain))[0] is None             # 4 > 3
    assert 'y' in c and chain not in eng._cone_info(('add', 'y'))[0]
    eng2 = _chain_engine(3)
    eng2._kids[('r',)] = ({P('lt', ('y', 'w'))}, 1)
    assert eng2._cone_info(('r',))[2] is True


def test_cache_hit_resets_last_budget_limited():
    eng, cache = _engine(discovery_budget=1)
    cache.put('y', 'positive', True)
    eng.is_(('add', ('add', 'x', 'w'), 'y'), 'real')
    assert eng.last_budget_limited is True
    assert eng.is_('y', 'positive') is True               # a cache hit
    assert eng.last_budget_limited is False


# --------------------------------------------------------------------------
# the audit, on a stream: every cached fact is what a fresh engine derives
# --------------------------------------------------------------------------

def test_audit_after_a_mixed_stream():
    leaves = ['x', 'y', 'z', 'w']
    nodes = list(leaves)
    for a, b in itertools.combinations(leaves, 2):
        nodes.append(('add', a, b))
        if a in ('x', 'w'):                 # ('sq', y) would contradict positive(y)
            nodes += [('sq', a), ('add', ('sq', a), b)]
    preds = ['positive', 'real', 'zero', 'nonzero', 'negative']
    for budget in (2, 4, None):
        kw = {} if budget is None else {"discovery_budget": budget}
        eng = Engine(templates=templates, cache=DictCache(), **kw)
        for i, (n, p) in enumerate(itertools.product(nodes, preds)):
            if i % 3 == 0:
                eng.is_(n, p)
            elif i % 3 == 1:
                eng.ask(P(p, n), P('positive', 'w'))
            else:
                eng.ask(Or(P(p, n), P('zero', 'x')))
        assert eng.cache.store, budget
        bad = _not_memos(eng, lambda: Engine(templates=templates, cache=DictCache(), **kw))
        assert bad == [], (budget, bad)


def test_audit_on_sympy_nodes():
    sympy = pytest.importorskip("sympy")
    x = sympy.Symbol('x', positive=True)
    y = sympy.Symbol('y', integer=True)
    z = sympy.Symbol('z')
    eng = Engine()
    exprs = [x * y + sympy.acos(x) - 1, sympy.exp(x) / (y ** 2 + 1), z ** 2, x + y,
             sympy.log(x), sympy.Abs(z) - 1, y * z, sympy.sqrt(x) + 2]
    for e in exprs:
        for pred in ('positive', 'real', 'negative', 'integer', 'zero', 'finite'):
            eng.is_(e, pred)
            eng.ask(P(pred, e), P('positive', z))
            eng.ask(P(pred, e), P('negative', y) & P('real', z))
    assert len(eng.cache.store) >= 4
    assert _not_memos(eng, Engine) == []
