"""crossing.py micro | real WL | samp WL: one cold process, JSON to stdout (issue 323 crossing costs).

micro  (a) Python into Rust and (b) Rust into Python, on no-op targets, against the same call from Python.
real   a live pass with sys.monitoring on SymPy __hash__ and __eq__ reached inside the boundary, keeping a sample of
       the real receivers. After the pass (c): hash, eq, intern and two reads, from Rust and from Python, on those
       objects. Monitoring slows the pass; the pass is not what is timed here.
samp   a live pass with a SIGALRM sampler that names the code each sample is in. Shares, not times.
"""
import gc
import hashlib
import json
import os
import signal
import statistics
import sys
import time

import xbench as X

pc = time.perf_counter
mode = sys.argv[1]
REPS = int(os.environ.get("XB_REPS", "7"))


def table(tests, reps=REPS):
    """Every test once per rep, in order, so neighbours alternate. First rep dropped. ns per unit, median."""
    out = {k: [] for k in tests}
    for r in range(reps + 1):
        for k, (f, units) in tests.items():
            v = f() / units * 1e9
            if r:
                out[k].append(v)
    return {k: round(statistics.median(v), 2) for k, v in out.items()}


# ---------------------------------------------------------------- micro
def py_empty(n):
    t = pc()
    for i in range(n):
        pass
    return pc() - t


def py_call0(f, n):
    t = pc()
    for i in range(n):
        f()
    return pc() - t


def py_call1(f, n):
    t = pc()
    for i in range(n):
        f(i)
    return pc() - t


def py_callb(f, b, n):
    t = pc()
    for i in range(n):
        f(b)
    return pc() - t


def py_callo(f, o, n):
    t = pc()
    for i in range(n):
        r = f(o)
        if r is not None and r:
            pass
    return pc() - t


def cb0():
    return None


def cb1(x):
    return x


def cbo(o):
    return None


class O:
    def m(self, x):
        return x

    def ask(self, b):
        return None


def micro():
    n = 400_000
    b132, b267, b538 = bytes(132), bytes(267), bytes(538)
    e, o = X.Eng(), O()
    tests = {
        "py_empty": (lambda: py_empty(n), n),
        # (a)
        "a_noop": (lambda: py_call0(X.a_noop, n), n),
        "a_noop_py": (lambda: py_call0(cb0, n), n),
        "a_int": (lambda: py_call1(X.a_int, n), n),
        "a_int_py": (lambda: py_call1(cb1, n), n),
        "a_bytes132": (lambda: py_callb(X.a_bytes, b132, n), n),
        "a_bytes267": (lambda: py_callb(X.a_bytes, b267, n), n),
        "a_bytes538": (lambda: py_callb(X.a_bytes, b538, n), n),
        "a_method267": (lambda: py_callb(e.ask, b267, n), n),
        "a_method267_py": (lambda: py_callb(o.ask, b267, n), n),
        # (b)
        "b_empty": (lambda: X.b_empty(n), n),
        "b_call0": (lambda: X.b_call0(cb0, n), n),
        "b_call1_int": (lambda: X.b_call1_int(cb1, n), n),
        "b_call1_obj": (lambda: X.b_call1_obj(cbo, o, n), n),
        "b_method": (lambda: X.b_method(o, n), n),
        "b_reattach": (lambda: X.b_reattach(cb1, n), n),
        "b_call0_py": (lambda: py_call0(cb0, n), n),
        "b_call1_py": (lambda: py_call1(cb1, n), n),
        "b_callo_py": (lambda: py_callo(cbo, o, n), n),
        "b_method_py": (lambda: py_call1(o.m, n), n),
    }
    if not X.ABI3:
        tests["b_raw"] = (lambda: X.b_raw(cb1, n), n)
    return dict(ns=table(tests))


# ---------------------------------------------------------------- a live pass
def load(wl):
    from evalbench.common import ask_all, workload
    from satassume import sympy_api
    if wl == "fuzz":
        from evalbench.fuzz import queries
        pairs = queries(424242)
    else:
        pairs = workload(wl)
    return ask_all, sympy_api, pairs


class B:
    depth = 0


def wrap_boundary():
    from satassume.engine import Engine
    for name in ("ask", "is_", "is_many", "verdict"):
        orig = getattr(Engine, name)

        def w(self, *a, _orig=orig, **k):
            if B.depth:
                return _orig(self, *a, **k)
            B.depth = 1
            try:
                return _orig(self, *a, **k)
            finally:
                B.depth = 0
        setattr(Engine, name, w)


def digest(ans):
    return hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- real objects
def py_loop(xs):
    t = pc()
    for x in xs:
        pass
    return pc() - t


def py_hash(xs):
    t = pc()
    for x in xs:
        hash(x)
    return pc() - t


def py_eq(xs, ys):
    t = pc()
    for x, y in zip(xs, ys):
        x == y
    return pc() - t


def py_zip(xs, ys):
    t = pc()
    for x, y in zip(xs, ys):
        pass
    return pc() - t


def py_intern(d, xs):
    t = pc()
    for x in xs:
        d[x]
    return pc() - t


def py_args(xs):
    t = pc()
    for x in xs:
        keep = list(x.args)
    return pc() - t


def py_isnum(xs):
    t = pc()
    for x in xs:
        if x.is_number:
            pass
    return pc() - t


