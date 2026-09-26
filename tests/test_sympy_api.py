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

def test_relations_return_none():
    # an engine without theory adapters (tests/test_relations.py has the rest)
    eng = Engine(cache=DictCache(), relations=[])
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


def test_is_true_over_relational_returns_none():
    # an engine without theory adapters (tests/test_relations.py has the rest)
    eng = Engine(cache=DictCache(), relations=[])
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
    assert eng.stats['queries'] == 0
    # relations are out of scope only for an engine without theory adapters
    # (satassume.relations); see tests/test_relations.py for the other case
    eng = Engine(cache=DictCache(), relations=[])
    assert ask(Q.positive(y), Q.gt(y, 0), eng) is None
    assert eng.stats['queries'] == 0


def test_in_scope_query_returns_none_only_when_undecided(eng):
    y = Symbol('y')
    assert out_of_scope(Q.positive(y), Q.real(y)) is None
    assert ask(Q.positive(y), Q.real(y), eng) is None
    assert eng.stats['queries'] == 1


# -- in scope: the classes closed while finishing the slice -------------------

def test_hermitian_antihermitian_scalars(eng):
    x = Symbol('x')
    assert ask(Q.hermitian(I), True, eng) is False
    assert ask(Q.antihermitian(Integer(11)), True, eng) is False
    assert ask(Q.hermitian(oo), True, eng) is False
    assert ask(Q.antihermitian(oo), True, eng) is False
    assert ask(Q.antihermitian(x), Q.zero(x), eng) is True
    assert ask(Q.hermitian(x), Q.imaginary(x), eng) is False
    assert ask(Q.hermitian(I*x), Q.antihermitian(x), eng) is True
    assert ask(Q.antihermitian(I*x), Q.real(x), eng) is True
    # 0 is real and antihermitian, so these stay undecided (SymPy says False)
    assert ask(Q.antihermitian(x), Q.real(x), eng) is None
    assert ask(Q.hermitian(I*x), Q.real(x), eng) is None


def test_add_mul_closures(eng):
    from sympy import log, sqrt, Mul
    x, y, z = Symbol('x'), Symbol('y'), Symbol('z')
    assert ask(Q.finite(x + y), Q.positive_infinite(x) & Q.positive_infinite(y), eng) is False
    assert ask(Q.finite(x + y + z), Q.negative_infinite(y) & Q.negative_infinite(z) & Q.positive(x), eng) is False
    assert ask(Q.finite(x + y), ~Q.extended_positive(x) & ~Q.extended_positive(y) & ~Q.finite(y), eng) is False
    assert ask(Q.finite(x + y), Q.positive_infinite(x) & Q.negative_infinite(y), eng) is None
    assert ask(Q.real(I*(1 + I)), True, eng) is False
    assert ask(Q.prime(I*(1 + I)), True, eng) is False
    assert ask(Q.imaginary(log(2) + I*pi/2), True, eng) is False
    assert ask(Q.prime(4*x), Q.integer(x), eng) is False
    assert ask(Q.rational(2/x), Q.irrational(x), eng) is False
    assert ask(Q.rational(y/x), Q.irrational(x) & Q.nonzero(y) & Q.rational(y), eng) is False
    assert ask(Q.positive(-x*y*z), Q.negative(y) & Q.negative(z) & Q.positive(x), eng) is False
    assert ask(Q.prime(Mul(2, 2, evaluate=False) + 0), True, eng) in (False, None)
    # x*y with x imaginary and y real may be zero, so imaginary is undecided
    assert ask(Q.imaginary(x*y), Q.imaginary(x) & Q.real(y), eng) is None


def test_pow_closures(eng):
    from sympy import E, Rational, exp, Pow
    x, y, n, i = Symbol('x'), Symbol('y'), Symbol('n'), Symbol('i')
    assert ask(Q.real(I**I), True, eng) is True
    assert ask(Q.real(I**(2 + I)), True, eng) is True
    assert ask(Q.imaginary(I**(3 + I)), True, eng) is True
    assert ask(Q.real(3**I), True, eng) is False
    assert ask(Q.positive(2**I), True, eng) is False
    assert ask(Q.real(I**i), Q.imaginary(i), eng) is True
    assert ask(Q.rational(sqrt(2)), True, eng) is False
    assert ask(Q.irrational(sqrt(2)), True, eng) is True
    assert ask(Q.integer(sqrt(5)), True, eng) is False
    assert ask(Q.prime(Pow(x, 1, evaluate=False)), Q.prime(x), eng) is True
    assert ask(Q.prime(n**x), Q.composite(n) & Q.integer(x), eng) is False
    assert ask(Q.finite(2**x), Q.extended_negative(x), eng) is True
    assert ask(Q.finite(Rational(1, 2)**x), Q.extended_positive(x), eng) is True
    assert ask(Q.imaginary(x**y), Q.rational(y) & Q.real(x) & ~Q.integer(2*y), eng) is False
    assert ask(Q.imaginary(x**Rational(1, 4)), Q.negative(x), eng) is False
    assert ask(Q.real(exp(x)**x), Q.imaginary(x), eng) is True
    assert ask(Q.real(Pow(exp(2*I*pi*x), x)), Q.integer(x), eng) is True
    assert ask(Q.imaginary(Pow(exp(I*pi*x/2), x)), Q.odd(x), eng) is True
    assert ask(Q.positive(Pow(E, I*pi*x, evaluate=False)), Q.even(x), eng) is True
    assert ask(Q.integer(x**y), Q.integer(x) & Q.integer(y) & Q.negative(y)
               & ~Q.zero(x - 1) & ~Q.zero(x + 1), eng) is False
    # 0**(-1) is zoo, so these stay undecided (SymPy says True)
    assert ask(Q.complex(x**y), Q.complex(x) & Q.complex(y), eng) is None


