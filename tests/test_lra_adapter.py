"""Tests for the SymPy -> LRA adapter (satassume/lra_adapter.py).

Assumed interface (agreed with lra-impl):

* ``to_constraint(atom)`` -> ``(payload, positive)`` | ``True`` | ``False`` |
  ``None``.  ``payload`` is ``(terms, constant, strict, equality)`` meaning
  ``sum(c*t) (<|<=|==) constant``; ``positive`` is False for ``Q.ne``/``Ne``
  (the atom is the negation of the equality payload).  True/False: the
  relation has no terms left (its value for all finite reals).  None: not
  interpreted (left to the SAT layer).
* ``terms(atom)``: the opaque terms, including ones that cancel.
* ``LRAAdapter(theory=None).register(solver, var, atom) -> bool``.

Semantics are checked by evaluation, not by comparing payload structure:
the payload, evaluated at a random rational point (each opaque term
substituted and evaluated exactly), must agree with SymPy's own evaluation
of the relation at that point.

The last sections go end to end through ``satassume.sympy_api.ask``
(relation atoms are routed to the theories by satassume/relations.py):
sympy/assumptions/tests/test_rel_queries.py transcribed (a ``None`` where
SymPy expects a definite answer is an xfail, a *wrong* definite answer
always fails), and a Hypothesis fuzz of random linear relations against
the Fourier-Motzkin oracle.
"""
from __future__ import annotations

import importlib
import os
import random
from fractions import Fraction as F

import pytest

sympy = pytest.importorskip("sympy")
from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import (E, Eq, Function, I, MatrixSymbol, Ne, Q, Rational, S, Symbol,
                   Tuple, cos, nan, oo, pi, sin, sqrt, symbols, zoo)
from sympy.core.relational import Ge, Gt, Le, Lt
from sympy.calculus.accumulationbounds import AccumBounds

from test_lra import _hang_guard, holds, payload_constraint  # noqa: F401

try:
    ad = importlib.import_module(os.environ.get("SATASSUME_LRA_ADAPTER", "satassume.lra_adapter"))
except ImportError as e:  # pragma: no cover
    ad = None
    _ERR = e
needs_adapter = pytest.mark.skipif(ad is None, reason="satassume.lra_adapter not available")

x, y, z = symbols("x y z")
f = Function("f")

_REL = {"lt": Lt, "le": Le, "gt": Gt, "ge": Ge, "eq": Eq, "ne": Ne}
_PRED = {"lt": Q.lt, "le": Q.le, "gt": Q.gt, "ge": Q.ge, "eq": Q.eq, "ne": Q.ne}


def pred_atom(kind, a, b):
    return _PRED[kind](a, b)


def rel_atom(kind, a, b):
    """A Relational; None if SymPy evaluates it on construction."""
    r = _REL[kind](a, b)
    return r if r not in (S.true, S.false) else None


def sympy_value(kind, a, b, point):
    """SymPy's truth value of ``a kind b`` at ``point``."""
    r = _REL[kind](a.subs(point), b.subs(point))
    assert r in (S.true, S.false), r
    return r is S.true


def payload_value(res, point):
    """Evaluate a to_constraint result at ``point``."""
    if res is True or res is False:
        return res
    p, positive = res
    vals = {}
    terms, rhs, strict, eq = p
    for t, c in (terms.items() if isinstance(terms, dict) else terms):
        v = sympy.sympify(t).subs(point)
        assert v.is_Rational, (t, v)
        vals[t] = F(int(v.p), int(v.q))
    return holds(payload_constraint(p, positive), vals)


def random_point(rng, syms=(x, y, z)):
    return {s: Rational(rng.randint(-6, 6), rng.choice([1, 2, 3])) for s in syms}


# ----------------------------------------------------------------------
# Semantics by evaluation
# ----------------------------------------------------------------------

