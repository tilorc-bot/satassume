"""analyze_pid.py RAW: per-round ratios (baseline s / candidate s), medians and ranges, rounds 1 up. Digest check over every run."""
import json, statistics as st, sys
R = [json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")]
print("runs", len(R), "digests", sorted({(r["wl"], r["digest"]) for r in R}))
for wl in ("dev", "fuzz"):
    T = {}
    for r in R:
        if r["wl"] == wl and r["round"] != "0":
            T.setdefault(r["round"], {})[r["run"]] = r["s"]
    for a, b, name in (("base", "pid", "base/pid"), ("base", "baseb", "A/A base/baseb")):
        q = [t[a] / t[b] for t in T.values()]
        print(f"{wl} {name}: median {st.median(q):.4f} range {min(q):.4f} to {max(q):.4f} rounds {len(q)}")
    for m in ("base", "baseb", "pid"):
        v = [t[m] for t in T.values()]
        print(f"{wl} {m}: median {st.median(v):.3f}s range {min(v):.3f} to {max(v):.3f}")
