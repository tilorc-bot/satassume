"""open326.py (sa-port-326): what convert_diff.diff names on deep324.py's f(e+1)/f(e)/sin(e) inputs at the given depths,
for three pairs: Python's walker against Rust's (all items), Python against Python (control), Rust against Rust; with
read_terms=0 (deep324's call), and with full reads at the depths in FULL. Prints the loaded .so and its hash."""
import os, sys, hashlib
from sympy import Function, Symbol, Q, sin
import convert, sa_solver
from convert_diff import diff
from satassume import engine as E
x = Symbol('x'); f = Function('f')
print('so', sa_solver.__file__, hashlib.sha256(open(sa_solver.__file__, 'rb').read()).hexdigest()[:8], 'convert', convert.__file__, flush=True)
rust = convert.rust_walk(convert.RUST_ITEMS)
SHAPES = {'f(e+1)': lambda e: f(e + 1), 'f(e)': lambda e: f(e), 'sin(e)': lambda e: sin(e)}
SHARED = os.environ.get('SHARED') == '1'   # 1: one proposition object for both calls (test_convert_walk's way)
ASM = Q.positive(x)
def out(walk, e):
    convert.WALK[0] = walk
    try:
        return convert.convert(e if SHARED else Q.positive(e), ASM if SHARED else Q.positive(x), E.Engine())
    except RecursionError as ex:
        return ex
    finally:
        convert.WALK[0] = None
DEPTHS = [int(d) for d in os.environ.get('DEPTHS', '1,2,10,40,50').split(',')]
FULL = [int(d) for d in os.environ.get('FULL', '').split(',') if d]
for name, step in SHAPES.items():
    e = x
    for k in range(1, max(DEPTHS) + 1):
        e = step(e)
        if k not in DEPTHS:
            continue
        for tag, wa, wb in (('py|rust', None, rust), ('py|py', None, None), ('rust|rust', rust, rust)):
            p = Q.positive(e) if SHARED else e
            ca, cb = out(wa, p), out(wb, p)
            print(name, k, tag, type(ca).__name__ + (':' + ca.reason if isinstance(ca, convert.Kept) else ''), 'reads=0:', diff(ca, cb, 0), flush=True)
            if k in FULL:
                seen = {}
                print(name, k, tag, 'full reads:', diff(ca, cb, None, seen), seen, flush=True)
