"""Tests for ``satrefine.reference.v3.power_exp_log`` (``Pow``, ``exp``, ``log``).

Every rule has a positive test that checks the refined form and a numeric
soundness check: the harness oracle draws sample points satisfying the
assumptions, and explicit edge points (zero, negative reals, points on the
branch cuts of ``log`` and ``sqrt``, complex points wherever only real-ness
or less was assumed) are compared with ``N(..., 30)``.  Negative tests pin
inputs where a tempting rewrite would be wrong and must come back unchanged,
and show the tempting rewrite failing numerically.
"""
from __future__ import annotations

import pytest
from sympy import (
    Abs, E, I, N, Pow, Q, Rational, S, exp, log, nan, oo, pi, sqrt, symbols, zoo,
)

from satrefine import refine
from satrefine.reference.v3.power_exp_log import refine_Pow, refine_exp, refine_log
from satrefine.testing.harness import assert_refinement_valid

x, y, z, a, b, n, m = symbols("x y z a b n m")

HALF = S.Half
THIRD = Rational(1, 3)

REALS = [S(-3), S(-1), Rational(-1, 2), S.Zero, HALF, S.One, S(2), pi]
POSITIVES = [HALF, S.One, S(2), pi, S(10)]
NEGATIVES = [S(-3), S(-1), Rational(-1, 2), -pi]
IMAGINARIES = [-2 * I, -I, I, 3 * I]
COMPLEXES = [1 + I, -1 + I, -2 - 3 * I, 2 - I, S(-1), -I, S(3)]
EVENS = [S(-4), S(-2), S.Zero, S(2), S(4)]
ODDS = [S(-3), S(-1), S.One, S(3), S(5)]
INTEGERS = [S(-3), S(-2), S(-1), S.Zero, S.One, S(2), S(3)]
EXPONENTS = [HALF, Rational(-1, 2), THIRD, Rational(3, 2), S(-1), S(3), 1 + I, -2 * I, pi]


def _agree_at(expr, refined, point):
    left = N(expr.subs(point), 30)
    right = N(refined.subs(point), 30)
    if left.has(zoo, nan, oo, -oo) or right.has(zoo, nan, oo, -oo):
        assert left == right, f"{expr} -> {refined} at {point}: {left} != {right}"
        return
    lv, rv = complex(left), complex(right)
    scale = max(1.0, abs(lv), abs(rv))
    assert abs(lv - rv) <= 1e-20 * scale, f"{expr} -> {refined} at {point}: {left} != {right}"


def _points(**grid):
    """Cartesian product of per-symbol value lists as substitution dicts."""
    keys = list(grid)
    out = [{}]
    for key in keys:
        out = [dict(p, **{key: v}) for p in out for v in grid[key]]
    return out


def check(expr, assumptions, expected, values=None, points=()):
    """Refine, compare with ``expected``, then check numerically."""
    refined = refine(expr, assumptions)
    assert refined == expected, f"refine({expr}, {assumptions}) = {refined}, expected {expected}"
    if values is not None:
        assert_refinement_valid(expr, assumptions, refined, values=values, samples=60)
    for point in points:
        _agree_at(expr, refined, point)
    return refined


def unchanged(expr, assumptions):
    assert refine(expr, assumptions) == expr


def rewrite_is_wrong(expr, tempting, point):
    """The tempting rewrite really is false at ``point`` (guards negative tests)."""
    left = N(expr.subs(point), 30)
    right = N(tempting.subs(point), 30)
    assert abs(complex(left) - complex(right)) > 1e-6, f"{expr} == {tempting} at {point}"


# ---------------------------------------------------------------------------
# Pow: sqrt(x**2) and (x**a)**b
# ---------------------------------------------------------------------------

