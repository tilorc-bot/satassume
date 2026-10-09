"""Stress tests: wide shapes of derived predicates, wide Add/Mul.

The shapes that once took quadratic time (one search conflict per
disjunct, see ``tests/test_wide_derived.py``) at the widths the review
benchmarked: Or/And/negations of derived predicates over 100-400 symbols,
the same and different predicates, in the proposition and in the
assumptions; and predicates of Add/Mul of 20-160 symbols.

Two kinds of bound:

* a machine-independent one: the solver's search conflicts per query
  (counted on every ``Solver`` the query creates) stay at most 2, so a
  quadratic search cannot come back whatever the machine;
  this is the primary assertion;
* a loose time ceiling per test case, only a sanity bound against a hang:
  ``ceiling(t)`` is ``max(30 s, 5 x t)`` for ``t`` about 10x what an
  i5-13600T needs, scaled by ``SATASSUME_STRESS_FACTOR`` (default 1; set
  it higher on a very slow runner).  It leaves CI-scale headroom (an M1
  needed up to 1/4 of the old 10x budgets) and still catches a search
  that runs away.
"""
import os
import time

import pytest
from sympy import Add, And, Mul, Not, Or, Q, symbols

from satassume.engine import Engine
from satassume.sympy_api import ask

FACTOR = float(os.environ.get("SATASSUME_STRESS_FACTOR", "1"))


def ceiling(t: float) -> float:
    """The time ceiling of a case whose i5-13600T time is about ``t / 10``."""
    return max(30.0, 5.0 * t) * FACTOR

SHAPES = {
    "or": lambda p, ys: Or(*[p(y) for y in ys]),
    "and": lambda p, ys: And(*[p(y) for y in ys]),
    "ornot": lambda p, ys: Or(*[Not(p(y)) for y in ys]),
    "nand": lambda p, ys: Not(And(*[p(y) for y in ys])),
    "nor": lambda p, ys: Not(Or(*[p(y) for y in ys])),
}

# proposition predicate / assumption predicate: same predicate, implied,
# implying, disjoint and unrelated pairs, plain and extended
PAIRS = [
    "positive/positive", "nonnegative/positive", "positive/nonnegative",
    "nonzero/nonzero", "odd/integer", "extended_nonnegative/extended_positive",
    "infinite/positive_infinite", "real/hermitian", "noninteger/irrational",
    "antihermitian/imaginary", "positive/negative", "transcendental/rational",
]

#: seconds per (pair, width) group of 25 queries (5 shapes x 5 shapes),
#: about 10x the i5-13600T time
BUDGET = {100: 2.0, 200: 5.0, 400: 15.0}


@pytest.fixture
def solvers(monkeypatch):
    from satassume.sat.solver import Solver
    made = []
    init = Solver.__init__

    def tracked(self, *a, **k):
        init(self, *a, **k)
        made.append(self)
    monkeypatch.setattr(Solver, "__init__", tracked)
    return made


def _grid(pp, ap, ys, solvers):
    answers = {}
    for pk, pf in SHAPES.items():
        for ak, af in SHAPES.items():
            p, a = pf(pp, ys), af(ap, ys)
            solvers.clear()
            try:
                r = ask(p, a, Engine())
            except ValueError:
                r = "ValueError"
            conflicts = sum(s._n_conflicts for s in solvers)
            assert conflicts <= 2, (pk, ak, conflicts)
            answers[pk, ak] = r
    return answers


@pytest.mark.parametrize("n", sorted(BUDGET))
@pytest.mark.parametrize("pair", PAIRS)
def test_wide_shapes(pair, n, solvers):
    pp, ap = [getattr(Q, p) for p in pair.split("/")]
    ys = symbols("v0:%d" % n)
    t = time.perf_counter()
    got = _grid(pp, ap, ys, solvers)
    dt = time.perf_counter() - t
    assert dt < ceiling(BUDGET[n]), (pair, n, dt)
    # the answers do not depend on the width: compare with a narrow run
    assert got == _grid(pp, ap, symbols("v0:9"), solvers)


@pytest.mark.parametrize("n", [100, 400])
def test_wide_mixed_predicates(n, solvers):
    """Each disjunct its own derived predicate, cycling through 6."""
    preds = [Q.positive, Q.nonnegative, Q.nonzero, Q.negative_infinite, Q.odd, Q.irrational]
    ys = symbols("v0:%d" % n)
    lits = [preds[i % len(preds)](y) for i, y in enumerate(ys)]
    t = time.perf_counter()
    for p, a, expected in [
        (Or(*lits), And(*lits), True),
        (Not(And(*lits)), And(*lits), False),
        (Or(*lits), Not(Or(*lits)), False),
        (Q.real(ys[0]), Or(*lits), None),
        (Or(*[Not(l) for l in lits]), Not(Or(*[Not(l) for l in lits])), False),
    ]:
        solvers.clear()
        assert ask(p, a, Engine()) is expected
        assert sum(s._n_conflicts for s in solvers) <= 2
    assert time.perf_counter() - t < ceiling(2.0 if n == 100 else 10.0)


#: (predicate of each symbol, predicate asked of the sum/product, answers)
_ARITH = [
    ("positive", "positive", True, True),
    ("nonnegative", "nonnegative", True, True),
    ("extended_positive", "extended_positive", True, True),
    ("real", "real", True, True),
    ("integer", "integer", True, True),
    ("nonzero", "nonzero", None, True),
    ("finite", "finite", True, True),
    ("negative", "negative", True, None),
    ("odd", "even", None, False),   # a product of odds is odd; ask_ref: None for the sum
]


@pytest.mark.parametrize("n", [20, 40, 80, 160])
def test_wide_add_mul(n, solvers):
    xs = symbols("x0:%d" % n)
    t = time.perf_counter()

    def ask_(p, a):
        solvers.clear()
        r = ask(p, a, Engine())
        assert sum(s._n_conflicts for s in solvers) <= 2, (p.func, n)
        return r

    for fact, asked, add_ans, mul_ans in _ARITH:
        a = And(*[getattr(Q, fact)(x) for x in xs])
        q = getattr(Q, asked)
        assert ask_(q(Add(*xs)), a) is add_ans, (fact, "Add")
        r = ask_(q(Mul(*xs)), a)
        if fact == "negative":      # sign of a product of n negatives
            mul_ans = n % 2 == 1
        assert r is mul_ans, (fact, "Mul", r)
    # a sum/product of mixed facts and the negated question
    half = n // 2
    a = And(*([Q.positive(x) for x in xs[:half]] + [Q.nonnegative(x) for x in xs[half:]]))
    assert ask_(Q.positive(Add(*xs)), a) is True
    assert ask_(~Q.nonnegative(Mul(*xs)), a) is False
    assert time.perf_counter() - t < ceiling(2.0 + n / 10.0)