LINEAR = [
    (x, 0), (x, 1), (0, x), (2 * x, 3), (x + y, 1), (x, y), (y, x),
    (x + 1, y - 2), (Rational(1, 3) * x - y, Rational(-2, 7)), (-x, -y),
    (2 * (x + y), x), (x + y + z, x - z), (x / 2, y / 3), (3, x + 2 * y - z),
    (x + y, y + x), (x - x + y, 0),
]
KINDS = ["lt", "le", "gt", "ge", "eq", "ne"]


@needs_adapter
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("pair", range(len(LINEAR)))
def test_linear_atoms_mean_what_sympy_means(kind, pair):
    a, b = map(sympy.sympify, LINEAR[pair])
    rng = random.Random(pair * 31 + KINDS.index(kind))
    forms = [pred_atom(kind, a, b), Q.is_true(_REL[kind](a, b, evaluate=False))]
    r = rel_atom(kind, a, b)
    if r is not None:
        forms.append(r)
    for atom in forms:
        res = ad.to_constraint(atom)
        assert res is not None, f"{atom} is linear but not interpreted"
        for _ in range(25):
            pt = random_point(rng)
            assert payload_value(res, pt) == sympy_value(kind, a, b, pt), (atom, pt, res)
        # points on the boundary matter most for strict/non-strict
        for sx in (-1, 0, 1):
            pt = random_point(rng)
            diff = (a - b).subs({y: pt[y], z: pt[z]})
            if diff.has(x) and diff.diff(x) != 0:
                root = sympy.solve(diff, x)
                if root:
                    pt[x] = root[0] + Rational(sx, 1000)
                    assert payload_value(res, pt) == sympy_value(kind, a, b, pt)


@st.composite
def lin_expr(draw):
    e = S(draw(st.integers(-3, 3))) / draw(st.integers(1, 3))
    for s in (x, y, z):
        c = draw(st.integers(-3, 3))
        if c:
            e += Rational(c, draw(st.integers(1, 3))) * s
    return e


@needs_adapter
@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(lin_expr(), lin_expr(), st.sampled_from(KINDS), st.integers(0, 10**6))
def test_fuzz_linear_semantics(a, b, kind, seed):
    rng = random.Random(seed)
    res = ad.to_constraint(pred_atom(kind, a, b))
    assert res is not None
    for _ in range(10):
        pt = random_point(rng)
        assert payload_value(res, pt) == sympy_value(kind, a, b, pt)


# ----------------------------------------------------------------------
# Normalisation
# ----------------------------------------------------------------------

@needs_adapter
@pytest.mark.parametrize("a,b", [(x, y), (x + 1, 2 * y), (x, 3), (3, x), (x + y, z - 1)])
def test_symmetry_gives_identical_payloads(a, b):
    a, b = sympy.sympify(a), sympy.sympify(b)
    assert ad.to_constraint(Q.lt(a, b)) == ad.to_constraint(Q.gt(b, a))
    assert ad.to_constraint(Q.le(a, b)) == ad.to_constraint(Q.ge(b, a))
    assert ad.to_constraint(Q.eq(a, b)) == ad.to_constraint(Q.eq(b, a))
    assert ad.to_constraint(Q.ne(a, b)) == ad.to_constraint(Q.ne(b, a))
    assert ad.to_constraint(Q.lt(a, b)) == ad.to_constraint(Q.lt(-b, -a))
    assert ad.to_constraint(Q.lt(a, b)) == ad.to_constraint(Q.lt(a - b, 0))
    eq, pos = ad.to_constraint(Q.eq(a, b))
    ne, npos = ad.to_constraint(Q.ne(a, b))
    assert pos is True and npos is False and eq == ne
    # Relational and Q.is_true forms agree with the predicate form
    for kind in KINDS:
        r = _REL[kind](a, b)
        if r not in (S.true, S.false):
            assert ad.to_constraint(r) == ad.to_constraint(pred_atom(kind, a, b))
        assert ad.to_constraint(Q.is_true(_REL[kind](a, b, evaluate=False))) == \
            ad.to_constraint(pred_atom(kind, a, b))


