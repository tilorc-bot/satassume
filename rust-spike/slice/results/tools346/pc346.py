"""pc346.py WL MODE (sa-port-346, issue 323; tools344/pc344.py with four more columns per call, for the work bound:
the query's compiled terms (_Query.size), the term evaluations charged (_Query.work), the microseconds in _pools (the
roots and the pools, before the first point) and the microseconds in Engine._ends_without_session (the engine's
no-session test the check asks before a point, None if not asked) with its result. The _Query is read through a
subclass set here, in the driver's process; `nosession` is wrapped in both modes (it is no guarded method).
Was: pc344.py WL MODE (sa-port-344, issue 323; tools343/pc343.py with two changes. (1) The wrappers this driver sets
on Engine.ask and Engine._within_budget are registered with witness.accept, as the docstring of accept asks of an
instrument: pc343.py did not, so in py mode the check's last guard (_patched, witness.py:841) took them for a user's
methods and no call was certified (cx343's 20 workloads and the py rows of timing-pc all read certified 0; rust mode
sets no wrapper on the engine and read wiring 231). (2) Each call also records the calls of _holds in it (points
decided, also when the check falls through) and the microseconds before _pools is entered (the per-call compile:
_formula twice and _own), None if _pools is not reached.
Was: pc343.py WL MODE (sa-port-343, issue 323; tools328/wit328.py with the slice's workloads budget and wiring loaded as
qt342.py loads them, any other but dev and fuzz by live.py's load(), and one row per call of the check): one cold pass over a workload with SLICE_WITNESS=1, every call
of the witness check timed, and what the engine did with the query after a call that fell through. Nothing in the
package is changed: the rows come from wrappers set here, in the driver's process.

Per call (`calls`): [query index, microseconds in the check, certified, points tried, exit, microseconds in Engine.ask,
calls of _holds, microseconds before _pools, size, work, microseconds in _pools, microseconds in
_ends_without_session, its result].
`exit` is what followed the check (MODE py only; in rust mode only the check is wrapped and exit is null):
  certified       the check returned a pair; Engine.ask is not called
  noncommutative  Engine.ask returned before its budget test (engine.py, _noncommutative_atoms): None, no session
  over-budget     Engine._over_budget was called: None without a session
  no-build        Engine.ask ended without Engine._build_context: a memoized Uninterpreted or INCONSISTENT of the set
  session         Engine._build_context ran: the query's session was built
Also: s (seconds over all asks, with the wrappers' clock reads: not an S1 time), digest of the answers, the engine's
stats, and `top`: the 10 calls with the most time in the check, with the query's text (str, made after the pass).
"""
import gc, hashlib, json, os, sys, time
wl, mode = sys.argv[1:3]
S = os.environ.get("SLICE_DIR")
so = None
if mode != "py":
    sys.path.insert(0, S)
    import p_install
    p_install.install()
from evalbench.common import workload
from satassume import sympy_api, witness
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
    pairs = queries(int(os.environ.get("FUZZ_SEED", "424242")))   # sa-port-346: another seed for the work rows
elif wl in ("budget", "wiring"):    # the slice's own workloads, as live.py's load() names them (qt342.py)
    import importlib
    if S not in sys.path:
        sys.path.append(S)
    pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
elif wl == "dev":
    pairs = workload(wl)
else:                               # any other workload of the slice (the gate's 20), by live.py's load()
    if S not in sys.path:
        sys.path.append(S)
    import live
    pairs = live.load(wl)
pc = time.perf_counter
calls = []          # (query index, seconds, certified, points tried)
compiled = [0]
cur = [0]
real_w, real_p = witness.witnesses, witness._pools


_Q0 = witness._Query


class _Q(_Q0):
    __slots__ = ()

    def __init__(self, pi=False):
        _Q0.__init__(self, pi)
        lastq[0] = self


lastq = [None]
witness._Query = _Q
tpool = [None]
tns = [None, None]


