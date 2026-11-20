"""prof356.py WL MODE cprof (sa-port-356, issue 323; tools350/prof350.py's driver and its cprof kind, for the whole pass):
one cold pass over a workload under cProfile, to count the Python still running on the Rust path by file.

WL: dev, fuzz (seed 424242), budget, wiring (the slice's own) or an evalbench workload. MODE: py (the package alone) or
rust (the slice's backend; the environment picks the switches). Per file (satassume/X.py, slice/X.py, sympy as one
group, stdlib:X): calls, tottime (own bytecode), the built-in calls it makes directly split into sa_solver's (Rust) and
the rest, and inclusive time from the caller edges (calls entering the file from another one).
cProfile charges every call and sees no Rust entered through a slot (tp_call, tp_hash callbacks), so these are
call-weighted ratios and call counts, not wall-time shares: the shares are the sampler's (ana356.py). `plain` runs
the pass with nothing added. Prints one JSON line. Not an S1 time (S1 is qt342.py).
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
_names = {}


def fkey(f):
    """A file's group: satassume/X.py, slice/X.py, sympy (one group: SymPy's own code), evalbench, the driver, stdlib."""
    k = _names.get(f)
    if k is None:
        p = f.replace("\\", "/")
        if p == "~":
            k = "builtins"
        elif "/satassume/" in p:
            k = "satassume/" + p.rsplit("/", 1)[1]
        elif "/rust-spike/slice/" in p:
            k = "slice/" + p.rsplit("/", 1)[1]
        elif "/sympy/" in p:
            k = "sympy"
        elif "/evalbench/" in p or p.endswith("_wl.py"):
            k = "evalbench"
        elif p.endswith("prof356.py"):
            k = "driver"
        else:
            k = "stdlib:" + p.rsplit("/", 1)[-1]
        _names[f] = k
    return k


prof = None
if kind == "cprof":
    import cProfile
    prof = cProfile.Profile()
ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
gc.freeze()
if prof is not None:
    prof.enable()
t0 = pc()
for i, (p, a) in enumerate(pairs):
    try:
        r = ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    ans[i] = r
total = pc() - t0
if prof is not None:
    prof.disable()
wn = sys.modules.get("witness_live")
out = dict(
    wl=wl, mode=mode, kind=kind, so=so, n=len(pairs), s=total,
    digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=witness.ENABLED[0], native=getattr(witness, "NATIVE", [None])[0] is not None, loaded_wn=wn is not None,
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"))
r4 = lambda d: {k: round(v, 5) for k, v in sorted(d.items(), key=lambda x: -x[1])}
if prof is not None:
    import pstats
    st = pstats.Stats(prof).stats
    by, calls, nat, rust, inc, fn, bn = {}, {}, {}, {}, {}, {}, {}
    for (f, line, name), (cc, nc, tt, ct, callers) in st.items():
        k = fkey(f)
        if k == "builtins":
            is_rust = "sa_solver" in name
            bn[name] = (round(tt, 5), nc)
            for (cf, cl, cn), (enc, ecc, ett, ect) in callers.items():
                ck = fkey(cf)
                d = rust if is_rust else nat
                d[ck] = d.get(ck, 0.0) + ett
            continue
        by[k] = by.get(k, 0.0) + tt
        calls[k] = calls.get(k, 0) + nc
        fn["%s:%s:%d" % (k, name, line)] = (round(tt, 5), nc)
        for (cf, cl, cn), (enc, ecc, ett, ect) in callers.items():
            if fkey(cf) != k:
                inc[k] = inc.get(k, 0.0) + ect
    tot = sum(by.values()) + sum(nat.values()) + sum(rust.values())
    out.update(cprof_total=round(tot, 5), cprof_own=r4(by), cprof_calls=dict(sorted(calls.items(), key=lambda x: -x[1])),
               cprof_native=r4(nat), cprof_rust=r4(rust), cprof_incl=r4(inc),
               cprof_builtins=dict(sorted(bn.items(), key=lambda x: -x[1][0])[:50]),
               cprof_top=dict(sorted(fn.items(), key=lambda x: -x[1][0])[:80]))
print(json.dumps(out))
