"""diff352.py WL ARM [OUT.jsonl] (sa-port-352, issue 323; tools351/diff351.py with live.py's loader, so all 20
workloads of the gate load as the bar loads them, and with every call of `witnesses` in the per-query row): the
native witness check (solver_rs/src/witness.rs behind
witness_live.py) against Python's satassume/witness.py, per call and per query, on the slice's backend.

WL: fuzzN (evalbench.fuzz, seed N), or a name live.py `load` takes (the gate's 20: lra f6 wiring scope dev fuzz ground
port loop zero cert budget core opaque rootof value twin transfer:7:60 transfer2:3:40 cls). A row `(f, live.CALL)` is
asked as `f()` (twin: rows with their own engines).
ARM:
  diff     every call of `witness.witnesses` runs twice in one process: the native path first, then the reference with
           the hook off; the reference's result is returned. Compared per call: the result (None, or symbols, the
           two points and the points tried, by ==), and where the native side compiled: size, pi, and the work
           charged (Python's `_Query`, read through a subclass that only remembers the instance).
  native   SLICE_WITNESS_RUST's path as a user runs it; python: the reference alone. Both write OUT.jsonl, one line per
           query: answer, the default engine's Engine.stats and last_budget_limited after it, and `w`: every call of
           `witness.witnesses` the query made, on whichever engine, as None or (symbols, the two points, points
           tried) in text (cmp352.py compares two such files: the certified set is the queries whose `w` holds a
           result).
Environment: SLICE_DIR, SLICE_WITNESS=1 SLICE_CONVERT=rust (and SLICE_TERM_FRAMES as wanted). Prints one JSON line.
"""
import hashlib, json, os, sys, time
wl, arm = sys.argv[1:3]
out_path = sys.argv[3] if len(sys.argv) > 3 else None
S = os.environ["SLICE_DIR"]
sys.path.insert(0, S)
import p_install
p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
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
import witness_live
so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:16]
import live
if wl.startswith("fuzz") and wl != "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(wl[4:]))
else:
    pairs = live.load(wl)
W = witness
assert W.ENABLED[0], "SLICE_WITNESS=1"
witness_live.install(arm != "python")
N = dict(calls=0, native_none=0, native_tuple=0, fallback=0, ref_none=0, ref_tuple=0, compiled=0, searched=0)
bad = []
cur = [0]
if arm == "diff":
    last_q, last_h = [None], [None]

    _Base = W._Query

    class _Q(_Base):
        __slots__ = ()

        def __init__(self, pi=False):
            _Base.__init__(self, pi)
            last_q[0] = self
    W._Query = _Q
    # an instrument of ours: the native path stays on with it in place (witness_live._replaced)
    witness_live._OWN = tuple((n, vars(W)[n]) for n, _ in witness_live._OWN)
    real_c = sa_solver.witness_compile

    def compile_(*a):
        h = last_h[0] = real_c(*a)
        return h
    sa_solver.witness_compile = compile_
    real_w = W.witnesses
    real_n = witness_live.native
    fell = [False]

    def native(p, a, eng):
        r = real_n(p, a, eng)
        fell[0] = r is NotImplemented
        return r

    def same(x, y):
        if x is None or y is None:
            return x is None and y is None
        return (len(x) == 4 and len(x[0]) == len(y[0]) and all(s == t and type(s) is type(t) for s, t in zip(x[0], y[0]))
                and list(x[1]) == list(y[1]) and list(x[2]) == list(y[2]) and x[3] == y[3])

    def witnesses(p, a, eng=None):
        N["calls"] += 1
        last_h[0] = None
        fell[0] = False
        W.NATIVE[0] = native
        rn = real_w(p, a, eng)
        h = last_h[0]
        W.NATIVE[0] = None
        last_q[0] = None
        rp = real_w(p, a, eng)
        q = last_q[0]
        N["ref_tuple" if rp is not None else "ref_none"] += 1
        if fell[0]:
            N["fallback"] += 1
        else:
            N["native_tuple" if rn is not None else "native_none"] += 1
        why = None
        if not same(rn, rp):
            why = "result"
        elif h is not None and h is not False:
            N["compiled"] += 1
            if q is None or (h.size, h.pi, len(h.syms)) != (q.size, q.pi, len(q.syms)):
                why = "compile %r %r" % ((h.size, h.pi, len(h.syms)), q and (q.size, q.pi, len(q.syms)))
            elif h.work != q.work:
                why = "work %d %d" % (h.work, q.work)
            if h.work:
                N["searched"] += 1
        if why and len(bad) < 40:
            bad.append((cur[0], why, repr(rn)[:300], repr(rp)[:300], repr(p)[:200], repr(a)[:300]))
        elif why:
            bad.append((cur[0], why))
        return rp
    W.witnesses = witnesses
calls = []
if arm != "diff":
    from fractions import Fraction
    real_w0 = W.witnesses

    def witnesses(p, a, eng=None):
        r = real_w0(p, a, eng)
        calls.append(None if r is None else [[type(s).__name__ + " " + str(s) for s in r[0]], [str(Fraction(v)) for v in r[1]],
                                             [str(Fraction(v)) for v in r[2]], r[3]])
        return r
    W.witnesses = witnesses
ans = [None] * len(pairs)
eng = sympy_api.default_engine()
f = open(out_path, "w") if out_path else None
ask = sympy_api.ask
t0 = time.perf_counter()
for i, (p, a) in enumerate(pairs):
    cur[0] = i
    try:
        r = p() if type(a) is str and a == live.CALL else ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
        if os.environ.get("TRACE351"):
            raise
    ans[i] = r
    if f:
        f.write(json.dumps(dict(q=i, a=r, stats=sorted(eng.stats.items()), bl=eng.last_budget_limited, w=calls[:])) + "\n")
    del calls[:]
s = time.perf_counter() - t0
print(json.dumps(dict(
    wl=wl, arm=arm, so=so, n=len(pairs), s=round(s, 3), digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    certified=eng.stats.get("witness_certified"), queries=eng.stats.get("queries"), N=N, counts=witness_live.counts(),
    mismatches=len(bad), first=bad[:6], convert=os.environ.get("SLICE_CONVERT", "py"),
    frames=os.environ.get("SLICE_TERM_FRAMES", "py"), cap=W.CAP[0], work=W.WORK[0])))
