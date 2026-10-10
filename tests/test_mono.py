"""MONO (#149, T5): the table of satassume.theories.mono and its lemmas in
the relation glue (``Relations._mono_*``).

The table tests check every piece and row with SymPy's own evaluation at
sample points, ``0`` and ``+-oo``; the end-to-end tests ask through the
public API, each in a fresh engine.
"""
from __future__ import annotations

import itertools

import pytest
from sympy import (Abs, Q, Rational, S, Symbol, acot, asinh, atan, ceiling, cosh,
                   exp, floor, log, oo, pi, sinh, sqrt, symbols, tanh)

from satassume.engine import Engine
from satassume.sympy_api import ask
from satassume.theories import mono

x, y, z = symbols("x y z")
n = Symbol("n", integer=True)
p = Symbol("p", positive=True)
r = Symbol("r", real=True)

FUNCS = [exp, log, atan, tanh, sinh, asinh, cosh, acot,
         lambda t: t**3, lambda t: t**2, lambda t: t**-1, lambda t: t**-2,
         lambda t: t**Rational(1, 3), lambda t: sqrt(t), lambda t: t**Rational(-3, 2),
         lambda t: t**4, lambda t: t**-3]
POINTS = [-oo, S(-100), S(-3), S(-1), -S.Half, -Rational(1, 100), S.Zero,
          Rational(1, 100), S.Half, S.One, S(2), S(7), S(100), oo]
LO = {"-oo": lambda v: True, "0": lambda v: v >= 0, "0+": lambda v: v > 0}
HI = {"oo": lambda v: True, "0": lambda v: v <= 0, "0-": lambda v: v < 0}


def _spec(f):
    sp = mono.spec(f(x))
    assert sp is not None and sp.arg == x
    return sp


@pytest.mark.parametrize("f", FUNCS)
def test_pieces_are_strictly_monotone_at_sample_points(f):
    sp = _spec(f)
    for piece in sp.pieces:
        pts = [v for v in POINTS if LO[piece.lo](v) and HI[piece.hi](v)]
        vals = [sp.apply(v) for v in pts]
        for v, fv in zip(pts, vals):
            assert fv.is_extended_real, (f(x), v, fv)
        for (a, fa), (b, fb) in itertools.combinations(zip(pts, vals), 2):
            assert (fb > fa if piece.dir > 0 else fa > fb) == True, (f(x), piece, a, b)


@pytest.mark.parametrize("f", FUNCS)
def test_inverse_candidates_are_preimages(f):
    sp = _spec(f)
    lo, hi, nonzero = sp.inv_range
    for d in [S(-3), -S.Half, Rational(1, 3), S.One, S(2), S(5)]:
        if (lo is not None and not d > lo or hi is not None and not d < hi
                or nonzero and d == 0):
            continue
        for c in sp.inverse(d):
            fc = sp.apply(c)
            if fc.is_extended_real and any(
                    LO[q.lo](c.evalf()) and HI[q.hi](c.evalf()) for q in sp.pieces):
                if sp.exact:
                    assert abs((fc - d).evalf(30)) < 1e-25, (f(x), d, c)


@pytest.mark.parametrize("f", [exp, atan, tanh, cosh, acot, lambda t: t**2,
                               Abs, floor, ceiling])
def test_rows_hold_at_sample_points(f):
    sp = mono.spec(f(x))
    for row in sp.rows:
        for v in POINTS:
            if row.guard in ("real",) and not v.is_finite:
                continue
            if row.guard == "extended_nonnegative" and v < 0:
                continue
            if row.guard == "extended_nonpositive" and v > 0:
                continue
            app = f(v)
            holds = bool(row.lhs(v, app) < row.rhs(v, app))
            assert holds == row.positive, (f(x), row, v)


def test_unlisted_terms_have_no_spec():
    for t in [x, x + 1, sinh(x) * y, x**y, (x + 1)**pi, exp(S(2)), tanh(x) + 1]:
        assert mono.spec(t) is None


