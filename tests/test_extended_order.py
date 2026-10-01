"""Order relations over the extended reals (``satassume.relations``,
"Meaning"): ``a < b`` holds iff both sides are extended reals and
``a < b`` there; ``a <= b`` likewise (it is not the negation of
``b < a``); a side that is no extended real (``I``, ``zoo``, ``nan``)
makes every order atom false.  ``Eq``/``Ne`` are unchanged.

The model checks at the end evaluate every atom on concrete values of the
symbols (``-oo``, finite rationals, ``oo``, ``I``, ``zoo``): SymPy
compares extended reals exactly, and anything that is no extended real
(``I``, ``zoo``, ``oo - oo = nan``, ``oo + I``) makes an order atom false.
A definite answer must hold at every point satisfying the assumptions.
"""
from __future__ import annotations

import itertools
from fractions import Fraction as F

import pytest

sympy = pytest.importorskip("sympy")
from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import (Eq, I, Integral, Matrix, Q, S, im, nan, oo, pi, re, sin, sqrt,
                   symbols, zoo)
from sympy.logic.boolalg import And

from satassume import DictCache, Engine
from satassume import constfield as cf
from satassume import lra_adapter as ad
from satassume.sympy_api import ask

x, y = symbols("x y")
xr = symbols("xr", real=True)


def _ask(prop, assum=True, **kw):
    try:
        return ask(prop, assum, Engine(cache=DictCache(), **kw))
    except ValueError:
        return "inconsistent"


# ----------------------------------------------------------------------
# the adapter: sides with oo summands
# ----------------------------------------------------------------------

@pytest.mark.parametrize("atom, expected", [
    (Q.lt(x, oo), (({x: F(1)}, 0), ({}, 1))),
    (Q.lt(-oo, x), (({}, -1), ({x: F(1)}, 0))),
    (Q.lt(x + oo, 2 * y - 1), (({x: F(1)}, 1), ({y: F(2)}, 0))),
    (Q.lt(-x, pi), (({x: F(-1)}, 0), ({}, 0))),            # pi: a number, dropped
    (Q.lt(pi * x, 1), (({x: cf.PI}, 0), ({}, 0))),
    (Q.lt(2 * (x + y), y - oo), (({x: F(2), y: F(2)}, 0), ({y: F(1)}, -1))),
], ids=str)
def test_order_sides(atom, expected):
    assert ad.order_sides(atom) == expected


@pytest.mark.parametrize("atom", [
    Q.lt(x, zoo), Q.lt(x, nan), Q.lt(oo * x, 1), Q.lt(sin(x + oo), 1),
    Q.lt(x, 0.5), Q.lt(I * x, 1), Q.lt(x, I), Q.eq(x, oo), Q.lt(Matrix([x]), 1),
], ids=str)
def test_order_sides_unread(atom):
    assert ad.order_sides(atom) is None


