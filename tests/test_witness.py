"""The exact witness check before a contextual query's session (satassume/witness.py, issue 323; SLICE_WITNESS=1,
off by default). The tests of behaviour turn the switch on themselves and never read the plant flag."""
import os
import sys
from fractions import Fraction as F

import pytest
from sympy import Dummy, Float, I, Q, Rational, Symbol, cos, exp, oo, pi, sin, sqrt, symbols

from satassume import sympy_api as A
from satassume import witness as W
from satassume.knowledge import extensions as E
from satassume.knowledge.extensions import Args, Extensions
from satassume.knowledge.rules import BASIS, DEFINITIONS
from satassume.knowledge.templates import _common as TC
from satassume.knowledge.templates import registry
from satassume.relations import AdapterSpec, default_specs
from satassume.sat.formula import Formula, P
from satassume.state.epoch import bump

x, y, z = symbols('x y z')
xp = Symbol('xp', positive=True)
xi = Symbol('xi', integer=True)


_OWN = 'satassume.knowledge.templates.'      # the package's own template modules; anyone else's are a user's


def _users(templates):
    return [t for t in templates if not str(getattr(t, '__module__', '')).startswith(_OWN)]


def _take_users_templates():
    """Takes every user's template and declared module off the default registry and returns them. The package's
    own stay, those of a built-in module loaded since the last call too: a declared module registers itself once,
    when it is imported, so putting back an earlier copy of the lists would lose its templates for good."""
    by_class = {c: _users(ts) for c, ts in registry._by_class.items()}
    lazy = [(c, m) for c, m in registry._lazy if not m.startswith(_OWN)]
    by_class = {c: ts for c, ts in by_class.items() if ts}
    if by_class or lazy:
        for c, users in by_class.items():
            rest = [t for t in registry._by_class[c] if not any(t is u for u in users)]
            if rest:
                registry._by_class[c] = rest
            else:
                del registry._by_class[c]
        registry._lazy = [(c, m) for c, m in registry._lazy if m.startswith(_OWN)]
        _templates_changed()
    return by_class, lazy


def _put_back_users_templates(by_class, lazy):
    """A user's template comes after every built-in one of its class, as ``register`` has it."""
    if by_class or lazy:
        for c, ts in by_class.items():
            registry._by_class.setdefault(c, []).extend(ts)
        registry._lazy = registry._lazy + lazy
        _templates_changed()


def _templates_changed():
    """What ``TemplateRegistry.register`` drops for a new template."""
    registry._mro_cache.clear()
    registry._clauses_cache.clear()
    TC._CACHE.clear()
    bump()


@pytest.fixture(autouse=True)
def clean_default_registry():
    """Every test here runs with no user's template on the default registry, and leaves the registry as it found
    it. A template another test left there (tests/test_templates.py and tests/test_p4_review.py did) is a user's
    knowledge for every engine of the process, so nothing would be certified. That is the guard working, which
    ``test_a_template_left_on_the_default_registry_makes_the_check_fall_through`` asserts, and not what the other
    tests are about. What a test here registers is taken off afterwards, and what was set aside is put back."""
    before = _take_users_templates()
    yield
    _take_users_templates()
    _put_back_users_templates(*before)


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
    assert tuple(W.TABLE) == BASIS + ('eq', 'lt') and len(W.TABLE) == 16 and W.TABLE['polar'] is None
    for name in ('eq', 'lt'):       # the relations are not unary predicates
        with pytest.raises(W._Undecided):
            W._pred(name)
    with pytest.raises(W._Undecided):
        W._pred('polar')
    with pytest.raises(W._Undecided):
        W._pred('sexyprime')
    with pytest.raises(W._Undecided):
        W.TABLE['prime'](F(10 ** 6 + 3))


def test_derived_predicates_follow_the_definitions():
    want = {'real': (1, 1, 1), 'positive': (0, 1, 0), 'negative': (0, 0, 1), 'nonzero': (0, 1, 1), 'odd': (0, 0, 0),
            'irrational': (0, 0, 0), 'noninteger': (0, 1, 1), 'infinite': (0, 0, 0), 'transcendental': (0, 0, 0),
            'hermitian': (1, 1, 1), 'commutative': (1, 1, 1), 'nonnegative': (1, 1, 0),
            'nonpositive': (1, 0, 1), 'extended_nonzero': (0, 1, 1), 'positive_infinite': (0, 0, 0),
            'negative_infinite': (0, 0, 0), 'extended_nonnegative': (1, 1, 0), 'extended_nonpositive': (1, 0, 1)}
    assert set(want) == (set(W.TWO_WAY) | set(W.ONE_WAY)) - {'antihermitian'} == set(DEFINITIONS) - {'antihermitian'}
    for name, row in want.items():
        f = W._pred(name)
        assert tuple(int(f(v)) for v in (F(0), F(1, 2), F(-3, 2))) == row, name
    assert W._pred('odd')(F(3)) is True


def test_the_relations_compare_two_rationals():
    eq, lt = W.TABLE['eq'], W.TABLE['lt']
    assert eq(F(1, 2), F(2, 4)) is True and eq(F(1, 2), F(1, 3)) is False and eq(2, F(4, 2)) is True
    assert lt(F(1, 3), F(1, 2)) is True and lt(F(1, 2), F(1, 2)) is False and lt(F(-1, 2), F(-1, 3)) is True
    assert lt(F(1, 2), 0) is False and lt(-1, F(-1, 2)) is True


