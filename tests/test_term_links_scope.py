"""Facts about a term reach an equivalent term without a relation atom
(nightly-invariants findings of run 36953488998, package NB).

* A *split zero* (``Q.nonnegative(t) & Q.nonpositive(t)``, and the other
  pairs of sign atoms that can give ``zero(t)``) of a ``t`` under an
  application is read as ``zero(t)`` is (``relations.zero_args``): its twin
  ``eq(t, 0)`` links ``f(t)`` to ``f(0)``.  Was None where the ``zero``
  spelling answered (``transfer`` profile, ``default`` and ``tight``).
* A sum ``r + c`` (``c`` a nonzero Rational, ``r`` a sum) has the derived
  node ``r`` (``templates.core._shift_template``), so ``r``, ``r + 1`` and
  ``r + 2`` share their shift-invariant facts.  Was None for
  ``irrational(6*k + 3*x + EulerGamma + 1)`` under ``irrational(6*k + 3*x +
  EulerGamma)`` (``related`` profile, ``lean`` and ``tight``).
* Not fixed, pinned (``harness/repros/invariants/
  I5-shifted-equality-notransfer``): under ``transfer=False``, ``Q.eq(x +
  1, 1)`` given ``Q.eq(x + 3/2, 3/2)`` stays None.

Every expected answer is the correct one, checked against the value
semantics in the comments, and agrees with ``ask_ref``.
"""
import itertools

import pytest
from sympy import (Abs, EulerGamma, Function, I, Q, Rational, S, Symbol, exp, log, nan, oo,
                   pi, sqrt, symbols, zoo)

from satassume.engine import DictCache, Engine
from satassume.formula import P
from satassume.ref import ask_ref
from satassume.relations import zero_args, zero_twins
from satassume.sympy_api import ask
from satassume.templates.core import _shift_rules

f = Function("f")
z, x, y, w = symbols("z x y w")
k = Symbol("k", integer=True, positive=True)

CONFIGS = {"default": {}, "whole": {"relevance": False},
           "tight": {"discovery_budget": 12}, "notransfer": {"transfer": False}}


def _ask(p, s, cfg):
    try:
        return ask(p, s, Engine(cache=DictCache(), **CONFIGS[cfg]))
    except Exception as ex:          # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


def _ref(p, s, cfg):
    return ask_ref(p, s, transfer=CONFIGS[cfg].get("transfer", True))


# --------------------------------------------------------------------------
# split zeros
# --------------------------------------------------------------------------

t = 3 * z - pi
SPLITS = {
    "nonneg-nonpos": lambda e: Q.nonnegative(e) & Q.nonpositive(e),
    "ext": lambda e: Q.extended_nonnegative(e) & Q.extended_nonpositive(e) & Q.finite(e),
    "not-pos-not-neg": lambda e: ~Q.positive(e) & ~Q.negative(e) & Q.real(e),
    "nonneg-not-pos": lambda e: Q.nonnegative(e) & ~Q.positive(e),
}
# (proposition, the rest of the set): with t = 0, f(t) = f(0)
SHAPES = {
    # the nightly case: Abs(f(0)) composite, so Abs(f(t)) is finite
    "finite": (Q.irrational(t) | Q.finite(Abs(f(t))), Q.composite(Abs(f(0)))),
    # the nested case: f(f(0)) an integer, so f(f(t)) is not transcendental
    "nested": (Q.transcendental(f(f(t))), Q.integer(f(f(0)))),
}
WANT = {"finite": True, "nested": False}


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("split", list(SPLITS))
def test_split_zero_in_the_set_answers_as_zero(split, shape, cfg):
    p, rest = SHAPES[shape]
    zero = _ask(p, rest & Q.zero(t), cfg)
    want = None if cfg == "notransfer" else WANT[shape]
    assert zero == want
    assert _ask(p, rest & SPLITS[split](t), cfg) == zero
    assert _ref(p, rest & SPLITS[split](t), cfg) == zero


@pytest.mark.parametrize("cfg", ["default", "whole"])
def test_split_zero_in_the_proposition(cfg):
    # the set says Abs(f(t)) is no integer while f(0) is 2: t is not 0
    s = ~Q.integer(Abs(f(t))) & Q.eq(f(0), 2)
    assert _ask(~(Q.nonnegative(t) & Q.nonpositive(t)), s, cfg) == _ask(~Q.zero(t), s, cfg) == True


