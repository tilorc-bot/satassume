"""Reciprocals of integers (#180 S7): bounds of ``1/v`` sign ``c0 + c1/v``,
an odd integer over an even one is no integer, ``1/v`` is an integer only
for ``v = +-1``, and ``(c0 + c1*u)**-k`` is no integer when integer bounds
of ``u`` put the base at 2 or more (or -2 or less).

Before, ``(1 - 1/n).is_nonnegative`` was None for a positive integer ``n``
(test_comb_numbers::test_harmonic, test_power::test_issue_18509), and so
were ``(o/e).is_integer`` (test_arit::test_Mul_is_integer) and
``((m + 1)**-2).is_integer`` (test_arit::test_Pow_is_integer).
"""
from itertools import product

import pytest
from sympy import Mul, Pow, Rational, Symbol

from satassume import DictCache, Engine

n = Symbol('n', integer=True, positive=True)
m = Symbol('m', integer=True, positive=True)
k = Symbol('k', integer=True)
pr = Symbol('pr', prime=True)
o = Symbol('o', odd=True)
e = Symbol('e', even=True)
ne = Symbol('ne', even=True, positive=True)


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    (1 - 1 / ne, 'extended_nonnegative', True),     # test_harmonic
    (1 - 1 / pr, 'extended_nonnegative', True),     # test_issue_18509
    (-1 + 1 / pr, 'extended_nonnegative', False),
    (o / e, 'integer', False),                      # test_Mul_is_integer
    (o / Symbol('2', prime=True, even=True), 'integer', False),
    ((m + 1)**-2, 'integer', False),                # test_Pow_is_integer
    (1 / pr, 'integer', False),                     # test_factorial_Mod
    (-1 / pr, 'integer', False),
    # more of the same
    (1 - 1 / n, 'nonnegative', True),
    (2 - 1 / n, 'positive', True),
    (Rational(1, 2) - 1 / pr, 'nonnegative', True),
    (1 + 1 / Symbol('j', integer=True, negative=True), 'nonnegative', True),
    (3 / e, 'integer', False),
    (o / e**3, 'integer', False),
    # core._pow_bound_templates (deleted by #315 step 2, no replacement):
    # 1 - 3*m <= -2, so its reciprocal is no integer; no SymPy test needs it
    pytest.param((1 - 3 * m)**-1, 'integer', False, marks=pytest.mark.xfail(
        strict=True, reason="#315 step 2 deleted core._pow_bound_templates")),
    ((m + 1)**(-k), 'integer', None),               # k = 0 or positive
    ((m + 1)**(-Symbol('kn', integer=True, positive=True)), 'integer', False),
    (1 / Symbol('c', composite=True), 'integer', False),
    # not theorems
    (1 - 1 / n, 'positive', None),                  # n = 1
    (1 / n, 'integer', None),
    (k**-2, 'integer', None),
    (e / o, 'integer', None),
    ((n - 1)**-1, 'integer', None),                 # n = 2
    ((1 - 2 * m)**-1, 'integer', None),             # m = 1
    (1 / k, 'odd', None),
    (Mul(o, Pow(e, -1, evaluate=False), evaluate=False), 'integer', False),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


# integer assumption sets with values (in -30..30) that satisfy them
INT_SETS = {
    'integer': (dict(integer=True), range(-30, 31)),
    'integer positive': (dict(integer=True, positive=True), range(1, 31)),
    'integer negative': (dict(integer=True, negative=True), range(-30, 0)),
    'odd': (dict(odd=True), range(-29, 31, 2)),
    'even': (dict(even=True), range(-30, 31, 2)),
    'prime': (dict(prime=True), [2, 3, 5, 7, 11, 13]),
    'composite': (dict(composite=True), [4, 6, 8, 9, 10, 12]),
    'even positive': (dict(even=True, positive=True), range(2, 31, 2)),
}
INT_PREDS = ('integer', 'odd', 'even', 'prime', 'composite')


def _int_facts(v):
    """The integer predicates of a SymPy number ``v``."""
    return {p: getattr(v, 'is_' + p) for p in INT_PREDS}


def _check(eng, expr, value):
    for pred in INT_PREDS:
        a = eng.is_(expr, pred)
        if a is not None:
            assert _int_facts(value)[pred] is a, (expr, pred, a, value)


@pytest.mark.parametrize("name", sorted(INT_SETS))
def test_powers_sound_at_points(name):
    # every definite integer fact of (c0 + c1*u)**j, u**j and a/u**-j
    # holds at every point u of the set
    kw, points = INT_SETS[name]
    u = Symbol('u', **kw)
    eng = fresh()
    for j in (-1, -2, -3):
        for c0, c1 in product((-3, -2, -1, 0, 1, 2, 3), (1, -1, 2, -2)):
            base = c0 + c1 * u
            for p in points:
                b = c0 + c1 * p
                if b != 0:
                    _check(eng, base**j, Rational(b)**j)
        for a in (1, 2, 3, -3, Rational(1, 2)):
            for p in points:
                if p != 0:
                    _check(eng, a * u**j, a * Rational(p)**j)


@pytest.mark.parametrize("na, nv", product(sorted(INT_SETS), repeat=2))
def test_quotients_sound_at_points(na, nv):
    a = Symbol('a', **INT_SETS[na][0])
    v = Symbol('v', **INT_SETS[nv][0])
    eng = fresh()
    for j in (-1, -2):
        for pa in list(INT_SETS[na][1])[::3]:
            for pv in list(INT_SETS[nv][1])[::3]:
                if pv != 0:
                    _check(eng, a * v**j, Rational(pa) * Rational(pv)**j)
