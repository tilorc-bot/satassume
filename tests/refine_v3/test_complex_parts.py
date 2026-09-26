"""Tests for ``satrefine.reference.v3.complex_parts``.

Every positive test asserts the exact refined form and then checks it
numerically with :func:`satrefine.harness.assert_refinement_valid`, whose
default sample set contains ``0``, negative reals, points on the imaginary
axis and genuinely complex points (``1 + I``, ``1 - I``), so a rule that is
stated for a real factor is exercised with the other symbols complex.
Negative tests assert that a tempting-but-wrong rewrite does not happen.
"""
from __future__ import annotations

import signal
from contextlib import contextmanager

import pytest
from sympy import (Abs, I, Mul, Rational, S, Symbol, arg, conjugate, cos, cosh,
                   exp, im, pi, re, sign, sin, sqrt, symbols)
from sympy.assumptions import Q

from satrefine import refine
from satrefine.reference.v3 import complex_parts
from satrefine.testing.harness import assert_refinement_valid

x, y, z, t, w = symbols('x y z t w')
n = Symbol('n')

REALS = [S.Zero, S.One, S.NegativeOne, S(2), S(-3), S.Half, Rational(-1, 2), sqrt(2), pi]
COMPLEX = REALS + [I, -I, 2 * I, -2 * I, 1 + I, 1 - I, -1 + I, -2 - I, Rational(1, 3) - 2 * I]


def check(expr, assumptions, expected, values=None):
    refined = refine(expr, assumptions)
    assert refined == expected, f"refine({expr}, {assumptions}) gave {refined}, expected {expected}"
    assert_refinement_valid(expr, assumptions, refined, values=values)
    return refined


def unchanged(expr, assumptions):
    assert refine(expr, assumptions) == expr


@contextmanager
def bounded(seconds):
    def on_alarm(signum, frame):
        raise TimeoutError(f"refine did not return within {seconds}s")

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# --------------------------------------------------------------------------
# registration
# --------------------------------------------------------------------------

def test_registered_handlers():
    from satrefine.identities.compat.upstream import handlers_dict
    for key in ('re', 'im', 'arg', 'sign', 'Abs', 'conjugate', 'Mul'):
        assert handlers_dict[key].__module__ == complex_parts.__name__


def test_handlers_return_none_when_nothing_applies():
    for handler, expr in [
        (complex_parts.refine_Abs, Abs(x)), (complex_parts.refine_re, re(x)),
        (complex_parts.refine_im, im(x)), (complex_parts.refine_arg, arg(x)),
        (complex_parts.refine_sign, sign(x)), (complex_parts.refine_conjugate, conjugate(x)),
        (complex_parts.refine_Mul, x * y),
    ]:
        assert handler(expr, Q.complex(x) & Q.complex(y)) is None


# --------------------------------------------------------------------------
# Abs
# --------------------------------------------------------------------------

@pytest.mark.parametrize("assumptions, expected", [
    (Q.nonnegative(x), x), (Q.positive(x), x), (Q.zero(x), S.Zero),
    (Q.real(x) & ~Q.negative(x), x),
    (Q.nonpositive(x), -x), (Q.negative(x), -x),
    (Q.real(x) & ~Q.positive(x), -x),
])
def test_abs_sign_rules(assumptions, expected):
    check(Abs(x), assumptions, expected)


def test_abs_imaginary_with_known_im_sign():
    check(Abs(x), Q.imaginary(x) & Q.positive(im(x)), -I * x)
    check(Abs(x), Q.imaginary(x) & Q.negative(im(x)), I * x)
    check(Abs(x), Q.imaginary(x) & Q.positive(-I * x), -I * x)
    unchanged(Abs(x), Q.imaginary(x))
    unchanged(Abs(x), Q.positive(im(x)))       # not known imaginary: |1 + I| != -I*(1 + I)


