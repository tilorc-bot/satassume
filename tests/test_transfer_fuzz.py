"""Fuzz: predicate transfer (satassume.transfer) against explicit clauses.

The engine with transfer (``Engine(transfer=True)``) is compared with an
oracle engine without it (``transfer=False``) that gets the transfer as
explicit clauses in the assumptions, the plan's section 5.3 oracle: for
every pair ``a, b`` of the problem's terms (numbers against numbers left
out: distinct values never merge)

    eq(a, b) -> (P(a) <-> P(b))        for each of the 33 predicates

and congruence spelled out for the one function symbol,
``eq(a, b) -> eq(f(a), f(b))``.  Terms are ``x, y, z, f(x), f(y)`` and the
numbers ``0, 1, 2, -1, 1/2``; assumptions are random conjunctions of unary
literals, ``eq``/``ne`` atoms and small disjunctions; queries are unary
predicates or equalities.  One engine pair per seed answers several
assumption sets, some repeated (reused sessions and a shared fact cache).

Two theory setups:

* ``euf`` (EUF only): both sides have the same theories, so answers must be
  identical (True / False / None / ValueError);
* ``lra`` (the default LRA and EUF): the oracle's extra equality atoms also
  reach LRA, which may derive equalities from orderings (``zero(x) &
  zero(y)`` gives ``x = y`` there); transfer does not take equalities from
  LRA by design, so here only soundness is checked: the engine never
  contradicts the oracle, never raises where the oracle answers, and every
  definite engine answer equals the oracle's.

In both, when the answers differ and the (oracle) assumptions are
unsatisfiable, any pair of definite answers or ValueError is accepted: the
engine checks the assumptions only by propagation when propagation already
decides the query, so the side whose propagation is stronger may answer
where the other one searches and finds the inconsistency (``x = 1 & f(x) =
1 & f(y) = 1/2 & (x = 2 | y = f(x))``: transfer decides
``imaginary(f(x))`` by propagation; the oracle searches and raises).

Seeds: ``TRANSFER_FUZZ_SEEDS`` (default 80) from ``TRANSFER_FUZZ_SEED0``;
by hand ``python tests/test_transfer_fuzz.py SEED0 N [euf|lra]`` (about
200 seeds a minute; keep each call under 270 s).
"""
from __future__ import annotations

import os
import random
import sys

import pytest

sympy = pytest.importorskip("sympy") if __name__ != "__main__" else __import__("sympy")

from sympy import Function, Rational, S, Symbol

from satassume.engine import Engine, InconsistentAssumptions
from satassume.euf_adapter import EUFAdapter
from satassume.formula import And, Equivalent, Implies, Not, Or, P
from satassume.relations import AdapterSpec, default_specs, relation_atom
from satassume.rules import PREDICATES

x, y, z = Symbol("x"), Symbol("y"), Symbol("z")
f = Function("f")
SYMS = [x, y, z, f(x), f(y)]
NUMS = [S.Zero, S.One, S(2), S.NegativeOne, Rational(1, 2)]
COMMON = ["positive", "negative", "zero", "nonzero", "integer", "even", "odd",
          "prime", "composite", "rational", "irrational", "real", "complex",
          "imaginary", "finite", "infinite", "nonnegative", "noninteger"]


def _is_num(t):
    return t in NUMS


def eq(a, b):
    return relation_atom("eq", a, b)


class Gen:
    def __init__(self, seed):
        self.r = random.Random(seed)

    def term(self, nums=0.25):
        r = self.r
        return r.choice(NUMS) if r.random() < nums else r.choice(SYMS)

    def pred(self):
        r = self.r
        return r.choice(COMMON) if r.random() < 0.7 else r.choice(PREDICATES)

    def unary(self):
        a = P(self.pred(), self.term(0.08))
        return Not(a) if self.r.random() < 0.35 else a

    def equality(self):
        a = self.term(0.35)
        b = self.term(0.35)
        while b == a or (_is_num(a) and _is_num(b)):
            b = self.term(0.35)
        e = eq(a, b)
        return Not(e) if self.r.random() < 0.25 else e

    def literal(self):
        return self.equality() if self.r.random() < 0.45 else self.unary()

    def assumptions(self):
        r = self.r
        items = []
        for _ in range(r.randint(1, 4)):
            if r.random() < 0.15:
                items.append(Or(self.literal(), self.literal()))
            else:
                items.append(self.literal())
        if not any(_has_eq(i) for i in items):
            items.append(self.equality())
        return And(*items) if len(items) > 1 else items[0]

    def query(self):
        return self.equality() if self.r.random() < 0.25 else self.unary()