class TestSqrtOfSquare:
    def test_real(self):
        check(sqrt(x**2), Q.real(x), Abs(x), values={x: REALS},
              points=_points(x=REALS))

    def test_nonnegative(self):
        check(sqrt(x**2), Q.nonnegative(x), x, values={x: [S.Zero] + POSITIVES},
              points=_points(x=[S.Zero] + POSITIVES))

    def test_nonpositive(self):
        check(sqrt(x**2), Q.nonpositive(x), -x, values={x: [S.Zero] + NEGATIVES},
              points=_points(x=[S.Zero] + NEGATIVES))

    def test_positive_and_negative(self):
        check(sqrt(x**2), Q.positive(x), x, values={x: POSITIVES})
        check(sqrt(x**2), Q.negative(x), -x, values={x: NEGATIVES})

    def test_imaginary(self):
        check(sqrt(x**2), Q.imaginary(x), I * Abs(x), values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))

    def test_imaginary_is_not_abs(self):
        # The vendored handler answers Abs(x) here; sqrt((2*I)**2) = 2*I.
        rewrite_is_wrong(sqrt(x**2), Abs(x), {x: 2 * I})
        assert refine(sqrt(x**2), Q.imaginary(x)) != Abs(x)

    def test_unevaluated_pow_form(self):
        check(Pow(Pow(x, 2), HALF), Q.real(x), Abs(x), points=_points(x=REALS))

    def test_no_assumptions_unchanged(self):
        unchanged(sqrt(x**2), True)
        rewrite_is_wrong(sqrt(x**2), Abs(x), {x: -1 + I})
        rewrite_is_wrong(sqrt(x**2), x, {x: -1 + I})

    def test_complex_unchanged(self):
        unchanged(sqrt(x**2), Q.complex(x))
        unchanged(sqrt(x**2), Q.finite(x) & Q.algebraic(x))  # Q.nonzero implies real in SymPy


