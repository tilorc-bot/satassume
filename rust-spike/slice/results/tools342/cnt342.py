"""cnt342.py WL [nob] (sa-port-342, issue 323; tools328/cnt329.py's reasons pass for both signatures of the check: 29c5a0db
has _pred(name) and _own(sym), the exact-pi step _pred(name, table) and _own(sym, pi), so every wrapper passes *args):
one cold pure-Python pass over a workload (dev, fuzz with seed 424242, or an evalbench workload) with SLICE_WITNESS=1,
every call of the check recorded. SLICE_WITNESS_CAP=0 gives the uncapped search.

Per call: [query index, certified, points tried, why, points evaluated, pi], with `why` as cnt329.py has it
(certified; extensions; atom: KIND; own: KIND; no symbol; own assumptions: no value; no pair: SIDES) and `pi` true when
the query was compiled a second time with values in Q[pi] (witness._Query(True); never on 29c5a0db, where a pi outside
a function is `atom: constant pi`). The _NeedPi of the first compile is not a reason: the wrappers let it pass.
`nob`: witness._roots is wrapped to drop every root that is a _PiPoly, which is the check without (2b).
Prints one JSON line."""
import gc, hashlib, json, os, sys
from collections import Counter
wl = sys.argv[1]
nob = len(sys.argv) > 2 and sys.argv[2] == "nob"
from evalbench.common import workload
from satassume import sympy_api, witness
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
rows = []
cur = [0]
st = {}
U = witness._Undecided
NP = getattr(witness, "_NeedPi", ())
PP = getattr(witness, "_PiPoly", None)
real = {n: getattr(witness, n) for n in ("witnesses", "_term", "_pred", "_formula", "_own", "_pools", "_holds", "_roots", "_Query")}


def kind_of(e):
    from sympy import Float, Function, NumberSymbol, Symbol, Wild, zoo, nan, I
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
    if isinstance(e, (Symbol, Wild)):
        return "symbol of type " + type(e).__name__
    return "type " + type(e).__name__


def w_term(e, q, u):
    try:
        return real["_term"](e, q, u)
    except U as x:
        if not isinstance(x, NP):
            st.setdefault("kind", kind_of(e))
        raise


def w_pred(name, *args):
    try:
        return real["_pred"](name, *args)
    except U:
        st.setdefault("kind", "predicate " + name)
        raise


def w_formula(f, q):
    try:
        return real["_formula"](f, q)
    except U as x:
        if "kind" not in st and not isinstance(x, NP):
            p = getattr(f, "pred", None)
            st["kind"] = ("relation " + str(p) + " of non-terms") if p is not None else "connective " + type(f).__name__
        raise


def w_own(sym, *args):
    st["own"] = True
    try:
        return real["_own"](sym, *args)
    except U:
        st["own_kind"] = True
        raise
    finally:
        st["own"] = False


def w_pools(q, owns):
    r = real["_pools"](q, owns)
    st["sizes"] = [len(p) for p in r]
    return r


def w_holds(pt, owns, fa, fp):
    r = real["_holds"](pt, owns, fa, fp)
    st["n"] = st.get("n", 0) + 1
    st[str(r)] = st.get(str(r), 0) + 1
    return r


def w_roots(q, n):
    r = real["_roots"](q, n)
    if nob:
        st["dropped"] = st.get("dropped", 0) + sum(type(v) is PP for rs in r for v in rs)
        r = [[v for v in rs if type(v) is not PP] for rs in r]
    return r


def w_query(*args):
    st["pi"] = bool(args and args[0])
    return real["_Query"](*args)


def witnesses(p, a, eng=None):
    st.clear()
    r = real["witnesses"](p, a, eng)
    if r is not None:
        w = "certified"
    elif eng is not None and eng.extensions is not None and (eng.extensions._handlers or eng.extensions._vocab):
        w = "extensions"
    elif "kind" in st:
        w = ("own: " if "sizes" not in st and st.get("own") is False and st.get("own_kind") else "atom: ") + st["kind"]
    elif "sizes" not in st:
        w = "no symbol"
    elif 0 in st["sizes"]:
        w = "own assumptions: no value"
    else:
        w = "no pair: " + (("T" if st.get("True") else "") + ("F" if st.get("False") else "") or "none")
    rows.append([cur[0], r is not None, r[3] if r is not None else 0, w, st.get("n", 0), bool(st.get("pi")),
                 st.get("dropped", 0)])
    return r


witness.witnesses, witness._term, witness._pred, witness._formula = witnesses, w_term, w_pred, w_formula
witness._own, witness._pools, witness._holds, witness._roots, witness._Query = w_own, w_pools, w_holds, w_roots, w_query
ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
for i, (p, a) in enumerate(pairs):
    cur[0] = i
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
print(json.dumps(dict(
    wl=wl, n=len(pairs), nob=nob, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    tree=witness.__file__, witness=witness.ENABLED[0], cap=witness.CAP[0], plant=witness.PLANT[0], fires=len(rows),
    certified=sum(1 for c in rows if c[1]), nones=sum(1 for r in ans if r is None),
    why=dict(Counter(c[3] for c in rows).most_common()), rows=rows, ans=ans)))
