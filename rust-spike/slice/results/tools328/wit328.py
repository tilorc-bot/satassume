"""wit328.py WL MODE (sa-port-328, issue 323): one cold pass over a workload with the witness check counted and timed.

WL: dev, fuzz (seed 424242) or any evalbench workload. MODE: py (the package alone) or rust (what qt195.py installs for
`rust`: the slice's backend; SLICE_CONVERT and SLICE_TERM_FRAMES pick the Rust switches). SLICE_WITNESS=1 turns the
check on, SLICE_WITNESS_CAP its cap (satassume/witness.py). The counting lives here, in the driver's process, by wrapping
`witness.witnesses` and `witness._pools`: the package keeps no counter. Prints one JSON line:
  s          seconds over all asks (includes this wrapper's two clock reads per check, so not an S1 time; S1 is qt195.py)
  digest     of the answers, as qt195.py computes it
  fires      calls of the check; compiled: those whose formula compiled (a point search ran); certified: pairs found
  check_s    seconds inside the check, total; check_us: median, 90%, 99%, max per call in microseconds
  tried      points tried per certified query: median, 90%, max
  cert_ids   the query indices certified;  ans, per: answers and seconds per query
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
    pairs = queries(424242)
else:
    pairs = workload(wl)
pc = time.perf_counter
calls = []          # (query index, seconds, certified, points tried)
compiled = [0]
cur = [0]
real_w, real_p = witness.witnesses, witness._pools


def witnesses(p, a, eng=None):
    t = pc()
    r = real_w(p, a, eng)
    calls.append((cur[0], pc() - t, r is not None, r[3] if r is not None else 0))
    return r


def pools(q, owns):
    compiled[0] += 1
    return real_p(q, owns)


witness.witnesses, witness._pools = witnesses, pools
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


us = [round(c[1] * 1e6, 1) for c in calls]
tr = [c[3] for c in calls if c[2]]
print(json.dumps(dict(
    wl=wl, mode=mode, so=so, n=len(pairs), s=total, digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
    witness=witness.ENABLED[0], cap=witness.CAP[0], plant=witness.PLANT[0],
    convert=os.environ.get("SLICE_CONVERT", "py"), frames=os.environ.get("SLICE_TERM_FRAMES", "py"),
    fires=len(calls), compiled=compiled[0], certified=len(tr), check_s=sum(c[1] for c in calls),
    check_us=[q(us, .5), q(us, .9), q(us, .99), max(us) if us else None],
    check_us_cert=q([round(c[1] * 1e6, 1) for c in calls if c[2]], .5),
    check_us_fall=q([round(c[1] * 1e6, 1) for c in calls if not c[2]], .5),
    tried=[q(tr, .5), q(tr, .9), max(tr) if tr else None],
    cert_s_off=None, cert_ids=[c[0] for c in calls if c[2]], ans=ans, per=per)))
