"""knowledge_units_cmp.py [--random N] [--seed S]: Rust's `Rules::units` against `_common.units`, field by field, over generated fact lists.

Workloads may not reach the conflict path or the `rest` loop (`antihermitian`), so this feeds both directly. Every list of
up to 2 facts over the vocabulary in order, duplicates and conflicts included, then N random lists of 3 to 12. Counts how many
inputs reached each path, on Python's side, so a zero there says the path was not run. Differences print with the smallest list.
"""
import argparse
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--random', type=int, default=200000)
ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--so-check', action='store_true')
args = ap.parse_args()

import sa_solver
import sympy
from satassume.knowledge.templates import _common as C
import knowledge_live as K

HERE = os.path.dirname(os.path.abspath(__file__))
kn = sa_solver.Knowledge(sa_solver.OfflineData(os.path.join(HERE, 'offline_data.json'),
                                               os.path.abspath(os.path.join(HERE, '..', '..')), sympy.__version__))
print('so', sa_solver.__file__)
VOCAB = sorted(p for p in C.VOCAB if p != 'commutative')
print('vocab', len(VOCAB))
LITS = [(p, v) for p in VOCAB for v in (True, False)]
x = sympy.Symbol('x')


def paths(facts):
    """Which of Python's paths this list takes, read from its own helpers rather than from Rust."""
    lits, rest = [], False
    for pred, value in facts:
        for c in C.expand_clause([(0, pred, value)]):
            if len(c) == 1:
                lits.append(C._signed(c[0][1], c[0][2]))
            else:
                rest = True
    return C.unit_propagate(C.RULE_INSTANTIATED, lits) is None, rest


diffs = {}
seen = dict(total=0, conflict=0, rest=0, conflict_and_rest=0, complete=0)


def one(facts):
    C._CACHE.clear()
    py = C.units(('cmp', tuple(facts)), lambda: list(facts), x).pattern
    ours = K._wrap(kn.units(list(facts)))
    conflict, rest = paths(facts)
    seen['total'] += 1
    seen['conflict'] += conflict
    seen['rest'] += rest
    seen['conflict_and_rest'] += conflict and rest
    seen['complete'] += bool(py.complete)
    for f in K.FIELDS:
        a, b = getattr(ours, f), getattr(py, f)
        if a != b or type(a) is not type(b):
            k = f
            if k not in diffs or len(facts) < len(diffs[k][0]):
                diffs[k] = (list(facts), repr(a)[:300], repr(b)[:300])
            diffs.setdefault('n:' + f, [0])
            diffs['n:' + f][0] += 1


one([])
for n in (1, 2):
    for facts in itertools.product(LITS, repeat=n):
        one(facts)
systematic = seen['total']
r = random.Random(args.seed)
for _ in range(args.random):
    n = r.randint(3, 12)
    # half biased to the clause-bearing predicate and to repeats, so the `rest` loop and duplicates are common
    pool = LITS if r.random() < .5 else [l for l in LITS if l[0] in ('antihermitian', 'hermitian', 'imaginary', 'real', 'zero')]
    one([r.choice(pool) for _ in range(n)])
print('systematic', systematic, 'random', args.random, 'seed', args.seed)
print(seen)
print('DIFFS' if diffs else 'no differences')
for k, v in diffs.items():
    print(k, v)
