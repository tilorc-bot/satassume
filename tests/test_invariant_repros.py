"""Pinned invariant violations (strict xfails).

An ``ask`` answer must be a function of its inputs only.  The invariant
hunts checked these invariants:

- I1 Removing clauses: dropping any subset of the clauses before solving
  never turns an answer into the other definite value, and never turns
  None into a definite answer.
- I2 Unrelated rules: adding clauses, terms or registered extensions with
  no path through shared variables to the query or the assumptions does
  not change the answer.
- I3 Monotone in assumptions: if ``ask(p, A)`` is definite,
  ``ask(p, A & B)`` gives the same value (anything, if ``A & B`` is
  inconsistent).
- I4 Negation symmetry: ``ask(p, A)`` is True exactly when ``ask(~p, A)``
  is False.
- I5 Syntax: reordering or duplicating conjuncts, nesting ``And``, or an
  equivalent restatement of an assumption doesn't change the answer.
- I6 Renaming: renaming symbols to fresh names with the same declared
  assumptions doesn't change the answer, under any ``PYTHONHASHSEED``.
- I7 Declared inputs only: changing an engine setting after queries have
  run gives the same answers as a fresh engine with that setting.

Each test below pins one violation found at f055b7b by the invariant
hunts: families K1-K8 (with the second entry paths K3b and K6b), W2A1-W2A4
and W2B1-W2B4; and the invariant harness's own findings that no earlier
test covers: families H1-H2 and the entry path W2A3c; and W2B4b, a
sibling of W2B4 that a plan review found.  Each asserts that the invariant holds, so it xfails while
the bug is present and XPASSes (failing the run, ``strict=True``) once it
is fixed: the PR that fixes a family removes its marker.

Every answer uses a fresh ``Engine`` (except K3/K3b, whose history is the
case), so no test depends on another or on the order they run in.
"""
import pytest
from sympy import (Basic, Float, Function, MatrixSymbol, Not, Or, And,
                   Implies, Q, Rational, Symbol, cos, false, log, pi, sin,
                   sqrt, symbols)

import satassume.extensions as extensions
from satassume import Engine, lra_adapter
from satassume.constfield import Undecided
from satassume.sympy_api import ask


def _xfail(reason, **kw):
    return pytest.mark.xfail(strict=True, reason=reason, **kw)


def test_k1_unrelated_relation_enables_theories():
    n, u, v = symbols('n u v')
    a = Q.integer(n) & Q.negative(n - 1)
    assert (ask(Q.nonpositive(n), a, Engine())
            == ask(Q.nonpositive(n), a & Q.gt(u, v), Engine()))


def test_k2_uninterpreted_relation_sinks_answer():
    x, y = symbols('x y')
    assert (ask(Q.real(x), Q.real(x), Engine())
            == ask(Q.real(x), Q.real(x) & Q.le(y, 1.5), Engine()))


def test_k3_setting_change_after_queries():
    x, y = symbols('x y')
    a = Q.real(x) & Q.le(y, 1.5)
    e = Engine()
    ask(Q.real(x), a, e)
    e.uninterpreted = "none"
    assert ask(Q.real(x), a, e) == ask(Q.real(x), a, Engine(uninterpreted="none"))


def test_k3b_generic_constants_flag_stale_process_memo():
    # uninterpreted="none": with the default "free" the cold answer
    # coincides (the relation's sign link decides it), hiding the stale memo
    x = Symbol('x')
    p, a = Q.gt(log(2)*x, 0), Q.gt(x, 1)
    eng = lambda: Engine(uninterpreted="none")
    # the memo is one dict per flag value: {flag: {atom: ...}}
    memo = lra_adapter._INTERPRETED
    saved_flag = lra_adapter.GENERIC_CONSTANTS
    saved_memo = {k: dict(v) for k, v in memo.items()}

    def clear():
        for v in memo.values():
            v.clear()

    try:
        clear()
        lra_adapter.GENERIC_CONSTANTS = True
        ask(p, a, eng())
        lra_adapter.GENERIC_CONSTANTS = False
        warm = ask(p, a, eng())
        clear()
        cold = ask(p, a, eng())
    finally:
        lra_adapter.GENERIC_CONSTANTS = saved_flag
        for k, v in saved_memo.items():
            memo[k].clear()
            memo[k].update(v)
    assert warm == cold


def test_k4_constant_prop_shortcut_vs_restated():
    x, w = symbols('x w')
    a = Q.le(x, Float('4.712'))
    restated = Or(Q.positive(2), And(Q.real(w), Not(Q.real(w)), evaluate=False),
                  evaluate=False)
    assert ask(Q.positive(2), a, Engine()) == ask(restated, a, Engine())


