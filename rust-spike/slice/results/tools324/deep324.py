"""deep324.py: deeply nested inputs under Python's walker and Rust's (all items): the outcome of `convert` per depth and
shape (Converted, or Kept and its reason), and whether the two differ by convert_diff's comparison (tables, ids, objects,
classes; the lazy reads are not asked). Python's `_may_be_nan` takes two frames a level; the native one counts against
Py_EnterRecursiveCall. Prints one line per shape: the depths where the outcomes differ."""
import os, sys
from sympy import Function, Symbol, Q, sin, oo
import convert
from convert_diff import diff
from satassume import engine as E
sys.setrecursionlimit(int(os.environ.get('LIMIT', sys.getrecursionlimit())))
x = Symbol('x'); f = Function('f')
rust = convert.rust_walk(convert.RUST_ITEMS)
SHAPES = {'f(e+1)': lambda e: f(e + 1), 'f(e)': lambda e: f(e), 'sin(e)': lambda e: sin(e), 'f(e,oo)': lambda e: f(e, oo)}
def out(walk, e):
    convert.WALK[0] = walk
    try:
        c = convert.convert(Q.positive(e), Q.positive(x), E.Engine())
        return type(c).__name__ + (':' + c.reason if isinstance(c, convert.Kept) else ''), c
    except BaseException as ex:
        return type(ex).__name__, ex
    finally:
        convert.WALK[0] = None
for name, step in SHAPES.items():
    e, k, res, differ = x, 0, {}, []
    try:
        for k in range(1, int(os.environ.get('DEPTH', 700)) + 1):
            e = step(e)
            if not (k in (50, 100, 200, 400, 600, 700) or (236 <= k <= 300 and k % 4 == 0) or (440 <= k <= 540 and k % 4 == 0)):
                continue
            a, ca = out(None, e); b, cb = out(rust, e)
            same = a == b and (a != 'Converted' or diff(ca, cb, 0) == [])
            res.setdefault((a, b, same), []).append(k)
            if not same:
                differ.append(k)
    except RecursionError:
        print(name, 'building stopped at', k)
    print(name, {key: (v[0], v[-1], len(v)) for key, v in res.items()}, 'DIFFER at', differ, flush=True)