# ----------------------------------------------------------------------
# the semantics, end to end (checked by hand; SymPy's ask in a comment
# where it differs)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("prop, assum, expected", [
    # pinned by the owner: x = oo satisfies x > 0, and positive is finite
    (Q.positive(x), Q.gt(x, 0), None),
    (Q.extended_positive(x), Q.gt(x, 0), True),                   # SymPy None
    (Q.extended_real(x), Q.lt(x, 1), True),                       # SymPy None
    (Q.extended_negative(x), Q.le(x, -1), True),                  # SymPy None
    # the motivating queries
    (Q.real(x), Q.nonnegative(x) & Q.lt(x, oo), True),
    (Q.positive(x), Q.gt(x, 1) & Q.lt(x, oo), True),              # SymPy None
    (Q.positive(x), Q.gt(x, 1) & Q.lt(x, oo) & Q.extended_real(x), True),
    # e < oo is extended_real(e) & ~positive_infinite(e)
    (Q.lt(x, oo), Q.extended_real(x) & ~Q.positive_infinite(x), True),
    (Q.lt(x, oo), Q.real(x), True),                               # SymPy None
    (Q.lt(x, oo), Q.negative_infinite(x), True),                  # SymPy None
    (Q.lt(x, oo), Q.positive_infinite(x), False),
    (Q.lt(x, oo), True, None),
    (Q.positive_infinite(x), Q.lt(x, oo), False),                 # SymPy None
    (Q.extended_real(x), Q.ge(x, -oo) & Q.le(x, oo), True),       # SymPy None
    (Q.extended_real(x), Q.le(x, oo), True),                      # SymPy None
    (Q.real(x), Q.ge(x, -oo) & Q.le(x, oo), None),                # x = oo
    (Q.positive_infinite(x), Q.ge(x, oo), True),                  # SymPy None
    (Q.finite(x), Q.gt(x, -oo) & Q.lt(x, oo), True),              # SymPy None
    (Q.gt(x, oo), True, False),                                   # SymPy None
    (Q.lt(x, -oo), True, False),                                  # SymPy None
    # ~(a < b) is not a >= b: x may be no extended real
    (Q.ge(x, oo), ~Q.lt(x, oo), None),
    (Q.ge(x, oo), ~Q.lt(x, oo) & Q.extended_real(x), True),
    (Q.le(x, x), True, None),
    (Q.le(x, x), Q.extended_real(x), True),
    (Q.le(x, y), Q.gt(x, y), False),
    (Q.lt(x, y), Q.lt(x, 0) & Q.lt(0, y), True),                  # SymPy None
    # sides that are no extended real: the atom is false
    (Q.lt(x, zoo), True, False),                                  # SymPy None
    (Q.ge(x, zoo), True, False),                                  # SymPy None
    (Q.lt(I, 1), True, False),                                    # SymPy None
    (Q.le(nan, 1), True, False),                                  # SymPy None
    (Q.gt(x, 0), Q.imaginary(x), False),                          # SymPy None
    # infinite terms with coefficients
    (Q.lt(x, x + 1), Q.real(x), True),
    (Q.lt(x, x + 1), Q.extended_real(x), None),                   # x = oo; SymPy True (wrong)
    (Q.lt(x, x + 1), Q.positive_infinite(x), False),
    (Q.lt(-x, x), Q.positive_infinite(x), True),                  # SymPy None
    (Q.lt(-x, 2 * x - 1), Q.negative_infinite(x), False),
    (Q.lt(x + y, 0), Q.positive_infinite(x) & Q.negative_infinite(y), False),
    (Q.lt(x + oo, 1), True, False),                               # SymPy None
    (Q.lt(-oo, x + 1), Q.real(x), True),                          # SymPy None
    (Q.lt(x - oo, y), Q.real(x) & Q.real(y), True),
    (Q.lt(x - oo, y), Q.real(x), None),                           # y = -oo
    # closed sides
    (Q.lt(-oo, oo), True, True),
    (Q.lt(oo, oo), True, False),
    (Q.le(oo, oo), True, True),
    (Q.le(-oo, -oo), True, True),
    (Q.lt(pi, oo), True, True),
    (Q.gt(pi, oo), True, False),
    (Q.gt(sqrt(2), -oo), True, True),
    # irrational constants are still bounded LRA terms
    (Q.gt(x, 0) & Q.lt(x, pi), Q.positive(x) & Q.lt(x, 3), True),
    (Q.lt(x, pi), Q.lt(x, 3), True),
    # equality is unchanged: it asserts nothing about the sides
    (Q.extended_real(x), Q.eq(x, y), None),
    (Q.eq(x, I), Q.eq(I, x), True),
    (Q.ne(x, 1), Q.lt(x, 1), True),
    # Eq with oo / -oo is linked to positive_infinite / negative_infinite
    (Q.eq(x, oo), Q.gt(x, 1) & ~Q.finite(x), True),               # SymPy None
    (Q.eq(x, -oo), Q.lt(x, 1) & Q.infinite(x), True),             # SymPy None
    (Q.eq(x, oo), Q.positive_infinite(x), True),
    (Q.positive_infinite(x), Q.eq(x, oo), True),
    (Q.negative_infinite(x), Q.eq(-oo, x), True),
    (Q.ne(x, oo), Q.real(x), True),
    (Q.eq(x + 1, oo), Q.positive_infinite(x), True),
    (Q.eq(x, oo) | Q.eq(x, -oo), Q.extended_real(x) & Q.infinite(x), True),
    (Q.eq(x, oo), Q.infinite(x), None),                           # x = -oo, zoo
    (Q.eq(zoo, oo), True, False),
    (Q.eq(-oo, oo), True, False),
])
def test_answers(prop, assum, expected):
    assert _ask(prop, assum) is expected


