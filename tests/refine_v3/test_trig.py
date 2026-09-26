"""Tests for ``satrefine/handlers_v3/trig.py``.

Every positive case is checked twice: against an expected closed form and
numerically (``assert_refinement_valid``) at integer shifts k in
{1, 2, 3, 4, -1, -3, ...} that satisfy the assumptions and at real and
complex values of the free part.
"""
from __future__ import annotations

import pytest
from sympy import (
    AccumBounds, I, N, Q, Rational, S, Symbol, cos, cot, csc, pi, sec, sin,
    sinc, tan, zoo,
)
from sympy.core.basic import Basic

from satrefine import handlers_dict, refine
from satrefine.testing.harness import assert_refinement_valid, stub_ask, use_ask
from satrefine.handlers_v3 import trig

x = Symbol('x')
y = Symbol('y')
k = Symbol('k')
n = Symbol('n')

K_VALUES = [1, 2, 3, 4, -1, -3, -2, 5, 6, 7, 0, -4, -5]
X_VALUES = [S.Zero, Rational(1, 3), S(2), 2 + I, -I / 2, Rational(3, 2) - 2 * I, pi / 5]
VALUES = {k: K_VALUES, n: K_VALUES, x: X_VALUES, y: [Rational(1, 7), 1 - I]}

ODD = Q.odd(k)
EVEN = Q.even(k)
K1 = Q.odd(k) & Q.even((k - 1) / 2)   # k = 1 mod 4
K3 = Q.odd(k) & Q.odd((k - 1) / 2)    # k = 3 mod 4
K0 = Q.even(k) & Q.even(k / 2)        # k = 0 mod 4
K2 = Q.even(k) & Q.odd(k / 2)         # k = 2 mod 4
INT = Q.integer(k)
m1 = S.NegativeOne

# (expr, assumptions, expected)
CASES = [
    # full-period shifts x + k*pi
    (sin(x + k*pi), EVEN, sin(x)),
    (sin(x + k*pi), ODD, -sin(x)),
    (sin(x + k*pi), INT, m1**k * sin(x)),
    (cos(x + k*pi), EVEN, cos(x)),
    (cos(x + k*pi), ODD, -cos(x)),
    (cos(x + k*pi), INT, m1**k * cos(x)),
    (sec(x + k*pi), ODD, -sec(x)),
    (csc(x + k*pi), ODD, -csc(x)),
    (sec(x + k*pi), INT, m1**k * sec(x)),
    (tan(x + k*pi), INT, tan(x)),
    (cot(x + k*pi), INT, cot(x)),
    (sin(x + y + 2*k*pi), INT, sin(x + y)),
    (cos(x + 2*k*pi), INT, cos(x)),
    # half-period shifts x + k*pi/2, k mod 4 known
    (sin(x + k*pi/2), K1, cos(x)),
    (sin(x + k*pi/2), K3, -cos(x)),
    (sin(x + k*pi/2), K0, sin(x)),
    (sin(x + k*pi/2), K2, -sin(x)),
    (cos(x + k*pi/2), K1, -sin(x)),
    (cos(x + k*pi/2), K3, sin(x)),
    (cos(x + k*pi/2), K0, cos(x)),
    (cos(x + k*pi/2), K2, -cos(x)),
    (sec(x + k*pi/2), K1, -csc(x)),
    (sec(x + k*pi/2), K3, csc(x)),
    (sec(x + k*pi/2), K2, -sec(x)),
    (csc(x + k*pi/2), K1, sec(x)),
    (csc(x + k*pi/2), K3, -sec(x)),
    (csc(x + k*pi/2), K2, -csc(x)),
    # half-period shifts, only parity known
    (tan(x + k*pi/2), ODD, -cot(x)),
    (cot(x + k*pi/2), ODD, -tan(x)),
    (tan(x + k*pi/2), EVEN, tan(x)),
    (cot(x + k*pi/2), EVEN, cot(x)),
    (sin(x + k*pi/2), ODD, m1**((k - 1)/2) * cos(x)),
    (cos(x + k*pi/2), ODD, m1**((k + 1)/2) * sin(x)),
    (sec(x + k*pi/2), ODD, m1**((k + 1)/2) * csc(x)),
    (csc(x + k*pi/2), ODD, m1**((k - 1)/2) * sec(x)),
    (sin(x + k*pi/2), EVEN, m1**(k/2) * sin(x)),
    (cos(x + k*pi/2), EVEN, m1**(k/2) * cos(x)),
    (sin(x + (2*k + 1)*pi/2), INT, m1**k * cos(x)),
    # mixed: known-parity part shifted, unknown part kept
    (cos(x + n*pi/2 + k*pi), Q.integer(n) & ODD, -cos(x + n*pi/2)),
    # special values
    (sin(k*pi), INT, S.Zero),
    (cos(k*pi), INT, m1**k),
    (cos(k*pi), EVEN, S.One),
    (cos(k*pi), ODD, S.NegativeOne),
    (cos(2*k*pi), INT, S.One),
    (tan(k*pi), INT, S.Zero),
    (sec(k*pi), ODD, S.NegativeOne),
    (sin(k*pi/2), K1, S.One),
    (sin(k*pi/2), K3, S.NegativeOne),
    (cos(k*pi/2), ODD, S.Zero),
    (cot(k*pi/2), ODD, S.Zero),
    (sinc(k*pi), INT & Q.nonzero(k), S.Zero),
    (sinc(2*k*pi), INT & Q.nonzero(k), S.Zero),
    (sinc(k*pi/2), K1, 2/(k*pi)),
    (sinc(k*pi/2), K3, -2/(k*pi)),
    # zero arguments and poles
    (sin(x), Q.zero(x), S.Zero),
    (cos(x), Q.zero(x), S.One),
    (tan(x), Q.zero(x), S.Zero),
    (sec(x), Q.zero(x), S.One),
    (cot(x), Q.zero(x), zoo),
    (csc(x), Q.zero(x), zoo),
    (sinc(x), Q.zero(x), S.One),
    (cos(x + k*pi), Q.zero(x) & ODD, S.NegativeOne),
    (cot(k*pi), INT, zoo),
    (csc(k*pi), INT, zoo),
    (tan(k*pi/2), ODD, zoo),
    (sec(k*pi/2), ODD, zoo),
]