class TestPowOfPow:
    def test_odd_inner_exponent_real_base_unchanged(self):
        # (x**3)**(1/2) is not Abs(x)**(3/2): at x = -1 it is -I, not 1.
        unchanged(sqrt(x**3), Q.real(x))
        rewrite_is_wrong(sqrt(x**3), Abs(x)**Rational(3, 2), {x: S(-1)})
        rewrite_is_wrong(sqrt(x**3), x**Rational(3, 2), {x: S(-1)})
        unchanged((x**a)**b, Q.real(x) & Q.odd(a))

    def test_positive_base_real_inner_exponent(self):
        check(sqrt(x**3), Q.positive(x), x**Rational(3, 2), values={x: POSITIVES},
              points=_points(x=POSITIVES))
        check((x**a)**b, Q.positive(x) & Q.real(a), x**(a * b),
              values={x: POSITIVES, a: REALS, b: EXPONENTS},
              points=_points(x=POSITIVES, a=[S(-3), HALF, S(2), pi], b=EXPONENTS))

    def test_nonnegative_base_positive_inner_exponent(self):
        check((x**a)**b, Q.nonnegative(x) & Q.positive(a), x**(a * b),
              values={x: [S.Zero] + POSITIVES, a: POSITIVES, b: [HALF, S(3), Rational(-1, 2)]},
              points=_points(x=[S.Zero, S(2)], a=[HALF, S(3)], b=[HALF, S(3), Rational(-1, 2)]))

    def test_positive_base_complex_inner_exponent_unchanged(self):
        # 2**(10*I) has argument 10*log(2) > pi, so the log wraps.
        unchanged((x**a)**b, Q.positive(x))
        rewrite_is_wrong((x**a)**b, x**(a * b), {x: S(2), a: 10 * I, b: HALF})

    def test_integer_outer_exponent(self):
        check((x**a)**b, Q.integer(b), x**(a * b),
              values={x: COMPLEXES, a: EXPONENTS, b: INTEGERS},
              points=_points(x=COMPLEXES, a=[HALF, 1 + I, -2 * I, S(3)], b=[S(-2), S(2), S(3)]))

    def test_real_base_even_inner_exponent(self):
        nonzero_reals = [v for v in REALS if v != 0]
        check((x**a)**b, Q.nonzero(x) & Q.even(a), Abs(x)**(a * b),
              values={x: nonzero_reals, a: EVENS, b: EXPONENTS},
              points=_points(x=nonzero_reals, a=[S(-2), S(2), S(4)], b=[HALF, THIRD, Rational(-1, 2), 1 + I]))
        check((x**a)**b, Q.real(x) & Q.even(a) & Q.positive(a), Abs(x)**(a * b),
              values={x: REALS, a: [S(2), S(4)], b: EXPONENTS},
              points=_points(x=REALS, a=[S(2), S(4)], b=[HALF, THIRD, Rational(-1, 2), 1 + I]))
        check((x**2)**THIRD, Q.real(x), Abs(x)**Rational(2, 3), values={x: REALS},
              points=_points(x=REALS))
        check((x**(-2))**HALF, Q.nonzero(x), Abs(x)**(-1), values={x: nonzero_reals},
              points=_points(x=nonzero_reals))

    def test_real_base_even_inner_exponent_signed(self):
        check((x**a)**b, Q.nonnegative(x) & Q.even(a) & Q.positive(a), x**(a * b),
              values={x: [S.Zero] + POSITIVES, a: [S(2), S(4)], b: EXPONENTS},
              points=_points(x=[S.Zero] + POSITIVES, a=[S(2), S(4)], b=[HALF, THIRD, 1 + I]))
        check((x**a)**b, Q.nonpositive(x) & Q.even(a) & Q.positive(a), (-x)**(a * b),
              values={x: [S.Zero] + NEGATIVES, a: [S(2), S(4)], b: EXPONENTS},
              points=_points(x=[S.Zero] + NEGATIVES, a=[S(2), S(4)], b=[HALF, THIRD, 1 + I]))
        check((x**a)**b, Q.negative(x) & Q.even(a), (-x)**(a * b),
              values={x: NEGATIVES, a: EVENS, b: EXPONENTS},
              points=_points(x=NEGATIVES, a=[S(-2), S(2)], b=[HALF, THIRD, 1 + I]))

    def test_zero_base_negative_even_inner_exponent_unchanged(self):
        # (0**(-4))**(1 + I) is zoo**(1 + I) in SymPy but 0**(-4 - 4*I) is nan.
        unchanged((x**a)**b, Q.real(x) & Q.even(a))
        unchanged((x**(-2))**b, Q.real(x))
        assert refine_Pow((x**a)**b, Q.real(x) & Q.even(a)) is None

    def test_imaginary_base_even_inner_exponent(self):
        check((x**6)**HALF, Q.imaginary(x), I * Abs(x)**3, values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))
        check((x**4)**HALF, Q.imaginary(x), -x**2, values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))
        check((x**2)**b, Q.imaginary(x), (-1)**b * Abs(x)**(2 * b),
              values={x: IMAGINARIES, b: EXPONENTS},
              points=_points(x=IMAGINARIES, b=EXPONENTS))
        check((x**4)**b, Q.imaginary(x), Abs(x)**(4 * b),
              values={x: IMAGINARIES, b: EXPONENTS},
              points=_points(x=IMAGINARIES, b=EXPONENTS))

    def test_symbolic_inner_exponent_unknown_parity_unchanged(self):
        unchanged((x**a)**b, Q.real(x) & Q.integer(a))
        unchanged((x**a)**b, Q.real(x) & Q.real(a) & Q.real(b))
        unchanged((x**a)**b, Q.imaginary(x) & Q.even(a))


# ---------------------------------------------------------------------------
# Pow: Abs(x)**n, (-1)**x, numeric bases, exp(x)**b, E**x
# ---------------------------------------------------------------------------

class TestPowOfAbs:
    def test_real_even(self):
        check(Abs(x)**n, Q.real(x) & Q.even(n), x**n, values={x: REALS, n: EVENS},
              points=_points(x=REALS, n=[S(-2), S(2), S(4)]))
        check(Abs(x)**2, Q.real(x), x**2, values={x: REALS})

    def test_imaginary_even(self):
        check(Abs(x)**2, Q.imaginary(x), -x**2, values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))
        check(Abs(x)**n, Q.imaginary(x) & Q.even(n), (-1)**(n / 2) * x**n,
              values={x: IMAGINARIES, n: EVENS},
              points=_points(x=IMAGINARIES, n=EVENS))
        check(Abs(x)**4, Q.imaginary(x), x**4, values={x: IMAGINARIES})

    def test_odd_or_unknown_unchanged(self):
        unchanged(Abs(x)**3, Q.real(x))
        rewrite_is_wrong(Abs(x)**3, x**3, {x: S(-2)})
        unchanged(Abs(x)**n, Q.real(x) & Q.integer(n))
        unchanged(Abs(x)**2, True)
        rewrite_is_wrong(Abs(x)**2, x**2, {x: 1 + I})
        unchanged(Abs(x)**2, Q.complex(x))


