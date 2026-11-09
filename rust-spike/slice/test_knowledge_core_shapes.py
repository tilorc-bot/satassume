"""Step 6e: crafted queries for the shape tests of core's moved functions that dev, fuzz, value and the core wl never reach
with an input that tells Rust and Python apart (the core plants 'off' scores `no`, mutate_knowledge.py). Each query is asked
twice, plain (Python) and under `knowledge_live.install(shadow=True)`, which also runs Python's function on each call and
compares every field. A test passes when the answers agree, the shadow saw no mismatch, and the function was reached."""
import pytest
from sympy import Add, E, I, Mul, Pow, Q, S, Symbol, ceiling, cos, cosh, exp, floor, im, pi, re, sin

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
#: Equivalent mutants (scored void, not caught by design): core-mul-sets-ct-two (a 2-arg Mul's rest is one factor, and
#: `kept_product` of one factor is None on both sides) and core-mul-sets-ipi-any (the Python shell's own `s_.is_Mul` test in
#: knowledge_core_live.mul_factor_sets drops a one-factor rest, as Python does). Their cases still check answers and the shadow.
CASES = [
    ('core:bound_split', 'core-bound-zero-kept', lambda: Q.positive(a(S(1), m(S.Zero, x))), lambda: Q.real(x)),
    ('core:recip_templates', 'core-recip-any-exp', lambda: Q.positive(a(S(1), Pow(x, 2, evaluate=False))), lambda: Q.real(x)),
    ('core:imag_templates', 'core-imag-rules-strict', lambda: Q.imaginary(a(m(I, x), m(I, y))), lambda: Q.positive(x) & Q.positive(y)),
    ('core:imag_split', 'core-imag-two-rest', lambda: Q.imaginary(a(m(I, x, y), m(S(2), I))), lambda: Q.positive(x) & Q.positive(y)),
    ('core:_pi_split', 'core-pi-split-second-i', lambda: Q.real(exp(m(I, I, pi, x), evaluate=False)), lambda: Q.integer(x)),
    ('core:_mul_factor_sets', 'core-mul-sets-ipi-any', lambda: Q.real(m(I, pi, x)), lambda: Q.integer(x)),
    ('core:_mul_factor_sets', 'core-mul-sets-ct-two', lambda: Q.positive(m(S(2), x)), lambda: Q.positive(x)),
    ('core:_quotient_templates', 'core-quotient-rules', lambda: Q.integer(m(x, Pow(y, -1, evaluate=False))),
     lambda: Q.odd(x) & Q.even(y)),
    ('core:_unit_angle', 'core-unit-angle-neg', lambda: Q.real(Pow(m(S.NegativeOne, I), Rational_(1, 2), evaluate=False)), lambda: True),
    ('core:_exp_arg', 'core-exp-arg-any', lambda: Q.positive(Pow(Pow(S(2), y, evaluate=False), m(I, x), evaluate=False)),
     lambda: Q.real(x) & Q.real(y)),
    ('core:_pow_bound_templates', 'core-pow-bound-any-exp', lambda: Q.positive(Pow(a(S(1), x), 3, evaluate=False)), lambda: Q.positive(x)),
    # 6g(c3): the Pow family's direct pieces.
    ('core:_pow_bound_templates', 'core-pow-bound-neg', lambda: Q.integer(Pow(a(S(2), m(S(3), x)), -1, evaluate=False)),
     lambda: Q.integer(x) & Q.positive(x)),
    ('core:irrational_root', 'core-irrational-root', lambda: Q.irrational(Pow(S(2), Rational_(1, 2), evaluate=False)), lambda: True),
    ('core:_unit_power_units', 'core-unit-power', lambda: Q.real(Pow(I, S(3), evaluate=False)), lambda: True),
    ('core:_pi_split', 'core-ipi-split-pow', lambda: Q.real(Pow(S.Exp1, m(I, pi, x), evaluate=False)), lambda: Q.integer(x)),
    ('core:_exp_arg', 'core-exp-arg-inner', lambda: Q.positive(Pow(Pow(E, x, evaluate=False), 2, evaluate=False)), lambda: Q.real(x)),
    ('core:ipi_rules', 'core-ipi-rules-pow', lambda: Q.complex(Pow(S.Exp1, m(S(2), I, pi, y), evaluate=False)), lambda: Q.real(y)),
    # 6g(c4): the compiled power rows' constants of a Rational exponent (number/2, 2*number, number - 2, 1/number) and of a
    # Rational base (Abs(number) - 1, Abs(number) - 2), computed in Rust; the shadow compares _rows_runtime.constant_value.
    ('core:constant_value', 'rows-constant-value-exp', lambda: Q.positive(Pow(x, Rational_(3, 2), evaluate=False)),
     lambda: Q.positive(x)),
    ('core:constant_value', 'rows-constant-value-base', lambda: Q.positive(Pow(Rational_(-1, 3), x, evaluate=False)),
     lambda: Q.even(x)),
    # 6g(c5): the four Addition template builders computed in Rust (`RowsTpl::add_tpl`); the shadow runs core's builder with
    # `facts` captured and compares (key, consts, objs, node, rules).
    ('core:_half_templates', 'rows-half-tpl-flip', lambda: Q.integer(a(m(Rational_(1, 2), x), m(Rational_(1, 2), y))),
     lambda: Q.odd(x) & Q.odd(y)),
    ('core:_bound_templates', 'rows-bound-tpl-neg', lambda: Q.positive(a(S(1), m(S(2), x))),
     lambda: Q.integer(x) & Q.nonnegative(x)),
    ('core:recip_templates', 'rows-recip-tpl-neg', lambda: Q.positive(a(S(2), m(S(3), Pow(y, -1, evaluate=False)))),
     lambda: Q.positive(y)),
    ('core:imag_templates', 'rows-imag-tpl-sign', lambda: Q.imaginary(a(m(I, x), m(I, y))),
     lambda: Q.positive(x) & Q.positive(y)),
    # 6g(c6): `_pi_trig` and the plain `_unary` as rows_tpl.rs families (Family::PiTrig, Family::Unary); the shadow runs
    # functions' template with `facts` captured and compares (key, consts, objs, node, rules); `pi_split` is direct.
    ('core:pi_split', 'rows-pi-split-shift', lambda: Q.negative(cos(m(pi, x))), lambda: Q.odd(x)),
    ('core:_pi_trig', 'rows-pi-trig-flip', lambda: Q.zero(sin(m(pi, x))), lambda: Q.integer(x)),
    ('core:_pi_trig', 'pi-trig-half', lambda: Q.odd(sin(m(Rational_(1, 2), pi, x))), lambda: Q.odd(x)),
    ('core:_pi_trig', 'pi-trig-cosh-ipi', lambda: Q.real(cosh(m(I, pi, x))), lambda: Q.real(x)),
    ('core:_unary', 'rows-unary-key-none', lambda: Q.real(a(sin(S(2)), sin(x))), lambda: Q.complex(x)),
    ('core:_unary', 'unary-cos-plain', lambda: Q.real(cos(x)), lambda: Q.real(x)),
    # 6g(c7): `_cosh_shift` as a rows_tpl.rs family (Family::CoshShift), `_cosh_shift_split` from the query's table; the
    # shadow runs functions' template with `facts` captured; no split: the plain `_unary` (cosh(x)).
    ('core:_cosh_shift', 'rows-cosh-shift-parity', lambda: Q.positive(cosh(a(y, m(2, I, pi, x)))),
     lambda: Q.real(y) & Q.integer(x)),
    ('core:_cosh_shift', 'cosh-shift-odd', lambda: Q.negative(cosh(a(y, m(I, pi)))), lambda: Q.real(y)),
    ('core:_cosh_shift', 'cosh-shift-odd-s', lambda: Q.negative(cosh(a(y, m(3, I, pi, x)))),
     lambda: Q.real(y) & Q.odd(x)),
    ('core:_unary', 'rows-cosh-plain-none', lambda: Q.real(cosh(x)), lambda: Q.real(x)),
    # 6g(c8): `_exp_ipi` as a rows_tpl.rs family (Family::ExpIpi): `ipi_split` and `ipi_rules` from Rust.
    ('core:_exp_ipi', 'rows-exp-ipi-drop', lambda: Q.real(exp(m(I, pi, x))), lambda: Q.integer(x)),
    ('core:_exp_ipi', 'exp-ipi-half', lambda: Q.imaginary(exp(m(Rational_(1, 2), I, pi, x))), lambda: Q.odd(x)),
    ('core:_exp_ipi', 'exp-ipi-plain', lambda: Q.positive(exp(x)), lambda: Q.real(x)),
    ('core:_exp_ipi', 'rows-exp-const-key-none', lambda: Q.positive(a(exp(S(2)), x)), lambda: Q.positive(x)),
    # 6g(c9): `parts_of_round_templates` as a rows_tpl.rs family (Family::PartsOfRound; `wiring._attributed` carries the tag).
    ('core:parts_of_round_templates', 'rows-round-skip', lambda: Q.integer(re(floor(x))), lambda: Q.finite(x)),
    ('core:parts_of_round_templates', 'round-im-ceiling', lambda: Q.integer(im(ceiling(x))), lambda: Q.finite(x)),
    ('core:parts_of_round_templates', 'rows-round-key-none',
     lambda: Q.integer(a(re(ceiling(Rational_(1, 3), evaluate=False), evaluate=False), x)), lambda: Q.integer(x)),
]


