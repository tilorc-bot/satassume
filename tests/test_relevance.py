"""Relevance: a query is answered under the assumption conjuncts connected to
it (``sympy_api._relevant``), once the whole set is known consistent."""
import pytest
from sympy import (E, Function, GoldenRatio, I, Integer, MatrixSymbol, Q, Rational, Symbol,
                   TribonacciConstant, besselj, false, oo, pi, sin, sqrt, symbols, zoo)
from sympy.assumptions.assume import Predicate

from satassume import sympy_api as api
from satassume.engine import Engine
from satassume.extensions import Extensions

x, y, z, t = symbols("x y z t")
xr, yr, zr = symbols("xr yr zr", real=True)
polar = Predicate("polar")      # in the vocabulary, not in this SymPy's Q
f = Function("f")


def both(p, a):
    """Answers (or "error") with and without relevance, fresh engines."""
    out = []
    for rel in (True, False):
        eng = Engine(relevance=rel)
        try:
            out.append(api.ask(p, a, engine=eng))
        except ValueError:
            out.append("error")
    return out


@pytest.fixture
def rationals():
    """``RELATIONAL = "rationals"``: sets with relations split too."""
    old = api.RELATIONAL
    api.RELATIONAL = "rationals"
    api._KEYS.clear()
    yield
    api.RELATIONAL = old
    api._KEYS.clear()


@pytest.fixture
def whole():
    """``RELATIONAL = "whole"`` (an ablation): sets and queries with a
    relation are not split."""
    old = api.RELATIONAL
    api.RELATIONAL = "whole"
    api._KEYS.clear()
    yield
    api.RELATIONAL = old
    api._KEYS.clear()


def used(p, a):
    """The assumptions the query is answered under (a fresh engine)."""
    return api._relevant(p, a, Engine())


# -- splitting ----------------------------------------------------------------

def test_unrelated_component_is_dropped():
    a = Q.positive(x) & Q.negative(y) & Q.integer(z)
    assert used(Q.positive(x), a) == Q.positive(x)
    assert used(Q.real(x + z), a) == Q.positive(x) & Q.integer(z)
    assert used(Q.positive(t), a) is True
    eng = Engine()
    assert api.ask(Q.positive(x), a, engine=eng) is True
    assert api.ask(Q.positive(y), a, engine=eng) is False
    assert api.ask(Q.positive(t), a, engine=eng) is None
    assert eng.stats["relevant"] == 3


def test_parts_share_the_answer_memo_and_session():
    eng = Engine()
    assert api.ask(Q.nonnegative(x), Q.positive(x) & Q.negative(y), engine=eng) is True
    q = eng.stats["queries"]
    # another set with the same part: answered from the memo
    assert api.ask(Q.nonnegative(x), Q.positive(x) & Q.odd(z), engine=eng) is True
    assert eng.stats["queries"] == q


def test_relation_splits_by_component():
    # RELATIONAL "components" (the default): a set or query with a relation
    # splits by key connectivity like a relation-free one (#53 R2)
    a = Q.positive(x) & Q.lt(x, y) & Q.real(y) & Q.negative(z)
    assert used(Q.positive(y), a) == Q.positive(x) & Q.lt(x, y) & Q.real(y)
    assert used(Q.positive(z), a) == Q.negative(z)
    assert both(Q.positive(y), a) == [True, True]
    a = Q.positive(x) & Q.negative(z)
    assert used(Q.lt(0, x), a) == Q.positive(x)
    assert both(Q.lt(0, x), a) == [True, True]


