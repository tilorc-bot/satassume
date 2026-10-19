"""Signs of closed compound constants in unary predicates (#180 C-SIGN).

The LRA adapter decides ``E - 2 > 0`` as a relation (exact field, else
rigorous interval bounds); ``relations.closed_units`` gives the unary sign
predicates of a closed node the same facts.
"""
import random

import pytest
from sympy import (Abs, Catalan, E, EulerGamma, Float, GoldenRatio, I, Integer, Q, Rational,
                   S, acos, asin, atan, cos, exp, gamma, log, pi, sin, sqrt, symbols, tan)

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
])
def test_undecided_signs(expr):
    eng = fresh()
    for pred in ('positive', 'negative', 'zero'):
        got = eng.is_(expr, pred)
        if got is not None:
            assert got == getattr(expr, 'is_' + pred), (expr, pred)


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
                    'asin', 'acos', 'gamma', 'abs'])
    if f == 'add':
        return a + b
    if f == 'sub':
        return a - b
    if f == 'mul':
        return a*b
    if f in ('asin', 'acos'):
        return {'asin': asin, 'acos': acos}[f](a/(Abs(a) + 1))
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
