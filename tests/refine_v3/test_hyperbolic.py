"""Tests for ``satrefine.handlers_v3.hyperbolic``.

Each rule gets a symbolic test (``refine`` with assumptions on ``k``) and a
numeric soundness check, with ``x`` sampled at real and complex points and
``k`` at integers of both parities.  Literal shifts (which SymPy already
evaluates on construction) are checked by calling the handlers directly on
unevaluated expressions.
"""
from __future__ import annotations

import pytest
from sympy import (
    Add, I, Mul, N, Q, Rational, S, Symbol, cosh, coth, csch, pi, sech, sinh,
    symbols, tanh, zoo)

from satrefine import refine
from satrefine._upstream import handlers_dict
from satrefine.testing.harness import assert_refinement_valid
from satrefine.handlers_v3 import hyperbolic

x, k, n = symbols("x k n")
y = Symbol("y", real=True)

FUNCS = [sinh, cosh, tanh, coth, sech, csch]
HANDLERS = {f: handlers_dict[f.__name__] for f in FUNCS}

X_SAMPLES = [Rational(1, 3), Rational(-7, 5), 2, I / 3, 1 + 2 * I / 3,
             Rational(-1, 2) + Rational(5, 4) * I]
EVEN_K = [0, 2, 4, -2, -4, 6]
ODD_K = [1, 3, -1, -3, 5, -5]
MOD1_K = [1, 5, -3, -7]
MOD3_K = [3, 7, -1, -5]
INT_K = EVEN_K + ODD_K

# Expected shift results by class (x the free part).
PERIOD_EVEN = {sinh: sinh(x), cosh: cosh(x), tanh: tanh(x),
               coth: coth(x), sech: sech(x), csch: csch(x)}
PERIOD_ODD = {sinh: -sinh(x), cosh: -cosh(x), tanh: tanh(x),
              coth: coth(x), sech: -sech(x), csch: -csch(x)}
HALF_1 = {sinh: I * cosh(x), cosh: I * sinh(x), tanh: coth(x),
          coth: tanh(x), sech: -I * csch(x), csch: -I * sech(x)}
HALF_3 = {sinh: -I * cosh(x), cosh: -I * sinh(x), tanh: coth(x),
          coth: tanh(x), sech: I * csch(x), csch: I * sech(x)}


def _close(a, b):
    a, b = N(a, 30), N(b, 30)
    if a.has(zoo) or b.has(zoo):
        return a == b
    return abs(complex(a - b)) < 1e-20 * max(1, abs(complex(b)))


def _check(expr, assumptions, expected, kvals, kvar=k):
    refined = refine(expr, assumptions)
    assert refined == expected, (expr, assumptions, refined)
    assert_refinement_valid(expr, assumptions, refined, samples=40,
                            values={kvar: kvals, x: X_SAMPLES})


# ---------------------------------------------------------------- period ---

@pytest.mark.parametrize("f", FUNCS)
def test_period_even(f):
    _check(f(x + k * pi * I), Q.even(k), PERIOD_EVEN[f], EVEN_K)


@pytest.mark.parametrize("f", FUNCS)
def test_period_odd(f):
    _check(f(x + k * pi * I), Q.odd(k), PERIOD_ODD[f], ODD_K)


@pytest.mark.parametrize("f", FUNCS)
def test_period_twice_integer_is_even(f):
    _check(f(x + 2 * n * pi * I), Q.integer(n), PERIOD_EVEN[f], INT_K, n)


@pytest.mark.parametrize("f", [tanh, coth])
def test_period_integer_tanh_coth(f):
    _check(f(x + k * pi * I), Q.integer(k), f(x), INT_K)


@pytest.mark.parametrize("f", [sinh, cosh, sech, csch])
def test_period_integer_sign_unknown_unchanged(f):
    expr = f(x + k * pi * I)
    assert refine(expr, Q.integer(k)) == expr