@needs_adapter
def test_constants_move_to_the_right():
    p, pos = ad.to_constraint(Q.lt(x + 1, 3))
    terms, rhs, strict, eq = p
    assert pos and strict and not eq
    assert dict(terms) == {x: 1} and rhs == 2
    p, _ = ad.to_constraint(Q.ge(5, 2 * x - 1))       # 2x - 1 <= 5  <=>  2x <= 6
    terms, rhs, strict, eq = p
    assert not strict and not eq
    assert {t: F(c) / F(rhs) for t, c in dict(terms).items()} == {x: F(1, 3)}
    for t, c in dict(terms).items():
        assert t.free_symbols, "a numeric term leaked into the terms"
        assert isinstance(c, F) or isinstance(c, int)
    assert isinstance(rhs, F) or isinstance(rhs, int)


@needs_adapter
def test_payload_is_hashable_and_deterministic():
    a = ad.to_constraint(Q.lt(x + 2 * y, z))
    b = ad.to_constraint(Q.lt(2 * y + x, z))
    assert a == b and hash(a) == hash(b)


@needs_adapter
@pytest.mark.parametrize("atom,value", [
    (Q.lt(1, 2), True), (Q.lt(2, 1), False), (Q.le(1, 1), True), (Q.gt(1, 1), False),
    (Q.eq(1, 1), True), (Q.eq(1, 2), False), (Q.ne(1, 1), False), (Q.ne(1, 2), True),
    (Q.lt(Rational(1, 3), Rational(1, 2)), True),
    (Q.lt(x, x + 1), True), (Q.le(x + 1, x), False), (Q.eq(x + y, y + x), True),
    (Q.ne(2 * x, x + x), False), (Q.gt(x - x, 0), False),
])
def test_ground_relations_fold_to_booleans(atom, value):
    assert ad.to_constraint(atom) is value


@needs_adapter
def test_cancelled_terms_are_reported():
    """Q.lt(x, x + 1) is True only for finite real x: the engine needs x in
    terms() to add the bridge clause."""
    assert x in ad.terms(Q.lt(x, x + 1))
    assert set(ad.terms(Q.lt(x + y, z))) == {x, y, z}
    assert ad.terms(Q.lt(1, 2)) == []
    assert ad.terms(Q.positive(x)) is None


# ----------------------------------------------------------------------
# Atoms left to the SAT layer (None, never an exception)
# ----------------------------------------------------------------------

A = MatrixSymbol("A", 2, 2)
im = Symbol("im", imaginary=True)

UNINTERPRETED = [
    Q.gt(x, 0.5), Q.lt(0.5 * x, 1), Q.lt(x, sqrt(2)), Q.lt(pi * x, 1), Q.lt(E * x, 1),
    Q.gt(x, I), Q.lt(I, 1), Q.lt(1 + I, 1),       # 1 + I: the references' Lt(I, 0) TypeError
    Q.lt(I * x, 1), Q.gt(im * I, 0),               # (im*I).is_real is True: sympy edge case
    Q.gt(x, nan), Q.gt(3, nan), Q.eq(x, nan),
    Q.gt(x, oo), Q.lt(x, -oo), Q.gt(x, -oo),       # -oo: SymPy's check only tests +oo
    Q.le(x, x + oo), Q.lt(x, zoo), Q.eq(zoo, x), Q.lt(sin(x + oo), 1), Q.gt(3, oo),
    Q.lt(f(1), x), Q.lt(sin(1), x), Q.lt(AccumBounds(0, 1), x), Q.lt((1 + I) * x, 1), Q.eq(A, A), Q.lt(A, 2), Q.eq(A, 2 * A),
    Q.positive(x), Q.real(x), Q.prime(x), Q.even(x),
]


@needs_adapter
@pytest.mark.parametrize("atom", UNINTERPRETED, ids=str)
def test_uninterpreted_atoms_give_none(atom):
    assert ad.to_constraint(atom) is None
    assert ad.terms(atom) is None


