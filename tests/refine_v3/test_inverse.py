"""Tests for ``satrefine.handlers_v3.inverse``.

Every rule gets a positive refine test, a numeric soundness check on the
real samples that satisfy its precondition (interval endpoints, 0 and the
neighbourhood of the poles included), a complex sample showing why a
weaker precondition would be wrong, and a negative test where a tempting
rule must not fire.

Relation assumptions (``Q.ge`` and friends) are given explicit real
``values=`` for the harness, since SymPy raises ``TypeError`` on
``Q.ge(I, ...)`` while the harness screens the default complex samples.
"""
from __future__ import annotations

import itertools

import pytest
from sympy import (
    AccumBounds, Abs, Basic, Float, Ge, I, Le, N, Rational, S, Symbol, acos,
    acosh, acoth, acsch, asech, asin,
    asinh, atan, atan2, atanh, cos, cosh, cot, coth, csch, nan, pi, sech,
    oo, sign, sin, sinh, sqrt, symbols, tan, tanh, zoo,
)
from sympy.assumptions import Q

from satrefine import _upstream, refine
from satrefine.handlers_v3 import inverse
from satrefine.testing.harness import assert_refinement_valid, use_ask

x, y, t = symbols('x y t')

# real sample points, with the interval endpoints and 0 included
HALF = [-pi/2, -1, -Rational(1, 2), 0, Rational(1, 2), 1, pi/2]
HALF_OPEN = [-pi/2 + Rational(1, 1000), -1, 0, Rational(1, 2), 1, pi/2 - Rational(1, 1000)]
UNIT = [0, Rational(1, 2), 1, 2, pi/2, 3, pi]
REALS = [-3, -pi, -1, -Rational(1, 2), 0, Rational(1, 2), 1, pi, 3]
NONZERO_REALS = [-3, -1, -Rational(1, 1000), Rational(1, 1000), Rational(1, 2), 2]
COMPLEX = [1 + 3*I, -2 + I/2, pi/2 + 3*I, 3*I]


def num(expr):
    return complex(N(expr, 30))


def close(a, b, tol=1e-20):
    return abs(num(a) - num(b)) <= tol * max(1.0, abs(num(a)))


def far(a, b):
    return abs(num(a) - num(b)) > 1e-3


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def test_registered_from_this_module():
    for key, handler in [
        ('asin', inverse.refine_asin), ('acos', inverse.refine_acos),
        ('atan', inverse.refine_atan), ('atan2', inverse.refine_atan2),
        ('asinh', inverse.refine_asinh), ('acosh', inverse.refine_acosh),
        ('atanh', inverse.refine_atanh), ('acoth', inverse.refine_acoth),
        ('asech', inverse.refine_asech), ('acsch', inverse.refine_acsch),
    ]:
        assert _upstream.handlers_dict[key] is handler


def test_handlers_return_none_when_nothing_applies():
    for expr in [asin(x), acos(x), atan(x), atan2(y, x), asinh(x), acosh(x),
                 atanh(x), acoth(x), asech(x), acsch(x),
                 asin(sin(x)), atan(tan(x)), acoth(coth(x))]:
        handler = _upstream.handlers_dict[expr.__class__.__name__]
        assert handler(expr, Q.real(x) & Q.real(y)) is None


def test_ask_exceptions_from_relations_are_swallowed():
    # bounds through y are not stated numerically on x, so the handler must
    # ask; the stubs then raise the way SymPy's ask can
    relations = (Q.ge, Q.gt, Q.le, Q.lt)
    bounds = Q.ge(x, y) & Q.le(x, y) & Q.zero(y)
    seen = []

    def raising_ask(prop, assumptions=True):
        if prop.function in relations:
            seen.append(prop)
            raise ValueError("inconsistent assumptions")
        return None

    def type_error_ask(prop, assumptions=True):
        if prop.function in relations:
            seen.append(prop)
            raise TypeError("Invalid comparison of non-real")
        return None

    for fake in (raising_ask, type_error_ask):
        seen.clear()
        with use_ask(fake):
            assert inverse.refine_asin(asin(sin(x)), bounds) is None
            assert inverse.refine_acos(acos(cos(x)), bounds) is None
            assert inverse.refine_atan(atan(tan(x)), bounds) is None
            assert refine(asin(sin(x)), bounds) == asin(sin(x))
        assert seen  # the relation really was asked