def test_k5_unrelated_undecidable_constant_kills_lra():
    x, y = symbols('x y')
    c = cos(1)**2 + sin(1)**2 - 1
    assert (ask(Q.gt(x, 0), Q.gt(x, 1), Engine())
            == ask(Q.gt(x, 0), Q.gt(x, 1) & Q.eq(y, c), Engine()))


def test_k6_undecided_escapes_affine_links():
    x, y = symbols('x y')
    c = cos(1)**2 + sin(1)**2 - 1
    a = Q.real(x) & Q.positive(y - 1) & Q.positive(y + c)
    assert ask(Q.real(x), a, Engine()) == ask(Q.real(x), Q.real(x), Engine())


def test_k6b_undecided_escapes_relations():
    x = Symbol('x')
    c = log(4) - 2*log(2)
    ask(Q.gt(x + c, 0), Q.gt(x, 0), Engine())


def test_k7_declared_fact_loses_definite():
    r = Symbol('r', rational=True)
    p = Q.hermitian(pi*(14.5 + 3/r)**2)
    a = ~Q.extended_real(14 + 2/r)
    assert (ask(p, a, Engine(discovery_budget=5))
            == ask(p, a & ~Q.transcendental(r), Engine(discovery_budget=5)))


def test_k7c_declared_fact_loses_definite():
    z0 = Symbol('z0', zero=True)
    he = Symbol('he', hermitian=True)
    f = Function('f')
    p = Q.negative(1/(1 + z0))
    a = Or(Q.positive(he), Q.negative_infinite(-3/sqrt(f(z0))),
           Q.prime(f(he)), Q.irrational(f(f(z0))))

    def eng():
        return Engine(discovery_budget=3, cone_search=True, cone_threshold=3)
    assert ask(p, a, eng()) == ask(p, a & Not(Q.irrational(z0)), eng())


def test_k8_implies_vs_or_restated():
    y = Symbol('y', real=True)
    r = Symbol('r', rational=True)
    f = Function('f')
    a = Q.commutative(y**2*f(r + y))
    c = Q.commutative(f(f(r + y)))
    p = Q.extended_real(r + 4.0)
    assert (ask(p, Implies(a, c), Engine(discovery_budget=5))
            == ask(p, Or(c, ~a), Engine(discovery_budget=5)))


class _Unrelated(Basic):
    """A class no term of any query belongs to."""


def test_w2a1_unrelated_vocab_registration_disables_split():
    n = Symbol('n', integer=True)
    u, v = Symbol('u'), Symbol('v')
    p = Q.negative(-n)
    a = Q.integer(n) & Q.negative(n - 1) & Q.nonzero(u + v) & Q.nonzero(u + 2*v)
    plain = ask(p, a, Engine())
    reg = extensions.extensions
    saved = ({k: list(v) for k, v in reg._handlers.items()},
             {k: list(v) for k, v in reg._vocab.items()})
    extensions.register('prime', _Unrelated)(lambda e: None)
    try:
        registered = ask(p, a, Engine())
    finally:
        extensions.unregister('prime')
        reg._handlers = {k: list(v) for k, v in saved[0].items()}
        reg._vocab = {k: list(v) for k, v in saved[1].items()}
        reg._node_cache.clear()
        reg.version += 1
    assert plain == registered


def test_w2a2_unrelated_sums_via_constant_key_engage_lra():
    n = Symbol('n', integer=True)
    u, v = Symbol('u'), Symbol('v')
    p = Q.negative(-n)
    a = Q.integer(n) & Q.negative(n - 1) & Q.real(pi*n)
    b = Q.nonzero(u + v) & Q.positive(u + pi)
    assert ask(p, a, Engine()) == ask(p, a & b, Engine())


def test_w2a3_unrelated_out_of_scope_conjunct_sinks_answer():
    x = Symbol('x')
    m = MatrixSymbol('M', 2, 2)
    assert (ask(Q.real(x), Q.positive(x), Engine())
            == ask(Q.real(x), Q.positive(x) & Q.invertible(m), Engine()))


def test_w2a4_budget_cut_negation_asymmetry():
    x = Symbol('x')
    he = Symbol('he', hermitian=True)
    p = Q.positive(x) & Q.lt(1/he, -3*sqrt(2)/2)
    a = Q.extended_nonnegative(sqrt(2)/he)
    r = ask(p, a, Engine(discovery_budget=1))
    rn = ask(Not(p, evaluate=False), a, Engine(discovery_budget=1))
    assert (r is None and rn is None) or (
        r is not None and rn is not None and r != rn)