@needs_adapter
@pytest.mark.parametrize("atom", [x, S.true, Tuple(x, y), Eq(Tuple(x), Tuple(y)), x < y,
                                  Q.eq(Tuple(x), Tuple(y))], ids=str)
def test_non_relation_inputs_do_not_raise(atom):
    r = ad.to_constraint(atom)
    assert r is None or isinstance(r, (bool, tuple))
    if isinstance(atom, sympy.core.relational.Relational) and atom.lhs.is_Symbol:
        assert r is not None


@needs_adapter
def test_matrix_equality_is_not_decided_false():
    """Q.eq(A, A) is true; A - A is a ZeroMatrix, so an adapter doing
    ``Eq(lhs - rhs, 0)`` would call it false (a reference flaw)."""
    assert ad.to_constraint(Q.eq(A, A)) is None


# ----------------------------------------------------------------------
# Nonlinear atoms: opaque terms (sound relaxation) or None
# ----------------------------------------------------------------------

NONLINEAR = [
    (Q.lt(x * y, 1), {x * y}), (Q.gt(x ** 2, x), {x ** 2, x}), (Q.lt(sin(x) + x, 2), {sin(x), x}),
    (Q.eq(f(x), f(y)), {f(x), f(y)}), (Q.lt(x * (y + 1), 0), None), (Q.lt(1 / x, y), {1 / x, y}),
    (Q.lt(2 * x * y, 3 * y * x), {x * y}),
]


@needs_adapter
@pytest.mark.parametrize("i", range(len(NONLINEAR)))
def test_nonlinear_terms_are_opaque_or_uninterpreted(i):
    """Either None, or a payload over opaque terms that is still exact
    when each term is evaluated (sound relaxation).  Different terms must
    stay different keys (x**2 is not x)."""
    atom, expected_terms = NONLINEAR[i]
    res = ad.to_constraint(atom)
    if res is None or isinstance(res, bool):
        return
    p, _ = res
    keys = {t for t, c in (p[0].items() if isinstance(p[0], dict) else p[0])}
    if expected_terms is not None:
        assert keys == expected_terms
    rng = random.Random(i)
    rel = ad.relation(atom) if hasattr(ad, "relation") else None
    for _ in range(20):
        pt = {s: Rational(rng.choice([-3, -2, -1, 1, 2, 3]), rng.choice([1, 2])) for s in (x, y)}
        try:
            vals = {}
            for t in keys:
                v = t.subs(pt)
                if not v.is_Rational:
                    raise ValueError
                vals[t] = F(int(v.p), int(v.q))
        except ValueError:
            continue
        if rel is None:
            continue
        kind, a, b = rel
        assert holds(payload_constraint(p, res[1]), vals) == sympy_value(kind, a, b, pt)


# ----------------------------------------------------------------------
# Through the solver
# ----------------------------------------------------------------------

def _solver_with(atoms):
    from satassume.solver import Solver
    s = Solver()
    adapter = ad.LRAAdapter()
    ok = {}
    for v, a in enumerate(atoms, 1):
        s.ensure_vars(v)
        ok[v] = adapter.register(s, v, a)
    return s, adapter, ok


@needs_adapter
def test_register_returns_false_and_attaches_nothing_for_uninterpreted():
    s, adapter, ok = _solver_with([Q.gt(x, 0.5), Q.positive(x)])
    assert ok == {1: False, 2: False}
    assert s.theories() == []


@needs_adapter
def test_transitivity_through_solver():
    s, _, ok = _solver_with([Q.lt(x, y), Q.lt(y, z), Q.lt(x, z), Q.gt(z, x)])
    assert all(ok.values())
    assert s.entails(3, [1, 2]) is True
    assert s.entails(4, [1, 2]) is True
    assert s.entails(-1, [2, -3]) is True
    with pytest.raises(ValueError):
        s.entails(3, [1, 2, -4])