# the cases of proposal T5 in #149: None without MONO
P5 = [
    (Q.extended_positive(log(x)), Q.gt(x, 1)),
    (Q.positive(log(x)), Q.gt(x, 1) & Q.finite(x)),
    (Q.gt(exp(x), 1), Q.positive(x)),
    (Q.lt(atan(x), 2), Q.real(x)),
    (Q.ge(Abs(x), x), Q.real(x)),
    (Q.le(floor(x), x), Q.real(x)),
    (Q.lt(x - floor(x), 1), Q.real(x)),
    (Q.gt(x**2, 4), Q.gt(x, 2)),
    (Q.extended_positive(sqrt(x) - 1), Q.gt(x, 1)),
    (Q.negative(log(x)), Q.gt(x, 0) & Q.lt(x, 1)),
    (Q.zero(log(x)), Q.eq(x, 1)),
    (Q.gt(log(x), log(y)), Q.gt(x, y) & Q.gt(y, 0)),
    (Q.lt(exp(x), exp(y)), Q.lt(x, y)),
    (Q.gt(x**3, y**3), Q.gt(x, y) & Q.real(x) & Q.real(y)),
    (Q.transcendental(log(x)), Q.algebraic(x) & Q.positive(x) & Q.ne(x, 1)),
]


@pytest.mark.parametrize("prop,assum", P5)
def test_issue_cases(prop, assum):
    assert ask(prop, assum, engine=Engine()) is True


MORE = [
    # inverse through a nested application and a scaled argument
    (Q.gt(x, 0), Q.gt(exp(log(x) + 1), exp(S(2))), True),
    (Q.lt(r, 1), Q.lt(tanh(3*r - 3), 0), True),
    (Q.ge(x, 1), Q.nonnegative(x) & Q.eq(x**3, 8), True),
    (Q.gt(x, 1), Q.eq(exp(x), 2), False),
    (Q.eq(exp(x), 1), Q.eq(x, 0), True),
    (Q.eq(x**2, 4), Q.eq(x, -2), True),
    # exact inverses: atan(tan(1/2)) stays unevaluated in SymPy
    (Q.gt(r, 1), Q.gt(atan(r), pi/4), True),
    (Q.gt(r, 0), Q.gt(atan(r), S.Half), True),
    # ranges
    (Q.lt(tanh(r), 1), Q.real(r), True),
    (Q.ge(cosh(r), 1), Q.real(r), True),
    (Q.gt(acot(p), 0), Q.positive(p), True),
    (Q.nonnegative(x**2 + exp(y)), Q.real(x) & Q.real(y) & Q.gt(x, y), True),
    # sums: a forward image bounds the term
    (Q.ge(n + exp(n), 4), Q.ge(n, 2), True),
]


@pytest.mark.parametrize("prop,assum,want", MORE)
def test_more_answers(prop, assum, want):
    assert ask(prop, assum, engine=Engine()) is want


SOUND = [
    # pair guards (a wrong orientation gave True / False here)
    (Q.ge(n**4, r**4), Q.negative(n) & Q.le(n, p) & Q.lt(n, r)),
    (Q.eq(-1/y**3, r**-3), Q.eq(y, z) & Q.lt(y, r)),
    # log(-oo) = oo: log(x) > 0 says nothing about the sign of x
    (Q.positive(x), Q.gt(log(x), 0)),
    # a non-real x with a real x**2
    (Q.positive(x), Q.gt(x**2, 4)),
    (Q.gt(x, 2), Q.gt(x**2, 4)),
]


@pytest.mark.parametrize("prop,assum", SOUND)
def test_no_answer_where_none_holds(prop, assum):
    assert ask(prop, assum, engine=Engine()) is None


def test_no_error_on_zero_threshold_of_negative_power():
    assert ask(Q.eq(n**-3, x**-3), Q.eq(0, n) & Q.gt(n, x), engine=Engine()) in (True, False, None)


def test_cascade_between_sibling_applications_ends():
    assert ask(Q.le(n**4, (n - 1)**4), Q.nonnegative(n), engine=Engine()) is None


