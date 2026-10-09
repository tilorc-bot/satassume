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


def make(**declared):
    """An engine over ``templates`` whose leaves ``declared`` (``x={'positive':
    True}``) carry those facts as template literals, the way a Symbol's
    ``assumptions0`` do.  Before #97 (P2) the facts were put into the cache
    and the sessions asserted them; the cache is a memo of ``is_`` now, a
    session never reads it, so declared facts are inputs of the templates.
    The cache is returned empty for the memo assertions."""
    def declaring(node):
        facts = declared.get(node) if isinstance(node, str) else None
        if not facts:
            return templates(node)
        return [P(p, node) if v else Not(P(p, node)) for p, v in facts.items()]
    cache = DictCache()
    return Engine(templates=declaring, cache=cache), cache


def test_rule_closure_from_declared_fact():
    # was test_rule_closure_from_cached_fact: the fact was a cache input
    eng, cache = make(x={'positive': True})
    assert eng.is_('x', 'real') is True
    assert eng.is_('x', 'nonzero') is True
    assert eng.is_('x', 'negative') is False
    assert eng.is_('x', 'complex') is True
    assert eng.is_('x', 'imaginary') is False
    assert eng.is_('x', 'integer') is None
    # the memo holds the answers given, True/False only, nothing of the
    # closure that was not asked for; an answer, once given, is a free hit
    assert cache.store['x'] == {'real': True, 'nonzero': True, 'negative': False,
                               'complex': True, 'imaginary': False}
    assert cache.get('x', 'extended_positive', 'missing') == 'missing'
    hits, sessions = eng.stats['cache_hits'], eng.stats['sessions']
    assert eng.is_('x', 'extended_positive') is True
    assert eng.stats['cache_hits'] == hits and eng.stats['sessions'] == sessions + 1
    assert cache.get('x', 'extended_positive') is True
    assert eng.is_('x', 'extended_positive') is True
    assert eng.stats['cache_hits'] == hits + 1 and eng.stats['sessions'] == sessions + 1


def test_structural_template_and_child_facts_are_not_memoized():
    # was test_structural_template_and_child_writeback
    eng, cache = make(x={'positive': True}, y={'positive': True})
    assert eng.is_(('add', 'x', 'y'), 'positive') is True
    assert eng.is_(('mul', 'x', 'y'), 'nonzero') is True
    # derived about a child while answering the parent: only the queried
    # node's answer is memoized, the child's facts are recomputed (the
    # "provenance" policy that cached them was removed by #97 P2)
    assert cache.get('y', 'nonzero', 'missing') == 'missing'
    assert cache.get('y', 'positive', 'missing') == 'missing'
    assert cache.get(('mul', 'x', 'y'), 'nonzero') is True
    assert set(cache.store) == {('add', 'x', 'y'), ('mul', 'x', 'y')}
    sessions = eng.stats['sessions']
    assert eng.is_('y', 'nonzero') is True
    assert eng.stats['sessions'] == sessions + 1
    assert cache.store['y'] == {'nonzero': True}
    with pytest.raises(ValueError, match="removed"):
        eng.writeback = "provenance"
    assert eng.writeback == "root-only"


def test_unknown_stays_unknown_and_is_not_memoized():
    # was test_unknown_stays_unknown_and_is_cached: the None was cached
    eng, cache = make(x={'real': True}, y={'real': True})
    assert eng.is_(('add', 'x', 'y'), 'positive') is None
    assert cache.get(('add', 'x', 'y'), 'positive', 'missing') == 'missing'
    # a None is recomputed, never served from the cache
    hits, sessions = eng.stats['cache_hits'], eng.stats['sessions']
    assert eng.is_(('add', 'x', 'y'), 'positive') is None
    assert eng.stats['cache_hits'] == hits and eng.stats['sessions'] == sessions + 1
    assert ('add', 'x', 'y') not in cache.store


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
    assert not cache.store                      # ten Nones: nothing memoized
    # a fact about x used while answering about x + z_i is not memoized:
    # computed once in its own session, then served as an answer
    assert eng.is_('x', 'positive') is True
    assert eng.stats['sessions'] == 11
    assert eng.is_('x', 'positive') is True
    assert eng.stats['sessions'] == 11
    assert eng.is_('x', 'nonzero') is True
    assert eng.stats['sessions'] == 12
    assert eng.is_('x', 'nonzero') is True
    assert eng.stats['sessions'] == 12
    assert cache.store == {'x': {'positive': True, 'nonzero': True}}


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
    # the settings of the earlier reuse design were removed (#97 P7): the
    # constructor refuses them, and the next query builds its own session
    for name in ('keep_sessions', 'session_limit', 'cone_search', 'cone_threshold'):
        with pytest.raises(TypeError):
            Engine(**{name: 0})
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
    from satassume.knowledge.rules import BASIS_INDEX
    n = neighbourhood('even')
    assert all(BASIS_INDEX[p] in n for p in ('even', 'integer', 'zero'))
    assert BASIS_INDEX['polar'] not in n
    # a derived predicate: the neighbourhoods of its basis literals
    assert neighbourhood('odd') == neighbourhood(BASIS_INDEX['integer']) | neighbourhood(BASIS_INDEX['even'])


def test_exactlyone_helper():
    f = Implies(And(allargs('complex', ['x', 'y']), exactlyonearg('imaginary', ['x', 'y'])), P('imaginary', ('mul', 'x', 'y')))
    # the declared facts of x and y are template literals (``make``); the
    # product's own template is given at construction with them
    eng, cache = make(x={'imaginary': True}, y={'real': True, 'nonzero': True})
    declaring = eng.templates
    eng = Engine(templates=lambda n: [f] if n == ('mul', 'x', 'y') else declaring(n), cache=cache)
    assert eng.is_(('mul', 'x', 'y'), 'imaginary') is True
    assert cache.store == {('mul', 'x', 'y'): {'imaginary': True}}
