"""``relations.difference`` builds SymPy's ``a - b`` (same class, same args
in the same order) and, for single terms, does not call ``Add.flatten``."""
import itertools
import subprocess
import sys

import pytest
from sympy import (Abs, AccumBounds, E, Float, Function, I, MatrixSymbol, Mul, O, Pow,
                   Rational, S, Symbol, cos, exp, log, nan, oo, pi, sqrt, symbols, zoo)
from sympy.core.parameters import evaluate

from satassume.relations import difference

x, y = symbols("x y", real=True)
a, b = symbols("a b")
n = Symbol("n", integer=True)
p = Symbol("p", positive=True)
A, B = symbols("A B", commutative=False)
f, g = Function("f"), Function("g")


def pool():
    terms = [x, y, a, b, n, p, -x, -a, 2*x, -2*x, x/2, Float(2.5)*x, Float(1.0)*x, pi*x, I*x,
             sqrt(2)*x, x*y, -x*y, 2*x*y, a*b, x**2, -x**2, 3*x**2, x**y, sqrt(x), 1/x, x/y,
             f(x), f(y), -f(x), 2*f(x), g(x, y), f(x)*g(y), exp(x), log(x), log(y), Abs(x),
             cos(x), exp(x)*x, sqrt(2), sqrt(3), pi, E, I, 2*pi, pi**2, exp(2), log(2),
             S.Zero, S.One, S.NegativeOne, Rational(1, 2), Rational(-3, 4), S(7), Float(1.5),
             oo, -oo, zoo, nan, x + 1, x + y, x - y, 2*x + 3, f(x) + 1, Float(2.0)*(x + y),
             x*(y + 1), Pow(2, 3, evaluate=False), Pow(2, -1, evaluate=False),
             Mul(2, 3, x, evaluate=False), Mul(1, x, evaluate=False), Mul(S.Half, x, evaluate=False),
             oo*x, -oo*x, Float(0.5)*x, Float(-0.5)*x, A, 2*A, A*B, O(x), AccumBounds(1, 2), MatrixSymbol("M", 2, 2)]
    return terms


def outcome(fn):
    try:
        return ("ok", fn())
    except Exception as e:  # noqa: BLE001
        return ("raises", type(e))


def same(u, v):
    if isinstance(u, tuple) or isinstance(v, tuple):
        return u == v
    if type(u) is not type(v) or u != v:
        return False
    return all(same(s, t) for s, t in zip(u.args, v.args)) and len(u.args) == len(v.args)


def test_difference_is_sympys_subtraction():
    ts = pool()
    for u, v in itertools.product(ts, ts):
        got = outcome(lambda: difference(u, v))
        want = outcome(lambda: u - v)
        assert got[0] == want[0], (u, v, got, want)
        if got[0] == "ok":
            assert same(got[1], want[1]), (u, v, got[1].args, want[1].args)
        else:
            assert got[1] is want[1], (u, v)


def test_difference_of_products():
    small = [x, y, a, -x, 2*x, Float(1.5)*y, f(x), sqrt(2), x**2, exp(x), S(3), pi, I]
    prods = sorted({u*v for u, v in itertools.product(small, small)}, key=str)
    for u, v in itertools.product(prods, prods):
        got = outcome(lambda: difference(u, v))
        want = outcome(lambda: u - v)
        assert got[0] == want[0] == "ok", (u, v)
        assert same(got[1], want[1]), (u, v, got[1].args, want[1].args)


def test_difference_unevaluated():
    with evaluate(False):
        for u, v in ((x, y), (x, S.One), (2*x, y)):
            d = difference(u, v)
            assert same(d, u - v)


def test_difference_does_not_import_tensor():
    code = ("import sys\n"
            "from sympy import symbols, Function, S, log\n"
            "from satassume.relations import difference\n"
            "x, y = symbols('x y', real=True)\n"
            "a, b = symbols('a b')\n"
            "f = Function('f')\n"
            "assert 'sympy.tensor.tensor' not in sys.modules\n"
            "for u, v in ((x, y), (a, b), (y, x), (f(x), f(y)), (2*x, x*y), (log(x), x), (x, S.One), (x*y, S.One)):\n"
            "    difference(u, v)\n"
            "assert 'sympy.tensor.tensor' not in sys.modules, 'imported'\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
