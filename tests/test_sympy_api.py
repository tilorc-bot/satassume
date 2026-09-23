import pytest

sympy = pytest.importorskip("sympy")
from sympy import Symbol, Q, exp, sqrt, I, pi, Integer, Rational, oo, Abs, sin, log

from satassume import Engine, DictCache
from satassume.sympy_api import ask, is_, install, uninstall, to_formula, Unsupported


@pytest.fixture
def eng():
    return Engine(cache=DictCache())


def test_symbol_bridge(eng):
    x = Symbol('x', positive=True)
    assert is_(x, 'real', eng) is True
    assert is_(x, 'negative', eng) is False
    assert is_(Symbol('y'), 'real', eng) is None


def test_numbers(eng):
    assert is_(Integer(3), 'prime', eng) is True
    assert is_(Rational(1, 2), 'integer', eng) is False
    assert is_(pi, 'transcendental', eng) is True
    assert is_(I, 'real', eng) is False
    assert is_(oo, 'finite', eng) is False
    assert is_(oo, 'extended_positive', eng) is True


def test_structural_context_free(eng):
    p, q = Symbol('p', positive=True), Symbol('q', positive=True)
    u = Symbol('u', real=True)
    assert is_(p + 1, 'positive', eng) is True
    assert is_(p * q, 'positive', eng) is True
    assert is_(u**2 + 1, 'zero', eng) is False
    assert is_(u**2 + 1, 'positive', eng) is True
    assert is_(-p, 'negative', eng) is True
    assert is_(sqrt(p), 'positive', eng) is True
    assert is_(exp(u), 'positive', eng) is True
    assert is_(Abs(u), 'nonnegative', eng) is True


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


def test_unsupported_returns_none(eng):
    y = Symbol('y')
    assert ask(Q.positive(y), Q.gt(y, 0), eng) is None
    with pytest.raises(Unsupported):
        to_formula(Q.gt(y, 0))


def test_install_routes_is_properties():
    x = Symbol('x_install_test', positive=True)
    eng = install(Engine(cache=DictCache()))
    try:
        assert (x + 1).is_positive is True
        assert (x**2 + 1).is_zero is False
        assert eng.stats['queries'] >= 1
    finally:
        uninstall()
