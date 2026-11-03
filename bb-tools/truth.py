"""Ground truth (z3, offline only) for each dumped exhausted problem.

    zenv/bin/python truth.py OUT.jsonl...   -> prints a table, writes OUT.truth.jsonl
"""
import json
import sys
from fractions import Fraction

import z3


PI = z3.Real("pi")


def Q(s):
    if s.startswith("Element("):
        assert s == "Element((1/2)*pi)", s
        return PI / 2
    f = Fraction(s)
    return z3.RealVal(f"{f.numerator}/{f.denominator}")


def decide(r, timeout_ms=20000):
    X = {}

    def term(a):
        if a not in X:
            X[a] = z3.Real(f"x{a}")
        return X[a]

    forms = {}
    for b in r["bounds"]:
        if b["form"]:
            forms[b["v"]] = b["form"]
    for i in r["ints"]:
        if i[4]:
            forms[i[0]] = i[4]
    for d in r["dis"]:
        if d[2]:
            forms[d[0]] = d[2]

    def ex(v):
        f = forms.get(v)
        if f is None:
            return term(v)
        return z3.Sum([Q(c) * ex(a) for a, c in f])

    s = z3.Solver()
    s.set("timeout", timeout_ms)
    s.add(PI > z3.RealVal("314159265/100000000"), PI < z3.RealVal("314159266/100000000"))
    for b in r["bounds"]:
        e = ex(b["v"])
        if b["lo"]:
            q, d = b["lo"]
            s.add(e > Q(q) if Q(d) is not None and Fraction(d) > 0 else e >= Q(q))
        if b["up"]:
            q, d = b["up"]
            s.add(e < Q(q) if Fraction(d) < 0 else e <= Q(q))
    for j, (v, m, k, lit, _) in enumerate(r["ints"]):
        t = Q(m) * ex(v) + Q(k)
        n = z3.Int(f"n{j}")
        if lit > 0:
            s.add(z3.ToReal(n) == t)
        else:
            s.add(z3.ToReal(n) < t, t < z3.ToReal(n) + 1)
    for v, c, _ in r["dis"]:
        s.add(ex(v) != Q(c))
    res = s.check()
    return str(res), len(X)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        out = []
        for line in open(path):
            r = json.loads(line)
            res, nx = decide(r)
            out.append({"q": r["q"], "truth": res, "nterms": nx})
        with open(path.replace(".jsonl", ".truth.jsonl"), "w") as f:
            for o in out:
                f.write(json.dumps(o) + "\n")
        from collections import Counter
        print(path, Counter(o["truth"] for o in out), Counter(o["nterms"] for o in out))
