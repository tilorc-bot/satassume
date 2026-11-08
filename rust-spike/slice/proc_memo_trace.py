"""proc_memo_trace.py WL MODE [--limit N]: step 5c9b's per-query trace of the process memos Rust works on.

Counts every Python call of engine.py's `want_of`, `_split`, `neighbourhood` and relations.py's `closed_units`,
`with_closed_units`, `sympy_atom` while WL runs, by caller (``<-C(file:func)`` when the caller's code does not name the
callee: a Rust callback), and on MODE rust the Rust counters of the same functions (`session_counts`). Also the sizes of
the five containers after the run.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGETS = {"engine.py": {"want_of", "_split", "neighbourhood"},
           "relations.py": {"closed_units", "with_closed_units", "sympy_atom"}}
RUST = ["ses:want_of", "ses:split", "rel:sympy_atom", "rel:closed_units", "rel:cb_sympy_q", "rel:cb_closed_sign"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wl")
    ap.add_argument("mode", choices=["py", "rust"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.mode == "rust":
        import p_install
        p_install.install()
        import backend
        backend.install_euf()
        import term_live, lra_live, session_live, knowledge_live
        term_live.from_env()
        lra_live.from_env()
        session_live.from_env()
        knowledge_live.from_env()
        backend.install()
    from satassume import sympy_api
    import satassume.engine as EN
    import satassume.relations as RE
    from live import load
    files = {os.path.abspath(EN.__file__): "engine.py", os.path.abspath(RE.__file__): "relations.py"}
    counts = collections.Counter()

    def prof(frame, event, arg):
        if event != "call":
            return
        co = frame.f_code
        tag = files.get(co.co_filename)
        if tag is None or co.co_name not in TARGETS[tag]:
            return
        b = frame.f_back
        if b is None:
            who = "?"
        else:
            bco = b.f_code
            where = f"{os.path.basename(bco.co_filename)}:{bco.co_name}"
            who = where if co.co_name in bco.co_names else f"C({where})"
        counts[f"py\t{tag}:{co.co_qualname}\t<-{who}"] += 1

    pairs = load(args.wl)
    if args.limit:
        pairs = pairs[:args.limit]
    c0 = {}
    if args.mode == "rust":
        import sa_solver
        c0 = dict(sa_solver.session_counts())
    bad = 0
    sys.setprofile(prof)
    for prop, assum in pairs:
        try:
            sympy_api.ask(prop, assum)
        except Exception:
            bad += 1
    sys.setprofile(None)
    print(f"{args.wl} {args.mode}: {len(pairs)} queries, {bad} raised")
    for k in sorted(counts):
        print(f"{k}\t{counts[k]}")
    if args.mode == "rust":
        c1 = dict(sa_solver.session_counts())
        for n in RUST:
            if n in c1:
                print(f"rust\t{n}\t{c1[n] - c0.get(n, 0)}")
    from satassume.state import memos
    sz = memos.PROCESS.sizes()
    for n in ("satassume.engine._WANT", "satassume.engine._SPLIT", "satassume.engine._NEIGH",
              "satassume.relations._CLOSED", "satassume.relations._SYMPY_ATOMS"):
        print(f"size\t{n}\t{sz.get(n)}")


if __name__ == "__main__":
    main()
