"""``ComplexRootOf`` facts (#180 C-CROOT) and the exact root counts behind them."""
import random

import pytest

sympy = pytest.importorskip("sympy")
from sympy import CRootOf, Poly, Q, Symbol, degree, symbols

from satassume import DictCache, Engine
from satassume.knowledge.realroots import (
    MAX_DEGREE, imaginary_root_count, real_root_counts, root_facts, squarefree)
from satassume.sympy_api import ask

x = symbols('x')
FACTS = ('real', 'extended_real', 'imaginary', 'positive', 'negative', 'zero', 'nonzero',
         'algebraic', 'transcendental', 'finite', 'complex', 'rational', 'irrational', 'integer')


def fresh():
    return Engine(cache=DictCache())


def test_reproducers():
    # #180: is_real None made CRootOf._get_interval raise KeyError
    r = CRootOf(x**3 + x + 3, 0)
    assert fresh().is_(r, 'real') is True
    assert ask(Q.real(r), True, fresh()) is True
    assert ask(Q.negative(r), True, fresh()) is True
    assert fresh().is_(CRootOf(x**3 + x + 3, 1), 'real') is False
    assert fresh().is_(CRootOf(x**4 + 1, 0), 'imaginary') is False
    assert fresh().is_(CRootOf(x**4 - 2, 2), 'imaginary') is True
    assert ask(Q.positive(CRootOf(x**4 - 2, 1) - 1), Q.positive(Symbol('y')), fresh()) is None


def test_counts():
    assert real_root_counts([1, 0, -1]) == (1, 0, 1)            # x**2 - 1
    assert real_root_counts([1, 0, -3, 0]) == (1, 1, 1)         # x**3 - 3*x
    assert real_root_counts([1, 0, 1]) == (0, 0, 0)             # x**2 + 1
    assert real_root_counts([1, 1, 3]) == (0, 0, 0)
    assert real_root_counts([1, 0, 1, 3]) == (1, 0, 0)          # x**3 + x + 3
    assert imaginary_root_count([1, 0, 1]) == 2                 # +-i
    assert imaginary_root_count([1, 0, 0, 0, -2]) == 2          # x**4 - 2
    assert imaginary_root_count([1, 0, 0, 0, 1]) == 0           # x**4 + 1
    assert imaginary_root_count([1, 0, 1, 3]) == 0
    assert not squarefree([1, 0, -2, 0, 1])                      # (x**2 - 1)**2
    assert root_facts([1, 0, -2, 0, 1], 0) is None
    assert root_facts([1] + [0] * MAX_DEGREE + [1], 0) is None
    assert root_facts([1, 1], 1) is None                        # index out of range


def _sympy_vs_engine(p, i, out):
    r = CRootOf(p, i)
    if not isinstance(r, CRootOf):
        return
    e = fresh()
    assert e.is_(r, 'real') is not None, r
    for f in FACTS:
        mine, theirs = e.is_(r, f), getattr(r, 'is_' + f)
        if mine is not None and theirs is not None:
            assert mine == theirs, (r, f, mine, theirs)
        out[mine is None and theirs is not None] += 1


def test_against_sympy_on_random_polynomials():
    rng = random.Random(180)
    out = [0, 0]
    n = 0
    while n < 25:
        d = rng.randint(3, 7)
        p = sum(rng.randint(-5, 5) * x**k for k in range(d)) + rng.choice([1, 2, -3]) * x**d
        if degree(p, x) != d or not Poly(p, x).is_irreducible:
            continue
        n += 1
        for i in range(d):
            _sympy_vs_engine(p, i, out)
    # a mixed polynomial (some non-real roots imaginary, some not) is the
    # only case left undecided
    assert out[1] <= out[0] // 20, out


def test_constructed_from_a_reducible_polynomial():
    # CRootOf stores the irreducible factor of the root
    for i in range(3):
        _sympy_vs_engine(x**3 - 3*x, i, [0, 0])
    for i in range(5):
        _sympy_vs_engine((x**2 + 1)*(x**3 + x + 3), i, [0, 0])
