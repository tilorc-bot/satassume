"""A query about a Python number is answered as when it is asked alone,
whatever was asked before it (#96).

A Python number equals a SymPy one and has its hash (``1 == True == S.One``,
``1.5 == Float(1.5)``, ``Fraction(3) == Integer(3)``), but it is another
node: the templates of a node are those of its type
(``TemplateRegistry.clauses_for`` reads ``templates_for(type(expr))``), and
``int``, ``bool``, ``float`` and ``Fraction`` have none.  The memo of
``clauses_for`` was keyed by the node alone, so the first of two equal nodes
filled the entry of both: ``Engine().ask(P('positive', 1))`` was None alone
and True after the same question about ``S.One``, and the question about
``S.One`` was None after the one about ``1``.  A Python number gets there
from a custom fact that writes ``1`` where ``S.One`` is meant, or from a
caller of ``Engine`` (``sympy_api`` sympifies its input).

Each case is asked in both orders from emptied process memos, with a new
``Engine`` per ask (the tables shared by every engine carried the first
node), and each answer is compared with the one the same question gets alone
from emptied memos.  What the answer about a Python number should be is not
this test's subject: the expected answers are computed, not written down.

The second half asks one ``Engine`` about both nodes of a pair.  Its own
tables are keyed with the types too (``typed``, satassume.sat.formula), and
so are the process-wide tables of the relation atoms; there is one block of
tests per table.
"""
from fractions import Fraction

import pytest
from sympy import Float, Integer, Q, S, Symbol
from sympy.assumptions import Predicate

from satassume import DictCache, Engine
from satassume import sympy_api as api
from satassume.knowledge.extensions import Args
from satassume.knowledge.templates.registry import registry
from satassume.sat.formula import And, Implies, Not, P, typed, types_of
from satassume.state import memos

s = Symbol('s')

# name: (the Python number, the equal SymPy number)
PAIRS = {
    'int 1, One': (1, S.One),
    'bool True, One': (True, S.One),
    'float 1.5, Float': (1.5, Float(1.5)),
    'Fraction 3, Integer': (Fraction(3), Integer(3)),
}


def _counts(v):
    compiled, formulas = registry.clauses_for(v)
    return len(compiled), len(formulas)


def _custom_facts(py, sy):
    """Two custom facts with a number in the condition, one written with
    the Python number and one with the SymPy one: ``cache_key_type_py(s)`` and
    ``positive(py)`` give ``positive(s)``, and the same for ``sy``.  The
    question about a number is the one that uses its fact.  The caller
    restores the registrations."""
    asked_by = {}
    for v, name in [(py, 'cache_key_type_py'), (sy, 'cache_key_type_sy')]:
        api.extensions.register(name, Symbol)(
            lambda a, v=v, name=name: Implies(And(P(name, a), P('positive', v)), P('positive', a)))
        asked_by[type(v)] = Predicate(name)
    return lambda v: api.ask(Q.positive(s), asked_by[type(v)](s), Engine())


# name: the question about the number ``v``
DOORS = {
    'clauses_for': _counts,
    'ask': lambda v: Engine().ask(P('positive', v), P('real', s)),
    'ask, no assumptions': lambda v: Engine().ask(P('positive', v)),
    'ask, in the assumptions': lambda v: Engine().ask(
        P('positive', s), And(P('real', s), Implies(P('positive', v), P('positive', s)))),
    'is_': lambda v: Engine().is_(v, 'positive'),
    'is_many': lambda v: Engine().is_many(v, ['positive', 'integer', 'real']),
    'verdict': lambda v: Engine().verdict(Not(P('positive', v))),
}


@pytest.fixture
def emptied():
    memos.PROCESS.clear()
    yield
    memos.PROCESS.clear()


def _alone(question, v):
    memos.PROCESS.clear()
    return question(v)


@pytest.mark.parametrize("order", ['Python-first', 'SymPy-first'])
@pytest.mark.parametrize("door", [*DOORS, 'custom facts'])
@pytest.mark.parametrize("pair", list(PAIRS))
def test_equal_numbers_of_two_types_are_answered_as_alone(pair, door, order, emptied):
    py, sy = PAIRS[pair]
    # one key by ``==``, two types
    assert py == sy and hash(py) == hash(sy) and type(py) is not type(sy)
    nodes = [py, sy] if order == 'Python-first' else [sy, py]
    registered = api.extensions.snapshot()
    try:
        question = _custom_facts(py, sy) if door == 'custom facts' else DOORS[door]
        alone = [_alone(question, v) for v in nodes]
        memos.PROCESS.clear()
        assert [question(v) for v in nodes] == alone
    finally:
        api.extensions.restore(registered)


