"""``tools/refine_fuzz.py``'s extended family (``--ext``): infinite sample
points, relations with infinite bounds, SymPy's conventions at infinity
classified instead of reported, and the default case streams unchanged.

The wrong rewrites below are the phase-3 bounds bugs B1-B7 (issue #10): the
checker must find each of them at +-oo without being pointed at the point.
"""
from __future__ import annotations

import hashlib
import importlib
import random
import sys
from pathlib import Path

import pytest
from sympy import (KroneckerDelta, Piecewise, Q, RisingFactorial, S, acoth, acsch, atan2, coth, csch, exp, gamma, log,
                   oo, pi, sign, symbols, zoo, Eq, I, Add, Pow, im)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
_argv, sys.argv = sys.argv, sys.argv[:1]
fz = importlib.import_module("refine_fuzz")
rd = importlib.import_module("refine_differential")
sys.argv = _argv

x, y, z, n, m, k = symbols("x y z n m k")


def _check(expr, refined, combos, rels=(), seed=0):
    pts = fz.ext_points([expr, refined], combos, rels, random.Random(seed))
    return fz.ext_compare(expr, refined, pts)


# --- the bounds bugs are found at +-oo --------------------------------------------------------

WRONG = [   # (input, wrong rewrite, combos, relations): B1-B7 at the refine-identities f83f195 engine
    (Piecewise((0, x < oo), (1, True)), S.Zero, {x: ()}, (Q.gt(x, 1),)),                       # B1
    (Piecewise((0, Eq(x, 2 * x)), (1, True)), S.One, {x: ()}, (Q.gt(x, 1),)),                  # B2
    (KroneckerDelta(x, 2 * x), S.Zero, {x: ()}, (Q.gt(x, 1),)),                                # B3
    (sign(exp(-x)), S.One, {x: ()}, (Q.gt(x, 1),)),                                            # B4
    (log(x ** n), n * log(x), {x: (), n: ("real",)}, (Q.gt(x, 1),)),                           # B5
    (acsch(csch(x)), x, {x: ()}, (Q.gt(x, 1),)),                                               # B6
    (RisingFactorial(x, y), gamma(x + y) / gamma(x), {x: (), y: ("positive", "integer")}, (Q.gt(x, 1),)),  # B7
    (acsch(csch(x)), x, {x: ("extended_positive",)}, ()),
    (sign(exp(-x)), S.One, {x: ("infinite", "extended_positive")}, ()),
]


@pytest.mark.parametrize("expr, wrong, combos, rels", WRONG)
def test_bounds_bugs_are_found_at_infinity(expr, wrong, combos, rels):
    _, ce, _ = _check(expr, wrong, combos, rels)
    assert ce is not None
    pt, a, b, kind = ce
    assert kind in ("infinite point", "undefined output")
    assert any(fz.is_inf(v) for v in pt.values())


RIGHT = [   # correct at +-oo, and at finite points
    (acoth(coth(x)), x, {x: ()}, (Q.gt(x, 0),)),
    (sign(exp(-x)), S.One, {x: ()}, (Q.gt(x, 1), Q.lt(x, oo))),
    (log(x ** n), n * log(x), {x: ("finite",), n: ("real",)}, (Q.gt(x, 1),)),
    (Piecewise((0, x < oo), (1, True)), S.One, {x: ()}, (Q.ge(x, oo),)),
]


@pytest.mark.parametrize("expr, right, combos, rels", RIGHT)
def test_right_rewrites_pass(expr, right, combos, rels):
    n_ok, ce, st = _check(expr, right, combos, rels)
    assert ce is None and n_ok > 0


def test_infinite_points_are_checked():
    n_ok, ce, st = _check(acoth(coth(x)), x, {x: ()}, (Q.gt(x, 0),))
    assert st["checked at an infinity"] >= 1


# --- SymPy's conventions are classified, not reported -----------------------------------------

