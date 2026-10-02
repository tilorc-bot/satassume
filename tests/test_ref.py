"""``satassume.ref.ask_ref``, the reference implementation of ``docs/spec.md``.

Three groups:

* the spec's ten corpus records (section 12) and the reviewer's ten
  (``reports/p5a-review.md``, "Ten records of my own"), embedded here with
  their recorded answers (``queries.jsonl`` is not committed): ``ask_ref``
  equals the recorded answer, or is more definite for a stated reason;
* twenty hand-written queries over ``0``, ``oo``, ``zoo``, ``nan`` and
  non-commutative symbols against SymPy's ``ask`` at the pinned version:
  agree or more definite; a contradiction fails;
* the routing and scope rules of sections 1, 3 and 9.
"""
from __future__ import annotations

import os
import sys

import pytest
from sympy import I, Mul, Pow, Symbol, nan, oo, pi, zoo, S
from sympy import ask as sympy_ask
from sympy.assumptions import Q

from satassume.ref import ask_ref, last_info, theory_scope
from satassume.formula import P, atoms_of
from satassume.sympy_api import to_formula

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from compare import rebuild  # noqa: E402

# (line, kind, prop | fact, assum | expr, recorded) of ``queries.jsonl``
RECORDS = [
    # the spec's ten (docs/spec.md section 12)
    (374, 'new', 'AppliedPredicate(Q.negative, zoo)', 'true', False),
    (392, 'new', "AppliedPredicate(Q.positive_infinite, Mul(I, Symbol('x')))", "AppliedPredicate(Q.real, Symbol('x'))", False),
    (636, 'new', 'AppliedPredicate(Q.algebraic, Add(Integer(1), I))', 'true', True),
    (1326, 'new', "AppliedPredicate(Q.rational, Pow(Symbol('x'), Symbol('y')))", "And(AppliedPredicate(Q.rational, Symbol('y')), AppliedBinaryRelation(Q.eq, Symbol('x'), Integer(-1)))", None),
    (1875, 'new', "AppliedPredicate(Q.odd, Mul(Integer(2), Symbol('x')))", "AppliedPredicate(Q.irrational, Symbol('x'))", False),
    (2369, 'new', "AppliedPredicate(Q.algebraic, log(Symbol('x')))", "AppliedPredicate(Q.algebraic, Symbol('x'))", None),
    (2514, 'new', "Implies(AppliedPredicate(Q.real, Symbol('x')), AppliedPredicate(Q.positive, Symbol('x')))", 'true', None),
    (2639, 'old', 'imaginary', "Pow(Symbol('x'), Integer(2))", None),
    (2968, 'new', "AppliedPredicate(Q.integer, Symbol('x'))", "AppliedPredicate(Q.integer, Symbol('x'))", True),
    (3135, 'new', "StrictLessThan(Symbol('x'), Integer(0))", "GreaterThan(Symbol('x'), Integer(0))", False),
    # the reviewer's ten (reports/p5a-review.md)
    (1325, 'new', "AppliedPredicate(Q.rational, Pow(Symbol('x'), Symbol('y')))", "And(AppliedPredicate(Q.rational, Symbol('y')), AppliedBinaryRelation(Q.eq, Symbol('x'), Integer(1)))", True),
    (1431, 'new', "AppliedPredicate(Q.rational, acos(Symbol('x')))", "And(AppliedPredicate(Q.rational, Symbol('x')), AppliedPredicate(Q.nonzero, Add(Integer(-1), Symbol('x'))))", False),
    (1816, 'new', "AppliedPredicate(Q.nonzero, Add(Symbol('x'), Symbol('y')))", "And(AppliedPredicate(Q.negative, Symbol('x')), AppliedPredicate(Q.negative, Symbol('y')))", True),
    (2097, 'new', 'AppliedPredicate(Q.real, Integer(1))', "AppliedPredicate(Q.imaginary, Symbol('x'))", True),
    (2350, 'new', "AppliedPredicate(Q.algebraic, asin(Symbol('x')))", "And(AppliedPredicate(Q.algebraic, Symbol('x')), AppliedPredicate(Q.nonzero, Symbol('x')))", False),
    (2515, 'new', "Equivalent(AppliedPredicate(Q.even, Symbol('x')), AppliedPredicate(Q.integer, Symbol('x')))", "AppliedPredicate(Q.even, Symbol('x'))", True),
    (2566, 'new', "AppliedPredicate(Q.positive, acos(Symbol('x')))", "AppliedPredicate(Q.nonnegative, Add(Integer(-1), Symbol('x')))", None),
    (3156, 'new', 'true', "GreaterThan(Symbol('y'), Integer(0))", True),
    (3199, 'new', "AppliedPredicate(Q.positive, Symbol('y'))", "And(AppliedPredicate(Q.negative, Symbol('x')), AppliedPredicate(Q.zero, Symbol('y')))", False),
    (3294, 'new', "AppliedPredicate(Q.real, Pow(Symbol('x'), Integer(2)))", "And(AppliedPredicate(Q.real, Symbol('x')), AppliedPredicate(Q.real, Symbol('y')))", True),
]

