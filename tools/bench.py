"""Microbenchmarks: old is_*, new ask(), and satassume on the same queries.

    PYTHONPATH=.:/path/to/sympy python tools/bench.py
"""
import time

from sympy import Symbol, Q, ask, sqrt, exp, sin, Integer

from satassume import Engine
from satassume.engine import DictCache
from satassume.sympy_api import ask as sat_ask


def fresh_objects(n, make):
    return [make(i) for i in range(n)]


def timed(label, objs, fn):
    t = time.perf_counter()
    for o in objs:
        fn(o)
    dt = (time.perf_counter() - t) / len(objs)
    print(f"{dt*1e6:9.2f} us  {label}")


def main():
    N = 1500
    cases = [
        ("(p_i + 1).is_positive", lambda i: Symbol(f'p{i}', positive=True) + 1, 'positive'),
        ("(p_i * q_i).is_positive", lambda i: Symbol(f'p{i}', positive=True) * Symbol(f'q{i}', positive=True), 'positive'),
        ("(u_i**2 + 1).is_zero", lambda i: Symbol(f'u{i}', real=True)**2 + 1, 'zero'),
        ("(sqrt(p_i) + exp(u_i)).is_real", lambda i: sqrt(Symbol(f'p{i}', positive=True)) + exp(Symbol(f'u{i}')), 'real'),
        ("(n_i + m_i).is_even  [unknown]", lambda i: Symbol(f'n{i}', integer=True) + Symbol(f'm{i}', integer=True), 'even'),
    ]
    for label, make, fact in cases:
        objs = fresh_objects(N, make)
        timed("old   " + label, objs, lambda o, f=fact: getattr(o, 'is_' + f))
        objs = fresh_objects(N, make)
        eng = Engine(cache=DictCache())
        timed("sat   " + label, objs, lambda o, f=fact: eng.is_(o, f))
        print(f"           searches={eng.stats['searches']}")
    print()
    y = Symbol('y'); w = Symbol('w')
    ctx = [
        (Q.positive(y + 1), Q.positive(y)),
        (Q.zero(y * w), Q.zero(y)),
        (Q.real(y * w), Q.real(y) & Q.real(w)),
        (Q.even(y + 1), Q.odd(y)),
        (Q.positive(exp(y)), Q.real(y)),
    ]
    for prop, assum in ctx:
        reps = 200
        t = time.perf_counter()
        for _ in range(reps):
            ask(prop, assum)
        told = (time.perf_counter() - t) / reps
        eng = Engine(cache=DictCache())
        t = time.perf_counter()
        for _ in range(reps):
            sat_ask(prop, assum, engine=eng)
        tsat = (time.perf_counter() - t) / reps
        print(f"{told*1e6:9.1f} us sympy.ask   {tsat*1e6:9.1f} us satassume   {prop} | {assum}  -> {ask(prop, assum)} / {sat_ask(prop, assum, engine=eng)}")


if __name__ == "__main__":
    main()