def test_abs_product_splits_only_known_sign_factors():
    check(Abs(x * y), Q.positive(y), y * Abs(x), values={x: COMPLEX})
    check(Abs(x * y), Q.negative(y), -y * Abs(x), values={x: COMPLEX})
    check(Abs(x * y), Q.zero(y), S.Zero)
    check(Abs(x * y * z), Q.positive(y) & Q.imaginary(z) & Q.positive(im(z)),
          -I * y * z * Abs(x), values={x: COMPLEX})
    unchanged(Abs(x * y), Q.real(y))            # real but of unknown sign: no split
    unchanged(Abs(x * y), Q.complex(x) & Q.complex(y))
    unchanged(Abs(x * y), Q.positive(re(y)))


def test_abs_of_i_times_x():
    expr = Abs(Mul(I, x, evaluate=False))
    assert refine(expr, True) == Abs(x)
    assert_refinement_valid(expr, True, Abs(x), values={x: COMPLEX})


def test_abs_of_even_power_of_real():
    check(Abs(x**2), Q.real(x), x**2)
    check(Abs(x**4), Q.real(x), x**4)
    check(Abs(x**n), Q.real(x) & Q.even(n) & Q.positive(n), x**n, values={n: [2, 4]})
    check(Abs(x**n), Q.real(x) & Q.even(n) & ~Q.zero(x), x**n, values={n: [-2, 2]})
    # complex base: |x**2| is |x|**2, not x**2
    check(Abs(x**2), Q.complex(x), Abs(x)**2, values={x: COMPLEX})
    assert refine(Abs(x**2), Q.complex(x)) != x**2
    # even but possibly negative exponent at x == 0: Abs(0**-2) is oo, 0**-2 is zoo
    unchanged(Abs(x**n), Q.real(x) & Q.even(n))


def test_abs_of_integer_power_of_real():
    check(Abs(x**3), Q.real(x), Abs(x)**3)
    check(Abs(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), Abs(x)**n, values={n: [1, 3]})
    check(Abs(x**3), Q.complex(x), Abs(x)**3, values={x: COMPLEX})


def test_abs_and_reim_of_literal_negative_power_with_nonzero_base():
    # regression: a literal negative exponent used to be rejected before the
    # base was consulted, so an unevaluated Abs(x**-3) never fired even with
    # ~Q.zero(x); Abs(0**-3) is oo while Abs(0)**-3 is zoo, so without the
    # nonzero base it must still stay
    from sympy import Pow
    nonzero = [c for c in COMPLEX if c != 0]
    for e, real_expected in ((-3, Abs(x)**-3), (-2, x**-2)):
        unevaluated = Abs(Pow(x, e, evaluate=False), evaluate=False)
        assert complex_parts.refine_Abs(unevaluated, Q.real(x) & Q.nonzero(x)) == real_expected
        assert complex_parts.refine_Abs(unevaluated, ~Q.zero(x)) == Abs(x)**e
        assert_refinement_valid(unevaluated, ~Q.zero(x), Abs(x)**e, values={x: nonzero})
        assert complex_parts.refine_Abs(unevaluated, Q.real(x)) is None
        assert complex_parts.refine_Abs(unevaluated, Q.complex(x)) is None
    unevaluated = Abs(Pow(x, -2, evaluate=False), evaluate=False)
    assert complex_parts.refine_Abs(unevaluated, Q.real(x) & ~Q.zero(x)) == x**-2
    unevaluated = re(Pow(x, -3, evaluate=False), evaluate=False)
    assert complex_parts.refine_re(unevaluated, Q.real(x) & ~Q.zero(x)) == x**-3
    assert complex_parts.refine_re(unevaluated, Q.real(x)) is None
    assert complex_parts.refine_im(im(Pow(x, -3, evaluate=False), evaluate=False), ~Q.zero(x)) is None
    assert complex_parts.refine_Abs(Abs(Pow(S.Zero, -2, evaluate=False), evaluate=False), True) is None


def test_abs_of_power_with_real_exponent():
    check(Abs(x**y), Q.real(y) & ~Q.zero(x), Abs(x)**y,
          values={x: [c for c in COMPLEX if c != 0], y: REALS})
    check(Abs(x**y), Q.positive(x) & Q.real(y), x**y)
    unchanged(Abs(x**y), Q.real(y))            # x may be 0 with y negative
    unchanged(Abs(x**y), Q.complex(x) & Q.complex(y))


