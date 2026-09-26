"""Differential fuzz of relevance: component-keyed answers against whole-set answers.

    PYTHONHASHSEED=0 PYTHONPATH=.:SYMPY python tools/relevance_fuzz.py SEED0 N [--sets K] [--queries Q]
        [--relational whole|rationals]

For each seed, two fresh engines, ``Engine(relevance=True)`` and
``Engine(relevance=False)``, get the same sequence of ``sympy_api.ask``
calls: ``K`` random assumption sets over five symbols (unary facts,
relations with each other and with 0, 1, 1/2, pi, pi/2, sqrt(2), a Float,
``f(x)`` terms, disjunctions, negations), each asked ``Q`` random
propositions.  Every answer (True / False / None / ``error``) is compared.

Prints one JSON line of counts.  Answers that are None on one side only
are counted (``whole-only`` / ``comp-only``) and listed with ``--show``;
they are allowed (answering under fewer conjuncts is sound, and the
engine's search is incomplete), but expected to be rare.  Every other
difference is listed with the answers of the same query in two fresh
engines (``fresh``: [comp, whole]):

* ``contradiction``: True on one side, False on the other;
* ``error-comp`` / ``error-whole``: an error on that side, a definite
  answer on the other;
* ``error-comp-none`` / ``error-whole-none``: an error on that side, None
  on the other.

``KIND-fresh`` counts those that still differ in fresh engines.  Exit
status 1 on a contradiction, or on a one-sided error that reproduces in
fresh engines; a one-sided error that does not is the engines' history
(fact cache, LRU sessions after the seed's earlier sets), which the old
path depends on in the same way.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter

from sympy import Function, Or, Q, Rational, S, Symbol, pi, sqrt, And, Float

from satassume import sympy_api as api
from satassume.engine import Engine

SYMS = [Symbol("x"), Symbol("y", real=True), Symbol("z"), Symbol("u", integer=True),
        Symbol("v", positive=True)]
f = Function("f")
CONSTS = [S.Zero, S.One, Rational(1, 2), S(-2), pi, pi / 2, sqrt(2)]
UNARY = ["positive", "negative", "zero", "nonzero", "nonnegative", "real", "integer",
         "even", "odd", "prime", "rational", "finite", "irrational"]
RELS = [Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne]


class Gen:
    def __init__(self, rng, syms):
        self.rng, self.syms = rng, syms

    def sym(self):
        return self.rng.choice(self.syms)

    def term(self):
        r = self.rng.random()
        s = self.sym()
        if r < 0.5:
            return s
        if r < 0.6:
            return s + 1
        if r < 0.7:
            return 2 * s
        if r < 0.8:
            return s * self.sym()
        if r < 0.9:
            return f(s)
        return s + self.sym()

    def side(self):
        r = self.rng.random()
        if r < 0.3:
            return self.rng.choice(CONSTS)
        if r < 0.33:
            return Float("0.5")          # unreadable by the theories
        return self.term()

    def atom(self):
        if self.rng.random() < 0.6:
            return getattr(Q, self.rng.choice(UNARY))(self.term())
        a, b = self.term(), self.side()
        return self.rng.choice(RELS)(a, b)

    def literal(self):
        a = self.atom()
        return ~a if self.rng.random() < 0.25 else a

    def conjunct(self):
        if self.rng.random() < 0.2:
            return Or(self.literal(), self.literal())
        return self.literal()

    def assumptions(self):
        n = self.rng.randint(2, 5)
        return And(*[self.conjunct() for _ in range(n)])

    def query(self):
        if self.rng.random() < 0.15:
            return Or(self.atom(), self.atom())
        return self.atom()


def answer(p, a, eng):
    try:
        return api.ask(p, a, engine=eng)
    except ValueError:
        return "error"


def run(seed0, n, nsets, nq, show):
    c = Counter()
    shown = []
    bad = False
    for seed in range(seed0, seed0 + n):
        rng = random.Random(seed)
        # a subset of the symbols per seed, so sets split often
        g = Gen(rng, SYMS[: rng.randint(2, 5)])
        comp, whole = Engine(relevance=True), Engine(relevance=False)
        for _ in range(nsets):
            a = g.assumptions()
            if a in (S.true, S.false):
                continue
            for _ in range(nq):
                p = g.query()
                rc, rw = answer(p, a, comp), answer(p, a, whole)
                c["queries"] += 1
                if rc == rw:
                    c["same"] += 1
                    c["same-" + str(rc)] += 1
                    continue
                if "error" in (rc, rw):
                    side = "comp" if rc == "error" else "whole"
                    other = rw if side == "comp" else rc
                    # an error on one side only: against a definite answer
                    # (``error-comp``/``error-whole``) or against None
                    # (``error-comp-none``/``error-whole-none``)
                    k = "error-" + side + ("-none" if other is None else "")
                elif rc is None:
                    k = "whole-only"
                elif rw is None:
                    k = "comp-only"
                else:
                    k = "contradiction"
                c[k] += 1
                row = {"seed": seed, "kind": k, "p": str(p), "a": str(a),
                       "comp": rc, "whole": rw}
                if k not in ("whole-only", "comp-only"):
                    # does it reproduce in fresh engines (one query each)?
                    fc = answer(p, a, Engine(relevance=True))
                    fw = answer(p, a, Engine(relevance=False))
                    row["fresh"] = [fc, fw]
                    if fc != fw:
                        c[k + "-fresh"] += 1
                        bad = True
                    elif k == "contradiction":
                        bad = True
                if len(shown) < show or k not in ("whole-only", "comp-only"):
                    shown.append(row)
        c["relevant"] += comp.stats["relevant"]
    return c, shown, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seed0", type=int)
    ap.add_argument("n", type=int)
    ap.add_argument("--sets", type=int, default=4)
    ap.add_argument("--queries", type=int, default=6)
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--relational", choices=("whole", "rationals"),
                    help="sympy_api.RELATIONAL for the relevance side")
    args = ap.parse_args()
    if args.relational:
        api.RELATIONAL = args.relational
        api._KEYS.clear()
    c, shown, bad = run(args.seed0, args.n, args.sets, args.queries, args.show)
    for s in shown:
        print(json.dumps(s))
    print(json.dumps({"seed0": args.seed0, "n": args.n, **c}))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
