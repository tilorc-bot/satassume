"""Closed real constants (``pi``, ``sqrt(2)``, ``E``, ``sin(1)``) in
linear relations (``satassume.lra_adapter``, item 2 of
``agent-reports/2026-09-25-next-steps.md``).

A constant in a linear position is an LRA term with rigorous rational
bounds ``lo < c < hi`` asserted once per session; ``pi/2`` and ``3*pi`` are
the term ``pi`` scaled; a constant times a symbol stays unreadable; a Float
stays unreadable (SymPy gives it no single meaning).

The fuzz at the end compares ``ask`` over real symbols with an oracle that
evaluates every constant to 60 digits (exact rationals then, Fourier-Motzkin
as in ``test_lra_fuzz.py``): a definite answer must agree with the oracle,
None is allowed (it is counted: the bounds are 1e-19 wide, so comparisons
closer than that stay open, on purpose).
"""
from __future__ import annotations

import random
from fractions import Fraction as F

import pytest

sympy = pytest.importorskip("sympy")
from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import (E, Float, I, Integral, Q, Rational, S, Symbol, cos, exp, log, pi,
                   sin, sqrt, symbols)
from sympy.calculus.accumulationbounds import AccumBounds

from test_lra import fm_feasible

from satassume import DictCache, Engine
from satassume import lra_adapter as ad
from satassume.sympy_api import ask

x, y = symbols("x y")
xr, yr = symbols("xr yr", real=True)


def _ask(prop, assum=True):
    try:
        return ask(prop, assum, Engine(cache=DictCache()))
    except ValueError:
        return "inconsistent"


# ----------------------------------------------------------------------
# The adapter
# ----------------------------------------------------------------------

def test_pi_over_two_and_pi_are_one_term():
    for c in (pi / 2, pi, 3 * pi / 2, -pi, 2 * pi + 1, pi / 2 - S(1) / 3):
        assert ad.terms(Q.lt(x, c)) == [pi, x]
    (items, rhs, strict, eq), pos = ad.to_constraint(Q.le(x, 3 * pi / 2 + 1))
    assert dict(items) == {pi: F(-3, 2), x: F(1)} and rhs == 1 and not strict


def test_closed_sums_split_into_constants():
    assert set(ad.terms(Q.lt(x, sqrt(2) + pi / 3 - E))) == {x, sqrt(2), pi, E}
    assert ad.terms(Q.lt(pi, 4)) == [pi]


@pytest.mark.parametrize("atom", [Q.lt(x * pi, 1), Q.lt(pi * x + 1, y), Q.lt(sqrt(2) * x, 1),
                                  Q.lt(0.5 * x, 1), Q.lt(x * (pi + 1), 1)], ids=str)
def test_constant_times_symbol_is_unreadable(atom):
    assert ad.terms(atom) is None
    assert _ask(Q.lt(xr, 2), Q.real(xr) & atom) is None


@pytest.mark.parametrize("c", [I * pi, pi + I, sqrt(-2), AccumBounds(0, 1),
                               Integral(sin(x), (x, 0, 1))], ids=str)
def test_non_real_or_undecided_constants_are_unreadable(c):
    assert ad.constant_bounds(c) is None
    assert ad.terms(Q.lt(x, c)) is None


def test_floats_are_unreadable():
    # SymPy reads a Float exactly in < and at its precision in Eq
    # (Eq(0.1, 1/10) is True, 0.1 > 1/10 is True): no reading agrees with both
    for atom in (Q.gt(x, 0.1), Q.le(x, Float("1.571")), Q.lt(x, 0.5 * pi + 0.25),
                 Q.lt(x, Float(2.0) * pi), Q.eq(Float(0.1), Rational(1, 10))):
        assert ad.terms(atom) is None, atom
    assert _ask(Q.eq(Float(0.1), Rational(1, 10))) is None
    assert _ask(Q.gt(Float(0.1), Rational(1, 10))) is None
    assert _ask(Q.gt(xr, Rational(1, 10)), Q.gt(xr, 0.1)) is None


@pytest.mark.parametrize("c", [pi, E, sqrt(2), log(2), sin(1), pi ** 2, exp(-100), exp(100),
                               2 ** pi, cos(1) - 1, -sqrt(3) / 7], ids=str)
def test_bounds_contain_the_value(c):
    lo, hi = ad.constant_bounds(c)
    v = sympy.Rational(c.evalf(60))
    assert lo < F(int(v.p), int(v.q)) < hi
    assert hi - lo < abs(F(int(v.p), int(v.q))) * F(1, 10 ** 18)


