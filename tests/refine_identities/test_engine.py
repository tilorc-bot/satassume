"""The engine: dispatcher fix and firing cap, pattern forms, both table kinds, wraps."""
from __future__ import annotations

import pytest
from sympy import (Abs, Function, I, N, Q, Rational, S, cos, exp, floor, frac, im, log, pi, sin,
                   symbols, true)

from satrefine import refine
from satrefine._upstream import handlers_dict
from satrefine.handlers_identities import _dispatch
from satrefine.handlers_identities._engine import (bindings, identity_handler, part, provable,
                                                   rule_handler, subst)
from satrefine.handlers_identities._wraps import fractional, principal, reflect_full, reflect_half, sawtooth

x, y, n, r, a, b, p, q = symbols("x y n r a b p q")
F = Function("F")


def test_satrefine_refine_is_the_fixed_dispatcher():
    assert refine is _dispatch.refine


def test_dispatcher_refines_after_auto_evaluation():
    e_, b_ = symbols("e b")
    assert refine(im(e_*log(b_)), Q.negative(b_) & Q.even(e_)) == pi*e_


def test_firing_cap_raises_instead_of_looping():
    class Ping(Function):
        pass
    handlers_dict["Ping"] = lambda expr, assumptions: Ping(expr.args[0] + 1)
    try:
        with pytest.raises(_dispatch.RefineLoopError):
            refine(Ping(x))
    finally:
        del handlers_dict["Ping"]


# --- pattern forms ---------------------------------------------------------

def test_symbol_binds_anything_and_repeats_must_agree():
    assert list(bindings(x, sin(y))) == [{x: sin(y)}]
    assert list(bindings(x + x, y + y)) == [] or all(b[x] == y for b in bindings(x + x, y + y))


def test_one_plus_rest_for_products_and_sums():
    got = [b_ for b_ in bindings(p*q, x*y*n)]
    assert {(b_[p], b_[q]) for b_ in got} == {(x, y*n), (y, x*n), (n, x*y)}
    assert list(bindings(p*q, x)) == []
    got = [b_ for b_ in bindings(a + b, x + y)]
    assert {(b_[a], b_[b]) for b_ in got} == {(x, y), (y, x)}


def test_unit_coefficient_form():
    got = list(bindings(n*pi/2 + r, x + 3*pi/2))
    assert got[0] == {n: 3, r: x}
    got = list(bindings(n*pi/2 + r, x + y*pi + pi/2))
    assert got[0] == {n: 2*y + 1, r: x}          # collected first
    assert {n: 2*y, r: x + pi/2} in got           # then each unit term alone
    assert {n: 1, r: x + y*pi} in got
    assert list(bindings(n*pi + r, x)) == []
    assert list(bindings(n*pi + r, 2*pi)) == [{n: 2, r: 0}]
    assert {n: y, r: I*pi*x} in list(bindings(n*pi*I + r, I*pi*(x + y)))   # a product over a sum, distributed


def test_structure_beside_a_rest_symbol():
    """``e*log(b)`` binds the logarithm to one factor and ``e`` to the rest;
    ``w*conjugate(w)*r`` likewise inside a longer product."""
    e_, b_, w = symbols("e b w")
    from sympy import conjugate
    found = list(bindings(exp(e_*log(b_)), exp(a*b*log(x))))
    assert any(m[b_] == x and m[e_] == a*b for m in found)
    found = list(bindings(w*conjugate(w)*r, 2*x*y*conjugate(x)))
    assert any(m[w] == x and m[r] == 2*y for m in found)
    assert list(bindings(exp(e_*log(b_)), exp(x))) == []


def test_sub_product_at_the_top_keeps_the_other_factors():
    from sympy import conjugate
    from satrefine.handlers_identities._engine import REBUILD
    w = symbols("w")
    found = [m for m in bindings(w*conjugate(w), 2*x*y*conjugate(x)) if m[w] == x]
    assert found and found[0][REBUILD](Abs(x)**2) == 2*y*Abs(x)**2


def test_partition_form():
    ints = part("i", Q.integer)
    got = list(bindings(ints + r, x + n + 3, Q.integer(n)))
    assert got == [{ints: n + 3, r: x}]
    assert list(bindings(ints + r, x, Q.integer(n))) == []
    pos = part("s", Q.positive)
    got = list(bindings(pos*r, x*y*2, Q.positive(x)))
    assert got == [{pos: 2*x, r: y}]


def test_head_wildcard_and_subst():
    got = list(bindings(F(x), sin(y + 1)))
    assert got == [{F: sin, x: y + 1}]
    assert subst(F(2*x), got[0]) == sin(2*y + 2)


def test_structural_match_requires_equal_constants():
    b_, e_ = symbols("b e")
    assert list(bindings(log(b_**e_), log(x**2))) == [{b_: x, e_: 2}]
    assert list(bindings(log(1/x), log(y**-1))) == [{x: y}]
    assert list(bindings(log(1/x), log(y**2))) == []
    assert list(bindings(log(exp(x)), log(y))) == []


