"""Real/imaginary splits (#180 S7).

- ``b**e`` for imaginary ``b`` and an integer constant ``e``: ``I**e`` is
  -1 for ``e = 2 mod 4`` and 1 for ``e = 0 mod 4``, so the power is
  negative or positive (``9 - b**2`` is positive;
  test_solvers::test_real_imag_splitting).
- ``1/b`` is imaginary iff ``b`` is.
- A product of an imaginary, a complex ``l`` and nonzero reals is real
  only for ``l`` imaginary or zero, imaginary only for real ``l``
  (``imag_times`` had this for two factors), and the nonzero reals times
  ``k`` give an imaginary only for imaginary ``k``.
- ``I*(c_1*x_1 + ... + c)`` is imaginary when the real sum is signed
  (``I*nn + I``; test_assumptions::test_Add_is_imaginary,
  ::test_issue_4149), by the signs of the terms or, for numbers, by the
  sum (``-sqrt(3)*I/2 + 0.866025403784439*I``).
- ``im(x)`` is nonzero and ``tan(x)``, ``cot(x)`` are not real for a
  finite non-real ``x`` (test_trigonometric::test_real_assumptions).
"""
from itertools import product

import pytest
from sympy import I, Mul, Rational, S, Symbol, cot, im, nan, pi, sqrt, tan, zoo

from satassume import DictCache, Engine

b = Symbol('b', imaginary=True)
a = Symbol('a', imaginary=True)
nn = Symbol('nn', nonnegative=True)
p = Symbol('p', positive=True)
r = Symbol('r', real=True)
nz = Symbol('nz', real=True, zero=False)
c = Symbol('c', real=False, complex=True)
nr = Symbol('nr', real=False, finite=True)

PREDS = ('positive', 'negative', 'zero', 'real', 'extended_real', 'imaginary', 'finite')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # the S7 tests
    (9 - b**2, 'positive', True),                   # test_real_imag_splitting
    (sqrt(9 - b**2), 'imaginary', False),
    (a**2 + b**2, 'negative', True),
    (I * nn + I, 'imaginary', True),                # test_Add_is_imaginary
    (3 * I + pi * I + p * I, 'imaginary', True),    # test_issue_4149
    (-3 * I - pi * I + Symbol('n', negative=True) * I, 'imaginary', True),
    (S('-sqrt(3)*I/2 + 0.866025403784439*I'), 'imaginary', True),
    (S('-sqrt(3)*I/2 + 0.866025403784439*I'), 'real', False),
    (tan(nr), 'real', False),                       # test_real_assumptions
    (im(nr), 'zero', False),                        # test_zero_assumptions
    (nz * Symbol('i', imaginary=True) * c, 'imaginary', False),  # test_mul_zero_detection
    ((p + p * I)**-1, 'imaginary', False),          # test_Mul_is_imaginary_real
    # more of the same
    (b**4, 'positive', True),
    (b**-2, 'negative', True),
    (b**-4, 'positive', True),
    (cot(nr), 'extended_real', False),
    (I * p - I * nn, 'imaginary', None),
    (I * r + I, 'imaginary', None),
    (I * nn, 'imaginary', None),                    # nn = 0
    (-sqrt(3) * I / 2 + I, 'imaginary', True),
    (I * pi - 3 * I, 'imaginary', True),
    # not theorems
    (b**3, 'real', False),
    (a * b, 'positive', None),
    (I * b, 'positive', None),
    (nz * Symbol('i', imaginary=True) * c * Symbol('c2', real=False, complex=True),
     'imaginary', None),
    (tan(Symbol('w')), 'real', None),
    (im(Symbol('w', real=False)), 'zero', None),    # w = I*oo is not finite
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def _facts(v):
    """The predicates of PREDS for a SymPy number ``v``."""
    if v is nan or v is zoo:
        return {'positive': False, 'negative': False, 'zero': False, 'real': False,
                'extended_real': False, 'imaginary': False, 'finite': False}
    return {q: getattr(v, 'is_' + q) for q in PREDS}


def _check(eng, expr, value):
    f = _facts(value)
    for pred in PREDS:
        got = eng.is_(expr, pred)
        if got is not None and f[pred] is not None:
            assert f[pred] is got, (expr, pred, got, value)


REALS = [Rational(-3, 2), -1, Rational(-1, 3), 0, Rational(1, 2), 1, 2]
COMPLEX = [x + I * y for x, y in product((-1, 0, Rational(1, 2)), (-2, 0, 1))]


@pytest.mark.parametrize("kw", [dict(imaginary=True), dict(complex=True),
                                dict(real=False, complex=True)])
def test_powers_sound_at_points(kw):
    u = Symbol('u', **kw)
    eng = fresh()
    pts = [z for z in COMPLEX if all(getattr(z, 'is_' + k) is v for k, v in kw.items())]
    for e, z in product(range(-5, 6), pts):
        if z != 0:
            _check(eng, u**e, z**e)


SETS = {
    'real': (dict(real=True), REALS),
    'nonzero real': (dict(real=True, zero=False), [v for v in REALS if v != 0]),
    'positive': (dict(positive=True), [v for v in REALS if v > 0]),
    'nonnegative': (dict(nonnegative=True), [v for v in REALS if v >= 0]),
    'negative': (dict(negative=True), [v for v in REALS if v < 0]),
    'imaginary': (dict(imaginary=True), [I * v for v in REALS if v != 0]),
    'complex': (dict(complex=True), COMPLEX),
    'non-real': (dict(complex=True, real=False), [z for z in COMPLEX if not z.is_real]),
}


@pytest.mark.parametrize("n1, n2, n3", [
    ('imaginary', 'complex', 'nonzero real'), ('non-real', 'imaginary', 'nonzero real'),
    ('imaginary', 'non-real', 'real'), ('imaginary', 'imaginary', 'nonzero real'),
    ('complex', 'nonzero real', 'nonzero real'),
])
def test_products_sound_at_points(n1, n2, n3):
    x, y, z = (Symbol(f's{k}', **SETS[n][0]) for k, n in enumerate((n1, n2, n3)))
    eng = fresh()
    for e in (Mul(x, y, z), Mul(x, y, z, Symbol('t', positive=True))):
        for px, py, pz in product(SETS[n1][1], SETS[n2][1], SETS[n3][1]):
            v = (px * py * pz).expand()
            if len(e.args) == 3:
                _check(eng, e, v)
            else:
                for pt in (Rational(1, 3), 2):
                    _check(eng, e, (v * pt).expand())


@pytest.mark.parametrize("names", [('positive', 'nonnegative'), ('negative', 'nonnegative'),
                                   ('real', 'positive'), ('nonnegative', 'nonnegative')])
@pytest.mark.parametrize("cs", [(1, 1, 1), (1, -1, 2), (-1, -2, -1), (Rational(1, 2), 1, 0),
                                (1, 1, -1), (2, 3, 0)])
def test_imaginary_sums_sound_at_points(names, cs):
    x, y = (Symbol(f's{k}', **SETS[n][0]) for k, n in enumerate(names))
    c1, c2, c0 = cs
    expr = c1 * I * x + c2 * I * y + c0 * I
    eng = fresh()
    for px, py in product(SETS[names[0]][1], SETS[names[1]][1]):
        _check(eng, expr, (c1 * px + c2 * py + c0) * I)


def test_functions_sound_at_points():
    eng = fresh()
    for f in (im, tan, cot):
        e = f(nr)
        for z in SETS['non-real'][1]:
            _check(eng, e, f(z).evalf() if f is not im else f(z))
