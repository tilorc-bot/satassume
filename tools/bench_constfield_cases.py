"""Worst cases of satassume/constfield.py (reviewer D's): a degree-70
univariate gcd with 166-bit coefficients, a degree-4096 power in
from_sympy, and Gaussian elimination on random n x n matrices whose
entries are, with probability 1/2, numbers with constants (an Undecided,
including TooLarge, aborts a matrix as phase 2 aborts a query).  Prints
times and outcomes; each pool and size has a time limit (argument,
default 120 s).

    PYTHONPATH=. python tools/bench_constfield_cases.py [limit]
"""

import random, signal, sys, time
from fractions import Fraction as F
import sympy
from satassume import constfield as cf
from satassume.constfield import E, PI, TooLarge, Undecided

SQ2 = cf.radical(2, 2); SQ3 = cf.radical(3, 2); L2 = cf.from_sympy(sympy.log(2))


class TO(BaseException):
    pass


def _alarm(*a):
    raise TO()


signal.signal(signal.SIGALRM, _alarm)


def elim(n, pool, rng):
    M = [[(rng.choice(pool) if rng.random() < 0.5 else F(rng.randint(-5, 5))) for _ in range(n)]
         for _ in range(n)]
    t = time.perf_counter()
    try:
        for c in range(n):
            p = None
            for r in range(c, n):
                if cf.sign(M[r][c]) != 0:
                    p = r
                    break
            if p is None:
                continue
            M[c], M[p] = M[p], M[c]
            inv = 1 / M[c][c]
            for r in range(c + 1, n):
                f = M[r][c] * inv
                if cf.formally_zero(f):
                    continue
                for k in range(c, n):
                    M[r][k] = M[r][k] - f * M[c][k]
        out = "done"
    except TooLarge:
        out = "TooLarge"
    except Undecided:
        out = "Undecided"
    return time.perf_counter() - t, out


pools = {
    "pi only": [PI, 1 / PI, PI + 1, 3 * PI / 2],
    "pi,E": [PI, E, PI + E, 1 / PI, E / 2],
    "pi,E,sqrt2": [PI, E, SQ2, PI * SQ2, 1 / (PI + E)],
    "five constants": [PI, E, SQ2, SQ3, L2, PI + L2],
}
rng = random.Random(5)
v = PI.numerator[0]


def rpoly(deg, bits):
    return cf._mk(v, [F(rng.randint(-(1 << bits), 1 << bits), rng.randint(1, 1 << 20))
                      for _ in range(deg)] + [F(1)])


h = rpoly(31, 40)
a, b = cf._mul(rpoly(39, 60), h), cf._mul(rpoly(39, 60), h)
times = []
for _ in range(5):
    t = time.perf_counter()
    cf._inner_gcd(a, b)
    times.append(time.perf_counter() - t)
best = min(times)
print(f"gcd degree 70 (166-bit coefficients): {best * 1e3:.2f} ms")
t = time.perf_counter()
r = cf.from_sympy(((sympy.pi + 1) ** 64 + 1) ** 64)
print(f"from_sympy(((pi+1)**64+1)**64): {r} in {(time.perf_counter() - t) * 1e3:.2f} ms")

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 120
rng = random.Random(1)
for name, pool in pools.items():
    for n in (4, 6, 8):
        signal.alarm(LIMIT)
        try:
            rs = [elim(n, pool, rng) for _ in range(3)]
            outs = ",".join(o for _, o in rs)
            print(f"{name:16s} n={n}: worst {max(t for t, _ in rs):7.3f}s  [{outs}]", flush=True)
        except TO:
            print(f"{name:16s} n={n}: TIMEOUT {LIMIT}s", flush=True)
        finally:
            signal.alarm(0)
