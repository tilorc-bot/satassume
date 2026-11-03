"""Replay one workload in this (cold) process; prints one JSON line.

    python -m evalbench.replay WORKLOAD [--answers OUT] [--counters] [--phases]

Run it through ``evalbench.run`` (or with PYTHONPATH = checkout, SymPy pin,
sa-eval root, and PYTHONHASHSEED=0).  The timed loop runs after the imports
and ``gc.collect(); gc.freeze()``; garbage collection stays enabled (as in a
SymPy session).  ``seconds`` is the loop's wall time; ``none_s``/``def_s``
split it by this run's answer (None vs anything else; ``err_s``: raised).
With ``--counters``/``--phases`` the wrappers add overhead: use those runs
for counts and shares, not for absolute time.
"""
import argparse
import gc
import hashlib
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workload")
    ap.add_argument("--answers")
    ap.add_argument("--counters", action="store_true")
    ap.add_argument("--phases", action="store_true")
    ap.add_argument("--profile", help="cProfile the timed loop into this file")
    args = ap.parse_args()
    sys.setrecursionlimit(10000)
    t0 = time.perf_counter()
    from evalbench.common import workload, ask_all
    pairs = workload(args.workload)
    import satassume
    from satassume import sympy_api
    t_load = time.perf_counter() - t0
    col = None
    if args.counters or args.phases:
        from evalbench.instrument import install
        ask, col = install(phases=args.phases, counters=args.counters)
        c0 = col.snapshot()
    else:
        ask = sympy_api.ask
    clock = time.perf_counter
    per = []
    gc.collect()
    gc.freeze()
    pr = None
    if args.profile:
        import cProfile
        pr = cProfile.Profile()
        pr.enable()
    t = clock()
    ans = ask_all(ask, pairs, clock, per)
    secs = clock() - t
    if pr is not None:
        pr.disable()
        pr.dump_stats(args.profile)
    out = {"workload": args.workload, "n": len(pairs), "seconds": round(secs, 5),
           "load_s": round(t_load, 3), "satassume": os.path.dirname(os.path.dirname(satassume.__file__))}
    for cls in ("none", "def", "err"):
        sel = [d for d, r in zip(per, ans) if (r is None if cls == "none" else
                                                isinstance(r, str) if cls == "err" else
                                                r is True or r is False)]
        out["n_" + cls], out[cls + "_s"] = len(sel), round(sum(sel), 5)
    out["digest"] = hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16]
    if col is not None:
        c1 = col.snapshot()
        out["counters"] = {k: c1[k] - c0.get(k, 0) for k in sorted(c1)}
        if col.phases is not None:
            out["phases"] = {k: round(v, 5) for k, v in sorted(col.phases.acc.items())}
        out["missing"] = col.missing
    if args.answers:
        with open(args.answers, "w") as f:
            for r in ans:
                f.write(json.dumps(r) + "\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