def test_common_value_does_not_connect():
    # D3: a Rational side of an equality is no key, so x = 2 and y = 2 are
    # two components and the value is not merged across them (True under
    # RELATIONAL "whole"); within one component it still is.  (With an
    # undefined f instead of sin, the class of f is a key and connects f(x)
    # with f(y): one component, True.)
    a = Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y))
    assert used(Q.positive(sin(x)), a) == Q.eq(x, 2)
    assert api.ask(Q.positive(sin(x)), a, engine=Engine()) is None
    b = Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(f(y))
    assert used(Q.positive(f(x)), b) is b
    assert api.ask(Q.positive(f(x)), b, engine=Engine()) is True
    b = Q.eq(x, 2) & Q.positive(sin(x))
    assert used(Q.positive(sin(x)), b) is b
    assert api.ask(Q.positive(sin(x)), b, engine=Engine()) is True
    assert api.ask(Q.positive(f(x)), Q.eq(x, 2) & Q.positive(f(x)), engine=Engine()) is True


def test_common_value_connects_whole(whole):
    a = Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y))
    assert api.ask(Q.positive(sin(x)), a, engine=Engine()) is True


def test_inconsistent_relational_set_raises_for_any_component():
    # raising is decided by the whole set's verdict, not by the part
    a = Q.gt(x, 1) & Q.lt(x, 0) & Q.positive(y)
    assert used(Q.positive(y), a) is a
    for p in (Q.positive(y), Q.lt(0, y), Q.positive(t)):
        with pytest.raises(ValueError):
            api.ask(p, a, engine=Engine())
    # also a keyless conjunct, which joins no component
    a = Q.lt(2, 1) & Q.positive(y) & Q.gt(x, 1)
    with pytest.raises(ValueError):
        api.ask(Q.positive(y), a, engine=Engine())


def test_sign_sums_set_raises_for_any_component():
    # sign atoms on sums sharing a symbol start the relation glue (#51) in
    # the whole set's session, which links x and y (both zero) across
    # components: the whole set is inconsistent while each component is
    # consistent on its own, so the whole set's verdict decides raising
    bj = lambda e: besselj(1, e)
    a = (Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.nonzero(bj(x))
         & Q.positive(z - 1) & Q.negative(z - 3))
    for p in (Q.gt(z, 0), Q.lt(0, z), Q.positive(z), Q.zero(bj(x))):
        assert both(p, a) == ["error", "error"], p


SPLIT_SWEEP = [
    Q.positive(x) & Q.lt(x, y) & Q.negative(z) & Q.eq(t, 3),
    Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y)) & Q.lt(1, 2),
    Q.integer(x) & Q.gt(x, Rational(1, 2)) & Q.lt(y, pi) & Q.ne(z, 1.5),
    Q.eq(f(x), 1) & Q.gt(y, 0) & Q.positive(f(z)) & Q.lt(z, E),
    Q.le(xr, yr) & Q.ge(xr, yr) & Q.positive(f(yr)) & Q.eq(z, t),
]
SWEEP_QUERIES = [Q.positive(x), Q.positive(y), Q.negative(z), Q.lt(x, 1), Q.gt(y, -1),
                 Q.positive(f(x)), Q.positive(f(xr)), Q.eq(z, t), Q.integer(t), Q.real(x + y)]


@pytest.mark.parametrize("a", SPLIT_SWEEP, ids=str)
def test_split_relational_answer_is_the_part_answer(a):
    # in one engine, in order: each answer equals the answer under the part
    # it is asked under, as a whole set in a fresh engine
    eng = Engine()
    for p in SWEEP_QUERIES:
        f = used(p, a)
        try:
            r = api.ask(p, a, engine=eng)
        except ValueError:
            r = "error"
        try:
            g = api.ask(p, f, engine=Engine(relevance=False))
        except ValueError:
            g = "error"
        assert r == g, (p, f)


def test_relation_is_not_split(whole):
    a = Q.positive(x) & Q.lt(x, y) & Q.real(y) & Q.negative(z)
    assert used(Q.positive(y), a) is a
    assert used(Q.positive(z), a) is a
    # nor under a relational query
    a = Q.positive(x) & Q.negative(z)
    assert used(Q.lt(0, x), a) is a
    assert both(Q.lt(0, x), a) == [True, True]


