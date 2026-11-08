"""memo_check.py WL MODE OUT.json [--limit N]: step 5c9a's registry check on one backend.

Runs WL once (MODE py: Python's backend; MODE rust: installed as `live.py WL rust --check plain`), then writes:
- `answers`: a hash of every answer, in order;
- `digest`: the snapshot digest of everything Python can read from the registry that both backends have: per memo of
  `memos.PROCESS` and of the default engine's `Engine.memos` that isn't a native view, (name, key, len, stamp); the
  per-table rows go in `tables`, so a difference names its table;
- MODE rust only: `native`, the views' (name, key, size, len) from `PROCESS.items()`, and `snapshot`, the same read from
  the Rust maps (`sa_solver.memo_snapshot`, test-only); `view_ok` is whether the two agree;
- `cleared`: after one `PROCESS.clear()` and `Engine.memos.clear()`, the memos still non-empty (views and maps), which
  must be none; then the first 200 queries run again and `rerun_same` says whether their answers equal the first pass's.
`memo_check.py --cmp PY.json RUST.json` prints MATCH or each difference, and exits 1 on any.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _h(x):
    return hashlib.sha256(repr(x).encode()).hexdigest()[:16]


def registry_rows(engine):
    from satassume.state import memos
    rows = []
    for owner, m in (("process", memos.PROCESS), ("engine", engine.memos)):
        for name, key, c in m.items():
            if getattr(c, "native", False):
                continue
            stamp = getattr(c, "stamp", None)
            rows.append((owner, name, key, len(c), repr(stamp)))
    return sorted(rows)


def main():
    if sys.argv[1] == "--cmp":
        a, b = (json.load(open(f)) for f in sys.argv[2:4])
        bad = []
        for k in ("answers", "digest", "rerun_same"):
            if a.get(k) != b.get(k):
                bad.append(f"{k}: {a.get(k)} != {b.get(k)}")
        if a.get("digest") != b.get("digest"):
            ta = {tuple(r[:3]): r[3:] for r in a["tables"]}
            tb = {tuple(r[:3]): r[3:] for r in b["tables"]}
            for k in sorted(set(ta) | set(tb)):
                if ta.get(k) != tb.get(k):
                    bad.append(f"  table {k}: {ta.get(k)} != {tb.get(k)}")
        for f, d in ((sys.argv[2], a), (sys.argv[3], b)):
            if d.get("view_ok") is False:
                bad.append(f"{f}: view != snapshot: {d['native']} vs {d['snapshot']}")
            if d.get("cleared"):
                bad.append(f"{f}: not empty after clear: {d['cleared']}")
        print("MATCH" if not bad else "DIFF\n" + "\n".join(bad))
        sys.exit(1 if bad else 0)
    wl, mode, out = sys.argv[1:4]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    if mode == "rust":
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
    from satassume.state import memos
    from live import load
    pairs = load(wl)
    if limit:
        pairs = pairs[:limit]

    def run(ps):
        res = []
        for prop, assum in ps:
            try:
                res.append(repr(sympy_api.ask(prop, assum)))
            except Exception as e:
                res.append(f"raise {type(e).__name__}")
        return res
    ans = run(pairs)
    eng = sympy_api.default_engine()
    rows = registry_rows(eng)
    r = dict(wl=wl, mode=mode, n=len(pairs), answers=_h(ans), digest=_h(rows), tables=rows)
    if mode == "rust" and hasattr(__import__("sa_solver"), "memo_snapshot"):
        import sa_solver
        r["native"] = sorted((n, c.key, c.size, len(c)) for n, _, c in memos.PROCESS.items() if getattr(c, "native", False))
        r["snapshot"] = sorted(list(t) for t in sa_solver.memo_snapshot())
        r["native"] = [list(t) for t in r["native"]]
        r["view_ok"] = r["native"] == r["snapshot"]
    memos.PROCESS.clear()
    eng.memos.clear()
    left = [n for n, _, c in list(memos.PROCESS.items()) + list(eng.memos.items()) if len(c)]
    if "snapshot" in r:
        left += [f"map:{t[0]}" for t in sa_solver.memo_snapshot() if t[3]]
    r["cleared"] = left
    r["rerun_same"] = run(pairs[:200]) == ans[:200]
    json.dump(r, open(out, "w"), indent=0)
    print(json.dumps({k: v for k, v in r.items() if k != "tables"}))


if __name__ == "__main__":
    main()
