"""Wide disjunctions and conjunctions of derived predicates stay linear.

A derived predicate is a conjunction (or disjunction) of basis literals
(``nonnegative = extended_real & finite & ~extended_negative``), so a
clause of n of them distributes to up to 3**n clauses.  ``compile._or_cnf``
distributes only up to ``MAX_DISTRIBUTE`` clauses and gives the larger
conjunctions Tseitin variables; ``templates._common.Pattern`` hands rules
that would expand past ``MAX_EXPAND`` clauses over as formulas.
"""
import time

import pytest
from sympy import Add, And, Implies, Mul, Not, Or, Q, symbols

from satassume.compile import VarTable, compile_formula
from satassume.formula import P
from satassume.formula import And as FAnd, Implies as FImplies, Not as FNot, Or as FOr
from satassume.sympy_api import ask
from satassume.templates.registry import registry

xs = symbols("x0:12")
DERIVED = ['nonnegative', 'nonpositive', 'positive', 'negative', 'real', 'nonzero',
           'extended_nonnegative', 'positive_infinite', 'negative_infinite',
           'irrational', 'odd', 'antihermitian', 'infinite', 'transcendental']


def _nclauses(f):
    out = []
    compile_formula(f, VarTable(), out.append)
    return len(out)


@pytest.mark.parametrize("pred", DERIVED)
def test_compiled_wide_formulas_are_linear(pred):
    atoms = [P(pred, x) for x in xs]
    shapes = [
        FOr(*atoms),
        FOr(*[FNot(a) for a in atoms]),
        FNot(FAnd(*atoms)),
        FNot(FOr(*atoms)),
        FAnd(*atoms),
        FImplies(FAnd(*atoms), P('positive', xs[0])),
        FImplies(FAnd(*[FNot(a) for a in atoms]), P('nonnegative', xs[0])),
        FOr(*[FAnd(a, P('real', a.expr)) for a in atoms]),
        FOr(FOr(*atoms[:6]), FOr(*atoms[6:])),
    ]
    for f in shapes:
        assert _nclauses(f) <= 50 * len(xs), f


ALL = And(*[Q.positive(x) for x in xs])
CASES = [
    (Or(*[Q.nonnegative(x) for x in xs]), True, None),
    (Q.real(xs[0]), Or(*[Q.nonnegative(x) for x in xs]), None),
    (Or(*[Q.nonnegative(x) for x in xs]), Or(*[Q.positive(x) for x in xs]), True),
    (Or(*[Q.positive(x) for x in xs]),
     Not(And(*[Q.nonpositive(x) for x in xs])) & And(*[Q.real(x) for x in xs]), True),
    (And(*[Q.nonnegative(x) for x in xs]), ALL, True),
    (Not(Or(*[Q.negative(x) for x in xs])), And(*[Q.nonnegative(x) for x in xs]), True),
    (Or(*[Q.real(x) for x in xs]), Or(*[Q.positive(x) for x in xs]), True),
    (Q.nonnegative(xs[0]),
     Implies(And(*[Q.nonnegative(x) for x in xs[1:]]), Q.positive(xs[0]))
     & And(*[Q.positive(x) for x in xs[1:]]), True),
    (Or(*[Q.finite(x) for x in xs]), Or(*[And(Q.positive(x), Q.real(x)) for x in xs]), True),
    (Q.nonnegative(xs[0]),
     Or(Not(Or(*[Q.nonnegative(x) for x in xs[1:]])), Q.positive(xs[0]))
     & Or(*[Q.positive(x) for x in xs[1:]]), True),
    (Q.negative_infinite(xs[11]), Or(*[Q.negative_infinite(x) for x in xs]) & Q.real(xs[0])
     & And(*[~Q.negative_infinite(x) for x in xs[1:11]]), True),
    (Q.positive(xs[0]), Or(*[Q.negative_infinite(x) for x in xs]) & Q.real(xs[0])
     & And(*[~Q.negative_infinite(x) for x in xs[1:11]]), None),
    (Or(*[Q.antihermitian(x) for x in xs]), And(*[Q.zero(x) for x in xs]), True),
]