def _ids(case):
    return f"{case[0]}|{case[1]}"


@pytest.mark.parametrize("expr, assumptions, expected", CASES, ids=[_ids(c) for c in CASES])
def test_rule(expr, assumptions, expected):
    refined = refine(expr, assumptions)
    assert (refined - expected).expand() == 0 or refined == expected, refined
    assert isinstance(refined, Basic)


@pytest.mark.parametrize("expr, assumptions, expected", CASES, ids=[_ids(c) for c in CASES])
def test_rule_numerically_sound(expr, assumptions, expected):
    refined = refine(expr, assumptions)
    free = expr.free_symbols - {k, n}
    values = {s: VALUES[s] for s in expr.free_symbols | refined.free_symbols}
    if free and not any(assumptions.has(Q.zero(s)) for s in free):
        # force at least one complex sample for the free part
        values[x] = [2 + I, -I / 2] + list(X_VALUES)
    assert_refinement_valid(expr, assumptions, refined, samples=400, values=values)


@pytest.mark.parametrize("func", [sin, cos, tan, cot, sec, csc])
@pytest.mark.parametrize("kv", [1, 2, 3, 4, -1, -3])
@pytest.mark.parametrize("xv", [Rational(1, 3), 2 + I, -I / 2])
def test_explicit_points_30_digits(func, kv, xv):
    """Evaluate at explicit points with N(., 30), k known only by parity/mod 4."""
    parity_q = Q.even(k) if kv % 2 == 0 else Q.odd(k)
    mod4_q = (Q.even(k / 2) if kv % 4 == 0 else Q.odd(k / 2)) if kv % 2 == 0 else \
        (Q.even((k - 1) / 2) if kv % 4 == 1 else Q.odd((k - 1) / 2))
    for arg in (x + k*pi, x + k*pi/2):
        for assumptions in (parity_q, parity_q & mod4_q):
            expr = func(arg)
            refined = refine(expr, assumptions)
            sub = {k: kv, x: xv}
            left = N(expr.subs(sub), 30)
            right = N(refined.subs(sub), 30)
            assert abs(complex(left - right)) < 1e-25, (expr, assumptions, refined)


# --- negative tests -------------------------------------------------------

@pytest.mark.parametrize("func", [sin, cos, tan, cot, sec, csc])
def test_half_period_needs_parity(func):
    expr = func(x + k*pi/2)
    assert refine(expr, Q.integer(k)) == expr


@pytest.mark.parametrize("func", [sin, cos, tan, cot, sec, csc])
def test_non_integer_shift_unchanged(func):
    for assumptions in (Q.real(k), Q.rational(k), True):
        expr = func(x + k*pi)
        assert refine(expr, assumptions) == expr


@pytest.mark.parametrize("func", [sin, cos, sec, csc])
def test_mod4_unknown_keeps_sign_symbolic(func):
    refined = refine(func(x + k*pi/2), Q.odd(k))
    assert refined.has(k)  # sign (-1)**(...) not resolved to a constant


def test_imaginary_shift_not_treated():
    for func in (sin, cos, tan, cot, sec, csc):
        expr = func(x + k*pi*I)
        assert refine(expr, Q.integer(k)) == expr


def test_sinc_needs_nonzero_integer():
    assert refine(sinc(k*pi), Q.integer(k)) == sinc(k*pi)
    assert refine(sinc(x + k*pi), Q.even(k)) == sinc(x + k*pi)
    assert refine(sinc(x), Q.real(x)) == sinc(x)


def test_sinc_zero_via_integer_k_includes_zero_case():
    # k even alone includes k = 0 where sinc = 1: must stay unchanged
    assert refine(sinc(k*pi), Q.even(k)) == sinc(k*pi)


def test_unknown_answers_leave_expression_unchanged():
    with use_ask(stub_ask({})):
        for func in (sin, cos, tan, cot, sec, csc, sinc):
            expr = func(x + k*pi/2)
            assert refine(expr, Q.odd(k)) == expr


def test_infinite_argument_bounds():
    for func in (sin, cos):
        assert refine(func(x), Q.infinite(x) & Q.extended_real(x)) == AccumBounds(-1, 1)
    assert refine(sin(x), Q.infinite(x)) == sin(x)


def test_registration_and_return_types():
    for key in ("sin", "cos", "tan", "cot", "sec", "csc", "sinc"):
        assert handlers_dict[key].__module__ == trig.__name__
    assert trig.refine_sin(sin(x), Q.real(x)) is None
    assert trig.refine_cos(cos(k*pi), Q.even(k)) is S.One
    assert trig.refine_sin(sin(x), Q.zero(x)) is S.Zero


def test_sinc_odd_literal_half_pi_shift_regression():
    # sin(pi/2) evaluates to 1 on construction; the handler used to index
    # its (empty) args and raise IndexError.
    assert refine(sinc(x + pi/2), Q.zero(x)) == 2/pi
    assert refine(sinc(x + 3*pi/2), Q.zero(x)) == -2/(3*pi)
    assert trig.refine_sinc(sinc(pi/2, evaluate=False), True) == 2/pi
    assert trig.refine_sinc(sinc(-5*pi/2, evaluate=False), True) == 2/(5*pi)
