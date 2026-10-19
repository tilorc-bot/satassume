"""Sums and products of many terms (#180 C-WIDEADD).

The per-term rules of the Add template (one rule of n literals per term)
made its pattern O(n^2): an Add of 4368 terms (heurisch's ansatz) took
more than 4 GB, 600 symbols 720 MB and 7 s.  Past ``MAX_ONEOUT_WIDE``
terms the strict-sign rule of Add and the zero rule of Mul are one formula
each (linear), the other per-term rules are not emitted, and a node with
more non-constant terms than the discovery budget is over the budget
before any of its templates is built.
"""
import time

import pytest
from sympy import Add, And, Integer, Mul, Q, S, oo, prime, sqrt, symbols

from satassume import DictCache, Engine
from satassume.knowledge.templates import registry
from satassume.knowledge.templates.core import MAX_ONEOUT_WIDE
from satassume.sympy_api import ask


def fresh():
    return Engine(cache=DictCache())


def literals(expr):
    """Literals of the clauses and atoms of the formulas of ``expr``'s
    templates (wide rules included)."""
    from satassume.sat.formula import atoms_of
    comp, formulas = registry.clauses_for(expr)
    n = sum(len(c[0]) for cp in comp for c in cp.pattern.clauses)
    n += sum(len(r[0]) + len(r[1]) for cp in comp for r in cp.pattern.wide)
    return n + sum(len(list(atoms_of(f))) for f in formulas)


@pytest.mark.parametrize("n", [MAX_ONEOUT_WIDE + 1, 100, 300])
def test_wide_add_templates_are_linear_in_literals(n):
    xs = symbols(f"x0:{n}")
    assert literals(Add(*xs)) <= 40 * n
    assert literals(Mul(*xs)) <= 40 * n


@pytest.mark.parametrize("n", [300, 600])
def test_wide_sum_reproducer_is_fast(n):
    # #180: 300 symbols took 1.28 s and 268 MB, 600 symbols 7.4 s and 720 MB
    e = Add(*symbols(f"x0:{n}"))
    t = time.perf_counter()
    assert fresh().is_(e, "finite") is None
    assert time.perf_counter() - t < 5.0


def test_sum_wider_than_the_budget_builds_no_template(monkeypatch):
    # heurisch's ansatz: 4368 terms; only the cone weight decides it
    e = Add(*symbols("x0:1000"))
    built = []
    real = registry.clauses_for
    monkeypatch.setattr(registry, "clauses_for", lambda o: (built.append(o), real(o))[1])
    eng = fresh()                   # binds the patched registry.clauses_for
    assert eng.is_(e, "finite") is None
    assert eng.last_budget_limited
    assert e not in built
    # the same answers as a budget large enough to build it would give,
    # but within the default budget a sum of closed terms is still decided
    s = Add(*[sqrt(prime(i)) for i in range(1, 101)])
    assert fresh().is_(s, "finite") is True


@pytest.mark.parametrize("n", [MAX_ONEOUT_WIDE + 1, 160])
def test_wide_strict_sign(n):
    xs = symbols(f"x0:{n}")
    s = Add(*xs)
    a = And(Q.positive(xs[0]), *[Q.nonnegative(x) for x in xs[1:]])
    assert ask(Q.positive(s), a, fresh()) is True
    a = And(Q.negative(xs[-1]), *[Q.nonpositive(x) for x in xs[:-1]])
    assert ask(Q.negative(s), a, fresh()) is True
    assert ask(Q.extended_positive(s), And(*[Q.extended_nonnegative(x) for x in xs[1:]],
                                           Q.positive_infinite(xs[0])), fresh()) is True
    # not entailed: no strictly positive term, or one term of the wrong sign
    assert ask(Q.positive(s), And(*[Q.nonnegative(x) for x in xs]), fresh()) is None
    a = And(Q.positive(xs[0]), Q.real(xs[1]), *[Q.nonnegative(x) for x in xs[2:]])
    assert ask(Q.positive(s), a, fresh()) is None


