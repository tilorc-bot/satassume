"""Tests for the SymPy adapter of the EUF theory (satassume/euf_adapter.py).

The adapter maps ``Q.eq``/``Q.ne``/``Eq``/``Ne`` atoms to EUF atoms over
flattened terms.  The documented rules (euf_adapter.py docstring):

* ``Rational``/``Integer`` -> distinct interpreted values;
* ``Add``, ``Mul``, ``Pow`` and ``Application`` subclasses -> a head applied
  to the canonical argument tuple (no AC reasoning), keyed by (head, arity);
* everything else (symbols, ``Float``, ``pi``, ``oo``, ``zoo``, binders such
  as ``Sum``/``Integral``/``Subs``, booleans) -> one opaque constant per
  expression;
* atoms containing ``nan`` are refused (``Eq(nan, nan)`` is False).

Refused atoms (register returns False): anything that is not an equality
or disequality (``Q.lt``, ``Q.prime``, ``x < y``, ``And``...), and any
equality with ``nan`` inside.

Queries are run on satassume's CDCL solver with the adapter's theory
attached: ``entails(query, facts)`` builds a fresh solver, registers every
atom through the adapter (atoms it refuses stay plain Boolean variables,
which is what the engine will do) and calls ``Solver.entails``.
Substitution of equals into other predicates (``Q.prime(x)`` from
``Q.eq(x, y) & Q.prime(y)``) is out of scope and must give None.
"""
from __future__ import annotations

import pytest

sympy = pytest.importorskip("sympy")
pytest.importorskip("satassume.euf_adapter")

from sympy import (Eq, Ne, Function, symbols, S, Rational, Float, sqrt, pi,  # noqa: E402
                   E, oo, zoo, nan, Sum, Integral, Subs, Lambda, sin, exp, Abs,
                   Max, And, Or, Not, Symbol)
from sympy.assumptions.ask import Q  # noqa: E402
from sympy.integrals.transforms import LaplaceTransform, FourierTransform  # noqa: E402
from hypothesis import given, settings, strategies as st, HealthCheck  # noqa: E402

from satassume.solver import Solver  # noqa: E402
from satassume.euf_adapter import EUFAdapter  # noqa: E402

x, y, z, u, w, s, t = symbols("x y z u w s t")
f, g, h = symbols("f g h", cls=Function)


# ----------------------------------------------------------------------
# Solver-level helper
# ----------------------------------------------------------------------

class Ctx:
    """One solver + one adapter; every atom gets one variable."""

    def __init__(self):
        self.solver = Solver()
        self.adapter = EUFAdapter()
        self.vars = {}
        self.interpreted = {}

    def lit(self, a):
        if isinstance(a, Not):
            return -self.lit(a.args[0])
        v = self.vars.get(a)
        if v is None:
            v = self.solver.new_var()
            self.vars[a] = v
            self.interpreted[a] = self.adapter.register(self.solver, v, a)
        return v

    def clause(self, fact):
        if isinstance(fact, Or):
            return [self.lit(a) for a in fact.args]
        return [self.lit(fact)]


def entails(query, *facts):
    """True / False / None, or "inconsistent" when the facts are."""
    c = Ctx()
    assumptions = []
    for fact in facts:
        if isinstance(fact, And):
            parts = fact.args
        else:
            parts = (fact,)
        for p in parts:
            cl = c.clause(p)
            if len(cl) == 1:
                assumptions.append(cl[0])
            else:
                c.solver.add_clause(cl)
    q = c.lit(query)
    try:
        return c.solver.entails(q, assumptions)
    except ValueError:
        return "inconsistent"


def consistent(*facts):
    c = Ctx()
    lits = []
    for fact in facts:
        cl = c.clause(fact)
        if len(cl) == 1:
            lits.append(cl[0])
        else:
            c.solver.add_clause(cl)
    return c.solver.solve(lits)


# ----------------------------------------------------------------------
# What is interpreted
# ----------------------------------------------------------------------

