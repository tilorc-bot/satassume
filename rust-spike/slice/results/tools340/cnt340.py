"""cnt340.py WL OUT.json (sa-port-340, issue 323; offline, pure Python, from tools328/cnt329.py): one cold pass over dev or
fuzz (seed 424242) with SLICE_WITNESS=1 and SLICE_WITNESS_CAP=0, and per call of the witness check a row for the three
counts the planner's brief asks for before anything is written in witness.py:

(2a) `pi`, `other`: a walk of the two formulas that mirrors witness._formula and witness._term and lists every leaf the
     check leaves undecided. pi is recognised by type only (the class of SymPy's singleton); nothing is evaluated. For
     each pi leaf the walk records where it stands: `plain` (under Add and Mul only), `base:N` (the base of a power with
     the non-negative integer literal N as exponent, possibly nested), `base:other` (the base of any other power) and
     `exp` (in an exponent). A function is a leaf of the check, so a pi inside one is not a pi leaf: the function is in
     `other`, with `pi_inside` saying whether a pi stands under it. `other` also holds undecided predicates and own
     assumptions.
(2b) nothing more is needed: a query whose formulas hold no pi has no constant in Q[pi] outside Q.
(3)  `sim`: the search rerun on the compiled query under four pool orders, uncapped (limit 2000): the point number at
     which the second side was found, or None. The pools are a copy of witness._pools with the order of its four parts
     as a parameter; order `hrct` (head, roots, constants, tail) is checked to give witness._pools's own lists and the
     real call's point number on every call.
Run from the tree's rust-spike/slice with PYTHONPATH as the bar's."""
import hashlib, json, os, sys
from fractions import Fraction
assert os.environ.get("SLICE_WITNESS") == "1" and os.environ.get("SLICE_WITNESS_CAP") == "0"
wl, out = sys.argv[1:3]
from evalbench.common import workload
from satassume import sympy_api, witness as W
from sympy import Integer, pi, preorder_traversal
PI = type(pi)
U = W._Undecided
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
ORDERS = ("hrct", "rhct", "rcht", "crht", "chrt")


def kind(e):
    from sympy import Float, Function, NumberSymbol, I, zoo, nan
    from sympy.core.function import AppliedUndef
    from sympy.core.numbers import Infinity, NegativeInfinity
    if isinstance(e, Float):
        return "Float"
    if isinstance(e, (Infinity, NegativeInfinity)) or e is zoo or e is nan:
        return "infinity, zoo or nan"
    if e is I or isinstance(e, NumberSymbol):
        return "constant " + str(e)
    if isinstance(e, AppliedUndef):
        return "undefined function"
    if isinstance(e, Function):
        return "function " + type(e).__name__
    return "type " + type(e).__name__


def walk_term(e, ctx, o):
    t = type(e)
    if t is W.Symbol or t is W.Dummy:
        o["syms"].add(e)
    elif isinstance(e, W.Rational):
        pass
    elif t is PI:
        o["pi"].append(ctx)
    elif t is W.Add or t is W.Mul:
        for a in e.args:
            walk_term(a, ctx, o)
    elif t is W.Pow:
        b, x = e.args
        lit = isinstance(x, Integer) and x.p >= 0
        walk_term(b, "exp" if ctx == "exp" else "base:N" if lit and ctx in ("plain", "base:N") else "base:other", o)
        walk_term(x, "exp", o)
    else:
        o["other"].append([kind(e), any(type(s) is PI for s in preorder_traversal(e))])


