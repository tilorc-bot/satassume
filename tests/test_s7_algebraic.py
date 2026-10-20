"""Algebraic products and powers (#180 S7 Galg).

- One non-algebraic factor and the rest nonzero algebraics: the product is
  not algebraic (the other factor is the product over the rest);
  test_assumptions::test_Mul_is_algebraic.
- ``1**e == 1`` for complex ``e``; test_assumptions::test_Pow_is_algebraic
  (``Pow(1, e, evaluate=False)``).
- Gelfond-Schneider for symbolic ``b`` and ``e``: ``b**e`` is not algebraic
  for algebraic ``b`` with ``b != 0``, ``b - 1 != 0`` and algebraic
  irrational ``e``; test_assumptions::test_Pow_is_algebraic (``ia**ib``).
"""
import pytest
from sympy import I, Pow, S, Symbol, oo, sqrt

from satassume import DictCache, Engine

a = Symbol('a', algebraic=True)
an = Symbol('an', algebraic=True, nonzero=True)
na = Symbol('na', algebraic=False)
e = Symbol('e', algebraic=True)
ia = Symbol('ia', algebraic=True, irrational=True)
ib = Symbol('ib', algebraic=True, irrational=True)
q = Symbol('q', rational=True, positive=True)
xi = Symbol('xi', infinite=True)
xr = Symbol('xr', real=True)
x = Symbol('x')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    (an * na, 'algebraic', False),                    # test_Mul_is_algebraic
    (Pow(1, e, evaluate=False), 'algebraic', True),   # test_Pow_is_algebraic
    (ia**ib, 'algebraic', False),
    # more of the same
    (an * na * ia, 'algebraic', False),
    (2 * na, 'algebraic', False),
    (an * xi, 'algebraic', False),
    (Pow(1, xr, evaluate=False), 'odd', True),
    (Pow(1, xr, evaluate=False), 'prime', False),
    (ia**ib, 'transcendental', True),
    ((q + 1)**ib, 'algebraic', False),                # q + 1 > 1
    (ia**(I * ib), 'algebraic', False),               # non-real exponent
    (sqrt(2)**ib, 'algebraic', False),                # constant base (b=algebraic.gs)
    # not theorems
    (a * na, 'algebraic', None),                      # a = 0
    (an * x, 'algebraic', None),
    (Pow(1, x, evaluate=False), 'algebraic', None),   # 1**oo is nan
    (q**ib, 'algebraic', None),                       # q = 1
    (a**ib, 'algebraic', None),                       # a = 0, 1
    (ia**e, 'algebraic', None),                       # e rational
    (ia**x, 'algebraic', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_one_to_infinity_not_one():
    eng = fresh()
    assert eng.is_(Pow(1, oo, evaluate=False), 'algebraic') is not True
    assert eng.is_(Pow(S.One, xi, evaluate=False), 'algebraic') is not True