#: The shell counters of the splits rows_tpl.rs computes directly (6g(c)), by the shadow's name.
DIRECT = {'core:half_split': '_half_split', 'core:bound_split': '_bound_split', 'core:imag_split': '_imag_split',
          'core:_mul_factor_sets': '_mul_factor_sets', 'core:_quotient_templates': '_quotient_templates',
          'core:_unit_angle': '_unit_angle', 'core:_exp_arg': '_exp_arg', 'core:_pow_bound_templates': '_pow_bound_templates',
          'core:irrational_root': 'irrational_root', 'core:_unit_power_units': '_unit_power_units',
          'core:_pi_split': 'ipi_split', 'core:ipi_rules': 'ipi_rules', 'core:constant_value': 'constant_value',
          'core:_half_templates': '_half_templates', 'core:_bound_templates': '_bound_templates',
          'core:recip_templates': '_recip_templates', 'core:imag_templates': '_imag_templates',
          'core:pi_split': 'pi_split', 'core:_pi_trig': '_pi_trig', 'core:_unary': '_unary',
          'core:_cosh_shift': '_cosh_shift', 'core:_exp_ipi': '_exp_ipi',
          'core:parts_of_round_templates': 'parts_of_round_templates'}


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
    # 6g(c): rows_tpl.rs answers a split of input terms directly, so the shell never runs; the shadow then runs Python's split
    # on that result and compares (`shadow:direct:NAME`, knowledge_core_live.shadow_split).
    direct = 'shadow:direct:' + DIRECT[counter] if counter in DIRECT else None
    assert c.get(counter, 0) + c.get(direct, 0) > 0, (counter, sorted(c))
    assert c.get('shadow:mismatch', 0) == 0, K.MISMATCHES[-3:]
    assert got == plain and c.get('fault', 0) == 0