# ---------------------------------------------------------------------------
# asin
# ---------------------------------------------------------------------------

def test_asin_sin_principal_interval():
    a = Q.ge(x, -pi/2) & Q.le(x, pi/2)
    assert refine(asin(sin(x)), a) == x
    assert_refinement_valid(asin(sin(x)), a, x, values={x: HALF})
    for v in HALF:
        assert asin(sin(v)) == v or close(asin(sin(v)), v)


def test_asin_sin_lower_bound_from_sign_fact():
    assert refine(asin(sin(x)), Q.nonnegative(x) & Q.le(x, pi/2)) == x
    assert refine(asin(sin(x)), Q.positive(x) & Q.le(x, pi/2)) == x
    assert refine(asin(sin(x)), Q.nonpositive(x) & Q.ge(x, -pi/2)) == x
    # sin(x) is already 0 under Q.zero(x) before asin sees it; both answers are x
    assert refine(asin(sin(x)), Q.zero(x)) in (x, S.Zero)
    assert inverse.refine_asin(asin(sin(x)), Q.zero(x)) == x


def test_asin_sin_shifted_intervals():
    a = Q.ge(x, pi/2) & Q.le(x, 3*pi/2)
    assert refine(asin(sin(x)), a) == pi - x
    assert_refinement_valid(asin(sin(x)), a, pi - x, values={x: [pi/2, 2, pi, 4, 3*pi/2]})
    b = Q.ge(x, -3*pi/2) & Q.le(x, -pi/2)
    assert refine(asin(sin(x)), b) == -pi - x
    assert_refinement_valid(asin(sin(x)), b, -pi - x, values={x: [-3*pi/2, -4, -pi, -2, -pi/2]})


def test_asin_cos():
    a = Q.ge(x, 0) & Q.le(x, pi)
    assert refine(asin(cos(x)), a) == pi/2 - x
    assert_refinement_valid(asin(cos(x)), a, pi/2 - x, values={x: UNIT})
    assert refine(asin(cos(x)), Q.nonnegative(x) & Q.le(x, pi)) == pi/2 - x


def test_asin_sin_needs_the_real_interval():
    # the boundary of the complex strip breaks the identity
    assert far(asin(sin(pi/2 + 3*I)), pi/2 + 3*I)
    # a point outside the interval breaks it too
    assert far(asin(sin(S(2))), 2)
    for a in [Q.real(x), Q.positive(x), Q.ge(x, -pi/2), Q.le(x, pi/2),
              Q.ge(x, -pi/2) & Q.le(x, pi), Q.gt(x, -pi) & Q.lt(x, pi), Q.integer(x)]:
        assert refine(asin(sin(x)), a) == asin(sin(x))
    assert refine(asin(cos(x)), Q.ge(x, -pi/2) & Q.le(x, pi/2)) == asin(cos(x))
    assert refine(asin(cos(x)), Q.real(x)) == asin(cos(x))


def test_asin_plain_argument_untouched():
    a = Q.real(x) & Q.ge(x, -1) & Q.le(x, 1)
    assert refine(asin(x), a) == asin(x)
    assert refine(asin(x), Q.positive(x)) == asin(x)
    assert refine(asin(-x), Q.positive(x)) == -asin(x)  # SymPy's own symmetry


# ---------------------------------------------------------------------------
# acos
# ---------------------------------------------------------------------------

def test_acos_cos_principal_interval():
    a = Q.ge(x, 0) & Q.le(x, pi)
    assert refine(acos(cos(x)), a) == x
    assert_refinement_valid(acos(cos(x)), a, x, values={x: UNIT})
    assert refine(acos(cos(x)), Q.nonnegative(x) & Q.le(x, pi)) == x
    assert refine(acos(cos(x)), Q.zero(x)) in (x, S.Zero)
    assert inverse.refine_acos(acos(cos(x)), Q.zero(x)) == x