def real(wl):
    ask_all, sympy_api, pairs = load(wl)
    wrap_boundary()
    stride = int(os.environ.get("XB_STRIDE_" + wl, "1"))
    H, EA, EB = [], [], []
    seen = dict(hash=0, eq=0)
    mon = sys.monitoring
    TOOL = 3
    DISABLE = mon.DISABLE
    getf = sys._getframe

    def start(code, offset):
        nm = code.co_name
        if nm != "__hash__" and nm != "__eq__" or "/sympy/" not in code.co_filename:
            return DISABLE
        if not B.depth:
            return None
        f = getf(1)
        if "/sympy/" in f.f_back.f_code.co_filename:   # outermost SymPy entries only, as in REPORT-rust-ceiling.md
            return None
        loc = f.f_locals
        vs = code.co_varnames
        if nm == "__hash__":
            seen["hash"] += 1
            if seen["hash"] % stride == 0:
                H.append(loc[vs[0]])
        else:
            seen["eq"] += 1
            EA.append(loc[vs[0]])
            EB.append(loc[vs[1]])
        return None

    mon.use_tool_id(TOOL, "xbench")
    mon.register_callback(TOOL, mon.events.PY_START, start)
    mon.set_events(TOOL, mon.events.PY_START)
    gc.collect()
    gc.freeze()
    ans = ask_all(sympy_api.ask, pairs)
    mon.set_events(TOOL, 0)
    mon.register_callback(TOOL, mon.events.PY_START, None)
    mon.free_tool_id(TOOL)

    # Distinct objects, keeping hash weight in H. Warm: every object has been hashed in the pass.
    D = list({id(o): o for o in H}.values())
    intern_d = {}
    for o in H:
        intern_d.setdefault(o, len(intern_d))
    R = [o for o in D if hasattr(o, "args") and hasattr(o, "is_number")]
    cold = [o for o in D if getattr(o, "_mhash", None) is not None]
    gc.collect()
    gc.freeze()

    def rs_cold():
        for o in cold:
            o._mhash = None
        return X.c_hash(cold)

    def py_cold():
        for o in cold:
            o._mhash = None
        return py_hash(cold)

    nh, ne, nr = len(H), max(len(EA), 1), max(len(R), 1)
    tests = {
        "py_loop": (lambda: py_loop(H), nh),
        "rs_walk": (lambda: X.c_walk(H), nh),
        "py_hash": (lambda: py_hash(H), nh),
        "rs_hash": (lambda: X.c_hash(H), nh),
        "py_zip": (lambda: py_zip(EA, EB), ne),
        "py_eq": (lambda: py_eq(EA, EB), ne),
        "rs_eq": (lambda: X.c_eq(EA, EB), ne),
        "py_intern": (lambda: py_intern(intern_d, H), nh),
        "rs_intern": (lambda: X.c_intern(intern_d, H), nh),
        "py_args": (lambda: py_args(R), nr),
        "rs_args": (lambda: X.c_args(R), nr),
        "py_isnum": (lambda: py_isnum(R), nr),
        "rs_isnum": (lambda: X.c_isnum(R), nr),
        "py_cold": (py_cold, max(len(cold), 1)),
        "rs_cold": (rs_cold, max(len(cold), 1)),
    }
    kinds = {}
    for o in H:
        n = type(o).__name__
        kinds[n] = kinds.get(n, 0) + 1
    top = sorted(kinds.items(), key=lambda kv: -kv[1])[:8]
    return dict(wl=wl, digest=digest(ans), seen=seen, kept=len(H), distinct=len(D), interned=len(intern_d),
                reads=len(R), cold=len(cold), eq=len(EA), eq_same=sum(a is b for a, b in zip(EA, EB)),
                kinds=top, ns=table(tests))


# ---------------------------------------------------------------- where a pass goes, by code
def place(fn):
    """A short name for a satassume file, or None for anything else."""
    i = fn.rfind("/satassume/")
    return fn[i + 11:] if i >= 0 else None


def samp(wl):
    ask_all, sympy_api, pairs = load(wl)
    wrap_boundary()
    log = []
    cur = [0]
    period = float(os.environ.get("XB_PERIOD", "0.0005"))

    def handler(signum, frame):
        f = frame
        leaf = frame.f_code
        own = None          # innermost satassume frame
        sym = False         # any SymPy frame on the stack
        while f is not None:
            fn = f.f_code.co_filename
            if own is None:
                p = place(fn)
                if p is not None:
                    own = (p, f.f_code.co_qualname)
            if "/sympy/" in fn:
                sym = True
            f = f.f_back
        lf = leaf.co_filename.rsplit("/", 1)[-1]
        log.append((cur[0], B.depth, sym, own, lf if lf != (own[0].rsplit("/", 1)[-1] if own else "") else ""))

    def clock():
        cur[0] += 1
        return pc()

    gc.collect()
    gc.freeze()
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, period, period)
    per = []
    ans = ask_all(sympy_api.ask, pairs, clock, per)
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    tally = {}
    for q, depth, sym, own, lf in log:
        idx = q // 2 if q % 2 == 0 else (q - 1) // 2
        c = "none" if ans[min(idx, len(ans) - 1)] is None else "def"
        k = f"{c}|{depth}|{int(sym)}|{own[0] if own else ''}|{own[1] if own else ''}|{lf}"
        tally[k] = tally.get(k, 0) + 1
    return dict(wl=wl, digest=digest(ans), period=period, samples=len(log), tally=tally)


if mode == "micro":
    out = micro()
elif mode == "real":
    out = real(sys.argv[2])
else:
    out = samp(sys.argv[2])
out.update(mode=mode, abi3=bool(X.ABI3))
print(json.dumps(out), flush=True)