@pytest.mark.parametrize("pair", list(PAIRS))
def test_the_two_types_have_different_templates(pair, emptied):
    """What makes the test above able to fail: the two nodes of a pair get
    different templates today (the Python types have none), so one entry
    for both is wrong for one of them."""
    py, sy = PAIRS[pair]
    assert _alone(_counts, py) == (0, 0)
    assert _alone(_counts, sy) != (0, 0)


@pytest.mark.parametrize("pair", list(PAIRS))
def test_each_type_has_its_own_entry_and_hits_it(pair, emptied):
    py, sy = PAIRS[pair]
    first = [registry.clauses_for(v) for v in (py, sy)]
    assert first[0] is not first[1]
    assert [registry.clauses_for(v) for v in (py, sy)] == first
    assert all(registry.clauses_for(v) is r for v, r in zip((py, sy), first))


# -- one Engine asked about both nodes of a pair -----------------------------
# The engine's own tables: one block per table below.  The questions that
# reach the table are asked of one Engine in both orders, and each answer is
# compared with the same question asked alone of a new Engine from emptied
# process memos.

ORDERS = ['Python-first', 'SymPy-first']
CUSTOM = 'cache_key_type_custom'


def _answer(question, *args):
    """The answer, or the name of what the question raised."""
    try:
        return question(*args)
    except Exception as e:      # noqa: BLE001
        return type(e).__name__


def _one_engine_as_alone(question, nodes, make=Engine):
    """Ask one engine about ``nodes`` in order; every answer must be the one
    a new engine gives alone.  Returns the asked-alone answers."""
    alone = []
    for v in nodes:
        memos.PROCESS.clear()
        alone.append(_answer(question, make(), v))
    memos.PROCESS.clear()
    e = make()
    assert [_answer(question, e, v) for v in nodes] == alone
    return alone


def _ordered(pair, order):
    py, sy = pair
    return [py, sy] if order == 'Python-first' else [sy, py]


def test_types_of_reads_the_types_that_equality_ignores():
    assert typed(1) == (int, 1) and typed(S.One) == (type(S.One), S.One)
    assert len({typed(1), typed(True), typed(1.0), typed(Fraction(1)), typed(S.One)}) == 5
    a, b = Args((1, s)), Args((S.One, s))
    assert a == b == (1, s) and len({typed(a), typed(b), typed((1, s))}) == 3
    assert P('lt', a) == P('lt', b) and typed(P('lt', a)) != typed(P('lt', b))
    f, g = And(P('positive', 1), P('real', s)), And(P('positive', True), P('real', s))
    assert f == g and typed(f) != typed(g)
    # through tuples and frozensets, as deep as they go
    assert typed(((1, 2), s)) != typed(((1.0, 2), s))
    assert typed((1, (2, (3, s)))) != typed((1, (2, (3.0, s))))
    assert typed(frozenset([1, s])) != typed(frozenset([True, s]))
    # a SymPy node is not looked into, and equal keys stay equal
    assert types_of(s + 1) is type(s + 1)
    assert typed(P('positive', s + 1)) == typed(P('positive', 1 + s))
    assert typed(Args((1, s))) == typed(Args((1, Symbol('s'))))


# Engine.cache.store and Engine.custom_cache.store (DictCache)
FACT_DOORS = {
    'is_': lambda e, v: e.is_(v, 'positive'),
    'is_many': lambda e, v: e.is_many(v, ['positive', 'integer', 'real']),
    'is_, custom predicate': lambda e, v: e.is_(v, CUSTOM),
}


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("door", list(FACT_DOORS))
@pytest.mark.parametrize("pair", list(PAIRS))
def test_one_engine_fact_caches(pair, door, order, emptied):
    registered = api.extensions.snapshot()
    try:
        # a custom predicate (answered from ``custom_cache``): it holds of
        # every positive node
        api.extensions.register(CUSTOM, object)(
            lambda a: Implies(P('positive', a), P(CUSTOM, a)))
        alone = _one_engine_as_alone(FACT_DOORS[door], _ordered(PAIRS[pair], order))
    finally:
        api.extensions.restore(registered)
    assert alone[0] != alone[1]     # or one entry for both would do


def test_fact_cache_has_an_entry_per_type(emptied):
    cache = DictCache()
    e = Engine(cache=cache)
    assert e.is_(S.One, 'positive') is True and e.is_(1, 'positive') is None
    assert cache.facts(S.One) == {'positive': True} and cache.facts(1) is None
    cache.put(1, 'positive', False)             # seeded by hand
    assert cache.get(1, 'positive') is False and cache.get(S.One, 'positive') is True
    assert cache.get(True, 'positive') is None and cache.get(1.0, 'positive') is None
    assert sorted(cache.items(), key=lambda nf: type(nf[0]).__name__) == [
        (S.One, {'positive': True}), (1, {'positive': False})]
    assert set(cache.store) == {typed(S.One), typed(1)}
