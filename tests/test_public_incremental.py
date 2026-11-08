"""Incremental against fresh through the public API (issue 323, the test-only
step before 5c7).

``tests/test_solver_incremental.py``'s ``test_incremental_matches_fresh``
family drives ``Solver`` directly: one solver takes clauses, assumptions and
queries in sequence, and every answer is compared with a fresh solver.  These
tests are the same comparison one level up, through what a user calls:
``satassume.Engine`` (``ask``, ``is_``, ``is_many``, ``verdict``) and
``satassume.sympy_api.ask``.  One engine answers a seeded stream of queries
under assumption sets built in sequence (conjuncts added, sets extended and
revisited); every answer, a raise included, must equal what a new engine
answers for that query alone.  ``Engine.ask``'s contract says so: "a query's
answer and cost depend on the query, the set and the registry, never on the
queries before it".

They read no private name, so they run unchanged whatever backs the engine
(the Rust slice's plugin included).  They add to the internals-based family
and replace none of it.  A failure on pure Python is a finding against main:
it gets a minimal repro and a strict xfail naming it, never a looser check.

``PUBLIC_SEEDS`` sets the number of seeds per stream (default 24).
"""
import os
import random

import pytest
from sympy import Function, Q, Symbol, symbols

from satassume import (And, Engine, Equivalent, Exclusive, Implies, InconsistentAssumptions,
                       ITE, Not, Or, P)
from satassume.engine import DictCache
from satassume.sympy_api import ask as sympy_ask

SEEDS = int(os.environ.get("PUBLIC_SEEDS", "24"))
CHUNKS = 4


