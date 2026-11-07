"""History independence of conversion: what conversion sends Rust for a query, and Rust's reads of the table, must depend
on that query alone. Writes one digest per query, by its index in the workload.

    term_history.py WL OUT.json [--order recorded|reverse|shuffle] [--dirty] [--limit N]

--dirty keeps the process-wide memos and SymPy's cache across queries, and only the answer memo starts empty, so the next
query's conversion sees whatever the earlier ones left. Otherwise each query starts fresh. Compare two OUT files with --cmp A B: any difference is a
history or hash-order dependence and is printed with its query.
"""
import argparse
import hashlib
import json
import os
import random
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)

ap = argparse.ArgumentParser()
ap.add_argument('wl', nargs='?')
ap.add_argument('out', nargs='?')
ap.add_argument('--order', default='recorded')
ap.add_argument('--dirty', action='store_true')
ap.add_argument('--limit', type=int)
ap.add_argument('--cmp', nargs='+')
args = ap.parse_args()

if args.cmp:
    a = json.load(open(args.cmp[0]))
    for path in args.cmp[1:]:
        b = json.load(open(path))
        diff = [k for k in a if k in b and a[k] != b[k]]
        print(os.path.basename(args.cmp[0]), os.path.basename(path), 'queries', len(a), len(b),
              'missing', len(set(a) ^ set(b)), 'differ', len(diff), diff[:10])
    sys.exit(0)

import sa_solver
from harness.state import reset_module_state
from satassume import sympy_api
from satassume import engine as E
from evalbench.common import workload
import convert as C

if args.wl == 'fuzz':
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(args.wl)
if args.limit:
    pairs = pairs[:args.limit]

order = list(range(len(pairs)))
if args.order == 'reverse':
    order.reverse()
elif args.order == 'shuffle':
    random.Random(1).shuffle(order)

CUR = [None]
OUT = {}
DEPTH = [0]
real_ask = sympy_api._ask


def digest(c):
    if isinstance(c, C.Kept):
        return 'kept ' + c.reason
    h = hashlib.sha256(repr(sorted((k, v) for k, v in c.tables.items())).encode())
    table = sa_solver.TermTable(c.tables)
    n = table.n_input
    for i in range(n):
        h.update(repr(table.row(i)[:5]).encode())
    for i in range(min(n, 20)):
        for j in range(min(n, 20)):
            try:
                h.update(repr(table.compare(i, j)).encode())
            except sa_solver.TermRefuse as e:
                h.update(str(e).encode())
    return h.hexdigest()[:16]


def _ask(proposition, assumptions, eng):
    DEPTH[0] += 1
    try:
        if DEPTH[0] == 1:
            try:
                OUT[str(CUR[0])] = digest(C.convert(proposition, assumptions, eng))
            except Exception as e:
                OUT[str(CUR[0])] = 'raised ' + type(e).__name__
        return real_ask(proposition, assumptions, eng)
    finally:
        DEPTH[0] -= 1


sympy_api._ask = _ask
sympy_api.set_default_engine(E.Engine())
for q in order:
    p, a = pairs[q]
    CUR[0] = q
    if not args.dirty:
        reset_module_state(sympy_cache=True)
    sympy_api.set_default_engine(E.Engine())    # a shared engine's answer memo would skip conversion, as it should
    try:
        sympy_api.ask(p, a)
    except Exception:
        pass
json.dump(OUT, open(args.out, 'w'), indent=0, sort_keys=True)
print(args.wl, args.order, 'dirty' if args.dirty else 'fresh', len(OUT))