@pytest.mark.parametrize("prop, assumptions, expected", CASES)
def test_wide_queries_are_fast(prop, assumptions, expected):
    t = time.perf_counter()
    assert ask(prop, assumptions) is expected
    assert time.perf_counter() - t < 2.0


@pytest.mark.parametrize("n", [3, 6, 12])
def test_wide_add_templates_are_linear(n):
    comp, formulas = registry.clauses_for(Add(*xs[:n], evaluate=False))
    assert sum(len(c.pattern.clauses) for c in comp) <= 40 * n + 100
    s = Add(*xs[:n])
    a = Q.positive_infinite(xs[0]) & And(*[Q.extended_real(x) & ~Q.negative_infinite(x) for x in xs[1:n]])
    t = time.perf_counter()
    expected = True if n < 12 else None   # as on the 33-predicate main
    assert ask(Q.positive_infinite(s), a) is expected
    assert ask(Q.infinite(s), a) is expected
    assert time.perf_counter() - t < 2.0


# compile time, not only output size: the choice in compile._or_cnf and the
# subsumption check in templates._common._unsubsumed were cubic / super-cubic
# in the width (OR of 200 derived atoms 2.6 s, cold Add of 80 symbols 11 s;
# main: 0.06 s, 0.3 s).  Wide enough that the old code takes far longer than
# the bounds here.

@pytest.mark.parametrize("pred", ["nonnegative", "positive", "nonzero"])
def test_wide_or_compiles_in_linear_time(pred):
    ys = symbols("y0:1000")
    t = time.perf_counter()
    assert _nclauses(FOr(*[P(pred, y) for y in ys])) <= 5 * len(ys)
    assert _nclauses(FOr(*[FNot(P(pred, y)) for y in ys[:500]]
                         + [P(pred, y) for y in ys[500:]])) <= 5 * len(ys)
    assert time.perf_counter() - t < 1.0


@pytest.mark.parametrize("build", [Add, Mul])
@pytest.mark.parametrize("pred", ["positive", "nonnegative", "extended_positive"])
def test_wide_pattern_builds_are_fast(build, pred):
    from satassume.templates import _common
    ys = symbols("w0:150")
    _common._CACHE.clear()
    t = time.perf_counter()
    assert ask(getattr(Q, pred)(build(*ys)), And(*[Q.positive(y) for y in ys])) is True
    assert time.perf_counter() - t < 4.0


def test_unsubsumed_matches_brute_force():
    import random
    from satassume.templates._common import _unsubsumed
    rng = random.Random(0)
    for _ in range(200):
        cs = [tuple(rng.sample(range(12), rng.randint(0, 5))) for _ in range(rng.randint(0, 30))]
        if rng.random() < 0.8:
            cs = [c for c in cs if c]
        uniq = sorted(dict.fromkeys(frozenset(c) for c in cs), key=len)
        want = [tuple(sorted(c)) for i, c in enumerate(uniq)
                if not any(d <= c for d in uniq[:i])]
        assert _unsubsumed(cs) == want


