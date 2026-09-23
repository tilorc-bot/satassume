"""Tests for ``satrefine.handlers_v3.integer_funcs``.

Each rule gets a positive test (the refined form) and a numeric soundness
check over a grid that covers every sign combination, exact divisibility,
zero, and non-integer reals, restricted to the points that satisfy the
assumptions.
"""
from __future__ import annotations

from itertools import product

import pytest
from sympy import (
    Abs, Mod, Q, Rational, Rem, S, ceiling, floor, frac, pi, sign, sqrt, symbols,
)

from sympy.assumptions.assume import AppliedPredicate

import satrefine._upstream as upstream
from satrefine import refine
from satrefine.harness import (
    _numerically_equal, _sample_satisfies, assert_refinement_valid, use_ask,
)

x, y, n, m, k, a, b = symbols('x y n m k a b')

INTS = [S(v) for v in range(-6, 7)]
REALS = INTS + [Rational(v, 2) for v in (-7, -5, -3, -1, 1, 3, 5, 7)] + [
    Rational(-7, 3), Rational(7, 3), Rational(1, 3), Rational(-1, 3),
    pi, -pi, sqrt(2), -sqrt(2)]
DIVISORS = [v for v in REALS if v != 0]          # Mod/Rem by zero raises


def _value(expr, sample):
    """Substitute, then spell out any ``Rem`` SymPy left unevaluated
    (it only evaluates for Number divisors, e.g. not ``Rem(1, pi)``)."""
    v = expr.subs(sample)
    return v.replace(lambda e: isinstance(e, Rem),
                     lambda e: e.args[0] - e.args[1]*sign(e.args[0]/e.args[1])
                     * floor(Abs(e.args[0]/e.args[1])))


def check_sound(expr, assumptions, refined, grid=None, minimum=3):
    """Compare ``expr`` and ``refined`` at every grid point satisfying the
    assumptions; return the list of checked points."""
    syms = sorted(expr.free_symbols | refined.free_symbols, key=str)
    grid = grid or {}
    cands = [grid.get(s, REALS) for s in syms]
    checked = []
    for vals in product(*cands):
        sample = dict(zip(syms, vals))
        if not _sample_satisfies(assumptions, sample):
            continue
        left, right = _value(expr, sample), _value(refined, sample)
        assert _numerically_equal(left, right), (
            f"{expr} -> {refined} wrong at {sample}: {left} != {right}")
        checked.append(sample)
    assert len(checked) >= minimum, f"only {len(checked)} points satisfy {assumptions}"
    return checked


def signs(points, sym):
    return {int(bool(p[sym] > 0)) - int(bool(p[sym] < 0)) for p in points}