@pytest.mark.parametrize("atom", [Q.eq(x, y), Q.ne(x, y), Eq(x, y), Ne(x, y),
                                  Q.eq(f(x), 1), Eq(f(x, y), g(z)), Q.eq(x + y, 2 * z),
                                  Q.eq(Float(0.5), x), Q.eq(pi, x), Q.eq(oo, x),
                                  Q.eq(Sum(x, (x, 1, 2)), y), Q.eq(x, x)])
def test_register_accepts_equalities(atom):
    c = Ctx()
    v = c.solver.new_var()
    assert c.adapter.register(c.solver, v, atom) is True
    assert c.adapter.interprets(atom) is True
    assert sum(1 for th in c.solver.theories() if th is c.adapter.theory) == 1


@pytest.mark.parametrize("atom", [Q.lt(x, y), Q.gt(x, y), Q.le(x, y), Q.ge(x, y),
                                  Q.prime(x), Q.positive(x), x < y, x >= y,
                                  And(Q.eq(x, y), Q.eq(y, z)), Or(Q.eq(x, y), Q.eq(y, z)),
                                  S.true, S.false,
                                  Q.eq(x, nan), Eq(f(nan), y), Q.ne(nan, nan),
                                  Q.eq(nan, nan)])
def test_register_refuses(atom):
    c = Ctx()
    v = c.solver.new_var()
    assert c.adapter.register(c.solver, v, atom) is False
    assert c.adapter.interprets(atom) is False


def test_theory_attached_once_for_many_atoms():
    c = Ctx()
    for a in (Q.eq(x, y), Q.ne(y, z), Eq(f(x), z), Q.lt(x, y)):
        c.lit(a)
    assert [th for th in c.solver.theories() if th is c.adapter.theory] == [c.adapter.theory]


# ----------------------------------------------------------------------
# sympy/assumptions/tests/test_rel_queries.py::test_equality
# ----------------------------------------------------------------------

def test_equality_reflexive():
    assert entails(Q.eq(x, x)) is True
    assert entails(Q.ne(x, x)) is False
    assert entails(Q.eq(f(x, y), f(x, y))) is True


def test_equality_symmetric():
    assert entails(Q.eq(y, x), Q.eq(x, y)) is True
    assert entails(Eq(y, x), Eq(x, y)) is True
    assert entails(Q.eq(y, x), Eq(x, y)) is True


def test_equality_symmetric_under_disjunction():
    assert entails(Q.eq(y, x), Or(Not(Q.eq(z, z)), Q.eq(x, y))) is True


def test_equality_transitive():
    assert entails(Q.eq(x, z), Q.eq(x, y) & Q.eq(y, z)) is True
    assert entails(Q.eq(x, z), Q.eq(x, y)) is None
    chain = [Q.eq(Symbol(f"v{i}"), Symbol(f"v{i + 1}")) for i in range(19)]
    assert entails(Q.eq(Symbol("v19"), Symbol("v0")), And(*chain)) is True


def test_equality_failing_cases_are_not_wrong():
    # test_equality_failing (XFAIL in SymPy): substitution is out of scope
    # (REF-FLAW 30327-substitution-scope).  EUF sees only the equality; the
    # unary predicates are plain variables.  Must stay None, never False.
    assert entails(Q.prime(x), Q.eq(x, y) & Q.prime(y)) is None
    assert entails(Q.real(x), Q.eq(x, y) & Q.real(y)) is None
    assert entails(Q.imaginary(x), Q.eq(x, y) & Q.imaginary(y)) is None


# ----------------------------------------------------------------------
# Through satassume's public ask() (relations wired in satassume/relations.py)
# ----------------------------------------------------------------------

def _ask(prop, assumptions=True):
    from theory_harness import relation_engine, ask_with
    return ask_with(relation_engine(), prop, assumptions)


def test_engine_equality():
    # sympy/assumptions/tests/test_rel_queries.py::test_equality
    assert _ask(Q.eq(x, x)) is True
    assert _ask(Q.eq(y, x), Q.eq(x, y)) is True
    assert _ask(Q.eq(y, x), ~Q.eq(z, z) | Q.eq(x, y)) is True
    assert _ask(Q.eq(x, z), Q.eq(x, y) & Q.eq(y, z)) is True


