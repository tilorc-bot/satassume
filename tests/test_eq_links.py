"""Equalities from infinities and differences, and sign facts on two sums.

* ``Relations._eq_links``: ``positive_infinite(a) & positive_infinite(b) ->
  eq(a, b)`` (and ``negative_infinite``), ``zero(a - b) -> eq(a, b)`` and
  ``nonzero(a - b) -> ~eq(a, b)``, in every domain: a zero or nonzero
  difference is finite, and equal infinite sides have a nan difference.
* ``Session._affine_links``: sign atoms on two sums sharing a symbol start
  the relation glue, so LRA compares them (``Q.negative(1 - x)`` from
  ``Q.positive(x - 1)``) without a relation atom.

The model checks evaluate every atom on concrete values (the extended
reals, ``I``, ``1 + I`` and ``zoo``; a difference may be ``nan``): a
definite answer must hold at every point satisfying the assumptions.
"""
from __future__ import annotations

import itertools

import pytest

sympy = pytest.importorskip("sympy")
from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import Function, I, Integral, Q, S, nan, oo, symbols, zoo
from sympy.logic.boolalg import And

from satassume import DictCache, Engine
from satassume.sympy_api import ask

x, y, t = symbols("x y t")
f, g = Function("f"), Function("g")
F, G = f(1), g(1)                     # shared subterms without free symbols
INT = Integral(g(t), (t, 0, 1))


def _ask(prop, assum=True):
    try:
        return ask(prop, assum, Engine(cache=DictCache()))
    except ValueError:
        return "inconsistent"


@pytest.mark.parametrize("prop, assum, expected", [
    # equal infinities
    (Q.eq(x, y), Q.positive_infinite(x) & Q.positive_infinite(y), True),
    (Q.eq(x, y), Q.negative_infinite(x) & Q.negative_infinite(y), True),
    (Q.ne(x, y), Q.positive_infinite(x) & Q.negative_infinite(y), True),
    (Q.eq(x, y), Q.infinite(x) & Q.infinite(y), None),           # zoo, or oo and -oo
    (Q.eq(x, y), Q.positive_infinite(x) & Q.infinite(y), None),
    # a zero or nonzero difference
    (Q.eq(x, y), Q.zero(x - y), True),
    (Q.eq(x, y), Q.zero(y - x), True),
    (Q.ne(x, y), Q.nonzero(x - y), True),
    (Q.ne(x, y), Q.nonzero(y - x), True),
    (Q.ne(x, y), Q.zero(x - y), False),
    # sides with a common symbol: SymPy's x - (x + y) is -y, but at x = oo the
    # difference is nan, so a nonzero y does not make x + y differ from x
    (Q.eq(x, x + y), Q.positive(y), None),
    (Q.ne(x, x + y), Q.positive(y) & Q.finite(x), None),
    (Q.eq(x, y), Q.positive(x - y), False),
    (Q.eq(x, y), Q.extended_positive(x - y), None),              # x - y = oo needs x != y ...
    (Q.eq(x, y), ~Q.zero(x - y), None),                          # ... but x = y = oo has x - y = nan
    (Q.zero(x - y), Q.eq(x, y), None),                           # x = y = oo
    # sides with a common term without free symbols: SymPy cancels it too, but
    # it may be infinite (both sides oo while x - y is nonzero) or the
    # cancelled part nan (both sides nan, so not equal, while x - y is zero)
    (Q.ne(x + F, y + F), Q.nonzero(x - y) & Q.positive_infinite(F), None),
    (Q.eq(x + F, y + F), Q.nonzero(x - y) & Q.positive_infinite(F), None),
    (Q.ne(x + F, F), Q.nonzero(x), None),
    (Q.ne(x + INT, y + INT), Q.nonzero(x - y) & Q.positive_infinite(INT), None),
    (Q.ne(x + INT, INT), Q.nonzero(x), None),
    (Q.ne(2*F + x, F + y), Q.nonzero(F + x - y) & Q.positive_infinite(F), None),  # merged
    (Q.eq(x + F - G, y + F - G),
     Q.zero(x - y) & Q.positive_infinite(F) & Q.positive_infinite(G), None),
    (Q.eq(x + F*G, y + F*G), Q.zero(x - y) & Q.zero(F) & Q.positive_infinite(G), None),
    (Q.ne(x + F, y), Q.nonzero(x + F - y), True),               # nothing cancelled
    (Q.eq(x + F, y), Q.zero(x + F - y), True),
    (Q.ne(x + 1, y + 2), Q.nonzero(x - y - 1), True),           # numbers are added up
    (Q.ne(x + I, y + I), Q.nonzero(x - y), True),               # ... and finite constants
    # sign facts on two sums: LRA compares them without a relation atom
    (Q.negative(1 - x), Q.positive(x - 1), True),
    (Q.positive(x - 1), Q.negative(1 - x), True),
    (Q.negative(1 - x), Q.positive(x - 1) & Q.real(x), True),
    (Q.negative(2 - x), Q.positive(x - 3), True),
    (Q.nonnegative(x - 2), Q.positive(x - 3), True),
    (Q.positive(x - 3), Q.positive(x - 2), None),
    (Q.negative(x + y), Q.negative(x - 1) & Q.negative(y + 1), True),
    (Q.extended_negative(1 - x), Q.extended_positive(x - 1), True),  # x may be oo, but
    #   extended_real(x - 1) & real(-1) gives extended_real(x) (the Add rule of T1)
    (Q.negative(1 - x), Q.extended_positive(x - 1), None),       # x = oo
], ids=str)
def test_answers(prop, assum, expected):
    assert _ask(prop, assum) is expected