class TestMinusOnePower:
    def test_parity(self):
        check((-1)**x, Q.even(x), S.One, values={x: EVENS})
        check((-1)**x, Q.odd(x), S.NegativeOne, values={x: ODDS})

    def test_no_parity_unchanged(self):
        unchanged((-1)**x, Q.integer(x))
        unchanged((-1)**x, Q.real(x))
        unchanged((-1)**x, True)

    def test_shift_rewrites(self):
        check((-1)**(x + y), Q.even(x), (-1)**y, values={x: EVENS, y: COMPLEXES},
              points=_points(x=EVENS, y=COMPLEXES))
        check((-1)**(x + y + z), Q.odd(x) & Q.odd(z), (-1)**y,
              values={x: ODDS, y: COMPLEXES, z: ODDS},
              points=_points(x=[S(-1), S(3)], y=COMPLEXES, z=[S(1), S(5)]))
        check((-1)**(x + y + 2), Q.odd(x), (-1)**(y + 1), values={x: ODDS, y: COMPLEXES},
              points=_points(x=ODDS, y=COMPLEXES))
        check((-1)**(x + 3), True, (-1)**(x + 1), values={x: COMPLEXES},
              points=_points(x=COMPLEXES + [HALF, Rational(-5, 2)]))
        check((-1)**(x + Rational(5, 2)), True, (-1)**(x + HALF), values={x: COMPLEXES},
              points=_points(x=COMPLEXES))

    def test_all_terms_of_known_parity_reduce_to_a_constant(self):
        # The vendored handler rebuilds (-1)**(3/2) here, which auto-evaluates
        # to -I, and then crashes reading its .exp.
        check((-1)**(-n - HALF), Q.even(n), -I, values={n: EVENS}, points=_points(n=EVENS))
        check((-1)**(-n - HALF), Q.odd(n), I, values={n: ODDS}, points=_points(n=ODDS))
        check((-1)**(n + HALF), Q.even(n), I, values={n: EVENS}, points=_points(n=EVENS))
        check((-1)**(n - Rational(3, 2)), Q.odd(n), -I, values={n: ODDS}, points=_points(n=ODDS))
        check((-1)**(n + m + HALF), Q.even(n) & Q.odd(m), -I,
              values={n: EVENS, m: ODDS}, points=_points(n=EVENS, m=ODDS))
        check((-1)**(2 * n + HALF), Q.integer(n), I, values={n: INTEGERS}, points=_points(n=INTEGERS))
        assert refine_Pow((-1)**(-n - HALF), Q.even(n)) == -I
        # A leftover term of unknown parity still goes to the vendored rules.
        check((-1)**(n + m + HALF), Q.even(n), (-1)**(m + HALF),
              values={n: EVENS, m: COMPLEXES}, points=_points(n=EVENS, m=COMPLEXES))
        check((-1)**(-n - HALF), Q.integer(n), (-1)**(Rational(3, 2) - n),
              values={n: INTEGERS}, points=_points(n=INTEGERS))

    def test_half_integer_form(self):
        expr = (-1)**((-1)**n / 2 + m / 2)
        refined = refine(expr, Q.integer(n))
        assert refined == (-1)**(n + m / 2 + HALF)
        for point in _points(n=INTEGERS, m=[S(-3), S.Zero, S.One, HALF, 1 + I]):
            _agree_at(expr, refined, point)

    def test_negative_number_base(self):
        check((-2)**n, Q.even(n), 2**n, values={n: EVENS}, points=_points(n=EVENS))
        check((-2)**n, Q.odd(n), -2**n, values={n: ODDS}, points=_points(n=ODDS))
        check((-pi)**n, Q.odd(n), -pi**n, values={n: ODDS}, points=_points(n=ODDS))
        unchanged((-2)**n, Q.integer(n))
        rewrite_is_wrong((-2)**n, 2**n, {n: HALF})

    def test_zero_and_positive_number_bases_unchanged(self):
        # sign(0)*0**n is nan at n = -1 while 0**(-1) is zoo.
        unchanged(Pow(0, n, evaluate=False), Q.odd(n))
        unchanged(2**n, Q.even(n))
        unchanged(pi**x, Q.odd(x))