# sympy/assumptions/facts.py, its unary facts on the predicates the old rule base does not have (the two infinite
# ones, hermitian, antihermitian), as rule strings; _FACTS_TEXT is where each stands in that file's source
_FACTS = (
    'extended_positive == positive | positive_infinite', 'extended_negative == negative | negative_infinite',
    'positive -> !positive_infinite', 'negative -> !negative_infinite',
    'positive_infinite -> infinite', 'negative_infinite -> infinite',
    'real -> hermitian', 'imaginary -> antihermitian', 'zero -> hermitian | antihermitian',
)
_FACTS_TEXT = (
    'Equivalent(Q.extended_positive(x), Q.positive(x) | Q.positive_infinite(x))',
    'Equivalent(Q.extended_negative(x), Q.negative(x) | Q.negative_infinite(x))',
    'Exclusive(Q.negative_infinite(x), Q.negative(x), Q.zero(x),',
    'Implies(Q.negative_infinite(x) | Q.positive_infinite(x), Q.infinite(x))',
    'Implies(Q.real(x), Q.hermitian(x))', 'Implies(Q.imaginary(x), Q.antihermitian(x))',
    'Implies(Q.zero(x), Q.hermitian(x) | Q.antihermitian(x))',
)


def _sympys_rules():
    """SymPy's own unary rules as clauses over the vocabulary: every string rule of sympy/core/assumptions.py, read
    from its source, plus _FACTS. None of the engine's own two-way readings (rules.py) is in it."""
    import inspect, re, sys
    from satassume.knowledge.rules import PRED_INDEX, compile_rules
    __import__('sympy.core.assumptions')
    src = inspect.getsource(sys.modules['sympy.core.assumptions'])
    block = src.split('_assume_rules = FactRules([')[1].split('])')[0]
    old = [re.sub(r'\s+', ' ', r).strip() for r in re.findall(r"'([^']+)'", block)]
    assert len(old) > 30 and 'extended_real -> commutative' in old and not [r for r in old if 'hermitian ==' in r]
    __import__('sympy.assumptions.facts')
    facts = inspect.getsource(sys.modules['sympy.assumptions.facts'])
    assert [t for t in _FACTS_TEXT if t not in facts] == []
    assert 'Equivalent(Q.hermitian' not in facts and 'Equivalent(Q.antihermitian' not in facts
    return list(compile_rules(old + list(_FACTS), PRED_INDEX)), PRED_INDEX


def _satisfiable(clauses, nv):
    from test_rules import _count_models
    return _count_models(clauses, nv) > 0


def test_two_way_definitions_follow_from_sympys_rules():
    """Each TWO_WAY definition is entailed in both directions by SymPy's own rules; each ONE_WAY one is not, and
    for those the rules give every rational hermitian and commutative and leave antihermitian open at zero and at a
    nonzero rational."""
    from satassume.knowledge.rules import PREDICATES, basis_lits
    rules, ix = _sympys_rules()
    nv = len(PREDICATES)
    lit = lambda l: (ix[BASIS[abs(l) - 1]] + 1) * (1 if l > 0 else -1)      # a basis literal in the vocabulary's numbering

    def two_way(name):
        d = ix[name] + 1
        op, ls = basis_lits(name)
        ls = [lit(l) for l in ls]
        if op == '&':       # d and not all, or all and not d
            fwd = rules + [(d,), tuple(-l for l in ls)]
            back = rules + [(-d,)] + [(l,) for l in ls]
        else:
            fwd = rules + [(d,)] + [(-l,) for l in ls]
            back = rules + [(-d,), tuple(ls)]
        return not _satisfiable(fwd, nv) and not _satisfiable(back, nv)

    assert [n for n in DEFINITIONS if two_way(n)] == [n for n in DEFINITIONS if n in W.TWO_WAY]
    assert sorted(n for n in DEFINITIONS if not two_way(n)) == sorted(W.ONE_WAY)
    rat = (ix['rational'] + 1,)
    for name in ('hermitian', 'commutative'):
        assert not _satisfiable(rules + [rat, (-(ix[name] + 1),)], nv), name
    ah, zero = ix['antihermitian'] + 1, ix['zero'] + 1
    for z in (zero, -zero):
        for a in (ah, -ah):
            assert _satisfiable(rules + [rat, (z,), (a,)], nv)


def test_antihermitian_is_undecided(on):
    with pytest.raises(W._Undecided):
        W._pred('antihermitian')
    assert pair(Q.antihermitian(x), Q.rational(x)) is None
    assert pair(Q.positive(x), Q.rational(x) & ~Q.antihermitian(x)) is None
    assert pair(Q.positive(x), Q.rational(x)) is not None
    assert both(Q.antihermitian(x), Q.rational(x)) == [None, None]
    assert both(Q.hermitian(x), Q.rational(x)) == [True, True]


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
    (Q.positive(x + exp(1)), Q.real(x)),            # a transcendental constant other than pi
    (Q.positive(x + cos(pi * x)), Q.real(x)),   # pi inside a function
    (Q.positive(x + sqrt(pi)), Q.real(x)),      # a root of pi: not in Q[pi]
    (Q.positive(x / pi), Q.real(x)),            # 1/pi: not in Q[pi]
    (Q.positive(x + pi ** x), Q.real(x)),       # pi**x is in Q[pi] only at x = 0, 1, 2, ...: undecided at 1/2
    (Q.positive(x + x ** pi), Q.real(x)),       # an exponent outside Q
    (Q.irrational(x), Q.real(x)),               # no pi in the query: no point outside Q is proposed
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