# (expr, assumptions, expected, grid)
POSITIVE = [
    # floor / ceiling
    (floor(x), Q.integer(x), x, None),
    (ceiling(x), Q.integer(x), x, None),
    (floor(x + n), Q.integer(n), n + floor(x), None),
    (ceiling(x + n), Q.integer(n), n + ceiling(x), None),
    (floor(x + 2*n + m), Q.integer(n) & Q.integer(m), 2*n + m + floor(x),
     {x: REALS[::3], n: INTS[::2], m: INTS[::3]}),
    (floor(x + floor(y)), Q.finite(y), floor(x) + floor(y), None),
    (floor(x), Q.nonnegative(x) & Q.lt(x, 1), S.Zero, None),
    (ceiling(x), Q.nonpositive(x) & Q.gt(x, -1), S.Zero, None),
    # frac
    (frac(x), Q.integer(x), S.Zero, None),
    (frac(x + n), Q.integer(n), frac(x), None),
    (frac(x + ceiling(y)), Q.finite(y), frac(x), None),
    (frac(x), Q.nonnegative(x) & Q.lt(x, 1), x, None),
    # Mod
    (Mod(n, 2), Q.even(n), S.Zero, None),
    (Mod(n, 2), Q.odd(n), S.One, None),
    (Mod(n, -2), Q.odd(n), S.NegativeOne, None),
    (Mod(n, -2), Q.even(n), S.Zero, None),
    (Mod(2*n + 1, 2), Q.integer(n), S.One, None),
    (Mod(2*n + 3, -2), Q.integer(n), S.NegativeOne, None),
    (Mod(x, 1), Q.integer(x), S.Zero, None),
    (Mod(k*n, n), Q.integer(k) & Q.nonzero(n), S.Zero, {n: DIVISORS}),
    (Mod(a, b), Q.integer(a/b) & Q.nonzero(b), S.Zero, {b: DIVISORS}),
    (Mod(x + 2*n, 2), Q.integer(n), Mod(x, 2), None),
    (Mod(x + k*b, b), Q.integer(k) & Q.nonzero(b), Mod(x, b),
     {x: REALS[::2], k: INTS[::2], b: DIVISORS[::2]}),
    (Mod(a, b), Q.nonnegative(a) & Q.lt(a, b), a, {b: DIVISORS}),
    (Mod(a, b), Q.nonpositive(a) & Q.gt(a, b), a, {b: DIVISORS}),
    (Mod(a, b), Q.positive(a) & Q.positive(b), Rem(a, b), {b: DIVISORS}),
    (Mod(a, b), Q.negative(a) & Q.negative(b), Rem(a, b), {b: DIVISORS}),
    # Rem
    (Rem(n, 2), Q.even(n), S.Zero, None),
    (Rem(n, -2), Q.even(n), S.Zero, None),
    (Rem(n, 2), Q.odd(n) & Q.positive(n), S.One, None),
    (Rem(n, 2), Q.odd(n) & Q.negative(n), S.NegativeOne, None),
    (Rem(n, -2), Q.odd(n) & Q.positive(n), S.One, None),
    (Rem(n, -2), Q.odd(n) & Q.negative(n), S.NegativeOne, None),
    (Rem(x, 1), Q.integer(x), S.Zero, None),
    (Rem(k*n, n), Q.integer(k) & Q.nonzero(n), S.Zero, {n: DIVISORS}),
    (Rem(a, b), Q.integer(a/b) & Q.nonzero(b), S.Zero, {b: DIVISORS}),
    (Rem(a, b), Q.nonnegative(a) & Q.lt(a, b), a, {b: DIVISORS}),
    (Rem(a, b), Q.nonnegative(a) & Q.lt(a, -b), a, {b: DIVISORS}),
    (Rem(a, b), Q.nonpositive(a) & Q.gt(a, -b), a, {b: DIVISORS}),
    (Rem(a, b), Q.nonpositive(a) & Q.gt(a, b), a, {b: DIVISORS}),
    (Rem(a, b), Q.positive(b) & Q.lt(a, b) & Q.gt(a, -b), a, {b: DIVISORS}),
    (Rem(a, b), Q.negative(b) & Q.gt(a, b) & Q.lt(a, -b), a, {b: DIVISORS}),
]


@pytest.mark.parametrize("expr, assumptions, expected, grid", POSITIVE,
                         ids=[f"{e}|{q}" for e, q, _, _ in POSITIVE])
def test_rule_fires_and_is_sound(expr, assumptions, expected, grid):
    refined = refine(expr, assumptions)
    assert refined == expected
    check_sound(expr, assumptions, refined, grid)


@pytest.mark.parametrize("expr, assumptions, expected, grid", POSITIVE[:12] + POSITIVE[19:22],
                         ids=[f"{e}|{q}" for e, q, _, _ in POSITIVE[:12] + POSITIVE[19:22]])
def test_rule_passes_harness_oracle(expr, assumptions, expected, grid):
    """The harness's own sampler (default samples include complex values)."""
    refined = refine(expr, assumptions)
    values = {s: v for s, v in (grid or {}).items()}
    if assumptions is not True and any(
            p.function in (Q.lt, Q.gt) for p in assumptions.atoms(AppliedPredicate)):
        # the harness cannot compare complex samples in a relation
        values = {s: values.get(s, REALS) for s in expr.free_symbols}
    assert_refinement_valid(expr, assumptions, refined, samples=200, values=values or None)