def test_exact_zero_gets_a_narrow_interval_around_zero():
    # evaluates to 0 without being syntactically 0: no sign, but interval
    # arithmetic still bounds it
    z = sqrt(2 + sqrt(3)) - (sqrt(2) + sqrt(6)) / 2
    lo, hi = ad.constant_bounds(pi * z)
    assert lo < 0 < hi and hi - lo < F(1, 10**30)
    # as a sum it is split into bounded parts, which cannot decide the sign
    assert _ask(Q.lt(xr, 0), Q.lt(xr, z)) is None
    assert _ask(Q.le(xr, 0), Q.le(xr, z)) is None


# ----------------------------------------------------------------------
# End to end
# ----------------------------------------------------------------------

def test_bounds_make_assumptions_inconsistent():
    assert _ask(Q.lt(xr, 2), Q.gt(xr, 3) & Q.le(xr, pi / 2)) == "inconsistent"
    assert _ask(Q.lt(x, 2), Q.real(x) & Q.gt(x, 3) & Q.le(x, pi / 2)) == "inconsistent"
    # a non-real x makes the relations free Booleans: not inconsistent
    assert _ask(Q.positive(x), Q.gt(x, 3) & Q.le(x, pi / 2)) is False


def test_bound_implies_rational_bound():
    assert _ask(Q.lt(xr, 2), Q.le(xr, pi / 2)) is True
    assert _ask(Q.lt(xr, Rational(3, 2)), Q.le(xr, pi / 2)) is None
    assert _ask(Q.lt(xr, Rational(1571, 1000)), Q.le(xr, pi / 2)) is True
    assert _ask(Q.lt(xr, Rational(1570, 1000)), Q.le(xr, pi / 2)) is None
    assert _ask(Q.gt(xr, 3), Q.gt(xr, pi)) is True
    assert _ask(Q.gt(xr, 0), Q.ge(xr, sqrt(2) - E + 2)) is True     # 0.695...


def test_one_variable_for_pi():
    assert _ask(Q.eq(yr, 2 * xr), Q.eq(xr, pi / 2) & Q.eq(yr, pi)) is True
    assert _ask(Q.lt(xr, yr), Q.le(xr, pi / 2) & Q.ge(yr, 3 * pi / 4)) is True


def test_constant_only_relations_use_the_bounds():
    assert _ask(Q.lt(pi, 4)) is True
    assert _ask(Q.lt(pi, 4), Q.lt(pi, 3)) is True      # constant route: assumptions not used
    assert _ask(Q.gt(pi, Rational(22, 7))) is False
    assert _ask(Q.lt(pi, Rational(355, 113))) is True
    assert _ask(Q.gt(E, Rational(2718, 1000))) is True
    assert _ask(Q.lt(sqrt(2) + sqrt(3), pi)) is None or sympy.ask(Q.lt(sqrt(2) + sqrt(3), pi)) is not None
    near = Rational(int(pi.evalf(40) * 10 ** 25), 10 ** 25)            # pi - 1e-25 < near < pi
    assert _ask(Q.lt(near, pi)) is None
    assert _ask(Q.lt(pi, 2 * pi)) is True


def test_nonlinear_constant_position_still_unreadable_end_to_end():
    assert _ask(Q.lt(xr, 2), Q.le(pi * xr, 1)) is None


# ----------------------------------------------------------------------
# Fuzz against the true values
# ----------------------------------------------------------------------

_RS = symbols("p q r", real=True)
_CONSTS = [pi, E, sqrt(2), log(2), sin(1), pi ** 2, 2 ** pi, exp(-3)]
_TRUE = {c: sympy.Rational(c.evalf(60)) for c in _CONSTS}
_OPS = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!="}
_NEG = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=", "!=": "=="}
_PRED = {"lt": Q.lt, "le": Q.le, "gt": Q.gt, "ge": Q.ge, "eq": Q.eq, "ne": Q.ne}


def _near(c, k):
    """A rational within 10**-k of the constant (the oracle keeps it apart)."""
    v = _TRUE[c]
    return Rational(int(v * 10 ** k), 10 ** k)


@st.composite
def rel(draw, nsyms=3):
    lhs = S(0)
    for s in _RS[:nsyms]:
        lhs += draw(st.integers(-2, 2)) * s
    rhs = S(0)
    for _ in range(draw(st.integers(0, 2))):
        c = draw(st.sampled_from(_CONSTS))
        rhs += Rational(draw(st.integers(-3, 3)), draw(st.sampled_from([1, 2, 3]))) * c
    kind = draw(st.integers(0, 4))
    if kind == 1:
        rhs += Rational(draw(st.integers(-4, 4)), draw(st.sampled_from([1, 2])))
    elif kind == 2:                       # compare with a close rational
        rhs -= _near(draw(st.sampled_from(_CONSTS)), draw(st.sampled_from([2, 6, 25])))
    elif kind == 3:                       # a constant minus a close rational: about 0
        c = draw(st.sampled_from(_CONSTS))
        rhs = c - _near(c, draw(st.sampled_from([6, 25])))
    return draw(st.sampled_from(list(_OPS))), lhs, rhs


