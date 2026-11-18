"""The exact witness check before a contextual query's session (satassume/witness.py, issue 323; SLICE_WITNESS=1,
off by default). The tests of behaviour turn the switch on themselves and never read the plant flag."""
import os
from fractions import Fraction as F

import pytest
from sympy import Dummy, Float, I, Q, Rational, Symbol, oo, pi, sin, sqrt, symbols

from satassume import sympy_api as A
from satassume import witness as W
from satassume.knowledge.extensions import Extensions
from satassume.knowledge.rules import BASIS, DEFINITIONS

x, y, z = symbols('x y z')
xp = Symbol('xp', positive=True)
xi = Symbol('xi', integer=True)


@pytest.fixture
def on():
    old = W.ENABLED[0]
    W.ENABLED[0] = True
    yield
    W.ENABLED[0] = old


def pair(p, a):
    return W.witnesses(A._formula(p, True), A._formula(a, True, True))


def both(p, a):
    """The answer with the switch off and with it on, each from a fresh engine."""
    out = []
    old = W.ENABLED[0]
    try:
        for sw in (False, True):
            W.ENABLED[0] = sw
            try:
                out.append(A.ask(p, a, A.Engine()))
            except ValueError:
                out.append('ValueError')
    finally:
        W.ENABLED[0] = old
    return out


# value: (algebraic complex composite even ext_neg ext_pos ext_real finite imaginary integer prime rational zero), by hand
ROWS = {
    F(0):     (1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1),
    F(1):     (1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0),
    F(-1):    (1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0),
    F(2):     (1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0),
    F(4):     (1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0),
    F(9):     (1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0),
    F(7):     (1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0),
    F(-4):    (1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 0),
    F(1, 2):  (1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0),
    F(-3, 2): (1, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0),
    F(97):    (1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0),
    F(91):    (1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0),
}


@pytest.mark.parametrize('v', sorted(ROWS))
def test_table_at_a_rational(v):
    names = [n for n in BASIS if n != 'polar']
    assert tuple(int(W.TABLE[n](v)) for n in names) == ROWS[v]
    assert tuple(int(W.TABLE[n](int(v))) for n in names) == ROWS[v] or v.denominator != 1


def test_table_is_the_basis_and_polar_is_undecided():
    assert tuple(W.TABLE) == BASIS and W.TABLE['polar'] is None
    with pytest.raises(W._Undecided):
        W._pred('polar')
    with pytest.raises(W._Undecided):
        W._pred('sexyprime')
    with pytest.raises(W._Undecided):
        W.TABLE['prime'](F(10 ** 6 + 3))


def test_derived_predicates_follow_the_definitions():
    want = {'real': (1, 1, 1), 'positive': (0, 1, 0), 'negative': (0, 0, 1), 'nonzero': (0, 1, 1), 'odd': (0, 0, 0),
            'irrational': (0, 0, 0), 'noninteger': (0, 1, 1), 'infinite': (0, 0, 0), 'transcendental': (0, 0, 0),
            'antihermitian': (1, 0, 0), 'hermitian': (1, 1, 1), 'commutative': (1, 1, 1), 'nonnegative': (1, 1, 0),
            'nonpositive': (1, 0, 1), 'extended_nonzero': (0, 1, 1), 'positive_infinite': (0, 0, 0)}
    for name, row in want.items():
        assert name in DEFINITIONS
        f = W._pred(name)
        assert tuple(int(f(v)) for v in (F(0), F(1, 2), F(-3, 2))) == row, name
    assert W._pred('odd')(F(3)) is True


def test_a_pair_is_two_points_with_both_values():
    syms, yes, no, tried = pair(Q.positive(x + y), Q.positive(x))
    pt = dict(zip(syms, yes)), dict(zip(syms, no))
    assert pt[0][x] > 0 and pt[1][x] > 0
    assert pt[0][x] + pt[0][y] > 0 and not pt[1][x] + pt[1][y] > 0
    syms, yes, no, tried = pair(Q.gt(x, 1), Q.gt(x, 0) & Q.lt(x, 3))
    assert 1 < yes[0] < 3 and 0 < no[0] <= 1
    syms, yes, no, tried = pair(Q.integer(x / 3), Q.integer(x))
    assert yes[0] % 3 == 0 and no[0] % 3 != 0 and no[0].denominator == 1