# ----------------------------------------------------------------------
# models
# ----------------------------------------------------------------------

_VALUES = [-oo, S(-1), S(0), S(1), S(2), oo, I, 1 + I, zoo]
_PREDS = ["zero", "nonzero", "positive", "negative", "extended_positive", "extended_negative",
          "positive_infinite", "negative_infinite", "finite", "real"]
_TERMS = [x, y, x - y, y - x, x - 1, 1 - x, x + y]


def _unary(pred, v):
    if v is nan:
        return False
    if v is zoo:
        return pred == "infinite"
    real, fin = v.is_extended_real, v.is_finite
    return bool({
        "zero": v == 0, "nonzero": real and fin and v != 0,
        "positive": real and fin and v > 0, "negative": real and fin and v < 0,
        "extended_positive": real and v > 0, "extended_negative": real and v < 0,
        "positive_infinite": v is oo, "negative_infinite": v is -oo,
        "finite": fin, "real": real and fin,
    }[pred])


def _holds(t, env):
    tag = t[0]
    if tag == "not":
        return not _holds(t[1], env)
    if tag == "u":
        return _unary(t[1], S(t[2]).xreplace(env))
    a, b = S(t[1]).xreplace(env), S(t[2]).xreplace(env)
    equal = a is not nan and b is not nan and a == b     # value equality; Eq(nan, nan) is False
    return equal == (tag == "eq")


def _to_sympy(t):
    tag = t[0]
    if tag == "not":
        return ~_to_sympy(t[1])
    if tag == "u":
        return getattr(Q, t[1])(t[2])
    return getattr(Q, tag)(t[1], t[2])


_POINTS = [dict(zip((x, y), v)) for v in itertools.product(_VALUES, repeat=2)]


def _check(prop_t, assum_ts, eng, points=_POINTS):
    prop = _to_sympy(prop_t)
    assum = And(*[_to_sympy(t) for t in assum_ts])
    if prop in (S.true, S.false) or assum in (S.true, S.false):
        return
    try:
        got = ask(prop, assum, eng)
    except ValueError:
        got = "inconsistent"
    for env in points:
        if not all(_holds(t, env) for t in assum_ts):
            continue
        assert got != "inconsistent", (prop, assum, env)
        if got is not None:
            assert _holds(prop_t, env) is got, (prop, assum, env, got)


_SIDES = [x, y, x + y, x - 1, y + 1]
_EQS = [(op, a, b) for op in ("eq", "ne") for a, b in itertools.combinations(_SIDES, 2)]
_ATOMS = [("u", p, t) for p in _PREDS for t in _TERMS] + _EQS


def test_eq_and_ne_against_models():
    """Every ``eq``/``ne`` atom under every one-atom assumption (and its
    negation), and every atom under every ``eq``/``ne`` atom."""
    eng = Engine(cache=DictCache())
    for a in _ATOMS:
        for a_t in (a, ("not", a)):
            for p in _EQS:
                _check(p, [a_t], eng)
                _check(a, [p], eng)


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.sampled_from(_ATOMS),
       st.lists(st.tuples(st.sampled_from(_ATOMS), st.booleans()), min_size=1, max_size=3))
def test_fuzz_against_models(prop_t, assum):
    _check(prop_t, [("not", a) if neg else a for a, neg in assum], Engine(cache=DictCache()))


# sides sharing ``f(1)``, which SymPy cancels in the difference although it
# may be infinite.  (A shared part that may be nan, ``f(1)*g(1)``, is left
# out: congruence closure already equates ``x + f(1)*g(1)`` with
# ``y + f(1)*g(1)`` from ``x = y``, though both are nan at ``0*oo``.)
_F_POINTS = [dict(zip((x, y, F), v)) for v in itertools.product(
    [-oo, S(0), S(1), oo, I, zoo], [-oo, S(0), S(1), oo, zoo], [-oo, S(0), oo, zoo])]
_F_SIDES = [x + F, y + F, F, 2*F + y, x - F, x]
_F_EQS = [(op, a, b) for op in ("eq", "ne") for a, b in itertools.combinations(_F_SIDES, 2)]
_F_UNARY = [("u", p, e) for p in ("zero", "nonzero", "positive_infinite", "finite")
            for e in (x - y, x, F, F + y - x, x - F - y)]


def test_shared_subterm_against_models():
    eng = Engine(cache=DictCache())
    for a in _F_UNARY + _F_EQS:
        for a_t in (a, ("not", a)):
            for p in _F_EQS:
                _check(p, [a_t], eng, _F_POINTS)
    for p in _F_EQS:
        for a, b in itertools.combinations(_F_UNARY, 2):
            _check(p, [a, b], eng, _F_POINTS)


def test_glue_made_equality_gets_user_clauses_when_asked():
    """S1 (#53 stage 5): ``ask(Q.real(w), S)`` makes ``eq(q, w)`` as an
    interface equality (glue) in the session of ``S``; asking that atom
    afterwards must give it the user-atom clauses (``nonzero(q - w) ->
    ~eq(q, w)``, :meth:`Relations._eq_links`) as a fresh session does, so
    the reused session answers False like a fresh one (``w`` is
    irrational, ``q`` rational)."""
    yr = symbols("y", real=True)
    q = symbols("q", rational=True)
    m = symbols("m", nonnegative=True, integer=True)
    w = symbols("w", nonzero=True)
    s = Q.eq(yr, q) & Q.irrational(-1 / (m * w * yr))
    e = Engine(cache=DictCache(), transfer=False)
    ask(Q.real(w), s, e)
    assert ask(Q.eq(q, w), s, e) is False
    assert ask(Q.eq(q, w), s, Engine(cache=DictCache(), transfer=False)) is False