@pytest.mark.parametrize("prop, assum, expected", [
    # re(zoo) = im(zoo) = nan, so re(x) <= oo fails at x = zoo
    (Q.le(re(x), oo), True, None),                                # SymPy True (wrong)
    (Q.le(re(x), oo), Q.complex(x), True),
    (Q.extended_real(re(x)), Q.extended_real(x), True),           # SymPy None
    (Q.extended_real(im(x)), Q.extended_real(x), True),           # SymPy None
    (Q.extended_real(im(x)), True, None),
    # 1**oo = 1**-oo = nan: a positive base needs a finite exponent
    (Q.extended_nonnegative(x**y), Q.positive(x) & Q.extended_real(y), None),
    (Q.extended_nonnegative(x**y), Q.positive(x) & Q.real(y), True),
    (Q.le(0, x**y), Q.positive(x) & Q.extended_real(y), None),
])
def test_sides_that_may_be_nan(prop, assum, expected):
    assert _ask(prop, assum) is expected


def test_relationals_and_is_true_have_the_same_meaning():
    for p in (x < 1, x <= 1, x > 1, x >= 1, Q.is_true(x < 1), Q.is_true(x >= 1)):
        assert _ask(Q.extended_real(x), p) is True
    assert _ask(Q.extended_real(x), Eq(x, 1) | Q.lt(x, 1)) is True    # x = 1 or x < 1
    assert _ask(Q.extended_real(x), Eq(x, I) | Q.lt(x, 1)) is None


@pytest.mark.parametrize("assum", [
    Q.real(x) & Q.lt(x, 0.5), Q.real(x) & Q.lt(I * x, 1),
    Q.real(x) & Q.lt(Integral(sin(y), (y, 0, 1)), x),
    Q.real(x) & Q.lt(oo * x, 1), Q.real(x) & Q.lt(x * zoo, 1),
], ids=str)
def test_unreadable_relations_are_free_atoms(assum):
    # no theory reads the relation: by default a free atom, so the query is
    # decided propositionally; uninterpreted="none" (opt-in) gives None
    assert _ask(Q.real(x), assum) is True
    assert _ask(Q.real(x), assum, uninterpreted="none") is None


def test_unreadable_relation_still_asserts_extended_real_sides():
    # an unread atom is kept (the default uninterpreted="free")
    assert _ask(Q.extended_real(x), Q.lt(x, 0.5)) is True
    assert _ask(Q.extended_real(x), Q.lt(x, 0.5), uninterpreted="none") is None


def test_inconsistent_assumptions():
    for assum in (Q.lt(x, -oo), Q.gt(x, oo), Q.lt(x, zoo), Q.ge(x, oo) & Q.real(x),
                  Q.gt(x, 3) & Q.le(x, pi / 2), Q.positive_infinite(x) & Q.lt(x, oo),
                  Q.gt(x, 0) & Q.imaginary(x)):
        assert _ask(Q.real(x), assum) == "inconsistent", assum


# ----------------------------------------------------------------------
# model checks
# ----------------------------------------------------------------------

_UNARY = ["extended_real", "real", "finite", "positive", "nonnegative",
          "extended_positive", "extended_negative", "extended_nonnegative",
          "positive_infinite", "negative_infinite", "infinite", "zero"]
_EXT = [-oo, S(-3), S(0), S(1), S(2), S(3), oo]
_NONREAL = [I, zoo]


def _unary(pred, v):
    return bool(_unary_value(pred, v))


def _unary_value(pred, v):
    if v is I:
        return pred == "finite"
    if v is zoo:
        return pred == "infinite"
    fin = v.is_finite
    return {
        "extended_real": True, "real": fin, "finite": fin,
        "positive": fin and v > 0, "nonnegative": fin and v >= 0,
        "extended_positive": v > 0, "extended_negative": v < 0,
        "extended_nonnegative": v >= 0,
        "positive_infinite": v is oo, "negative_infinite": v is -oo,
        "infinite": not fin, "zero": v == 0,
    }[pred]