@pytest.mark.parametrize('p, a', [
    (Q.positive(sin(x)), Q.real(x)),            # a function
    (Q.positive(Symbol('pp', polar=True)), Q.real(x)),    # polar, as a symbol's own assumption
    (Q.positive(x * Float(1.5)), Q.real(x)),    # a Float
    (Q.positive(x + oo), Q.real(x)),            # an infinity
    (Q.positive(x + pi), Q.real(x)),            # a transcendental constant
    (Q.positive(x + I), Q.real(x)),             # the imaginary unit
    (Q.positive(x + sqrt(2)), Q.real(x)),       # a root
    (Q.finite(x), Q.extended_real(x)),          # the False side needs an infinity
    (Q.real(x), Q.positive(x)),                 # entailed: one value only
    (Q.negative(x), Q.positive(x)),             # refuted: one value only
    (Q.prime(x), Q.integer(x) & (x > 4) & (x < 6)),     # one point satisfies the set
    (Q.positive(x), Q.positive(x) & Q.negative(x)),     # no point satisfies the set
    (Q.zero(x ** 2 - 2), Q.rational(x)),        # false at every rational
    (Q.positive(2 ** x), Q.rational(x)),        # true where decided, undecided at 1/2
])
def test_falls_through(p, a):
    assert pair(p, a) is None


def test_a_noncommutative_symbol_and_a_wild_have_no_value():
    from sympy import Wild
    n = Symbol('n', commutative=False)
    q = W._Query()
    for t in (n, Wild('w')):
        try:
            f = W._term(t, q, set())
            own = W._own(t)
        except W._Undecided:
            continue
        assert not any(own(v) for v in (0, 1, F(1, 2)))


def test_power_is_exact_or_undecided():
    q = W._Query()
    f = W._term(x ** y, q, set())
    assert f([F(1, 2), -3]) == 8 and f([2, 10]) == 1024 and f([0, 2]) == 0
    for pt in ([4, F(1, 2)], [0, 0], [0, -1], [2, 65], [2 ** 70, 64]):
        with pytest.raises(W._Undecided):
            f(pt)


def test_own_assumptions_bound_the_points():
    assert pair(Q.positive(xp), Q.integer(xp)) is None
    syms, yes, no, tried = pair(Q.even(xi), Q.positive(xi))
    assert yes[0].denominator == 1 and no[0].denominator == 1 and yes[0] > 0 and no[0] > 0
    d = Dummy('d', negative=True)
    assert pair(Q.negative(d), Q.integer(d)) is None


def test_integer_is_false_at_a_half(on):
    # a wrong table entry (integer true at 1/2) would make x = 1/2 a point of the set and 2*x = 1 odd there
    assert A.ask(Q.even(2 * x), Q.integer(x), A.Engine()) is True
    assert both(Q.integer(x + Rational(1, 2)), Q.integer(x)) == [False, False]


def test_one_witness_is_not_enough(on):
    assert A.ask(Q.real(x), Q.positive(x), A.Engine()) is True
    assert A.ask(Q.positive(x), Q.negative(x), A.Engine()) is False
    assert A.ask(Q.gt(x, 0), Q.gt(x, 1), A.Engine()) is True


def test_the_symbols_own_assumptions_count(on):
    assert A.ask(Q.positive(xp), Q.integer(xp), A.Engine()) is True
    assert A.ask(Q.rational(xi + y), Q.rational(y), A.Engine()) is True


def test_an_inconsistent_set_still_raises(on):
    with pytest.raises(ValueError):
        A.ask(Q.positive(y), Q.positive(x) & Q.negative(x) & Q.real(y), A.Engine())
    with pytest.raises(ValueError):
        A.ask(Q.positive(x), Q.positive(x) & Q.negative(x), A.Engine())


def test_registered_knowledge_falls_through():
    class Eng:
        extensions = Extensions()
    fp, fa = A._formula(Q.positive(x), True), A._formula(Q.real(x), True, True)
    assert W.witnesses(fp, fa, Eng) is not None
    Eng.extensions._vocab['positive'] = [((Symbol,), lambda e: True)]
    assert W.witnesses(fp, fa, Eng) is None


