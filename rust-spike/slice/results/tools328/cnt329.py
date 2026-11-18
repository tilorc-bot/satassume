"""cnt329.py WL MODE [reasons] (sa-port-329, issue 323; from wit328.py): one cold pass over a workload with every call of
the witness check recorded one by one. Run with SLICE_WITNESS=1; SLICE_WITNESS_CAP=0 gives the uncapped search, from
which the certified count at any smaller cap follows (a pair found at the t-th point is found under every cap >= t: the
order of the points does not depend on the cap).

WL, MODE: as wit328.py. Without `reasons` only `witness.witnesses` is wrapped (two clock reads a call), and `calls` holds
[query index, seconds, certified, points tried] per call: the check's own time per call. With `reasons` the driver also
wraps _term, _pred, _formula, _own, _pools and _holds in its own process (the package keeps no counter) and adds per call
why it fell through: `why` is one of
  extensions                 a registration in the engine's extensions
  atom: KIND                 an atom with no exact value at any point; KIND is the leaf's or the predicate's kind
  own: KIND                  a symbol's own assumption the table does not decide
  no symbol                  nothing to give a value to
  own assumptions: no value  a symbol's own assumptions exclude every candidate value
  no pair: SIDES             the search ended (limit or points exhausted) with SIDES found (T, F, or none), `n` points tried
The seconds of a `reasons` pass include the wrappers and are not the check's cost. Also printed: `used`, how often each
derived predicate (rules.DEFINITIONS) was asked for, by atoms and by own assumptions; `queries_without_call`;
`ctx`, per query whether it was asked with assumptions at all; `entry`, per query how sympy_api._engine_ask was last
called for it (with assumptions, without, or None: not called, an answer memo hit)."""
import gc, hashlib, json, os, sys, time
from collections import Counter
wl, mode = sys.argv[1:3]
reasons = len(sys.argv) > 3 and sys.argv[3] == "reasons"
S = os.environ.get("SLICE_DIR")
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
from satassume.knowledge.rules import DEFINITIONS
if mode != "py":
    import sa_solver
    import backend
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    import knowledge_live
    knowledge_live.from_env()
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
calls, why = [], []
cur = [0]
st = {}
used = Counter()
U = witness._Undecided
real = {n: getattr(witness, n) for n in ("witnesses", "_term", "_pred", "_formula", "_own", "_pools", "_holds")}


def kind_of(e):
    from sympy import Float, Function, NumberSymbol, Symbol, Wild, zoo, nan, oo, I
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
    except U:
        st.setdefault("kind", kind_of(e))
        raise


def w_pred(name):
    if name in DEFINITIONS:
        used[("own " if st.get("own") else "atom ") + name] += 1
    try:
        return real["_pred"](name)
    except U:
        st.setdefault("kind", "predicate " + name)
        raise


def w_formula(f, q):
    try:
        return real["_formula"](f, q)
    except U:
        if "kind" not in st:
            p = getattr(f, "pred", None)
            st["kind"] = ("relation " + str(p) + " of non-terms") if p is not None else "connective " + type(f).__name__
        raise


def w_own(sym):
    st["own"] = True
    try:
        return real["_own"](sym)
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


def witnesses(p, a, eng=None):
    st.clear()
    t = pc()
    r = real["witnesses"](p, a, eng)
    dt = pc() - t
    calls.append([cur[0], dt, r is not None, r[3] if r is not None else 0])
    if not reasons:
        return r
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
    prod = 1
    for m in st.get("sizes", [0]):
        prod *= m
    why.append([cur[0], w, st.get("n", 0), prod])
    return r


witness.witnesses = witnesses
entry = {}      # query -> how sympy_api._engine_ask was last called for it: with assumptions or without
if reasons:
    def w_engine_ask(proposition, assumptions, eng, _e=sympy_api._engine_ask):
        entry[cur[0]] = "without assumptions" if assumptions is True else "with assumptions"
        return _e(proposition, assumptions, eng)
    sympy_api._engine_ask = w_engine_ask
    def w_own(sym, _o=real["_own"]):        # an undecided own assumption is marked as such
        st["own"] = True
        try:
            return _o(sym)
        except U:
            st["own_kind"] = True
            raise
        finally:
            st["own"] = False
    witness._term, witness._pred, witness._formula, witness._own = w_term, w_pred, w_formula, w_own
    witness._pools, witness._holds = w_pools, w_holds
per = [0.0] * len(pairs)
ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
gc.freeze()
t0 = pc()
for i, (p, a) in enumerate(pairs):
    cur[0] = i
    t = pc()
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    per[i] = pc() - t
    ans[i] = r
total = pc() - t0
called = set(c[0] for c in calls)
print(json.dumps(dict(
    wl=wl, mode=mode, so=so, n=len(pairs), s=total, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=witness.ENABLED[0], cap=witness.CAP[0], plant=witness.PLANT[0], reasons=reasons,
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"),
    fires=len(calls), certified=sum(1 for c in calls if c[2]), check_s=sum(c[1] for c in calls),
    queries_without_call=len(pairs) - len(called), used=dict(sorted((k, v) for k, v in used.items())),
    ctx=[a is not True for p, a in pairs], entry=[entry.get(i) for i in range(len(pairs))], calls=calls, why=why, ans=ans, per=per)))
