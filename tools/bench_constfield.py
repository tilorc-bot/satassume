"""Micro-benchmark of satassume/theories/lra/constfield.py: the rational fast path
against plain Fraction, and typical operations on rows with pi.

    PYTHONPATH=. python tools/bench_constfield.py

or pinned (see /home/tilo/bin/README.md), from a snapshot directory
holding ``satassume/`` and this script:

    bench-container run benchmark-sympy:local SNAPSHOT -- python bench_constfield.py

Prints the best of 7 repeats per operation (ns); with a writable
``/results`` also writes ``constfield-bench.json`` there.
"""
import json
import platform
import random
import sys
import timeit
from fractions import Fraction as F

from satassume.theories.lra import constfield as cf
from satassume.theories.lra.constfield import PI, E, num


def bench(label, stmt, g, number=None):
    t = timeit.Timer(stmt, globals=g)
    if number is None:
        n, _ = t.autorange()
        number = max(n, 1000)
    best = min(t.repeat(repeat=7, number=number)) / number
    return label, best * 1e9

g = dict(F=F, cf=cf, PI=PI, E=E, num=num)
g.update(a=F(3, 7), b=F(-5, 11), c=F(2, 9), q1=(F(3, 7), F(0)), q2=(F(3, 7), F(1)))
g.update(p2=PI / 2, pinv=-1 / PI, p3=3 * PI / 2 + 1, pp1=PI + 1, pe=(PI + E) / 2)
g.update(t1=(PI / 2, F(0)), t2=(PI / 2, F(-1)), t3=(PI / 2 + F(1, 10**6), F(0)),
         three=F(3), four=F(4))
rows = []
# the rational fast path
rows.append(bench("Fraction a*b + c (baseline)", "a*b + c", g))
rows.append(bench("Fraction(a) (today's coercion)", "F(a)", g))
rows.append(bench("num(a) (coercion with constants)", "num(a)", g))
rows.append(bench("Fraction a < b", "a < b", g))
rows.append(bench("Fraction pair (q,d) < (q,d')", "q1 < q2", g))
rows.append(bench("Fraction a != b", "a != b", g))
# rows with pi
rows.append(bench("pi/2 + Fraction", "p2 + a", g))
rows.append(bench("Fraction * (pi/2)", "a * p2", g))
rows.append(bench("pivot update: (3pi/2+1) + (-1/pi)*(pi/2)", "p3 + pinv * p2", g))
rows.append(bench("(pi/2) + (-1/pi)  (unlike denominators)", "p2 + pinv", g))
rows.append(bench("1 / (pi+1)", "1 / pp1", g))
rows.append(bench("(pi+1) / (pi/2)", "pp1 / p2", g))
rows.append(bench("pi/2 < 4 (cached enclosure)", "p2 < four", g))
rows.append(bench("pi/2 == pi/2 + 0 (formal)", "p2 == t1[0]", g))
rows.append(bench("pi/2 != 3 (transcendental)", "p2 != three", g))
rows.append(bench("pair (pi/2,0) < (pi/2,-1)", "t1 < t2", g))
rows.append(bench("pair (pi/2,0) < (pi/2+1e-6,0)", "t1 < t3", g))
rows.append(bench("fresh sign of p3 + a*pi (no cache)", "(p3 + a * PI).sign()", g))
rows.append(bench("fresh compare (pi+E)/2 + a < 3", "(pe + a) < three", g))
rows.append(bench("floor(3pi/2 + 1)", "p3.__floor__()", g))

# Gaussian elimination (the pivot arithmetic of the simplex) on a 6x6
# rational matrix, and on the same matrix with one pi entry
def elim(m):
    m = [row[:] for row in m]
    n = len(m)
    for i in range(n):
        piv = m[i][i]
        inv = 1 / piv
        for r in range(i + 1, n):
            f = m[r][i] * inv
            if f:
                for k in range(i, n):
                    m[r][k] = m[r][k] - f * m[i][k]
    return m

rng = random.Random(3)
mat = [[F(rng.randint(-9, 9), rng.randint(1, 4)) for _ in range(6)] for _ in range(6)]
for i in range(6):
    mat[i][i] += 40
matpi = [row[:] for row in mat]
matpi[0][3] = PI / 2
g.update(elim=elim, mat=mat, matpi=matpi)
rows.append(bench("6x6 elimination, rationals", "elim(mat)", g, number=50))
rows.append(bench("6x6 elimination, one pi entry", "elim(matpi)", g, number=5))

out = {"python": sys.version, "machine": platform.machine(),
       "rows": [{"op": l, "ns": round(ns, 1)} for l, ns in rows]}
w = max(len(l) for l, _ in rows)
for l, ns in rows:
    print(f"{l:{w}s} {ns:12.1f} ns")
try:
    with open("/results/constfield-bench.json", "w") as fh:
        json.dump(out, fh, indent=1)
except OSError:
    pass
