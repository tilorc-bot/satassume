"""The native witness check (solver_rs/src/witness.rs behind witness_live.py, SLICE_WITNESS_RUST=1; sa-port-351, issue
323) against Python's satassume/witness.py, the reference. No test reads a plant's flag: each compares the native side
with what witness.py gives for the same input. Plants 760-764 (SLICE_WITNESS_RUST_PLANT) and the test that catches each:
760 wn-integer-half   test_the_native_table_is_pythons
761 wn-work-one       test_the_work_bound_trips_on_the_same_evaluation
762 wn-skip-patched   test_a_users_method_on_the_engine_is_left_to_the_engine
763 wn-int-side       test_a_python_int_side_goes_to_python
764 wn-skip-own       test_a_replaced_function_of_witness_py_is_called
The module needs the slice's .so and no installed backend: a query's table is pushed as term_live._ask pushes it.
"""
import os
from fractions import Fraction

import pytest

sa_solver = pytest.importorskip('sa_solver')
from sympy import And, Dummy, Eq, Integer, Q, Rational, Symbol, pi, sin
from satassume import sympy_api as A, witness as W
from satassume.knowledge.extensions import Args
from satassume.knowledge.rules import BASIS, DEFINITIONS
from satassume.sat.formula import P

import term_live
import witness_live

x, y = Symbol('x'), Symbol('y')
n = Symbol('n', integer=True, positive=True)


@pytest.fixture(autouse=True)
def _plant():
    witness_live.plant(os.environ.get('SLICE_WITNESS_RUST_PLANT') or None)
    yield
    witness_live.plant(None)
    W.NATIVE[0] = None


def both(prop, assum, eng=None, query=None):
    """(native, reference) for one query: `witnesses` with the hook on, then off, under the query's own table."""
    e = A.default_engine()
    rel = bool(e.relation_specs)
    q = term_live._convert(*(query or (prop, assum)), e)
    fp = prop if isinstance(prop, P) and query else A._formula(prop, rel)
    fa = assum if isinstance(assum, P) and query else A._formula(assum, rel, True)
    s = term_live.stack()
    s.append(q)
    try:
        W.NATIVE[0] = witness_live.native
        rn = W.witnesses(fp, fa, eng)
        W.NATIVE[0] = None
        rp = W.witnesses(fp, fa, eng)
    finally:
        W.NATIVE[0] = None
        s.pop()
    return rn, rp


def moved(f):
    """What a call adds to the counters 706-713."""
    c0 = witness_live.counts()
    out = f()
    c1 = witness_live.counts()
    return out, {k: c1[k] - c0[k] for k in c1 if c1[k] != c0[k]}


QUERIES = [
    (Q.positive(x), Q.real(x)), (Q.positive(x + y), Q.positive(x)), (Q.even(n), Q.integer(n)), (Q.prime(n), Q.odd(n)),
    (x > 1, Q.positive(x)), (Eq(x, 2), x > 1), (x**2 > 4, Q.real(x)), (Q.positive(x - pi), Q.positive(x)),
    (x > pi, x > 3), (Q.rational(x * pi), Q.real(x)), (Q.positive(sin(x)), Q.real(x)), (Q.positive(x), Q.negative(x)),
    (Q.zero(x * y - 6), Q.integer(x) & Q.integer(y)), (Q.positive(x**y), Q.positive(x) & Q.integer(y)),
    (Q.negative(Dummy('d') + Rational(7, 3)), Q.real(x)), (Q.positive(1 / pi + x), Q.real(x)),
    (Q.composite(n + 10**7), Q.integer(n)), (x**3 - 3*x > 0, Q.real(x) & (x > -2)),
]


def test_the_native_check_is_pythons_per_query():
    certified = 0
    for prop, assum in QUERIES:
        (rn, rp), c = moved(lambda: both(prop, assum))
        assert rn == rp, (prop, assum)
        assert c.get('wn:compile') == 1 and not any(k.startswith('wn:fallback') for k in c), (prop, assum, c)
        certified += rp is not None
    assert certified >= 8