def test_an_own_assumption_undecided_at_a_value_leaves_the_value_out(on):
    # 10**7 is above the bound of the trial division, so prime is undecided there: the value is not proposed, and
    # nothing is raised (before sa-port-341 _Undecided left _pools and the query)
    p = Symbol('p', prime=True)
    assert pair(Q.gt(p, 10 ** 7), Q.integer(p)) is None
    assert both(Q.gt(p, 10 ** 7), Q.integer(p)) == [None, None]
    syms, yes, no, tried = pair(Q.gt(p, 3), Q.lt(p, 10 ** 7))
    assert yes[0] in (5, 7) and no[0] in (2, 3)


# ---- exact pi (sa-port-341) ----

def _atan_inv(n, terms):
    """Bounds of atan(1/n) = 1/n - 1/(3 n**3) + 1/(5 n**5) - ...: the terms alternate and decrease, so a partial sum
    that ends on a negative term is below the limit and the next partial sum is above it."""
    assert terms % 2 == 0
    s = sum(F((-1) ** k, (2 * k + 1) * n ** (2 * k + 1)) for k in range(terms))
    return s, s + F(1, (2 * terms + 1) * n ** (2 * terms + 1))


def _machin():
    """An enclosure of pi from Machin's formula pi = 16 atan(1/5) - 4 atan(1/239), in Fractions; no SymPy."""
    (a, b), (c, d) = _atan_inv(5, 50), _atan_inv(239, 16)
    return 16 * a - 4 * d, 16 * b - 4 * c


PI_LO, PI_HI = _machin()
PI = W._PiPoly((0, 1))


def enc(v):
    """Bounds of a value of Q[pi] by the test's own enclosure of pi (not witness.py's)."""
    if type(v) is not W._PiPoly:
        return F(v), F(v)
    lo = hi = F(v.c[0])
    for k in range(1, len(v.c)):
        a, b = v.c[k] * PI_LO ** k, v.c[k] * PI_HI ** k
        lo, hi = lo + min(a, b), hi + max(a, b)
    return lo, hi


def test_the_enclosure_holds_pi():
    assert 0 < PI_HI - PI_LO < F(1, 10 ** 60)
    lo, hi = F(W._PI_N, W._PI_D), F(W._PI_N + 1, W._PI_D)
    assert lo < PI_LO and PI_HI < hi and hi - lo == F(1, 10 ** 50)
    assert len(W._LO) == len(W._HI) == W._MAX_DEG + 1
    assert all(W._LO[k] == lo ** k and W._HI[k] == hi ** k for k in range(W._MAX_DEG + 1))


