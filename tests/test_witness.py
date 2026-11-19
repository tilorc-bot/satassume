"""The exact witness check before a contextual query's session (satassume/witness.py, issue 323; SLICE_WITNESS=1,
off by default). The tests of behaviour turn the switch on themselves and never read the plant flag."""
import os
from fractions import Fraction as F

import pytest
from sympy import Dummy, Float, I, Q, Rational, Symbol, oo, pi, sin, sqrt, symbols

from satassume import sympy_api as A
from satassume import witness as W
from satassume.knowledge import extensions as E
from satassume.knowledge.extensions import Extensions
from satassume.knowledge.rules import BASIS, DEFINITIONS
from satassume.knowledge.templates import _common as TC
from satassume.knowledge.templates import registry
from satassume.relations import AdapterSpec, default_specs
from satassume.sat.formula import P
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


def test_an_own_assumption_undecided_at_a_value_leaves_the_value_out(on):
    # 10**7 is above the bound of the trial division, so prime is undecided there: the value is not proposed, and
    # nothing is raised (before sa-port-341 _Undecided left _pools and the query)
    p = Symbol('p', prime=True)
    assert pair(Q.gt(p, 10 ** 7), Q.integer(p)) is None
    assert both(Q.gt(p, 10 ** 7), Q.integer(p)) == [None, None]
    syms, yes, no, tried = pair(Q.gt(p, 3), Q.lt(p, 10 ** 7))
    assert yes[0] in (5, 7) and no[0] in (2, 3)


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
