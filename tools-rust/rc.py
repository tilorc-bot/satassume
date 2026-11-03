"""rc.py MODE WORKLOAD [--ans OUT]: one cold replay of dev or fuzz 424242 with
outside instrumentation only (monkeypatches, nothing in the package). JSON to stdout.

Modes
  base   nothing: the same loop as sa-lzr's protime.py, the reference time.
  bdry   outermost timers at the boundary: Engine.ask, Engine.is_, Engine.is_many,
         Engine.verdict. Time outside them stays in Python whatever happens.
  mon    bdry + sys.monitoring intervals on every code object under sympy/: outermost
         entry into SymPy to its return, by entry function, inside and outside the
         boundary. Includes callback time; see the calibration in the output.
  moncall mon + caller of each outermost entry (slower; for the names, not the times).
  samp   bdry + an in-process SIGALRM sampler that classifies the stack.
  fn     bdry + outermost timers on the satassume functions that read or build SymPy
         objects behind the boundary (coarse.py lists them).
  monfn  mon + fn: only to split SymPy entries inside the boundary into those under an fn
         group (side 2) and those not (side 1), so the fn row does not double count them.
  dbl    base + one extra Python layer on Basic.__hash__ and Integer.__hash__, and a hot
         loop timing of a plain hash(e) at the end: the real cost of a thin SymPy call,
         with no monitoring. T(dbl) - T(base) over the count is the cost of one layer.
  out    bdry + exclusive timers on the items outside the boundary (outside.py).
  dblc   dbl with a counter in the layer: the count (not timed).
  enc    bdry + the encoder of encode.py run and timed at each boundary call.
"""
import gc
import hashlib
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
mode, wl = sys.argv[1], sys.argv[2]
ans_out = sys.argv[sys.argv.index("--ans") + 1] if "--ans" in sys.argv else None

from evalbench.common import ask_all, workload  # noqa: E402
from satassume import sympy_api  # noqa: E402
from satassume.engine import Engine  # noqa: E402

if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

pc = time.perf_counter


class B:
    """Boundary state: depth, inside seconds, outermost calls by name."""
    depth = 0
    inside = 0.0
    calls = {}
    t_extra = 0.0   # time a mode spends in its own work outside the boundary timers
    enter = None    # hook(name, args) at an outermost boundary call (enc)
    leave = None    # hook(name, args, session list) after it


ENTRIES = ("ask", "is_", "is_many", "verdict")


def wrap_boundary():
    for name in ENTRIES:
        orig = getattr(Engine, name)
        B.calls[name] = 0

        def w(self, *a, _orig=orig, _name=name, **k):
            if B.depth:
                return _orig(self, *a, **k)
            B.depth = 1
            B.calls[_name] += 1
            if B.enter is not None:
                B.enter(_name, a)
            t = pc()
            try:
                return _orig(self, *a, **k)
            finally:
                B.inside += pc() - t
                B.depth = 0
                if B.leave is not None:
                    B.leave(_name, a)
        setattr(Engine, name, w)


# ---------------------------------------------------------------- sys.monitoring
def is_sympy_file(fn):
    return "/sympy/" in fn and "satassume" not in fn


class M:
    depth = 0
    t0 = 0.0
    entry = None
    side = 0
    t = [0.0, 0.0, 0.0]   # interval seconds, [outside, inside, inside under an fn group]
    n_outer = [0, 0, 0]
    n_nested = [0, 0, 0]
    fn_state = None       # coarse.St in monfn
    wfn = None            # the function behind an outermost cacheit wrapper
    wt = {}               # (side, wrapped function) -> [calls, seconds]
    by = {}               # (side, code) -> [outer calls, seconds, nested calls]
    nested_now = 0
    callers = {}          # (side, caller code, entry code) -> calls
    any_depth = {}        # (side, qualname) -> calls of __new__, _eval_*, doit* at any depth
    want_callers = False
    unbalanced = 0


