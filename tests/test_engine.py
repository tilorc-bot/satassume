"""Engine tests that do not need SymPy: nodes are tuples, templates are local."""
import pytest

from satassume import Engine, DictCache, P, And, Or, Not, Implies, allargs, anyarg, exactlyonearg
from satassume.engine import InconsistentAssumptions, neighbourhood


# nodes: 'x' (a leaf) or ('add', a, b, ...) / ('mul', a, b, ...)
def templates(node):
    if isinstance(node, tuple):
        kind, *args = node
        if kind == 'add':
            return [Implies(allargs('positive', args), P('positive', node)),
                    Implies(allargs('real', args), P('real', node)),
                    Implies(allargs('integer', args), P('integer', node))]
        if kind == 'mul':
            return [Implies(allargs('positive', args), P('positive', node)),
                    Implies(allargs('real', args), P('real', node)),
                    Implies(allargs('finite', args), Implies(anyarg('zero', args), P('zero', node))),
                    Implies(allargs('nonzero', args), P('nonzero', node))]
    return []


def make(**cache_facts):
    cache = DictCache()
    for node, facts in cache_facts.items():
        for p, v in facts.items():
            cache.put(node, p, v)
    return Engine(templates=templates, cache=cache), cache


def test_rule_closure_from_cached_fact():
    eng, cache = make(x={'positive': True})
    assert eng.is_('x', 'real') is True
    assert eng.is_('x', 'nonzero') is True
    assert eng.is_('x', 'negative') is False
    assert eng.is_('x', 'complex') is True
    assert eng.is_('x', 'imaginary') is False
    assert eng.is_('x', 'integer') is None
    # write-back: the closure landed in the cache, later hits are free
    assert cache.get('x', 'extended_positive') is True
    hits = eng.stats['cache_hits']
    eng.is_('x', 'extended_positive')
    assert eng.stats['cache_hits'] == hits + 1


def test_structural_template_and_child_writeback():
    eng, cache = make(x={'positive': True}, y={'positive': True})
    assert eng.is_(('add', 'x', 'y'), 'positive') is True
    assert eng.is_(('mul', 'x', 'y'), 'nonzero') is True
    # derived about a child while answering the parent: the default
    # writeback="root-only" caches only the queried node's facts, the child's
    # are recomputed; writeback="provenance" caches them (they come from the
    # child's own cone)
    assert cache.get('y', 'nonzero', 'missing') == 'missing'
    assert cache.get(('mul', 'x', 'y'), 'nonzero') is True
    assert eng.is_('y', 'nonzero') is True
    eng.writeback = "provenance"
    cache.put('x', 'positive', True)
    cache.put('y', 'positive', True)
    assert eng.is_(('mul', 'x', 'y'), 'nonzero') is True
    assert cache.get('y', 'nonzero') is True


def test_unknown_stays_unknown_and_is_cached():
    eng, cache = make(x={'real': True}, y={'real': True})
    assert eng.is_(('add', 'x', 'y'), 'positive') is None
    assert cache.get(('add', 'x', 'y'), 'positive', 'missing') is None


def test_contextual_query_does_not_pollute_cache():
    eng, cache = make()
    assert eng.ask(P('real', 'x'), P('positive', 'x')) is True
    assert eng.ask(P('negative', 'x'), P('positive', 'x')) is False
    assert eng.ask(P('positive', ('add', 'x', 'y')), And(P('positive', 'x'), P('positive', 'y'))) is True
    assert cache.get('x', 'positive', 'missing') == 'missing'
    assert cache.get('x', 'real', 'missing') == 'missing'
    assert eng.is_('x', 'real') is None


def test_case_split_needs_search():
    eng, cache = make()
    # even | odd  ->  integer  requires reasoning by cases
    assert eng.ask(P('integer', 'x'), Or(P('even', 'x'), P('odd', 'x'))) is True
    assert eng.stats['searches'] >= 1
    # (positive | negative) -> nonzero and real
    assert eng.ask(P('nonzero', 'x'), Or(P('positive', 'x'), P('negative', 'x'))) is True
    assert eng.ask(P('zero', 'x'), Or(P('positive', 'x'), P('negative', 'x'))) is False


def test_compound_proposition():
    eng, cache = make()
    assert eng.ask(Or(P('rational', 'x'), P('irrational', 'x')), P('real', 'x')) is True
    assert eng.ask(And(P('real', 'x'), Not(P('zero', 'x'))), P('positive', 'x')) is True
    assert eng.ask(Implies(P('even', 'x'), P('integer', 'x'))) is True


