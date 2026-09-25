"""Relation atoms end to end: sympy_api -> engine -> theories.

The dummy adapters of ``theory_harness`` (a dense-order theory standing in
for LRA, an equality-with-uninterpreted-functions theory standing in for
EUF) exercise the wiring, the guards, the unary links and equality
sharing.  The transcription of SymPy's ``test_rel_queries.py`` at the end
runs on the real adapters and is xfail until they land.
"""
import itertools
from fractions import Fraction

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from sympy import Symbol, symbols, Q, Function, Rational, oo, I, S
from sympy.core.relational import Relational

from satassume.relations import Relations, relation_atom, default_specs
from satassume.theory import EqualitySharing
from satassume.formula import Not, P
from satassume.extensions import Args
from satassume.sympy_api import out_of_scope

from theory_harness import (relation_engine, dummy_specs, ask_with, OrderTheory,
                            UFTheory)

x, y, z = symbols("x y z", real=True)
f = Function("f")


@pytest.fixture
def eng():
    return relation_engine(dummy_specs())


# ----------------------------------------------------------------------
# normalisation and scope
# ----------------------------------------------------------------------

def test_normalisation():
    assert relation_atom("gt", x, y) == P("lt", Args((y, x)))
    assert relation_atom("ge", x, y) == Not(P("lt", Args((x, y))))
    assert relation_atom("le", x, y) == Not(P("lt", Args((y, x))))
    assert relation_atom("eq", y, x) == relation_atom("eq", x, y)
    assert relation_atom("ne", x, y) == Not(relation_atom("eq", x, y))


def test_without_adapters_relations_stay_out_of_scope():
    e = relation_engine([])
    assert ask_with(e, Q.lt(x, 2) & Q.gt(x, 3)) is None
    assert ask_with(e, Q.positive(x), x > 0) is None
    assert ask_with(e, Q.positive(x), Q.positive(x)) is True
    assert out_of_scope(Q.lt(x, y)) == "relation"


def test_uninterpreted_relation_gives_none():
    # Only the UF stand-in: lt atoms have no theory, so the query is out of
    # scope (None) even where propositional reasoning alone would decide it.
    e = relation_engine(dummy_specs(order=False))
    assert ask_with(e, Q.lt(x, y), Q.lt(x, y)) is None
    assert ask_with(e, Q.eq(x, y), Q.eq(y, x)) is True
    # nonlinear / unsupported argument for the order stand-in
    e = relation_engine(dummy_specs(uf=False))
    assert ask_with(e, Q.lt(x * y, 1), Q.lt(x * y, 1)) is None


# ----------------------------------------------------------------------
# answers through the dummy theories
# ----------------------------------------------------------------------

@pytest.mark.parametrize("prop, assum, expected", [
    (Q.lt(x, z), Q.lt(x, y) & Q.lt(y, z), True),
    (Q.lt(x, 2) & Q.gt(x, 3), True, False),
    (x > z, (x > y) & (y > z), True),
    (x <= z, (x <= y) & (y <= z), True),
    (x < z, (x <= y) & (y < z), True),
    (Q.lt(x, y), True, None),
    (Q.gt(x, 0), Q.gt(x, 1), True),
    (Q.eq(y, x), Q.eq(x, y), True),
    (Q.eq(x, z), Q.eq(x, y) & Q.eq(y, z), True),
    (Q.eq(x, x), True, True),
    (Q.ne(x, x), True, False),
    (Q.eq(x, 1), ~Q.ne(x, 0), False),
    (Q.eq(x, 0), ~Q.ne(x, 0), True),
    (Q.ne(x, 0), Q.eq(x, 0), False),
    (Q.gt(x, 0), Q.gt(x, 0) & Q.lt(x, 0), "inconsistent"),
    # SymPy's definition: <= is the complement of the reversed <, for any
    # arguments (the corpus has these for plain symbols)
    (Q.le(Symbol("u"), Symbol("v")), Q.gt(Symbol("u"), Symbol("v")), False),
    (Symbol("u") < 0, Symbol("u") >= 0, False),
])
def test_dummy_theory_answers(eng, prop, assum, expected):
    assert ask_with(eng, prop, assum) == expected