@pytest.mark.parametrize("f", FUNCS)
@pytest.mark.parametrize("kv", [1, 2, 3, 4, -1, -3])
def test_period_literal(f, kv):
    arg = Add(x, Mul(kv, pi, I, evaluate=False), evaluate=False)
    expr = f(arg, evaluate=False)
    out = HANDLERS[f](expr, True)
    table = PERIOD_EVEN if kv % 2 == 0 else PERIOD_ODD
    assert out == table[f]
    for xv in X_SAMPLES:
        assert _close(f(xv + kv * pi * I), out.subs(x, xv))


# ----------------------------------------------------------- half period ---

@pytest.mark.parametrize("f", FUNCS)
def test_half_period_1_mod_4(f):
    _check(f(x + k * pi * I / 2), Q.odd(k) & Q.even((k - 1) / 2),
           HALF_1[f], MOD1_K)


@pytest.mark.parametrize("f", FUNCS)
def test_half_period_3_mod_4(f):
    _check(f(x + k * pi * I / 2), Q.odd(k) & Q.odd((k - 1) / 2),
           HALF_3[f], MOD3_K)


@pytest.mark.parametrize("f", FUNCS)
def test_half_period_4n_plus_1(f):
    _check(f(x + (4 * n + 1) * pi * I / 2), Q.integer(n), HALF_1[f],
           [0, 1, -1, 2], n)


@pytest.mark.parametrize("f", FUNCS)
def test_half_period_4n_plus_3(f):
    _check(f(x + (4 * n + 3) * pi * I / 2), Q.integer(n), HALF_3[f],
           [0, 1, -1, 2], n)


@pytest.mark.parametrize("f", FUNCS)
def test_half_period_split_terms(f):
    # x + n*pi*I + pi*I/2: SymPy peels off pi*I/2 itself on construction
    # (sech -> -I/sinh(...)), and the inner n*pi*I shift is then refined.
    for assumptions, kvals in ((Q.even(n), EVEN_K), (Q.odd(n), ODD_K)):
        expr = f(x + n * pi * I + pi * I / 2)
        refined = refine(expr, assumptions)
        assert not refined.has(n), refined
        assert_refinement_valid(expr, assumptions, refined, samples=40,
                                values={n: kvals, x: X_SAMPLES})


@pytest.mark.parametrize("f", [tanh, coth])
def test_half_period_odd_only_tanh_coth(f):
    _check(f(x + k * pi * I / 2), Q.odd(k), HALF_1[f], ODD_K)


@pytest.mark.parametrize("f", [sinh, cosh, sech, csch])
def test_half_period_odd_only_sign_unknown_unchanged(f):
    expr = f(x + k * pi * I / 2)
    assert refine(expr, Q.odd(k)) == expr


@pytest.mark.parametrize("f", FUNCS)
@pytest.mark.parametrize("kv", [1, 3, -1, -3, 5, 7])
def test_half_period_literal(f, kv):
    arg = Add(x, Mul(Rational(kv, 2), pi, I, evaluate=False), evaluate=False)
    expr = f(arg, evaluate=False)
    out = HANDLERS[f](expr, True)
    assert out == (HALF_1 if kv % 4 == 1 else HALF_3)[f]
    for xv in X_SAMPLES:
        assert _close(f(xv + kv * pi * I / 2), out.subs(x, xv))


def test_real_free_part_also_works():
    assert refine(sinh(y + k * pi * I), Q.odd(k)) == -sinh(y)
    assert refine(cosh(y + k * pi * I / 2), Q.odd(k) & Q.odd((k - 1) / 2)) \
        == -I * sinh(y)


# ----------------------------------------------------------- exact points ---

def _at(f, m, assumptions):
    """Handler on the unevaluated ``f(m*pi*I/2)``."""
    expr = f(Mul(S(m) / 2, pi, I, evaluate=False), evaluate=False)
    return HANDLERS[f](expr, assumptions)


def _check_point(f, m, assumptions, expected, kvals):
    out = _at(f, m, assumptions)
    assert out == expected, (f, m, assumptions, out)
    for kv in kvals:
        assert _close(f((m * pi * I / 2).subs(k, kv)), S(out).subs(k, kv)), (f, kv)


@pytest.mark.parametrize("f,even,odd", [
    (sinh, 0, 0), (cosh, 1, -1), (tanh, 0, 0),
    (coth, zoo, zoo), (sech, 1, -1), (csch, zoo, zoo)])
