"""Rebuild each dumped exhausted problem as a standalone LRATheory and try
prototype completions of branch and bound on it.

    python proto.py OUT.jsonl...      (PYTHONPATH = a satassume clone)

Variants per problem (budget N nodes):
  base   : lra.py's _branch as is
  lat    : + conflict when a negated integrality form lies in the Z-affine span
           of the asserted positive ones (pinned variables substituted)
  lat+ds : + slacks whose form lies in that span branch as integers too
           ("derived integral"), with GCD rounding of their bounds
"""
import json
import sys
from fractions import Fraction
from math import gcd, floor

sys.setrecursionlimit(100000)
import satassume.theories.lra.lra as L  # noqa: E402
from satassume.theories.lra.lra import LRATheory, constraint, Integral  # noqa: E402

F = Fraction


def build(r):
    """(theory, forms over term names) with every dumped literal asserted."""
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

    def form(v):
        f = forms.get(v)
        return {f"x{v}": F(1)} if f is None else {f"x{a}": F(c) for a, c in f}

    t = LRATheory()
    lits = []
    n = 0
    for b in r["bounds"]:
        if b["lo"]:
            q, d = map(F, b["lo"])
            n += 1
            lits.append((n, constraint(form(b["v"]), ">" if d > 0 else ">=", q)))
        if b["up"]:
            q, d = map(F, b["up"])
            n += 1
            lits.append((n, constraint(form(b["v"]), "<" if d < 0 else "<=", q)))
    ints = []
    for v, m, k, lit, _ in r["ints"]:
        n += 1
        fm = {a: c * F(m) for a, c in form(v).items()}
        ints.append((fm, F(k), lit > 0))
        lits.append((n if lit > 0 else -n, Integral(tuple(fm.items()), F(k))))
    for v, c, _ in r["dis"]:
        n += 1
        lits.append((n, constraint(form(v), "!=", F(c))))
    for l, p in lits:
        t.register_atom(abs(l), p)
    for l, p in lits:
        if t.assert_lit(l) is not None:
            return None, ints
    return t, ints


# ---- Z-affine span membership over Q (vectors: dict name -> Fraction, "1" = constant)

def _echelon(gens):
    """Integer echelon basis (list of (pivot, intvector)) of the Z-span of gens."""
    keys = sorted({k for g in gens for k in g})
    D = 1
    for g in gens:
        for c in g.values():
            D = D * c.denominator // gcd(D, c.denominator)
    rows = [[int(g.get(k, 0) * D) for k in keys] for g in gens]
    basis = []
    for col in range(len(keys)):
        piv = [r for r in rows if r[col]]
        rest = [r for r in rows if not r[col]]
        while len(piv) > 1:
            piv.sort(key=lambda r: abs(r[col]))
            p = piv[0]
            nxt = [p]
            for r in piv[1:]:
                q = r[col] // p[col]
                r = [a - q * b for a, b in zip(r, p)]
                (nxt if r[col] else rest).append(r)
            piv = nxt
        if piv:
            basis.append((col, piv[0]))
        rows = rest
    return keys, D, basis


def in_span(gens, target):
    keys, D, basis = _echelon(gens)
    if any(k not in keys and c for k, c in target.items()):
        return False
    t = [target.get(k, F(0)) * D for k in keys]
    if any(x.denominator != 1 for x in t):
        return False
    t = [int(x) for x in t]
    for col, p in basis:
        if t[col] % p[col]:
            return False
        q = t[col] // p[col]
        t = [a - q * b for a, b in zip(t, p)]
    return not any(t)


def lattice_conflict(r, ints):
    """Some negated integrality form lies in the Z-affine span of the positive
    ones and the constant 1, with pinned term variables substituted."""
    pinned = {}
    for b in r["bounds"]:
        if b["form"] is None and b["lo"] and b["lo"] == b["up"] and F(b["lo"][1]) == 0:
            pinned[f"x{b['v']}"] = F(b["lo"][0])

    def vec(fm, k):
        out = {"1": k}
        for a, c in fm.items():
            if a in pinned:
                out["1"] += c * pinned[a]
            elif c:
                out[a] = out.get(a, 0) + c
        return {a: c for a, c in out.items() if c}

    gens = [{"1": F(1)}] + [vec(fm, k) for fm, k, pos in ints if pos]
    return any(in_span(gens, vec(fm, k)) for fm, k, pos in ints if not pos)


