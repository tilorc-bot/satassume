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
    assert cache.get('y', 'nonzero') is True     # derived about a child while answering the parent


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
    assert eng.is_('x', 'nonzero') is True      # cache hit, no new session
    assert eng.stats['sessions'] == 10


def test_context_session_is_reused_for_same_assumptions():
    eng, cache = make()
    a = P('positive', 'x')
    assert eng.ask(P('real', 'x'), a) is True
    n = eng.stats['sessions']
    assert eng.ask(P('nonzero', 'x'), a) is True
    assert eng.ask(P('real', ('add', 'x', 'x')), P('positive', 'x')) is True   # equal formula, same session
    assert eng.stats['sessions'] == n
    assert eng.ask(P('real', 'x'), P('negative', 'x')) is True                 # different assumptions
    assert eng.stats['sessions'] == n + 1


def test_neighbourhood_contains_pred_and_rule_partners():
    from satassume.rules import PRED_INDEX
    n = neighbourhood('even')
    assert all(PRED_INDEX[p] in n for p in ('even', 'integer', 'odd', 'zero'))
    assert PRED_INDEX['polar'] not in n and PRED_INDEX['hermitian'] not in n


def test_exactlyone_helper():
    eng, cache = make(x={'imaginary': True}, y={'real': True, 'nonzero': True})
    f = Implies(And(allargs('complex', ['x', 'y']), exactlyonearg('imaginary', ['x', 'y'])), P('imaginary', ('mul', 'x', 'y')))
    eng.templates = lambda n: [f] if n == ('mul', 'x', 'y') else templates(n)
    assert eng.is_(('mul', 'x', 'y'), 'imaginary') is True