#: records whose recorded answer the clause set does not entail (a corpus
#: miss the baseline already counts, not a disagreement): line -> reason
LESS_DEFINITE = {
    1325: "no pow rule derives rational(b**e) from integer(b) & positive(b) & "
          "rational(e) (2**(1/2) is irrational), so C & L does not entail q; "
          "baseline compare-relations.log none=3 (p5a-review.md, 'Ten records')",
}


def _query(rec):
    line, kind, a, b, want = rec
    if kind == "old":
        return getattr(Q, a)(rebuild(b)), True, want
    return rebuild(a), rebuild(b), want


@pytest.mark.parametrize("rec", RECORDS, ids=[str(r[0]) for r in RECORDS])
def test_corpus_record(rec):
    p, a, want = _query(rec)
    try:
        got = ask_ref(p, a)
    except ValueError:
        got = "ValueError"
    line = rec[0]
    if line in LESS_DEFINITE:
        assert got is None, f"line {line}: {LESS_DEFINITE[line]} -- now {got!r}; flip the pin"
        return
    if got == want:
        return
    assert want is None and got is not None, \
        f"line {line}: ask_ref gave {got!r}, recorded {want!r}"
    pytest.fail(f"line {line}: ask_ref more definite ({got!r}) than the record "
                f"({want!r}); state the reason in LESS_DEFINITE's counterpart")


# --------------------------------------------------------------------------
x, y, n = Symbol('x'), Symbol('y'), Symbol('n')
A, B = Symbol('A', commutative=False), Symbol('B', commutative=False)

HAND = [
    (Q.zero(S.Zero), True),
    (Q.prime(S.Zero), True),
    (Q.positive(oo), True),
    (Q.negative(-oo), True),
    (Q.odd(oo), True),
    (Q.finite(zoo), True),
    (Q.extended_real(zoo), True),
    (Q.rational(zoo), True),
    (Q.real(nan), True),
    (Q.integer(nan), True),
    (Q.commutative(A), True),
    (Q.commutative(A * B), True),
    (Q.real(A), Q.positive(A)),
    (Q.zero(A * B - B * A), True),
    (Q.commutative(A + x), Q.real(x)),
    (Q.infinite(x + y), Q.infinite(x) & Q.finite(y)),
    (Q.zero(x * y), Q.zero(x) & Q.finite(y)),
    (Q.positive(x**2), Q.nonzero(x) & Q.real(x)),
    (Q.even(2 * n), Q.integer(n)),
    (Q.real(x + oo), Q.real(x)),
    (Q.zero(Mul(x, S.Zero, evaluate=False)), True),
    (Q.positive(Pow(x, S.Zero, evaluate=False)), True),
]