def run_base(t, n):
    t.exhausted = False
    b0 = t.stats["branches"]
    r = t._simplex()
    if r is None:
        r = t._branch([n])
    res = "conflict" if r is not None else ("exhausted" if t.exhausted else "intpoint")
    return res, t.stats["branches"] - b0


if __name__ == "__main__":
    from collections import Counter
    N = 2000
    for path in sys.argv[1:]:
        C = Counter()
        rows = []
        for line in open(path):
            r = json.loads(line)
            if r["fields"]:
                C["fields(skipped)"] += 1
                continue
            t, ints = build(r)
            if t is None:
                C["conflict-on-assert"] += 1
                continue
            base = run_base(t, N)
            lat = lattice_conflict(r, ints)
            C[(base[0], "lat" if lat else "-")] += 1
            rows.append({"q": r["q"], "base": base, "lat": lat})
        print(path, dict(C))
        with open(path.replace(".jsonl", ".proto.jsonl"), "w") as f:
            for o in rows:
                f.write(json.dumps(o) + "\n")


def derived_slacks(r, ints, t):
    """Theory vars of the rebuilt t whose form (over terms) is in the span."""
    pinned = {}
    gens = [{"1": F(1)}]
    for fm, k, pos in ints:
        if pos:
            g = {"1": k}
            g.update({a: c for a, c in fm.items() if c})
            gens.append(g)
    out = []
    for form, s in t._slack_of.items():
        tgt = {t._key[a]: c for a, c in form}
        if all(isinstance(k, str) for k in tgt) and in_span(gens, tgt):
            out.append(s)
    return out


def run_ds(r, ints, n):
    t, _ = build(r)
    extra = derived_slacks(r, ints, t)
    for s in extra:
        t._int_lits.append((s, L._ONE, L._ZERO, 10 ** 6))
    res = run_base(t, n)
    return res, len(extra)


if __name__ == "__main__" and len(sys.argv) > 1:
    from collections import Counter
    for path in sys.argv[1:]:
        C = Counter()
        for line in open(path):
            r = json.loads(line)
            if r["fields"]:
                continue
            t, ints = build(r)
            if t is None or lattice_conflict(r, ints):
                continue
            (res, nodes), nx = run_ds(r, ints, 2000)
            C[(res, nodes if nodes < 50 else ">=50", nx)] += 1
        print("ds", path, dict(C))


def run_v(r, ints, n, mode):
    t, _ = build(r)
    extra = derived_slacks(r, ints, t)
    pos = [(v, m, k, l) for v, m, k, l in t._int_lits if l > 0 and m == 1 and k == 0]
    if mode == "first":
        t._int_lits[:0] = [(s, L._ONE, L._ZERO, 10 ** 6) for s in extra]
    else:                                   # tighten: round bounds of integral vars
        t._int_lits.extend((s, L._ONE, L._ZERO, 10 ** 6) for s in extra)
        t.push_level()
        for v in {v for v, *_ in pos} | set(extra):
            lo, up = t._lo[v], t._up[v]
            if lo is not None:
                c = L._ceil(*lo)
                if t._assert_kind(v, ">=", F(c), 0) is not None:
                    return ("conflict", 0)
            if up is not None:
                c = L._floor(*up)
                if t._assert_kind(v, "<=", F(c), 0) is not None:
                    return ("conflict", 0)
    return run_base(t, n)


if __name__ == "__main__" and len(sys.argv) > 1:
    for mode in ("first", "tighten"):
        for path in sys.argv[1:]:
            C = Counter()
            for line in open(path):
                r = json.loads(line)
                if r["fields"]:
                    continue
                t, ints = build(r)
                if t is None or lattice_conflict(r, ints):
                    continue
                res, nodes = run_v(r, ints, 2000, mode)
                C[(res, nodes if nodes < 50 else ">=50")] += 1
            print(mode, path, dict(C))