@pytest.mark.parametrize("prop, assum, expected", [
    # relation -> unary
    (Q.positive(x), Q.gt(x, y) & Q.positive(y), True),
    (Q.negative(x), Q.lt(x, y) & Q.lt(y, 0), True),
    (Q.nonnegative(x), Q.ge(x, 0), True),
    (Q.zero(x), Q.eq(x, 0), True),
    (Q.nonzero(x), Q.gt(x, 0), True),
    (Q.extended_positive(x), x > 2, True),
    # unary -> relation
    (Q.gt(x, 0), Q.positive(x), True),
    (Q.le(x, 0), Q.positive(x), False),
    (Q.lt(x, y), Q.negative(x) & Q.positive(y), True),
    (Q.eq(x, 0), Q.zero(x), True),
    (Q.ne(x, 0), Q.nonzero(x), True),
    # through the rule base: positive_infinite is not finite
    (Q.positive_infinite(x), Q.gt(x, 1), False),
])
def test_links_to_unary_vocabulary(eng, prop, assum, expected):
    assert ask_with(eng, prop, assum) == expected


def test_old_assumptions_link():
    w = Symbol("w", positive=True)
    e = relation_engine(dummy_specs())
    assert ask_with(e, Q.le(w, 0)) is False
    assert ask_with(e, Q.gt(w, 0)) is True
    w = Symbol("w", nonpositive=True)
    assert ask_with(e, Q.gt(w, 0)) is False


def test_guard_non_real_and_infinite():
    # For non-real or possibly infinite arguments an order atom has no
    # meaning; the answer must not come from the order theory.
    u, v, w = symbols("u v w")                    # no assumptions
    e = relation_engine(dummy_specs())
    assert ask_with(e, Q.lt(u, w), Q.lt(u, v) & Q.lt(v, w)) is None
    # stating realness in the assumptions enables the theory
    real = Q.real(u) & Q.real(v) & Q.real(w)
    assert ask_with(e, Q.lt(u, w), Q.lt(u, v) & Q.lt(v, w) & real) is True
    # extended reals may be infinite: not interpreted
    a, b, c = symbols("a b c", extended_real=True)
    assert ask_with(e, Q.lt(a, c), Q.lt(a, b) & Q.lt(b, c)) is None
    # no contradiction from a free order atom over imaginary terms
    im = Symbol("im", imaginary=True)
    assert ask_with(e, Q.gt(im, 0), Q.gt(im, 0)) is True      # propositional
    assert ask_with(e, Q.positive(im), Q.gt(im, 0)) is False  # rule base: not real


def test_equality_sharing_is_needed_and_works(monkeypatch):
    prop, assum = Q.eq(f(x), f(y)), (x <= y) & (y <= x)
    assert ask_with(relation_engine(dummy_specs()), prop, assum) is True
    monkeypatch.setattr(Relations, "_share", lambda self: False)
    assert ask_with(relation_engine(dummy_specs()), prop, assum) is None


def test_real_euf_with_order_stand_in():
    # the real EUF adapter combined with the dummy order theory (LRA stand-in)
    from satassume.euf_adapter import EUFAdapter
    from satassume.relations import AdapterSpec
    from theory_harness import OrderAdapter
    specs = [AdapterSpec("order", OrderAdapter, True),
             AdapterSpec("euf", EUFAdapter, False)]
    e = relation_engine(specs)
    assert ask_with(e, Q.eq(f(x), f(y)), (x <= y) & (y <= x)) is True
    assert ask_with(e, Q.eq(f(x), f(y)), x <= y) is None
    assert ask_with(e, Q.lt(x, z), Q.lt(x, y) & Q.eq(y, z)) is True
    assert ask_with(e, Q.ne(f(x), f(z)), Q.lt(x, y) & Q.lt(y, z)) is None
    assert ask_with(e, Q.gt(f(x), 0), Q.eq(f(x), f(y)) & Q.gt(f(y), 0)) is None  # f(x) not a symbol for the stand-in


def test_sharing_bookkeeping():
    sh = EqualitySharing()
    assert sh.update([{1, 2}, {3}]) == []
    assert sh.update([{1, 2}, {2, 3}]) == []          # one shared term, no pair
    assert sh.update([{1, 2, 3}, {2, 3, 1}]) == [(2, 1), (2, 3), (1, 3)]
    assert set(sh.shared) == {1, 2, 3}
    assert sh.update([{1, 2, 3}, {1, 2, 3}]) == []


def test_theories_are_per_session(eng):
    ask_with(eng, Q.lt(x, z), Q.lt(x, y) & Q.lt(y, z))
    ask_with(eng, Q.lt(x, y), Q.lt(y, z))
    sessions = [s for s, _ in eng._context_sessions.values()]
    theories = [id(ad.theory) for s in sessions if s.relations
                for ad in s.relations.adapters.values()]
    assert len(theories) == len(set(theories)) > 0


# ----------------------------------------------------------------------
# random formulas versus a grid model checker
# ----------------------------------------------------------------------