def test_acos_cos_reflected_intervals():
    a = Q.ge(x, -pi) & Q.le(x, 0)
    assert refine(acos(cos(x)), a) == -x
    assert_refinement_valid(acos(cos(x)), a, -x, values={x: [-pi, -3, -pi/2, -1, 0]})
    assert refine(acos(cos(x)), Q.nonpositive(x) & Q.ge(x, -pi)) == -x
    b = Q.ge(x, pi) & Q.le(x, 2*pi)
    assert refine(acos(cos(x)), b) == 2*pi - x
    assert_refinement_valid(acos(cos(x)), b, 2*pi - x, values={x: [pi, 4, 3*pi/2, 6, 2*pi]})


def test_acos_sin():
    a = Q.ge(x, -pi/2) & Q.le(x, pi/2)
    assert refine(acos(sin(x)), a) == pi/2 - x
    assert_refinement_valid(acos(sin(x)), a, pi/2 - x, values={x: HALF})


def test_acos_cos_needs_the_real_interval():
    assert far(acos(cos(-2 + I/2)), -2 + I/2)
    assert far(acos(cos(S(-1))), -1)
    for a in [Q.real(x), Q.positive(x), Q.nonnegative(x), Q.ge(x, 0),
              Q.ge(x, -pi/2) & Q.le(x, pi/2), Q.ge(x, 0) & Q.le(x, 2*pi)]:
        assert refine(acos(cos(x)), a) == acos(cos(x))
    assert refine(acos(sin(x)), Q.ge(x, 0) & Q.le(x, pi)) == acos(sin(x))
    assert refine(acos(x), Q.real(x) & Q.ge(x, -1) & Q.le(x, 1)) == acos(x)


# ---------------------------------------------------------------------------
# atan
# ---------------------------------------------------------------------------

def test_atan_tan_open_interval():
    a = Q.gt(x, -pi/2) & Q.lt(x, pi/2)
    assert refine(atan(tan(x)), a) == x
    assert_refinement_valid(atan(tan(x)), a, x, values={x: HALF_OPEN})
    for v in HALF_OPEN:
        assert close(atan(tan(v)), v)


def test_atan_tan_bounds_from_sign_facts():
    assert refine(atan(tan(x)), Q.positive(x) & Q.lt(x, pi/2)) == x
    assert refine(atan(tan(x)), Q.nonnegative(x) & Q.lt(x, pi/2)) == x
    assert refine(atan(tan(x)), Q.negative(x) & Q.gt(x, -pi/2)) == x
    assert refine(atan(tan(x)), Q.nonpositive(x) & Q.gt(x, -pi/2)) == x
    assert refine(atan(tan(x)), Q.zero(x)) in (x, S.Zero)
    assert inverse.refine_atan(atan(tan(x)), Q.zero(x)) == x


def test_atan_tan_shifted_intervals():
    a = Q.gt(x, pi/2) & Q.lt(x, 3*pi/2)
    assert refine(atan(tan(x)), a) == x - pi
    assert_refinement_valid(atan(tan(x)), a, x - pi, values={x: [2, 3, pi, 4, Rational(47, 10)]})
    b = Q.gt(x, -3*pi/2) & Q.lt(x, -pi/2)
    assert refine(atan(tan(x)), b) == x + pi
    assert_refinement_valid(atan(tan(x)), b, x + pi, values={x: [-2, -3, -pi, -4, -Rational(47, 10)]})


def test_atan_cot():
    a = Q.gt(x, 0) & Q.lt(x, pi)
    assert refine(atan(cot(x)), a) == pi/2 - x
    assert_refinement_valid(atan(cot(x)), a, pi/2 - x, values={x: [Rational(1, 1000), 1, pi/2, 2, pi - Rational(1, 1000)]})
    assert refine(atan(cot(x)), Q.positive(x) & Q.lt(x, pi)) == pi/2 - x


def test_atan_tan_poles_and_closed_interval_do_not_fire():
    # tan has poles at +-pi/2; SymPy leaves atan(zoo) alone, so the closed
    # interval must not be accepted
    assert tan(pi/2) is zoo
    assert atan(tan(pi/2)) != pi/2
    for a in [Q.ge(x, -pi/2) & Q.le(x, pi/2), Q.ge(x, -pi/2) & Q.lt(x, pi/2),
              Q.gt(x, -pi/2) & Q.le(x, pi/2), Q.real(x), Q.positive(x),
              Q.nonnegative(x) & Q.le(x, pi/2), Q.gt(x, -pi/2) & Q.lt(x, pi)]:
        assert refine(atan(tan(x)), a) == atan(tan(x))
    assert refine(atan(cot(x)), Q.ge(x, 0) & Q.le(x, pi)) == atan(cot(x))
    assert far(atan(tan(-2 + I/2)), -2 + I/2)
    assert far(atan(tan(S(2))), 2)
    assert refine(atan(x), Q.real(x)) == atan(x)


