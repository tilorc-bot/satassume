"""prof350.py WL MODE KIND (sa-port-350, issue 323; from tools328/wit328.py): one cold pass over a workload with the
witness check (satassume/witness.py, SLICE_WITNESS=1) timed by phase. The planner's item 1: a profile before any port.

WL: dev, fuzz (seed 424242), budget, wiring (the slice's own) or an evalbench workload. MODE: py (the package alone) or rust (the slice's backend;
SLICE_CONVERT and SLICE_TERM_FRAMES pick the Rust switches). KIND:
  plain   only `witness.witnesses` is wrapped (two clock reads per check): `check_s` is the check's inclusive time
  phase   the phases are wrapped as well, all from the driver's process (the package keeps no timer):
            compile   entry of `witnesses` to the first guard (`_patched`), or to the exit if it returns before one:
                      the two `_formula` walks, the second compile of a query with pi, `_own` per symbol
            guards    `_patched`, `Engine._known_inconsistent`, `_users_knowledge` (they read the engine; not the port)
            evaluation  the probes' functions inside `_roots` plus `_holds` (the closures, Fraction and _PiPoly
                      arithmetic, the tables, the own assumptions at a point)
            search    the rest: `_pools` without its probe evaluations, `_by_index_sum`, the loop of `witnesses`
  cprof   cProfile enabled only inside `witnesses`: tottime by file under the check (own = witness.py). cProfile
          charges every Python call, so this is a ratio of call-weighted time, not a wall time.
Prints one JSON line. Not an S1 time (S1 is qt342.py); the shares are read against `s` of the plain pass.
"""
import gc, hashlib, json, os, sys, time
wl, mode, kind = sys.argv[1:4]
S = os.environ.get("SLICE_DIR")
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
from satassume import engine as _engine
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
elif wl in ("budget", "wiring"):    # the slice's own workloads, as tools342/qt342.py loads them
    import importlib
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
else:
    pairs = workload(wl)
pc = time.perf_counter
W = witness
calls = []          # (query index, seconds, certified, points tried, compiled)
cur = [0]
T = dict(compile=0.0, patched=0.0, known=0.0, users=0.0, pools=0.0, roots=0.0, probe_eval=0.0, enum=0.0, holds=0.0)
N = dict(patched=0, known=0, users=0, pools=0, roots=0, probe_eval=0, enum=0, holds=0, work=0, size=0, syms=0,
         pi=0, over_work=0)
cend = [None]
inside = [False]
qref = [None]
real_w = W.witnesses
prof = None
if kind == "cprof":
    import cProfile
    prof = cProfile.Profile()


def witnesses(p, a, eng=None):
    cend[0] = None
    qref[0] = None
    inside[0] = True
    if prof is not None:
        prof.enable()
    t = pc()
    r = real_w(p, a, eng)
    t1 = pc()
    if prof is not None:
        prof.disable()
    inside[0] = False
    T["compile"] += (cend[0] if cend[0] is not None else t1) - t
    q = qref[0]
    if q is not None:
        N["work"] += q.work
        N["size"] += q.size
        N["syms"] += len(q.syms)
        N["pi"] += q.pi
        N["over_work"] += W.WORK[0] != 0 and q.work > W.WORK[0]
    calls.append((cur[0], t1 - t, r is not None, r[3] if r is not None else 0, q is not None))
    return r


W.witnesses = witnesses
if kind == "phase":
    def timed(name, f, mark=False):
        def g(*a):
            t = pc()
            if mark and cend[0] is None:
                cend[0] = t
            try:
                return f(*a)
            finally:
                T[name] += pc() - t
                N[name] += 1
        return g

    W._patched = timed("patched", W._patched, True)
    W._users_knowledge = timed("users", W._users_knowledge)
    W._roots = timed("roots", W._roots)
    W._holds = timed("holds", W._holds)
    real_p, real_b = W._pools, W._by_index_sum

    def pools(q, owns):
        qref[0] = q
        q.probes = [(timed("probe_eval", d), used, cost) for d, used, cost in q.probes]
        t = pc()
        try:
            return real_p(q, owns)
        finally:
            T["pools"] += pc() - t
            N["pools"] += 1

    def by_index_sum(sizes):
        it = real_b(sizes)
        while True:
            t = pc()
            try:
                v = next(it)
            except StopIteration:
                T["enum"] += pc() - t
                return
            T["enum"] += pc() - t
            N["enum"] += 1
            yield v

    W._pools, W._by_index_sum = pools, by_index_sum
    real_k = _engine.Engine._known_inconsistent

    def known(self, assumptions):
        if not inside[0]:
            return real_k(self, assumptions)
        t = pc()
        try:
            return real_k(self, assumptions)
        finally:
            T["known"] += pc() - t
            N["known"] += 1

    _engine.Engine._known_inconsistent = known
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
check = sum(c[1] for c in calls)
out = dict(
    wl=wl, mode=mode, kind=kind, so=so, n=len(pairs), s=total,
    digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=W.ENABLED[0], cap=W.CAP[0], work_bound=W.WORK[0], plant=str(W.PLANT[0]),
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"),
    fires=len(calls), certified=sum(1 for c in calls if c[2]), compiled=sum(1 for c in calls if c[4]),
    check_s=check, check_cert_s=sum(c[1] for c in calls if c[2]), check_fall_s=sum(c[1] for c in calls if not c[2]),
    # the queries the check certified and the ones it did not: seconds of the whole ask
    ask_cert_s=sum(per[i] for i in {c[0] for c in calls if c[2]}),
    stats=None)
if kind == "phase":
    ev = T["probe_eval"] + T["holds"]
    gd = T["patched"] + T["known"] + T["users"]
    out.update(T=T, N=N, compile_s=T["compile"], guards_s=gd, evaluation_s=ev,
               search_s=check - T["compile"] - gd - ev)
if prof is not None:
    import pstats
    by = {}
    fn = {}
    for (f, line, name), (cc, nc, tt, ct, callers) in pstats.Stats(prof).stats.items():
        k = os.path.basename(f) if f != "~" else "builtins"
        by[k] = by.get(k, 0.0) + tt
        if k in ("witness.py", "fractions.py", "builtins", "engine.py"):
            fn["%s:%s" % (k, name)] = fn.get("%s:%s" % (k, name), 0.0) + tt
    tot = sum(by.values())
    out.update(cprof_total=tot, cprof_by_file={k: round(v, 4) for k, v in sorted(by.items(), key=lambda x: -x[1])[:12]},
               cprof_top={k: round(v, 4) for k, v in sorted(fn.items(), key=lambda x: -x[1])[:25]})
print(json.dumps(out))