def test_the_split_condition():
    tw = zero_twins((P("nonnegative", x), P("nonpositive", x), P("finite", f(x))))
    assert [a.pred for a in tw] == ["eq"]
    assert zero_args((P("nonnegative", x), P("nonpositive", x))) == (x,)
    assert zero_args((P("positive", x), P("negative", x))) == (x,)
    assert zero_args((P("extended_nonnegative", x), P("positive", x))) == (x,)
    # one side only, or two terms: no split
    assert zero_args((P("nonnegative", x), P("positive", y))) == ()
    assert zero_args((P("nonnegative", x), P("negative", x))) == ()
    assert zero_args((P("nonzero", x), P("real", x))) == ()
    # a number is never a twin's side
    assert zero_args((P("nonnegative", S(2)), P("nonpositive", S(2)))) == ()
    # no application over x: no twin, as for zero(x)
    assert zero_twins((P("nonnegative", x), P("nonpositive", x))) == []


# --------------------------------------------------------------------------
# sums that differ by a rational constant
# --------------------------------------------------------------------------

T = 6 * k + 3 * x + EulerGamma


def test_the_nightly_shifted_sum():
    a = Q.irrational(T) & Q.extended_negative(-3 * T)
    for cfg in CONFIGS:
        assert _ask(Q.irrational(T + 1) & Q.extended_negative(-3 * T), a, cfg) is True
        assert _ref(Q.irrational(T + 1) & Q.extended_negative(-3 * T), a, cfg) is True


# (proposition, set, answer): each holds for every value of the symbols
SHIFTED = [
    (Q.irrational(T + 1), Q.irrational(T), True),
    (Q.rational(T + Rational(1, 2)), Q.rational(T), True),
    (Q.algebraic(T - 3), Q.transcendental(T), False),
    (Q.integer(T + 2), Q.integer(T), True),
    (Q.integer(T + Rational(1, 2)), Q.integer(T), False),
    (Q.even(T + 2), Q.even(T), True),
    (Q.odd(T + 1), Q.even(T), True),
    (Q.even(T - 3), Q.even(T), False),
    (Q.real(T + 1), Q.real(T), True),
    (Q.finite(T + 1), ~Q.finite(T), False),
    (Q.imaginary(x + y + 1), Q.imaginary(x + y), False),
    (Q.positive_infinite(T - 7), Q.positive_infinite(T), True),
    # through the derived node r = x + y of both sums
    (Q.irrational(x + y + 2), Q.irrational(x + y + 1), True),
    (Q.integer(x + y - 1), Q.integer(x + y + 1), True),
    # signs: r >= 0 gives r + 1 > 0; r + 1 <= 0 gives r < 0
    (Q.positive(T + 1), Q.positive(T), True),
    (Q.positive(x + y + 1), Q.nonnegative(x + y), True),
    (Q.negative(x + y), Q.nonpositive(x + y + 1), True),
    (Q.negative(x + y - 1), Q.nonpositive(x + y), True),
    # not entailed: r + 1 > 0 says nothing of the sign of r
    (Q.positive(x + y), Q.positive(x + y + 1), None),
]


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("i", range(len(SHIFTED)))
def test_shifted_sums_share_their_facts(i, cfg):
    p, a, want = SHIFTED[i]
    assert _ask(p, a, cfg) is want
    assert _ref(p, a, cfg) is want


def test_two_term_sums_have_no_shift_node():
    from satassume.templates.core import add_templates
    # x + 1: x is an argument already; the Add rules relate them
    assert not isinstance(add_templates(x + 1), list)
    assert len(add_templates(x + y + 1)) == 2
    assert not isinstance(add_templates(x + y + pi), list)


# value-level check of the shift rules: every rule holds at every sample
# value r whose facts SymPy decides, for every sign and parity of c
VALUES = [S(0), S(1), S(-2), S(3), Rational(1, 2), Rational(-7, 3), sqrt(2), -sqrt(3),
          pi, -pi + 1, EulerGamma, I, 1 + I, sqrt(2) * I, oo, -oo, zoo, nan]
CS = [S(1), S(2), S(-3), S(-4), Rational(1, 2), Rational(-5, 3)]


