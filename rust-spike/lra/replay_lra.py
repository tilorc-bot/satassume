"""replay_lra.py WORKLOAD TRACEDIR MODE: replay the recorded calls through the real LRATheory.

timed: one pass, per-class wall time. empty: the same dispatch into a class of empty methods, so what's left after
subtracting it is the time inside the methods. check: hash every result and the state after it, compare with the
recording, and print totals (not timed).

Everything is decoded before the clock starts. As in tools-rust/rc.py base: gc.collect(); gc.freeze(), collector on.
"""
import gc
import json
import os
import sys
import time
import zlib
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from common_lra import result_str, state_str  # noqa: E402

from satassume.theories.lra.lra import Integral, LRATheory, Negated  # noqa: E402

wl, tdir, mode = sys.argv[1], sys.argv[2], sys.argv[3]
pc = time.perf_counter


def frac(s):
    n, d = s.split("/")
    return Fraction(int(n), int(d))


def terms(xs, i):
    n = int(xs[i])
    i += 1
    return tuple((int(xs[i + 2 * j]), frac(xs[i + 2 * j + 1])) for j in range(n))


def payload(xs):
    if xs[3] == "I":
        return Integral(terms(xs, 5), frac(xs[4]))
    neg, strict, eq = int(xs[4]), bool(int(xs[5])), bool(int(xs[6]))
    p = (terms(xs, 8), frac(xs[7]), strict, eq)
    for _ in range(neg):
        p = Negated(p)
    return p


NEW, DROP, REG, ASSERT, CHECK, PROP, PUSH, POP, QUERY = range(9)


def decode():
    ops = []
    with open(os.path.join(tdir, f"{wl}.lra")) as f:
        for line in f:
            xs = line.split()
            o = xs[0]
            if o == "A":
                ops.append((ASSERT, int(xs[1]), int(xs[2]), None))
            elif o == "G":
                ops.append((PROP, int(xs[1]), None, None))
            elif o == "U":
                ops.append((PUSH, int(xs[1]), None, None))
            elif o == "O":
                ops.append((POP, int(xs[1]), None, None))
            elif o == "C":
                ops.append((CHECK, int(xs[1]), None, None))
            elif o == "R":
                ops.append((REG, int(xs[1]), int(xs[2]), payload(xs)))
            elif o == "N":
                ops.append((NEW, int(xs[1]), None, None))
            elif o == "D":
                ops.append((DROP, int(xs[1]), None, None))
            else:
                ops.append((QUERY, int(xs[1]), None, None))
    return ops


class Empty:
    def register_atom(self, a, b):
        pass

    def assert_lit(self, a):
        pass

    def check(self):
        pass

    def propagate(self):
        pass

    def push_level(self):
        pass

    def pop_level(self):
        pass


ops = decode()
meta = json.load(open(os.path.join(tdir, f"{wl}.lra.meta.json")))
cls = meta["cls"]
Th = Empty if mode == "empty" else LRATheory

if mode == "check":
    crcs = [int(x) for x in open(os.path.join(tdir, f"{wl}.lra.res"))]
    ths = {}
    all_ths = []
    bad = 0
    first = None
    n = 0
    for k, (op, t, a, b) in enumerate(ops):     # crcs has one line per trace line, -1 for Q, N and D
        if op == QUERY:
            continue
        if op == NEW:
            ths[t] = LRATheory()
            all_ths.append(ths[t])
            continue
        if op == DROP:
            del ths[t]
            continue
        th = ths[t]
        r = (th.register_atom(a, b) if op == REG else th.assert_lit(a) if op == ASSERT else th.check() if op == CHECK
             else th.propagate() if op == PROP else th.push_level() if op == PUSH else th.pop_level())
        n += 1
        if zlib.crc32((result_str(r) + state_str(th)).encode()) != crcs[k]:
            bad += 1
            if first is None:
                first = k
    tot = {}
    for th in all_ths:
        for name, x in th.stats.items():
            tot[name] = tot.get(name, 0) + x
    print(json.dumps(dict(run="py", mode="check", wl=wl, ops=n, mismatches=bad, first=first, totals=tot)), flush=True)
    sys.exit(0)

gc.collect()
gc.freeze()
ths = {}
qt = {"none": 0.0, "definite": 0.0, "other": 0.0}
start = pc()
last = start
cur = None
for op, t, a, b in ops:
    if op == ASSERT:
        ths[t].assert_lit(a)
    elif op == PROP:
        ths[t].propagate()
    elif op == PUSH:
        ths[t].push_level()
    elif op == POP:
        ths[t].pop_level()
    elif op == CHECK:
        ths[t].check()
    elif op == REG:
        ths[t].register_atom(a, b)
    elif op == NEW:
        ths[t] = Th()
    elif op == DROP:
        del ths[t]
    else:
        now = pc()
        if cur is not None:
            qt[cur] += now - last
        last = now
        cur = cls[t]
now = pc()
qt[cur] += now - last
T = now - start
print(json.dumps(dict(run="py" + ("" if mode == "timed" else mode), wl=wl, T=T, classes=qt, ops=len(ops))), flush=True)