@needs_adapter
def test_ne_and_eq_through_solver():
    s, _, ok = _solver_with([Q.eq(x, 1), Q.ne(x, 1), Q.ne(x, 0), Q.le(x, 0), Q.ge(x, 0)])
    assert all(ok.values())
    assert s.entails(-2, [1]) is True           # eq -> not ne
    assert s.entails(1, [-2]) is True           # not ne -> eq
    assert s.solve([4, 5, 3]) is False          # x = 0 and x != 0
    assert s.solve([4, 3]) is True


@needs_adapter
def test_ground_atoms_through_solver():
    s, _, ok = _solver_with([Q.lt(1, 2), Q.gt(1, 2), Q.lt(x, x + 1)])
    assert all(ok.values())
    assert s.entails(1) is True
    assert s.entails(2) is False
    assert s.entails(3) is True


@needs_adapter
def test_uninterpreted_atoms_do_not_disable_the_rest():
    s, _, ok = _solver_with([Q.gt(x, 0.5), Q.gt(x, 0), Q.eq(x, 2)])
    assert ok == {1: False, 2: True, 3: True}
    assert s.entails(2, [3]) is True
    assert s.entails(1, [3]) is None            # 1 is a free Boolean


@needs_adapter
def test_same_relation_registered_twice_is_equivalent():
    s, _, ok = _solver_with([Q.lt(x, y), Q.gt(y, x), y > x, Q.ge(x, y)])
    assert all(ok.values())
    assert s.entails(2, [1]) is True
    assert s.entails(3, [-2]) is False
    assert s.entails(-4, [3]) is True


@needs_adapter
def test_model_is_consistent_with_sympy():
    atoms = [Q.lt(x + y, 1), Q.gt(x, Rational(1, 2)), Q.gt(y, Rational(1, 3)), Q.ne(x, y)]
    s, _, ok = _solver_with(atoms)
    assert s.solve([1, 2, 3, 4]) is True
    (model,) = s.theory_models()
    pt = {t: Rational(v.numerator, v.denominator) for t, v in dict(model).items() if t in (x, y)}
    for a in atoms:
        kind = {Q.lt: "lt", Q.gt: "gt", Q.ne: "ne"}[a.function]
        assert sympy_value(kind, a.arguments[0], a.arguments[1], pt)


# ----------------------------------------------------------------------
# sympy/assumptions/tests/test_rel_queries.py through satassume.ask
# ----------------------------------------------------------------------

xr, yr, zr = symbols("x y z", real=True)
a_, b_, c_ = symbols("a b c", real=True)
X = MatrixSymbol("X", 2, 2)


def _w(**kw):
    return Symbol("w", real=True, **kw)