def _has_eq(f):
    from satassume.formula import atoms_of
    return any(a.pred == "eq" for a in atoms_of(f))


def _terms(*fs):
    from satassume.formula import atoms_of
    out = []
    for fm in fs:
        for a in atoms_of(fm):
            args = a.expr if a.pred == "eq" else (a.expr,)
            for t in args:
                if t not in out:
                    out.append(t)
                for c in getattr(t, "args", ()):
                    if c not in out and (c in SYMS or c in NUMS):
                        out.append(c)
    return out


def oracle_assumptions(assum, query):
    ts = _terms(assum, query)
    extra = []
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            if _is_num(a) and _is_num(b):
                continue
            e = eq(a, b)
            extra.append(Implies(e, And(*[Equivalent(P(p, a), P(p, b)) for p in PREDICATES])))
            fa, fb = f(a), f(b)
            if fa in ts and fb in ts:
                extra.append(Implies(e, eq(fa, fb)))
    return And(assum, *extra)


def answer(eng, prop, assum):
    try:
        return eng.ask(prop, assum)
    except InconsistentAssumptions:
        return "error"


def inconsistent(specs, assum) -> bool:
    """The assumptions are unsatisfiable (full search, fresh engine)."""
    e = Engine(relations=list(specs), transfer=False)
    s, lits = e._context_session(assum)
    return not s.solver.solve(lits)


def euf_specs():
    return [AdapterSpec("euf", EUFAdapter, False)]


def run_seed(seed, setup="euf", log=None):
    g = Gen(seed)
    specs = euf_specs() if setup == "euf" else default_specs()
    eng = Engine(relations=specs, transfer=True)
    ora = Engine(relations=list(specs), transfer=False)
    sets = [g.assumptions() for _ in range(g.r.randint(1, 3))]
    counts = {"same": 0, "definite": 0, "oracle_more": 0}
    for _ in range(g.r.randint(3, 8)):
        assum = g.r.choice(sets)
        q = g.query()
        a = answer(eng, q, assum)
        o = answer(ora, q, oracle_assumptions(assum, q))
        if log is not None:
            log.append((assum, q, a, o))
        where = f"seed {seed} ({setup}): ask({q}, {assum}) = {a}, oracle {o}"
        if a != o and inconsistent(specs, oracle_assumptions(assum, q)):
            # The engine checks the assumptions by propagation only when
            # propagation decides the query (Session.query_literal), so under
            # inconsistent assumptions either side may give a definite answer
            # where the other finds the inconsistency.  Never None.
            assert a is not None and o is not None, where
            counts["inconsistent_differs"] = counts.get("inconsistent_differs", 0) + 1
            continue
        if setup == "euf":
            assert a == o, where
        else:
            assert a is None or a == o, where
            if a != o:
                counts["oracle_more"] += 1
        counts["same" if a == o else "diff"] = counts.get("same" if a == o else "diff", 0) + 1
        if a is not None:
            counts["definite"] += 1
    return counts


SEEDS = int(os.environ.get("TRANSFER_FUZZ_SEEDS", "80"))
SEED0 = int(os.environ.get("TRANSFER_FUZZ_SEED0", "0"))
CHUNKS = 6


@pytest.mark.parametrize("setup", ["euf", "lra"])
@pytest.mark.parametrize("chunk", range(CHUNKS))
def test_transfer_against_explicit_clauses(chunk, setup):
    n = (SEEDS + CHUNKS - 1) // CHUNKS
    lo = SEED0 + chunk * n
    for seed in range(lo, min(lo + n, SEED0 + SEEDS)):
        run_seed(seed, setup)


if __name__ == "__main__":
    import time
    seed0, n = int(sys.argv[1]), int(sys.argv[2])
    setup = sys.argv[3] if len(sys.argv) > 3 else "euf"
    tot = {}
    t0 = time.time()
    for s in range(seed0, seed0 + n):
        for k, v in run_seed(s, setup).items():
            tot[k] = tot.get(k, 0) + v
    print(f"seeds {seed0}..{seed0 + n - 1} ({setup}): {tot} in {time.time() - t0:.1f}s")