# ---------------------------------------------------------------- quadrants

@pytest.mark.parametrize("expr, assumptions, divisor_signs", [
    (Mod(a, b), Q.nonnegative(a) & Q.lt(a, b), {1}),
    (Mod(a, b), Q.nonpositive(a) & Q.gt(a, b), {-1}),
    (Rem(a, b), Q.nonnegative(a) & Q.lt(a, -b), {-1}),
    (Rem(a, b), Q.nonpositive(a) & Q.gt(a, -b), {1}),
    (Mod(a, b), Q.integer(a/b) & Q.nonzero(b), {-1, 1}),
    (Rem(a, b), Q.integer(a/b) & Q.nonzero(b), {-1, 1}),
    (Mod(x + k*b, b), Q.integer(k) & Q.nonzero(b), {-1, 1}),
])
def test_rules_checked_in_every_allowed_quadrant(expr, assumptions, divisor_signs):
    refined = refine(expr, assumptions)
    assert refined != expr
    pts = check_sound(expr, assumptions, refined, {b: DIVISORS, k: INTS[::2]})
    assert signs(pts, b) == divisor_signs
    for s in expr.args[0].free_symbols:
        assert len(signs(pts, s)) >= 2      # zero and a nonzero sign at least


def test_integer_quadrants_for_multiple_rule_include_exact_divisibility():
    expr, q = Rem(a, b), Q.integer(a/b) & Q.nonzero(b)
    pts = check_sound(expr, q, refine(expr, q), {a: INTS, b: [S(v) for v in (-3, -2, 2, 3)]})
    quads = {(signs([p], a).pop(), signs([p], b).pop()) for p in pts}
    assert {(1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (0, -1)} <= quads


# ------------------------------------------------------------- conventions

def test_sympy_conventions_the_rules_rely_on():
    assert Mod(-3, 2) == 1 and Mod(3, -2) == -1 and Mod(-3, -2) == -1
    assert Rem(-3, 2) == -1 and Rem(3, -2) == 1 and Rem(-3, -2) == -1
    assert Mod(Rational(-7, 2), 2) == Rational(1, 2)
    assert Rem(Rational(-7, 2), 2) == Rational(-3, 2)


# ---------------------------------------------------------------- negatives

NEGATIVE = [
    (Rem(n, 2), Q.odd(n)),                          # Rem(-3, 2) = -1
    (Rem(n, -2), Q.odd(n)),
    (Rem(n, 2), Q.integer(n)),
    (Mod(n, 2), Q.integer(n)),
    (Mod(n, 3), Q.odd(n)),
    (Mod(x, 2), Q.real(x)),
    (frac(x), Q.real(x)),
    (frac(x), Q.positive(x)),
    (floor(x), Q.real(x)),
    (floor(x), Q.positive(x)),
    (ceiling(x), Q.negative(x)),
    (floor(x + y), Q.real(x) & Q.real(y)),
    (Mod(a, b), Q.negative(a) & Q.positive(b)),     # signs differ: not Rem
    (Mod(a, b), Q.positive(a) & Q.negative(b)),
    (Mod(a, b), Q.nonnegative(a)),
    (Mod(a, b), Q.integer(a) & Q.integer(b)),
    (Mod(a, b), Q.lt(a, b)),                        # a may be negative
    (Rem(a, b), Q.positive(a) & Q.positive(b)),
    (Rem(a, b), Q.lt(a, b) & Q.positive(b)),        # a may be <= -b
    (Rem(x + 2*n, 2), Q.integer(n) & Q.real(x)),     # shift can flip the sign
    (Rem(a, b), Q.integer(a/b)),                    # b may be zero
    (Mod(x + n*b, b), Q.integer(n)),                # b may be zero
    (frac(x + floor(y)), True),                     # y may be oo
    (frac(x + ceiling(y)), Q.extended_real(y)),
]


@pytest.mark.parametrize("expr, assumptions", NEGATIVE,
                         ids=[f"{e}|{q}" for e, q in NEGATIVE])
def test_rule_does_not_fire(expr, assumptions):
    assert refine(expr, assumptions) == expr


def test_rem_odd_without_sign_counterexample():
    # why Rem(n, 2) with only Q.odd(n) must stay: it is 1 or -1
    assert {Rem(v, 2) for v in (-5, -3, -1, 1, 3, 5)} == {S(-1), S(1)}


def test_mod_rem_disagree_across_signs():
    # why M5 needs matching signs
    assert Mod(-3, 5) != Rem(-3, 5) and Mod(3, -5) != Rem(3, -5)


# ------------------------------------------------------- ask robustness

def test_relation_ask_errors_are_treated_as_unknown():
    def raising_ask(prop, assumptions=True):
        if prop.function in (Q.lt, Q.le, Q.gt, Q.ge):
            raise ValueError("inconsistent assumptions")
        return None
    with use_ask(raising_ask):
        assert refine(Mod(a, b), Q.nonnegative(a) & Q.lt(a, b)) == Mod(a, b)
        assert refine(Rem(a, b), Q.lt(a, b)) == Rem(a, b)
        assert refine(floor(x), Q.lt(x, 1)) == floor(x)


def test_handlers_return_none_when_nothing_is_known():
    from satrefine.handlers_v3 import integer_funcs as mod
    with use_ask(lambda p, q=True: None):
        assert mod.refine_floor(floor(x), True) is None
        assert mod.refine_ceiling(ceiling(x), True) is None
        assert mod.refine_frac(frac(x), True) is None
        assert mod.refine_Mod(Mod(a, b), True) is None
        assert mod.refine_Rem(Rem(a, b), True) is None


def test_registration():
    from satrefine.handlers_v3 import integer_funcs as mod
    assert upstream.handlers_dict['floor'] is mod.refine_floor
    assert upstream.handlers_dict['ceiling'] is mod.refine_ceiling
    assert upstream.handlers_dict['frac'] is mod.refine_frac
    assert upstream.handlers_dict['Mod'] is mod.refine_Mod
    assert upstream.handlers_dict['Rem'] is mod.refine_Rem


def test_infinite_real_floor():
    assert refine(floor(x), Q.infinite(x) & Q.extended_real(x)) == x
    check_sound(floor(x), True, x, {x: [S.Infinity, S.NegativeInfinity]}, minimum=2)
    assert refine(ceiling(x), Q.infinite(x) & Q.extended_real(x)) == x


def test_floor_of_infinite_is_not_a_gaussian_integer():
    # regression: frac(1/2 + floor(oo)) = AccumBounds(0, 1), not frac(1/2)
    assert frac(S.Half + floor(S.Infinity)) != frac(S.Half)
    assert refine(frac(x + floor(y))) == frac(x + floor(y))
    assert refine(floor(x + floor(y))) == floor(x + floor(y))


@pytest.mark.parametrize("expr, assumptions", [
    (floor(x), Q.positive(x) & Q.negative(x)),
    (frac(x), Q.integer(x) & Q.imaginary(x)),
    (floor(x + n), Q.integer(n) & Q.positive(n) & Q.negative(n)),
    (Mod(n, 2), Q.integer(n) & Q.positive(n) & Q.negative(n)),
    (Rem(a + n, b), Q.integer(n) & Q.positive(n) & Q.negative(n)),
])
def test_contradictory_assumptions_do_not_raise(expr, assumptions):
    # regression: the integer test used to propagate ask's ValueError
    from satrefine.handlers_v3 import integer_funcs as mod
    handler = getattr(mod, "refine_" + type(expr).__name__)
    handler(expr, assumptions)              # any answer is vacuously sound
