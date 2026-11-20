"""med363.py BASE NEW DIR... (sa-port-363, issue 323; tools359/med359.py's reading and rule for item 6 of the formula
skeleton's removal): the rows of every DIR read together (timing-s1: dev and fuzz; timing-bw: budget and wiring; the
same arms and 12 rounds in each). Per workload and arm (SHA:MODE-WITNESS): rounds, median, min, max and the
interquartile range as a share of the median. Then NEW against BASE for every MODE-WITNESS and workload, on the rounds
paired: the ratio of the medians, the median and quartiles of the per-round ratios, and in how many rounds NEW was
slower. "BEYOND THE SPREAD" is printed when the ratio of the medians is outside 1 by more than the larger interquartile
share of the two arms and NEW is slower (or faster) in at least 10 of the 12 rounds (med342.py's rule, unchanged).
Last, per MODE-WITNESS, the sum over the workloads per round. Also the digests and .so hashes seen per workload and
arm."""
import json, statistics as st, sys
base, new, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
by, dig, so = {}, {}, {}
for d in dirs:
    for l in open(d + "/time.jsonl"):
        r = json.loads(l)
        by.setdefault((r["wl"], r["arm"]), {})[r["round"]] = r["s"]
        dig.setdefault(r["wl"], {}).setdefault(r["digest"], set()).add(r["arm"])
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


def line(label, xa, xb):
    rs = sorted(xa[r] / xb[r] for r in xa if r in xb)
    q = st.quantiles(rs, n=4)
    ma, mb = st.median(xa.values()), st.median(xb.values())
    m = ma / mb
    slower = sum(1 for r in rs if r > 1)
    spread = max(iq(xa.values()), iq(xb.values()))
    verdict = "within the spread"
    if abs(m - 1) > spread and (slower >= len(rs) - 2 or slower <= 2):
        verdict = "BEYOND THE SPREAD: " + ("slower" if m > 1 else "faster")
    print(f"{label}: medians {ma:.4f} / {mb:.4f} {100 * (m - 1):+.1f}%; per round median {100 * (q[1] - 1):+.1f}% quartiles "
          f"{100 * (q[0] - 1):+.1f}% {100 * (q[2] - 1):+.1f}%; slower in {slower} of {len(rs)}; larger iqr {100 * spread:.1f}%; {verdict}")


wls = sorted({wl for wl, _ in by})
kinds = sorted({a.split(":")[1] for _, a in by})
print("\nper workload and arm: rounds, median, min, max, iqr share")
for (wl, a), v in sorted(by.items()):
    print(f"  {wl} {a}: {len(v)} {st.median(v.values()):.4f} {min(v.values()):.4f} {max(v.values()):.4f} {100 * iq(v.values()):.1f}%")
print(f"\nNEW {new} against BASE {base}, same mode and switches")
for k in kinds:
    for wl in wls:
        line(f"{wl} {k}", by[(wl, f"{new}:{k}")], by[(wl, f"{base}:{k}")])
print("\nthe sum over the workloads per round")
for k in kinds:
    tot = {s: {r: sum(by[(wl, f"{s}:{k}")][r] for wl in wls) for r in by[(wls[0], f"{s}:{k}")] if all(r in by[(wl, f"{s}:{k}")] for wl in wls)} for s in (new, base)}
    line(f"sum {k}", tot[new], tot[base])