def test_relation_connects(rationals):
    a = Q.positive(x) & Q.lt(x, y) & Q.real(y) & Q.negative(z)
    assert used(Q.positive(y), a) == Q.positive(x) & Q.lt(x, y) & Q.real(y)
    assert both(Q.positive(y), a) == [True, True]
    a = Q.positive(x) & Q.eq(x, y) & Q.negative(z)
    assert used(Q.positive(y), a) == Q.positive(x) & Q.eq(x, y)
    assert both(Q.positive(y), a) == [True, True]


def test_undefined_function_connects(rationals):
    a = Q.positive(f(x)) & Q.eq(y, z) & Q.negative(t)
    assert used(Q.positive(f(y)), a) == Q.positive(f(x)) & Q.eq(y, z)
    a = Q.positive(f(x)) & Q.eq(x, y) & Q.negative(t)
    assert both(Q.positive(f(y)), a) == [True, True]


def test_irrational_constant_connects(rationals):
    # pi is a bounded LRA variable: facts about it may flow between components
    a = Q.lt(xr, pi) & Q.gt(yr, pi) & Q.positive(z)
    assert used(Q.lt(xr, yr), a) == Q.lt(xr, pi) & Q.gt(yr, pi)
    assert used(Q.positive(xr), a) == Q.lt(xr, pi) & Q.gt(yr, pi)
    assert used(Q.positive(z), a) == Q.positive(z)
    assert both(Q.lt(xr, yr), a) == [True, True]


def test_decided_irrational_constant_is_no_key():
    a = Q.positive(x * sqrt(2)) & Q.positive(y)
    # sqrt(2) inside x*sqrt(2) is no key: every fact of it is decided
    # context-free, so it carries nothing between components (W2A2)
    assert used(Q.positive(sqrt(2)), a) is True
    assert both(Q.positive(sqrt(2)), a) == [True, True]


# Terms pinned to the same value are merged in EUF, and congruence carries
# facts between sin(x) and sin(y) (or sin(2)); definite without relevance
# (irrational-tune), None when the set was split by symbols only.
PINNED = [
    (Q.positive(sin(x)), Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(sin(y)), True),
    (Q.positive(besselj(1, x)), Q.eq(x, 2) & Q.eq(y, 2) & Q.positive(besselj(1, y)), True),
    (Q.positive(besselj(1, x)), Q.zero(x) & Q.eq(y, 0) & Q.positive(besselj(1, y)), True),
    (Q.positive(sin(x)), Q.eq(x, 2) & Q.positive(sin(2)), True),
    (polar(x), ~polar(2) & Q.eq(x, 2), False),
]
# ... and values LRA or the rule base derive, which no Rational key finds
DERIVED = [
    (Q.positive(sin(x)), Q.eq(x + 1, 3) & Q.eq(y, 2) & Q.positive(sin(y)), True),
    (Q.positive(sin(xr)), Q.le(xr, 2) & Q.ge(xr, 2) & Q.le(yr, 2) & Q.ge(yr, 2)
     & Q.positive(sin(yr)), True),
    (Q.positive(sin(xr)), Q.eq(xr, yr + 2) & Q.eq(yr, 0) & Q.eq(zr, 2)
     & Q.positive(sin(zr)), True),
    (Q.positive(besselj(1, x)), Q.nonnegative(x) & Q.nonpositive(x) & Q.eq(y, 0)
     & Q.positive(besselj(1, y)), True),
]


@pytest.mark.parametrize("p, a, r", PINNED + DERIVED)
def test_pinned_values_connect(whole, p, a, r):
    assert used(p, a) is a
    assert both(p, a) == [r, r]


@pytest.mark.parametrize("p, a, r", PINNED + DERIVED)
def test_pinned_values_split(p, a, r):
    # "components" (D3): a common value does not connect, the query is
    # answered under its own component, as that component alone is
    f = used(p, a)
    assert f is not a
    assert both(p, a) == [None, r]
    assert api.ask(p, f, engine=Engine()) is None


@pytest.mark.parametrize("p, a, r", PINNED)
def test_rational_keys_connect(rationals, p, a, r):
    assert both(p, a) == [r, r]


