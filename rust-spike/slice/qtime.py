"""qtime.py WL MODE: one cold pass. MODE time: per-query seconds only. MODE sample: 0.5 ms sampler tagging each sample with the
query and the innermost satassume frame (part as in REPORT-rust-spike.md) and whether a SymPy frame is on the stack. Prints one JSON line.
SLICE_BACKEND=rust: `backend.install()` before the pass, with `sa_solver` taken from PYTHONPATH (step 5: full API or abi3). Unset: pure Python.
time also prints each answer, for the None and definite split."""
import collections, gc, hashlib, json, os, signal, sys, time
wl, mode = sys.argv[1:3]
from evalbench.common import workload
from satassume import sympy_api
so = None
if os.environ.get("SLICE_BACKEND") == "rust":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import backend, sa_solver
    backend.install()
    so = hashlib.sha256(open(sa_solver.__file__, "rb").read()).hexdigest()[:8]
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
cur = [-1]
samples = collections.Counter()
def handler(sig, frame):
    f = frame; own = None; sym = False
    while f is not None:
        fn = f.f_code.co_filename
        if own is None:
            i = fn.rfind("/satassume/")
            if i >= 0:
                own = (fn[i + 11:], f.f_code.co_qualname.split(".")[0])
        if "/sympy/" in fn:
            sym = True
        f = f.f_back
    samples[(cur[0], own[0] if own else "", own[1] if own else "", sym)] += 1
gc.collect(); gc.freeze()
if mode == "sample":
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.0005, 0.0005)
per = [0.0] * len(pairs); ans = [None] * len(pairs)
ask = sympy_api.ask
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
if mode == "sample":
    signal.setitimer(signal.ITIMER_REAL, 0)
d = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
print(json.dumps(dict(wl=wl, mode=mode, digest=d, s=total, so=so, per=per if mode == "time" else None, ans=ans if mode == "time" else None,
                      samples=[[*k, v] for k, v in samples.items()] if mode == "sample" else None)))
