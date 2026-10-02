"""Random sum-heavy queries under every engine preset, for an answer
comparison between two checkouts (#113: the derived node of ``r + c``).

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python \\
        tools/sum_fuzz.py SEED N OUT.json

``N`` queries from ``random.Random(SEED)``: a predicate on a sum of 1-4
terms (symbols under random declarations, small multiples, ``exp``,
``log``, ``sqrt``, ``Abs`` of nested sums, products), a Rational term
added with probability 0.7, under 0-2 conjuncts on the same sum shifted
by a constant, another such sum or a symbol.  Each query is asked with a
fresh engine of every preset of ``harness.state.PRESETS``; the output is
one row per query (its srepr and the answer per preset).  Run it from
each checkout and compare the rows.
"""
import json
import random
import sys

from sympy import Abs, Q, Rational, Symbol, exp, log, sqrt, srepr

from harness.state import PRESETS
from satassume.sympy_api import ask

DECL = [{}, {"real": True}, {"positive": True}, {"nonnegative": True}, {"integer": True},
        {"integer": True, "positive": True}, {"negative": True}]
PREDS = ["positive", "negative", "nonnegative", "real", "finite", "integer", "rational",
         "irrational", "even", "odd", "zero", "nonzero", "algebraic", "transcendental"]
CONSTS = [Rational(1), Rational(2), Rational(-1), Rational(-3, 2), Rational(1, 2), Rational(5)]


def gen(rng):
    syms = [Symbol(n, **rng.choice(DECL)) for n in "xyzwk"]
    def atom(d):
        r = rng.random()
        if d > 1 or r < 0.4:
            s = rng.choice(syms)
            return s if rng.random() < 0.7 else rng.choice([2, 3, -1]) * s
        if r < 0.6:
            return rng.choice([exp, log, sqrt, Abs])(term(d + 1))
        return atom(d + 1) * atom(d + 1)
    def term(d=0):
        n = rng.randint(1, 4)
        t = sum((atom(d) for _ in range(n)), 0)
        if rng.random() < 0.7:
            t = t + rng.choice(CONSTS)
        return t
    t = term()
    p = getattr(Q, rng.choice(PREDS))(t)
    a = True
    for _ in range(rng.randint(0, 2)):
        u = rng.choice([t - rng.choice(CONSTS), term(), rng.choice(syms)])
        f = getattr(Q, rng.choice(PREDS))(u)
        a = f if a is True else a & f
    return p, a


def main():
    seed, n, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    rng = random.Random(seed)
    res = []
    for _ in range(n):
        p, a = gen(rng)
        row = {"q": srepr(p) + " | " + (srepr(a) if a is not True else "True")}
        for name, cfg in PRESETS.items():
            try:
                row[name] = repr(ask(p, a, engine=cfg.make()))
            except ValueError:
                row[name] = "error"
            except Exception as e:  # noqa: BLE001 (compared as an outcome)
                row[name] = "exc:" + type(e).__name__
        res.append(row)
    with open(out, "w") as fh:
        json.dump(res, fh)


if __name__ == "__main__":
    main()
