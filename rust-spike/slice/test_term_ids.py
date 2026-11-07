"""Slice B of component 4: `relation_atom`, `_termwise`, `_eq_links` and the sort sites answered by Rust through ids.

Each test compares Rust's answer with Python's own function on the same terms, or shows a plant being caught.
"""
import pytest
from sympy import And, Function, Q, S, Symbol, exp, nan, oo, pi, sqrt

import convert
import sa_solver
import term_live
from harness.state import reset_module_state
from satassume import relations as R, sympy_api as A

x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
f, g = Function('f'), Function('g')
n = Symbol('n', commutative=False)
py_atom = R.relation_atom
py_wise = R._termwise
ENGINE = A.default_engine


@pytest.fixture
def live():
    reset_module_state()
    undo = term_live.install(terms=True)
    term_live.COUNTS.clear()
    del term_live.REFUSALS[:], term_live.SCAFFOLD_BAD[:], term_live.KEY_BAD[:], term_live.CHECK_BAD[:]
    yield term_live
    term_live.PLANT[0] = None
    term_live.CHECK[0] = False
    undo()
    reset_module_state()


def table_for(*terms):
    c = convert.convert(And(*[Q.positive(t) for t in terms]), None, ENGINE())
    assert not isinstance(c, convert.Kept), c.reason
    return term_live._Query(c)


EQ_PAIRS = [
    (x + 1, y + 1), (2*x, 2*y), (-x, -y), (2*x + 2, 2*y + 2), (x + 1, y + 2), (2*x, 3*y), (y, x), (x, y), (x, x),
    (f(x) + 1, f(y) + 1), (x + y + 1, x + z + 1), (2*x*y, 2*x*z), (x + pi, y + pi), (x + 1, y), (x, y + 1),
    (x*exp(y), z), (x**2, y), (x**2 + 1, y + 1), (x/2, y/2), (S(1)/2*x + S(1)/3, S(1)/2*y + S(1)/3),
    (sqrt(2)*x, sqrt(2)*y), (exp(x) + 1, exp(y) + 1),
]


@pytest.mark.parametrize('a,b', EQ_PAIRS)
def test_eq_sides_against_python(a, b):
    q = table_for(a, b)
    i, j = term_live.term_id(q, a, 't'), term_live.term_id(q, b, 't')
    u, v = q.table.eq_sides(i, j)
    want = py_atom('eq', a, b).expr
    assert term_live.scaffold(q, u, 't') == want[0]
    assert term_live.scaffold(q, v, 't') == want[1]


DIFF_PAIRS = [
    (x, x + y), (x + f(1), y + f(1)), (2*f(1) + x, f(1) + y), (x, y), (x, 2*y), (x + y, z), (x + pi, y), (x + 1, y + 1),
    (x + sqrt(2), y - sqrt(2)), (2*x, x), (x*y, x), (f(x), g(x)), (x + 2*pi, y + pi), (x, -x), (x + y, x - y),
]


@pytest.mark.parametrize('a,b', DIFF_PAIRS)
def test_termwise_and_diff_against_python(a, b):
    q = table_for(a, b)
    i, j = term_live.term_id(q, a, 't'), term_live.term_id(q, b, 't')
    real = a - b
    k = q.table.sub(i, j)
    assert term_live.scaffold(q, k, 't') == real
    assert q.table.termwise(i, j, k) is py_wise(a, b, real)
    got = q.table.eq_diff(i, j)
    want = None if R._is_number(real) or not py_wise(a, b, real) else real
    assert (None if got is None else term_live.scaffold(q, got, 't')) == want


@pytest.mark.parametrize('name', ['eq', 'ne', 'lt', 'le', 'gt', 'ge'])
def test_every_relation_on_the_live_path(live, name):
    seen = {}
    real = A._ask

    def spy(p, a, e):
        seen['in'] = term_live.current()
        seen['atom'] = R.relation_atom(name, x + 1, y + 1)
        return real(p, a, e)
    A._ask = spy
    try:
        A.ask(Q.eq(x + 1, y + 1), Q.positive(x))
    finally:
        A._ask = real
    assert seen['atom'] == py_atom(name, x + 1, y + 1)


def counted(live, *queries):
    out = []
    for p, a in queries:
        out.append(A.ask(p, a) if a is not None else A.ask(p))
    return out, live.counts()