# ---------------------------------------------------------------------------
# atan2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("assumptions, expected", [
    (Q.real(y) & Q.positive(x), atan(y/x)),
    (Q.zero(y) & Q.positive(x), S.Zero),
    (Q.negative(y) & Q.negative(x), atan(y/x) - pi),
    (Q.positive(y) & Q.negative(x), atan(y/x) + pi),
    (Q.nonnegative(y) & Q.negative(x), atan(y/x) + pi),
    (Q.zero(y) & Q.negative(x), pi),
    (Q.positive(y) & Q.zero(x), pi/2),
    (Q.negative(y) & Q.zero(x), -pi/2),
    (Q.nonzero(y) & Q.zero(x), sign(y)*pi/2),
    (Q.zero(y) & Q.zero(x), nan),
])
def test_atan2_by_signs(assumptions, expected):
    assert refine(atan2(y, x), assumptions) == expected
    assert_refinement_valid(atan2(y, x), assumptions, expected,
                            values={x: [-3, -1, -Rational(1, 2), 0, Rational(1, 2), 1, 3],
                                    y: [-3, -1, -Rational(1, 2), 0, Rational(1, 2), 1, 3]})


def test_atan2_numeric_edges():
    assert atan2(0, -1) == pi and atan2(0, 1) == 0
    assert atan2(1, 0) == pi/2 and atan2(-1, 0) == -pi/2
    assert atan2(0, 0) is nan
    # the y = 0 endpoint of the nonnegative rule
    assert (atan(y/x) + pi).subs({y: 0, x: -2}) == pi == atan2(0, -2)
    # the endpoint that makes the nonpositive rule wrong
    assert (atan(y/x) - pi).subs({y: 0, x: -2}) == -pi != atan2(0, -2)


def test_atan2_negative_cases():
    for a in [Q.nonpositive(y) & Q.negative(x), Q.positive(x), Q.real(y) & Q.real(x),
              Q.real(y) & Q.nonnegative(x), Q.real(y) & Q.negative(x), Q.zero(x) & Q.real(y),
              Q.positive(y) & Q.real(x), Q.real(y) & Q.nonzero(x), Q.positive(x) & Q.imaginary(y)]:
        assert refine(atan2(y, x), a) == atan2(y, x)


def test_atan2_vendored_cases_agree():
    for a in [Q.real(y) & Q.positive(x), Q.negative(y) & Q.negative(x),
              Q.positive(y) & Q.negative(x), Q.zero(y) & Q.negative(x),
              Q.positive(y) & Q.zero(x), Q.negative(y) & Q.zero(x), Q.zero(y) & Q.zero(x)]:
        assert refine(atan2(y, x), a) == _upstream.refine_atan2(atan2(y, x), a)


# ---------------------------------------------------------------------------
# asinh, atanh
# ---------------------------------------------------------------------------

def test_asinh_sinh_real():
    assert refine(asinh(sinh(x)), Q.real(x)) == x
    assert refine(asinh(sinh(x)), Q.positive(x)) == x
    assert refine(asinh(sinh(x)), Q.integer(x)) == x
    assert_refinement_valid(asinh(sinh(x)), Q.real(x), x, values={x: REALS})
    assert refine(asinh(sinh(x + 1)), Q.real(x)) == x + 1


def test_asinh_sinh_not_off_the_real_line():
    assert far(asinh(sinh(1 + 3*I)), 1 + 3*I)
    assert far(asinh(sinh(3*I)), 3*I)
    for a in [True, Q.complex(x), Q.imaginary(x), Q.finite(x)]:
        assert refine(asinh(sinh(x)), a) == asinh(sinh(x))
    assert refine(asinh(x), Q.real(x)) == asinh(x)


def test_atanh_tanh_real():
    assert refine(atanh(tanh(x)), Q.real(x)) == x
    assert refine(atanh(tanh(x)), Q.negative(x)) == x
    assert_refinement_valid(atanh(tanh(x)), Q.real(x), x, values={x: REALS})
    for v in [-3, 0, Rational(1, 2), 3]:
        assert close(atanh(tanh(S(v))), v)