def test_engine_equality_failing_is_not_wrong():
    # test_equality_failing: EUF does not substitute; the engine does, by
    # predicate transfer (satassume.transfer).  True, never False.
    assert _ask(Q.prime(x), Q.eq(x, y) & Q.prime(y)) is True
    assert _ask(Q.real(x), Q.eq(x, y) & Q.real(y)) is True
    assert _ask(Q.imaginary(x), Q.eq(x, y) & Q.imaginary(y)) is True
    assert _ask(Q.prime(x), Q.ne(x, y) & Q.prime(y)) is None


def test_engine_ne_congruence_numbers():
    assert _ask(Q.ne(x, y), Q.eq(x, y)) is False
    assert _ask(Q.ne(x, z), Q.eq(x, y) & Q.ne(y, z)) is True
    assert _ask(Q.eq(f(x), f(y)), Q.eq(x, y)) is True
    assert _ask(Q.eq(x, y), Q.eq(f(x), f(y))) is None
    assert _ask(Q.eq(g(x, y), g(y, x))) is None
    assert _ask(Q.eq(f(x, z), f(y, z)), Q.eq(f(x), f(y))) is None
    assert _ask(Q.ne(x, 2), Q.eq(x, 1)) is True
    assert _ask(Q.eq(x, y), Q.eq(x, 1) & Q.eq(y, 2)) is False
    assert _ask(Q.eq(x, y), Q.eq(x, 1) & Q.eq(y, 1)) is True
    assert _ask(Q.eq(f(x), f(y)), Q.eq(x, 1) & Q.eq(y, 1)) is True
    assert _ask(Q.eq(x, 1), Q.eq(x, 1) & Q.eq(x, 2)) == "inconsistent"


def test_engine_zero_link_through_congruence():
    # zero(e) <-> eq(e, 0) (relations.py) plus congruence: sound, entailed.
    assert _ask(Q.zero(x), Q.eq(x, 0)) is True
    assert _ask(Q.zero(f(y)), Q.zero(f(x)) & Q.eq(x, y)) is True
    assert _ask(Q.nonzero(f(y)), Q.zero(f(x)) & Q.eq(x, y)) is False


def test_engine_numbers_of_different_types_never_wrong():
    for q, a in [(Q.eq(x, Float(2.0)), Q.eq(x, 2)),
                 (Q.eq(S(2), Float(2.0)), True),
                 (Q.eq(Float(0.1), Rational(1, 10)), True),
                 (Q.eq(x, Float(0.5)), Q.eq(x, S.Half)),
                 (Q.eq(sqrt(2) + sqrt(3), sqrt(5 + 2 * sqrt(6))), True)]:
        assert _ask(q, a) in (True, None), (q, a)


def test_engine_nan_and_binders_never_wrong():
    assert _ask(Q.eq(nan, nan)) is not True
    assert _ask(Q.eq(f(nan), f(nan))) is not True
    for make in (lambda a: Sum(a, (x, 1, 2)), lambda a: Integral(a, (x, 0, 1)),
                 lambda a: Subs(a, x, 1), lambda a: LaplaceTransform(a, x, s)):
        assert _ask(Q.eq(make(x), make(y)), Q.eq(x, y)) is None
        assert _ask(Q.ne(make(x), make(y)), Q.eq(x, y)) is None


# ----------------------------------------------------------------------
# Q.ne / Ne and negation
# ----------------------------------------------------------------------

def test_ne_is_the_negation_of_eq():
    assert entails(Q.ne(x, y), Q.eq(x, y)) is False
    assert entails(Q.eq(x, y), Q.ne(x, y)) is False
    assert entails(Q.eq(x, y), Not(Q.ne(x, y))) is True
    assert entails(Q.ne(x, y), Not(Q.eq(y, x))) is True
    assert entails(Ne(x, y), Eq(y, x)) is False
    assert entails(Q.ne(x, z), Q.eq(x, y) & Q.ne(y, z)) is True
    assert entails(Q.ne(x, z), Q.ne(x, y) & Q.ne(y, z)) is None
    assert consistent(Q.eq(x, y), Q.ne(y, x)) is False
    assert consistent(Eq(x, y), Eq(y, z), Ne(z, x)) is False


