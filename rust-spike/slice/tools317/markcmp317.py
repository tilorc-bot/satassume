"""markcmp317.py JSON... (sa-port-317): mark317.py's per-run lists side by side: pooled inclusive share, per-run median
and min-max of the share and of ms (share x the run's wall)."""
import json, statistics as st, sys
for f in sys.argv[1:]:
    d = json.loads(open(f).read()); r = d["runs"]; N = sum(x["n"] for x in r)
    print(f"{d['dir']} {d['wl']}: runs {len(r)}, samples {N}, wall median {st.median(x['s'] for x in r):.3f} s, digests {sorted({x['digest'] for x in r})}")
    for k in ("mark", "note", "attr_or", "live"):
        sh = [100 * x[k] / x["n"] for x in r]; ms = [1000 * x["s"] * x[k] / x["n"] for x in r]
        print(f"   {k:8} pooled {sum(x[k] for x in r):5} = {100*sum(x[k] for x in r)/N:5.2f}%; per run {st.median(sh):5.2f}% ({min(sh):.2f}-{max(sh):.2f}); ms {st.median(ms):6.1f} ({min(ms):.1f}-{max(ms):.1f})")