def test_atanh_tanh_not_off_the_real_line():
    assert far(atanh(tanh(1 + 3*I)), 1 + 3*I)
    for a in [True, Q.complex(x), Q.imaginary(x)]:
        assert refine(atanh(tanh(x)), a) == atanh(tanh(x))
    assert refine(atanh(x), Q.real(x) & Q.gt(x, -1) & Q.lt(x, 1)) == atanh(x)


# ---------------------------------------------------------------------------
# acosh, asech (even forward functions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inv, fwd", [(acosh, cosh), (asech, sech)])
def test_even_inverse_by_sign(inv, fwd):
    e = inv(fwd(x))
    assert refine(e, Q.nonnegative(x)) == x
    assert refine(e, Q.positive(x)) == x
    assert refine(e, Q.zero(x)) == x
    assert refine(e, Q.nonpositive(x)) == -x
    assert refine(e, Q.negative(x)) == -x
    assert refine(e, Q.real(x)) == Abs(x)
    assert_refinement_valid(e, Q.nonnegative(x), x, values={x: [0, Rational(1, 2), 1, 3, 10]})
    assert_refinement_valid(e, Q.nonpositive(x), -x, values={x: [-10, -3, -1, -Rational(1, 2), 0]})
    assert_refinement_valid(e, Q.real(x), Abs(x), values={x: REALS})
    for v in [-3, -Rational(1, 2), 0, Rational(1, 2), 3]:
        assert close(e.subs(x, v), Abs(S(v)))


@pytest.mark.parametrize("inv, fwd", [(acosh, cosh), (asech, sech)])
def test_even_inverse_negative_cases(inv, fwd):
    e = inv(fwd(x))
    # cosh is even, so x itself is wrong for negative x
    assert far(e.subs(x, -2), -2)
    assert far(e.subs(x, -2 + I/2), -2 + I/2)
    assert far(e.subs(x, 1 + 3*I), -(1 + 3*I))  # and not simply -x either
    for a in [True, Q.complex(x), Q.imaginary(x)]:
        assert refine(e, a) == e
    assert refine(e, Q.real(x)) != x
    assert refine(inv(x), Q.positive(x)) == inv(x)


# ---------------------------------------------------------------------------
# acoth, acsch (odd forward functions with a pole at 0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("inv, fwd", [(acoth, coth), (acsch, csch)])
def test_odd_inverse_real_nonzero(inv, fwd):
    e = inv(fwd(x))
    assert refine(e, Q.nonzero(x)) == x
    assert refine(e, Q.positive(x)) == x
    assert refine(e, Q.negative(x)) == x
    assert refine(e, Q.real(x) & Q.nonzero(x)) == x
    assert_refinement_valid(e, Q.nonzero(x), x, values={x: NONZERO_REALS})
    for v in NONZERO_REALS:
        assert close(e.subs(x, v), v)


@pytest.mark.parametrize("inv, fwd", [(acoth, coth), (acsch, csch)])
def test_odd_inverse_pole_and_complex(inv, fwd):
    e = inv(fwd(x))
    # the pole: only the zoo convention rescues x = 0, so the rule is not
    # claimed there
    assert fwd(0) is zoo
    assert e.subs(x, 0) == 0
    assert far(e.subs(x, 1 + 3*I), 1 + 3*I)
    for a in [True, Q.real(x), Q.complex(x), Q.imaginary(x), Q.nonnegative(x), Q.nonpositive(x)]:
        assert refine(e, a) == e
    assert refine(inv(x), Q.positive(x)) == inv(x)


# ---------------------------------------------------------------------------
# composition through the dispatcher
# ---------------------------------------------------------------------------

def test_results_are_re_refined():
    # acosh(cosh(x)) -> Abs(x) -> x under a sign fact reached via Abs
    assert refine(acosh(cosh(x)) + asinh(sinh(x)), Q.positive(x)) == 2*x
    assert refine(sqrt(asin(sin(x))**2), Q.nonnegative(x) & Q.le(x, pi/2)) == x
    assert refine(asin(sin(I*x)), Q.real(x)) == I*x  # SymPy routes this through asinh


