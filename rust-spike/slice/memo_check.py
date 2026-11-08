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
- step 5c9c: `em_sizes`, `em_content` and `em_order` of the five engine memos moved to Rust (`ENGMEMOS`), and on Rust
  `em_view_bad`, the maps whose view differs from `sa_solver.em_snapshot` (test-only).
- step 5c10a: the fact caches' stores (`cache.store`, `custom_cache.store`) join `em_sizes`, `em_content` and `em_order` (each
  node's facts in their insertion order), and on Rust `fc_view_bad`, the caches whose view differs from `sa_solver.fc_snapshot`.
`memo_check.py --cmp PY.json RUST.json` prints MATCH or each difference, and exits 1 on any.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _h(x):
    return hashlib.sha256(repr(x).encode()).hexdigest()[:16]


#: Step 5c9c: the engine memos moved to Rust (engmemo.rs); their contents go in `em_content` (sorted, hash-seed free) and
#: `em_order` (insertion order: compare under one PYTHONHASHSEED).
#: Step 5c10b: `_failed`, `_verdict`, `_context_sessions` (context.rs; engmemo slots 5-7) join them.
CTXMEMOS = ("_failed", "_verdict", "_context_sessions")
#: Step 5c10c: `_cones` and `_constructing` (budget.rs cone rows; engmemo slots 8-9) join them (`_constructing` holds `None` values).
CONEMEMOS = ("_cones", "_constructing")
ENGMEMOS = ("_kids", "_qcones", "_glue_adapters", "_xbasis", "splits") + CTXMEMOS + CONEMEMOS


def _canon(x):
    """A repr that doesn't depend on set order or object identity: sets sorted, `Split`s by their getters."""
    if isinstance(x, (set, frozenset)):
        return "{" + ", ".join(sorted(_canon(y) for y in x)) + "}"
    if isinstance(x, tuple):
        return "(" + ", ".join(_canon(y) for y in x) + ")"
    if isinstance(x, list):
        return "[" + ", ".join(_canon(y) for y in x) + "]"
    if type(x) is object:      # a bare sentinel (`splits` keys): its repr carries an address
        return "<object>"
    if type(x).__name__ in ("Split", "_Split"):
        return "Split" + _canon((x.whole, tuple(x.conjuncts), x.opaque, x.relational, x.keyless,
                                 [(frozenset(k), tuple(i)) for k, i in x.comps], x.consistent, x.vocab))
    return repr(x)


def engmemo_rows(engine):
    """Per moved memo: (name, rows in insertion order); an adapter value by its type's name."""
    out = []
    for n in ENGMEMOS:
        c = getattr(engine, n)
        glue = n == "_glue_adapters"
        if n == "_constructing":    # a set on Python, a map to None on Rust (5c10c): its members, sorted (a set's order isn't read)
            out.append((n, sorted((_canon(k), "None") for k in list(c))))
            continue
        out.append((n, [(_canon(k), type(v).__name__ if glue else _canon(v)) for k, v in list(c.items())]))
    return out


#: Step 5c10a: the fact caches moved to Rust (factcache.rs), by their registry names.
FACTCACHES = ("cache", "custom_cache")


def factcache_rows(engine):
    """Per fact cache: ("<name>.store", rows in insertion order, each node's facts in theirs)."""
    return [(n + ".store", [(_canon(k), [(p, repr(v)) for p, v in f.items()]) for k, f in list(getattr(engine, n).store.items())])
            for n in FACTCACHES]


def factcache_view_ok(engine):
    """Rust only: each cache's view holds the same nodes, facts and order as `fc_snapshot` reads from the store, and the same
    `maxsize`, `_epoch`, `_settings`."""
    import sa_solver
    bad = []
    for n in FACTCACHES:
        c = getattr(engine, n)
        if type(c).__module__ != "sa_solver":
            bad.append(f"{n}: {type(c).__module__}.{type(c).__name__}")
            continue
        maxsize, epoch, settings, rows = sa_solver.fc_snapshot(c)
        view = list(c.store.items())
        if maxsize != c.maxsize or epoch != c._epoch or settings is not c._settings or len(rows) != len(view) or any(
                a[0] is not b[0] or list(b[1].items()) != a[1] for a, b in zip(rows, view)):
            bad.append(n)
    return bad