# (id, proposition, assumptions, expected); expected "raises" means
# ValueError (inconsistent assumptions); a tuple of values means any of them
REL_QUERIES = [
    # test_lra_satask (lra_satask(p, a) is ask(p, a) restricted to LRA)
    ("eq_given_not_ne_1", Q.eq(xr, 1), ~Q.ne(xr, 0), False),
    ("eq_given_not_ne_0", Q.eq(xr, 0), ~Q.ne(xr, 0), True),
    ("not_ne_given_eq", ~Q.ne(xr, 0), Q.eq(xr, 0), True),
    ("not_eq_given_eq", ~Q.eq(xr, 0), Q.eq(xr, 0), False),
    ("ne_given_eq", Q.ne(xr, 0), Q.eq(xr, 0), False),
    ("ne_x_x", Q.ne(xr, xr), True, False),
    ("eq_x_x", Q.eq(xr, xr), True, True),
    ("gt0_given_gt1", Q.gt(xr, 0), Q.gt(xr, 1), True),
    ("gt0_given_true", Q.gt(xr, 0), True, None),
    ("gt0_given_false", Q.gt(xr, 0), False, "raises"),
    # test_old_assumptions: the "unhandled" ones raised UnhandledInput in
    # SymPy; the proposition is false for every real w, so only False
    # (or None) is acceptable
    ("plain_w_lt2_gt3", Q.lt(Symbol("w"), 2) & Q.gt(Symbol("w"), 3), True, (False, None)),
    ("int_w_lt2_gt3", Q.lt(_w(integer=True), 2) & Q.gt(_w(integer=True), 3), True, False),
    ("odd_w_lt2_gt3", Q.lt(_w(odd=True), 2) & Q.gt(_w(odd=True), 3), True, False),
    ("pos_w_le0", Q.le(_w(positive=True), 0), True, False),
    ("pos_w_gt0", Q.gt(_w(positive=True), 0), True, True),
    ("neg_w_lt0", Q.lt(_w(negative=True), 0), True, True),
    ("neg_w_ge0", Q.ge(_w(negative=True), 0), True, False),
    ("zero_w_eq0", Q.eq(_w(zero=True), 0), True, True),
    ("zero_w_ne0", Q.ne(_w(zero=True), 0), True, False),
    ("nonzero_w_ne0", Q.ne(_w(nonzero=True), 0), True, True),
    ("nonzero_w_eq1", Q.eq(_w(nonzero=True), 1), True, None),
    ("nonpos_w_le0", Q.le(_w(nonpositive=True), 0), True, True),
    ("nonpos_w_gt0", Q.gt(_w(nonpositive=True), 0), True, False),
    ("nonneg_w_ge0", Q.ge(_w(nonnegative=True), 0), True, True),
    ("nonneg_w_lt0", Q.lt(_w(nonnegative=True), 0), True, False),
    # test_rel_queries
    ("lt2_and_gt3", Q.lt(xr, 2) & Q.gt(xr, 3), True, False),
    ("positive_x_minus_z", Q.positive(xr - zr), (xr > yr) & (yr > zr), True),
    ("sum_gt2_given_negs", xr + yr > 2, (xr < 0) & (yr < 0), False),
    ("x_gt_z_chain", xr > zr, (xr > yr) & (yr > zr), True),
    # test_unhandled_queries
    ("matrix_lt_gt", Q.lt(X, 2) & Q.gt(X, 3), True, None),
    # test_all_pred
    ("ext_pos_given_gt2", Q.extended_positive(xr), xr > 2, True),
    ("pos_inf_real", Q.positive_infinite(xr), True, False),
    ("neg_inf_real", Q.negative_infinite(xr), True, False),
    ("gt0_given_gt2_prime", xr > 0, (xr > 2) & Q.prime(xr), True),
    ("gt0_given_gt2_integer", xr > 0, (xr > 2) & Q.integer(xr), True),
    # test_number_line_properties
    ("trans_le_le", a_ <= c_, (a_ <= b_) & (b_ <= c_), True),
    ("trans_le_lt", a_ < c_, (a_ <= b_) & (b_ < c_), True),
    ("trans_lt_le", a_ < c_, (a_ < b_) & (b_ <= c_), True),
    ("add_c", a_ + c_ <= b_ + c_, a_ <= b_, True),
    ("sub_c", a_ - c_ <= b_ - c_, a_ <= b_, True),
    # test_failing_number_line_properties (XFAIL in SymPy): the linear one
    # is in reach of LRA; the nonlinear ones must at least not be wrong
    ("additive_inverse", -a_ >= -b_, a_ <= b_, True),
    ("mul_pos_c", a_ * c_ <= b_ * c_, (a_ <= b_) & (c_ > 0) & ~Q.zero(c_), (True, None)),
    ("div_pos_c", a_ / c_ <= b_ / c_, (a_ <= b_) & (c_ > 0) & ~Q.zero(c_), (True, None)),
    ("mul_neg_c", a_ * c_ >= b_ * c_, (a_ <= b_) & (c_ < 0) & ~Q.zero(c_), (True, None)),
    # SymPy's own test has Q.positive(x) (a typo for a): not entailed
    ("inverse_typo", 1 / a_ >= 1 / b_, (a_ <= b_) & Q.positive(xr) & Q.positive(b_), None),
    ("inverse_pos", 1 / a_ >= 1 / b_, (a_ <= b_) & Q.positive(a_) & Q.positive(b_), (True, None)),
    # test_equality
    ("eq_refl", Q.eq(xr, xr), True, True),
    ("eq_sym", Q.eq(yr, xr), Q.eq(xr, yr), True),
    ("eq_sym_or", Q.eq(yr, xr), ~Q.eq(zr, zr) | Q.eq(xr, yr), True),
    ("eq_trans", Q.eq(xr, zr), Q.eq(xr, yr) & Q.eq(yr, zr), True),
    # test_equality_failing (XFAIL in SymPy; needs EUF / substitution)
    ("subst_prime", Q.prime(xr), Q.eq(xr, yr) & Q.prime(yr), (True, None)),
    ("subst_real", Q.real(Symbol("x")), Q.eq(Symbol("x"), yr) & Q.real(yr), (True, None)),
]


