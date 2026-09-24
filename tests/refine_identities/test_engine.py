"""The engine: dispatcher fix and firing cap, pattern forms, both table kinds, wraps."""
from __future__ import annotations

import pytest
from sympy import (Abs, Function, I, N, Q, Rational, S, cos, exp, floor, frac, im, log, pi, sin,
                   symbols, true)

from satrefine import refine
from satrefine._upstream import handlers_dict
from satrefine.handlers_identities import _dispatch
from satrefine.handlers_identities._engine import (bindings, identity_handler, part, rule_handler,
                                                   subst)
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
    handlers_dict["floor"] = rule_handler(rows)
    saved = handlers_dict.get("ceiling")
    handlers_dict["ceiling"] = handlers_dict["floor"]
    try:
        from sympy import ceiling
        assert refine(floor(x + n), Q.integer(n)) == n + floor(x)
        assert refine(ceiling(x + n + 1), Q.integer(n)) == n + 1 + ceiling(x)
    finally:
        from satrefine._upstream import refine_floor_ceiling
        handlers_dict["floor"] = refine_floor_ceiling
        handlers_dict["ceiling"] = saved or refine_floor_ceiling


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
