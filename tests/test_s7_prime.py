"""Primality of sums, products and powers of integers (#180 S7).

- A sum of two or more positive integers is at least 2: prime or composite.
- A product of two integers >= 2 (and more positive integers) is
  composite ((x+1)*(y+1); test_assumptions::test_Mul_is_prime_composite).
- An integer to a power >= 2 is no prime; an integer >= 2 to such a power
  and an integer <= -2 (``b + 1`` negative) to an even one are composite
  (x**(y+1), (x+1)**(y+1), (-x-1)**(2*y);
  test_assumptions::test_Pow_is_prime_composite).
"""
from itertools import product

import pytest
from sympy import Integer, Mul, Pow, Symbol, factorial, isprime

from satassume import DictCache, Engine

x = Symbol('x', positive=True, integer=True)
y = Symbol('y', positive=True, integer=True)
z = Symbol('z', positive=True, integer=True)
n = Symbol('n', integer=True)
p = Symbol('p', prime=True)
r = Symbol('r', positive=True)
m = Symbol('m', integer=True, nonnegative=True)


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    ((x + 1) * (y + 1), 'prime', False),            # test_Mul_is_prime_composite
    ((x + 1) * (y + 1), 'composite', True),
    (x**(y + 1), 'prime', False),                   # test_Pow_is_prime_composite
    ((x + 1)**(y + 1), 'composite', True),
    ((-x - 1)**(2 * y), 'composite', True),
    # more of the same
    ((x + y) * p, 'composite', True),
    ((x + 1) * (y + 1) * z, 'composite', True),
    (p**(y + 1), 'composite', True),
    (n**(y + 1), 'prime', False),
    ((-x - 1)**(2 * y + 1), 'prime', False),
    ((-x - 1)**(2 * y + 1), 'composite', False),    # negative
    (factorial(m + 2), 'even', True),               # test_issue_9115_9150
    # not theorems
    (factorial(m + 1), 'even', None),
    (x * y, 'prime', None),
    (x**(y + 1), 'composite', None),                # x = 1
    ((x + 1) * (y + 1) * n, 'composite', None),     # n <= 0
    ((r + 1) * (y + 1), 'prime', None),
    ((r + 1) * (y + 1), 'composite', None),
    ((-x)**(2 * y), 'composite', None),             # x = 1
    ((n - 1)**(2 * y), 'composite', None),          # n = 0
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


EXPRS = [
    x + y, x + 1, x + y + z, (x + 1) * (y + 1), (x + y) * (z + 1), (x + 1) * (y + 1) * z,
    x**(y + 1), (x + 1)**(y + 1), (-x - 1)**(2 * y), (-x - 1)**(2 * y + 1), (-x)**(2 * y),
    (x + 1)**y, Pow(x + 1, y, evaluate=False) * (z + 1), (n + 1)**(y + 1), (n - 1)**(2 * y),
]


@pytest.mark.parametrize("expr", EXPRS, ids=str)
def test_sound_at_points(expr):
    eng = fresh()
    got = {pred: eng.is_(expr, pred) for pred in ('prime', 'composite')}
    free = sorted(expr.free_symbols, key=str)
    values = {x: range(1, 5), y: range(1, 4), z: range(1, 4), n: range(-3, 4)}
    for vals in product(*(values[s] for s in free)):
        v = expr.subs(dict(zip(free, vals)))
        assert isinstance(v, Integer), (expr, vals, v)
        facts = {'prime': bool(isprime(v)), 'composite': bool(v > 1) and not isprime(v)}
        for pred, g in got.items():
            if g is not None:
                assert facts[pred] is g, (expr, vals, v, pred, g)


def test_unevaluated_product_of_powers():
    e = Mul(Pow(x + 1, y + 1, evaluate=False), y + 1, evaluate=False)
    assert fresh().is_(e, 'composite') is True