def test_rational_argument_is_a_key():
    # polar(2) is open for the engine: the Rational is a node of its own
    a = (polar(2) | Q.positive(x)) & (~polar(2) | Q.positive(y)) & ~Q.positive(x)
    assert used(Q.positive(y), a) is a
    assert both(Q.positive(y), a) == [True, True]


# -- no split -----------------------------------------------------------------

def test_custom_predicate_is_not_split():
    from sympy.assumptions.assume import Predicate

    class MyPred(Predicate):
        name = "mypred_rel"
    mp = MyPred()
    a = mp(x) & Q.positive(y)
    # unregistered: an opaque atom keyed by its argument, split off
    assert used(Q.positive(y), a) == Q.positive(y)
    api.register("mypred_rel", Symbol)(lambda s: None)
    try:
        # registered: its function may mention any term, never split (the
        # key memo follows the registration)
        assert used(Q.positive(y), a) is a
    finally:
        api.unregister("mypred_rel")
    assert used(Q.positive(y), a) == Q.positive(y)


def test_vocabulary_extension_is_not_split():
    """A vocabulary registration on a class disables the split only of a
    set or query with an instance of it (W2A1)."""
    ext = Extensions()

    class Thing(Symbol):
        pass
    th = Thing("th")
    ext.register("positive", Thing)(lambda n: None)
    eng = Engine(extensions=ext)
    a = Q.positive(x) & Q.negative(y)
    assert api._relevant(Q.positive(x), a, eng) == Q.positive(x)
    b = Q.positive(x) & Q.negative(y + th)
    assert api._relevant(Q.positive(x), b, eng) is b
    assert api._relevant(Q.positive(x + th), a, eng) is a


def test_vocabulary_extension_on_derived_class_is_not_split():
    """A class templates derive nodes of (``b - 1``: Add) may meet any set."""
    from sympy import Add
    ext = Extensions()
    ext.register("positive", Add)(lambda n: None)
    eng = Engine(extensions=ext)
    a = Q.positive(x) & Q.negative(y)
    assert api._relevant(Q.positive(x), a, eng) is a


def keys(e):
    return set(api._keys(e))


def test_closed_term_keys():
    from sympy import E, Float, cos, oo
    # pi, sqrt(2), 2*pi, oo: every fact decided context-free, no key
    assert keys(Q.positive(y + pi)) == {y}
    assert keys(Q.positive(y + sqrt(2) + 2*pi)) == {y}
    assert keys(Q.real(pi*y)) == {y}
    assert keys(Q.positive(y + oo)) == {y}
    # f(1): a free EUF term
    assert keys(Q.positive(f(1) + y)) >= {y, f, f(1)}
    # a Float: its rationality is open
    assert Float(1.5) in keys(Q.positive(y + Float(1.5)))
    # pi + E (rationality open), pi - 3 and cos(1) (sign not decided)
    assert keys(Q.positive(y*(pi + E))) == {y, pi + E, pi, E}
    assert pi - 3 in keys(Q.positive(y*(pi - 3)))
    assert cos(1) in keys(Q.positive(y + cos(1)))
    # a closed predicate argument and anything inside polar stay keys
    assert keys(Q.negative(pi)) == {pi}
    assert keys(polar(y*pi)) == {y, pi}


@pytest.mark.parametrize("c", [
    pi, sqrt(2), 2*pi, -pi, pi/2, 1/pi, pi**2, sqrt(pi), 3*sqrt(2),
    2**Rational(1, 3), sqrt(2)*Rational(1, 3), Integer(2)**Rational(-1, 2),
    E, GoldenRatio, TribonacciConstant, I, -I, 2*I, oo, -oo, zoo,
])
def test_unkeyed_constants_are_decided(c):
    """Soundness of dropping a closed term's key (see "Closed terms" in
    sympy_api): the engine's context-free clauses of every form of ``K``
    fix every predicate of its block except ``polar``."""
    from satassume.engine import Session
    from satassume.rules import PREDICATES, PRED_INDEX
    assert api._const_free(c)
    s = Session(Engine())
    s.ensure(c)
    s.escalate(10**6)
    assert s.solver.propagate()
    b = s.base[c]
    open_ = [p for p in PREDICATES
             if p != "polar" and s.solver.value(b + PRED_INDEX[p]) is None]
    assert not open_