class TestPowOfExp:
    def test_real_argument(self):
        check(exp(x)**y, Q.real(x), exp(x * y), values={x: REALS, y: EXPONENTS},
              points=_points(x=REALS, y=EXPONENTS))

    def test_integer_exponent(self):
        check(exp(x)**y, Q.integer(y), exp(x * y), values={x: COMPLEXES, y: INTEGERS},
              points=_points(x=COMPLEXES + [5 * I], y=[S(-2), S(3)]))

    def test_unchanged(self):
        unchanged(exp(x)**y, True)
        unchanged(exp(x)**y, Q.imaginary(x) & Q.real(y))
        rewrite_is_wrong(exp(x)**y, exp(x * y), {x: 5 * I, y: HALF})


class TestEPower:
    def test_unevaluated_e_power_is_exp(self):
        expr = Pow(E, 2 * pi * I * n, evaluate=False)
        assert refine_Pow(expr, Q.integer(n)) == S.One
        assert refine(expr, Q.integer(n)) == S.One
        assert refine_Pow(Pow(E, x, evaluate=False), True) == exp(x)
        assert refine(Pow(E, x + 2 * pi * I, evaluate=False), True) == exp(x)

    def test_nothing_to_do(self):
        assert refine_Pow(1 / x, Q.real(x)) is None
        assert refine_Pow(x**y, Q.positive(x)) is None
        assert refine_Pow(x**(-2), Q.nonzero(x)) is None
        unchanged(1 / x, Q.real(x))
        unchanged(x**y, Q.positive(x) & Q.real(y))


# ---------------------------------------------------------------------------
# exp
# ---------------------------------------------------------------------------

class TestExp:
    def test_full_turns(self):
        check(exp(x + 2 * pi * I * n), Q.integer(n), exp(x),
              values={x: COMPLEXES, n: INTEGERS}, points=_points(x=COMPLEXES, n=INTEGERS))
        check(exp(2 * pi * I * n), Q.integer(n), S.One, values={n: INTEGERS})

    def test_half_turns_parity(self):
        check(exp(x + pi * I * n), Q.even(n), exp(x),
              values={x: COMPLEXES, n: EVENS}, points=_points(x=COMPLEXES, n=EVENS))
        check(exp(x + pi * I * n), Q.odd(n), -exp(x),
              values={x: COMPLEXES, n: ODDS}, points=_points(x=COMPLEXES, n=ODDS))
        check(exp(x + pi * I * n), Q.integer(n), (-1)**n * exp(x),
              values={x: COMPLEXES, n: INTEGERS}, points=_points(x=COMPLEXES, n=INTEGERS))
        check(exp(pi * I * n), Q.odd(n), S.NegativeOne, values={n: ODDS})

    def test_quarter_turn_constant(self):
        check(exp(pi * I * (n + HALF)), Q.integer(n), (-1)**n * I, values={n: INTEGERS},
              points=_points(n=INTEGERS))
        check(exp(x + pi * I * (n + Rational(3, 2))), Q.even(n), -I * exp(x),
              values={x: COMPLEXES, n: EVENS}, points=_points(x=COMPLEXES, n=EVENS))
        check(exp(x + 3 * pi * I), True, -exp(x), values={x: COMPLEXES},
              points=_points(x=COMPLEXES))

    def test_scaled_multiples(self):
        check(exp(x + pi * I * n / 2), Q.even(n), (-1)**(n / 2) * exp(x),
              values={x: COMPLEXES, n: EVENS}, points=_points(x=COMPLEXES, n=EVENS))
        check(exp(x + 4 * pi * I * n), Q.integer(n), exp(x),
              values={x: COMPLEXES, n: INTEGERS}, points=_points(x=COMPLEXES, n=INTEGERS))

    def test_mixed_terms(self):
        check(exp(pi * I * (n + y)), Q.integer(n), (-1)**n * exp(I * pi * y),
              values={n: INTEGERS, y: COMPLEXES}, points=_points(n=INTEGERS, y=COMPLEXES))
        check(exp(x + pi * I * n + pi * I * m), Q.even(n) & Q.odd(m), -exp(x),
              values={x: COMPLEXES, n: EVENS, m: ODDS},
              points=_points(x=COMPLEXES, n=[S(-2), S(2)], m=[S(-1), S(3)]))

    def test_unchanged(self):
        unchanged(exp(x), Q.real(x))
        unchanged(exp(x + pi * I * n / 2), Q.odd(n))
        unchanged(exp(x + pi * n), Q.integer(n))
        unchanged(exp(x + pi * I * n), Q.real(n))
        unchanged(exp(x + pi * I * n), Q.rational(n))
        unchanged(exp(x + pi * I / 3), True)
        assert refine_exp(exp(x), Q.integer(x)) is None
        rewrite_is_wrong(exp(x + pi * I * n), exp(x), {x: S.One, n: HALF})

    def test_exp_of_log_is_already_evaluated(self):
        assert exp(log(x)) == x
        unchanged(exp(log(x) + y), True)


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------