def test_eq_and_not_ne_are_both_explained():
    # REF-FLAW 30327-eq-literal-map: two atoms stating the same equation
    # must each be explained by its own literal, also across pops.
    ad = EUFAdapter()
    sol = Solver()
    v1, v2 = sol.new_var(), sol.new_var()
    assert ad.register(sol, v1, Q.eq(x, y)) and ad.register(sol, v2, Q.ne(x, y))
    th = ad.theory
    tx, ty = ad.term(x), ad.term(y)
    th.push_level()
    assert th.assert_lit(v1) is None
    th.push_level()
    r = th.assert_lit(-v2)
    assert r is None
    th.pop_level()
    assert th.equal(tx, ty) and list(th.explain(tx, ty)) == [v1]
    th.pop_level()
    th.push_level()
    assert th.assert_lit(-v2) is None
    assert list(th.explain(tx, ty)) == [-v2]
    r = th.assert_lit(-v1)
    assert r is not None and r[0] is False and set(r[1]) == {v1, v2}
    th.pop_level()


# ----------------------------------------------------------------------
# Congruence
# ----------------------------------------------------------------------

def test_function_congruence():
    assert entails(Q.eq(f(x), f(y)), Q.eq(x, y)) is True
    assert entails(Q.eq(f(f(x)), f(f(y))), Q.eq(x, y)) is True
    assert entails(Q.eq(g(x, z), g(y, z)), Q.eq(x, y)) is True
    assert entails(Q.eq(g(x, z), g(y, u)), Q.eq(x, y)) is None
    assert entails(Q.eq(g(x, z), g(y, u)), Q.eq(x, y) & Q.eq(z, u)) is True
    assert consistent(Q.eq(x, y), Q.ne(f(x), f(y))) is False
    assert entails(Q.eq(f(y), z), Q.eq(x, y) & Q.eq(f(x), z)) is True


def test_builtin_functions_are_congruent():
    assert entails(Q.eq(sin(x), sin(y)), Q.eq(x, y)) is True
    assert entails(Q.eq(exp(x) + 1, exp(y) + 1), Q.eq(x, y)) is True
    assert entails(Q.eq(Abs(x), Abs(y)), Q.eq(x, y)) is True
    assert entails(Q.eq(Max(x, z), Max(y, z)), Q.eq(x, y)) is True


def test_congruence_is_not_injectivity():
    assert entails(Q.eq(x, y), Q.eq(f(x), f(y))) is None
    assert entails(Q.eq(x, y), Q.eq(sin(x), sin(y))) is None
    assert entails(Q.eq(x, y), Q.eq(g(x, y), g(y, x))) is None


def test_no_commutativity_for_uninterpreted_functions():
    assert entails(Q.eq(g(x, y), g(y, x))) is None
    assert entails(Q.eq(g(x, y), g(y, x)), Q.eq(x, y)) is True


def test_distinct_function_symbols():
    assert entails(Q.eq(f(x), g(x))) is None
    assert entails(Q.eq(f(x), g(y)), Q.eq(x, y)) is None


def test_mixed_arity_function_is_not_curried():
    # REF-FLAW 30010-currying: f(x) and f(x, z) share the name f.
    assert entails(Q.eq(f(x, z), f(y, z)), Q.eq(f(x), f(y))) is None
    assert consistent(Q.eq(f(x), f(y)), Q.ne(f(x, z), f(y, z))) is True
    assert consistent(Q.eq(f(x), 1), Q.eq(f(x, y), 2)) is True


def test_symbol_named_like_a_function():
    fs, gs = Symbol("f"), Symbol("g")
    assert entails(Q.eq(f(x), g(x)), Q.eq(fs, gs)) is None
    assert consistent(Q.eq(fs, gs), Q.ne(f(x), g(x))) is True


def test_iterated_function_cycle():
    p = [x]
    for _ in range(5):
        p.append(f(p[-1]))
    assert entails(Q.eq(f(x), x), Q.eq(p[3], x) & Q.eq(p[5], x)) is True
    assert entails(Q.eq(f(x), x), Q.eq(p[4], x)) is None


