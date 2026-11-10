"""split_order.py: the comparison and guard results/split-order-cause.md proposes for `_SPLIT`, `_WANT`, `_CLOSED`, `_SYMPY_ATOMS`
(issue 323). Draft, test-only; reads split_probe.py's rows. Nothing here is wired into bar.sh or livecmp.py.

`python split_order.py cmp PY.probe RUST.probe`: per engine point MATCH or DIFFER.
- `_WANT`, `_CLOSED`, `_SYMPY_ATOMS`: equal as multisets of (key, value). Order is left out: no reader iterates them (`guard`).
- `_SPLIT`: the distinct (clauses, want, len(now), len(later)) are the same set, Python has no row Rust lacks, and every
  Rust-only row is a second copy whose clause list belongs to a pattern outside `_common._CACHE` (Rust's atom templates,
  knowledge_live.rust_compiled, build a pattern per call and never use the cache).
`guard(root)`: every use in `root`'s Python source of the four names that is not a keyed read or write, `len`, `clear` or
`.size`. Empty on satassume/: the state rule's condition (2) for leaving the order out.
Plants (SPLIT_PLANT, armed by split_probe.arm): 450 `split-row-drop`, 451 `atoms-uncached`, 453 `closed-row-drop`; 452
`order-reader` is `PLANTED_READER`, a source text with an iterating reader for the guard.
"""
import ast
import json
import os
import sys
from collections import Counter

NAMES = ('_WANT', '_SPLIT', '_CLOSED', '_SYMPY_ATOMS')
PLANTED_READER = "def f():\n    for k in _CLOSED:\n        yield k\n"      # plant 452


def compare(a, b):
    """Differences between Python's rows `a` and Rust's `b` (one engine point each), and the number of Rust-only `_SPLIT` rows
    (a difference too)."""
    out = []
    for n in ('_WANT', '_CLOSED', '_SYMPY_ATOMS'):
        if Counter(map(json.dumps, a[n])) != Counter(map(json.dumps, b[n])):
            out.append('%s rows differ (%d against %d)' % (n, len(a[n]), len(b[n])))
    key = lambda r: json.dumps([r[0], r[1], r[3], r[4]])
    ca, cb = Counter(map(key, a['_SPLIT'])), Counter(map(key, b['_SPLIT']))
    if set(ca) != set(cb):
        out.append('_SPLIT distinct rows differ (%d against %d)' % (len(ca), len(cb)))
    if ca - cb:
        out.append('_SPLIT: %d Python rows Rust lacks' % sum((ca - cb).values()))
    # Exact since the `_CACHE` fix (c170496, 311fb80): Rust's atom templates fill `_CACHE` under Python's keys, so a
    # Rust-only copy has no cause left and is a difference, and `_CACHE` holds the same keys.
    extra = sum((cb - ca).values())
    if extra:
        out.append('_SPLIT: %d Rust-only rows' % extra)
    if Counter((r[0], r[2]) for r in a['_CACHE']) != Counter((r[0], r[2]) for r in b['_CACHE']):     # key, clause count
        out.append('_CACHE keys differ (%d against %d)' % (len(a['_CACHE']), len(b['_CACHE'])))
    return out, extra


def guard(root=None, text=None):
    """`file:line: code` of each use of the four names that is not `X.get(k)`, `X[k]`, `len(X)`, `X.clear()`, `X.size`, the
    name's own definition or its `global` line."""
    if text is not None:
        files = [('<planted>', text)]
    else:
        files = []
        for d, _, fs in os.walk(root):
            files += [(os.path.join(d, f), open(os.path.join(d, f)).read()) for f in fs if f.endswith('.py')]
    bad = []
    for path, src in files:
        tree = ast.parse(src)
        up = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
        for x in ast.walk(tree):
            if not (isinstance(x, ast.Name) and x.id in NAMES or isinstance(x, ast.Attribute) and x.attr in NAMES):
                continue
            p = up.get(x)
            ok = (isinstance(p, ast.Subscript) and p.value is x
                  or isinstance(p, ast.Attribute) and p.attr in ('get', 'clear') and isinstance(up.get(p), ast.Call)
                  or isinstance(p, ast.Attribute) and p.attr == 'size'
                  or isinstance(p, ast.Call) and getattr(p.func, 'id', '') == 'len'
                  or isinstance(p, (ast.Assign, ast.AnnAssign)) and x in getattr(p, 'targets', [getattr(p, 'target', None)]))
            if not ok:
                bad.append('%s:%d: %s' % (path, x.lineno, src.splitlines()[x.lineno - 1].strip()))
    return bad


if __name__ == '__main__':
    if sys.argv[1] == 'guard':
        print('\n'.join(guard(sys.argv[2])) or 'guard: no other reader')
    else:
        A, B = ([json.loads(l) for l in open(p)] for p in sys.argv[2:4])
        for x, y in zip(A, B):
            d, extra = compare(x['rows'], y['rows'])
            print('point', x['at'], 'DIFFER' if d else 'MATCH', '_SPLIT %d against %d, Rust-only copies %d' % (
                len(x['rows']['_SPLIT']), len(y['rows']['_SPLIT']), extra), '; '.join(d))
