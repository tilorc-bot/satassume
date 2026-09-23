"""Relational ask microbenchmarks: sympy.ask versus satassume, cold (fresh
engine) and warm (same engine).  PYTHONPATH=.:/path/to/sympy python tools/relbench.py
"""
import gc, time, statistics, warnings
warnings.simplefilter("ignore")
from sympy import symbols, Q, Function, Abs, exp, sin, ask as sask
from satassume import Engine
from satassume.engine import DictCache
from satassume.sympy_api import ask as sat_ask

x, y, z = symbols('x y z'); xr, yr, zr = symbols('x y z', real=True); f = Function('f')
R = Q.real(x) & Q.real(y) & Q.real(z)
cases = [
 ("transitivity, real symbols",            xr > zr, (xr > yr) & (yr > zr)),
 ("transitivity, Q.real assumptions",      x > z, (x > y) & (y > z) & R),
 ("transitivity, implied real",            x > z, (x > y) & (y > z) & Q.positive(x) & Q.integer(y) & Q.rational(z)),
 ("x+1 > x, real",                         xr + 1 > xr, True),
 ("x+1 > x, plain (None)",                 x + 1 > x, True),
 ("2x+y > 0 | x>1, y>-2, real",            2*xr + yr > 0, (xr > 1) & (yr > -2)),
 ("x <= y | x > y, plain",                 x <= y, x > y),
 ("EUF: eq(x,z) | eq(x,y)&eq(y,z)",        Q.eq(x, z), Q.eq(x, y) & Q.eq(y, z)),
 ("EUF: eq(f(x),f(y)) | eq(x,y)",          Q.eq(f(x), f(y)), Q.eq(x, y)),
 ("sharing: eq(f(x),f(y)) | x<=y<=x real", Q.eq(f(xr), f(yr)), (xr <= yr) & (yr <= xr)),
 ("positive(x) | x>0 & real(x)",           Q.positive(x), (x > 0) & Q.real(x)),
 ("structural Abs/sin/exp chain, real",    Abs(xr) > exp(yr), (Abs(xr) > sin(yr)) & (sin(yr) > exp(yr))),
]
def timeit(fn, reps):
    gc.collect(); gc.disable()
    ts = []
    for _ in range(reps):
        t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    gc.enable()
    return statistics.median(ts) * 1e6
print(f"{'sympy.ask':>10} {'cold':>9} {'warm':>9}   answer  query")
tot = [0, 0, 0]
for label, p, a in cases:
    rs = sask(p, a)
    r = sat_ask(p, a, engine=Engine(cache=DictCache()))
    ts = timeit(lambda: sask(p, a), 20)
    cold = timeit(lambda: sat_ask(p, a, engine=Engine(cache=DictCache())), 30)
    eng = Engine(cache=DictCache()); sat_ask(p, a, engine=eng)
    warm = timeit(lambda: sat_ask(p, a, engine=eng), 200)
    tot[0] += ts; tot[1] += cold; tot[2] += warm
    flag = "" if rs == r else f"  (sympy {rs})"
    print(f"{ts:8.0f}us {cold:7.0f}us {warm:7.0f}us   {str(r):5}   {label}{flag}")
print(f"{tot[0]:8.0f}us {tot[1]:7.0f}us {tot[2]:7.0f}us   sum")