# ----------------------------------------------------------------------
# Add / Mul / Pow: opaque heads over canonical argument tuples
# ----------------------------------------------------------------------

def test_add_mul_pow_congruence():
    assert entails(Q.eq(x + z, y + z), Q.eq(x, y)) is True
    assert entails(Q.eq(x * z, y * z), Q.eq(x, y)) is True
    assert entails(Q.eq(2 * x, 2 * y), Q.eq(x, y)) is True
    assert entails(Q.eq(x + 1, y + 1), Q.eq(x, y)) is True
    assert entails(Q.eq(x ** 2, y ** 2), Q.eq(x, y)) is True
    assert entails(Q.eq(f(x * w + z), f(y * w + z)), Q.eq(x, y)) is True
    assert consistent(Q.eq(x, y), Q.ne(x + z, y + z)) is False


def test_add_mul_incompleteness_is_never_wrong():
    # No AC or arithmetic reasoning: these hold but EUF cannot see them.
    # They must be True or None, never False or an inconsistency.
    for q, facts in [(Q.eq(x + y, 2 * y), [Q.eq(x, y)]),
                     (Q.eq(x * (y + 1), x * y + x), []),
                     (Q.eq(x + y + z, u + z), [Q.eq(x + y, u)]),
                     (Q.eq(x - y, 0), [Q.eq(x, y)]),
                     (Q.eq(x ** 2, x * x), [])]:
        assert entails(q, *facts) in (True, None), q
    assert entails(Q.eq(y + x, x + y)) is True       # SymPy canonicalizes


def test_add_argument_order_never_unsound():
    # Canonical ordering may put equal arguments at different positions;
    # the adapter must not "fix" that by guessing.
    a, b = symbols("a b")
    # a + b is Add(a, b) but z + b is Add(b, z): positions differ, so EUF
    # cannot see the equality (incomplete), and must not invent one either.
    assert entails(Q.eq(a + b, z + b), Q.eq(a, z)) in (True, None)
    assert consistent(Q.eq(a, z), Q.ne(a + y, b + y)) is True


# ----------------------------------------------------------------------
# Numbers
# ----------------------------------------------------------------------

def test_distinct_numbers():
    assert entails(Q.eq(S(1), S(2))) is False
    assert entails(Q.ne(S(1), S(2))) is True
    assert entails(Q.eq(x, 2), Q.eq(x, 1)) is False
    assert entails(Q.ne(x, 2), Q.eq(x, 1)) is True
    assert consistent(Q.eq(x, 1), Q.eq(y, 2), Q.eq(x, y)) is False
    assert consistent(Q.eq(f(x), Rational(1, 2)), Q.eq(f(y), Rational(1, 3)),
                      Q.eq(x, y)) is False
    assert entails(Q.eq(x, y), Q.eq(x, Rational(2, 4)) & Q.eq(y, S.Half)) is True
    assert entails(Q.eq(f(S(1)), f(S(2)))) is None        # f(1) = f(2) possible
    assert entails(Q.eq(x, -3), Q.eq(x, S(-3))) is True


def test_equal_numbers_of_different_types():
    # REF-FLAW 30327-numbers-by-structure: 2 and 2.0 are the same number;
    # Eq(0.1, 1/10) is True in SymPy.  Never a conflict.
    assert consistent(Q.eq(x, 2), Q.eq(x, Float(2.0))) is True
    assert entails(Q.eq(S(2), Float(2.0))) in (True, None)
    assert entails(Q.eq(Float(0.5), S.Half)) in (True, None)
    assert entails(Q.eq(Float(0.1), Rational(1, 10))) in (True, None)
    assert consistent(Q.eq(x, Float(0.1)), Q.eq(x, Rational(1, 10))) is True
    assert consistent(Q.eq(x, Float(2.0)), Q.eq(x, Float(2.0, 30))) is True