def test_abs_of_exp():
    check(Abs(exp(x)), Q.real(x), exp(x))
    check(Abs(exp(x)), True, exp(re(x)), values={x: COMPLEX})
    check(Abs(exp(I * t)), Q.real(t), S.One)
    unevaluated = Abs(exp(x), evaluate=False)
    assert complex_parts.refine_Abs(unevaluated, True) == exp(re(x))
    assert refine(exp(re(x)), Q.imaginary(x)) == S.One


def test_abs_of_conjugate():
    assert complex_parts.refine_Abs(Abs(conjugate(x), evaluate=False), True) == Abs(x)
    check(Abs(conjugate(x)), Q.negative(x), -x)


def test_abs_negatives():
    unchanged(Abs(x), Q.real(x))
    unchanged(Abs(x), Q.complex(x))
    unchanged(Abs(x)**2, Q.complex(x))         # Abs(x)**2 -> x**2 is only true for real x
    unchanged(Abs(x + y), Q.real(x) & Q.real(y))
    unchanged(Abs(x), Q.positive(re(x)))


# --------------------------------------------------------------------------
# re / im
# --------------------------------------------------------------------------

@pytest.mark.parametrize("expr, assumptions, expected", [
    (re(x), Q.real(x), x), (im(x), Q.real(x), S.Zero),
    (re(x), Q.imaginary(x), S.Zero), (im(x), Q.imaginary(x), -I * x),
    (re(x), Q.zero(x), S.Zero), (im(x), Q.zero(x), S.Zero),
    (re(x), Q.positive(x), x), (im(x), Q.negative(x), S.Zero),
])
def test_reim_scalar(expr, assumptions, expected):
    check(expr, assumptions, expected)


def test_reim_product_pulls_out_real_and_imaginary_factors():
    check(re(x * y), Q.real(y), y * re(x), values={x: COMPLEX})
    check(im(x * y), Q.real(y), y * im(x), values={x: COMPLEX})
    check(re(x * y), Q.imaginary(y), I * y * im(x), values={x: COMPLEX})
    check(im(x * y), Q.imaginary(y), -I * y * re(x), values={x: COMPLEX})
    check(re(x * y), Q.real(x) & Q.real(y), x * y)
    check(im(x * y), Q.real(x) & Q.real(y), S.Zero)
    check(re(x * y * z), Q.real(y) & Q.imaginary(z), I * y * z * im(x), values={x: COMPLEX})
    unchanged(re(x * y), Q.complex(x) & Q.complex(y))
    unchanged(im(x * y), Q.positive(re(y)))


def test_reim_of_i_times_x_and_sums():
    check(re(I * x), Q.real(x), S.Zero)
    check(im(I * x), Q.real(x), x)
    check(re(x + I * y), Q.real(x) & Q.real(y), x)
    check(im(x + I * y), Q.real(x) & Q.real(y), y)
    check(re(x + y), Q.real(y), y + re(x), values={x: COMPLEX})
    unevaluated = re(Mul(I, x, evaluate=False))
    assert refine(unevaluated, Q.real(x)) == S.Zero


def test_reim_of_exp():
    check(re(exp(x)), Q.real(x), exp(x))
    check(im(exp(x)), Q.real(x), S.Zero)
    check(re(exp(x)), Q.imaginary(x), cosh(x))
    check(im(exp(I * t)), Q.real(t), sin(t))
    check(re(exp(I * t)), Q.real(t), cos(t))
    assert complex_parts.refine_re(re(exp(x), evaluate=False), True) == exp(re(x)) * cos(im(x))
    assert complex_parts.refine_im(im(exp(x), evaluate=False), True) == exp(re(x)) * sin(im(x))