class TestLogOfExp:
    def test_real(self):
        check(log(exp(x)), Q.real(x), x, values={x: REALS}, points=_points(x=REALS + [S(100)]))

    def test_not_real_unchanged(self):
        unchanged(log(exp(x)), True)
        unchanged(log(exp(x)), Q.imaginary(x))
        unchanged(log(exp(x)), Q.complex(x))
        rewrite_is_wrong(log(exp(x)), x, {x: 4 * I})
        rewrite_is_wrong(log(exp(x)), x, {x: 1 - 4 * I})

    def test_inside_product(self):
        check(log(exp(x) * y), Q.real(x), x + log(y), values={x: REALS, y: COMPLEXES},
              points=_points(x=REALS, y=COMPLEXES))


class TestLogOfPower:
    def test_square_real(self):
        check(log(x**2), Q.real(x), 2 * log(Abs(x)), values={x: REALS},
              points=_points(x=REALS))

    def test_square_signed(self):
        check(log(x**2), Q.positive(x), 2 * log(x), values={x: POSITIVES})
        check(log(x**2), Q.negative(x), 2 * log(-x), values={x: NEGATIVES},
              points=_points(x=NEGATIVES))

    def test_square_imaginary(self):
        check(log(x**2), Q.imaginary(x), 2 * log(Abs(x)) + I * pi, values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))
        check(log(x**4), Q.imaginary(x), 4 * log(Abs(x)), values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))

    def test_square_unchanged_without_assumptions(self):
        unchanged(log(x**2), True)
        unchanged(log(x**2), Q.complex(x))
        rewrite_is_wrong(log(x**2), 2 * log(x), {x: -1 + I})
        rewrite_is_wrong(log(x**2), 2 * log(Abs(x)), {x: -1 + I})

    def test_symbolic_exponent_positive_base(self):
        check(log(x**n), Q.positive(x) & Q.real(n), n * log(x),
              values={x: POSITIVES, n: REALS}, points=_points(x=POSITIVES, n=REALS))
        check(log(x**HALF), Q.positive(x), log(x) / 2, values={x: POSITIVES})
        check(log(x**n), Q.nonnegative(x) & Q.positive(n), n * log(x),
              values={x: [S.Zero] + POSITIVES, n: POSITIVES},
              points=_points(x=[S.Zero, S(2)], n=[HALF, S(3)]))

    def test_symbolic_exponent_even(self):
        nonzero_reals = [v for v in REALS if v != 0]
        nonzero_evens = [v for v in EVENS if v != 0]
        check(log(x**n), Q.nonzero(x) & Q.even(n), n * log(Abs(x)),
              values={x: nonzero_reals, n: EVENS}, points=_points(x=nonzero_reals, n=EVENS))
        check(log(x**n), Q.real(x) & Q.even(n) & Q.nonzero(n), n * log(Abs(x)),
              values={x: REALS, n: nonzero_evens}, points=_points(x=REALS, n=nonzero_evens))

    def test_symbolic_even_exponent_needs_nonzero_base_or_exponent(self):
        # log(0**0) is log(1) = 0 in SymPy, but 0*log(Abs(0)) is nan.
        expr = log(x**n)
        unchanged(expr, Q.real(x) & Q.even(n))
        assert refine_log(expr, Q.real(x) & Q.even(n)) is None
        at_zero = {x: S.Zero, n: S.Zero}
        assert expr.xreplace(at_zero) == 0
        assert (n * log(Abs(x))).xreplace(at_zero) is nan

    def test_odd_exponent_negative_base(self):
        check(log(x**n), Q.negative(x) & Q.odd(n), n * log(-x) + I * pi,
              values={x: NEGATIVES, n: ODDS}, points=_points(x=NEGATIVES, n=ODDS))
        check(log(x**3), Q.negative(x), 3 * log(-x) + I * pi, values={x: NEGATIVES},
              points=_points(x=NEGATIVES))

    def test_odd_exponent_real_base_unchanged(self):
        unchanged(log(x**3), Q.real(x))
        unchanged(log(x**n), Q.real(x) & Q.integer(n))
        unchanged(log(x**n), Q.real(x) & Q.odd(n))
        rewrite_is_wrong(log(x**3), 3 * log(x), {x: S(-2)})
        rewrite_is_wrong(log(x**3), 3 * log(Abs(x)), {x: S(-2)})

    def test_positive_base_complex_exponent_unchanged(self):
        unchanged(log(x**n), Q.positive(x))
        rewrite_is_wrong(log(x**n), n * log(x), {x: S(2), n: 10 * I})

    def test_reciprocal(self):
        check(log(1 / x), Q.positive(x), -log(x), values={x: POSITIVES})
        check(log(1 / x), Q.imaginary(x), -log(x), values={x: IMAGINARIES},
              points=_points(x=IMAGINARIES))
        check(log(1 / x), Q.negative(x), -log(-x) + I * pi, values={x: NEGATIVES},
              points=_points(x=NEGATIVES))
        check(log(1 / x), Q.zero(x), -log(x), values={x: [S.Zero]}, points=[{x: S.Zero}])

    def test_reciprocal_unchanged_on_branch_cut(self):
        unchanged(log(1 / x), Q.real(x))
        unchanged(log(1 / x), Q.nonzero(x))
        unchanged(log(1 / x), True)
        rewrite_is_wrong(log(1 / x), -log(x), {x: S(-2)})

    def test_reciprocal_unchanged_for_infinite_argument(self):
        # log(1/oo) is log(0) = zoo, but -log(oo) is -oo.
        for assumptions in (Q.infinite(x), Q.extended_positive(x), Q.extended_nonnegative(x)):
            unchanged(log(1 / x), assumptions)
            assert refine_log(log(1 / x), assumptions) is None
        assert log(1 / x).subs(x, oo) is zoo and (-log(x)).subs(x, oo) is -oo
        literal = log(Pow(oo, -1, evaluate=False), evaluate=False)
        assert refine_log(literal, True) is None

    def test_general_inverse_power_needs_real_base_sign(self):
        unchanged(log(x**(-2)), Q.complex(x))
        check(log(x**(-2)), Q.real(x), -2 * log(Abs(x)), values={x: REALS},
              points=_points(x=REALS))