@pytest.mark.parametrize("p,a", HAND, ids=[f"{p}|{a}" for p, a in HAND])
def test_hand_written_against_sympy(p, a):
    """Agree with SymPy's ``ask`` or be more definite; a contradiction
    fails.  Where SymPy is definite and ``ask_ref`` is not, the miss must
    be the engine's too (``sympy_api.ask`` on a fresh engine answers None
    as well): non-commutative symbols are out of scope (category
    ``matrix``, spec section 1) and an unevaluated ``x*0`` has no template
    rule, in the engine as in the reference."""
    from satassume.engine import Engine
    from satassume.sympy_api import ask as engine_ask
    want = sympy_ask(p, a)
    got = ask_ref(p, a)
    if want is None or got == want:
        return                              # agree or more definite
    assert got is None, f"ask_ref {got!r} contradicts sympy.ask {want!r}"
    eng = engine_ask(p, a, engine=Engine())
    assert eng is None, f"ask_ref None where the engine answers {eng!r} (sympy {want!r})"


# --------------------------------------------------------------------------
def test_constant_route_ignores_assumptions():
    # spec section 9.3
    assert ask_ref(Q.prime(S(7)), Q.composite(S(7))) is True
    e = S.Exp1 ** pi - pi ** S.Exp1
    assert ask_ref(Q.positive(e), Q.positive(e)) is None
    assert last_info().route == "constant"


def test_inconsistent_assumptions_raise():
    with pytest.raises(ValueError):
        ask_ref(Q.positive(x), Q.positive(x) & Q.negative(x))
    with pytest.raises(ValueError):
        ask_ref(Q.real(x), Q.lt(x, 0) & Q.gt(x, 0))


def test_true_false_and_unsupported():
    assert ask_ref(S.true, Q.real(x)) is True
    assert ask_ref(S.false, Q.real(x)) is False
    from sympy import MatrixSymbol
    M = MatrixSymbol('M', 2, 2)
    assert ask_ref(Q.invertible(M), True) is None


def test_theory_scope_by_syntax():
    f = lambda e, opaque=False: atoms_of(to_formula(e, True, opaque))
    # a relation atom: glue; an eq atom: transfer; numbers never linked
    g, t, linked = theory_scope(f(Q.eq(x, 1) & Q.rational(y), True), f(Q.rational(x**y)))
    assert (g, t) == (True, True) and linked == {x, y, x**y}
    g, t, linked = theory_scope(f(x >= 0, True), f(x < 0))
    assert (g, t) == (True, False) and linked == {x}
    # two sign atoms on different sums sharing a symbol: glue, no transfer
    g, t, _ = theory_scope(f(Q.positive(x - 1), True), f(Q.negative(1 - x)))
    assert (g, t) == (True, False)
    # on disjoint symbols: no glue (the budget's weaker test is not this)
    g, t, _ = theory_scope(f(Q.positive(x - 1), True), f(Q.negative(1 - y)))
    assert (g, t) == (False, False)
    # no sums at all
    g, t, linked = theory_scope(f(Q.real(x), True), f(Q.positive(x**2)))
    assert (g, t) == (False, False) and linked == {x, x**2}


def test_affine_pair_uses_the_glue():
    # the glue links the sign facts to the linear forms (spec 3, 5.5)
    assert ask_ref(Q.negative(1 - x), Q.positive(x - 1)) is True
    assert ask_ref(Q.positive(1 - x), Q.positive(x - 1)) is False
    g, t, _ = last_info().scope
    assert g and not t


def test_relation_and_transfer():
    assert ask_ref(Q.lt(x, 0), x >= 0) is False
    assert ask_ref(Q.positive(y), Q.eq(x, y) & Q.positive(x)) is True
    assert last_info().scope[:2] == (True, True)
    assert ask_ref(Q.even(y), Q.eq(x, y) & Q.even(x)) is True


def test_ref_outcome_form():
    from satassume.ref import ref_outcome
    assert ref_outcome(Q.integer(x), Q.integer(x)) == "True"
    assert ref_outcome(Q.positive(x), Q.positive(x) & Q.negative(x)) == "ValueError"
    assert ref_outcome(Q.real(x), True) == "None"
