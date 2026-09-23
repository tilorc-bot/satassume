import pytest

sympy = pytest.importorskip("sympy")
from sympy import (Symbol, Q, exp, sqrt, I, pi, Integer, Rational, oo, Abs,
                   Eq, Predicate, MatrixSymbol)

from satassume import Engine, DictCache
from satassume.sympy_api import ask, out_of_scope, to_formula, Unsupported


@pytest.fixture
def eng():
    return Engine(cache=DictCache())


# -- in scope: context-free ---------------------------------------------------

def test_symbol_bridge(eng):
    x = Symbol('x', positive=True)
    assert ask(Q.real(x), True, eng) is True
    assert ask(Q.negative(x), True, eng) is False
    assert ask(Q.real(Symbol('y')), True, eng) is None


def test_numbers(eng):
    assert ask(Q.prime(Integer(3)), True, eng) is True
    assert ask(Q.integer(Rational(1, 2)), True, eng) is False
    assert ask(Q.transcendental(pi), True, eng) is True
    assert ask(Q.real(I), True, eng) is False
    assert ask(Q.finite(oo), True, eng) is False
    assert ask(Q.extended_positive(oo), True, eng) is True


def test_structural_context_free(eng):
    p, q = Symbol('p', positive=True), Symbol('q', positive=True)
    u = Symbol('u', real=True)
    assert ask(Q.positive(p + 1), True, eng) is True
    assert ask(Q.positive(p * q), True, eng) is True
    assert ask(Q.zero(u**2 + 1), True, eng) is False
    assert ask(Q.positive(u**2 + 1), True, eng) is True
    assert ask(Q.negative(-p), True, eng) is True
    assert ask(Q.positive(sqrt(p)), True, eng) is True
    assert ask(Q.positive(exp(u)), True, eng) is True
    assert ask(Q.nonnegative(Abs(u)), True, eng) is True


def test_context_free_is_cached_on_engine(eng):
    p = Symbol('p', positive=True)
    assert ask(Q.positive(p + 1), engine=eng) is True
    n = eng.stats['queries']
    assert ask(Q.positive(p + 1), engine=eng) is True
    assert eng.stats['queries'] == n
    assert eng.stats['cache_hits'] >= 1


# -- in scope: contextual ------------------------------------------------------

def test_contextual(eng):
    y, w = Symbol('y'), Symbol('w')
    assert ask(Q.positive(y + 1), Q.positive(y), eng) is True
    assert ask(Q.zero(y * w), Q.zero(y) & Q.finite(w), eng) is True
    assert ask(Q.real(y * w), Q.real(y) & Q.real(w), eng) is True
    assert ask(Q.even(y + 1), Q.odd(y), eng) is True
    assert ask(Q.odd(y + 1), Q.odd(y), eng) is False
    assert ask(Q.positive(exp(y)), Q.real(y), eng) is True
    assert ask(Q.integer(y), Q.even(y) | Q.odd(y), eng) is True
    assert ask(Q.real(y), Q.negative(y) | Q.positive(y), eng) is True
    assert ask(Q.positive(y), Q.real(y), eng) is None
    with pytest.raises(ValueError):
        ask(Q.real(y), Q.even(y) & Q.odd(y), eng)


def test_compound_proposition(eng):
    y, w = Symbol('y'), Symbol('w')
    assert ask(Q.positive(y) | Q.negative(y), Q.real(y) & Q.nonzero(y), eng) is True
    assert ask(Q.real(y) & Q.real(w), Q.positive(y) & Q.negative(w), eng) is True
    assert ask(Q.positive(y) & Q.positive(w), Q.positive(y), eng) is None
    assert ask(Q.positive(y + w**2 + 1), Q.positive(y) & Q.real(w), eng) is True


def test_boolean_constants(eng):
    y = Symbol('y')
    assert ask(True, True, eng) is True
    assert ask(False, Q.real(y), eng) is False
    assert ask(Q.real(y), Q.real(y), eng) is True
    with pytest.raises(ValueError):
        ask(Q.real(y), False, eng)


# -- out of scope: None, with the category reported ---------------------------

def test_relations_return_none(eng):
    x, y = Symbol('x'), Symbol('y')
    assert ask(Q.positive(y), Q.gt(y, 0), eng) is None
    assert ask(Q.gt(y, 0), Q.positive(y), eng) is None
    assert ask(y > 0, Q.positive(y), eng) is None
    assert ask(Q.positive(x), Eq(x, 1), eng) is None
    assert ask(Q.positive(x) & Q.lt(y, x), Q.positive(y), eng) is None
    assert out_of_scope(Q.positive(y), Q.gt(y, 0)) == "relation"
    assert out_of_scope(y > 0) == "relation"
    assert out_of_scope(Q.positive(x), Eq(x, 1)) == "relation"
    with pytest.raises(Unsupported) as info:
        to_formula(Q.gt(y, 0))
    assert info.value.category == "relation"
    with pytest.raises(Unsupported) as info:
        to_formula(y > 0)
    assert info.value.category == "relation"


def test_is_true_over_relational_returns_none(eng):
    x = Symbol('x')
    assert ask(Q.is_true(x < 0), True, eng) is None
    assert ask(Q.is_true(x < 0), Q.negative(x), eng) is None
    assert out_of_scope(Q.is_true(x < 0)) == "relation"
    # Q.is_true over an applied predicate evaluates to that predicate: in scope
    assert ask(Q.is_true(Q.positive(x)), Q.positive(x), eng) is True


def test_matrix_predicates_return_none(eng):
    X = MatrixSymbol('X', 2, 2)
    x = Symbol('x')
    assert ask(Q.invertible(X), True, eng) is None
    assert ask(Q.invertible(X), Q.positive_definite(X), eng) is None
    assert ask(Q.square(X), True, eng) is None
    assert out_of_scope(Q.invertible(X)) == "matrix"
    # vocabulary predicate on a non-scalar argument
    assert ask(Q.real(X), True, eng) is None
    assert ask(Q.commutative(X), Q.real_elements(X), eng) is None
    assert out_of_scope(Q.real(X)) == "matrix"
    assert out_of_scope(Q.positive(x), Q.positive(x) & Q.invertible(X)) == "matrix"
    with pytest.raises(Unsupported) as info:
        to_formula(Q.real(X))
    assert info.value.category == "matrix"


def test_custom_predicates_return_none(eng):
    x = Symbol('x')
    mine = Predicate('mypredicate')
    assert ask(mine(x), True, eng) is None
    assert ask(Q.positive(x), mine(x) & Q.positive(x), eng) is None
    assert out_of_scope(mine(x)) == "custom"


def test_non_boolean_propositions_return_none(eng):
    x = Symbol('x')
    assert ask(Q.positive, True, eng) is None
    assert ask(pi / x, Q.real, eng) is None
    assert out_of_scope(Q.positive) == "other"


def test_out_of_scope_never_touches_the_engine(eng):
    X = MatrixSymbol('X', 2, 2)
    y = Symbol('y')
    assert ask(Q.invertible(X), True, eng) is None
    assert ask(Q.positive(y), Q.gt(y, 0), eng) is None
    assert eng.stats['queries'] == 0


def test_in_scope_query_returns_none_only_when_undecided(eng):
    y = Symbol('y')
    assert out_of_scope(Q.positive(y), Q.real(y)) is None
    assert ask(Q.positive(y), Q.real(y), eng) is None
    assert eng.stats['queries'] == 1