def walk_formula(f, o):
    if f is True or f is False:
        return
    t = type(f)
    if t is W.P:
        name, e = f.pred, f.expr
        if name == "eq" or name == "lt":
            if type(e) is not W.Args or len(e) != 2:
                o["other"].append(["relation of non-terms", False])
                return
            walk_term(e[0], "plain", o)
            walk_term(e[1], "plain", o)
            return
        if type(e) is W.Args:
            o["other"].append(["predicate of several terms", False])
            return
        try:
            W._pred(name)
        except U:
            o["other"].append(["predicate " + name, False])
        walk_term(e, "plain", o)
        o["preds"].add(name)
        return
    if t in (W.Not, W.And, W.Or, W.Implies, W.Equivalent, W.Exclusive, W.ITE):
        for a in f.args:
            walk_formula(a, o)
        return
    o["other"].append(["connective " + t.__name__, False])


def pools(q, owns, order):
    """witness._pools with the order of its parts as `order`: h head, r roots (with midpoints and a step outside),
    c the query's constants and their neighbours, t tail."""
    n = len(q.syms)
    roots = W._roots(q, n)
    consts = []
    for c in sorted(set(q.consts), key=lambda c: (abs(c), c))[:8]:
        consts += [c, c + 1, c - 1, c + Fraction(1, 2), c - Fraction(1, 2)]
    res = []
    for i in range(n):
        rs = sorted(roots[i][:12])
        crit = list(rs)
        for a, b in zip(rs, rs[1:]):
            crit.append((a + b) / 2)
        if rs:
            crit += [rs[0] - 1, rs[-1] + 1, rs[0] - Fraction(1, 2), rs[-1] + Fraction(1, 2)]
        part = {"h": list(W._HEAD), "r": crit, "c": consts, "t": list(W._TAIL)}
        seen, pool = set(), []
        for v in [v for k in order for v in part[k]]:
            if v not in seen:
                seen.add(v)
                if owns[i] is None or owns[i](v):
                    pool.append(v)
        res.append(pool)
    return res


def search(ps, owns, fa, fp):
    sizes = [len(p) for p in ps]
    if 0 in sizes:
        return None
    found, tried = {}, 0
    for idx in W._by_index_sum(sizes):
        if tried >= W.LIMIT:
            return None
        tried += 1
        r = W._holds([p[i] for p, i in zip(ps, idx)], owns, fa, fp)
        if r is None:
            continue
        found.setdefault(r, None)
        if len(found) == 2:
            return tried
    return None


rows, cur, real = [], [0], W.witnesses


def witnesses(p, a, eng=None):
    r = real(p, a, eng)
    o = {"pi": [], "other": [], "syms": set(), "preds": set()}
    walk_formula(a, o)
    walk_formula(p, o)
    for s in sorted(o["syms"], key=str):
        try:
            W._own(s)
        except U:
            o["other"].append(["own assumption", False])
    row = {"i": cur[0], "cert": r is not None, "tried": r[3] if r is not None else None, "pi": o["pi"], "other": o["other"],
           "nsyms": len(o["syms"]), "sim": None}
    q = W._Query()
    try:
        fa, fp = W._formula(a, q), W._formula(p, q)
        owns = [W._own(s) for s in q.syms]
        ok = bool(q.syms)
    except U:
        ok = False
    assert ok or r is None
    assert ok == (not o["pi"] and not o["other"] and bool(o["syms"])), (cur[0], o, ok)
    if ok:
        assert pools(q, owns, "hrct") == W._pools(q, owns)
        row["sim"] = {k: search(pools(q, owns, k), owns, fa, fp) for k in ORDERS}
        row["sizes"] = [len(x) for x in W._pools(q, owns)]
        assert row["sim"]["hrct"] == row["tried"], (cur[0], row)
    rows.append(row)
    return r


W.witnesses = witnesses
ans = [None] * len(pairs)
for i, (p, a) in enumerate(pairs):
    cur[0] = i
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
json.dump(dict(wl=wl, n=len(pairs), digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16], orders=ORDERS,
               witness_sha=hashlib.sha256(open(W.__file__, "rb").read()).hexdigest()[:16], ans=ans, rows=rows), open(out, "w"))
print(wl, "queries", len(pairs), "calls", len(rows), "certified", sum(r["cert"] for r in rows))