@pytest.mark.parametrize("assum", [
    Q.ge(tanh(r - 1), 1),
    Q.eq(cosh(2*p), log(2)),
    Q.gt(-1, r) & Q.eq(Abs(r), 1),
    Q.lt(4, p) & Q.lt(log(p), log(2)),
    Q.gt(-2, x) & Q.le(acot(x), -3),
])
def test_inconsistent_assumptions_found(assum):
    with pytest.raises(ValueError):
        ask(Q.real(x), assum, engine=Engine())


# -- the sign rows MONO replaces (SIGN_FUNCS: atan, tanh, sinh, log) ----------

_xp = Symbol("xp", positive=True)
_xr = Symbol("xr", real=True)

SIGNS = [
    # unary queries: no relation atom, the glue is on for the application
    (Q.positive(atan(x)), Q.positive(x), True),
    (Q.negative(atan(x)), Q.nonnegative(x), False),
    (Q.nonnegative(tanh(x)), Q.extended_nonnegative(x), True),
    (Q.zero(tanh(x)), Q.zero(x), True),
    (Q.negative(sinh(x + 1)), Q.negative(x + 1), True),
    (Q.extended_positive(sinh(x)), Q.extended_negative(x), False),
    (Q.positive(atan(_xp)), True, True),
    (Q.negative(atan(_xp) + _xp), True, False),
    # in any position of the cone
    (Q.positive(atan(x) * y), Q.positive(x) & Q.positive(y), True),
    (Q.negative(sinh(x) * y), Q.negative(x) & Q.positive(y), True),
    (Q.positive(tanh(atan(x))), Q.positive(x), True),
    # log against x - 1 (template rows; MONO in relational queries)
    (Q.positive(log(x)), Q.positive(x - 1), True),
    (Q.negative(log(x)), Q.positive(x) & Q.negative(x - 1), True),
    (Q.zero(log(x)), Q.zero(x - 1), True),
    (Q.positive(x - 1), Q.positive(x) & Q.positive(log(x)), True),
    (Q.negative(log(_xp + 1)), True, False),
    (Q.positive(log(x) * y), Q.positive(y) & Q.gt(x, 1), None),   # x = oo
    # log(u) = 0 -> u = 1 holds for any u (exp(log(u)) = u): no guard
    (Q.eq(x, 1), Q.zero(log(x)), True),
    (Q.zero(x), Q.zero(log(x + 1)), True),
    (Q.zero(x), Q.zero(atan(x)), True),
    # closed arguments keep their template rows (no MONO lemma without a
    # free symbol)
    (Q.positive(sinh(4)), True, True),
    (Q.negative(log(Rational(1, 2))), True, True),
    (Q.negative(tanh(-3)), True, True),
    (Q.eq(sinh(4), sinh(y)), Q.gt(-S.Half, y), False),
]


@pytest.mark.parametrize("prop,assum,want", SIGNS)
def test_signs_from_mono(prop, assum, want):
    assert ask(prop, assum, engine=Engine()) is want


def test_sign_terms_and_scope():
    from satassume.scope import mono_terms, scope_of_atoms
    from satassume.sat.formula import P
    assert mono.sign_terms(atan(x) * y) == {atan(x), x}
    assert mono.sign_terms(atan(_xp + 1)) == {atan(_xp + 1), _xp + 1, _xp}
    assert mono.sign_terms(log(x)) == frozenset()     # log keeps its rows
    assert mono.sign_terms(sinh(4)) == frozenset()
    assert mono.sign_terms(exp(x) + cosh(y)) == frozenset()
    atoms = [P("positive", atan(x) * y), P("positive", y)]
    assert mono_terms(atoms) == {atan(x), x}
    sc = scope_of_atoms(atoms)
    assert sc.glue and not sc.transfer and {atan(x), x} <= sc.linked_terms
    assert not scope_of_atoms([P("positive", exp(x)), P("real", x)]).glue
