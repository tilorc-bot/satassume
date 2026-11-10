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
from decimal import Decimal
from fractions import Fraction

import pytest
from sympy import Float, Integer, Q, S, Symbol, srepr
from sympy.assumptions import Predicate

from satassume import DictCache, Engine
from satassume import sympy_api as api
from satassume.knowledge.extensions import Args
from satassume.knowledge.templates.registry import registry
from satassume.relations import sympy_atom
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


# Engine._verdict, the memo of the assumption sets (Engine._failed, its
# other half, is with the relation atoms below)
SET_DOORS = {
    'verdict': lambda e, v: e.verdict(Not(P('positive', v))),
    'verdict, set of two': lambda e, v: e.verdict(And(P('real', s), Not(P('positive', v)))),
    'ask, inconsistent assumptions': lambda e, v: e.ask(P('real', s), Not(P('positive', v))),
}


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("door", list(SET_DOORS))
@pytest.mark.parametrize("pair", list(PAIRS))
def test_one_engine_set_verdicts(pair, door, order, emptied):
    alone = _one_engine_as_alone(SET_DOORS[door], _ordered(PAIRS[pair], order))
    assert alone[0] != alone[1]


# Engine._kids, Engine._cones and Engine._qcones: the structural cones the
# discovery budget is tested on.  A fact registered for the SymPy type only
# puts two more symbols in the cone of the SymPy number (weight 3, the
# Python number's 1); with a budget of 2 one is answered and the other is
# over the budget.
CONE_DOORS = {
    'is_': lambda e, v: e.is_(v, 'positive'),
    'is_many': lambda e, v: e.is_many(v, ['positive', 'zero']),
    'ask': lambda e, v: e.ask(P('positive', v), P('real', s)),
    'ask, no assumptions': lambda e, v: e.ask(P('positive', v)),
    'ask, in the assumptions': lambda e, v: e.ask(P('real', s), P('positive', v)),
    'verdict': lambda e, v: e.verdict(P('positive', v)),
}


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("door", list(CONE_DOORS))
@pytest.mark.parametrize("pair", list(PAIRS))
def test_one_engine_cones(pair, door, order, emptied):
    py, sy = PAIRS[pair]
    w1, w2 = Symbol('w1'), Symbol('w2')
    question = CONE_DOORS[door]
    registered = api.extensions.snapshot()
    try:
        api.extensions.register('prime', type(sy))(
            lambda n: Implies(P('prime', n), And(P('positive', w1), P('positive', w2))))
        alone = _one_engine_as_alone(
            lambda e, v: (question(e, v), e.last_budget_limited),
            _ordered((py, sy), order), lambda: Engine(discovery_budget=2))
    finally:
        api.extensions.restore(registered)
    assert alone[0] != alone[1]


# -- relation atoms ----------------------------------------------------------
# relations._SYMPY_ATOMS (process-wide): ``Q.lt`` / ``Q.eq`` of a relation
# atom, whose sides are sympified by type.  ``lt(True, s)`` became
# ``Q.lt(1, s)`` after ``lt(S.One, s)`` and was then read as a bound, and
# the bool reached code written for SymPy sides ('bool' object has no
# attribute 'args'); ``lt(S.One, s)`` after ``lt(True, s)`` was not read.
REL_PAIRS = {
    'bool True, One': (True, S.One),
    'Decimal 1, One': (Decimal(1), S.One),
    'bool False, Zero': (False, S.Zero),
}
REL_DOORS = {
    'ask': lambda e, v: e.ask(P('lt', Args((v, s))), P('lt', Args((Integer(2), s)))),
    'ask, in the assumptions': lambda e, v: e.ask(P('positive', s), P('lt', Args((v, s)))),
    'ask, equality in the assumptions': lambda e, v: e.ask(P('positive', s), P('eq', Args((s, v)))),
    'verdict': lambda e, v: e.verdict(P('lt', Args((s, v)))),
}
ENGINES = ['a new Engine per ask', 'one Engine']


def _as_alone(question, nodes, engines, make=Engine):
    if engines == 'one Engine':
        return _one_engine_as_alone(question, nodes, make)
    alone = []
    for v in nodes:
        memos.PROCESS.clear()
        alone.append(_answer(question, make(), v))
    memos.PROCESS.clear()
    assert [_answer(question, make(), v) for v in nodes] == alone
    return alone


@pytest.mark.parametrize("engines", ENGINES)
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("door", list(REL_DOORS))
@pytest.mark.parametrize("pair", list(REL_PAIRS))
def test_relation_atoms_of_equal_sides_of_two_types(pair, door, order, engines, emptied):
    _as_alone(REL_DOORS[door], _ordered(REL_PAIRS[pair], order), engines)


@pytest.mark.parametrize("engines", ENGINES)
@pytest.mark.parametrize("order", ORDERS)
def test_true_against_one_in_a_relation_atom(order, engines, emptied):
    """The reported case: each gets its own answer, and nothing is raised."""
    alone = _as_alone(REL_DOORS['ask'], _ordered((True, S.One), order), engines)
    assert sorted(alone, key=repr) == [None, True]


@pytest.mark.parametrize("sides", [(True, S.One), (1.0, 1), (1.5, Fraction(3, 2)),
                                   ((1, 2), (1.0, 2)), ((1, (2, 3)), (1, (2.0, 3)))])
def test_relation_atom_key_goes_as_deep_as_sympify(sides, emptied):
    """The value is ``Q.lt`` of the sympified sides, and ``sympify``
    converts by type through tuples: equal atoms whose sides differ in type
    at any depth of a tuple side are different entries."""
    for a, b in (sides, sides[::-1]):
        memos.PROCESS.clear()
        pa, pb = P('lt', Args((a, s))), P('lt', Args((b, s)))
        assert pa == pb and hash(pa) == hash(pb)
        got = [sympy_atom(pa), sympy_atom(pb)]
        assert [srepr(r) for r in got] == [srepr(Q.lt(a, s)), srepr(Q.lt(b, s))]
        assert srepr(got[0]) != srepr(got[1])
        assert sympy_atom(pa) is got[0] and sympy_atom(pb) is got[1]    # and each hits


# Engine._failed: the sets whose session raised Uninterpreted (an engine
# that does not leave unread relation atoms free)
@pytest.mark.parametrize("order", ORDERS)
def test_one_engine_failed_sets(order, emptied):
    alone = _one_engine_as_alone(
        lambda e, v: e.ask(P('positive', s), P('lt', Args((v, s)))),
        _ordered((True, S.One), order), lambda: Engine(uninterpreted='none'))
    assert set(alone) == {None, 'Uninterpreted'}     # one of the two is not read