def test_w2a3c_keyless_proposition_with_out_of_scope_conjunct():
    m = MatrixSymbol('M', 2, 2)
    assert ask(false, True, Engine()) == ask(false, Q.symmetric(m), Engine())


def test_w2b1_restated_relation_loses_term_sign():
    x = Symbol('x')
    z = Symbol('z', positive=True)
    assert (ask(Q.gt(x, 0), Q.gt(x, z), Engine())
            == ask(Q.gt(x, 0), Q.gt(x - z, 0), Engine()))


def test_w2b2_integer_bound_restated_strict():
    n = Symbol('n', integer=True)
    assert (ask(Q.eq(n, 1), Q.ge(n, 1) & Q.le(n, 1), Engine())
            == ask(Q.eq(n, 1), Q.ge(n, 1) & Q.lt(n, 2), Engine()))


def test_w2b3_unrelated_integer_block_exhausts_branch_budget():
    x, y, u, v = symbols('x y u v', integer=True)
    a = Q.gt(x, y + Rational(1, 3)) & Q.ge(y, 0) & Q.le(y, 5)
    b = Q.gt(u, v + Rational(1, 3)) & Q.ge(v, 0) & Q.ne(u, v + 1)
    assert (ask(Q.ge(x, y + 1), a, Engine())
            == ask(Q.ge(x, y + 1), a & b, Engine()))


def test_w2b3b_unrelated_integer_blocks_exhaust_branch_budget():
    x, y, u0, v0, u1, v1 = symbols('x y u0 v0 u1 v1', integer=True)
    a = Q.gt(x, y + Rational(1, 3)) & Q.ge(y, 0) & Q.le(y, 5)
    b = And(*[Q.gt(u, v + Rational(1, 3)) & Q.ge(v, 0) & Q.ne(u, v + 1)
              for u, v in ((u0, v0), (u1, v1))])
    assert (ask(Q.ge(x, y + 1), a, Engine())
            == ask(Q.ge(x, y + 1), a & b, Engine()))


def test_w2b3c_unrelated_bounded_integer_blocks_exhaust_branch_budget():
    x, y = symbols('x y', integer=True)
    a = Q.gt(x, y + Rational(1, 3)) & Q.ge(y, 0) & Q.le(y, 5)
    b = And(*[Q.ge(u, Rational(1, 2)) & Q.le(u, 100) & Q.ne(u, 1)
              & Q.ne(u, 2) & Q.ne(u, 3)
              for u in symbols('u0 u1', integer=True)])
    assert (ask(Q.ge(x, y + 1), a, Engine())
            == ask(Q.ge(x, y + 1), a & b, Engine()))


def test_w2b4_unrelated_equality_engages_transfer():
    x, y = symbols('x y', real=True)
    u, v = symbols('u v')
    f = Function('f')
    a = Q.positive(f(y)) & Q.le(x, y) & Q.ge(x, y)
    assert (ask(Q.positive(f(x)), a, Engine())
            == ask(Q.positive(f(x)), a & Q.eq(u, v), Engine()))


@_xfail("W2B4b (I5, depends): an equality LRA derives from two inequalities "
        "(x <= y & x >= y vs x = y) does not engage transfer; relations.py "
        "Relations._want_transfer/_engage_transfer (only a syntactic eq atom)")
def test_w2b4b_derived_equality_does_not_engage_transfer():
    x, y = symbols('x y')
    f = Function('f')
    p = Q.positive(f(x))
    assert (ask(p, Q.positive(f(y)) & Q.eq(x, y), Engine())
            == ask(p, Q.positive(f(y)) & Q.le(x, y) & Q.ge(x, y), Engine()))


def test_h1_equality_of_nonreal_terms_restated():
    x, y = symbols('x y')
    assert (ask(Q.eq(x, y), Q.eq(x, y), Engine())
            == ask(Q.eq(x, y), Q.eq(-x, -y), Engine()))


def test_h2_unrelated_material_consumes_discovery_budget():
    x, u = symbols('x u')
    a = Q.positive(x - 1)
    assert (ask(Q.positive(x), a, Engine(discovery_budget=1, relevance=False))
            == ask(Q.positive(x), a & Q.real(1/u),
                   Engine(discovery_budget=1, relevance=False)))

def test_h2b_unrelated_material_consumes_discovery_budget():
    x, u = symbols('x u')
    a = Q.positive(x - 1)
    assert (ask(Q.positive(x), a, Engine(discovery_budget=1, relevance=False))
            == ask(Q.positive(x), a & Q.real(1/(u + 1)) & Q.real(1/(u + 2)),
                   Engine(discovery_budget=1, relevance=False)))
