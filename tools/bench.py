"""Microbenchmarks: contextual ``ask(prop, assumptions)``, SymPy versus satassume.

    PYTHONPATH=.:/path/to/sympy python tools/bench.py [reps]

Every case is in scope (unary scalar predicates on scalar expressions).
Each side answers the same query ``reps`` times; the mean per call is
printed together with both answers, which must match.
"""
import sys
import time

from sympy import Symbol, Q, ask, exp

from satassume import Engine
from satassume.engine import DictCache
from satassume.sympy_api import ask as sat_ask


def cases():
    y, w, z = Symbol('y'), Symbol('w'), Symbol('z')
    return [
        (Q.positive(y + 1), Q.positive(y)),
        (Q.zero(y * w), Q.zero(y) & Q.finite(w)),
        (Q.real(y * w), Q.real(y) & Q.real(w)),
        (Q.even(y + 1), Q.odd(y)),
        (Q.positive(exp(y)), Q.real(y)),
        # nested Pow: positive base to a real power, squared
        (Q.positive(((y**2 + 1)**w)**2), Q.real(y) & Q.real(w)),
        # three-term Add with mixed assumptions
        (Q.positive(y + w**2 + z), Q.positive(y) & Q.real(w) & Q.nonnegative(z)),
        # compound proposition
        (Q.positive(y) | Q.negative(y), Q.real(y) & Q.nonzero(y)),
    ]


def main(reps=200):
    print(f"{'sympy.ask':>12s} {'satassume':>12s}   query -> sympy / satassume")
    for prop, assum in cases():
        t = time.perf_counter()
        for _ in range(reps):
            r_sympy = ask(prop, assum)
        told = (time.perf_counter() - t) / reps
        eng = Engine(cache=DictCache())
        t = time.perf_counter()
        for _ in range(reps):
            r_sat = sat_ask(prop, assum, engine=eng)
        tsat = (time.perf_counter() - t) / reps
        flag = "" if r_sympy == r_sat else "   MISMATCH"
        print(f"{told*1e6:9.1f} us {tsat*1e6:9.1f} us   {prop} | {assum} -> {r_sympy} / {r_sat}{flag}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