# ---------------------------------------------------------------------------
# bounds read from stated relations
# ---------------------------------------------------------------------------

def test_bounds_implied_by_stated_relations():
    # a tighter stated interval implies the principal one (SymPy's LRA cannot
    # do this itself because it treats pi as a symbol)
    a = Q.ge(x, 0) & Q.le(x, 1)
    assert refine(asin(sin(x)), a) == x
    assert_refinement_valid(asin(sin(x)), a, x, values={x: [0, Rational(1, 2), 1]})
    assert refine(atan(tan(x)), Q.gt(x, -1) & Q.lt(x, 1)) == x
    assert refine(atan(tan(x)), Q.ge(x, -1) & Q.le(x, 1)) == x
    assert refine(acos(cos(x)), Q.gt(x, Rational(1, 2)) & Q.lt(x, 3)) == x
    # relations written the other way round
    assert refine(asin(sin(x)), Q.le(-pi/2, x) & Q.ge(pi/2, x)) == x
    assert refine(atan(tan(x)), Q.lt(-pi/2, x) & Q.gt(pi/2, x)) == x


def test_stated_relations_that_must_not_fire():
    # Q.ge(-pi/2, x) means x <= -pi/2
    assert refine(asin(sin(x)), Q.ge(-pi/2, x) & Q.le(x, pi/2)) == asin(sin(x))
    # a closed lower bound does not give the open interval atan needs
    assert refine(atan(tan(x)), Q.ge(x, -pi/2) & Q.lt(x, 1)) == atan(tan(x))
    assert refine(atan(tan(x)), Q.gt(x, -1) & Q.le(x, pi/2)) == atan(tan(x))
    # relations under Or / Not are not conjuncts
    assert refine(asin(sin(x)), Q.ge(x, -pi/2) | Q.le(x, pi/2)) == asin(sin(x))
    # a symbolic bound is not a numeric one, and Not is not a conjunct
    assert inverse._conjunct_bounds(x, Q.ge(x, y)) == []
    assert inverse._conjunct_bounds(x, ~Q.ge(x, -pi/2) & Q.le(x, pi/2)) == [('le', pi/2)]
    assert inverse._conjunct_bounds(x, Q.ge(-pi/2, x)) == [('le', -pi/2)]
    assert inverse._conjunct_bounds(x, True) == []


# ---------------------------------------------------------------------------
# adversarial regressions: endpoints, floats, spans, weaker facts
# ---------------------------------------------------------------------------

def test_float_endpoints_are_compared_by_exact_value():
    # the double just below pi/2 is a valid upper bound, the one just above
    # is not; Float arithmetic against pi must not round either to "equal"
    below, above = Float('1.5707963267948966'), Float('1.5707963267948967')
    assert Rational(below) < pi/2 < Rational(above)
    assert refine(asin(sin(x)), Q.ge(x, -pi/2) & Q.le(x, below)) == x
    assert refine(atan(tan(x)), Q.gt(x, -pi/2) & Q.le(x, below)) == x
    assert refine(asin(sin(x)), Q.ge(x, -pi/2) & Q.le(x, above)) == asin(sin(x))
    # low-precision floats: 4.712 (4 digits) is below 3*pi/2, 1.571 is above pi/2
    assert refine(asin(sin(x)), Q.ge(x, pi/2) & Q.le(x, Float('4.712', 4))) == pi - x
    assert refine(asin(sin(x)), Q.ge(x, -pi/2) & Q.le(x, Float('1.571', 4))) == asin(sin(x))
    assert inverse._stated_le(x, pi/2, False, Q.le(x, Float('1.571', 4))) is False
    assert inverse._stated_le(x, pi/2, False, Q.le(x, Float('1.570796', 7))) is True


def test_endpoint_strictness_with_reversed_relations():
    # the pole of tan at -pi/2 stays excluded however the bound is written
    assert refine(atan(tan(x)), Q.le(-pi/2, x) & Q.gt(pi/2, x)) == atan(tan(x))
    assert refine(atan(tan(x)), Q.lt(-pi/2, x) & Q.ge(pi/2, x)) == atan(tan(x))
    assert refine(atan(tan(x)), Q.ge(x, pi/2) & Q.lt(x, 3*pi/2)) == atan(tan(x))
    assert refine(atan(cot(x)), Q.gt(x, 0) & Q.ge(pi, x)) == atan(cot(x))
    # the closed endpoints of asin/acos are fine either way round
    assert refine(asin(sin(x)), Q.le(-pi/2, x) & Q.ge(pi*Rational(1, 2), x)) == x
    assert refine(acos(cos(x)), Q.le(pi, x) & Q.ge(2*pi, x)) == 2*pi - x
    assert refine(acos(cos(x)), Q.le(0, x) & Q.gt(pi, x)) == x


