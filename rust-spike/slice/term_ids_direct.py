"""Slice B, a direct comparison: random pairs of terms, Rust's answer on ids against Python's own function on the objects.

    term_ids_direct.py N SEED [--plant swap|wise|key|sub] [--out FILE]

The workloads reach `_termwise` and `_eq_links` thinly, so this is what reaches them. Per pair, each in its own table:
`relation_atom`'s eq sides, `a - b` with its form, `_termwise`, `_eq_links`' difference, and the sort keys of the difference and
of a product `a*b`, the shape at the LRA sort sites. A refusal is counted by reason and is no evidence for or against; a
`differs:*` is a finding and its first few are printed. `--plant` breaks this script's reading of one Rust answer, to show that
the comparison catches it. Exit status: 0 with no `differs:*`.
"""
import argparse
import collections
import random
import sys

from sympy import And, Function, I, Mul, Q, Rational as Rat, S, Symbol, exp, log, oo, pi, sqrt, sin
from sympy.core.sorting import default_sort_key

import convert
import sa_solver
import term_live as TL
from satassume import relations as R, sympy_api as A

x, y, z, w = Symbol('x'), Symbol('y'), Symbol('z'), Symbol('w', positive=True)
f, g = Function('f'), Function('g')
ATOMS = [x, y, z, w, f(x), f(y), g(x), f(S(1)), g(S(1)), pi, sqrt(2), S(2), S(-3), Rat(1, 2), I, exp(x), exp(S(1)), log(y), sin(x),
         x**2, y**-1, w**Rat(1, 2), S(2)**x, exp(y), exp(x + 1), exp(-y)]
#: Rare, so that most pairs aren't refusals: each is a shape the algebra refuses.
RARE = [S(1.5)*x, oo, -oo, S.NaN, S.ComplexInfinity, Symbol('n', commutative=False), exp(log(y), evaluate=False),
        exp(2*log(x), evaluate=False), exp(S(0), evaluate=False), exp(Symbol('z0', zero=True), evaluate=False)]


def term(r, depth=2):
    k = r.random()
    if depth == 0 or k < 0.3:
        return r.choice(RARE) if r.random() < 0.03 else r.choice(ATOMS)
    n = r.choice((2, 2, 3))
    args = [term(r, depth - 1) for _ in range(n)]
    if k < 0.65:
        return sum(args[1:], args[0])
    return Mul(*args)


def same_form(o, real):
    return o == real and type(o) is type(real) and getattr(o, 'args', ()) == getattr(real, 'args', ())


class Run:
    def __init__(self, plant):
        self.c = collections.Counter()
        self.bad = []
        self.plant = plant

    def differs(self, what, *detail):
        self.c['differs:' + what] += 1
        if len(self.bad) < 20:
            self.bad.append((what,) + tuple(repr(d)[:200] for d in detail))

    def step(self, what, f):
        """`f` compares one thing. A refusal counts by reason; Python's own raise on the same input was tested by `f`."""
        self.c['asked:' + what] += 1
        try:
            f()
        except sa_solver.TermRefuse as e:
            self.c[f'refused:{what}:{e}'] += 1
        else:
            self.c['answered:' + what] += 1

    def pair(self, a, b):
        env = A.default_engine()
        c = convert.convert(And(Q.positive(a), Q.positive(b)), True, env)
        if isinstance(c, convert.Kept):
            self.c['kept:' + c.reason] += 1
            return
        q = TL._Query(c)
        i, j = q.ids[a], q.ids[b]
        self.c['pairs'] += 1
        self.step('eq_sides', lambda: self.eq_sides(q, i, j, a, b))
        self.step('sub', lambda: self.sub(q, i, j, a, b))
        self.step('product-key', lambda: self.product(q, a, b))

    def eq_sides(self, q, i, j, a, b):
        u, v = q.table.eq_sides(i, j)
        if self.plant == 'swap':
            u, v = v, u
        try:
            want = R.relation_atom('eq', a, b).expr
        except Exception as e:      # Python raised where Rust answered
            self.differs('eq_sides-python-raised', a, b, e)
            return
        got = (TL.scaffold(q, u, 'direct'), TL.scaffold(q, v, 'direct'))
        if not all(same_form(p, r) for p, r in zip(got, want)):
            self.differs('eq_sides', a, b, got, want)

    def sub(self, q, i, j, a, b):
        k = q.table.sub(i, j)
        if self.plant == 'sub':
            k = i
        real = a - b
        o = TL.scaffold(q, k, 'direct')
        if not same_form(o, real):
            self.differs('sub', a, b, o, real)
            return
        wise = q.table.termwise(i, j, k)
        if self.plant == 'wise':
            wise = not wise
        want = R._termwise(a, b, real)
        if wise is not want:
            self.differs('termwise', a, b, wise, want)
        d = q.table.eq_diff(i, j)
        want = None if R._is_number(real) or not want else real
        if self.plant != 'wise' and not (d is None and want is None or d is not None and want is not None and same_form(TL.scaffold(q, d, 'direct'), want)):
            self.differs('eq_diff', a, b, d, want)
        self.key(q, k, real, 'sub-key')

    def product(self, q, a, b):
        p = a*b
        i = TL.term_id(q, p, 'direct')
        if i is None:
            self.c['product:no-id'] += 1
            return
        self.key(q, i, p, 'product-key')
        self.c[f'product:{type(p).__name__}'] += 1

    def key(self, q, i, real, what):
        got = q.table.sort_key(i)
        if self.plant == 'key':
            got = ('reversed', got)
        try:
            want = default_sort_key(real)
        except Exception as e:
            self.differs(what + '-python-raised', real, e)
            return
        if not TL._same_key(got, want, q):
            self.differs(what, real, got, want)
        self.c['same:' + what] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('n', type=int)
    ap.add_argument('seed', type=int)
    ap.add_argument('--plant', choices=['swap', 'wise', 'key', 'sub'])
    ap.add_argument('--out')
    a = ap.parse_args()
    r = random.Random(a.seed)
    run = Run(a.plant)
    for _ in range(a.n):
        p, q = term(r), term(r)
        try:
            run.pair(p, q)
        except Exception as e:     # this script or Rust outside `TermRefuse`: a finding, with its case
            run.differs('raised', p, q, type(e).__name__, e)
    out = sys.stdout if a.out is None else open(a.out, 'w')
    for k in sorted(run.c):
        print(f'{run.c[k]}\t{k}', file=out)
    for b in run.bad:
        print(b, file=out)
    sys.exit(1 if any(k.startswith('differs:') for k in run.c) else 0)


main()
