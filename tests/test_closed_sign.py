"""Signs of closed compound constants in unary predicates (#180 C-SIGN).

The LRA adapter decides ``E - 2 > 0`` as a relation (exact field, else
rigorous interval bounds); ``relations.closed_units`` gives the unary sign
predicates of a closed node the same facts.
"""
import random

import pytest
from sympy import (Abs, Catalan, E, EulerGamma, Float, GoldenRatio, I, Integer, Q, Rational,
                   S, acos, asin, atan, cos, exp, gamma, log, pi, sin, sqrt, symbols, tan, zeta)

from satassume import DictCache, Engine
from satassume.ref import ask_ref
from satassume.relations import default_specs
from satassume.sympy_api import ask

x = symbols('x')


def fresh():
    return Engine(cache=DictCache())


@pytest.mark.parametrize("expr, pred, expected", [
    # #180's table
    (E - 2, 'positive', True),
    (log(3)/log(2) - 1, 'positive', True),
    (sqrt(5) - 3, 'extended_nonnegative', False),
    (1 - exp(-1), 'positive', True),
    (2*acos(sqrt(30)/30), 'extended_real', True),
    # the constants and functions #180 measured as missing
    (log(GoldenRatio), 'positive', True),
    (Float(1.5) - sqrt(2), 'positive', True),
    (asin(Rational(1, 3)) - Rational(1, 3), 'positive', True),
    (gamma(Rational(1, 3)) - 2, 'positive', True),
    (EulerGamma - Rational(1, 2), 'positive', True),
    (Catalan - 1, 'negative', True),
    (pi - 3, 'zero', False),
    (acos(Rational(1, 3)) - 1, 'positive', True),
    (Abs(sin(2) - 1) - Rational(1, 10), 'negative', True),
    # #196: test_hypersum's Abs(243/8 - 27*zeta(3))
    (Rational(243, 8) - 27*zeta(3), 'negative', True),
    (Abs(Rational(243, 8) - 27*zeta(3)), 'positive', True),
    (zeta(3) - Rational(6, 5), 'positive', True),
    (zeta(5) - 1 - Rational(1, 32), 'positive', True),
    (zeta(Rational(3, 2)) - Rational(13, 5), 'positive', True),
    (zeta(1 + pi) - Rational(107, 100), 'positive', True),
    (zeta(sqrt(2)) - 3, 'positive', True),
])
def test_reproducers(expr, pred, expected):
    assert fresh().is_(expr, pred) is expected


def test_relation_and_unary_agree():
    for e in (E - 2, sqrt(5) - 3, pi - 3, log(3)/log(2) - 1):
        assert ask(Q.positive(e), True, fresh()) is ask(Q.gt(e, 0), True, fresh())


@pytest.mark.parametrize("expr", [
    sin(10**100),                    # no bounds: the argument is huge
    exp(I) - 1,                      # complex: no real interval
    sqrt(2) + I,
    log(-2) - 1,
    asin(Rational(3, 2)),            # outside [-1, 1]: complex
    gamma(Rational(-1, 2)) + 1,      # the argument is not positive
    zeta(Rational(1, 2)) + 1,        # zeta below 1 is not evaluated
    zeta(pi - 3) + 1,
    zeta(10**6 + 1) - 1,             # the terms are below 2**-4096
])
def test_undecided_signs(expr):
    eng = fresh()
    for pred in ('positive', 'negative', 'zero'):
        got = eng.is_(expr, pred)
        if got is not None:
            assert got == getattr(expr, 'is_' + pred), (expr, pred)


def test_log_with_a_base():
    # log(8, 3, evaluate=False) is log(8)/log(3) ~ 1.893, not log(8) ~ 2.079 (#190 review)
    e = log(8, 3, evaluate=False)
    assert fresh().is_(e - 2, 'positive') is not True
    assert ask(Q.gt(e, 2), True, fresh()) is not True


@pytest.mark.parametrize("expr", [
    Float('nan') - 1, Float('inf') - 1, Float('1e5000') - 1,
])
def test_float_without_bounds(expr):
    eng = fresh()
    for pred in ('positive', 'negative', 'zero', 'real'):
        assert eng.is_(expr, pred) is not True or getattr(expr, 'is_' + pred) is True


def test_real_without_a_sign():
    # finite real, but the interval cannot exclude 0: real, no sign
    e = asin(Rational(1, 3)) + acos(Rational(1, 3)) - pi/2
    eng = fresh()
    assert eng.is_(e, 'real') is True
    assert eng.is_(e, 'zero') is None


def test_abs_of_an_interval_around_zero():
    # Abs of an interval that straddles 0 starts at 0
    e = Abs(asin(Rational(1, 3)) + acos(Rational(1, 3)) - pi/2, evaluate=False)
    assert fresh().is_(e, 'negative') is not True
    assert fresh().is_(e - Rational(1, 10), 'negative') is True


def test_reference_agrees():
    specs = default_specs()
    for e in (E - 2, sqrt(5) - 3, asin(Rational(1, 3)) - Rational(1, 3)):
        assert ask_ref(Q.positive(e), True, relations=specs) is fresh().is_(e, 'positive')


def _random_closed(rng, depth):
    atoms = [pi, E, GoldenRatio, EulerGamma, Catalan, Rational(rng.randint(-9, 9), rng.randint(1, 9)),
             Float(rng.uniform(-3, 3), 20), sqrt(rng.randint(2, 30))]
    if depth == 0:
        return rng.choice(atoms)
    a, b = _random_closed(rng, depth - 1), _random_closed(rng, depth - 1)
    f = rng.choice(['add', 'sub', 'mul', 'exp', 'log', 'atan', 'sin', 'cos', 'tan',
                    'asin', 'acos', 'gamma', 'abs', 'zeta'])
    if f == 'add':
        return a + b
    if f == 'sub':
        return a - b
    if f == 'mul':
        return a*b
    if f in ('asin', 'acos'):
        return {'asin': asin, 'acos': acos}[f](a/(Abs(a) + 1))
    if f == 'zeta':
        return zeta(Rational(rng.randint(1, 9), 10) + Abs(a))   # half of them above 1
    return {'exp': exp, 'log': log, 'atan': atan, 'sin': sin, 'cos': cos, 'tan': tan,
            'gamma': gamma, 'abs': Abs}[f](a)


def test_random_closed_constants_against_high_precision():
    rng = random.Random(180)
    decided = 0
    for _ in range(150):
        e = _random_closed(rng, rng.randint(1, 3))
        if e.is_Atom or not e.is_number:
            continue
        v = e.evalf(60)
        re, im = v.as_real_imag()
        if abs(im) > Float('1e-40') or not re.is_Float or abs(re) < Float('1e-30'):
            continue                 # only clearly real, clearly nonzero values are checked
        truth = re > 0
        eng = fresh()
        pos, neg = eng.is_(e, 'positive'), eng.is_(e, 'negative')
        if pos is not None or neg is not None:
            decided += 1
        assert pos in (None, bool(truth)), e
        assert neg in (None, not truth), e
    assert decided >= 40