# value: (algebraic complex composite even ext_neg ext_pos ext_real finite imaginary integer prime rational zero), by
# hand: 22/7 and 355/113 are above pi, 9 < pi**2 < 10, 31 < pi**3 < 32
PI_ROWS = {
    'pi': (PI,                               (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
    '-pi': (-PI,                             (0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0)),
    'pi-3': (PI - 3,                         (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
    '22/7-pi': (F(22, 7) - PI,               (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
    'pi-355/113': (PI - F(355, 113),         (0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0)),
    'pi**2-10': (PI * PI - 10,               (0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0)),
    'pi**3-31': (PI ** 3 - 31,               (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
    '32-pi**3': (32 - PI ** 3,               (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
    'pi**2/2-3*pi+9/2': ((PI - 3) ** 2 / 2,  (0, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0)),
}


@pytest.mark.parametrize('v', sorted(PI_ROWS))
def test_table_at_a_value_of_q_pi(v):
    val, row = PI_ROWS[v]
    assert type(val) is W._PiPoly
    names = [n for n in BASIS if n != 'polar']
    assert tuple(int(W.PI_TABLE[n](val)) for n in names) == row
    assert W.PI_TABLE['polar'] is None and tuple(W.PI_TABLE) == tuple(W.TABLE)
    # the derived predicates through their definitions, and the two one-way ones
    f = {n: W._pi_pred(n)(val) for n in DEFINITIONS if n != 'antihermitian'}
    pos = bool(row[5])
    assert f['real'] and f['irrational'] and f['transcendental'] and f['noninteger'] and f['nonzero']
    assert f['hermitian'] and f['commutative'] and not f['odd'] and not f['infinite']
    assert f['positive'] is pos and f['negative'] is (not pos) and f['nonnegative'] is pos
    # at a rational the same function still reads TABLE
    assert W._pi_pred('rational')(F(1, 2)) is True and W._pi_pred('irrational')(3) is False


def test_q_pi_is_a_ring_with_one_polynomial_per_value():
    assert (PI + 1) * (PI - 1) == PI * PI - 1 == PI ** 2 - 1
    assert hash((PI + 1) * (PI - 1)) == hash(PI ** 2 - 1)
    assert (PI / 2) * 2 == PI and PI / 2 + PI / 2 == PI and 2 * PI - PI == PI and 1 - (1 - PI) == PI
    # a rational result is a rational again, never a _PiPoly
    for r, want in ((PI - PI, 0), (PI * 0, 0), ((PI + 1) - (PI - F(1, 2)), F(3, 2)), (PI ** 0, 1)):
        assert type(r) is not W._PiPoly and r == want
    assert PI != F(22, 7) and not (PI == 3) and PI + 1 != PI and (PI + F(1, 2)).c == (F(1, 2), 1)
    assert (PI - 1) ** 3 == PI ** 3 - 3 * PI ** 2 + 3 * PI - 1
    # what leaves Q[pi], or passes the guards, is undecided
    for f in (lambda: 1 / PI, lambda: PI / PI, lambda: PI / 0, lambda: PI ** -1, lambda: PI ** (W._MAX_DEG + 1),
              lambda: (PI ** W._MAX_DEG) * PI, lambda: (PI * 2 ** 3000) ** 2):
        with pytest.raises(W._Undecided):
            f()
    q = W._Query(True)
    f = W._term(x ** y, q, set())
    assert f([PI, 2]) == PI * PI and f([PI, 0]) == 1 and f([F(1, 2), -3]) == 8
    for pt in ([PI, -1], [2, PI], [PI, F(1, 2)], [PI, 65], [0, 0]):
        with pytest.raises(W._Undecided):
            f(pt)


def test_the_sign_is_exact_or_undecided():
    assert W._sign(F(-1, 2)) == -1 and W._sign(0) == 0 and W._sign(7) == 1
    assert W._sign(PI - 3) == 1 and W._sign(PI - F(22, 7)) == -1 and W._sign(F(355, 113) - PI) == 1
    assert W._sign(PI * PI - 10) == -1 and W._sign(PI ** 3 - 31) == 1
    lo = F(W._PI_N, W._PI_D)
    # inside the enclosure nothing is decided; a step of 10**-50 outside it, everything is
    for c in (lo, lo + F(1, 2 * 10 ** 50), lo + F(1, 10 ** 50)):
        with pytest.raises(W._Undecided):
            W._sign(PI - c)
    assert W._sign(PI - (lo - F(1, 10 ** 50))) == 1 and W._sign(PI - (lo + F(2, 10 ** 50))) == -1
    assert PI - 3 > 0 and PI < F(22, 7) and not PI > 4 and PI * 2 >= 6
    assert W.PI_TABLE['lt'](3, PI) and not W.PI_TABLE['lt'](PI, 3) and not W.PI_TABLE['lt'](PI, PI)
    assert W.PI_TABLE['lt'](1, 2) and not W.PI_TABLE['lt'](2, 1) and W.PI_TABLE['eq'](PI + 0, PI)
    assert not W.PI_TABLE['eq'](PI, 3) and not W.PI_TABLE['eq'](3, PI) and W.PI_TABLE['eq'](F(1, 2), F(2, 4))


def test_witness_points_with_pi_hold_by_the_tests_own_enclosure():
    # x from 3 to 63/20: the proposition x > pi has both values there. Each returned point is rational and is
    # checked with Machin's bounds, not with witness.py's enclosure
    syms, yes, no, tried = pair(Q.gt(x, pi), Q.ge(x, 3) & Q.le(x, Rational(63, 20)))
    assert type(yes[0]) is not W._PiPoly and type(no[0]) is not W._PiPoly
    assert PI_HI < yes[0] <= F(63, 20) and 3 <= no[0] < PI_LO
    # pi**2 between 9 and 10: x**2 < pi**2 at one point of 3 <= x <= 22/7 with x != pi, not at another
    syms, yes, no, tried = pair(Q.lt(x ** 2, pi ** 2), Q.ge(x, 3) & Q.le(x, Rational(22, 7)) & Q.ne(x, pi))
    assert type(yes[0]) is not W._PiPoly and type(no[0]) is not W._PiPoly
    assert 3 <= yes[0] < PI_LO and PI_HI < no[0] <= F(22, 7)
    # a term in pi with rational points: x + pi > 0 at 0, not at -4
    syms, yes, no, tried = pair(Q.positive(x + pi), Q.rational(x))
    assert type(yes[0]) is not W._PiPoly and type(no[0]) is not W._PiPoly
    assert yes[0] + PI_LO > 0 and no[0] + PI_HI <= 0


def test_a_symbol_stands_for_rational_values_only():
    # no value of Q[pi] outside Q is proposed for a symbol: x - pi/2 is zero at no rational x, so there is no pair
    assert pair(Q.zero(x - pi / 2), Q.real(x)) is None
    assert pair(Q.zero(xp - pi), Q.real(y)) is None
    assert pair(Q.irrational(x), Q.gt(x, pi - 1) & Q.lt(x, pi + 1)) is None
    syms, yes, no, tried = pair(Q.zero(x - pi / 2) | Q.zero(2 * x - 3), Q.real(x))
    assert yes == [F(3, 2)] and type(no[0]) is not W._PiPoly
    # a term of the query still has its value in Q[pi] at a rational point
    syms, yes, no, tried = pair(Q.positive(x - pi), Q.real(x))
    assert type(yes[0]) is not W._PiPoly and type(no[0]) is not W._PiPoly and no[0] < PI_LO and PI_HI < yes[0]
    assert pair(Q.irrational(x + pi), Q.real(x)) is None        # irrational at every rational x
    # without pi in the query, as before
    assert pair(Q.irrational(x), Q.real(x)) is None and pair(Q.transcendental(x), Q.gt(x, 3) & Q.lt(x, 4)) is None


def test_a_positive_value_of_q_pi_is_not_negative(on):
    # plant 755 (the sign of a positive value flipped): pi*x would be negative at x = 1, and y decides
    assert both(Q.positive(pi * x) | Q.positive(y), Q.positive(x)) == [True, True]
    assert both(Q.gt(pi * x, 3 * x), Q.positive(x)) == [True, True]


def test_a_value_with_pi_is_not_rational(on):
    # plant 756 (a _PiPoly called rational): x + pi would be rational at x = 0, and y decides
    assert both(Q.irrational(pi + x) | Q.positive(y), Q.rational(x)) == [True, True]
    assert both(Q.rational(x + pi), Q.rational(x)) == [False, False]


def test_pi_is_below_22_sevenths(on):
    # plant 757 (an interval that does not hold pi): between 22/7 and 63/20 x would be below pi
    a = Q.gt(x, Rational(22, 7)) & Q.lt(x, 4) & Q.ne(x, Rational(63, 20))
    assert both(Q.gt(x, pi), a) == [True, True]


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
    eng = A.Engine()
    eng.extensions = Extensions()
    fp, fa = A._formula(Q.positive(x), True), A._formula(Q.real(x), True, True)
    assert W.witnesses(fp, fa, eng) is not None
    eng.extensions._vocab['positive'] = [((Symbol,), lambda e: True)]
    assert W.witnesses(fp, fa, eng) is None


class _UsersSymbol(Symbol):
    """A class of the test's own, for a declaration that reaches no other test's terms."""


def _users_template(e):
    return P('positive', e)             # unsound on purpose: no symbol is positive for being a Symbol


@pytest.fixture
def users_knowledge():
    """Removes what the test below registers on the default ``extensions``, and a new epoch drops what the engines
    derived meanwhile. Its template and its declared module are taken off the default registry by
    ``clean_default_registry``, which keeps the built-in modules that ``register`` loaded."""
    yield
    E.extensions.unregister('positive')
    bump()


@pytest.mark.parametrize('how', ['template', 'lazy', 'templates-function', 'adapter', 'default-registry'])
def test_a_users_knowledge_falls_through_and_the_engines_answer_is_used(on, users_knowledge, how):
    """With knowledge a user registered in force, by any entry point, the check falls through, as it does for a
    function in the engine's ``extensions``. A user's template may be unsound: the engine then gives a definite
    answer where two points exist, and the answer with the switch on is the engine's, as with the switch off."""
    u = Symbol('u_users')
    p, a = Q.positive(u), Q.real(u) & Q.positive(y)
    fp, fa = A._formula(p, True), A._formula(a, True, True)
    assert W.witnesses(fp, fa, A.Engine()) is not None and A.ask(p, a, A.Engine()) is None  # certified before
    make, answer = A.Engine, None
    if how == 'template':
        registry.register(Symbol)(_users_template)
        answer = True
    elif how == 'lazy':
        # declared like a built-in module: its templates would register on the class's first use, with no new epoch
        registry.lazy(__name__, _UsersSymbol)
    elif how == 'templates-function':
        def make():
            return A.Engine(templates=lambda node: [_users_template(node)] if type(node) is Symbol else ())
        answer = True
    elif how == 'adapter':
        def make():                     # the package's adapter in all but its module
            lra = default_specs()[0]
            return A.Engine(relations=[AdapterSpec(lra.name, type('UsersAdapter', (lra.factory,), {}), lra.guarded)])
    else:
        def make():                     # the engine reads its own registry; the default one decides the scope
            eng = A.Engine()
            eng.extensions = Extensions()
            return eng
        E.register(Q.positive, _UsersSymbol)(lambda e: True)
    assert A.ask(p, a, make()) is answer
    assert W.witnesses(fp, fa, make()) is None
    W.ENABLED[0] = False
    assert A.ask(p, a, make()) is answer


def test_a_template_left_on_the_default_registry_makes_the_check_fall_through(on):
    """A user's template on the default registry, for a class no query here mentions, is knowledge in force for
    every engine of the process: the check falls through and the engine answers, with a session, as with the switch
    off. Once the template is off the registry the same query is certified again."""
    p, a = Q.positive(x), Q.real(x)
    fp, fa = A._formula(p, True), A._formula(a, True, True)

    def counts(eng):
        return eng.stats['queries'], eng.stats['witness_certified'], eng.stats['sessions']
    eng = A.Engine()
    assert W.witnesses(fp, fa, eng) is not None and A.ask(p, a, eng) is None and counts(eng) == (1, 1, 0)
    registry.register(_UsersSymbol)(lambda e: ())       # says nothing, and about no term of the query
    eng = A.Engine()
    assert W.witnesses(fp, fa, eng) is None
    assert A.ask(p, a, eng) is None and counts(eng) == (1, 0, 1)
    left = _take_users_templates()
    assert list(left[0]) == [_UsersSymbol] and left[1] == []
    eng = A.Engine()
    assert W.witnesses(fp, fa, eng) is not None and A.ask(p, a, eng) is None and counts(eng) == (1, 1, 0)
    _put_back_users_templates(*left)
    assert W.witnesses(fp, fa, A.Engine()) is None      # back as it was left; the fixture takes it off


@pytest.mark.parametrize('name', W.GUARDED)
@pytest.mark.parametrize('where', ['class', 'instance', 'subclass'])
def test_a_users_method_on_the_engine_is_called_and_its_answer_is_used(on, monkeypatch, name, where):
    """Formula ruling P1 as the check applies it: with ``ask``, ``verdict``, ``_context_session`` or
    ``_within_budget`` replaced by a user, on the class, on one engine or in a subclass, the check falls through:
    the user's method gets the calls it gets with the switch off, and the answer is the one it leads to."""
    p, a = Q.positive(x), Q.real(x) & Q.positive(y)     # relevance splits the set, so ``verdict`` is reached too
    assert pair(p, a) is not None and A.ask(p, a, A.Engine()) is None    # certified while nothing is replaced
    real = getattr(A.Engine, name)
    calls = []

    def users(self, *args, **kw):
        calls.append(name)
        if name == 'ask':
            return True                 # a user's answer, not the engine's None
        return real(self, *args, **kw)

    def run():
        del calls[:]
        if where == 'class':
            with monkeypatch.context() as m:
                m.setattr(A.Engine, name, users)
                return A.ask(p, a, A.Engine()), len(calls)
        if where == 'subclass':
            return A.ask(p, a, type('Mine', (A.Engine,), {name: users})()), len(calls)
        eng = A.Engine()
        setattr(eng, name, users.__get__(eng))
        return A.ask(p, a, eng), len(calls)

    W.ENABLED[0] = False
    off = run()
    W.ENABLED[0] = True
    assert run() == off and off[1] > 0
    assert off[0] is (True if name == 'ask' else None)
    assert A.ask(p, a, A.Engine()) is None and not W._patched(A.Engine())   # the engine's own again: certified


def _state(eng):
    return dict(eng.stats), eng.last_budget_limited


@pytest.mark.parametrize('budget', [0, 1, 2])
def test_a_query_over_the_budget_still_answers_none(budget):
    """sa-port-348: the check does not ask the discovery budget. Two points certify this query, so over the budget it
    is certified: None, the answer the engine gives it with the switch off, where it is counted as budget limited."""
    p, a = Q.positive(x + y), Q.real(x) & Q.real(y)
    assert pair(p, a) is not None
    old = W.ENABLED[0]
    try:
        got = []
        for sw in (False, True):
            W.ENABLED[0] = sw
            eng = A.Engine(discovery_budget=budget)
            got.append((A.ask(p, a, eng), _state(eng)))
        off, on_ = got
        assert on_[0] is None and off[0] is None
        assert off[1][0]['budget_limited'] == 1 and off[1][1] is True and off[1][0]['witness_certified'] == 0
        assert on_[1][0]['budget_limited'] == 0 and on_[1][1] is False and on_[1][0]['witness_certified'] == 1
    finally:
        W.ENABLED[0] = old


def test_a_set_the_engine_knows_inconsistent_tries_no_point(on, monkeypatch):
    """sa-port-346 (1): the set's memoized INCONSISTENT comes before any point. The first query under the set finds
    no point that satisfies it and the engine raises; a second query under it is left to the engine at once."""
    a = Q.positive(x) & Q.negative(x)
    points = []
    real = W._holds

    def holds(pt, *rest):
        points.append(list(pt))
        return real(pt, *rest)
    monkeypatch.setattr(W, '_holds', holds)
    eng = A.Engine()
    with pytest.raises(ValueError):
        A.ask(Q.zero(x), a, eng)
    first = len(points)
    assert first > 0
    with pytest.raises(ValueError):
        A.ask(Q.integer(x), a, eng)
    assert len(points) == first and eng.stats['witness_certified'] == 0
    with pytest.raises(ValueError):
        A.ask(Q.integer(x), a, A.Engine())      # an engine that has not seen the set: the points are tried
    assert len(points) > first


@pytest.fixture
def work():
    """Sets the work bound for the test."""
    old = W.WORK[0]

    def set_(n):
        W.WORK[0] = n
    yield set_
    W.WORK[0] = old


def _spent(monkeypatch, p, a, eng=None):
    """The check's result for the query, its compiled terms and the term evaluations it charged."""
    made = []
    base = W._Query

    class Seen(base):
        __slots__ = ()

        def __init__(self, pi=False):
            base.__init__(self, pi)
            made.append(self)
    with monkeypatch.context() as m:
        m.setattr(W, '_Query', Seen)
        r = W.witnesses(A._formula(p, True), A._formula(a, True, True), eng)
    return r, made[-1].size, made[-1].work


def test_the_work_is_the_terms_evaluated(monkeypatch, work):
    """sa-port-346 (2): what a query is charged. ``x + y`` is three terms and each assumption one, so a point costs
    5; the one compound atom is evaluated for its roots 3 times for each symbol with the other at 0 and at 1, 12
    evaluations of 3 terms."""
    work(0)
    r, size, spent = _spent(monkeypatch, Q.positive(x + y), Q.real(x) & Q.real(y))
    assert r is not None and size == 5 and spent == 36 + 5 * r[3]
    r, size, spent = _spent(monkeypatch, Q.positive(x), Q.real(x))      # no compound atom: no root is looked for
    assert r is not None and size == 2 and spent == 2 * r[3]


def test_past_the_work_bound_the_check_falls_through_and_the_engine_answers(on, monkeypatch, work):
    """sa-port-346 (2): the bound is on the term evaluations, not on the points. At the work a pair takes the query
    is certified; one evaluation less and the check falls through, during the points or during the roots, and the
    query is the engine's with the answer it has with the switch off."""
    p, a = Q.positive(x + y), Q.real(x) & Q.real(y)
    work(0)
    r, size, need = _spent(monkeypatch, p, a)
    assert r is not None and need > 36
    for bound, found in ((need, True), (need - 1, False), (36, False), (35, False), (1, False)):
        work(bound)
        got, _size, spent = _spent(monkeypatch, p, a)
        assert (got is not None) == found
        assert found or spent > bound >= spent - size     # stopped by the charge that passed the bound
        eng = A.Engine()
        assert A.ask(p, a, eng) is None
        assert (eng.stats['witness_certified'], eng.stats['sessions'] > 0) == ((1, False) if found else (0, True))
    W.ENABLED[0] = False
    assert A.ask(p, a, A.Engine()) is None


def test_the_default_work_bound_leaves_a_long_sum_to_the_engine(on, monkeypatch, work):
    """sa-port-346 (2): the default, 2500 term evaluations. The roots of a sum of 40 symbols alone cost more (40
    symbols, 6 evaluations each, 41 terms), so the check stops there; a small query never comes near the bound."""
    assert W.WORK[0] == int(os.environ.get('SLICE_WITNESS_WORK', '2500'))
    work(2500)
    xs = symbols('w0:40')
    p, a = Q.positive(sum(xs)), Q.real(xs[0])
    got, size, spent = _spent(monkeypatch, p, a)
    assert got is None and size == 42 and 2500 < spent <= 2500 + 41
    work(0)
    got, size, spent = _spent(monkeypatch, p, a)
    assert got is not None and spent == 40 * 6 * 41 + 42 * got[3]
    work(2500)
    assert _spent(monkeypatch, Q.positive(x + y), Q.real(x) & Q.real(y))[0] is not None
    both_ = both(p, a)
    assert both_[0] is both_[1] is None


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


def test_on_skips_the_session_and_counts_the_query(on):
    """A certified query is a query like any other in ``stats['queries']`` and counted by itself in
    ``stats['witness_certified']``; it builds no session. The same query with the switch off builds one."""
    def counts(eng):
        return eng.stats['queries'], eng.stats['witness_certified'], eng.stats['sessions']
    eng = A.Engine()
    assert A.ask(Q.positive(x), Q.real(x), eng) is None
    assert counts(eng) == (1, 1, 0)         # certified before Engine.ask
    assert A.ask(Q.real(x), Q.positive(x), eng) is True
    assert counts(eng) == (2, 1, 1)
    W.ENABLED[0] = False
    off = A.Engine()
    assert A.ask(Q.positive(x), Q.real(x), off) is None
    assert counts(off) == (1, 0, 1)



def test_the_cap_bounds_the_points_tried():
    old = W.CAP[0]
    try:
        W.CAP[0] = 1
        assert pair(Q.positive(x), Q.real(x)) is None
        W.CAP[0] = 2
        assert pair(Q.positive(x), Q.real(x))[3] == 2
    finally:
        W.CAP[0] = old


# ---- every raise of the check is caught before the query returns (sa-port-342, planner on [151]) ----

def _raises():
    """The line of every ``raise`` statement of satassume/witness.py and what it raises, and the module's exception
    classes, read from the source."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(W))
    lines = {n.lineno: ast.unparse(n.exc) if n.exc is not None else None
             for n in ast.walk(tree) if isinstance(n, ast.Raise)}
    classes = [getattr(W, n.name) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return lines, [c for c in classes if issubclass(c, BaseException)]


def test_the_check_raises_only_its_own_undecided():
    # one except clause, ``except _Undecided``, covers every raise: the module has two exception classes, the second
    # a subclass of the first, and no raise statement names anything else or re-raises
    lines, classes = _raises()
    assert sorted(classes, key=lambda c: c.__name__) == [W._NeedPi, W._Undecided]
    assert issubclass(W._NeedPi, W._Undecided) and W._Undecided.__bases__ == (Exception,)
    assert lines and set(lines.values()) == {'_Undecided', '_NeedPi'}


class _OtherNode(Formula):
    """A formula node the check does not know."""


def _escapes():
    """One case per raise statement of the check, each a call of the check's entry: ``(proposition, assumptions)``
    for ``ask``, or ``(formula, formula, None)`` for ``witness.witnesses`` where no query gives the formula."""
    xq = Symbol('xq', polar=True)
    big = 10 ** 100
    inside = W._LO[1] + F(1, 2 * 10 ** 50)      # between the two bounds of pi: the sign of pi - inside is not decided
    inside = Rational(inside.numerator, inside.denominator)
    return [
        (Q.prime(x), Q.gt(x, 10 ** 7)),                         # _is_prime above its bound
        (Q.gt(Symbol('p', prime=True), 10 ** 7), Q.integer(Symbol('p', prime=True))),   # [151]: the same in _pools
        (Q.positive(pi ** 9 * (x + pi) ** 8), Q.real(x)),       # a product of degree 17 in pi
        (Q.positive(x + pi ** 18), Q.real(x)),                  # a power of degree 18 in pi
        (Q.gt(x + pi, inside), Q.real(x)),                      # a sign the enclosure does not give
        (Q.positive(xq), Q.real(xq)),                           # polar, an own assumption without a table entry
        (Q.antihermitian(x), Q.real(x)),                        # the one-way predicate without a value
        (P('symmetric', x), True, None),                        # a predicate outside the vocabulary
        (Q.positive(x / pi), Q.real(x)),                        # 1/pi
        (Q.gt(2 ** x, 1), Q.gt(x, 0) & Q.lt(x, 1)),             # a root: 2**(1/2)
        (Q.positive(x ** y), Q.real(x) & Q.real(y)),            # 0**0
        (Q.positive(x ** 13 - 1), Q.gt(x, big)),                # a power too long
        (Q.positive(sin(x)), Q.real(x)),                        # a function
        (Q.positive(x ** pi), Q.real(x)),                       # pi as an exponent
        (Q.positive((x + pi) ** -1), Q.real(x)),                # a negative power of a value with pi
        (Q.positive(pi + 1 / x), Q.real(x)),                    # 1/0 in a query that holds pi
        (Q.positive(pi + x ** 13), Q.gt(x, big)),               # a power too long in a query that holds pi
        (P('eq', x), True, None),                               # a relation without its two sides
        (P('positive', Args((x, y))), True, None),              # a unary predicate of two terms
        (_OtherNode(P('positive', x)), True, None),             # a formula node the check does not know
    ]


def test_every_raise_of_the_check_is_caught_before_the_query_returns():
    """[151] was an _Undecided that left the check and the query. Here every raise statement of witness.py is
    executed (a line trace of the module says which) under a call of the check's entry, and nothing leaves it:
    ``witnesses`` returns, and ``ask`` gives the answer it gives with the switch off. Three raises no query reaches
    (below) are executed directly; a raise added to the module without a case here fails the last assertion."""
    lines, _ = _raises()
    seen = set()
    fn = W.__file__

    def trace(frame, event, arg):
        if frame.f_code.co_filename != fn:
            return None

        def line(frame, event, arg):
            if event == 'line':
                seen.add(frame.f_lineno)
            return line
        return line

    old = sys.gettrace()
    sys.settrace(trace)
    try:
        for case in _escapes():
            if len(case) == 3:
                assert W.witnesses(case[0], case[1]) is None
            else:
                pair(*case)         # certified or not: it returns
                off, on_ = both(*case)
                assert off == on_, case
        # the check divides a value only by a non-zero rational (the secant's slope in _roots, 2 in _pools), so no
        # query reaches the two divisions that leave Q[pi]; and no definition of a derived predicate names polar,
        # the only basis predicate without a table entry
        with pytest.raises(W._Undecided):
            W._PI / W._PI
        with pytest.raises(W._Undecided):
            1 / W._PI
        with pytest.raises(W._Undecided):
            W._pred('real', dict(W.TABLE, finite=None))
    finally:
        sys.settrace(old)
    assert sorted(set(lines) - seen) == []


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
    # with pi (sa-port-341)
    (Q.positive(x + pi), Q.real(x)), (Q.gt(x, pi), Q.gt(x, 3) & Q.lt(x, Rational(63, 20))), (Q.rational(x + pi), Q.real(x)),
    (Q.rational(x + pi), Q.rational(x)), (Q.zero(x - pi / 2), Q.real(x)), (Q.positive(x ** 2 - pi), Q.real(x)),
    (Q.positive(x / pi), Q.real(x)), (Q.positive(pi ** 2 - 9), Q.real(x)), (Q.integer(x * pi), Q.rational(x)),
    (Q.lt(x, pi), Q.gt(x, Rational(22, 7)) & Q.lt(x, Rational(63, 20))), (Q.positive(pi * x), Q.positive(x)),
    (Q.gt(pi * x, 3 * x), Q.positive(x)), (Q.eq(x * pi, y * pi), Q.real(x) & Q.real(y)),
    (Q.irrational(x), Q.gt(x, pi - 1) & Q.lt(x, pi + 1)), (Q.transcendental(x * pi + 1), Q.rational(x) & Q.nonzero(x)),
    (Q.transcendental(x * pi + 1), Q.rational(x)), (Q.algebraic(xi * pi), Q.real(y)), (Q.positive(pi - xp), Q.real(y)),
    (Q.even(x + pi), Q.real(x)), (Q.irrational(x * pi), Q.rational(x)), (Q.lt(x * pi, y), Q.lt(x, y) & Q.positive(x)),
]


@pytest.mark.parametrize('i', range(len(QUERIES)))
def test_answers_are_equal_on_and_off(i):
    off, on_ = both(*QUERIES[i])
    assert off == on_