_VARS = (x, y, z)
# dense enough: three variables fit strictly between consecutive constants
_GRID = [Fraction(k, 4) for k in range(-4, 13)]
_CONSTS = (0, 1, 2)


def _atoms():
    terms = list(_VARS) + [S(c) for c in _CONSTS]
    rel = st.sampled_from(["lt", "le", "gt", "ge", "eq", "ne"])
    return st.one_of(
        st.tuples(rel, st.sampled_from(_VARS), st.sampled_from(terms)),
        st.tuples(st.sampled_from(["positive", "negative", "zero", "nonnegative"]),
                  st.sampled_from(_VARS)))


def _build(t):
    if t[0] in ("positive", "negative", "zero", "nonnegative"):
        return getattr(Q, t[0])(t[1])
    return getattr(Q, t[0])(t[1], t[2])


def _eval(t, m):
    val = lambda e: m[e] if e in m else Fraction(int(e))
    if len(t) == 2:
        v = m[t[1]]
        return {"positive": v > 0, "negative": v < 0, "zero": v == 0,
                "nonnegative": v >= 0}[t[0]]
    a, b = val(t[1]), val(t[2])
    return {"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b,
            "eq": a == b, "ne": a != b}[t[0]]


@st.composite
def _formulas(draw):
    # a formula as a tree of ('and'|'or'|'not', ...) over atom tuples
    def tree(depth):
        if depth == 0 or draw(st.booleans()):
            return draw(_atoms())
        op = draw(st.sampled_from(["and", "or", "not"]))
        if op == "not":
            return ("not", tree(depth - 1))
        return (op, tree(depth - 1), tree(depth - 1))
    return tree(2)


def _to_sympy(t):
    if t[0] == "not":
        return ~_to_sympy(t[1])
    if t[0] == "and":
        return _to_sympy(t[1]) & _to_sympy(t[2])
    if t[0] == "or":
        return _to_sympy(t[1]) | _to_sympy(t[2])
    return _build(t)


def _holds(t, m):
    if t[0] == "not":
        return not _holds(t[1], m)
    if t[0] == "and":
        return _holds(t[1], m) and _holds(t[2], m)
    if t[0] == "or":
        return _holds(t[1], m) or _holds(t[2], m)
    return _eval(t, m)


@settings(max_examples=60, deadline=None, suppress_health_check=list(HealthCheck))
@given(_formulas(), st.lists(_atoms(), min_size=1, max_size=3))
def test_random_order_queries_are_sound(prop_t, assum_ts):
    from sympy import And
    prop = _to_sympy(prop_t)
    assum = And(*[_build(t) for t in assum_ts])
    if isinstance(prop, bool) or prop in (S.true, S.false) or \
            isinstance(assum, bool) or assum in (S.true, S.false):
        return
    models = [dict(zip(_VARS, vs)) for vs in itertools.product(_GRID, repeat=3)]
    models = [m for m in models if all(_eval(t, m) for t in assum_ts)]
    got = ask_with(relation_engine(dummy_specs()), prop, assum)
    if got == "inconsistent":
        assert not models
    elif got is True:
        assert all(_holds(prop_t, m) for m in models)
    elif got is False:
        assert not any(_holds(prop_t, m) for m in models)
    # the order theory is complete for these atoms: no None when decided
    elif models:
        vals = {_holds(prop_t, m) for m in models}
        assert vals == {True, False}, (prop, assum)


# ----------------------------------------------------------------------
# SymPy's sympy/assumptions/tests/test_rel_queries.py on the real theories
# ----------------------------------------------------------------------

import importlib.util
_HAVE_LRA = importlib.util.find_spec("satassume.lra_adapter") is not None
# strict once LRA is present: these must then pass
_real = pytest.mark.xfail(not _HAVE_LRA, reason="waits for the LRA adapter", strict=True)


@pytest.fixture
def real_eng():
    return relation_engine(None)


@_real
def test_rel_queries(real_eng):
    assert ask_with(real_eng, Q.lt(x, 2) & Q.gt(x, 3)) is False
    assert ask_with(real_eng, Q.positive(x - z), (x > y) & (y > z)) is True
    assert ask_with(real_eng, x + y > 2, (x < 0) & (y < 0)) is False
    assert ask_with(real_eng, x > z, (x > y) & (y > z)) is True