# A wide formula of derived atoms against another one over the same terms:
# the shapes below, (proposition, assumptions) in every pairing, with the
# answers of the encoding with one variable per predicate (ca49991).  With
# a derived atom's definition expanded into basis literals at each
# occurrence (a private Plaisted-Greenbaum variable under a disjunction, a
# clause for a negated conjunction), the negated proposition did not
# propagate into the assumptions: the solver found one conflict per
# disjunct, each after deciding most of the formula's variables
# (quadratic: 400 disjuncts took seconds).  Session.dvar gives every
# occurrence the atom's shared variable, linked to the node's other
# derived variables by the rule base's binary implications, so one
# propagation decides these queries.
_SHAPES = {
    "or": lambda p, ys: Or(*[p(y) for y in ys]),
    "and": lambda p, ys: And(*[p(y) for y in ys]),
    "ornot": lambda p, ys: Or(*[Not(p(y)) for y in ys]),
    "nand": lambda p, ys: Not(And(*[p(y) for y in ys])),
    "nor": lambda p, ys: Not(Or(*[p(y) for y in ys])),
}
_WIDE_ANSWERS = [   # proposition/assumptions predicates, answers in _SHAPES x _SHAPES order
    ("positive/positive", "TTNNFNTFFFNFTTTNFTTTFFNNT"),
    ("nonnegative/positive", "TTNNNNTNNNNFNNNNFNNNFFNNN"),
    ("positive/nonnegative", "NNNNFNNFFFNNTTTNNTTTNNNNT"),
    ("real/positive", "TTNNNNTNNNNFNNNNFNNNFFNNN"),
    ("nonzero/nonzero", "TTNNFNTFFFNFTTTNFTTTFFNNT"),
    ("odd/integer", "NNNNFNNFFFNNTTTNNTTTNNNNT"),
    ("positive/negative", "NFNNNFFNNNTTNNNTTNNNNTNNN"),
    ("antihermitian/imaginary", "TTNNNNTNNNNFNNNNFNNNFFNNN"),
    ("infinite/positive_infinite", "TTNNNNTNNNNFNNNNFNNNFFNNN"),
]


@pytest.fixture
def solvers(monkeypatch):
    from satassume.solver import Solver
    made = []
    init = Solver.__init__

    def tracked(self, *a, **k):
        init(self, *a, **k)
        made.append(self)
    monkeypatch.setattr(Solver, "__init__", tracked)
    return made


@pytest.mark.parametrize("preds,answers", _WIDE_ANSWERS)
def test_wide_derived_queries_propagate(preds, answers, solvers):
    pp, ap = [getattr(Q, p) for p in preds.split("/")]
    ys = symbols("v0:60")
    got = ""
    for pk in _SHAPES:
        for ak in _SHAPES:
            solvers.clear()
            r = ask(_SHAPES[pk](pp, ys), _SHAPES[ak](ap, ys))
            got += {True: "T", False: "F", None: "N"}[r]
            conflicts = sum(s._n_conflicts for s in solvers)
            assert conflicts <= 2, (pk, ak, conflicts)
    assert got == answers


@pytest.mark.parametrize("pk,ak", [("or", "or"), ("or", "nor"), ("nor", "or"), ("nor", "nor")])
def test_wide_derived_or_against_or_is_fast(pk, ak):
    ys = symbols("v0:400")
    t = time.perf_counter()
    ask(_SHAPES[pk](Q.nonnegative, ys), _SHAPES[ak](Q.positive, ys))
    ask(_SHAPES[pk](Q.nonzero, ys), _SHAPES[ak](Q.nonzero, ys))
    assert time.perf_counter() - t < 2.0


@pytest.mark.parametrize("pred", ["positive", "negative", "nonnegative", "nonpositive", "real"])
def test_many_negated_conjunctions_keep_their_meaning(pred):
    """A set with many negated conjunctive atoms asserts each through its
    shared literal (``Session.dvar(atom, negunit)``): the literal must
    carry definition -> literal, or ``~positive(x)`` would assert nothing."""
    xs = symbols("x0:10")
    P_ = getattr(Q, pred)
    negs = And(*[Not(P_(x)) for x in xs])
    assert ask(P_(xs[0]), negs) is False
    assert ask(Not(P_(xs[3])), negs) is True
    if pred == "positive":
        assert ask(Q.finite(xs[0]), And(negs, Q.extended_positive(xs[0]))) is False
        assert ask(Q.infinite(xs[1]), And(negs, Q.extended_positive(xs[1]))) is True


# ORs of conjunctions of one node's literals (Or(And(nonnegative(y),
# nonzero(y)), ...)): each conjunction got a Tseitin variable of its own
# per occurrence, and a negated one in the assumptions a clause over basis
# literals, so again one search conflict per disjunct (quadratic, as on the
# original main).  compile._def makes such a conjunction a derived atom of
# its own (the conjunction of its basis literals), with one shared literal.
def _nonneg_nonzero(y):
    return And(Q.nonnegative(y), Q.nonzero(y))


