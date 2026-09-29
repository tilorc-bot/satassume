"""Relevance: a query is answered under the assumption conjuncts connected to
it (``sympy_api._relevant``), once the whole set is known consistent."""
import pytest
from sympy import Function, MatrixSymbol, Q, Symbol, besselj, pi, sin, sqrt, symbols
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


def test_relation_is_not_split():
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


def test_irrational_constant_is_a_key():
    a = Q.positive(x * sqrt(2)) & Q.positive(y)
    # sqrt(2) is a key (ask itself answers this constant proposition
    # without the assumptions)
    assert used(Q.positive(sqrt(2)), a) == Q.positive(x * sqrt(2))


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
def test_pinned_values_connect(p, a, r):
    assert used(p, a) is a
    assert both(p, a) == [r, r]


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
    ext = Extensions()
    from sympy.assumptions.assume import Predicate

    class MyPred(Predicate):
        name = "mypred_rel"
    mp = MyPred()
    ext.register("mypred_rel", Symbol)(lambda s: None)
    eng = Engine(extensions=ext)
    a = mp(x) & Q.positive(y)
    assert api._relevant(Q.positive(y), a, eng) is a


def test_vocabulary_extension_is_not_split():
    ext = Extensions()

    class Thing(Symbol):
        pass
    ext.register("positive", Thing)(lambda n: None)
    eng = Engine(extensions=ext)
    a = Q.positive(x) & Q.negative(y)
    assert api._relevant(Q.positive(x), a, eng) is a


def test_query_without_keys_is_not_split():
    a = Q.positive(x) & Q.negative(y)
    # Q.is_true over a non-relational is out of scope: opaque
    assert used(Q.is_true(x), a) is a


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

def test_out_of_scope_rest_keeps_none():
    Y = MatrixSymbol("Y", 2, 2)
    a = Q.positive(x) & Q.invertible(Y)
    assert both(Q.positive(x), a) == [None, None]
    a = Q.positive(x) & Q.zero(Y)
    assert both(Q.positive(x), a) == [None, None]


def test_uninterpreted_rest_keeps_none():
    # a Float in a relation is not read by any theory
    a = Q.positive(x) & Q.gt(y, 0.5)
    assert both(Q.positive(x), a) == [None, None]
    assert both(Q.positive(t), a) == [None, None]


def test_relevance_off():
    eng = Engine(relevance=False)
    assert api.ask(Q.positive(x), Q.positive(x) & Q.negative(y), engine=eng) is True
    assert eng.stats["relevant"] == 0
