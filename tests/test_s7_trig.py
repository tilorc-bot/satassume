"""``sin(pi*c*s)`` and ``cos(pi*c*s)`` for a rational ``c`` (#180 S7).

- The value is algebraic when ``c*s`` is rational (``sin(pi*q)``,
  ``cos(2*pi/7)``; test_trigonometric::test_sin, ::test_cos).
- For a number ``c`` the sign is that of ``sin(pi*r)``, ``r = c mod 2``
  (``c + 1/2`` for cos), and the value is 0 or +-1 at the multiples of
  ``1/2``.
- For an integer ``s``: ``sin(pi*k*s)`` is 0 and ``cos(pi*k*s)`` is +-1
  (``k`` integer, the sign by the parities); ``sin(pi*s/2)`` and
  ``cos(pi*s/2)`` by the parity of ``s``.
"""
import pytest
from sympy import I, Rational, Symbol, cos, pi, sin

from satassume import DictCache, Engine

q = Symbol('q', rational=True)
k = Symbol('k', integer=True)
e = Symbol('e', even=True)
o = Symbol('o', odd=True)
x = Symbol('x')
r = Symbol('r', real=True)

PREDS = ('positive', 'negative', 'zero', 'odd', 'algebraic', 'real')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    (sin(pi * q), 'algebraic', True),               # test_sin
    (sin(k * pi, evaluate=False), 'zero', True),
    (cos(pi * q), 'algebraic', True),               # test_cos
    (cos(pi * Rational(2, 7)), 'algebraic', True),
    # more of the same
    (cos(2 * pi / 7), 'positive', True),
    (sin(-2 * pi / 7), 'negative', True),
    (cos(pi * k, evaluate=False), 'odd', True),
    (cos(2 * pi * k, evaluate=False), 'positive', True),
    (cos(pi * e, evaluate=False), 'positive', True),
    (cos(pi * o, evaluate=False), 'negative', True),
    (cos(pi * o / 2, evaluate=False), 'zero', True),
    (cos(pi * e / 2, evaluate=False), 'odd', True),
    (sin(pi * e / 2, evaluate=False), 'zero', True),
    (sin(pi * o / 2, evaluate=False), 'odd', True),
    (sin(3 * pi * q / 5), 'algebraic', True),
    # not theorems
    (sin(pi * x), 'algebraic', None),
    (sin(pi * r), 'algebraic', None),
    (cos(pi * k / 2, evaluate=False), 'zero', None),
    (sin(pi * o / 2, evaluate=False), 'positive', None),
    (cos(pi * k / 3, evaluate=False), 'positive', None),
    (sin(pi * q), 'zero', None),
    (sin(I * pi * k, evaluate=False), 'zero', None),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def _facts(value):
    """The predicates of PREDS for ``value``, a real algebraic number, from
    its numeric value (``sin(pi*c)`` is 0 or +-1 exactly when the float
    is)."""
    v = float(value.evalf(30))
    z = abs(v) < 1e-12
    return {'positive': not z and v > 0, 'negative': not z and v < 0, 'zero': z,
            'odd': abs(abs(v) - 1) < 1e-12, 'algebraic': True, 'real': True}


def _check(eng, expr, value):
    f = _facts(value)
    for pred in PREDS:
        got = eng.is_(expr, pred)
        if got is not None:
            assert f[pred] is got, (expr, pred, got, value)


@pytest.mark.parametrize("f", [sin, cos])
def test_numbers_sound(f):
    eng = fresh()
    for d in (1, 2, 3, 4, 6, 7, 12):
        for n in range(-3 * d, 3 * d + 1):
            c = Rational(n, d)
            if c == 0:
                continue
            _check(eng, f(pi * c, evaluate=False), f(pi * c))


@pytest.mark.parametrize("f", [sin, cos])
@pytest.mark.parametrize("c", [1, 2, 3, -1, -2, Rational(1, 2), Rational(3, 2), Rational(-1, 2),
                               Rational(5, 2), Rational(1, 3), Rational(-2, 5)])
def test_symbols_sound_at_points(f, c):
    eng = fresh()
    for s, points in ((k, range(-4, 5)), (e, range(-4, 5, 2)), (o, range(-5, 6, 2)),
                      (q, [Rational(n, 6) for n in range(-7, 8)])):
        expr = f(pi * c * s, evaluate=False)
        for v in points:
            _check(eng, expr, f(pi * c * v))
