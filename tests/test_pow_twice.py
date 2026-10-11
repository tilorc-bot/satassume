"""The node a Pow's rows over ``integer(2*e)`` read (``core._twice``):
validity of the slot at values, the exponent shapes, and the answers of
half-integer powers that the dropped derived ``2*e`` used to give."""
from itertools import product

import pytest
from sympy import I, Mul, Q, Rational as R, S, Symbol, symbols, nan, oo, zoo, sin

from satassume.knowledge.templates import core
from satassume.sympy_api import ask

n, m, x, y = symbols('n m x y')
VALUES = [S(v) for v in range(-4, 5)] + [R(1, 2), R(-3, 2), R(1, 3), R(5, 6), R(7, 4),
                                         oo, -oo, zoo, I, nan]

EXPONENTS = [n / 2, -n / 2, 3 * n / 2, -5 * n / 2, n * m / 2, -n * m / 2, n + R(1, 2),
             n - R(3, 2), Mul(R(1, 2), n, m, evaluate=False), n, sin(n), n ** 2,
             2 * n / 3, n + R(1, 3), n / 4, n * m, n + m, 2 * n, -n, n + 1, 3 * n * m]


def _integer(v):
    return v.is_integer is True


@pytest.mark.parametrize('e', EXPONENTS, ids=str)
def test_twice_slot_is_valid_at_values(e):
    """integer(s) -> integer(2*e) at every value of the symbols (k >= 1),
    and the converse for k == 2, whenever e is a rational number (the
    rows' premise ``rational(e)``)."""
    s_, k = core._twice(e)
    if s_ is None:
        assert k == 0
        return
    syms = sorted(e.free_symbols, key=str)
    for vals in product(VALUES, repeat=len(syms)):
        sub = dict(zip(syms, vals))
        ev = e.xreplace(sub)
        if ev.is_rational is not True:
            continue
        sv = s_.xreplace(sub)
        t2 = _integer(2 * ev)
        if _integer(sv):
            assert t2, (e, sub)
        if k == 2:
            assert _integer(sv) == t2, (e, sub)


def test_twice_shapes():
    assert core._twice(n / 2) == (n, 2)
    assert core._twice(-n / 2) == (n, 2)
    assert core._twice(3 * n / 2) == (n, 1)
    assert core._twice(n + R(1, 2)) == (n, 1)
    assert core._twice(n * m / 2) == (n * m, 2)
    # a symbol, a function, a power and a lattice coefficient keep 2*e
    for e in (n, sin(n), n ** 2, 2 * n / 3, n + R(1, 3), n / 4):
        assert core._twice(e) == (2 * e, 2)
    # integer coefficients: no node
    for e in (n * m, n + m, 2 * n, -n, n + 1):
        assert core._twice(e) == (None, 0)


k = Symbol('k', integer=True)
o = Symbol('o', odd=True)


@pytest.mark.parametrize('prop, assum, want', [
    (Q.imaginary((-2) ** (n / 2)), Q.odd(n), True),
    (Q.imaginary((-2) ** (-n / 2)), Q.odd(n), True),
    (Q.imaginary((-2) ** (n / 2)), Q.even(n), False),
    (Q.imaginary((-2) ** (3 * n / 2)), Q.odd(n), True),
    (Q.imaginary((-3) ** (n + R(1, 2))), Q.integer(n), True),
    (Q.imaginary((-2) ** (n * m / 2)), Q.odd(n) & Q.odd(m), True),
    (Q.imaginary(x ** y), Q.negative(x) & Q.rational(y) & ~Q.integer(2 * y), False),
    (Q.imaginary(x ** y), Q.negative(x) & Q.integer(2 * y) & ~Q.integer(y), True),
    (Q.imaginary((-2) ** (2 * k / 3)), Q.positive(k), False),
    (Q.imaginary((-2) ** (o / 2 + R(1, 3))), True, False),
])
def test_half_integer_powers(prop, assum, want):
    assert ask(prop, assum) is want