def test_reim_of_conjugate():
    check(re(conjugate(x)), Q.imaginary(x), S.Zero)
    check(im(conjugate(x)), Q.imaginary(x), I * x)
    assert complex_parts.refine_re(re(conjugate(x), evaluate=False), True) == re(x)
    assert complex_parts.refine_im(im(conjugate(x), evaluate=False), True) == -im(x)


def test_reim_of_real_integer_power():
    check(re(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), x**n, values={n: [1, 2, 3]})
    check(im(x**n), Q.real(x) & Q.integer(n) & Q.positive(n), S.Zero, values={n: [1, 2, 3]})
    check(re(x**2), Q.real(x), x**2)
    unchanged(re(x**n), Q.real(x) & Q.integer(n))       # 0**(-1) is zoo, re(zoo) is nan
    unchanged(re(x**2), Q.complex(x))


def test_reim_of_general_power_returns_in_bounded_time():
    # the vendored handler expands with complex=True and recurses forever here
    with bounded(30):
        assert refine(re(x**z), Q.imaginary(z) & Q.real(x)) == re(x**z)
        assert refine(im(y**x), Q.imaginary(x) & Q.real(y)) == im(y**x)
        assert refine(re(x**z) + im(x**z), Q.imaginary(z) & Q.real(x)) == re(x**z) + im(x**z)


def test_reim_never_rebuilds_itself():
    # with nothing known about the factors the product rule must not fire,
    # and an unevaluated sum/conjugate/exp must not come back as itself
    assert complex_parts.refine_re(re(x * y), True) is None
    assert complex_parts.refine_im(im(x * y), True) is None
    for expr in (re(x * y), im(x * y), re(x + y), re(exp(x)), im(conjugate(x))):
        handler = complex_parts.refine_re if isinstance(expr, re) else complex_parts.refine_im
        result = handler(expr, Q.complex(x) & Q.complex(y))
        assert result is None or result != expr


# --------------------------------------------------------------------------
# arg
# --------------------------------------------------------------------------

def test_arg_scalar():
    check(arg(x), Q.positive(x), S.Zero)
    check(arg(x), Q.negative(x), pi)
    check(arg(x), Q.imaginary(x) & Q.positive(im(x)), pi / 2)
    check(arg(x), Q.imaginary(x) & Q.negative(im(x)), -pi / 2)
    unchanged(arg(x), Q.real(x))
    unchanged(arg(x), Q.imaginary(x))
    unchanged(arg(x), Q.zero(x))
    unchanged(arg(x), Q.nonnegative(x))


def test_arg_product_drops_positive_factors():
    check(arg(x * y), Q.positive(y), arg(x), values={x: COMPLEX})
    check(arg(x * y * z), Q.positive(y) & Q.positive(z), arg(x), values={x: COMPLEX})
    check(arg(x * y), Q.positive(x) & Q.positive(y), S.Zero)
    unchanged(arg(x * y), Q.real(y))
    unchanged(arg(x * y), Q.negative(y))       # arg(-x) is arg(x) +- pi, branch dependent
    unchanged(arg(x * y), Q.imaginary(y) & Q.positive(im(y)))
    unchanged(arg(x * y), Q.nonnegative(y))    # y == 0 gives nan


def test_arg_of_exp_needs_the_principal_range():
    in_range = Q.real(t) & Q.positive(t + pi) & Q.nonpositive(t - pi)
    check(arg(exp(I * t)), in_range, t, values={t: [0, 1, -1, 3, -3, pi, S.Half, -S.Half]})
    check(arg(exp(x + I * t)), Q.real(x) & in_range, t,
          values={t: [0, 1, -1, 3, pi], x: [0, 1, -2]})
    check(arg(exp(I * t)), Q.positive(t) & Q.negative(t - pi), t, values={t: [1, 3, S.Half]})
    check(arg(exp(x)), Q.real(x), S.Zero)
    unchanged(arg(exp(I * t)), Q.real(t))                     # t = 4 gives 4 - 2*pi
    unchanged(arg(exp(I * t)), Q.real(t) & Q.positive(t + pi))
    unchanged(arg(exp(I * t)), Q.positive(t))
    unchanged(arg(exp(x + I * t)), Q.real(t) & Q.positive(t + pi) & Q.nonpositive(t - pi))
    # exact points: a literal multiple of I outside the range is not returned
    def literal(k):
        return arg(exp(k, evaluate=False), evaluate=False)

    assert complex_parts.refine_arg(literal(3 * pi * I), True) == pi     # never 3*pi
    assert complex_parts.refine_arg(literal(I * pi / 3), True) == pi / 3
    assert complex_parts.refine_arg(literal(I * pi), True) == pi
    assert complex_parts.refine_arg(literal(-I * pi), True) == pi       # exp(-I*pi) is -1, never -pi
    assert complex_parts.refine_arg(literal(2 - 3 * I), True) == -3