def _chunk(i: int) -> range:
    return range(i * SEEDS // CHUNKS, (i + 1) * SEEDS // CHUNKS)


def _outcome(f, *args):
    """An answer or the name of what was raised: a raise is an outcome too."""
    try:
        return f(*args)
    except InconsistentAssumptions:
        return "InconsistentAssumptions"
    except Exception as ex:          # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


def _fresh_engine():
    return Engine(cache=DictCache())


# ----------------------------------------------------------------------
# Streams over P atoms (Engine.ask, is_, is_many, verdict)
# ----------------------------------------------------------------------

xs = symbols("a b c d")
PREDS = ("positive", "negative", "zero", "nonzero", "nonnegative", "integer", "even", "odd",
         "rational", "irrational", "real", "prime", "composite", "finite")


def _atom(rng):
    return P(rng.choice(PREDS), rng.choice(xs))


def _formula(rng, depth=2):
    if depth == 0 or rng.random() < 0.3:
        a = _atom(rng)
        return Not(a) if rng.random() < 0.3 else a
    k = rng.randrange(7)
    f = lambda: _formula(rng, depth - 1)                       # noqa: E731
    if k == 0:
        return And(f(), f())
    if k == 1:
        return Or(f(), f())
    if k == 2:
        return Not(f())
    if k == 3:
        return Implies(f(), f())
    if k == 4:
        return Equivalent(f(), f())
    if k == 5:
        return Exclusive(f(), f(), f())
    return ITE(f(), f(), f())


def _set(conj):
    return And(*conj) if conj else None


def _ops(rng, n=30, hold=False):
    """A stream of (op, args): assumption sets built in sequence.  With
    ``hold`` the sets are mostly prefixes of one list that grows, is cut
    back and grows again, so a set often extends the one before it (the
    public counterpart of a held assumption prefix)."""
    conj, out = [], []
    for _ in range(n):
        r = rng.random()
        if hold:
            if r < 0.35:
                conj.append(_formula(rng, 1))
            elif r < 0.45 and conj:
                del conj[rng.randrange(len(conj)):]
        elif r < 0.3:
            conj.append(_formula(rng, 1))
        elif r < 0.4 and conj:
            conj.pop(rng.randrange(len(conj)))
        elif r < 0.45:
            conj = []
        a = _set(conj)
        k = rng.random()
        if k < 0.55:
            out.append(("ask", _formula(rng), a))
        elif k < 0.7:
            out.append(("is_", rng.choice(xs), rng.choice(PREDS)))
        elif k < 0.8:
            out.append(("is_many", rng.choice(xs), tuple(rng.sample(PREDS, 3))))
        elif k < 0.9 and a is not None:
            out.append(("verdict", a))
        else:
            out.append(("ask", _formula(rng), a if a is None or rng.random() < 0.5 else
                        And(a, _formula(rng, 1))))
    return out


def _run(engine, op):
    name, *args = op
    return _outcome(getattr(engine, name), *args)


def run_stream(ops, counts=None):
    """Every op on one engine, in sequence, and on a fresh engine alone."""
    warm = _fresh_engine()
    bad = []
    prev = None
    for i, op in enumerate(ops):
        w = _run(warm, op)
        f = _run(_fresh_engine(), op)
        if w != f:
            bad.append((i, op, w, f))
        if counts is not None:
            counts[op[0]] = counts.get(op[0], 0) + 1
            counts[repr(f) if f in (True, False, None) else "raise"] = \
                counts.get(repr(f) if f in (True, False, None) else "raise", 0) + 1
            a = op[2] if op[0] == "ask" else op[1] if op[0] == "verdict" else None
            if a is not None and prev is not None and a != prev and set(_conj(prev)) <= set(_conj(a)):
                counts["extends"] = counts.get("extends", 0) + 1
            if a is not None and a == prev:
                counts["same_set"] = counts.get("same_set", 0) + 1
            prev = a if a is not None else prev
    return bad


def _conj(a):
    return a.args if isinstance(a, And) else (a,)


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_public_incremental_matches_fresh(chunk):
    for seed in _chunk(chunk):
        bad = run_stream(_ops(random.Random(seed)))
        assert not bad, (seed, bad[:3])


@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_public_incremental_matches_fresh_with_hold(chunk):
    counts: dict = {}
    for seed in _chunk(chunk):
        bad = run_stream(_ops(random.Random(10007 + seed), hold=True), counts)
        assert not bad, (seed, bad[:3])
    assert counts.get("extends", 0) > 0 and counts.get("same_set", 0) > 0, counts


def test_public_mix_covers_the_outcomes():
    """The streams reach every op and every outcome, raises included."""
    counts: dict = {}
    for seed in range(SEEDS):
        run_stream(_ops(random.Random(seed)), counts)
        run_stream(_ops(random.Random(10007 + seed), hold=True), counts)
    for key in ("ask", "is_", "is_many", "verdict", "True", "False", "None", "raise", "extends"):
        assert counts.get(key, 0) > 0, (key, counts)


def test_public_comparison_catches_a_planted_history_dependence(monkeypatch):
    """A planted memo that answers a repeated proposition from an earlier
    set (ignoring the set) is caught by ``run_stream``."""
    real = Engine.ask
    memo: dict = {}

    def leaky(self, proposition, assumptions=None):
        key = (id(self), proposition)
        if key in memo:
            return memo[key]
        memo[key] = real(self, proposition, assumptions)
        return memo[key]

    monkeypatch.setattr(Engine, "ask", leaky)
    a, b = xs[0], xs[1]
    ops = [("ask", P("positive", a), P("positive", a)), ("ask", P("positive", a), Not(P("positive", a))),
           ("ask", P("integer", b), None), ("ask", P("integer", b), P("even", b))]
    assert len(run_stream(ops)) == 2


# ----------------------------------------------------------------------
# Streams through sympy_api.ask, with the theories (LRA, EUF, transfer)
# ----------------------------------------------------------------------

g = Function("g")
u, v, w = symbols("u v w")
n = Symbol("n", integer=True)
y = Symbol("y", real=True)
TERMS = (u, v, n, y, u - v, u + 1, n - 1, g(u), g(n), 2 * v - y)
UNARY = (Q.positive, Q.negative, Q.zero, Q.nonzero, Q.integer, Q.even, Q.prime, Q.finite, Q.real)


def _q_atom(rng):
    r = rng.random()
    if r < 0.55:
        return rng.choice(UNARY)(rng.choice(TERMS))
    rel = rng.choice((Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne))
    return rel(rng.choice(TERMS), rng.choice(TERMS + (0, 1)))


def _q_formula(rng, depth=1):
    if depth == 0 or rng.random() < 0.5:
        a = _q_atom(rng)
        return ~a if rng.random() < 0.25 else a
    l, r = _q_formula(rng, depth - 1), _q_formula(rng, depth - 1)
    return (l & r) if rng.random() < 0.5 else (l | r)


def _q_ops(rng, n=16):
    conj, out = [], []
    for _ in range(n):
        r = rng.random()
        if r < 0.35:
            conj.append(_q_formula(rng, 0))
        elif r < 0.45 and conj:
            del conj[rng.randrange(len(conj)):]
        a = True
        for c in conj:
            a = a & c
        out.append((_q_formula(rng), a))
    return out


CONFIGS = {"default": {}, "whole": {"relevance": False}, "notransfer": {"transfer": False}}


def run_q_stream(ops, cfg):
    warm = Engine(cache=DictCache(), **CONFIGS[cfg])
    bad = []
    for i, (p, a) in enumerate(ops):
        wa = _outcome(sympy_ask, p, a, warm)
        fa = _outcome(sympy_ask, p, a, Engine(cache=DictCache(), **CONFIGS[cfg]))
        if wa != fa:
            bad.append((i, p, a, wa, fa))
    return bad


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_public_incremental_matches_fresh_with_theories(chunk, cfg):
    for seed in _chunk(chunk):
        bad = run_q_stream(_q_ops(random.Random(20011 + seed)), cfg)
        assert not bad, (seed, bad[:3])


# ----------------------------------------------------------------------
# Zero twins: created only under an application (scope.py, "chosen for its
# cost"), so that is where history or path could show.  The queries come
# from Session._glue_of's twin branch and Engine._within_budget's `cross`
# twins (a zero(t) of one formula, t under an application of the other).
# ----------------------------------------------------------------------

k, x = symbols("k x")
SUM = k - x + 1
BASE = Q.integer(k) & Q.integer(x) & Q.negative(k) & Q.positive(x)

ZERO_STREAMS = {
    # the pinned spelling pair (relations.py "Zero is an equality"), then
    # the same with an application over the sum in the set, the query, both
    "pair": [(Q.zero(SUM), BASE), (Q.eq(SUM, 0), BASE), (~Q.zero(SUM), BASE), (Q.nonzero(SUM), BASE),
             (Q.zero(SUM), BASE & Q.finite(g(SUM))), (Q.eq(SUM, 0), BASE & Q.finite(g(SUM))),
             (Q.zero(SUM) | Q.zero(g(SUM)), BASE), (Q.eq(SUM, 0) | Q.zero(g(SUM)), BASE),
             (Q.zero(SUM), BASE), (Q.eq(SUM, 0), BASE)],
    # a zero of the set, its term under an application of the query only
    # (the `cross` twins), then the plain query under the same set
    "cross": [(Q.composite(g(n, 1)), Q.zero(n) & Q.composite(g(0, 1))),
              (Q.positive(n), Q.zero(n) & Q.composite(g(0, 1))),
              (Q.composite(g(n, 1)) | Q.lt(u, v), Q.zero(n) & Q.composite(g(0, 1))),
              (Q.eq(g(n, 1), g(0, 1)), Q.zero(n)), (Q.zero(g(n, 1) - g(0, 1)), Q.zero(n)),
              (Q.composite(g(0, 1) + n), Q.zero(n) & Q.composite(g(0, 1)))],
    # a zero of the query, its term under an application of the set
    "query-zero": [(Q.zero(y), ~Q.finite(g(y)) & Q.finite(g(0))), (Q.zero(g(y)), Q.zero(y) & Q.zero(g(0))),
                   (Q.zero(y) | Q.positive(y), Q.finite(g(y))), (~Q.zero(y), ~Q.finite(g(y)) & Q.finite(g(0))),
                   (Q.zero(y), Q.positive(y) & Q.finite(g(y)))],
}


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("name", list(ZERO_STREAMS))
def test_public_zero_twins_incremental_matches_fresh(name, cfg):
    assert not run_q_stream(ZERO_STREAMS[name], cfg)


@pytest.mark.parametrize("cfg", list(CONFIGS))
def test_public_zero_pair_reversed_matches_fresh(cfg):
    """The pair stream in reverse order: the twin-making queries first."""
    assert not run_q_stream(ZERO_STREAMS["pair"][::-1], cfg)