def test_off_means_not_called(monkeypatch):
    assert W.ENABLED[0] == (os.environ.get('SLICE_WITNESS') == '1')
    old = W.ENABLED[0]
    W.ENABLED[0] = False

    def boom(*a):
        raise AssertionError('the check ran with the switch off')
    monkeypatch.setattr(W, 'independent', boom)
    try:
        assert A.ask(Q.positive(x), Q.real(x), A.Engine()) is None
    finally:
        W.ENABLED[0] = old


def test_on_skips_the_session(on):
    eng = A.Engine()
    assert A.ask(Q.positive(x), Q.real(x), eng) is None
    assert eng.stats['queries'] == 0        # certified before Engine.ask
    assert A.ask(Q.real(x), Q.positive(x), eng) is True
    assert eng.stats['queries'] >= 1        # not certified: the unchanged path


def test_the_cap_bounds_the_points_tried():
    old = W.CAP[0]
    try:
        W.CAP[0] = 1
        assert pair(Q.positive(x), Q.real(x)) is None
        W.CAP[0] = 2
        assert pair(Q.positive(x), Q.real(x))[3] == 2
    finally:
        W.CAP[0] = old


QUERIES = [
    (Q.positive(x), Q.real(x)), (Q.real(x), Q.positive(x)), (Q.even(2 * x), Q.integer(x)), (Q.positive(x + y), Q.positive(x)),
    (Q.positive(x + y), Q.positive(x) & Q.positive(y)), (Q.gt(x, 1), Q.gt(x, 0) & Q.lt(x, 3)), (x > y, Q.positive(x - y + 1)),
    (x > y, Q.positive(x - y)), (Q.integer(x), Q.eq(3 * x, 1)), (Q.zero(x * y), Q.zero(x) | Q.zero(y)),
    (Q.nonzero(x * y), Q.nonzero(x)), (Q.odd(x + 1), Q.even(x)), (Q.odd(x + y), Q.even(x)), (Q.prime(x), Q.even(x) & (x > 2)),
    (Q.prime(x), Q.even(x) & Q.positive(x)), (Q.composite(x), Q.integer(x) & (x > 3)), (Q.le(x, y), Q.lt(x, y + 1)),
    (Q.le(x, y), Q.lt(x + 1, y)), (Q.eq(x, y), Q.le(x, y) & Q.ge(x, y)), (Q.ne(x, y), Q.le(x, y)),
    (Q.positive(x ** 2), Q.real(x)), (Q.nonnegative(x ** 2), Q.real(x)), (Q.positive(x ** 2), Q.nonzero(x)),
    (Q.rational(x / 2), Q.integer(x)), (Q.integer(x / 2), Q.integer(x)), (Q.integer(x / 2), Q.even(x)),
    (Q.finite(x + y), Q.finite(x)), (Q.positive(xp + y), Q.nonnegative(y)), (Q.positive(xp + y), Q.real(y)),
    (Q.even(xi * y), Q.integer(y)), (Q.even(xi * (xi + 1)), Q.integer(y)), (Q.negative(x), Q.positive(x) | Q.zero(y)),
    (Q.positive(x) | Q.negative(x), Q.nonzero(x)), (Q.positive(x) & Q.negative(y), Q.real(x) & Q.real(y)),
    (Q.positive(x), Q.positive(x) & Q.negative(x)), (Q.positive(z), Q.gt(z, x) & Q.gt(x, y) & Q.ge(y, 0)),
    (Q.positive(z), Q.gt(z, x) & Q.gt(x, y) & Q.ge(y, -1)), (Q.irrational(x), Q.real(x) & ~Q.rational(x)),
    (Q.imaginary(x), Q.real(x)), (Q.algebraic(x), Q.rational(x)), (Q.gt(2 * x, x), Q.positive(x)), (Q.gt(2 * x, x), Q.real(x)),
]


@pytest.mark.parametrize('i', range(len(QUERIES)))
def test_answers_are_equal_on_and_off(i):
    off, on_ = both(*QUERIES[i])
    assert off == on_