def test_arg_of_conjugate():
    check(arg(conjugate(x)), Q.positive(re(x)), -arg(x), values={x: [1, 1 + I, 1 - I, 2 - 3 * I, S.Half]})
    check(arg(conjugate(x)), Q.nonnegative(re(x)), -arg(x), values={x: [0, 1, I, -I, 1 + I, 1 - I]})
    check(arg(conjugate(x)), ~Q.zero(im(x)), -arg(x), values={x: [I, -I, 1 + I, -1 + I, -1 - I]})
    check(arg(conjugate(x)), Q.positive(x), S.Zero)
    check(arg(conjugate(x)), Q.negative(x), pi)
    unchanged(arg(conjugate(x)), True)
    unchanged(arg(conjugate(x)), Q.complex(x))
    unchanged(arg(conjugate(x)), Q.negative(re(x)))          # x = -1: pi on both sides, not -pi
    # -oo lies on the negative axis: arg(conjugate(-oo)) is pi
    assert complex_parts.refine_arg(arg(conjugate(x)), Q.negative_infinite(x)) is None


# --------------------------------------------------------------------------
# sign
# --------------------------------------------------------------------------

def test_sign_scalar():
    check(sign(x), Q.positive(x), S.One)
    check(sign(x), Q.negative(x), S.NegativeOne)
    check(sign(x), Q.zero(x), S.Zero)
    check(sign(x), Q.imaginary(x) & Q.positive(im(x)), I)
    check(sign(x), Q.imaginary(x) & Q.negative(im(x)), -I)
    unchanged(sign(x), Q.real(x))
    unchanged(sign(x), Q.nonnegative(x))
    unchanged(sign(x), Q.imaginary(x))
    unchanged(sign(x), Q.positive(im(x)))


def test_sign_of_abs_and_exp():
    check(sign(Abs(x)), ~Q.zero(x), S.One, values={x: [c for c in COMPLEX if c != 0]})
    check(sign(Abs(x)), Q.nonzero(x), S.One)
    check(sign(Abs(x)), Q.imaginary(x), S.One)
    check(sign(exp(x)), Q.real(x), S.One)
    unchanged(sign(Abs(x)), Q.complex(x))
    unchanged(sign(Abs(x)), Q.real(x))
    unchanged(sign(exp(x)), Q.complex(x))
    unchanged(sign(exp(x)), Q.imaginary(x))


def test_sign_product_splits_known_sign_factors():
    check(sign(x * y), Q.positive(y), sign(x), values={x: COMPLEX})
    check(sign(x * y), Q.negative(y), -sign(x), values={x: COMPLEX})
    check(sign(x * y), Q.zero(y), S.Zero)
    check(sign(x * y), Q.imaginary(y) & Q.positive(im(y)), I * sign(x), values={x: COMPLEX})
    check(sign(x * Abs(y)), Q.positive(x) & ~Q.zero(y), S.One,
          values={y: [c for c in COMPLEX if c != 0]})
    check(sign(x * y * z), Q.negative(y) & Q.positive(z), -sign(x), values={x: COMPLEX})
    unchanged(sign(x * y), Q.real(y))
    unchanged(sign(x * y), Q.nonnegative(y))
    unchanged(sign(x * y), Q.complex(x) & Q.complex(y))


# --------------------------------------------------------------------------
# conjugate
# --------------------------------------------------------------------------