def test_unrelated_sums_through_pi_are_split():
    """W2A2: pi no longer connects unrelated components."""
    n = Symbol("n", integer=True)
    u, v = symbols("u v")
    a = Q.integer(n) & Q.negative(n - 1) & Q.real(pi*n)
    b = Q.nonzero(u + v) & Q.positive(u + pi)
    assert used(Q.negative(-n), a & b) == a


def test_query_without_keys_is_not_split():
    a = Q.positive(x) & Q.negative(y)
    assert used(false, a) is a
    # Q.is_true over a non-relational is keyed by its argument (an opaque
    # atom in the assumptions); as a proposition it stays out of scope
    assert used(Q.is_true(x), a) == Q.positive(x)
    assert both(Q.is_true(x), a) == [None, None]


# -- errors and out of scope stay as before -----------------------------------

@pytest.mark.parametrize("a", [
    Q.positive(x) & Q.positive(y) & Q.negative(y),                   # no relation
    Q.positive(x) & Q.lt(yr, 0) & Q.gt(yr, 1),                       # relations
    Q.positive(x) & Q.lt(zr, yr) & Q.lt(yr, zr),
    Q.positive(x) & Q.lt(1, 0),                                      # no key
    Q.positive(x) & Q.negative(pi),
])
def test_inconsistent_unrelated_component_still_raises(a):
    for rel in (True, False):
        eng = Engine(relevance=rel)
        with pytest.raises(ValueError):
            api.ask(Q.positive(x), a, engine=eng)
        with pytest.raises(ValueError):       # and again (memoized check)
            api.ask(Q.nonnegative(x), a, engine=eng)
        with pytest.raises(ValueError):       # an empty part
            api.ask(Q.positive(t), a, engine=eng)


def test_inconsistent_only_by_search_still_raises():
    # no relation; propagation does not see the conflict, search does
    p, i = Q.positive(y), Q.integer(y)
    xor = (p | i) & (p | ~i) & (~p | i) & (~p | ~i)
    assert both(Q.positive(x), xor & Q.real(x)) == ["error", "error"]
    assert both(Q.positive(t), xor) == ["error", "error"]

def test_out_of_scope_rest_is_opaque():
    # a matrix predicate (or a vocabulary predicate of a matrix) in the
    # assumptions is an opaque atom: it no longer sinks the rest (W2A3)
    Y = MatrixSymbol("Y", 2, 2)
    a = Q.positive(x) & Q.invertible(Y)
    assert both(Q.positive(x), a) == [True, True]
    assert both(Q.invertible(Y), a) == [None, None]
    a = Q.positive(x) & Q.zero(Y)
    assert both(Q.positive(x), a) == [True, True]
    a = Q.positive(x) & Q.invertible(Y) & ~Q.invertible(Y)
    assert both(Q.positive(x), a) == ["error", "error"]


def test_uninterpreted_rest_is_free():
    # a Float in a relation is not read by any theory: a free atom by
    # default (the set splits, the Float side keys y's component), None
    # with uninterpreted="none" (the whole set cannot be checked, so it
    # answers as a whole)
    a = Q.positive(x) & Q.gt(y, 0.5)
    assert both(Q.positive(x), a) == [True, True]
    assert both(Q.positive(t), a) == [None, None]
    assert api.ask(Q.positive(x), a, engine=Engine(uninterpreted="none")) is None


def test_relevance_off():
    eng = Engine(relevance=False)
    assert api.ask(Q.positive(x), Q.positive(x) & Q.negative(y), engine=eng) is True
    assert eng.stats["relevant"] == 0