def test_function_closures(eng):
    from sympy import exp, log, acos, asin, cot, acot, Rational
    x = Symbol('x')
    assert ask(Q.real(exp(I*pi, evaluate=False)), True, eng) is True
    assert ask(Q.imaginary(exp(I*pi/2, evaluate=False)), True, eng) is True
    assert ask(Q.real(exp(I*pi/2, evaluate=False)), True, eng) is False
    assert ask(Q.positive(exp(I*pi*x)), Q.even(x), eng) is True
    assert ask(Q.positive(exp(I*pi*x)), Q.odd(x), eng) is False
    assert ask(Q.rational(exp(0, evaluate=False)), True, eng) is True
    assert ask(Q.rational(log(1, evaluate=False)), True, eng) is True
    assert ask(Q.rational(log(7)), True, eng) is False
    assert ask(Q.positive(log(x + 2)), Q.positive(x), eng) is True
    assert ask(Q.rational(log(x)), Q.rational(x) & Q.nonzero(x - 1), eng) is False
    assert ask(Q.algebraic(acos(7)), True, eng) is False
    assert ask(Q.rational(acos(1, evaluate=False)), True, eng) is True
    assert ask(Q.positive(acos(Rational(1, 7))), True, eng) is True
    assert ask(Q.positive(asin(x)), Q.positive(x) & Q.nonpositive(x - 1), eng) is True
    assert ask(Q.rational(cot(7)), True, eng) is False
    assert ask(Q.rational(cot(x)), Q.rational(x), eng) is False
    assert ask(Q.algebraic(acot(x)), Q.algebraic(x), eng) is False
    assert ask(Q.positive(acot(x)), Q.imaginary(x), eng) is False
    # sin(oo*I) is oo*I, so finiteness needs a finite argument
    from sympy import sin
    assert ask(Q.finite(sin(x)), True, eng) is None
    assert ask(Q.finite(sin(x)), Q.finite(x), eng) is True


# -- constants: answered without the assumptions -------------------------------

def test_constant_proposition_ignores_assumptions(eng):
    x = Symbol('x')
    # inconsistent assumptions do not raise for a question about constants
    assert ask(Q.positive(pi), Q.positive(x) & Q.negative(x), eng) is True
    assert ask(~Q.zero(Integer(-1)) & Q.negative(Integer(-1)), Q.zero(x) & ~Q.zero(x), eng) is True
    # an assumption about something else does not change the answer
    assert ask(Q.rational(pi), Q.rational(x), eng) is False
    # a proposition with a free symbol still reads the assumptions and raises
    with pytest.raises(ValueError):
        ask(Q.positive(x + pi), Q.positive(x) & Q.negative(x), eng)


def test_undefined_function_value_is_not_a_constant(eng):
    from sympy import Function
    f = Function('f')
    assert ask(Q.positive(f(1)), Q.positive(f(1)), eng) is True
    with pytest.raises(ValueError):
        ask(Q.positive(f(1)), Q.positive(f(1)) & Q.negative(f(1)), eng)


def test_constant_route_needs_builtin_predicates_and_no_undefined_function(eng):
    from sympy import Function, Integral
    from satassume import Implies
    from satassume.sympy_api import _is_constant_proposition
    from satassume.formula import P
    f, x = Function('f'), Symbol('x')
    assert _is_constant_proposition(Q.positive(pi) & Q.lt(pi, 4))
    assert not _is_constant_proposition(Q.positive(Integral(f(x), (x, 0, 1))))
    e = Integral(f(x), (x, 0, 1))
    assert ask(Q.positive(e), Q.positive(e), eng) is True

    class Nice(Predicate):
        name = 'nice_constant_test'
    nice = Nice()
    from satassume.sympy_api import register, unregister
    fn = register('nice_constant_test', Integer)(lambda n: Implies(P('nice_constant_test', n),
                                                                      P('positive', n)))
    try:
        assert not _is_constant_proposition(nice(Integer(2)))
        assert ask(nice(Integer(2)), nice(Integer(2)), eng) is True
    finally:
        unregister('nice_constant_test')