def test_inconsistent_assumptions_raise():
    eng, cache = make()
    with pytest.raises(InconsistentAssumptions):
        eng.ask(P('real', 'x'), And(P('even', 'x'), P('odd', 'x')))
    eng2, cache2 = make(x={'positive': True})
    with pytest.raises(InconsistentAssumptions):
        eng2.ask(P('real', 'x'), P('negative', 'x'))


def test_sessions_are_per_query_and_facts_persist():
    eng, cache = make(x={'positive': True})
    for i in range(10):
        assert eng.is_(('add', 'x', f'z{i}'), 'real') is None
    assert eng.stats['sessions'] == 10
    assert eng.is_('x', 'positive') is True     # cache hit, no new session
    assert eng.stats['sessions'] == 10
    # a fact about x derived while answering about x + z_i is not cached
    # (writeback="root-only"): recomputed once, then cached as an answer
    assert eng.is_('x', 'nonzero') is True
    assert eng.stats['sessions'] == 11
    assert eng.is_('x', 'nonzero') is True
    assert eng.stats['sessions'] == 11


def test_contextual_queries_build_and_discard():
    """Every contextual query builds the session of its set (one set check
    each) and discards it: no session is kept, whatever the assumptions;
    the set's verdict is memoized (one memo per distinct formula)."""
    eng, cache = make()
    a = P('positive', 'x')
    assert eng.ask(P('real', 'x'), a) is True
    n = eng.stats['sessions']
    assert n == 1 and eng.stats['set_checks'] == 1
    assert eng.ask(P('nonzero', 'x'), a) is True
    assert eng.ask(P('real', ('add', 'x', 'x')), P('positive', 'x')) is True   # equal formula
    assert eng.stats['sessions'] == n + 2 and eng.stats['set_checks'] == 3
    assert eng.ask(P('real', 'x'), P('negative', 'x')) is True                 # different assumptions
    assert eng.stats['sessions'] == n + 3
    assert not eng._context_sessions
    assert len(eng._verdict) == 2
    # the settings of the earlier reuse design are accepted and change nothing
    eng.keep_sessions, eng.session_limit, eng.cone_search, eng.cone_threshold = 0, 1, False, 0
    assert eng.ask(P('nonzero', 'x'), a) is True
    assert eng.stats['sessions'] == n + 4 and not eng._context_sessions


def test_stream_under_one_set_answers_as_a_fresh_engine():
    """Fifty random contextual queries under one assumption set, in one
    long-lived engine, give the answers a fresh engine gives each of them
    (the harness checker's warm-versus-fresh comparison, ENGINE level,
    on a CI-sized stream)."""
    pytest.importorskip("sympy")
    from harness.checker import Ask, ReferenceLevel, execute
    from harness.generators import random_stream
    from harness.state import preset
    items = random_stream(97, n=50, nsets=1, relations=True, custom=False)
    asks = [it for it in items if isinstance(it, Ask)]
    sets = {it.assum for it in asks if it.assum is not True}
    assert len(asks) == 50 and len(sets) == 1
    assert sum(it.assum is not True for it in asks) >= 25
    rows, eng = execute(items, preset("default"), ReferenceLevel.ENGINE)
    bad = [(r.item, r.warm, r.ref) for r in rows if r.warm != r.ref]
    assert bad == []
    assert not eng._context_sessions and eng.stats["sessions"] >= 25


def test_neighbourhood_contains_pred_and_rule_partners():
    from satassume.rules import PRED_INDEX
    n = neighbourhood('even')
    assert all(PRED_INDEX[p] in n for p in ('even', 'integer', 'odd', 'zero'))
    assert PRED_INDEX['polar'] not in n and PRED_INDEX['hermitian'] not in n


def test_exactlyone_helper():
    _, cache = make(x={'imaginary': True}, y={'real': True, 'nonzero': True})
    f = Implies(And(allargs('complex', ['x', 'y']), exactlyonearg('imaginary', ['x', 'y'])), P('imaginary', ('mul', 'x', 'y')))
    # templates given at construction: assigning them later starts a new
    # registry epoch, which drops the hand-filled cache
    eng = Engine(templates=lambda n: [f] if n == ('mul', 'x', 'y') else templates(n), cache=cache)
    assert eng.is_(('mul', 'x', 'y'), 'imaginary') is True