@_real
def test_lra_satask_basics(real_eng):
    e = real_eng
    assert ask_with(e, Q.eq(x, 1), ~Q.ne(x, 0)) is False
    assert ask_with(e, Q.eq(x, 0), ~Q.ne(x, 0)) is True
    assert ask_with(e, ~Q.ne(x, 0), Q.eq(x, 0)) is True
    assert ask_with(e, ~Q.eq(x, 0), Q.eq(x, 0)) is False
    assert ask_with(e, Q.ne(x, 0), Q.eq(x, 0)) is False
    assert ask_with(e, Q.ne(x, x)) is False
    assert ask_with(e, Q.eq(x, x)) is True
    assert ask_with(e, Q.gt(x, 0), Q.gt(x, 1)) is True
    assert ask_with(e, Q.gt(x, 0), True) is None
    im = Symbol("im", imaginary=True)
    # SymPy raises UnhandledInput here; either None or the propositional
    # answer is acceptable, never a theory answer
    assert ask_with(e, Q.gt(im * I, 0), Q.gt(im * I, 0)) in (True, None)


@_real
def test_old_assumptions(real_eng):
    e = real_eng
    for kw, prop, want in [
            ("positive", Q.le, False), ("positive", Q.gt, True),
            ("negative", Q.lt, True), ("negative", Q.ge, False),
            ("zero", Q.eq, True), ("zero", Q.ne, False),
            ("nonzero", Q.ne, True), ("nonpositive", Q.le, True),
            ("nonpositive", Q.gt, False), ("nonnegative", Q.ge, True),
            ("nonnegative", Q.lt, False)]:
        w = Symbol("w", real=True, **{kw: True})
        assert ask_with(e, prop(w, 0)) is want, (kw, prop)
    w = Symbol("w", nonzero=True, real=True)
    assert ask_with(e, Q.eq(w, 1)) is None


@_real
def test_all_pred(real_eng):
    assert ask_with(real_eng, Q.extended_positive(x), x > 2) is True
    assert ask_with(real_eng, Q.positive_infinite(x)) is False
    assert ask_with(real_eng, Q.negative_infinite(x)) is False


@_real
def test_number_line_properties(real_eng):
    a, b, c = symbols("a b c", real=True)
    e = real_eng
    assert ask_with(e, a <= c, (a <= b) & (b <= c)) is True
    assert ask_with(e, a < c, (a <= b) & (b < c)) is True
    assert ask_with(e, a < c, (a < b) & (b <= c)) is True
    assert ask_with(e, a + c <= b + c, a <= b) is True
    assert ask_with(e, a - c <= b - c, a <= b) is True


@pytest.mark.xfail(reason="XFAIL in SymPy too: needs nonlinear reasoning", strict=False)
def test_failing_number_line_properties(real_eng):
    a, b, c = symbols("a b c", real=True)
    e = real_eng
    assert ask_with(e, a*c <= b*c, (a <= b) & (c > 0) & ~Q.zero(c)) is True
    assert ask_with(e, a/c <= b/c, (a <= b) & (c > 0) & ~Q.zero(c)) is True
    assert ask_with(e, a*c >= b*c, (a <= b) & (c < 0) & ~Q.zero(c)) is True
    assert ask_with(e, a/c >= b/c, (a <= b) & (c < 0) & ~Q.zero(c)) is True
    assert ask_with(e, -a >= -b, a <= b) is True
    assert ask_with(e, 1/a >= 1/b, (a <= b) & Q.positive(x) & Q.positive(b)) is True
    assert ask_with(e, 1/a >= 1/b, (a <= b) & Q.negative(x) & Q.negative(b)) is True


def test_equality(real_eng):   # EUF
    e = real_eng
    assert ask_with(e, Q.eq(x, x)) is True
    assert ask_with(e, Q.eq(y, x), Q.eq(x, y)) is True
    assert ask_with(e, Q.eq(y, x), ~Q.eq(z, z) | Q.eq(x, y)) is True
    assert ask_with(e, Q.eq(x, z), Q.eq(x, y) & Q.eq(y, z)) is True


def test_equality_failing(real_eng):
    # XFAIL in SymPy; answered here by predicate transfer (satassume.transfer)
    e = real_eng
    assert ask_with(e, Q.prime(x), Q.eq(x, y) & Q.prime(y)) is True
    assert ask_with(e, Q.real(x), Q.eq(x, y) & Q.real(y)) is True
    # x, y are declared real here, so imaginary(y) is inconsistent by itself
    assert ask_with(e, Q.imaginary(x), Q.eq(x, y) & Q.imaginary(y)) == "inconsistent"
    u, v = symbols("u v")
    assert ask_with(e, Q.imaginary(u), Q.eq(u, v) & Q.imaginary(v)) is True


def test_unhandled_matrix_queries(real_eng):
    from sympy import MatrixSymbol
    X = MatrixSymbol("X", 2, 2)
    assert ask_with(real_eng, Q.lt(X, 2) & Q.gt(X, 3)) is None
