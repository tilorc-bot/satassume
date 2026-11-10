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
One ``Engine`` asked about both nodes is not covered: its own tables
(``Engine.cache`` and the memos of whole queries) are keyed by ``==`` too.
"""
from fractions import Fraction

import pytest
from sympy import Float, Integer, Q, S, Symbol
from sympy.assumptions import Predicate

from satassume import Engine
from satassume import sympy_api as api
from satassume.knowledge.extensions import Args
from satassume.knowledge.templates.registry import registry
from satassume.sat.formula import And, Implies, Not, P
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