def witnesses(p, a, eng=None):
    holds[0] = 0
    tp[0] = tpool[0] = lastq[0] = None
    tns[:] = [None, None]
    t = pc()
    r = real_w(p, a, eng)
    t1 = pc()
    q_ = lastq[0]
    calls.append([cur[0], round((t1 - t) * 1e6, 1), r is not None, r[3] if r is not None else 0,
                  "certified" if r is not None else None, None, holds[0],
                  None if tp[0] is None else round((tp[0] - t) * 1e6, 1),
                  q_.size if q_ is not None else None, q_.work if q_ is not None else None, tpool[0], tns[0], tns[1]])
    pend[0] = r is None
    return r


pend = [False]      # the last call of the check fell through and Engine.ask has not been seen since
seen = [0, 0, 0]    # inside the Engine.ask after it: calls of _within_budget, _over_budget, _build_context
engs = []
if mode == "py":
    from satassume.engine import Engine
    real_ask, real_wb, real_ob, real_bc = Engine.ask, Engine._within_budget, Engine._over_budget, Engine._build_context

    def e_ask(self, proposition, assumptions=None):
        if not pend[0]:
            return real_ask(self, proposition, assumptions)
        pend[0] = False
        if not engs:
            engs.append(self)
        seen[:] = [0, 0, 0]
        row = calls[-1]
        t = pc()
        try:
            return real_ask(self, proposition, assumptions)
        finally:
            row[5] = round((pc() - t) * 1e6, 1)
            row[4] = ("over-budget" if seen[1] else "session" if seen[2] else "noncommutative" if not seen[0]
                      else "no-build")

    def e_wb(self, *a):
        seen[0] += 1
        return real_wb(self, *a)

    def e_ob(self):
        seen[1] += 1
        return real_ob(self)

    def e_bc(self, *a):
        seen[2] += 1
        return real_bc(self, *a)

    Engine.ask, Engine._within_budget, Engine._over_budget, Engine._build_context = e_ask, e_wb, e_ob, e_bc
    witness.accept(Engine)      # sa-port-344: these wrappers are instruments, not a user's methods


def pools(q, owns):
    tp[0] = pc()
    compiled[0] += 1
    try:
        return real_p(q, owns)
    finally:
        tpool[0] = round((pc() - tp[0]) * 1e6, 1)


from satassume.engine import Engine as _E
real_ns = _E._ends_without_session


def e_ns(self, *a):
    t = pc()
    r = None
    try:
        r = real_ns(self, *a)
        return r
    finally:
        tns[:] = [round((pc() - t) * 1e6, 1), r]


_E._ends_without_session = e_ns


def holds_(*a):
    holds[0] += 1
    return real_h(*a)


holds = [0]
tp = [None]
real_h = witness._holds
witness.witnesses, witness._pools, witness._holds = witnesses, pools, holds_
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


def q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else None


def med(xs):
    return q(xs, .5)


kinds = {}
for c in calls:
    kinds.setdefault(c[4], []).append(c)
split = {str(k): dict(n=len(v), check_s=round(sum(c[1] for c in v) / 1e6, 4), check_us=[med([c[1] for c in v]),
                      q([c[1] for c in v], .9), max(c[1] for c in v)],
                      engine_s=round(sum(c[5] or 0 for c in v) / 1e6, 4), engine_us=med([c[5] or 0 for c in v]))
         for k, v in kinds.items()}
top = [dict(q=c[0], check_us=c[1], certified=c[2], tried=c[3], exit=c[4], engine_us=c[5], ask_us=round(per[c[0]] * 1e6, 1),
            prop=str(pairs[c[0]][0])[:300], assume=str(pairs[c[0]][1])[:600])
       for c in sorted(calls, key=lambda c: -c[1])[:10]]
st = dict(engs[0].stats) if engs else None
print(json.dumps(dict(
    wl=wl, mode=mode, so=so, n=len(pairs), s=total, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=witness.ENABLED[0], cap=witness.CAP[0], work=witness.WORK[0], plant=witness.PLANT[0],
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"),
    fires=len(calls), compiled=compiled[0], certified=sum(1 for c in calls if c[2]),
    check_s=sum(c[1] for c in calls) / 1e6, split=split, top=top,
    stats={k: v for k, v in st.items() if isinstance(v, (int, float))} if st else None, calls=calls)))