class TestLogOfProduct:
    def test_one_positive_factor(self):
        check(log(x * y), Q.positive(x), log(x) + log(y), values={x: POSITIVES, y: COMPLEXES},
              points=_points(x=POSITIVES, y=COMPLEXES + [S.Zero]))
        check(log(x * y * z), Q.positive(x), log(x) + log(y * z),
              values={x: POSITIVES, y: COMPLEXES, z: COMPLEXES},
              points=_points(x=[S(2)], y=[-1 + I, S(-1)], z=[S(-1), -I, 2 - I]))

    def test_both_positive(self):
        check(log(x * y), Q.positive(x) & Q.positive(y), log(x) + log(y),
              values={x: POSITIVES, y: POSITIVES})

    def test_negative_factors(self):
        check(log(x * y), Q.negative(x) & Q.positive(y), log(-x) + log(y) + I * pi,
              values={x: NEGATIVES, y: POSITIVES}, points=_points(x=NEGATIVES, y=POSITIVES))
        check(log(x * y), Q.negative(x) & Q.negative(y), log(-x) + log(-y),
              values={x: NEGATIVES, y: NEGATIVES}, points=_points(x=NEGATIVES, y=NEGATIVES))
        check(log(x * y), Q.negative(x), log(-x) + log(-y),
              values={x: NEGATIVES, y: COMPLEXES}, points=_points(x=NEGATIVES, y=COMPLEXES))
        check(log(x * y * z), Q.negative(x) & Q.negative(y), log(-x) + log(-y) + log(z),
              values={x: NEGATIVES, y: NEGATIVES, z: COMPLEXES},
              points=_points(x=[S(-1), -pi], y=[S(-2)], z=COMPLEXES))

    def test_numeric_coefficient(self):
        check(log(-x), Q.positive(x), log(x) + I * pi, values={x: POSITIVES},
              points=_points(x=POSITIVES))
        check(log(2 * x), Q.positive(x), log(2) + log(x), values={x: POSITIVES})
        check(log(-2 * x), Q.positive(x), log(2) + log(x) + I * pi, values={x: POSITIVES},
              points=_points(x=POSITIVES))
        check(log(-x), Q.negative(x), log(-x), values={x: NEGATIVES})
        check(log(-x * y), Q.negative(x), log(-x) + log(y),
              values={x: NEGATIVES, y: COMPLEXES}, points=_points(x=NEGATIVES, y=COMPLEXES))

    def test_unchanged(self):
        unchanged(log(x * y), Q.real(x) & Q.real(y))
        unchanged(log(x * y), Q.nonnegative(x))
        unchanged(log(x * y), True)
        unchanged(log(2 * x), True)
        unchanged(log(-x), True)
        unchanged(log(-x), Q.real(x))
        rewrite_is_wrong(log(x * y), log(x) + log(y), {x: S(-1), y: S(-1)})
        rewrite_is_wrong(log(x * y), log(x) + log(y), {x: -1 + I, y: -1 + I})
        rewrite_is_wrong(log(-x), log(x) + I * pi, {x: S(-2)})
        assert refine_log(log(x * y), Q.real(x)) is None


