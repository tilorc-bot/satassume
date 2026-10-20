"""Integer bounds of a sum ``c0 + c1*u`` (#180 S7): a positive integer is
at least 1, a prime at least 2, a composite at least 4, a positive even
integer at least 2.

Before, ``(n - 1).is_nonnegative`` was None for a positive integer ``n``
(test_sums_products::test_Sum_doit, test_comb_factorials::test_factorial_Mod
and a dozen more): ``is_`` queries are propositional, and the Add
template had no rule that rounds a strict sign of an integer.
"""
from itertools import product

import pytest
from sympy import Rational, Symbol, atan, factorial, log

from satassume import DictCache, Engine

n = Symbol('n', integer=True, positive=True)
pr = Symbol('pr', prime=True)

PREDS = ('positive', 'negative', 'nonnegative', 'nonpositive', 'zero', 'nonzero',
         'extended_positive', 'extended_nonnegative')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the reproducer table of #180 S7
    (pr - 1, 'nonnegative', True),
    (n - 1, 'nonnegative', True),
    (log(n), 'nonnegative', True),
    # from the S7 tests
    (pr - 1, 'positive', True),
    (1 - pr, 'extended_nonnegative', False),
    (2 * n - 1, 'positive', True),
    (n - Rational(1, 2), 'positive', True),
    (factorial(n) - 1, 'nonnegative', True),
    (atan(n - 1), 'nonnegative', True),
    (n * (n - 1), 'nonnegative', True),
    # not theorems
    (n - 1, 'positive', None),          # n = 1
    (Symbol('i', integer=True) - 1, 'nonnegative', None),
    (Symbol('r', positive=True) - 1, 'nonnegative', None),
    (1 - 1 / n, 'positive', None),      # n = 1
    (pr / 2 - 1, 'nonnegative', True),
    (Symbol('c', composite=True) - 4, 'nonnegative', True),
    (Symbol('e', even=True, negative=True) + 2, 'nonpositive', True),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


# assumption sets of u with the integer values (in -30..30) that satisfy
# them; the non-integer sets have no rule and must give no bound
INT_SETS = {
    'integer positive': (dict(integer=True, positive=True), range(1, 31)),
    'prime': (dict(prime=True), [2, 3, 5, 7, 11, 13]),
    'composite': (dict(composite=True), [4, 6, 8, 9, 10, 12]),
    'even positive': (dict(even=True, positive=True), range(2, 31, 2)),
    'odd negative': (dict(odd=True, negative=True), range(-29, 0, 2)),
    'even negative': (dict(even=True, negative=True), range(-30, 0, 2)),
    'integer nonnegative': (dict(integer=True, nonnegative=True), range(0, 31)),
    'integer nonpositive': (dict(integer=True, nonpositive=True), range(-30, 1)),
}
REAL_SETS = {
    'positive': (dict(positive=True), [Rational(1, 7), Rational(1, 2), 1, 3]),
    'negative': (dict(negative=True), [Rational(-1, 7), Rational(-1, 2), -1, -3]),
    'nonnegative': (dict(nonnegative=True), [0, Rational(1, 7), 1]),
}
C0 = [Rational(c) for c in (-4, -3, -2, -1, 0, 1, 2, 3, 4)] + [Rational(k, 2) for k in (-3, -1, 1, 3)] \
    + [Rational(1, 3), Rational(-1, 3)]
C1 = [Rational(c) for c in (1, -1, 2, -2, 3)] + [Rational(1, 2), Rational(-1, 2)]


def _holds(pred, v):
    return {'positive': v > 0, 'negative': v < 0, 'nonnegative': v >= 0, 'nonpositive': v <= 0,
            'zero': v == 0, 'nonzero': v != 0, 'extended_positive': v > 0,
            'extended_nonnegative': v >= 0}[pred]


@pytest.mark.parametrize("name", sorted(INT_SETS) + sorted(REAL_SETS))
@pytest.mark.parametrize("recip", [False, True])
def test_sound_at_points(name, recip):
    # every definite answer about c0 + c1*u (c0 + c1/u) holds at every point
    # u of the assumption set (all of them for the integer sets)
    kw, points = {**INT_SETS, **REAL_SETS}[name]
    u = Symbol('u', **kw)
    eng = fresh()
    for c0, c1 in product(C0, C1):
        expr = c0 + c1 / u if recip else c0 + c1 * u
        for pred in PREDS:
            a = eng.is_(expr, pred)
            if a is None:
                continue
            for p in points:
                if recip and p == 0:
                    continue
                v = c0 + (c1 / Rational(p) if recip else c1 * p)
                assert bool(_holds(pred, v)) is a, (expr, pred, a, p)


def test_answers_agree_with_sympy():
    # the sweep answers what SymPy answers (the old rules round the same
    # bounds), apart from the cases where SymPy says None
    for name in sorted(INT_SETS):
        u = Symbol('u', **INT_SETS[name][0])
        eng = fresh()
        for c0, c1 in product(C0, C1):
            expr = c0 + c1 * u
            for pred in PREDS:
                a, b = eng.is_(expr, pred), getattr(expr, 'is_' + pred)
                assert a is None or b is None or a is b, (expr, pred, a, b)