def test_symbolic_constants_are_not_assumed_distinct():
    # Equal but structurally different closed forms must not be refuted.
    lhs, rhs = sqrt(2) + sqrt(3), sqrt(5 + 2 * sqrt(6))
    assert lhs != rhs                                  # SymPy keeps them apart
    assert entails(Q.eq(lhs, rhs)) in (True, None)
    assert consistent(Q.eq(x, lhs), Q.eq(x, rhs)) is True
    assert entails(Q.eq(oo, oo)) is True
    assert entails(Q.eq(zoo, zoo)) is True
    assert entails(Q.eq(pi, pi)) is True


def test_nan_is_not_reflexive():
    # REF-FLAW 30327-reflexive-nan: Eq(nan, nan) is False in SymPy.
    assert Eq(nan, nan) is S.false
    assert entails(Q.eq(nan, nan)) is not True
    assert entails(Q.eq(f(nan), f(nan))) is not True


# ----------------------------------------------------------------------
# Binders: congruence over bound variables is unsound
# ----------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    lambda a: Sum(a, (x, 1, 2)),                     # 3 vs 2*y
    lambda a: Integral(a, (x, 0, 1)),                # 1/2 vs y
    lambda a: Subs(a, x, 1),                         # 1 vs y
    lambda a: LaplaceTransform(a, x, s),             # 1/s**2 vs y/s
    lambda a: FourierTransform(a, x, s),
    lambda a: f(Sum(a, (x, 1, 2))),                  # binder nested in a function
], ids=["Sum", "Integral", "Subs", "LaplaceTransform", "FourierTransform", "f(Sum)"])
def test_binders_are_not_congruent(make):
    # REF-FLAW 30327-binders: from x = y (x free), B(x) = B(y) does not
    # follow when B binds x.  Satisfiable: x = y = 0 (or 1) separates them.
    bx, by = make(x), make(y)
    assert bx != by
    assert entails(Q.eq(bx, by), Q.eq(x, y)) is None
    assert consistent(Q.eq(x, y), Q.ne(bx, by)) is True


def test_binders_are_still_congruent_as_opaque_wholes():
    # The same binder expression is one term, and it takes part in
    # congruence as an argument.
    b = Sum(x, (x, 1, u))
    assert entails(Q.eq(f(b), f(y)), Q.eq(b, y)) is True
    assert entails(Q.eq(b, b)) is True


def test_lambda_atoms_do_not_crash():
    lam1, lam2 = Lambda(x, x + 1), Lambda(x, y + 1)
    c = Ctx()
    c.lit(Q.eq(x, y))
    c.lit(Q.ne(lam1, lam2))
    assert c.solver.solve([c.lit(Q.eq(x, y)), c.lit(Q.ne(lam1, lam2))]) is True


# ----------------------------------------------------------------------
# Non-Expr arguments
# ----------------------------------------------------------------------

def test_boolean_arguments_do_not_crash_and_are_not_wrong():
    for atom in (Q.eq(Q.prime(x), S.true), Eq(S.true, S.false)):
        c = Ctx()
        v = c.solver.new_var()
        c.adapter.register(c.solver, v, atom)
    assert entails(Q.eq(Q.prime(x), S.true)) is None


# ----------------------------------------------------------------------
# Adapter bookkeeping
# ----------------------------------------------------------------------

def test_term_interning_and_shared_terms():
    ad = EUFAdapter()
    sol = Solver()
    v = sol.new_var()
    ad.register(sol, v, Q.eq(f(x), y + 1))
    assert ad.term(f(x)) == ad.term(f(x))
    assert ad.term(x + y) == ad.term(y + x)
    assert ad.term(f(x)) != ad.term(g(x))
    assert ad.term(S(2)) == ad.term(Rational(4, 2))
    shared = ad.shared_terms()
    assert {f(x), y + 1, x, y} <= shared


def test_deep_expression():
    # REF-FLAW 30010/30327-recursion: flattening must not recurse once per
    # nesting level (SymPy itself builds this expression without trouble).
    import sys
    depth = sys.getrecursionlimit() + 200
    ex, ey = x, y
    for _ in range(depth):
        ex, ey = f(ex), f(ey)
    assert entails(Q.eq(ex, ey), Q.eq(x, y)) is True