class TestLogNegativeArgument:
    def test_symbol(self):
        check(log(x), Q.negative(x), log(-x) + I * pi, values={x: NEGATIVES},
              points=_points(x=NEGATIVES))

    def test_product_known_negative(self):
        check(log(x * y), Q.negative(x * y), log(-x * y) + I * pi,
              values={x: NEGATIVES, y: POSITIVES}, points=_points(x=NEGATIVES, y=POSITIVES))

    def test_unchanged(self):
        unchanged(log(x), Q.real(x))
        unchanged(log(x), Q.positive(x))
        unchanged(log(x), Q.nonpositive(x))
        unchanged(log(x), True)
        assert refine_log(log(x), Q.nonzero(x)) is None


class TestLogOfAbs:
    def test_reduces_through_abs(self):
        check(log(Abs(x)), Q.positive(x), log(x), values={x: POSITIVES})
        check(log(Abs(x)), Q.negative(x), log(-x), values={x: NEGATIVES})

    def test_unchanged(self):
        unchanged(log(Abs(x)), Q.real(x))
        unchanged(log(Abs(x)), True)
        assert refine_log(log(Abs(x)), Q.real(x)) is None


# ---------------------------------------------------------------------------
# Handlers return SymPy objects or None, never Python ints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("handler, expr, assumptions", [
    (refine_Pow, (-1)**x, Q.even(x)),
    (refine_Pow, (-1)**x, Q.odd(x)),
    (refine_exp, exp(2 * pi * I * n), Q.integer(n)),
    (refine_exp, exp(pi * I * n), Q.odd(n)),
    (refine_log, log(exp(x)), Q.real(x)),
])
def test_handler_results_are_sympy_objects(handler, expr, assumptions):
    result = handler(expr, assumptions)
    assert result is not None
    assert not isinstance(result, (int, bool))
    assert hasattr(result, "free_symbols")


def test_handlers_are_registered():
    from satrefine.identities.compat.upstream import handlers_dict
    assert handlers_dict["Pow"] is refine_Pow
    assert handlers_dict["exp"] is refine_exp
    assert handlers_dict["log"] is refine_log
