"""Regressions from the rd/semdrop review: the Add rule "extended_real of
a sum without both infinities" is not implied by the other Add rules for 7
or more terms, and products of nonpositive factors need the nonpositive
Mul rows (without them their sign is found only after escalation)."""
import pytest

sympy = pytest.importorskip("sympy")

from sympy import Add, And, Mul, Q, symbols  # noqa: E402

from satassume.sympy_api import ask  # noqa: E402


@pytest.mark.parametrize("n", range(2, 13))
def test_extended_real_of_long_sums(n):
    xs = symbols(f"x0:{n}")
    s = Add(*xs)
    reals = [Q.real(x) for x in xs[:-1]]
    assert ask(Q.extended_real(s), And(*reals, Q.extended_real(xs[-1]))) is True
    assert ask(Q.extended_real(s), And(*reals, Q.real(xs[-1]))) is True
    no_pinf = [Q.extended_real(x) & ~Q.positive_infinite(x) for x in xs]
    assert ask(Q.extended_real(s), And(*no_pinf)) is True
    assert ask(Q.real(s), And(*reals, Q.extended_real(xs[-1]))) is None


@pytest.mark.parametrize("n", range(2, 6))
def test_products_of_nonpositives(n):
    xs = symbols(f"y0:{n}")
    p = Mul(*xs)
    neg = And(*[Q.negative(x) for x in xs])
    nonpos = And(*[Q.nonpositive(x) for x in xs])
    want = 'positive' if n % 2 == 0 else 'negative'
    assert ask(getattr(Q, want)(p), neg) is True
    assert ask(Q.nonnegative(p) if n % 2 == 0 else Q.nonpositive(p), nonpos) is True


@pytest.mark.parametrize("n", range(2, 11))
def test_products_of_integers(n):
    # integer closure of Mul is not implied by the other rows for >= 7
    # factors (rd/semdrop2 had dropped it)
    xs = symbols(f"z0:{n}")
    p = Mul(*xs)
    ints = And(*[Q.integer(x) for x in xs])
    evens = And(*[Q.even(x) for x in xs])
    assert ask(Q.integer(p), ints) is True
    assert ask(Q.noninteger(p), ints) is False
    assert ask(Q.integer(p), evens) is True
    assert ask(Q.integer(p), And(*[Q.odd(x) for x in xs[:-1]], Q.integer(xs[-1]))) is True