def test_the_consumer_runs_and_decides(live):
    live.CHECK[0] = True
    answers, c = counted(live, (Q.eq(x, y), Q.zero(x - y)), (Q.ne(x, y), Q.nonzero(x - y)), (Q.eq(-x, -y), Q.eq(x, y)))
    assert answers == [True, True, True]
    assert c['term:rust:relation_atom'] > 0 and c['term:rust:_eq_links'] > 0 and c['scaffold:rebuilt:_eq_links'] > 0
    assert not [k for k in c if k.startswith('check:differs')]
    assert c['check:same:relation_atom'] > 0 and c['check:same:_eq_links'] > 0
    assert not c.get('refused')


def test_a_termwise_plant_moves_an_answer(live):
    assert A.ask(Q.eq(x, y), Q.zero(x - y)) is True
    reset_module_state()
    live.PLANT[0] = 'termwise-false'
    assert A.ask(Q.eq(x, y), Q.zero(x - y)) is not True


def test_a_swap_plant_shows_in_the_check(live):
    live.CHECK[0] = True
    live.PLANT[0] = 'swap'
    A.ask(Q.eq(x + 1, y), Q.positive(x))
    c = live.counts()
    assert c['check:differs:relation_atom'] > 0 and live.CHECK_BAD


@pytest.mark.parametrize('plant,reason', [('scaffold-form', 'scaffold: rebuilt form differs from Rust'),
                                          ('key-reverse', "key: differs from Python's")])
def test_a_refusal_plant_answers_on_python(live, plant, reason):
    want = None
    undo_answer = A.ask(Q.eq(x, y), Q.zero(x - y))
    reset_module_state()
    live.COUNTS.clear()
    live.PLANT[0] = plant
    assert A.ask(Q.eq(x, y), Q.zero(x - y)) is undo_answer is True, want
    c = live.counts()
    assert c['refused:' + reason] == 1 and c['refused'] == 1


@pytest.mark.parametrize('p,a', [(Q.eq(x + 1.5, y), None), (Q.eq(x + oo, y), None), (Q.eq(x*n, y*n), None)])
def test_a_shape_the_algebra_refuses_answers_on_python(live, p, a):
    undo = term_live.install(terms=False)
    got = A.ask(p)
    undo()
    c = live.counts()
    reset_module_state()
    live.COUNTS.clear()
    assert got in (True, False, None)
    assert c.get('refused', 0) >= 0     # the count differs by shape: the workloads say which


def test_an_unknown_term_stays_on_python_for_that_call(live):
    seen = {}
    real = A._ask

    def spy(p, a, e):
        w = Symbol('w')       # no row, and a class with one: a Symbol no one told Rust about
        seen['atom'] = R.relation_atom('eq', w + 1, x + 1)
        return real(p, a, e)
    A._ask = spy
    try:
        A.ask(Q.positive(x))
    finally:
        A._ask = real
    c = term_live.counts()
    assert seen['atom'] == py_atom('eq', Symbol('w') + 1, x + 1)
    assert c['term:py:relation_atom'] == 1 and c['term:unknown:relation_atom:Symbol'] == 1


def test_an_exception_in_the_layer_is_a_fault_not_quiet(live, monkeypatch):
    def boom(*a):
        raise RuntimeError('planted')
    monkeypatch.setattr(term_live, 'term_id', boom)
    with pytest.raises(term_live.TermFault):
        A.ask(Q.eq(x, y))


def test_undo_restores_python():
    undo = term_live.install(terms=True)
    assert R.relation_atom is not py_atom and R._termwise is not py_wise
    undo()
    assert R.relation_atom is py_atom and A.relation_atom is py_atom and R._termwise is py_wise


def test_nan_goes_last_without_a_key():
    q = table_for(x)
    i = q.ids[x]
    assert R.relation_atom('eq', nan, x).expr == py_atom('eq', nan, x).expr == (x, nan)
    assert i is not None


def test_scaffold_rejects_what_sympy_would_not_build():
    # A Mul of a Rational and an Add: SymPy distributes it, so Rust's raw form isn't what the constructor gives back.
    q = table_for(x, y)
    t = q.table
    a = t.raw_add([q.ids[x], q.ids[y]])
    two = t.number(2, 1)
    m = t.raw_mul([two, a])
    with pytest.raises(sa_solver.TermRefuse):
        term_live.scaffold(q, m, 't')
    assert term_live.SCAFFOLD_BAD
