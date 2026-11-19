"""med342.py DIR BASE NEW (sa-port-342, issue 323; tools328/med329.py for arms of two trees): time342.sh's rows read.
Per workload and arm (SHA:MODE-WITNESS): rounds, median, min, max and the interquartile range as a share of the median.
Then the comparisons, each on the rounds paired (both arms ran in every round): the ratio of the medians, the median and
the quartiles of the per-round ratios, and in how many rounds the first arm was slower.
  head against base, same mode and switch (the landing measure: on against on, and off against off)
  on against off, same tree and mode (what the switch costs)
"beyond the spread" is printed when the ratio of the medians is outside 1 by more than the larger interquartile share
of the two arms and the first arm is slower (or faster) in at least 10 of the 12 rounds. Also the digests and .so hashes
seen per workload (one digest per workload is the gate inside the timing), and wit.jsonl's counts if present."""
import json, os, statistics as st, sys
d, base, new = sys.argv[1:4]
rows = [json.loads(l) for l in open(d + "/time.jsonl")]
by, dig, so = {}, {}, set()
for r in rows:
    by.setdefault((r["wl"], r["arm"]), {})[r["round"]] = r["s"]
    dig.setdefault(r["wl"], set()).add(r["digest"])
    if r.get("so"):
        so.add(r["so"])
print("digests", {k: sorted(v) for k, v in dig.items()}, "so", sorted(so))
iqr = {}
print("wl arm n median min max iqr%")
for (wl, arm), xs in sorted(by.items()):
    v = sorted(xs.values())
    q = st.quantiles(v, n=4)
    iqr[(wl, arm)] = (q[2] - q[0]) / st.median(v)
    print(wl, arm, len(v), f"{st.median(v):.4f} {v[0]:.4f} {v[-1]:.4f} {100 * iqr[(wl, arm)]:.1f}%")


def cmp(wl, a, b):
    xa, xb = by[(wl, a)], by[(wl, b)]
    rs = sorted(xa[r] / xb[r] for r in xa if r in xb)
    q = st.quantiles(rs, n=4)
    m = st.median(xa.values()) / st.median(xb.values())
    slower = sum(1 for r in rs if r > 1)
    spread = max(iqr[(wl, a)], iqr[(wl, b)])
    n = len(rs)
    verdict = "within the spread"
    if abs(m - 1) > spread and (slower >= n - 2 or slower <= 2):
        verdict = "BEYOND THE SPREAD: " + ("slower" if m > 1 else "faster")
    print(f"{wl} {a} / {b}: medians {100 * (m - 1):+.1f}%; per round median {100 * (q[1] - 1):+.1f}% quartiles {100 * (q[0] - 1):+.1f}% {100 * (q[2] - 1):+.1f}%; slower in {slower} of {n}; larger iqr {100 * spread:.1f}%; {verdict}")


wls = sorted(dig)
print("head against base:")
for wl in wls:
    for a in ("py-off", "py-on32", "rust-off", "rust-on32"):
        cmp(wl, f"{new}:{a}", f"{base}:{a}")
print("on against off:")
for wl in wls:
    for s in (base, new):
        for m in ("py", "rust"):
            cmp(wl, f"{s}:{m}-on32", f"{s}:{m}-off")
if os.path.exists(d + "/wit.jsonl"):
    print("wl arm fires compiled certified check_s share_of_pass check_us[med,90,99,max] med_cert med_fall tried[med,90,max] digest")
    for l in open(d + "/wit.jsonl"):
        r = json.loads(l)
        print(r["wl"], r["arm"], r["fires"], r["compiled"], r["certified"], f"{r['check_s']:.4f}", f"{100 * r['check_s'] / r['s']:.1f}%",
              r["check_us"], r["check_us_cert"], r["check_us_fall"], r["tried"], r["digest"])
