"""Fork-per-case regime: a slice of satsimp's refine battery
(``tests/refine_identities/battery_v3`` of satsimp 95c9340, every
EVERY-th case: 104 cases), each case in a child forked from a parent that
imported everything, preloaded the templates and ran the eval harness's
warm-up, as the assume-eval harness runs cases (after reteassume's
bench/cold_battery.py).  satsimp answers through satassume's ``ask``
(and falls back to SymPy's on None); ``ask_s`` is the time inside
satassume's ``ask``, ``refine_s`` the whole ``refine``.  Prints one JSON
line; ``--out`` writes each case's ``repr(refine(...))``.

    python -m evalbench.cold_battery [--out PATH]
"""
import argparse
import hashlib
import json
import os
import sys
import time

EVERY = 17


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--every", type=int, default=EVERY)
    args = ap.parse_args()
    sys.setrecursionlimit(10000)
    t0 = time.perf_counter()
    from sympy import Abs, Q, Symbol
    from sympy.core.cache import clear_cache
    import satsimp
    import satassume.sympy_api as mod
    from tests.refine_identities.battery_v3 import BATTERY
    reg = None
    try:
        from satassume.knowledge.templates import registry as reg
    except ImportError:
        pass
    if reg is not None and hasattr(reg, "load_all"):
        reg.load_all()
    W = Symbol('W')
    satsimp.refine(Abs(W), Q.positive(W))
    clear_cache()
    load_s = time.perf_counter() - t0
    cases = BATTERY[::args.every]
    tot = {"ask_s": 0.0, "asks": 0, "refine_s": 0.0, "ask_none": 0, "ask_none_s": 0.0}
    outs = []
    digest = hashlib.sha256()
    for expr, assum, _, _ in cases:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            acc = {"ask_s": 0.0, "asks": 0, "ask_none": 0, "ask_none_s": 0.0}
            f = mod.ask

            def ask(*x, **k):
                t = time.perf_counter()
                res = None
                try:
                    res = f(*x, **k)
                    return res
                finally:
                    dt = time.perf_counter() - t
                    acc["ask_s"] += dt
                    acc["asks"] += 1
                    if res is None:
                        acc["ask_none"] += 1
                        acc["ask_none_s"] += dt
            mod.ask = ask
            t = time.perf_counter()
            try:
                out = repr(satsimp.refine(expr, assum, strict=True))
            except Exception as e:  # noqa: BLE001
                out = "error " + type(e).__name__
            acc["refine_s"] = time.perf_counter() - t
            acc["out"] = out
            os.write(w, json.dumps(acc).encode())
            os._exit(0)
        os.close(w)
        data = b""
        while True:
            chunk = os.read(r, 1 << 16)
            if not chunk:
                break
            data += chunk
        os.close(r)
        os.waitpid(pid, 0)
        acc = json.loads(data) if data else {"out": "child died"}
        out = acc.pop("out")
        outs.append(out)
        digest.update(out.encode() + b"\n")
        for key, v in acc.items():
            tot[key] += v
    if args.out:
        with open(args.out, "w") as fh:
            for o in outs:
                fh.write(json.dumps(o) + "\n")
    print(json.dumps({"workload": "fork-battery", "cases": len(cases), "load_s": round(load_s, 3),
                      "satassume": os.path.dirname(mod.__file__).rsplit("/", 1)[0],
                      "digest": digest.hexdigest()[:16],
                      **{k: round(v, 5) if isinstance(v, float) else v for k, v in tot.items()}}))


if __name__ == "__main__":
    main()