# --- table kinds -----------------------------------------------------------

def test_rule_handler_fires_on_provable_hypothesis():
    class G(Function):
        pass
    rows = [(G(x), x, Q.positive(x)), (G(x), -x, Q.negative(x))]
    handlers_dict["G"] = rule_handler(rows)
    try:
        assert refine(G(y), Q.positive(y)) == y
        assert refine(G(y), Q.negative(y)) == -y
        assert refine(G(y), Q.real(y)) == G(y)
    finally:
        del handlers_dict["G"]


def test_rule_handler_with_head_wildcard_and_partition():
    ints = part("i", Q.integer)
    rows = [(F(ints + r), ints + F(r), true)]          # floor/ceiling distribute over integers
    saved = handlers_dict["floor"], handlers_dict["ceiling"]
    handlers_dict["floor"] = handlers_dict["ceiling"] = rule_handler(rows)
    try:
        from sympy import ceiling
        assert refine(floor(x + n), Q.integer(n)) == n + floor(x)
        assert refine(ceiling(x + n + 1), Q.integer(n)) == n + 1 + ceiling(x)
    finally:
        handlers_dict["floor"], handlers_dict["ceiling"] = saved


def test_identity_handler_does_not_loop_and_respects_ordering():
    """Two identities that undo each other on log(-x) terminate by the ordering."""
    assert refine(log(-x), Q.negative(x)) == log(-x)
    assert refine(log(x), Q.negative(x)) == log(-x) + I*pi


# --- wraps -----------------------------------------------------------------

@pytest.mark.parametrize("t", [Rational(-7, 2), -2, Rational(-1, 3), 0, Rational(1, 2), 2, Rational(9, 2), 7])
def test_wraps_numerically(t):
    from sympy import acos, asin, atan, tan
    assert abs(N(principal(t*pi*I + 1) - log(exp(t*pi*I + 1)))) < 1e-12
    assert abs(N(sawtooth(t, pi) - atan(tan(t)))) < 1e-12 or abs(N(t - round(float(t)))) < 1e-12 and t.is_integer
    assert abs(N(reflect_half(t) - asin(sin(t)))) < 1e-12
    assert abs(N(reflect_full(t) - acos(cos(t)))) < 1e-12
    assert abs(N(fractional(t) - frac(t))) < 1e-12


# --- simple rules and case split -------------------------------------------

@pytest.fixture
def relaxed_log(monkeypatch):
    """The log rows with the domains the branch-cut author is asked to adopt:
    a power needs only one of base or exponent nonzero, a product needs nothing
    (SymPy's zoo arithmetic makes log(0*r) == log(0) + log(r))."""
    from sympy import true
    monkeypatch.setenv(_dispatch.MODE_ENV_VAR, "live")
    from satrefine.handlers_identities._engine import derive, principal
    z, b_, e_, p_, r_ = symbols("z b e p r")
    facts = [(log(exp(z)), principal(z), true), (log(x), log(Abs(x)) + I*arg_(x), ~Q.zero(x))]
    forms = [(b_**e_, e_*log(b_), ~Q.zero(b_) | ~Q.zero(e_)), (p_*r_, log(p_) + log(r_), true)]
    saved = handlers_dict["log"]
    handlers_dict["log"] = identity_handler(derive(facts, forms))
    try:
        yield
    finally:
        handlers_dict["log"] = saved


from sympy import arg as arg_  # noqa: E402


def test_provable_reads_stated_bounds():
    """A stated bound carries realness and decides the sign atoms ask leaves open."""
    t = symbols("t")
    assert provable(Q.real(t), Q.ge(t, 0) & Q.le(t, 1)) is True
    assert provable(Q.real(t**2), Q.ge(t**2, 0) & Q.le(t**2, pi/2)) is True
    assert provable(Q.nonpositive(t), Q.le(t, 0) & Q.ge(t, -pi)) is True
    assert provable(Q.positive(t), Q.gt(t, 0) & Q.lt(t, pi)) is True
    assert provable(Q.positive(t), Q.ge(t, 0) & Q.lt(t, pi)) is None
    assert provable(Q.negative(t), Q.positive(t + pi) & Q.nonpositive(t - pi)) is None
    assert provable(Q.real(t), Q.positive(t + pi)) is True
    assert provable(Q.nonpositive(t - 2*pi), Q.le(t, 2*pi) & Q.ge(t, pi)) is True    # bounds of an affine expression
    assert provable(~Q.integer(t/pi + S.Half), Q.gt(t, -pi/2) & Q.lt(t, pi/2)) is True
    assert provable(~Q.integer(t/pi + S.Half), Q.ge(t, -pi/2) & Q.lt(t, pi/2)) is None