def engmemo_view_ok(engine):
    """Rust only: each map's view (`items()`) holds the same objects, in the same order, as `em_snapshot` reads from the map."""
    import sa_solver
    bad = []
    for n in ENGMEMOS:
        c = getattr(engine, n)
        if n in CTXMEMOS and not __import__("session_live").context_native():
            continue
        if n in CONEMEMOS and not getattr(__import__("session_live"), "cones_native", lambda: False)():
            continue
        if type(c).__name__ != "EngineMemo":
            bad.append(f"{n}: {type(c).__name__}")
            continue
        name, maxsize, rows = sa_solver.em_snapshot(c)
        view = list(c.items())
        if name != n or maxsize != c.maxsize or len(rows) != len(view) or any(
                a[0] is not b[0] or a[1] is not b[1] for a, b in zip(rows, view)):
            bad.append(n)
    return bad


def registry_rows(engine):
    from satassume.state import memos
    rows = []
    for owner, m in (("process", memos.PROCESS), ("engine", engine.memos)):
        for name, key, c in m.items():
            if getattr(c, "native", False) and not getattr(c, "moved", False):     # 5c9b's moved memos count
                continue
            stamp = getattr(c, "stamp", None)
            rows.append((owner, name, key, len(c), repr(stamp)))
    return sorted(rows)


def main():
    if sys.argv[1] == "--cmp":
        a, b = (json.load(open(f)) for f in sys.argv[2:4])
        bad = []
        for k in ("answers", "digest", "rerun_same", "em_sizes", "em_content") + (
                ("em_order",) if a.get("hash_seed") is not None and a.get("hash_seed") == b.get("hash_seed") else ()):
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
            if d.get("fc_view_bad"):
                bad.append(f"{f}: fact cache view != store: {d['fc_view_bad']}")
            if d.get("em_view_bad"):
                bad.append(f"{f}: engine memo view != map: {d['em_view_bad']}")
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
    em = engmemo_rows(eng) + factcache_rows(eng)
    r["em_sizes"] = {n: len(v) for n, v in em}
    r["em_content"] = {n: _h(sorted(v)) for n, v in em}
    r["em_order"] = {n: _h(v) for n, v in em}
    r["hash_seed"] = os.environ.get("PYTHONHASHSEED")
    if mode == "rust" and hasattr(__import__("sa_solver"), "em_snapshot") and type(eng.splits).__name__ == "EngineMemo":
        r["em_view_bad"] = engmemo_view_ok(eng)
    if mode == "rust" and hasattr(__import__("sa_solver"), "fc_snapshot"):
        r["fc_view_bad"] = factcache_view_ok(eng)
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
    if "em_view_bad" in r:
        left += [f"em:{n}" for n in ENGMEMOS if type(getattr(eng, n)).__name__ == "EngineMemo"
                 and len(sa_solver.em_snapshot(getattr(eng, n))[2])]
    if r.get("fc_view_bad") == []:
        left += [f"fc:{n}" for n in FACTCACHES if len(sa_solver.fc_snapshot(getattr(eng, n))[3])]
    r["cleared"] = left
    if mode == "rust":      # step 5c10a: the fact caches' counters, the plant's firings, the refusals `_Mark` rolled back
        c = session_live.counts()
        r["counts"] = {k: v for k, v in c.items() if v and k.startswith(("fc:", "em:", "bud:"))}
        r["fired"] = c.get("rel:plant_fired", 0)
        r["refused"] = term_live.COUNTS["refused"]
    r["rerun_same"] = run(pairs[:200]) == ans[:200]
    json.dump(r, open(out, "w"), indent=0)
    print(json.dumps({k: v for k, v in r.items() if k != "tables"}))


if __name__ == "__main__":
    main()
