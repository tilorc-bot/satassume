"""memo_trace.py WL MODE [--limit N] [--passes P]: step 5c9a's per-query trace of the memo registry rows.

Counts every Python call into satassume/state/memos.py, satassume/state/epoch.py and the Engine settings properties
(extensions .. templates, getters and setters) while WL runs, by callee and caller. A caller frame whose code does not
name the callee (``co_names``) called it through C: on MODE rust that is a Rust callback, shown as ``<-C(file:func)``.
MODE py runs Python's backend (nothing installed), MODE rust installs as ``live.py WL rust --check plain`` does.
Before each pass after the first, PROCESS and the default engine's memos are emptied without an epoch bump, as
registry_count.py does, so the repeat runs the per-query code again.
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SETTINGS = {"extensions", "relation_specs", "discovery_budget", "transfer", "uninterpreted", "writeback",
            "relevance", "templates", "_settings_changed"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wl")
    ap.add_argument("mode", choices=["py", "rust"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--passes", type=int, default=1)
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
    import satassume.state.memos as M
    import satassume.state.epoch as E
    import satassume.engine as EN
    from live import load
    files = {os.path.abspath(M.__file__): "memos", os.path.abspath(E.__file__): "epoch"}
    eng_file = os.path.abspath(EN.__file__)
    counts = collections.Counter()
    cur = [0]

    def prof(frame, event, arg):
        if event != "call":
            return
        co = frame.f_code
        fn = co.co_filename
        tag = files.get(fn)
        if tag is None:
            if fn != eng_file or co.co_name not in SETTINGS or not co.co_qualname.startswith("Engine."):
                return
            tag = "engine"
        b = frame.f_back
        if b is None:
            who = "?"
        else:
            bco = b.f_code
            where = f"{os.path.basename(bco.co_filename)}:{bco.co_name}"
            direct = co.co_name in bco.co_names or (tag == "memos" and os.path.abspath(bco.co_filename) == fn)
            who = where if direct else f"C({where})"
        counts[f"pass{cur[0]}\t{tag}:{co.co_qualname}\t<-{who}"] += 1

    pairs = load(args.wl)
    if args.limit:
        pairs = pairs[:args.limit]
    bad = 0
    for p in range(1, args.passes + 1):
        cur[0] = p
        if p > 1:
            M.PROCESS.clear()
            sympy_api.default_engine().memos.clear()
        sys.setprofile(prof)
        for prop, assum in pairs:
            try:
                sympy_api.ask(prop, assum)
            except Exception:
                bad += 1
        sys.setprofile(None)
    print(f"{args.wl} {args.mode}: {len(pairs)} queries x {args.passes}, {bad} raised")
    for k in sorted(counts):
        print(f"{k}\t{counts[k]}")


if __name__ == "__main__":
    main()