def _oracle_con(kind, lhs, rhs):
    """``lhs - rhs OP 0`` with every constant replaced by its 60-digit value."""
    e = sympy.expand(lhs - rhs)
    co, k = {}, F(0)
    for t, v in e.as_coefficients_dict().items():
        if t in _RS:
            co[t] = co.get(t, F(0)) + F(int(v.p), int(v.q))
        else:
            val = sympy.Rational(v) * (1 if t == 1 else _TRUE[t])
            k += F(int(val.p), int(val.q))
    return co, _OPS[kind], -k


def _expected(assumptions, query):
    qc = _oracle_con(*query)
    # a constant-only query is answered without the assumptions (sympy_api)
    constant = not (query[1].free_symbols or query[2].free_symbols)
    cons = [] if constant else [_oracle_con(*a) for a in assumptions]
    if not fm_feasible(cons):
        return "inconsistent"
    if not fm_feasible(cons + [(qc[0], _NEG[qc[1]], qc[2])]):
        return True
    if not fm_feasible(cons + [qc]):
        return False
    return None


def check_case(assumptions, query, stats=None):
    expected = _expected(assumptions, query)
    assum = sympy.And(*[_PRED[k](a, b) for k, a, b in assumptions])
    r = _ask(_PRED[query[0]](query[1], query[2]), assum)
    # under inconsistent assumptions every answer is entailed: an answer
    # instead of the error only means the bounds could not see the
    # inconsistency (unchecked, like None)
    missed = r is None or (expected == "inconsistent" and r != expected)
    if stats is not None:
        stats["cases"] += 1
        if r != expected:
            stats["unchecked" if missed else "wrong"] += 1
    if not missed:
        assert r == expected, (query, assumptions, r, expected)
    return r, expected