def test_values_at_multiples_of_pi_i(f, even, odd):
    _check_point(f, 2 * k, Q.even(k), S(even), EVEN_K)
    _check_point(f, 2 * k, Q.odd(k), S(odd), ODD_K)


@pytest.mark.parametrize("f,expected", [
    (sinh, S.Zero), (cosh, (-1) ** k), (tanh, S.Zero), (coth, zoo),
    (sech, (-1) ** k), (csch, zoo)])
def test_values_at_integer_multiples_of_pi_i(f, expected):
    _check_point(f, 2 * k, Q.integer(k), expected, INT_K)


@pytest.mark.parametrize("f,v1,v3", [
    (sinh, I, -I), (cosh, 0, 0), (tanh, zoo, zoo), (coth, 0, 0),
    (sech, zoo, zoo), (csch, -I, I)])
def test_values_at_odd_multiples_of_half_pi_i(f, v1, v3):
    _check_point(f, k, Q.odd(k) & Q.even((k - 1) / 2), S(v1), MOD1_K)
    _check_point(f, k, Q.odd(k) & Q.odd((k - 1) / 2), S(v3), MOD3_K)


@pytest.mark.parametrize("f,expected", [
    (cosh, S.Zero), (tanh, zoo), (coth, S.Zero), (sech, zoo)])
def test_values_at_odd_only(f, expected):
    _check_point(f, k, Q.odd(k), expected, ODD_K)


@pytest.mark.parametrize("f", [sinh, csch])
def test_values_at_odd_only_sign_unknown(f):
    assert _at(f, k, Q.odd(k)) is None


@pytest.mark.parametrize("f", FUNCS)
@pytest.mark.parametrize("m", [1, 2, 3, 4, -1, -3, 6])
def test_values_literal(f, m):
    out = _at(f, S(m), True)
    assert out is not None
    assert _close(f(m * pi * I / 2), out)


@pytest.mark.parametrize("f", FUNCS)
def test_no_pole_off_the_point(f):
    for assumptions, m in [(Q.even(k), 2 * k), (Q.odd(k), 2 * k),
                           (Q.integer(k), 2 * k), (Q.odd(k), k)]:
        refined = refine(f(x + m * pi * I / 2), assumptions)
        assert not refined.has(zoo)


# -------------------------------------------------------------- negative ---

@pytest.mark.parametrize("f", FUNCS)
def test_half_period_needs_odd(f):
    expr = f(x + k * pi * I / 2)
    assert refine(expr, Q.integer(k)) == expr
    assert HANDLERS[f](expr, Q.integer(k)) is None


@pytest.mark.parametrize("f", FUNCS)
@pytest.mark.parametrize("assumptions", [
    Q.even(k), Q.odd(k), Q.integer(k), Q.odd(k) & Q.even((k - 1) / 2)])
def test_real_pi_never_fires(f, assumptions):
    for arg in (x + k * pi, x + k * pi / 2, y + k * pi):
        expr = f(arg)
        assert HANDLERS[f](expr, assumptions) is None
        assert refine(expr, assumptions) == expr


@pytest.mark.parametrize("f", FUNCS)
def test_no_information_unchanged(f):
    for assumptions in (True, Q.real(k), Q.positive(k), Q.rational(k)):
        expr = f(x + k * pi * I)
        assert refine(expr, assumptions) == expr
        assert HANDLERS[f](expr, assumptions) is None


@pytest.mark.parametrize("f", FUNCS)
def test_no_shift_unchanged(f):
    assert HANDLERS[f](f(x), Q.real(x)) is None
    assert HANDLERS[f](f(x + y), Q.integer(y)) is None


@pytest.mark.parametrize("f", FUNCS)
def test_non_integer_multiple_unchanged(f):
    expr = f(x + k * pi * I / 3)
    assert refine(expr, Q.odd(k)) == expr
    expr = f(x + Rational(1, 3) * pi * I)
    assert HANDLERS[f](expr, True) is None


def test_registered_keys():
    for f in FUNCS:
        assert handlers_dict[f.__name__] is getattr(
            hyperbolic, "refine_" + f.__name__)