CONVENTIONS = [
    (log(exp(k)), k, {k: ("extended_real",)}, (), "zoo vs signed infinity (log(0) = zoo)"),  # log(exp(-oo))
    (Pow(Pow(y + 1, -1), -1, evaluate=False), y + 1, {y: ("extended_positive",)}, (),
     "zoo vs signed infinity (1/0 = zoo)"),
    (atan2(x, x), pi / 4, {x: ()}, (Q.gt(x, 1),), "atan2 of two infinities"),
    (exp(log(x), evaluate=False), x, {x: ("extended_negative",)}, (), "log of a non-positive infinity"),  # log(-oo) = oo
]


@pytest.mark.parametrize("expr, refined, combos, rels, label", CONVENTIONS)
def test_conventions_are_counted_not_reported(expr, refined, combos, rels, label):
    _, ce, st = _check(expr, refined, combos, rels)
    assert ce is None
    assert st["convention: " + label] >= 1


def test_undefined_input_is_skipped():
    # oo - oo is nan: the input has no value there, so the point is skipped and counted
    _, ce, st = _check(Add(x, -x, 1, evaluate=False), S.One, {x: ("infinite", "extended_positive")})
    assert ce is None and st["input undefined"] >= 1


# --- the samplers ----------------------------------------------------------------------------

@pytest.mark.parametrize("combo", fz.EXT_COMBOS)
def test_ext_samples_satisfy_their_predicates(combo):
    rng = random.Random(1)
    for _ in range(30):
        v = fz.draw_ext(combo, rng, inf_ok=True)
        assert v is not None
        assert all(fz.EXT_PREDS[p][1](v) for p in combo)


def test_values_classify_infinities():
    assert fz.ext_value(x, {x: oo}) == ("inf", 1)
    assert fz.ext_value(-x + 1, {x: oo}) == ("inf", -1)
    assert fz.ext_value(I * x, {x: oo})[0] == "inf"
    assert fz.ext_value(1 / x, {x: S.Zero}) == "zoo"
    assert fz.ext_value(x - x + 0 * x, {x: oo}) in ("nan", 0j)
    assert fz.ext_value(KroneckerDelta(x, 2 * x), {x: oo}) == 1     # SymPy leaves it unevaluated; Eq decides
    assert fz.ext_value(KroneckerDelta(x, 2 * x), {x: S(3)}) == 0


def test_relations_at_infinity():
    assert fz.rel_holds_ext(Q.gt(x, 1), {x: oo}) is True
    assert fz.rel_holds_ext(Q.lt(x, oo), {x: oo}) is False
    assert fz.rel_holds_ext(Q.ge(x, oo), {x: oo}) is True
    assert fz.rel_holds_ext(Q.gt(x, 1), {x: zoo}) is None
    assert fz.rel_holds_ext(Q.eq(x, y), {x: -oo, y: -oo}) is True


def test_ext_stream_is_deterministic_and_fired_heads_exist():
    heads = set()
    for c in range(200):
        g = fz.ext_generate(5, c)
        assert g == fz.ext_generate(5, c)
        if g:
            heads.add(g[0])
    assert {"Piecewise", "acot_cot", "acoth_coth", "asech_sech", "acsch_csch"} <= heads


# --- the default streams are unchanged -------------------------------------------------------

def test_default_scalar_and_matrix_streams_unchanged():
    """The gates' differential seeds compare 1:1 with earlier baselines only if these streams are the same."""
    h = hashlib.sha256()
    for s in (2, 3, 7):
        for c in range(0, 1500, 7):
            g = rd.generate(s, c)
            h.update(repr(None if g is None else (g[0], str(g[1]), str(g[2]), sorted((str(q), v) for q, v in g[3].items()),
                                                  str(g[4]))).encode())
    assert h.hexdigest()[:16] == "30b0eb22641f2de1"
    h = hashlib.sha256()
    for c in range(0, 300, 3):
        g = fz.mat_generate(2, c)
        h.update(repr(None if g is None else (g[0], str(g[1]), str(g[2]))).encode())
    assert h.hexdigest()[:16] == "548bbfac92699b94"