def _order(op, a, b):
    """``a op b`` on values: false unless both are extended reals."""
    for v in (a, b):
        if v is nan or v.is_extended_real is not True:
            return False
    return bool({"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op])


def _holds(t, env):
    tag = t[0]
    if tag == "not":
        return not _holds(t[1], env)
    if tag in ("and", "or"):
        a, b = _holds(t[1], env), _holds(t[2], env)
        return (a and b) if tag == "and" else (a or b)
    if tag == "u":
        return _unary(t[1], env[t[2]])
    _, op, a, b = t
    a, b = S(a).subs(env), S(b).subs(env)
    if op in ("eq", "ne"):
        return (a == b) == (op == "eq")         # value equality, any domain
    return _order(op, a, b)


def _to_sympy(t):
    tag = t[0]
    if tag == "not":
        return ~_to_sympy(t[1])
    if tag in ("and", "or"):
        a, b = _to_sympy(t[1]), _to_sympy(t[2])
        return (a & b) if tag == "and" else (a | b)
    if tag == "u":
        return getattr(Q, t[1])(t[2])
    _, op, a, b = t
    return getattr(Q, op)(a, b)


def _check(prop_t, assum_ts, syms, values, eng=None):
    prop = _to_sympy(prop_t)
    assum = And(*[_to_sympy(t) for t in assum_ts])
    if prop in (S.true, S.false) or assum in (S.true, S.false):
        return
    try:
        got = ask(prop, assum, eng or Engine(cache=DictCache()))
    except ValueError:
        got = "inconsistent"
    for vals in itertools.product(values, repeat=len(syms)):
        env = dict(zip(syms, vals))
        if not all(_holds(t, env) for t in assum_ts):
            continue
        assert got != "inconsistent", (prop, assum, env)
        if got is not None:
            assert _holds(prop_t, env) is got, (prop, assum, env, got)


_OPS = ["lt", "le", "gt", "ge"]
_BOUNDS = [oo, -oo, S(0), S(2)]
_ONE = ([("u", p, x) for p in _UNARY]
        + [("r", op, x, b) for op in _OPS for b in _BOUNDS]
        + [("r", op, b, x) for op in _OPS for b in _BOUNDS]
        + [("r", op, x, b) for op in ("eq", "ne") for b in _BOUNDS])


def test_every_pair_of_atoms_against_models():
    """Every one-symbol atom as the query under every atom (and its
    negation) as the assumption, x over the extended reals, I and zoo."""
    eng = Engine(cache=DictCache())
    for p in _ONE:
        for a in _ONE:
            for a_t in (a, ("not", a)):
                _check(p, [a_t], [x], _EXT + _NONREAL, eng)


_TERMS = [x, y, -x, x + y, x - y, 2 * x - y, x + 1, x * y, x + oo, y - oo]
_SIDES = _TERMS + [oo, -oo, S(0), S(2)]
_VALUES_2 = [-oo, S(-1), S(0), S(2), oo, I, zoo]


@st.composite
def _atoms2(draw):
    if draw(st.integers(0, 3)) == 0:
        return ("u", draw(st.sampled_from(_UNARY)), draw(st.sampled_from([x, y])))
    if draw(st.integers(0, 4)) == 0:
        return ("r", draw(st.sampled_from(["eq", "ne"])), draw(st.sampled_from(_BOUNDS)),
                draw(st.sampled_from(_TERMS)))
    return ("r", draw(st.sampled_from(_OPS)), draw(st.sampled_from(_SIDES)),
            draw(st.sampled_from(_TERMS)))


@st.composite
def _formulas2(draw, depth=2):
    if depth == 0 or draw(st.booleans()):
        return draw(_atoms2())
    op = draw(st.sampled_from(["and", "or", "not"]))
    if op == "not":
        return ("not", draw(_formulas2(depth - 1)))
    return (op, draw(_formulas2(depth - 1)), draw(_formulas2(depth - 1)))


@settings(max_examples=200, deadline=None, suppress_health_check=list(HealthCheck))
@given(_formulas2(), st.lists(_atoms2(), min_size=1, max_size=3))
def test_fuzz_two_symbols_against_models(prop_t, assum_ts):
    _check(prop_t, assum_ts, [x, y], _VALUES_2)