def mon_start():
    mon = sys.monitoring
    tid = 3
    mon.use_tool_id(tid, "rc")
    known = {}
    DISABLE = mon.DISABLE
    getframe = sys._getframe

    def sympy_code(code):
        r = known.get(code)
        if r is None:
            r = known[code] = is_sympy_file(code.co_filename)
        return r

    def start(code, offset):
        if not sympy_code(code):
            return DISABLE
        if M.depth == 0:
            M.side = 1 if B.depth else 0
            if M.side and M.fn_state is not None and M.fn_state.cur is not None:
                M.side = 2
            M.entry = code
            M.nested_now = 0
            M.wfn = None
            if code.co_name == "wrapper" and "cache.py" in code.co_filename:
                M.wfn = getattr(getframe(1).f_locals.get("func"), "__qualname__", "?")
            if M.want_callers:
                f = getframe(1).f_back
                k = (M.side, f.f_code if f else None, code)
                M.callers[k] = M.callers.get(k, 0) + 1
            M.depth = 1
            M.t0 = pc()
        else:
            M.depth += 1
            M.nested_now += 1
        if M.want_callers and (code.co_name == "__new__" or code.co_name.startswith(("_eval_", "doit"))):
            k = (M.side, code.co_qualname)
            M.any_depth[k] = M.any_depth.get(k, 0) + 1

    def leave(code, offset, ret):
        if not sympy_code(code):
            return DISABLE
        d = M.depth - 1
        if d == 0:
            dt = pc() - M.t0
            M.depth = 0
            s = M.side
            M.t[s] += dt
            M.n_outer[s] += 1
            M.n_nested[s] += M.nested_now
            k = (s, M.entry)
            r = M.by.get(k)
            if r is None:
                M.by[k] = [1, dt, M.nested_now]
            else:
                r[0] += 1
                r[1] += dt
                r[2] += M.nested_now
            if M.wfn is not None:
                w = M.wt.get((s, M.wfn))
                if w is None:
                    M.wt[(s, M.wfn)] = [1, dt]
                else:
                    w[0] += 1
                    w[1] += dt
        elif d > 0:
            M.depth = d
        else:
            M.unbalanced += 1

    def unwind(code, offset, exc):
        if sympy_code(code):
            leave(code, offset, None)

    def throw(code, offset, exc):
        if sympy_code(code):
            start(code, offset)

    E = mon.events
    mon.register_callback(tid, E.PY_START, start)
    mon.register_callback(tid, E.PY_RESUME, start)
    mon.register_callback(tid, E.PY_RETURN, leave)
    mon.register_callback(tid, E.PY_YIELD, leave)
    mon.register_callback(tid, E.PY_UNWIND, unwind)
    mon.register_callback(tid, E.PY_THROW, throw)
    mon.set_events(tid, E.PY_START | E.PY_RESUME | E.PY_RETURN | E.PY_YIELD | E.PY_UNWIND | E.PY_THROW)
    return tid


def mon_stop(tid):
    sys.monitoring.set_events(tid, 0)
    sys.monitoring.free_tool_id(tid)


def mon_calibrate():
    """Cost the monitoring adds to a no-op outermost call (seen by the interval and in
    all) and to a nested call. Fake functions compiled under a sympy/ file name, so the
    callbacks treat them as SymPy; the same functions unmonitored give the true cost."""
    src = ("def noop(self=None):\n    return None\n"
           "def nest(n, pc):\n    t = pc()\n    for _ in range(n):\n        noop()\n    return pc() - t\n")
    ns = {}
    exec(compile(src, "/fake/sympy/calib.py", "exec"), ns)
    noop, nest = ns["noop"], ns["nest"]
    N = 200_000

    def loop(n):
        t = pc()
        for _ in range(n):
            noop()
        return pc() - t

    def empty(n):
        t = pc()
        for _ in range(n):
            pass
        return pc() - t

    def med(f, *a):
        return sorted(f(*a) for _ in range(7))[3]

    plain_call = (med(loop, N) - med(empty, N)) / N
    plain_nest = med(nest, N, pc) / N
    tid = mon_start()
    M.t = [0.0, 0.0, 0.0]
    M.n_outer = [0, 0, 0]
    t_loop = med(loop, N)
    sum_iv = M.t[0] / (7 * N)
    t_nest = med(nest, N, pc)
    mon_stop(tid)
    M.depth = 0
    return dict(plain_call_ns=plain_call * 1e9, plain_nest_ns=plain_nest * 1e9,
                # all-in cost of a monitored outermost no-op call, net of the plain call
                outer_all_ns=((t_loop - med(empty, N)) / N - plain_call) * 1e9,
                # what the interval of a no-op sees, net of the plain call
                outer_iv_ns=(sum_iv - plain_call) * 1e9,
                # all-in cost of a monitored nested call, net of the plain call
                nested_all_ns=(t_nest / N - plain_nest) * 1e9)