FUZZ = settings(max_examples=150, deadline=None,
                suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


@FUZZ
@given(st.lists(rel(), min_size=1, max_size=4), rel())
def test_fuzz_constants_against_true_values(assumptions, query):
    check_case(assumptions, query)


@FUZZ
@given(st.lists(rel(nsyms=1), min_size=1, max_size=3), rel(nsyms=1))
def test_fuzz_one_symbol_against_true_values(assumptions, query):
    check_case(assumptions, query)


def run(seed0: int, n: int) -> dict:
    """Seeded standalone run (``python tests/test_lra_constants.py SEED0 N``):
    counts cases, wrong answers (must be 0) and unchecked ones (engine None,
    oracle definite)."""
    stats = {"cases": 0, "wrong": 0, "unchecked": 0}
    for seed in range(seed0, seed0 + n):
        rng = random.Random(seed)

        def draw_rel(nsyms):
            lhs = sum((rng.randint(-2, 2) * s for s in _RS[:nsyms]), S(0))
            rhs = S(0)
            for _ in range(rng.randint(0, 2)):
                rhs += Rational(rng.randint(-3, 3), rng.choice([1, 2, 3])) * rng.choice(_CONSTS)
            kind = rng.randint(0, 4)
            if kind == 1:
                rhs += Rational(rng.randint(-4, 4), rng.choice([1, 2]))
            elif kind == 2:
                rhs -= _near(rng.choice(_CONSTS), rng.choice([2, 6, 25]))
            elif kind == 3:
                c = rng.choice(_CONSTS)
                rhs = c - _near(c, rng.choice([6, 25]))
            return rng.choice(list(_OPS)), lhs, rhs
        nsyms = rng.randint(1, 3)
        assumptions = [draw_rel(nsyms) for _ in range(rng.randint(1, 4))]
        try:
            check_case(assumptions, draw_rel(nsyms), stats)
        except AssertionError as e:
            print("WRONG", seed, e)
    return stats


if __name__ == "__main__":
    import sys
    print(run(int(sys.argv[1]), int(sys.argv[2])))


def test_huge_and_tiny_constants_get_no_bounds_quickly():
    """The exact rational of exp(exp(exp(5))) (about 2**(4e64)) would take
    all memory; constants beyond 2**±4096 are not read."""
    import time
    from sympy import exp, factorial
    from satassume.lra_adapter import constant_bounds
    t = time.time()
    for c in (exp(exp(exp(5))), exp(-exp(exp(5))), exp(-3000), factorial(10**5)):
        assert constant_bounds(c) is None
    assert constant_bounds(exp(1000)) is not None
    assert time.time() - t < 5
    x = Symbol('x')
    assert ad.interpret(Q.lt(x, exp(exp(exp(5))))) is None


def test_constants_evalf_cannot_bound_rigorously_are_not_read():
    """Review of the bounds: sign/tanh/erf evaluate loosely under strict
    evalf (sign(Z) of an exact zero Z got bounds near 1), and a trig of a
    huge argument makes evalf work at that many bits."""
    import time
    from sympy import sign, tanh, erf
    from satassume.lra_adapter import constant_bounds
    Z = cos(pi/7) + cos(3*pi/7) + cos(5*pi/7) - S.Half
    for c in (sign(Z), tanh(10**300*Z), erf(10**300*Z)):
        assert constant_bounds(c) is None
    x = Symbol('x')
    assert ask(Q.lt(2*sign(Z), 3*sign(Z))) is not True
    assert ask(Q.gt(x, S.Half), Q.real(x) & Q.gt(x, sign(Z))) is None
    t = time.time()
    assert constant_bounds(sin(exp(exp(exp(5))))) is None
    assert constant_bounds(sin(I*exp(exp(exp(5))))) is None
    assert ask(Q.lt(x, sin(exp(exp(exp(5))))), Q.positive(x)) is None
    assert time.time() - t < 5
    # the tame ones still read
    for c in (pi, pi/2, sqrt(2), log(2), sin(1), exp(-100), E**pi - pi**E, sin(10**20)):
        assert constant_bounds(c) is not None


def test_loose_node_under_a_saturating_parent_gets_true_bounds():
    """Review of 064e59e: tan next to a pole and log next to 1 claim full
    accuracy; their two evaluations disagree, but atan saturates and hid
    that.  Every argument now needs bounds of its own."""
    from sympy import atan, tan
    from satassume.lra_adapter import constant_bounds
    r = Rational(157079632679489661923132169163975144209858469968755291049, 10**56)
    c1 = atan(tan(r)**3)                     # r is just past pi/2: about -pi/2
    c2 = atan(10**100 * log(1 - Rational(1, 10**200)))   # about -1e-100
    import mpmath
    with mpmath.workdps(300):
        true = [mpmath.atan(mpmath.tan(mpmath.mpf(r.p) / r.q) ** 3),
                mpmath.atan(mpmath.mpf(10)**100 * mpmath.log(1 - mpmath.mpf(10)**-200))]
        for c, v in zip((c1, c2), true):
            b = constant_bounds(c)
            assert b is None or (mpmath.mpf(b[0].numerator) / b[0].denominator < v
                                 < mpmath.mpf(b[1].numerator) / b[1].denominator)
    assert _ask(Q.lt(c1, 0)) is not False
    assert _ask(Q.lt(c2, -1)) is not True
    assert constant_bounds(atan(tan(1)**3)) is not None


def test_directed_rounding_of_mpmath_is_not_trusted():
    """Review of c05c00c: mpmath's exp and log round an approximation in
    the requested direction, so a value within a few 2**-140 of a 128-bit
    number can land on the wrong side (upper end of exp(891) and of
    log(156434) below the value); a cancelling parent then turned that into
    a wrong True.  Transcendental results are widened by 2**-120."""
    import mpmath
    from mpmath.libmp import from_int, mpf_exp, mpf_log
    from satassume.lra_adapter import constant_bounds
    for sf, mf, n in ((exp, mpf_exp, 891), (log, mpf_log, 156434)):
        with mpmath.workprec(800):
            t = (mpmath.exp if sf is exp else mpmath.log)(n)
            wrong = mpmath.mpf(mf(from_int(n), 128, 'c'))
            # mpmath 1.3.0: its upper end is below the value (wrong < t)
            m, e = mpmath.mpf((wrong + t) / 2).man_exp
            Y = Rational(int(m)) * Rational(2) ** int(e)
            c = pi * (sf(n) - Y)
            v = mpmath.pi * (t - mpmath.mpf(Y.p) / Y.q)
            lo, hi = constant_bounds(c)
            assert mpmath.mpf(lo.numerator) / lo.denominator < v \
                < mpmath.mpf(hi.numerator) / hi.denominator
            if v > 0:
                T = Rational(int(mpmath.floor(v * 10**400 / 2)), 10**400)   # 0 < T < v
                assert _ask(Q.lt(c, T)) is not True


def test_tiny_ends_do_not_build_huge_rationals():
    """Review of c05c00c: pi**-(10**20) passed the size check (only large
    ends were checked) and its exact rational raised OverflowError out of
    ask; pi**-(10**9) took a minute and 900 MB."""
    import time
    from sympy import Pow, tan
    from satassume.lra_adapter import constant_bounds
    t = time.time()
    for c in (Pow(pi, -10**20), Pow(pi, -10**9), tan(22)**(10**100), exp(-2047)**3):
        b = constant_bounds(c)
        assert b is None or b[0] < 0 < b[1] or 0 < b[0] < b[1] < F(1, 2**4000)
    assert _ask(Q.lt(xr, Pow(pi, -10**20)), Q.lt(xr, 0)) is not False
    assert time.time() - t < 5