def test_bounds_spanning_more_than_one_branch_do_not_fire():
    # no single rewrite is valid across a branch point
    assert asin(sin(S(1))) == 1 and asin(sin(S(2))) == pi - 2
    for a in [Q.ge(x, -pi/2) & Q.le(x, 3*pi/2), Q.ge(x, -3*pi/2) & Q.le(x, pi/2),
              Q.ge(x, 2) & Q.le(x, 5), Q.ge(x, 1) & Q.le(x, 2), Q.ge(x, -oo) & Q.le(x, oo),
              Q.ge(x, 0) & Q.le(x, oo), Q.eq(x, pi/2), Q.eq(x, 2)]:
        assert refine(asin(sin(x)), a) == asin(sin(x))
    for a in [Q.ge(x, -pi) & Q.le(x, pi), Q.ge(x, 0) & Q.le(x, 2*pi), Q.nonnegative(x)]:
        assert refine(acos(cos(x)), a) == acos(cos(x))
    for a in [Q.gt(x, -pi/2) & Q.lt(x, 3*pi/2), Q.positive(x), Q.positive(x) & Q.lt(x, pi),
              Q.negative(x) & Q.gt(x, -pi)]:
        assert refine(atan(tan(x)), a) == atan(tan(x))
    assert refine(acos(sin(x)), Q.nonnegative(x) & Q.le(x, pi)) == acos(sin(x))
    assert refine(asin(cos(x)), Q.ge(x, pi) & Q.le(x, 2*pi)) == asin(cos(x))
    assert refine(atan(cot(x)), Q.gt(x, pi) & Q.lt(x, 2*pi)) == atan(cot(x))


def test_numeric_intervals_select_the_shifted_branch():
    cases = [
        (asin(sin(x)), Q.ge(x, 2) & Q.le(x, 4), pi - x, [2, 3, 4]),
        (asin(sin(x)), Q.ge(x, -4) & Q.le(x, -2), -pi - x, [-4, -3, -2]),
        (acos(cos(x)), Q.ge(x, 4) & Q.le(x, 6), 2*pi - x, [4, 5, 6]),
        (acos(cos(x)), Q.ge(x, -3) & Q.le(x, -1), -x, [-3, -2, -1]),
        (atan(tan(x)), Q.gt(x, 2) & Q.lt(x, 4), x - pi, [Rational(21, 10), 3, Rational(39, 10)]),
        (atan(tan(x)), Q.gt(x, -4) & Q.lt(x, -2), x + pi, [-Rational(39, 10), -3, -Rational(21, 10)]),
        (atan(cot(x)), Q.gt(x, 1) & Q.lt(x, 3), pi/2 - x, [Rational(11, 10), 2, Rational(29, 10)]),
    ]
    for expr, a, expected, values in cases:
        assert refine(expr, a) == expected
        assert_refinement_valid(expr, a, expected, values={x: values})
    # an extra, looser or redundant stated bound never blocks the tight one
    assert refine(asin(sin(x)), Q.ge(x, 0) & Q.ge(x, -5) & Q.le(x, 1) & Q.le(x, 3)) == x