def values():
    rs = [Fraction(p, q) for p in (-7, -2, -1, 0, 1, 2, 3, 4, 9, 97, 10**6 + 3, 10**6 + 4) for q in (1, 2, 3)]
    pis = [(0, 1), (-3, 1), (Fraction(-22, 7), 1), (3, 0, 1), (-10, 0, 1), (Fraction(-314159, 100000), 1),
           (-Fraction(W._PI_N, W._PI_D), 1)]
    return rs + [W._PiPoly(tuple(c)) for c in pis]


def coeffs(v):
    c = v.c if type(v) is W._PiPoly else (v,)
    return [(Fraction(a).numerator, Fraction(a).denominator) for a in c]


def test_the_native_table_is_pythons():
    """Every predicate of the vocabulary and one name outside it, at rationals and at values of Q[pi]; then eq and lt."""
    for name in BASIS + tuple(DEFINITIONS) + ('sexyprime',):
        for v in values():
            try:
                want = W._pi_pred(name)(v)
            except W._Undecided:
                want = None
            assert sa_solver.witness_pred(name, coeffs(v)) is want, (name, v)
    for a in values():
        for b in values():
            for name in W.RELATIONS:
                try:
                    want = W.PI_TABLE[name](a, b)
                except W._Undecided:
                    want = None
                assert sa_solver.witness_rel(name, coeffs(a), coeffs(b)) is want, (name, a, b)


def test_the_native_definitions_are_the_rules():
    got = {name: ' & '.join(('' if want else '!') + b for b, want in lits) for name, lits in sa_solver.witness_definitions()}
    assert got == {name: DEFINITIONS[name] for name in W.TWO_WAY}


def test_the_work_bound_trips_on_the_same_evaluation():
    """At Python's own work count the query is certified on both sides; one below, on neither."""
    prop, assum = x**3 - 3*x > 0, Q.real(x) & (x > -2)
    seen = []

    class Rec(W._Query):
        __slots__ = ()

        def __init__(self, pi=False):
            super().__init__(pi)
            seen.append(self)
    old, bound = W._Query, W.WORK[0]
    W._Query = Rec          # Python's count only: with a class of witness.py replaced, both calls are witness.py's
    try:
        rp = both(prop, assum)[1]
        work = seen[-1].work
        assert rp is not None and work > 0
    finally:
        W._Query = old
    try:
        for w, certified in ((bound, True), (work, True), (work - 1, False), (0, True)):
            W.WORK[0] = w
            (rn, rp), c = moved(lambda: both(prop, assum))
            assert (rp is not None) is certified and rn == rp and c.get('wn:search') == 1, (w, c)
    finally:
        W.WORK[0] = bound


def test_the_cap_trips_on_the_same_point():
    old = W.CAP[0]
    try:
        # the query of the list that Python certifies after the most points
        tried, prop, assum = max(((r[1][3], p, a) for r, p, a in ((both(p, a), p, a) for p, a in QUERIES) if r[1]),
                                 key=lambda t: t[0])
        assert 2 < tried < old
        for cap in (tried, tried - 1, 0):
            W.CAP[0] = cap
            rn, rp = both(prop, assum)
            assert rn == rp and (rp is None) == (cap == tried - 1), cap
    finally:
        W.CAP[0] = old


def test_a_users_method_on_the_engine_is_left_to_the_engine():
    """Formula ruling P1 as the check applies it: with a user's `verdict` on the engine no point is tried."""
    from satassume.engine import Engine
    eng = Engine()
    prop, assum = Q.positive(x), Q.real(x)
    (rn, rp), c = moved(lambda: both(prop, assum, eng))
    assert rp is not None and rn == rp and c.get('wn:found') == 1
    eng.verdict = lambda *a, **k: Engine.verdict(eng, *a, **k)
    (rn, rp), c = moved(lambda: both(prop, assum, eng))
    assert rp is None and rn is None and 'wn:search' not in c, c