def test_perf_many_atoms():
    import time
    n = 150
    v = symbols(f"p0:{n}")
    facts = And(*[Q.eq(f(v[i]), v[i + 1]) for i in range(n - 1)])
    t0 = time.perf_counter()
    assert entails(Q.eq(f(f(v[0])), v[2]), facts) is True
    assert entails(Q.eq(v[0], v[n - 1]), facts) is None
    assert time.perf_counter() - t0 < 10.0


# ----------------------------------------------------------------------
# Random differential test through the adapter
# ----------------------------------------------------------------------
#
# Terms over symbols a, b, c with the uninterpreted functions f/1, f/2 and
# g/2 (no Add/Mul, so SymPy does not rewrite them) and the numbers 1, 2.
# The oracle is test_euf's naive closure over an independent structural
# translation of the SymPy terms.

A, B_, C = symbols("a b c")


@st.composite
def sym_terms(draw, depth=2):
    if depth == 0 or draw(st.integers(0, 2)) == 0:
        return draw(st.sampled_from([A, B_, C, S(1), S(2)]))
    kind = draw(st.integers(0, 2))
    if kind == 0:
        return f(draw(sym_terms(depth=depth - 1)))
    if kind == 1:
        return f(draw(sym_terms(depth=depth - 1)), draw(sym_terms(depth=depth - 1)))
    return g(draw(sym_terms(depth=depth - 1)), draw(sym_terms(depth=depth - 1)))


def _spec(expr, terms, index):
    """Independent translation into test_euf's oracle term specs."""
    if expr in index:
        return index[expr]
    if expr.is_Integer:
        spec = ("v", int(expr))
    elif expr.is_Symbol:
        spec = ("c", expr.name)
    else:
        args = tuple(_spec(a, terms, index) for a in expr.args)
        spec = ("a", str(expr.func), args)
    terms.append(spec)
    index[expr] = len(terms) - 1
    return index[expr]


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(sym_terms(), sym_terms(), st.booleans()), min_size=1, max_size=6))
def test_random_conjunctions_match_oracle(lits):
    from test_euf import oracle_consistent
    terms, index = [], {}
    atoms = []
    facts = []
    for l, r, pos in lits:
        atoms.append((_spec(l, terms, index), _spec(r, terms, index), True))
        facts.append(Q.eq(l, r) if pos else Not(Q.eq(l, r)))
    oracle_lits = [(k + 1) if pos else -(k + 1) for k, (_, _, pos) in enumerate(lits)]
    # duplicate atoms map to one oracle variable per occurrence; fine: the
    # oracle only looks at the meaning of each literal
    want = oracle_consistent(terms, atoms, oracle_lits)
    got = consistent(*facts)
    assert got == want, (facts, got, want)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(st.tuples(sym_terms(), sym_terms(), st.booleans()), min_size=1, max_size=5),
       sym_terms(), sym_terms())
def test_random_ask_matches_oracle(lits, ql, qr):
    """ask(Q.eq(ql, qr), facts) through the whole engine (EUF and LRA both
    attached) against the EUF oracle.  Only uninterpreted functions and
    integers occur, where EUF with distinct values is complete, so every
    answer is checked, None included."""
    from test_euf import oracle_consistent
    terms, index = [], {}
    atoms, facts, olits = [], [], []
    for k, (l, r, pos) in enumerate(lits):
        atoms.append((_spec(l, terms, index), _spec(r, terms, index), True))
        facts.append(Q.eq(l, r) if pos else Q.ne(l, r))
        olits.append((k + 1) if pos else -(k + 1))
    atoms.append((_spec(ql, terms, index), _spec(qr, terms, index), True))
    q = len(atoms)
    if not oracle_consistent(terms, atoms, olits):
        want = "inconsistent"
    elif not oracle_consistent(terms, atoms, olits + [-q]):
        want = True
    elif not oracle_consistent(terms, atoms, olits + [q]):
        want = False
    else:
        want = None
    got = _ask(Q.eq(ql, qr), And(*facts))
    if got != want:
        # a definite answer must be right; None is reported as incompleteness
        assert got is None, (facts, Q.eq(ql, qr), got, want)
        pytest.fail(f"incomplete: ask gave None, EUF entails {want} for "
                    f"{Q.eq(ql, qr)} given {facts}")
