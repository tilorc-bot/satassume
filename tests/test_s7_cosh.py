"""``cosh(I*pi*c*s)`` and ``cosh(r + I*pi*c*s)`` (#180 S7).

- ``cosh(I*pi*c*s) == cos(pi*c*s)`` gets the rules of ``cos(pi*c*s)``
  (``cosh(I*pi/4)`` is positive, ``cosh(3*I*pi/4)`` negative;
  test_hyperbolic::test_cosh_positive, ::test_cosh_nonnegative).
- ``cosh(r + I*pi*m) == (-1)**m*cosh(r)`` for an integer ``m == c*s``:
  ``cosh(k + 2*n*pi*I)`` is positive and ``cosh(k + pi*I)`` negative for
  a real ``k``; real for an imaginary ``r``.
"""
import pytest
from sympy import Add, I, Rational, Symbol, cosh, oo, pi

from satassume import DictCache, Engine

k = Symbol('k', real=True)
n = Symbol('n', integer=True)
e = Symbol('e', even=True)
o = Symbol('o', odd=True)
q = Symbol('q', rational=True)
x = Symbol('x')
y = Symbol('y', extended_real=True)
p = Symbol('p', positive=True)

PREDS = ('positive', 'negative', 'zero', 'odd', 'real', 'finite')


def fresh():
    return Engine(cache=DictCache())


def C(arg):
    return cosh(arg, evaluate=False)


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    (C(k + 2 * n * pi * I), 'positive', True),         # test_cosh_positive
    (C(I * pi / 4), 'positive', True),
    (C(3 * I * pi / 4), 'positive', False),
    (C(k + 2 * n * pi * I), 'nonnegative', True),      # test_cosh_nonnegative
    (C(I * pi / 4), 'nonnegative', True),
    (C(3 * I * pi / 4), 'nonnegative', False),
    # more of the same
    (C(k + pi * I), 'negative', True),
    (C(k + 3 * o * pi * I), 'negative', True),
    (C(k + 3 * e * pi * I), 'positive', True),
    (C(k + 2 * o * n * pi * I), 'positive', True),
    (C(p + k + 2 * n * pi * I), 'positive', True),
    (C(1 + 2 * n * pi * I), 'positive', True),
    (C(Rational(1, 2) + 3 * o * pi * I), 'negative', True),
    (C(I * pi * n), 'odd', True),
    (C(I * pi * o), 'negative', True),
    (C(I * pi * o / 2), 'zero', True),
    (C(I * pi * q), 'algebraic', True),
    (C(I * pi * Rational(2, 7)), 'algebraic', True),
    # not theorems
    (C(k + n * pi * I), 'positive', None),             # n odd: -cosh(k)
    (C(k + n * pi * I / 2), 'real', None),
    (C(x + 2 * n * pi * I), 'positive', None),
    (C(y + 2 * n * pi * I), 'positive', None),         # y = oo
    (C(Add(k, -k, 2 * n * pi * I, evaluate=False)), 'positive', None),
    (C(I * pi * x), 'algebraic', None),
    (C(I * pi * k / 2), 'zero', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def _facts(value):
    """The predicates of PREDS for ``value``, a finite real number."""
    v = complex(value.evalf(30))
    assert abs(v.imag) < 1e-12, value
    v = v.real
    z = abs(v) < 1e-12
    return {'positive': not z and v > 0, 'negative': not z and v < 0, 'zero': z,
            'odd': abs(abs(v) - 1) < 1e-12, 'real': True, 'finite': True}


def _check(eng, expr, value):
    f = _facts(value)
    for pred in PREDS:
        got = eng.is_(expr, pred)
        if got is not None:
            assert f[pred] is got, (expr, pred, got, value)


@pytest.mark.parametrize("c", [1, 2, 3, -1, -2, Rational(1, 2), Rational(3, 2), Rational(1, 3)])
def test_ipi_sound_at_points(c):
    eng = fresh()
    for s, points in ((n, range(-4, 5)), (e, range(-4, 5, 2)), (o, range(-5, 6, 2)),
                      (q, [Rational(m, 6) for m in range(-7, 8)])):
        expr = C(I * pi * c * s)
        for v in points:
            _check(eng, expr, cosh(I * pi * c * v))


@pytest.mark.parametrize("c", [1, 2, 3, -1, -2])
def test_shift_sound_at_points(c):
    eng = fresh()
    for s, points in ((None, [1]), (n, range(-3, 4)), (e, range(-4, 5, 2)), (o, range(-5, 6, 2))):
        for r in (k, p + k):
            expr = C(r + I * pi * c * (1 if s is None else s))
            for v in points:
                for kv in (0, 1, Rational(-3, 2)):
                    val = cosh(r.subs({k: kv, p: 1}) + I * pi * c * v)
                    _check(eng, expr, val)


def test_infinite_rest_not_shifted():
    # cosh(oo + 2*I*pi*n) must not get the facts of cosh(oo)
    eng = fresh()
    assert eng.is_(C(y + 2 * n * pi * I), 'finite') is None
    assert eng.is_(C(oo + 2 * n * pi * I), 'positive') is None