def test_a_python_int_side_goes_to_python():
    """`3 == Integer(3)` with one hash, so the lookup finds the Integer's row for a plain int side, which witness.py
    leaves undecided: the row's object is compared by type and the query goes to Python (`wn:fallback:type`)."""
    query = (x > Integer(3), Q.real(x))
    for three, why in ((3, 'wn:fallback:type'), (True, 'wn:fallback:miss')):
        (rn, rp), c = moved(lambda: both(P('lt', Args((three, x))), P('extended_real', x), query=query))
        assert rp is None and rn is None and c.get(why) == 1, (three, c)
    rn, rp = both(P('lt', Args((Integer(3), x))), P('extended_real', x), query=query)
    assert rp is not None and rn == rp


def test_what_is_not_mirrored_goes_to_python_and_is_counted():
    """Each fallback counter fires, so its zero on a workload says something."""
    query = (Q.positive(x), Q.real(x))

    class Odd:
        args = ()
    z = Symbol('z')
    for prop, why in ((P('positive', z), 'wn:fallback:miss'), (P(7, x), 'wn:fallback:shape')):
        (rn, rp), c = moved(lambda: both(prop, P('extended_real', x), query=query))
        assert rn == rp and c.get(why) == 1, (prop, c)
    q = term_live._convert(*query, A.default_engine())
    s = term_live.stack()
    s.append(q)
    W.NATIVE[0] = witness_live.native
    try:
        _, c = moved(lambda: W.witnesses(Odd(), P('extended_real', x)))
        assert c.get('wn:fallback:shape') == 1, c
    finally:
        s.pop()
    # outside any query of the slice, and under a plant of witness.py: before the native compile
    for plant in ('', 'single'):
        old, W.PLANT[0] = W.PLANT[0], plant
        try:
            if plant:
                s.append(q)
            r, c = moved(lambda: W.witnesses(P('positive', x), P('extended_real', x)))
            assert c == {'wn:fallback:off': 1} and r is not None, (plant, c)
        finally:
            W.PLANT[0] = old
            if plant:
                s.pop()
    W.NATIVE[0] = None


def test_a_replaced_function_of_witness_py_is_called(monkeypatch):
    """What a test or an instrument puts in place of one of witness.py's own functions is called: the query goes to
    witness.py before the native compile, and the wrapper sees the reference's points both times (sa-port-353:
    tests/test_witness.py::test_a_set_the_engine_knows_inconsistent_tries_no_point counts points through `_holds`).
    A wrapper around an entry point or a guard, which witness.py calls by name anyway, keeps the native path."""
    seen = []
    real = W._holds

    def holds(pt, *rest):
        seen.append(list(pt))
        return real(pt, *rest)
    monkeypatch.setattr(W, '_holds', holds)
    (rn, rp), c = moved(lambda: both(Q.positive(x), Q.real(x)))
    half = len(seen) // 2
    assert rn == rp and rn is not None and c == {'wn:fallback:off': 1}, c
    assert half and seen[:half] == seen[half:]
    monkeypatch.undo()
    monkeypatch.setattr(W, '_patched', lambda eng, real=W._patched: real(eng))
    (rn, rp), c = moved(lambda: both(Q.positive(x), Q.real(x)))
    assert rn == rp and c.get('wn:found') == 1 and 'wn:fallback:off' not in c, c


def test_nothing_native_outlives_the_call():
    """The compiled query is the call's own: two calls on one table give two objects, and the table holds no more
    than the symbols' reads."""
    q = term_live._convert(Q.positive(x), Q.real(x), A.default_engine())
    fp, fa = P('positive', x), P('extended_real', x)
    h1 = sa_solver.witness_compile(q.table, q.ids, q.objects, fa, fp, witness_live._classes())
    h2 = sa_solver.witness_compile(q.table, q.ids, q.objects, fa, fp, witness_live._classes())
    assert h1 is not h2 and h1.work == 0 and h1.syms == h2.syms
    assert h1.search(32, 2000, 2500) == h2.search(32, 2000, 2500) and h1.work == h2.work > 0