@pytest.mark.parametrize("pp,ap", [(_nonneg_nonzero, _nonneg_nonzero),
                                   (_nonneg_nonzero, Q.positive),
                                   (Q.positive, _nonneg_nonzero)])
def test_wide_conjunctions_propagate(pp, ap, solvers):
    ys = symbols("v0:60")
    got = ""
    for pk in _SHAPES:
        for ak in _SHAPES:
            solvers.clear()
            r = ask(_SHAPES[pk](pp, ys), _SHAPES[ak](ap, ys))
            got += {True: "T", False: "F", None: "N"}[r]
            conflicts = sum(s._n_conflicts for s in solvers)
            assert conflicts <= 2, (pk, ak, conflicts)
    assert got == dict(_WIDE_ANSWERS)["positive/positive"]


# A literal whose definition is a constant (a derived predicate with an
# empty definition, as ``commutative`` with rd/nocomm: ``('&', ())`` is
# TRUE, its negation ``('|', ())`` FALSE) adds no basis literal: TRUE may
# be dropped from a conjunction, FALSE may not (compile._def leaves such a
# conjunction to the general encoding).  Built with stand-in predicates so
# that it runs whether or not some predicate's definition is empty.
def test_conjunction_with_constant_literal(monkeypatch):
    from satassume import rules
    from satassume.compile import _def
    from satassume.engine import Engine
    monkeypatch.setitem(rules.DEF_LITS, "_const_true", ("&", ()))
    monkeypatch.setitem(rules.DEF_LITS, "_const_false", ("|", ()))
    x = xs[0]
    nn = P("nonnegative", x)
    want = (("&", tuple(sorted(rules.DEF_LITS["nonnegative"][1], key=abs))), x)
    for t in (P("_const_true", x), FNot(P("_const_false", x))):
        assert _def(FAnd(t, nn)) == want
    for f in (P("_const_false", x), FNot(P("_const_true", x))):
        assert _def(FAnd(f, nn)) is None
    # end to end with commutative (TRUE for every term in scope, by
    # definition or by its basis variable)
    c = P("commutative", x)
    assert Engine().ask(FAnd(FNot(c), nn), nn) is False
    assert Engine().ask(FNot(FAnd(FNot(c), nn)), nn) is True
    assert Engine().ask(FAnd(c, nn), nn) is True
    assert Engine().ask(FOr(FAnd(FNot(c), nn), nn)) is None
    assert ask(~Q.commutative(x) & Q.nonnegative(x), Q.nonnegative(x)) is False


# A basis atom under a connective (``extended_positive``) and a unit of one
# (``~complex``) are linked to the node's derived literals like two derived
# ones (Session._link: ``extended_positive -> extended_nonnegative``,
# ``nonnegative -> complex``), and an asserted disjunction (``antihermitian``)
# in a set with many derived atoms gets its shared literal like a negated
# conjunction; without them each of these shapes cost one search conflict
# per disjunct (0.75 s at width 400 against 0.03 s before the basis).
_MIXED_PAIRS = [
    "extended_nonnegative/extended_positive", "extended_nonpositive/extended_negative",
    "extended_nonzero/extended_positive", "extended_positive/extended_nonnegative",
    "antihermitian/antihermitian", "extended_positive/antihermitian",
    "nonnegative/complex", "hermitian/complex", "irrational/complex", "infinite/finite",
]


@pytest.mark.parametrize("preds", _MIXED_PAIRS)
def test_wide_basis_against_derived_propagates(preds, solvers):
    pp, ap = [getattr(Q, p) for p in preds.split("/")]
    ys = symbols("v0:60")
    narrow = symbols("v0:9")
    for pk in _SHAPES:
        for ak in _SHAPES:
            solvers.clear()
            r = ask(_SHAPES[pk](pp, ys), _SHAPES[ak](ap, ys))
            conflicts = sum(s._n_conflicts for s in solvers)
            assert conflicts <= 2, (pk, ak, conflicts)
            assert r is ask(_SHAPES[pk](pp, narrow), _SHAPES[ak](ap, narrow)), (pk, ak)