@pytest.mark.parametrize("c", CS, ids=str)
def test_shift_rules_hold_at_values(c):
    rules = _shift_rules(bool(c.is_Integer), bool(c.is_Integer and c.p % 2), bool(c.is_positive))
    assert rules
    checked = 0
    for r in VALUES:
        vals = {1: r, 0: r + c}

        def holds(lit):
            slot, pred, pos = lit
            e = vals[slot]
            if pred in ("positive_infinite", "negative_infinite"):
                v = None if e is nan else e == (oo if pred[0] == "p" else -oo)
            else:
                v = getattr(e, "is_" + pred)
            return None if v is None else (v == pos)
        for prem, concl in rules:
            ps = [holds(li) for li in prem]
            cs = [holds(li) for li in concl]
            if None in ps or None in cs:
                continue
            checked += 1
            assert not all(ps) or any(cs), (c, r, prem, concl)
    assert checked > 100


# --------------------------------------------------------------------------
# pinned, not fixed
# --------------------------------------------------------------------------

def test_shifted_equality_without_transfer_is_none():
    # x + 3/2 = 3/2 holds iff x = 0, for every complex x; without transfer
    # nothing makes x real, and LRA's twin of the equality is guarded by
    # real(x) (harness/repros/invariants/I5-shifted-equality-notransfer)
    p = Q.eq(x + 1, 1)
    a = Q.eq(x + Rational(3, 2), Rational(3, 2))
    assert _ask(p, a, "default") is True
    assert _ask(p, a, "notransfer") is None
    assert _ref(p, a, "notransfer") is None


# --------------------------------------------------------------------------
# the derived r does not spend the discovery budget (PR #113 review)
# --------------------------------------------------------------------------

from harness.state import PRESETS  # noqa: E402

_xr, _yr = symbols("x y", real=True)
_zp, _wp = symbols("z w", positive=True)
_a, _b, _c = symbols("a b c", nonnegative=True)
_xi, _yi = symbols("x y", integer=True)
_kr = Symbol("k", real=True)
_ki = Symbol("k", integer=True)
_w = Symbol("w")
_xp, _yp = symbols("x y", positive=True)
_kn = Symbol("k", nonnegative=True)
_wi = Symbol("w", integer=True, positive=True)

#: (proposition, set, the answer under every preset but those listed):
#: each answered so at 51e8c58 and lost to the budget by the first version
#: of the shift node, whose r weighed in the cone
BUDGET = [
    (Q.positive(exp(_xr + _yr + 1) + log(_wp + _zp + 2) + 1), True, True,
     {"budget": None, "boundary": None}),
    (Q.real(sqrt(_a + _b + _c + 1)), True, True, {"boundary": None}),
    (Q.integer(_xi * _yi + exp(_xi) - Rational(3, 2)), True, False, {"boundary": None}),
    (Q.finite(sqrt(_kr + sqrt(_yr) + 1)), True, True, {"boundary": None}),
    # found by a sum-heavy fuzz against 51e8c58 under tight and lean
    (Q.finite(_ki + _w + 9 * _xp**2 * _yp), Q.transcendental(3 * sqrt(_w) * _yp + _xp + 1),
     True, {"budget": None, "boundary": None}),
    (Q.positive(3 * _kn * _xp * z + _xp + sqrt(_kn + 5) + 1),
     Q.algebraic(2 * _kn + _wi + 1) & Q.negative(3 * _kn * _xp * z + _xp + sqrt(_kn + 5) + Rational(5, 2)),
     False, {"budget": None, "boundary": None, "norel": None}),
]


@pytest.mark.parametrize("cfg", list(PRESETS))
@pytest.mark.parametrize("i", range(len(BUDGET)))
def test_shift_node_spends_no_budget(i, cfg):
    p, a, want, other = BUDGET[i]
    try:
        got = ask(p, a, engine=PRESETS[cfg].make())
    except ValueError:
        got = "error"
    assert got == other.get(cfg, want)


def test_free_derived_node_weighs_nothing():
    eng = Engine()
    n = _xp + 3 * sqrt(_w) * _yp + 1
    r = n - 1
    c, w, _rel = eng._cone_info(n)
    assert r in c                               # visited like a derived node
    cr, wr, _ = eng._cone_info(r)
    assert w == wr                              # n counted, r not: same size
    # named otherwise (r asked about), r weighs again
    assert eng._union([n, r])[1] == w + 1


def test_shifted_equality_without_transfer_in_the_proposition_is_none():
    # the proposition form of the pinned case (pinned separately: #115
    # keeps prop and restate variants apart): same cause, real(x) missing
    a = Q.eq(x + 1, 1)
    p = Q.eq(-1, -1 - x)
    assert _ask(p, a, "default") is True
    assert _ask(p, a, "notransfer") is None
    assert _ref(p, a, "notransfer") is None
    assert _ask(p, a & Q.real(x), "notransfer") is True
