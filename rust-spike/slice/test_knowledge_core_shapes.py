"""Step 6e: crafted queries for the shape tests of core's moved functions that dev, fuzz, value and the core wl never reach
with an input that tells Rust and Python apart (the core plants 'off' scores `no`, mutate_knowledge.py). Each query is asked
twice, plain (Python) and under `knowledge_live.install(shadow=True)`, which also runs Python's function on each call and
compares every field. A test passes when the answers agree, the shadow saw no mismatch, and the function was reached."""
import pytest
from sympy import Add, E, I, Mul, Pow, Q, S, Symbol, exp, pi

import knowledge_live as K
import term_live
from harness.state import reset_module_state
from satassume import engine as E_, sympy_api

x, y = Symbol('x'), Symbol('y')


def m(*a):
    return Mul(*a, evaluate=False)


def a(*t):
    return Add(*t, evaluate=False)


#: (moved function's counter, plant it stands for, query builder, assumptions builder). Built per test, so no test reuses
#: another's objects.
CASES = [
    ('core:bound_split', 'core-bound-zero-kept', lambda: Q.positive(a(S(1), m(S.Zero, x))), lambda: Q.real(x)),
    ('core:recip_templates', 'core-recip-any-exp', lambda: Q.positive(Pow(a(S(1), x), 2, evaluate=False)), lambda: Q.positive(x)),
    ('core:imag_split', 'core-imag-two-rest', lambda: Q.imaginary(a(m(I, x, y), m(S(2), I))), lambda: Q.positive(x) & Q.positive(y)),
    ('core:_pi_split', 'core-pi-split-second-i', lambda: Q.real(exp(m(I, I, pi, x), evaluate=False)), lambda: Q.integer(x)),
    ('core:_mul_factor_sets', 'core-mul-sets-ipi-any', lambda: Q.real(m(I, pi, x)), lambda: Q.integer(x)),
    ('core:_mul_factor_sets', 'core-mul-sets-ct-two', lambda: Q.positive(m(S(2), x)), lambda: Q.positive(x)),
    ('core:_unit_angle', 'core-unit-angle-neg', lambda: Q.real(Pow(m(S.NegativeOne, I), Rational_(1, 2), evaluate=False)), lambda: True),
    ('core:_exp_arg', 'core-exp-arg-any', lambda: Q.real(Pow(S(2), m(I, pi, x), evaluate=False)), lambda: Q.integer(x)),
    ('core:_pow_bound_templates', 'core-pow-bound-any-exp', lambda: Q.positive(Pow(a(S(1), x), 3, evaluate=False)), lambda: Q.positive(x)),
]


def Rational_(p, q):
    return S(p) / q


def fresh():
    reset_module_state()                # the engine's memos and its answer memo would answer a repeat without the template
    sympy_api.set_default_engine(E_.Engine())


@pytest.mark.parametrize('counter,plant,query,assume', CASES, ids=[c[1] for c in CASES])
def test_shape(counter, plant, query, assume):
    fresh()
    plain = sympy_api.ask(query(), assume())
    undo = K.install(shadow=True)
    try:
        K.COUNTS.clear()
        fresh()
        got = sympy_api.ask(query(), assume())
        c = dict(K.COUNTS)
    finally:
        undo()
        K.COUNTS.clear()
    assert c.get(counter, 0) > 0, (counter, sorted(c))
    assert c.get('shadow:mismatch', 0) == 0, K.MISMATCHES[-3:]
    assert got == plain and c.get('fault', 0) == 0
