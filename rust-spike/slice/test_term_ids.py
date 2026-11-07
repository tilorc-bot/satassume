"""Slice B of component 4: `relation_atom`, `_termwise`, `_eq_links` and the sort sites answered by Rust through ids.

Each test compares Rust's answer with Python's own function on the same terms, or shows a plant being caught.
"""
import pytest
from sympy import And, Function, Q, S, Symbol, exp, nan, oo, pi, sqrt

import convert
import sa_solver
import term_live
from harness.state import reset_module_state
from satassume import engine as E, relations as R, sympy_api as A

x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
f, g = Function('f'), Function('g')
n = Symbol('n', commutative=False)
py_atom = R.relation_atom
py_wise = R._termwise
ENGINE = A.default_engine


def fresh():
    """As `test_term_live.fresh`: no answer memo or session carries over, so a second `ask` runs again."""
    reset_module_state(sympy_cache=False)
    A.set_default_engine(E.Engine())


def clear():
    term_live.COUNTS.clear()
    del term_live.REFUSALS[:], term_live.SCAFFOLD_BAD[:], term_live.KEY_BAD[:], term_live.CHECK_BAD[:]


@pytest.fixture
def live():
    undo = term_live.install(terms=True)
    clear()
    fresh()
    yield term_live
    term_live.PLANT[0] = None
    term_live.CHECK[0] = False
    undo()
    fresh()


def table_for(*terms):
    c = convert.convert(And(*[Q.positive(t) for t in terms]), True, ENGINE())
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
    (2*x, x), (x*y, x), (f(x), g(x)), (x + 2*pi, y + pi), (x, -x), (x + y, x - y),
]


@pytest.mark.parametrize('a,b', DIFF_PAIRS)
def test_termwise_and_diff_against_python(a, b):
    q = table_for(a, b)
    i, j = term_live.term_id(q, a, 't'), term_live.term_id(q, b, 't')
    real = a - b
    k = q.table.sub(i, j)       # `REFUSED_DIFFS` are the shapes this doesn't answer
    assert term_live.scaffold(q, k, 't') == real
    assert q.table.termwise(i, j, k) is py_wise(a, b, real)
    got = q.table.eq_diff(i, j)
    want = None if R._is_number(real) or not py_wise(a, b, real) else real
    assert (None if got is None else term_live.scaffold(q, got, 't')) == want


def test_negating_a_numeric_power_refuses():
    # `-(-sqrt(2))`: the crate's `mul` refuses a coefficient beside a numeric-base power, here at `sub`.
    a, b = x + sqrt(2), y - sqrt(2)
    q = table_for(a, b)
    with pytest.raises(sa_solver.TermRefuse, match='numeric-base power'):
        q.table.sub(term_live.term_id(q, a, 't'), term_live.term_id(q, b, 't'))


def inside_the_run(monkeypatch, f):
    """`f` runs inside a query, where `current()` is its table. `sympy_api._ask` is `term_live`'s wrapper, so a spy on it
    would sit outside the run: this goes one call further in."""
    seen = []
    real = A._engine_ask

    def spy(p, a, e):
        seen.append(f())
        return real(p, a, e)
    monkeypatch.setattr(A, '_engine_ask', spy)
    return seen


@pytest.mark.parametrize('name', ['eq', 'ne', 'lt', 'le', 'gt', 'ge'])
def test_every_relation_on_the_live_path(live, monkeypatch, name):
    seen = inside_the_run(monkeypatch, lambda: (term_live.current(), R.relation_atom(name, x + 1, y + 1)))
    A.ask(Q.eq(x + 1, y + 1), Q.positive(x))
    q, atom = seen[0]
    assert q is not None and q.kept is None
    assert atom == py_atom(name, x + 1, y + 1)
    assert (live.counts().get('term:rust:relation_atom', 0) > 0) is True


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
    fresh()
    live.PLANT[0] = 'termwise-false'
    assert A.ask(Q.eq(x, y), Q.zero(x - y)) is not True


def test_a_swap_plant_shows_in_the_check(live):
    live.CHECK[0] = True
    live.PLANT[0] = 'swap'
    A.ask(Q.eq(x + 1, y), Q.positive(x))
    c = live.counts()
    assert c['check:differs:relation_atom'] > 0 and live.CHECK_BAD


def test_a_key_plant_answers_on_python(live):
    # The sort sites that remain are in `lra_adapter`: this query reaches one.
    p, a = Q.gt(x + y, 1), Q.gt(x, 1) & Q.gt(y, 0)
    want = A.ask(p, a)
    fresh()
    clear()
    live.PLANT[0] = 'key-reverse'
    assert A.ask(p, a) is want is True
    c = live.counts()
    assert c["refused:key: differs from Python's"] == 1 and c['refused'] == 1


def test_a_scaffold_plant_answers_on_python(live):
    # On a fresh engine the glue has already built each difference. `scaffold` builds one only where a memo from an earlier
    # query saved the glue's work, so the first query is the point here.
    assert A.ask(Q.eq(x, y), Q.zero(x - y)) is True
    clear()
    live.PLANT[0] = 'scaffold-form'
    assert A.ask(Q.ne(x, y), Q.nonzero(x - y)) is True
    c = live.counts()
    assert c['refused:scaffold: rebuilt form differs from Rust'] == 1 and c['refused'] == 1


@pytest.mark.parametrize('p,reason', [
    (Q.eq(x + 1.5, y), 'algebra: holds an infinity, nan or Float'),
    (Q.eq(x + oo, y), 'algebra: holds an infinity, nan or Float'),
    (Q.eq(x*n, y*n), 'algebra: non-commutative'),
])
def test_a_shape_the_algebra_refuses_answers_on_python(p, reason):
    fresh()
    want = A.ask(p)     # no wrapper here: Python's own answer
    undo = term_live.install(terms=True)
    try:
        clear()
        fresh()
        got = A.ask(p)
        c = term_live.counts()
    finally:
        undo()
        fresh()
    assert got is want
    assert c['refused'] == 1 and c['refused:' + reason] == 1, c


def test_an_unknown_term_stays_on_python_for_that_call(live, monkeypatch):
    w = Symbol('w')     # no row, in a class that has one
    seen = inside_the_run(monkeypatch, lambda: R.relation_atom('eq', w + 1, x + 1))
    A.ask(Q.positive(x))
    c = live.counts()
    assert seen[0] == py_atom('eq', w + 1, x + 1)
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
    q = table_for(nan, x)
    i, j = q.ids[nan], q.ids[x]
    assert q.table.eq_sides(i, j) == (j, i) and q.table.eq_sides(j, i) == (j, i)
    assert py_atom('eq', nan, x).expr == (x, nan)


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
