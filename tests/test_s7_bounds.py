"""An odd composite is at least 9 (#180 S7 G7).

``factorial(n - 1) % n`` is 0 for a composite ``n >= 6`` (Wilson's
theorem, inverse): SymPy asks ``(n - 6).is_nonnegative``
(test_arit::test_Mod, odd composite ``n``).  The bound also feeds
``_not_unit_premises``: ``1/(n - 7)`` is no integer.
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
    (n / 2 - 4, 'positive', True),
    ((n - 7)**-1, 'integer', False),                  # base >= 2 (_not_unit_premises)
    ((11 - n)**-1, 'integer', False),                 # base <= -2
    # not theorems
    (n - 10, 'nonnegative', None),                    # n = 9
    (n - 9, 'positive', None),
    (n / 2 - 5, 'positive', None),
    ((n - 8)**-1, 'integer', None),                   # n = 9
    (c - 6, 'nonnegative', None),                     # c = 4
    (k - 5, 'nonnegative', None),                     # k = 4
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_smallest_odd_composite_is_9():
    # composite excludes 1 (and every integer below 4)
    assert min(m for m in range(3, 100, 2) if not isprime(m)) == 9
