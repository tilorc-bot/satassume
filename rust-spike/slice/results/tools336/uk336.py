"""uk336.py WL MODE (sa-port-336, issue 323; the setup is tools328/wit328.py's): what `witness._users_knowledge` costs per
certified call. One cold pass over a workload with SLICE_WITNESS=1; only `_users_knowledge` is wrapped (two clock reads a
call), in the driver's process. It is asked last, so it is called once per query that would be certified. Prints one JSON
line: calls, total seconds inside it, per call in microseconds (median, 90%, max), the templates it scans at the end of the
pass (classes, templates, lazy entries, relation specs), and a second measure with no wrapper: the same engine asked
20000 times after the pass (bare_us, the minimum of 5 repeats, per call). Not an S1 time."""
import gc, hashlib, json, os, sys, time, timeit
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
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
calls, engs = [], []
real = witness._users_knowledge


def users_knowledge(eng):
    t = pc()
    r = real(eng)
    calls.append(pc() - t)
    if not engs:
        engs.append(eng)
    return r


witness._users_knowledge = users_knowledge
ans = [None] * len(pairs)
ask = sympy_api.ask
gc.collect()
gc.freeze()
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
us = sorted(round(c * 1e6, 2) for c in calls)
q = lambda f: us[min(len(us) - 1, int(f * len(us)))] if us else None
bare = scan = None
if engs:
    eng = engs[0]
    reg = getattr(eng._templates, "__self__", None)
    scan = dict(classes=len(reg._by_class), templates=sum(len(v) for v in reg._by_class.values()), lazy=len(reg._lazy),
                relation_specs=len(eng._relation_specs), result=real(eng))
    bare = round(min(timeit.repeat(lambda: real(eng), number=20000, repeat=5)) / 20000 * 1e6, 3)
print(json.dumps(dict(
    wl=wl, mode=mode, so=so, n=len(pairs), s=total, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=witness.ENABLED[0], cap=witness.CAP[0], calls=len(calls), total_s=sum(calls), us=[q(.5), q(.9), us[-1] if us else None],
    scan=scan, bare_us=bare, stats_certified=engs[0].stats.get("witness_certified") if engs else None)))