def test_conjugate_scalar():
    check(conjugate(x), Q.real(x), x)
    check(conjugate(x), Q.imaginary(x), -x)
    check(conjugate(x), Q.zero(x), S.Zero)
    check(conjugate(Abs(x)), True, Abs(x), values={x: COMPLEX})
    assert complex_parts.refine_conjugate(conjugate(arg(x), evaluate=False), True) == arg(x)
    assert complex_parts.refine_conjugate(conjugate(re(x), evaluate=False), True) == re(x)
    unchanged(conjugate(x), Q.complex(x))
    unchanged(conjugate(x), Q.positive(re(x)))


def test_conjugate_of_sums_and_products():
    check(conjugate(x + y), Q.real(y), y + conjugate(x), values={x: COMPLEX})
    check(conjugate(x * y), Q.imaginary(y), -y * conjugate(x), values={x: COMPLEX})
    check(conjugate(x + I * y), Q.real(x) & Q.real(y), x - I * y)
    check(conjugate(x * y), Q.real(x) & Q.real(y), x * y)
    unchanged(conjugate(x + y), Q.complex(x) & Q.complex(y))
    # unevaluated sum/product: split only if some term becomes conjugate-free
    from sympy import Add
    unevaluated = conjugate(Add(x, y, evaluate=False), evaluate=False)
    assert complex_parts.refine_conjugate(unevaluated, Q.real(y)) == conjugate(x) + y
    assert complex_parts.refine_conjugate(unevaluated, Q.complex(x) & Q.complex(y)) is None
    unevaluated = conjugate(Mul(x, y, evaluate=False), evaluate=False)
    assert complex_parts.refine_conjugate(unevaluated, Q.real(x)) == x * conjugate(y)
    assert complex_parts.refine_conjugate(unevaluated, True) is None


def test_conjugate_of_powers():
    check(conjugate(x**n), Q.integer(n), conjugate(x)**n,
          values={x: [c for c in COMPLEX if c != 0], n: [-2, -1, 0, 1, 2, 3]})
    check(conjugate(x**n), Q.integer(n) & Q.real(x), x**n,
          values={x: [c for c in REALS if c != 0], n: [-1, 1, 2, 3]})
    check(conjugate(x**3), Q.real(x), x**3)
    check(conjugate(x**y), Q.positive(x), x**conjugate(y), values={y: COMPLEX})
    check(conjugate(x**y), Q.positive(x) & Q.real(y), x**y)
    check(conjugate(sqrt(x)), Q.positive(x), sqrt(x))
    # branch cut: conjugate((-1)**(1/3)) != conjugate(-1)**(1/3)
    unchanged(conjugate(x**Rational(1, 3)), Q.real(x))
    unchanged(conjugate(sqrt(x)), Q.complex(x))
    unchanged(conjugate(x**y), Q.real(y))
    unchanged(conjugate(x**y), Q.negative(x))


def test_conjugate_of_exp():
    check(conjugate(exp(x)), Q.real(x), exp(x))
    check(conjugate(exp(I * t)), Q.real(t), exp(-I * t))
    assert complex_parts.refine_conjugate(conjugate(exp(x), evaluate=False), True) == exp(conjugate(x))


# --------------------------------------------------------------------------
# Mul: conjugate pairs
# --------------------------------------------------------------------------

def test_mul_conjugate_pair():
    check(x * conjugate(x), True, Abs(x)**2, values={x: COMPLEX})
    check(-x * conjugate(x), True, -Abs(x)**2, values={x: COMPLEX})
    check(2 * x * y * conjugate(x), True, 2 * y * Abs(x)**2, values={x: COMPLEX, y: [1, I, 1 + I]})
    check(x * y * conjugate(x) * conjugate(y), True, Abs(x)**2 * Abs(y)**2,
          values={x: [1, -1, I, 1 + I], y: [2, -I, 1 - I]})
    check(x * conjugate(x), Q.complex(x), Abs(x)**2, values={x: COMPLEX})


