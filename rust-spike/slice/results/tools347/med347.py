"""med347.py BASE NEW DIR... (sa-port-347, issue 323; tools342/med342.py for time347.sh's arms): the rows of every DIR
read together (timing-s1: dev and fuzz; timing-bw: budget and wiring; the same 12 arms and 12 rounds in each).
Per workload and arm (SHA:MODE-WITNESS): rounds, median, min, max and the interquartile range as a share of the median.
Then the comparisons, each on the rounds paired: the ratio of the medians, the median and quartiles of the per-round
ratios, and in how many rounds the first arm was slower. "BEYOND THE SPREAD" is printed when the ratio of the medians is
outside 1 by more than the larger interquartile share of the two arms and the first arm is slower (or faster) in at
least 10 of the 12 rounds (med342.py's rule).
  A  head on against base on (the landing rule), and head off against base off
  B  on against off, each tree (what the switch costs; dev and fuzz must keep their gains)
  C  head on against head cf (what item (1)'s test costs: cf is the head with the test taken out)
  D  head w8400 against head on (the two bounds), w8400 against base on, w8400 against head off
  E  the sum over the four workloads per round, bound 2500 (on32) against 8400, per mode and both modes together
Also the digests and .so hashes seen per workload, and wit.jsonl's counts where present."""
import json, os, statistics as st, sys
base, new, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
by, dig, so = {}, {}, set()
for d in dirs:
    for l in open(d + "/time.jsonl"):
        r = json.loads(l)
        by.setdefault((r["wl"], r["arm"]), {})[r["round"]] = r["s"]
        dig.setdefault(r["wl"], set()).add(r["digest"])
        if r.get("so"):
            so.add(r["so"])
print("digests", {k: sorted(v) for k, v in dig.items()}, "so", sorted(so))


def iq(xs):
    v = sorted(xs)
    q = st.quantiles(v, n=4)
    return (q[2] - q[0]) / st.median(v)


iqr = {}
print("wl arm n median min max iqr%")
for (wl, arm), xs in sorted(by.items()):
    v = sorted(xs.values())
    iqr[(wl, arm)] = iq(v)
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
    print(f"{wl} {a} / {b}: medians {st.median(xa.values()):.4f} / {st.median(xb.values()):.4f} {100 * (m - 1):+.1f}%; per round median {100 * (q[1] - 1):+.1f}% quartiles {100 * (q[0] - 1):+.1f}% {100 * (q[2] - 1):+.1f}%; slower in {slower} of {n}; larger iqr {100 * spread:.1f}%; {verdict}")


wls = [w for w in ("dev", "fuzz", "budget", "wiring") if w in dig]
M = ("py", "rust")
print("A head against base, same mode and switch:")
for wl in wls:
    for m in M:
        for w in ("on32", "off"):
            cmp(wl, f"{new}:{m}-{w}", f"{base}:{m}-{w}")
print("B on against off, same tree and mode:")
for wl in wls:
    for s in (base, new):
        for m in M:
            cmp(wl, f"{s}:{m}-on32", f"{s}:{m}-off")
print("C head on against head with item (1)'s test taken out (check-first):")
for wl in wls:
    for m in M:
        cmp(wl, f"{new}:{m}-on32", f"{new}:{m}-cf")
print("D the bound at 8400: against the head's 2500, against base on, against head off:")
for wl in wls:
    for m in M:
        cmp(wl, f"{new}:{m}-w8400", f"{new}:{m}-on32")
        cmp(wl, f"{new}:{m}-w8400", f"{base}:{m}-on32")
        cmp(wl, f"{new}:{m}-w8400", f"{new}:{m}-off")
print("E the sum over", " ".join(wls), "per round:")


def sums(arms):
    rounds = set.intersection(*(set(by[(wl, a)]) for wl in wls for a in arms))
    return {r: sum(by[(wl, a)][r] for wl in wls for a in arms) for r in rounds}


for label, ms in (("py", ("py",)), ("rust", ("rust",)), ("py+rust", M)):
    row = {}
    for w in ("off", "on32", "w8400", "cf"):
        row[w] = sums([f"{new}:{m}-{w}" for m in ms])
    row["base-on32"] = sums([f"{base}:{m}-on32" for m in ms]); row["base-off"] = sums([f"{base}:{m}-off" for m in ms])
    print(" ", label, "; ".join(f"{k} median {st.median(v.values()):.4f} iqr {100 * iq(v.values()):.1f}%" for k, v in row.items()))
    for a, b in (("on32", "w8400"), ("on32", "base-on32"), ("w8400", "base-on32"), ("on32", "off"), ("w8400", "off")):
        xa, xb = row[a], row[b]
        rs = sorted(xa[r] / xb[r] for r in xa if r in xb)
        q = st.quantiles(rs, n=4)
        m = st.median(xa.values()) / st.median(xb.values())
        slower = sum(1 for r in rs if r > 1)
        spread = max(iq(xa.values()), iq(xb.values()))
        verdict = "within the spread"
        if abs(m - 1) > spread and (slower >= len(rs) - 2 or slower <= 2):
            verdict = "BEYOND THE SPREAD: " + ("slower" if m > 1 else "faster")
        print(f"    {label} sum {a} / {b}: medians {100 * (m - 1):+.1f}% ({st.median(xa.values()) - st.median(xb.values()):+.4f} s); per round median {100 * (q[1] - 1):+.1f}%; slower in {slower} of {len(rs)}; larger iqr {100 * spread:.1f}%; {verdict}")
print("what each py switch-on arm sets and counts on one pass (arm347.py):")
for d in dirs:
    if os.path.exists(d + "/arm.jsonl"):
        for l in open(d + "/arm.jsonl"):
            r = json.loads(l)
            print(" ", r["wl"], r["arm"], {k: r[k] for k in ("cap", "work", "plant", "fired", "certified", "budget_limited", "queries", "n")})
for d in dirs:
    if os.path.exists(d + "/wit.jsonl"):
        print("wl arm fires compiled certified check_s share_of_pass check_us[med,90,99,max] med_cert med_fall tried[med,90,max] digest")
        for l in open(d + "/wit.jsonl"):
            r = json.loads(l)
            print(r["wl"], r["arm"], r["fires"], r["compiled"], r["certified"], f"{r['check_s']:.4f}", f"{100 * r['check_s'] / r['s']:.1f}%",
                  r["check_us"], r["check_us_cert"], r["check_us_fall"], r["tried"], r["digest"])