@needs_adapter
@pytest.mark.parametrize("case", REL_QUERIES, ids=[c[0] for c in REL_QUERIES])
def test_rel_queries_through_ask(case):
    from satassume import DictCache, Engine
    from satassume.sympy_api import ask
    _, prop, assum, expected = case
    eng = Engine(cache=DictCache())
    if expected == "raises":
        try:
            r = ask(prop, assum, eng)
        except ValueError:
            return
        if r is None:
            pytest.xfail("engine gives no answer (incomplete)")
        pytest.fail(f"expected ValueError, got {r}")
    r = ask(prop, assum, eng)
    allowed = expected if isinstance(expected, tuple) else (expected,)
    if r in allowed:
        return
    if r is None:
        pytest.xfail("engine gives no answer (incomplete)")
    pytest.fail(f"wrong definite answer {r}, expected {expected}")


# ----------------------------------------------------------------------
# End to end through ask: random linear relations vs the FM oracle
# ----------------------------------------------------------------------

from test_lra import fm_feasible  # noqa: E402

_RS = symbols("p q r", real=True)
_OPS = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!="}
_NEGOP = {"<": ">=", "<=": ">", ">": "<=", ">=": "<", "==": "!=", "!=": "=="}


@st.composite
def real_relation(draw):
    e = S(0)
    for s in _RS:
        e += draw(st.integers(-2, 2)) * s
    if not e.free_symbols:
        e += _RS[0]
    return draw(st.sampled_from(KINDS)), e, S(draw(st.integers(-2, 2)))


def _oracle_con(kind, e, c):
    co = {s: F(int(v)) for s, v in e.as_coefficients_dict().items() if s != 1}
    return co, _OPS[kind], F(int(c))


@needs_adapter
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(real_relation(), min_size=1, max_size=4), real_relation())
def test_fuzz_ask_against_oracle(assumptions, query):
    """ask(query, And(assumptions)) over real symbols equals the FM oracle:
    inconsistent / True / False / None.  LRA is complete for conjunctions,
    so None is right only when neither the query nor its negation is
    entailed."""
    from satassume import DictCache, Engine
    from satassume.sympy_api import ask
    cons = [_oracle_con(*a) for a in assumptions]
    qc = _oracle_con(*query)
    neg = (qc[0], _NEGOP[qc[1]], qc[2])
    if not fm_feasible(cons):
        expected = "inconsistent"
    elif not fm_feasible(cons + [neg]):
        expected = True
    elif not fm_feasible(cons + [qc]):
        expected = False
    else:
        expected = None
    assum = sympy.And(*[pred_atom(k, e, c) for k, e, c in assumptions])
    try:
        r = ask(pred_atom(*query), assum, Engine(cache=DictCache()))
    except ValueError:
        r = "inconsistent"
    assert r == expected, (query, assumptions, r, expected)
