"""med359.py BASE NEW DIR... (sa-port-359, issue 323; tools354/med354.py for item 5 of the convert.py port): the rows of
every DIR read together (timing-s1: dev and fuzz; timing-bw: budget and wiring; the same 10 arms and 12 rounds in each).
Per workload and arm (SHA:MODE-WITNESS): rounds, median, min, max and the interquartile range as a share of the median.
Then the comparisons, each on the rounds paired: the ratio of the medians, the median and quartiles of the per-round
ratios, and in how many rounds the first arm was slower. "BEYOND THE SPREAD" is printed when the ratio of the medians is
outside 1 by more than the larger interquartile share of the two arms and the first arm is slower (or faster) in at
least 10 of the 12 rounds (med342.py's rule, unchanged).
  A  the landing rule: Rust at the head against Rust at the base, same switches (nat = S1's fastest configuration,
     then on32 and off)
  P  the Python rows: head against base, py off and on32
  E  the sum over the four workloads per round
Also the digests and .so hashes seen per workload and arm, and wn359.py's rows (the walker and counters 740-746)."""
import json, os, statistics as st, sys
base, new, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
by, dig, so = {}, {}, {}
for d in dirs:
    for l in open(d + "/time.jsonl"):
        r = json.loads(l)
        by.setdefault((r["wl"], r["arm"]), {})[r["round"]] = r["s"]
        dig.setdefault(r["wl"], {}).setdefault(r["digest"], set()).add(r["arm"].split(":")[1])
        so.setdefault(r["arm"], set()).add(r.get("so"))
print("digests per workload (the arms that gave each):")
for wl, v in dig.items():
    for g, arms in sorted(v.items()):
        print(" ", wl, g, " ".join(sorted(arms)))
print("so per arm", {k: sorted(map(str, v)) for k, v in sorted(so.items())})


def iq(xs):
    v = sorted(xs)
    q = st.quantiles(v, n=4)
    return (q[2] - q[0]) / st.median(v)


def line(label, xa, xb, unit=""):
    rs = sorted(xa[r] / xb[r] for r in xa if r in xb)
    q = st.quantiles(rs, n=4)
    ma, mb = st.median(xa.values()), st.median(xb.values())
    m = ma / mb
    slower = sum(1 for r in rs if r > 1)
    spread = max(iq(xa.values()), iq(xb.values()))
    verdict = "within the spread"
    if abs(m - 1) > spread and (slower >= len(rs) - 2 or slower <= 2):
        verdict = "BEYOND THE SPREAD: " + ("slower" if m > 1 else "faster")
    print(f"{label}: medians {ma:.4f} / {mb:.4f} {100 * (m - 1):+.1f}%; per round median {100 * (q[1] - 1):+.1f}% quartiles {100 * (q[0] - 1):+.1f}% {100 * (q[2] - 1):+.1f}%; slower in {slower} of {len(rs)}; larger iqr {100 * spread:.1f}%; {verdict}")


def cmp(wl, a, b):
    line(f"{wl} {a} / {b}", by[(wl, a)], by[(wl, b)])


print("wl arm n median min max iqr%")
for (wl, arm), xs in sorted(by.items()):
    v = sorted(xs.values())
    print(wl, arm, len(v), f"{st.median(v):.4f} {v[0]:.4f} {v[-1]:.4f} {100 * iq(v):.1f}%")
wls = [w for w in ("dev", "fuzz", "budget", "wiring") if w in dig]
print("A the landing rule: Rust at the head against Rust at the base, same switches:")
for w in ("nat", "on32", "off"):
    for wl in wls:
        cmp(wl, f"{new}:rust-{w}", f"{base}:rust-{w}")
print("P the Python rows: head against base:")
for w in ("off", "on32"):
    for wl in wls:
        cmp(wl, f"{new}:py-{w}", f"{base}:py-{w}")
print("E the sum over", " ".join(wls), "per round:")


def sums(arm):
    rounds = set.intersection(*(set(by[(wl, arm)]) for wl in wls))
    return {r: sum(by[(wl, arm)][r] for wl in wls) for r in rounds}


for a in ("rust-nat", "rust-on32", "rust-off", "py-off", "py-on32"):
    line(f"  sum {new}:{a} / {base}:{a}", sums(f"{new}:{a}"), sums(f"{base}:{a}"))
print("wn359.py, one pass per workload and arm: wl arm walk certified queries digest so cv")
for d in dirs:
    if os.path.exists(d + "/wn.jsonl"):
        for l in open(d + "/wn.jsonl"):
            r = json.loads(l)
            c = r.get("cv") or {}
            print(" ", r["wl"], r["arm"], (r.get("walk") or "-")[:60], r["certified"], r["queries"], r["digest"], r["so"],
                  " ".join(f"{k}={v}" for k, v in sorted(c.items()) if v))
