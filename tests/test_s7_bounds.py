"""An odd composite is at least 9 (#180 S7 G7).

``factorial(n - 1) % n`` is 0 for a composite ``n >= 6`` (Wilson's
theorem, inverse): SymPy asks ``(n - 6).is_nonnegative``
(test_arit::test_Mod, odd composite ``n``).
"""
import pytest
from sympy import Symbol, isprime

from satassume import DictCache, Engine

n = Symbol('n', composite=True, odd=True)
c = Symbol('c', composite=True)
k = Symbol('k', composite=True, even=True)


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    (n - 6, 'nonnegative', True),                     # test_Mod
    (n - 9, 'nonnegative', True),
    (n - 8, 'positive', True),
    (9 - n, 'nonpositive', True),
    (-n + 8, 'negative', True),
    (2 * n - 18, 'nonnegative', True),
    # not theorems
    (n - 10, 'nonnegative', None),                    # n = 9
    (n - 9, 'positive', None),
    (c - 6, 'nonnegative', None),                     # c = 4
    (k - 5, 'nonnegative', None),                     # k = 4
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_smallest_odd_composite_is_9():
    assert min(m for m in range(3, 100, 2) if not isprime(m)) == 9