@pytest.mark.parametrize("c, nonneg, one_positive", [
    (Integer(1), True, True), (S.Half, True, True), (S.Zero, None, True),
    (Integer(-1), None, None), (oo, True, None)])
def test_wide_strict_sign_with_a_constant_term(c, nonneg, one_positive):
    # extended_positive of c + (nonnegative terms), and positive with x0
    # positive; c = oo makes the sum +oo, which is not positive (False; the
    # infinite-sum rules stop at MAX_ONEOUT terms, so None)
    xs = symbols(f"x0:{MAX_ONEOUT_WIDE + 3}")
    s = Add(c, *xs, evaluate=False)
    a = And(*[Q.nonnegative(x) for x in xs])
    assert ask(Q.extended_positive(s), a, fresh()) is nonneg
    a = And(Q.positive(xs[0]), *[Q.nonnegative(x) for x in xs[1:]])
    assert ask(Q.positive(s), a, fresh()) is one_positive


def test_wide_zero_product():
    xs = symbols(f"x0:{MAX_ONEOUT_WIDE + 8}")
    p = Mul(*xs)
    a = And(Q.zero(xs[3]), *[Q.finite(x) for x in xs])
    assert ask(Q.zero(p), a, fresh()) is True
    # 0*oo is nan: a factor that may be infinite leaves it open
    a = And(Q.zero(xs[3]), *[Q.finite(x) for x in xs[1:]])
    assert ask(Q.zero(p), a, fresh()) is None


@pytest.mark.parametrize("c", [-oo, S.ComplexInfinity, S.NaN, S.ImaginaryUnit])
def test_wide_strict_sign_with_a_constant_that_is_not_nonnegative(c):
    # -oo + (...) is -oo, zoo and nan are not real, I + (real) is not real:
    # the sum is never positive, so the wide formula must not fire
    xs = symbols(f"x0:{MAX_ONEOUT_WIDE + 3}")
    s = Add(c, *xs, evaluate=False)
    a = And(Q.positive(xs[0]), *[Q.nonnegative(x) for x in xs[1:]])
    assert ask(Q.positive(s), a, fresh()) is not True
    assert ask(Q.extended_positive(s), a, fresh()) is not True


@pytest.mark.parametrize("n", [MAX_ONEOUT_WIDE, MAX_ONEOUT_WIDE + 1])
def test_strict_sign_and_zero_rules_agree_at_the_threshold(n):
    xs = symbols(f"x0:{n}")
    s, p = Add(*xs), Mul(*xs)
    a = And(Q.positive(xs[5]), *[Q.nonnegative(x) for x in xs])
    assert ask(Q.positive(s), a, fresh()) is True
    a = And(Q.negative(xs[5]), *[Q.nonpositive(x) for x in xs])
    assert ask(Q.negative(s), a, fresh()) is True
    a = And(Q.zero(xs[5]), *[Q.finite(x) for x in xs])
    assert ask(Q.zero(p), a, fresh()) is True


def test_wide_product_with_a_constant_factor():
    xs = symbols(f"x0:{MAX_ONEOUT_WIDE + 3}")
    a = And(*[Q.finite(x) for x in xs])
    assert ask(Q.zero(Mul(S.Zero, *xs, evaluate=False)), a, fresh()) is True
    # 0*oo, 0*zoo and 0*nan are nan
    for c in (oo, S.ComplexInfinity, S.NaN):
        p = Mul(S.Zero, c, *xs, evaluate=False)
        assert ask(Q.zero(p), a, fresh()) is not True
        p = Mul(c, *xs, evaluate=False)
        assert ask(Q.zero(p), And(Q.zero(xs[0]), a), fresh()) is not True


def test_wide_terms_around_the_budget():
    # repeated terms count once and number atoms not at all
    x = symbols("x")
    ints = [Integer(i) for i in range(2, 16)]
    eng = Engine(cache=DictCache(), discovery_budget=10)
    assert ask(Q.finite(Add(*([x] * 12), evaluate=False)), Q.finite(x), eng) is True
    assert ask(Q.finite(Add(x, *ints, evaluate=False)), Q.finite(x), eng) is True
