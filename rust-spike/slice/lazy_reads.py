"""The planner's ruling on lazy reads, item 3: queries where the lazy path reads a term Python's run didn't, with the
callback count by kind.

    lazy_reads.py WL OUT.jsonl [--limit N]

Two passes per query in one process, so a term is the same object in both, each from `reset_module_state(sympy_cache=True)`
on a fresh engine, since a shared cache hides inner reads.
  Pass 1, pure Python: records (kind, term) at every `sort_key` defined on a Basic subclass (outside `cacheit`), at
  `Expr.__complex__`, at `exprtools.decompose_power`, and at `is_finite`, both the property and `assumptions._ask`.
  Pass 2, the lazy path: the shadow in DRIVE mode, so Rust's algebra follows the run and each key the run uses is asked of
  Rust, with no checks and no printing. Records (kind, term) at `_Walk.read`, with pass 1's recording off.

A row: q, answers (pass 1's), same (answers equal), py (reads by kind), lazy (reads by kind), extra (lazy reads pass 1
didn't make), py_complex, lazy_complex (`complex()` calls over the whole pass), missing, raised, refused.

Limits, which go with any number from here:
- `is_commutative` isn't compared: on stock classes it's an instance slot or a class constant, so no wrapper sees Python
  read it. Its reads are counted and left out of `extra`.
- `is_finite` that's a class constant, or already in `_assumptions` from an earlier query or pass, isn't seen in pass 1. So
  a finite row in `extra` can be such a read: it stays in `extra` and the summary gives the class.
- Everything is on input terms. Pass 1 also records derived ones, which pass 2 can't read.
"""
import argparse
from collections import Counter
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

ap = argparse.ArgumentParser()
ap.add_argument('wl')
ap.add_argument('out')
ap.add_argument('--limit', type=int)
args = ap.parse_args()

from sympy.core.basic import Basic
from sympy.core.expr import Expr
import sympy.core.exprtools as X
from harness.state import reset_module_state
from satassume import engine as E
from satassume import sympy_api
from evalbench.common import workload

import convert as C
import term_shadow as TS

if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
if args.limit:
    pairs = pairs[:args.limit]

ON = [False]            # pass 1's recording
PY = set()
PY_N = Counter()
COMPLEX = [0]
LAZY = []


def note(kind, t):
    if ON[0]:
        PY.add((kind, t))
        PY_N[kind] += 1


def classes():
    seen, stack = set(), [Basic]
    while stack:
        k = stack.pop()
        if k not in seen:
            seen.add(k)
            stack.extend(k.__subclasses__())
    return seen


def wrap_key(f):
    def sort_key(self, *a, **k):
        note('key', self)
        return f(self, *a, **k)
    return sort_key


def wrap_finite(p):
    def is_finite(self):
        note('finite', self)
        return p.fget(self)
    return property(is_finite)


for k in classes():
    d = k.__dict__
    if 'sort_key' in d and callable(d['sort_key']):
        k.sort_key = wrap_key(d['sort_key'])
    if isinstance(d.get('is_finite'), property):
        k.is_finite = wrap_finite(d['is_finite'])

real_complex = Expr.__complex__


def counted_complex(self):
    COMPLEX[0] += 1
    note('complex', self)
    return real_complex(self)


Expr.__complex__ = counted_complex

real_decompose = X.decompose_power


def decompose_power(e):
    note('power', e)
    return real_decompose(e)


X.decompose_power = decompose_power     # expr.py:1228 imports it inside as_terms, so at call time

A = sys.modules['sympy.core.assumptions']
real_fact = A._ask


def _ask_fact(fact, obj):
    if fact == 'finite':
        note('finite', obj)
    return real_fact(fact, obj)


A._ask = _ask_fact

real_read = C._Walk.read


def read(self, kind, i):
    LAZY.append((C.READS[kind], self.objects[i]))
    return real_read(self, kind, i)


C._Walk.read = read

plain_ask = sympy_api._ask
TS.install()
TS.install_algebra()
TS.DRIVE[0] = True
shadow_ask = sympy_api._ask


def run(p, a):
    reset_module_state(sympy_cache=True)
    sympy_api.set_default_engine(E.Engine())
    try:
        return repr(sympy_api.ask(p, a))
    except Exception as e:
        return 'raised ' + type(e).__name__


def show(t):
    return type(t).__name__ + ' ' + str(t)[:160]


totals = Counter()
with open(args.out, 'w') as out:
    for q, (p, a) in enumerate(pairs):
        PY.clear()
        PY_N.clear()
        LAZY.clear()
        TS.CUR[0] = None
        sympy_api._ask = plain_ask
        ON[0] = True
        COMPLEX[0] = 0
        ans1 = run(p, a)
        ON[0] = False
        py_complex = COMPLEX[0]
        sympy_api._ask = shadow_ask
        COMPLEX[0] = 0
        before = dict(TS.COUNTS)
        refused_before = sum(TS.REFUSED.values())
        ans2 = run(p, a)
        lazy_complex = COMPLEX[0]
        lazy = Counter(k for k, _ in LAZY)
        extra = [(k, t) for k, t in LAZY if k != 'commutative' and (k, t) not in PY]
        row = dict(q=q, ans=ans1[:40], same=ans1 == ans2, py=dict(PY_N), lazy=dict(lazy), n_extra=len(extra),
                   py_complex=py_complex, lazy_complex=lazy_complex,
                   missing=TS.COUNTS['convert:read_term_missing'] - before.get('convert:read_term_missing', 0),
                   raised=TS.COUNTS['convert:read_raised'] - before.get('convert:read_raised', 0),
                   refused=sum(TS.REFUSED.values()) - refused_before)
        if extra:
            # Printing can evaluate, so it's here, after both passes.
            row['extra'] = sorted({k + ' ' + show(t) for k, t in extra})[:20]
            row['query'] = str(p)[:300]
            row['assumptions'] = str(a)[:300]
        out.write(json.dumps(row) + '\n')
        out.flush()
        totals['queries'] += 1
        totals['same'] += row['same']
        totals['with_extra'] += bool(extra)
        for k, v in lazy.items():
            totals['lazy:' + k] += v
        for k, v in PY_N.items():
            totals['py:' + k] += v
print(args.wl, dict(sorted(totals.items())))