def test_floor_of_a_bounded_symbol():
    """Bounds stated as relations or sign facts on the symbol (or an expression) collapse a floor."""
    t = symbols("t")
    assert refine(floor(t/pi + S.Half), Q.ge(t, pi/2) & Q.lt(t, 3*pi/2)) == 1
    assert refine(floor(t/pi + S.Half), Q.gt(t, -pi/2) & Q.lt(t, pi/2)) == 0
    assert refine(floor(t/(2*pi) + S.Half), Q.positive(t + pi) & Q.nonpositive(t - pi)) != 0   # 1 at t = pi
    assert refine(floor(S.Half - t/(2*pi)), Q.positive(t + pi) & Q.nonpositive(t - pi)) == 0
    assert refine(floor(t/pi + S.Half), Q.nonnegative(t) & Q.le(t, 1)) == 0
    assert refine(floor(t/pi + S.Half), Q.ge(1, t) & Q.le(0, t)) == 0           # reversed relations
    assert refine(floor(t/pi + S.Half), Q.ge(t, -5) & Q.ge(t, 0) & Q.le(t, 1) & Q.le(t, 3)) == 0
    assert refine(floor(t**2/pi + S.Half), Q.ge(t**2, 0) & Q.lt(t**2, pi/2)) == 0
    assert refine(floor(t/pi + S.Half), Q.ge(t, -pi/2) & Q.le(t, pi/2)) != 0   # closed at the jump: two-valued
    assert refine(floor(t/pi + S.Half), Q.real(t)) != 0


def test_two_valued_floor_and_endpoint_split():
    from satrefine.handlers_identities._simple import floor_two_valued
    from satrefine.handlers_identities._engine import endpoint_split
    t = symbols("t")
    closed = Q.ge(t, -pi/2) & Q.le(t, pi/2)
    assert floor_two_valued(floor(t/pi + S.Half), closed) == (0, t, pi/2, 1)
    assert floor_two_valued(floor(t/pi + S.Half), Q.gt(t, -pi/2) & Q.le(t, pi/2)) == (0, t, pi/2, 1)
    assert floor_two_valued(floor(t/pi + S.Half), Q.ge(t, -pi/2) & Q.lt(t, pi/2)) is None
    assert endpoint_split(None, reflect_half(t), closed) == t          # both values agree at pi/2
    assert endpoint_split(None, sawtooth(t, pi), closed) is None       # t versus t - pi at pi/2


def test_floor_of_bounded_head():
    assert refine(floor(S.Half - arg_(y)/(2*pi)), Q.complex(y)) == 0        # arg in (-pi, pi]
    assert refine(floor(S.Half + arg_(y)/(2*pi)), Q.complex(y)) != 0        # (0, 1]: not constant
    assert refine(floor(S.Half + arg_(x)/(2*pi)), Q.imaginary(x)) == 0      # open at pi
    from sympy import atan, ceiling
    assert refine(floor(atan(x)/pi + S.Half), Q.real(x)) == 0
    assert refine(ceiling(atan(x)/pi - S.Half), Q.real(x)) == 0


def test_simple_parts_of_exp_log_and_products():
    from sympy import cos, re, sin
    w, e_, b_ = symbols("w e b")
    assert refine(im(e_*log(b_)), Q.negative(b_) & Q.even(e_)) == pi*e_
    assert refine(Abs(exp(w)), Q.complex(w)) == exp(re(w))
    assert refine(im(exp(w)), Q.complex(w)) == exp(re(w))*sin(im(w))
    assert refine(arg_(x), Q.imaginary(x) & Q.positive(-I*x)) == pi/2


def test_piecewise_branches_refine_under_their_conditions():
    from sympy import Piecewise
    pw = Piecewise((Abs(x), Q.positive(x)), (Abs(x), True))
    assert refine(pw, Q.real(x)) == Abs(x)
    pw = Piecewise((Abs(x), Q.positive(x)), (-x, True))
    assert refine(pw, Q.real(x)) == Piecewise((x, Q.positive(x)), (-x, True))


def test_simple_re_im_never_recurse_on_a_power():
    from sympy import re
    z = symbols("z")
    assert refine(re(x**n), Q.real(x) & Q.integer(n)) == re(x**n)
    assert refine(re(x**z), Q.imaginary(z) & Q.real(x)) == re(x**z)


def test_case_split_resolves_leftover_bookkeeping(relaxed_log):
    assert refine(log(x**2), Q.real(x)) == 2*log(Abs(x))                 # branches generalized by Abs
    assert refine(log(x**2), Q.nonnegative(x)) == 2*log(x)              # one branch, checked at zero
    assert refine(log(x**n), Q.nonzero(x) & Q.even(n)) == n*log(Abs(x))  # agreement modulo expansion
    assert refine(log(x**2), Q.imaginary(x)) == 2*log(Abs(x)) + I*pi     # branches agree
    assert refine(log(x*y), Q.positive(x) & Q.complex(y)) == log(x) + log(y)
    assert refine(log(1/x), Q.imaginary(x)) == -log(x)
    assert refine(log(-x), Q.negative(x)) == log(-x)                     # ordering still holds
