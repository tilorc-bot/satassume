"""relations.has_any(e, atoms) is e.has(*atoms) for the singleton atoms the
adapters test for (nan, oo, -oo, zoo)."""
import itertools

from sympy import (Abs, AccumBounds, Add, E, Eq, Float, Function, I, Integral,
                   Interval, Lambda, Matrix, Max, Min, Mul, O, Piecewise, Pow,
                   Rational, S, Symbol, Tuple, exp, log, nan, oo, pi, sin,
                   sqrt, symbols, zoo)
from sympy.core.parameters import evaluate

from satassume.euf_adapter import _NAN
from satassume.lra_adapter import _BAD
from satassume.relations import has_any

x, y = symbols("x y", real=True)
a = Symbol("a")
f = Function("f")


def _pool():
    base = [x, a, S.Zero, S.One, Rational(-3, 2), Float(2.5), pi, E, I, sqrt(2),
            nan, oo, -oo, zoo, Float("inf"), Float("-inf"), Float("nan"),
            S.Infinity, S.NegativeInfinity, S.ComplexInfinity]
    out = list(base)
    out += [x + 1, 2 * x - y, x * y, x ** 2, 1 / x, exp(x), log(a), sin(x),
            Abs(x - 1), Max(x, y), Min(x, 1), f(x), f(oo), f(nan), f(zoo),
            Eq(x, oo), Tuple(x, nan), Interval(0, oo), Interval(-oo, x),
            AccumBounds(-1, 1), AccumBounds(-oo, oo), O(x), Integral(x, (x, 0, oo)),
            Piecewise((x, x > 0), (oo, True)), Lambda(x, x + zoo),
            Matrix([[x, oo], [1, 2]]).as_immutable(), exp(-oo), log(oo)]
    with evaluate(False):
        out += [Add(x, oo), Add(oo, -oo), Mul(0, oo), Pow(0, -1), Add(x, nan),
                Mul(zoo, x), Pow(oo, 0), Add(Float("inf"), 1)]
    out += [Add(*p) for p in itertools.combinations([x, y, a, 3, pi], 2)]
    out += [f(e) for e in base] + [Mul(2, e, evaluate=False) for e in base]
    return out


def test_has_any_is_has():
    sets = [_BAD, _NAN, frozenset((oo,)), frozenset((zoo, -oo)), frozenset()]
    n = 0
    for e in _pool():
        for s in sets:
            assert has_any(e, s) is e.has(*s), (e, s)
            n += 1
    assert n > 400


def test_has_any_nested():
    e = x
    for k in range(30):
        e = f(e, k)
    assert not has_any(e, _BAD)
    assert has_any(f(e, oo), _BAD) and f(e, oo).has(*_BAD)