def test_atan2_sign_grid_is_numerically_sound():
    samples = {'positive': [1, 2], 'negative': [-1, -2], 'zero': [0], 'nonnegative': [0, 1, 3],
               'nonpositive': [0, -1, -3], 'nonzero': [-2, -1, 1, 2], 'real': [-2, 0, 2]}
    fired = 0
    for py, px in itertools.product(samples, samples):
        a = getattr(Q, py)(y) & getattr(Q, px)(x)
        r = refine(atan2(y, x), a)
        assert isinstance(r, Basic)
        if r == atan2(y, x):
            continue
        fired += 1
        for vy in samples[py]:
            for vx in samples[px]:
                got, want = r.subs({y: vy, x: vx}), atan2(S(vy), S(vx))
                assert got == want or close(got, want), (a, vy, vx, got, want)
    # the cases the module documents, and nothing on the ambiguous ones
    assert fired == 15
    assert refine(atan2(y, x), Q.nonpositive(y) & Q.negative(x)) == atan2(y, x)
    assert refine(atan2(y, x), Q.nonzero(y) & Q.negative(x)) == atan2(y, x)
    assert refine(atan2(y, x), Q.real(y) & Q.zero(x)) == atan2(y, x)
    assert refine(atan2(y, x), Q.extended_positive(x) & Q.real(y)) == atan2(y, x)
    # numeric first arguments and second arguments
    assert refine(atan2(y, -1), Q.nonnegative(y)) == pi - atan(y)
    assert refine(atan2(y, -1), Q.negative(y)) == -atan(y) - pi
    assert refine(atan2(1, x), Q.zero(x)) == pi/2


def test_hyperbolic_inverses_with_weaker_complex_facts():
    # Q.nonzero implies real; Q.imaginary and the extended predicates do not
    for inv, fwd in [(acoth, coth), (acsch, csch)]:
        e = inv(fwd(x))
        assert far(e.subs(x, 2*I), 2*I)
        assert refine(e, Q.nonzero(x) & Q.complex(x)) == x
        assert refine(e, Q.integer(x) & Q.nonzero(x)) == x
        for a in [Q.imaginary(x) & Q.nonzero(x), Q.extended_positive(x), Q.ge(x, 1), Q.gt(x, 0)]:
            assert refine(e, a) == e
    for inv, fwd in [(acosh, cosh), (asech, sech)]:
        e = inv(fwd(x))
        assert refine(e, Q.rational(x)) == Abs(x)
        assert refine(e, Q.real(x) & Q.nonzero(x)) == Abs(x)
        for a in [Q.extended_nonnegative(x), Q.imaginary(x), Q.ge(x, 0), Q.gt(x, -1)]:
            assert refine(e, a) == e
    for inv, fwd in [(asinh, sinh), (atanh, tanh)]:
        e = inv(fwd(x))
        for a in [Q.extended_real(x), Q.ge(x, 0), Q.gt(x, y) & Q.real(y)]:
            assert refine(e, a) == e


def test_results_are_sympy_objects_and_terminate():
    a = Q.ge(x, 0) & Q.le(x, pi/2)
    for expr, assumptions, expected in [
        (asin(sin(asin(sin(x)))), a, x),
        (asin(sin(acos(cos(x)))), a, asin(sqrt(1 - cos(x)**2))),  # SymPy's own asin(sin(acos)) form
        (asin(sin(x)) + acos(cos(x)), a, 2*x),
        (asin(sin(x**2)), Q.ge(x**2, 0) & Q.le(x**2, pi/2), x**2),
        (asin(sin(Abs(x))), Q.ge(Abs(x), 0) & Q.le(Abs(x), pi/2), Abs(x)),
    ]:
        r = refine(expr, assumptions)
        assert isinstance(r, Basic)
        assert r == expected, (expr, r)
    assert refine(acosh(cosh(acosh(cosh(x)))), Q.real(x)) == Abs(x)
    assert refine(atan(tan(atan(tan(x)))), Q.gt(x, 0) & Q.lt(x, pi/2)) == x
    # atan2's result contains atan of a quotient, which is not a tan
    assert refine(atan2(x*tan(t), x), Q.positive(x) & Q.gt(t, -pi/2) & Q.lt(t, pi/2)) == atan2(x*tan(t), x)
    # old-style relationals and odd assumption shapes do not raise
    e = asin(sin(x))
    for a in [Ge(x, -pi/2) & Le(x, pi/2), (x > -pi/2) & (x < pi/2), Q.ge(x, zoo), Q.gt(x, x),
              Q.ge(x, I) & Q.le(x, I), Q.ge(x, 0) & Q.le(x, AccumBounds(0, 1)), Q.ge(x, 0) & Q.lt(x, zoo)]:
        r = refine(e, a)
        assert isinstance(r, Basic) and r in (e, x)
    assert inverse._conjunct_bounds(x, Q.ge(x, nan) & Q.le(x, zoo) & Q.ge(x, I)) == []
