"""registry_count.py WL [--passes 2] [--limit N]: the planner's count checks for registry.py and templates/__init__.py.

Runs WL (dev by default) PASSES times in one process on the Rust backend, installed as `live.py WL rust --check plain` does,
and counts per pass: registry `_load`, `_covers`, `register`, and `_may_be_nan` by its caller (file:function, first
frame outside templates/__init__.py, so its own recursion is folded into the caller). The ruling: on the second pass
`_load` and `_covers` count 0; `_may_be_nan`'s only per-query caller is convert.py. Before each pass after the first,
the process memos and the default engine's memos are emptied without an epoch bump, so the repeat runs the per-query
code again instead of reading answers back.

SLICE_PLANT_COUNT=1 calls each wrapped function once before the first pass, so the counters are shown to fire.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wl", nargs="?", default="dev")
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--trace", help="comma-separated file basenames under knowledge/templates: count every Python call "
                    "into them per pass (sys.setprofile), by function and caller file")
    args = ap.parse_args()

    import p_install
    p_install.install()
    # live.py's --check plain on rust: the default Rust backend, as a user runs it
    import backend
    backend.install_euf()
    import term_live, lra_live, session_live, knowledge_live
    term_live.from_env()
    lra_live.from_env()
    session_live.from_env()
    knowledge_live.from_env()
    backend.install()
    from satassume import sympy_api
    from satassume.knowledge import templates as TP
    RG = sys.modules["satassume.knowledge.templates.registry"]
    from live import load

    counts = collections.Counter()
    cur = [0]
    init = os.path.abspath(TP.__file__)

    def wrap(owner, name, static=False, by_caller=False):
        real = owner.__dict__[name]
        fn = real.__func__ if static else real

        def counted(*a, **k):
            key = f"pass{cur[0]}:{name}"
            if by_caller:
                f = sys._getframe(1)
                while f is not None and (os.path.abspath(f.f_code.co_filename) == init or f.f_code is counted.__code__):
                    f = f.f_back
                where = "?" if f is None else f"{os.path.basename(f.f_code.co_filename)}:{f.f_code.co_name}"
                key += f"<-{where}"
                if f is not None and f.f_code.co_name == "clauses_for":      # Python's, the user path: which class
                    e = f.f_locals.get("expr")
                    ts = RG.registry.templates_for(type(e)) if hasattr(RG, "registry") else []
                    key += f"[{type(e).__name__}: " + ",".join(f"{t.__module__}:{t.__qualname__}" for t in ts) + "]"
            counts[key] += 1
            return fn(*a, **k)
        setattr(owner, name, staticmethod(counted) if static else counted)
        return counted

    TR = RG.TemplateRegistry
    wrap(TR, "_covers", static=True)
    wrap(TR, "_load")
    wrap(TR, "register")
    # `_may_be_nan` is imported by name into convert.py and term_shadow.py: rebind it there too
    orig = TP._may_be_nan
    mbn = wrap(TP, "_may_be_nan", by_caller=True)

    def rebind():
        for m in list(sys.modules.values()):
            if m is not None and m is not TP and getattr(m, "_may_be_nan", None) is orig:
                m._may_be_nan = mbn
                counts[f"rebound:{m.__name__}"] = 1
    rebind()

    if os.environ.get("SLICE_PLANT_COUNT"):
        from sympy import Symbol
        TR._covers(int, (int,))
        TP._may_be_nan(Symbol("x"))
        print("plant:", dict(counts))
        counts.clear()

    pairs = load(args.wl)
    if args.limit:
        pairs = pairs[:args.limit]
    traced = set((args.trace or "").split(",")) - {""}
    tdir = os.path.dirname(init)

    def prof(frame, event, arg):
        if event != "call":
            return
        co = frame.f_code
        fn = co.co_filename
        if os.path.dirname(fn) == tdir and os.path.basename(fn) in traced:
            b = frame.f_back
            who = "?" if b is None else os.path.basename(b.f_code.co_filename)
            counts[f"pass{cur[0]}:trace:{os.path.basename(fn)}:{co.co_qualname}<-{who}"] += 1
    if traced:
        sys.setprofile(prof)
    for p in range(1, args.passes + 1):
        cur[0] = p
        rebind()
        if p > 1:       # every query memo emptied (no epoch bump: the registry's lazy state and class caches stay)
            from satassume.state.memos import PROCESS
            PROCESS.clear()
            sympy_api.default_engine().memos.clear()
        bad = 0
        for prop, assum in pairs:
            try:
                sympy_api.ask(prop, assum)
            except Exception:
                bad += 1
        d = knowledge_live.DISPATCH[0]
        dc = d.counts() if d is not None else {}
        print(f"pass {p}: {len(pairs)} queries, {bad} raised; dispatch",
              {k: v for k, v in sorted(dc.items()) if "python" in k or "plant" in k}, flush=True)
        if d is not None:
            d.clear_counts()
    print("dispatch installed:", knowledge_live.installed(), "COUNTS:",
          {k: v for k, v in knowledge_live.COUNTS.items() if k.startswith(("registry", "fault"))})
    print("convert in sys.modules:", "convert" in sys.modules,
          getattr(sys.modules.get("convert"), "_may_be_nan", None) is mbn)
    for k in sorted(counts):
        print(f"{k}\t{counts[k]}")


if __name__ == "__main__":
    main()