def test_mul_conjugate_pair_with_powers():
    check(x**2 * conjugate(x)**2, True, Abs(x)**4, values={x: COMPLEX})
    check(x**3 * conjugate(x), True, x**2 * Abs(x)**2, values={x: COMPLEX})
    check(x * conjugate(x)**2, True, conjugate(x) * Abs(x)**2, values={x: COMPLEX})
    check(1 / (x * conjugate(x)), True, Abs(x)**(-2), values={x: [c for c in COMPLEX if c != 0]})
    check(x**n * conjugate(x)**n, Q.integer(n), Abs(x)**(2 * n),
          values={x: [c for c in COMPLEX if c != 0], n: [-1, 1, 2, 3]})
    check(x * conjugate(x) * exp(y), True, exp(y) * Abs(x)**2, values={x: COMPLEX, y: [0, 1, I]})


def test_mul_conjugate_pair_negatives():
    unchanged(x / conjugate(x), True)                        # opposite exponents: not a pair
    unchanged(x * conjugate(y), True)
    unchanged(x**n * conjugate(x)**n, True)                  # n unknown: sqrt branch breaks it
    unchanged(sqrt(x) * sqrt(conjugate(x)), True)            # x = -4: (2*I)*(2*I) != 4
    unchanged(x * y, Q.real(x) & Q.real(y))
    unchanged(x * y * z, Q.positive(x))
    unchanged(x * conjugate(x)**Rational(1, 2), True)
    A, B = symbols('A B', commutative=False)
    unchanged(A * conjugate(A), True)
    unchanged(A * B, True)


def test_mul_conjugate_pair_after_argument_refinement():
    # with x real the pair collapses to x**2 before the Mul handler sees it
    check(x * conjugate(x), Q.real(x), x**2)
    check(x * conjugate(x), Q.imaginary(x), -x**2)
    check(y * x * conjugate(x), Q.positive(y), y * Abs(x)**2, values={x: COMPLEX})


# --------------------------------------------------------------------------
# soundness sweep: every rule at the edge points 0, negative reals, imaginary axis
# --------------------------------------------------------------------------

EDGE = [S.Zero, S.NegativeOne, S(-2), Rational(-1, 2), I, -I, 2 * I, -2 * I, 1 + I, -1 - I]


@pytest.mark.parametrize("expr, assumptions", [
    (Abs(x * y), Q.positive(y)), (Abs(x * y), Q.negative(y)),
    (re(x * y), Q.real(y)), (im(x * y), Q.imaginary(y)),
    (arg(x * y), Q.positive(y)), (sign(x * y), Q.negative(y)),
    (sign(Abs(x)), ~Q.zero(x)), (conjugate(x**n), Q.integer(n)),
    (conjugate(x * y), Q.real(y)), (x * conjugate(x), True),
    (x**3 * conjugate(x), True), (Abs(x**y), Q.real(y) & ~Q.zero(x)),
])
def test_rules_hold_at_edge_points(expr, assumptions):
    refined = refine(expr, assumptions)
    assert refined != expr
    assert_refinement_valid(expr, assumptions, refined,
                            values={x: EDGE, y: [S(2), S(-3), S.Half, 3 * I, -I],
                                    n: [-2, -1, 1, 2, 3]})


def test_sign_of_conjugate_pair_product_numeric():
    # sign(x**2*conjugate(x)) -> sign(x*Abs(x)**2): checked by evaluating the
    # product to a number first, because SymPy's own sign.eval mis-evaluates
    # sign((1 - I)**2*(1 + I)) (it gives I*sign(1 + I) instead of -I*sign(1 + I)),
    # which makes the substitution oracle unusable for this input.
    from sympy import N
    expr = sign(x**2 * conjugate(x))
    refined = refine(expr, Q.complex(x))
    assert refined == sign(x * Abs(x)**2)
    for v in [1 - I, 1 + I, -1 + I, -2 - I, 2 * I, -3, S.Half]:
        product = N((v**2 * conjugate(v)).expand(), 30)
        assert abs(N(sign(product), 30) - N(refined.subs(x, v), 30)) < 1e-20