# ---------------------------------------------------------------- sampler
class S:
    period = 0.000997
    q = 0
    log = []              # (query, inside the boundary?, entry code raw, entry code corrected)


def samp_start():
    import opcode
    RESUME = opcode.opmap["RESUME"]
    known = {}
    resumes = {}

    def outer_sympy(f):
        """The outermost SymPy frame of the stack, or None."""
        r = None
        while f is not None:
            c = f.f_code
            k = known.get(c)
            if k is None:
                k = known[c] = is_sympy_file(c.co_filename)
            if k:
                r = c
            f = f.f_back
        return r

    def handler(signum, frame):
        # safepoint bias: a signal is delivered at a RESUME, a back-edge or after a C
        # call. At a RESUME the frame has done nothing yet: the time was its caller's.
        # "raw" believes the delivered frame (thin callees over-counted), "corr" moves a
        # delivery at a RESUME to the caller (thin callees under-counted): they bracket.
        c = frame.f_code
        rs = resumes.get(c)
        if rs is None:
            b = c.co_code
            rs = resumes[c] = frozenset(i for i in range(0, len(b), 2) if b[i] == RESUME)
        raw = outer_sympy(frame)
        corr = outer_sympy(frame.f_back) if frame.f_lasti in rs else raw
        S.log.append((S.q, 1 if B.depth else 0, raw, corr))

    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, S.period, S.period)


def samp_stop():
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)


# ---------------------------------------------------------------- per query snapshots
snaps = []


def clock_b():
    snaps.append((B.inside, M.t[1], M.t[0], M.n_outer[1], M.n_nested[1], B.t_extra))
    return pc()


def clock_s():
    S.q = len(snaps) // 2
    snaps.append(None)
    return pc()


# ---------------------------------------------------------------- the run
extra = {}
clock = pc
mon_tid = None
if mode not in ("base", "dbl", "dblc"):
    wrap_boundary()
    clock = clock_b
if mode in ("fn", "monfn"):
    import coarse
    coarse.install(B, snaps, len(pairs))
    if mode == "monfn":
        M.fn_state = coarse.St
if mode == "enc":
    import encode
    encode.install(B, snaps, len(pairs))
if mode == "out":
    import outside
    outside.install(B, snaps, len(pairs))
if mode == "samp":
    S.period = float(os.environ.get("RC_PERIOD", S.period))
    clock = clock_s

gc.collect()
gc.freeze()
if mode in ("dbl", "dblc"):
    from sympy import Basic, Integer
    H = {"n": 0}
    orig_hash = (Basic.__hash__, Integer.__hash__)

    def layer(orig):
        if mode == "dbl":
            def h(self):
                return orig(self)
        else:
            def h(self):
                H["n"] += 1
                return orig(self)
        return h
    Basic.__hash__ = layer(orig_hash[0])
    Integer.__hash__ = layer(orig_hash[1])
if mode in ("mon", "moncall", "monfn"):
    M.want_callers = mode == "moncall"
    mon_tid = mon_start()
if mode == "samp":
    samp_start()
per = []
t = pc()
ans = ask_all(sympy_api.ask, pairs, clock, per)
T = pc() - t
if mode == "samp":
    samp_stop()
if mon_tid is not None:
    mon_stop(mon_tid)


def hot_hash():
    """ns per hash(e) with _mhash already set, net of hash(int): the floor of a thin call
    (hot code, no cache misses). Restores the original methods first."""
    from sympy import Symbol, sqrt
    Basic.__hash__, Integer.__hash__ = orig_hash
    x = Symbol("x")
    basics = [x + i for i in range(1000)] + [sqrt(x + i) for i in range(1000)]
    ints = [Integer(i + 10**6) for i in range(2000)]
    plain = list(range(10**7, 10**7 + 2000))
    keep = [hash(e) for e in basics + ints]

    def loop(xs):
        t = pc()
        for _ in range(200):
            for e in xs:
                hash(e)
        return (pc() - t) / (200 * len(xs))

    def med(xs):
        return sorted(loop(xs) for _ in range(7))[3] * 1e9
    p = med(plain)
    return dict(basic_ns=round(med(basics) - p, 1), integer_ns=round(med(ints) - p, 1), plain_ns=round(p, 1),
                _keep=len(keep))


def entry_name(c):
    return f"{c.co_filename.split('/sympy/')[-1]}:{c.co_qualname}"


def split(values):
    none = sum(v for v, r in zip(values, ans) if r is None)
    defi = sum(v for v, r in zip(values, ans) if r is not None)
    return {"none": round(none, 5), "def": round(defi, 5)}


out = dict(mode=mode, wl=wl, s=round(T, 4), n=len(ans), n_none=sum(r is None for r in ans),
           none_s=round(sum(d for d, r in zip(per, ans) if r is None), 4),
           def_s=round(sum(d for d, r in zip(per, ans) if r is not None), 4),
           digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16])
if mode not in ("base", "dbl", "dblc"):
    out["calls"] = B.calls
if mode == "dbl":
    out["hot"] = hot_hash()
if mode == "dblc":
    out["n_layer"] = H["n"]
if mode not in ("base", "samp", "dbl", "dblc"):
    d = [[b[i] - a[i] for a, b in zip(snaps[0::2], snaps[1::2])] for i in range(6)]
    out["inside"] = split(d[0])
    out["inside_s"] = round(B.inside, 5)
    if mode in ("mon", "moncall", "monfn"):
        out["t_side"] = [round(v, 5) for v in M.t]
        out["sym_in"] = split(d[1])
        out["sym_out"] = split(d[2])
        out["n_outer_in"] = split(d[3])
        out["n_nested_in"] = split(d[4])
        out["n_outer"] = list(M.n_outer)
        out["n_nested"] = list(M.n_nested)   # copied: mon_calibrate adds to this list
        out["unbalanced"] = M.unbalanced
        out["calib"] = mon_calibrate()
        out["wt"] = sorted(([s, n, r[0], round(r[1], 5)] for (s, n), r in M.wt.items()), key=lambda r: -r[3])
        out["by"] = sorted(
            ([s, f"{c.co_filename.split('/sympy/')[-1]}:{c.co_qualname}", r[0], round(r[1], 5), r[2]]
             for (s, c), r in M.by.items() if "/fake/" not in c.co_filename), key=lambda r: -r[3])
    if mode == "moncall":
        out["any_depth"] = sorted(([s, n, c] for (s, n), c in M.any_depth.items() if "noop" not in n), key=lambda r: -r[2])
        out["callers"] = sorted(
            ([s, (f"{f.co_filename.split('/satassume/')[-1]}:{f.co_qualname}" if f else "?"),
              f"{c.co_filename.split('/sympy/')[-1]}:{c.co_qualname}", n]
             for (s, f, c), n in M.callers.items() if "/fake/" not in c.co_filename), key=lambda r: -r[3])
if mode in ("fn", "monfn"):
    out["fn"] = coarse.report(ans)
if mode == "enc":
    out["enc"] = encode.report(ans)
if mode == "out":
    out["out"] = outside.report(ans)
if mode == "samp":
    tally = {}
    for q, side, raw, corr in S.log:
        k = ("none" if ans[q] is None else "def", side,
             entry_name(raw) if raw else "", entry_name(corr) if corr else "")
        tally[k] = tally.get(k, 0) + 1
    out["samples"] = [[*k, n] for k, n in sorted(tally.items(), key=lambda kv: -kv[1])]
    out["period"] = S.period
if ans_out:
    with open(ans_out, "w") as f:
        json.dump(ans, f)
print(json.dumps(out), flush=True)
