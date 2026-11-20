"""tab356.py DIR (sa-port-356): the profile of item 1 as tables, from DIR/time/time.jsonl (pys356.sh's timed rows),
DIR/ana-WL.json (ana356.py) and DIR/run/WL-rust-cprof-0.json (prof356.py). Shares are of the sampler's in-loop samples
of the rust-nat arm; seconds are share times the median timed pass."""
import json, statistics, sys
d = sys.argv[1]
WLS = ("dev", "fuzz", "budget", "wiring")
rows = [json.loads(l) for l in open(d + "/time/time.jsonl")]
med = statistics.median
iqr = lambda v: (statistics.quantiles(v, n=4)[2] - statistics.quantiles(v, n=4)[0]) / med(v)
print("| workload | arm | rounds | median s | min | max | iqr/median | digest | .so |\n|---|---|---|---|---|---|---|---|---|")
S = {}
for wl in WLS:
    for arm in ("rust-nat", "py-on32"):
        g = [r for r in rows if r["wl"] == wl and r["arm"] == arm]
        v = [r["s"] for r in g]
        S[wl, arm] = med(v)
        print("| %s | %s | %d | %.4f | %.4f | %.4f | %.1f%% | %s | %s |" % (wl, arm, len(v), med(v), min(v), max(v), 100 * iqr(v),
              ",".join(sorted({r["digest"] for r in g})), ",".join(sorted({str(r.get("so")) for r in g}))))
A = {wl: json.load(open("%s/ana-%s.json" % (d, wl))) for wl in WLS}
C = {wl: json.load(open("%s/run/%s-rust-cprof-0.json" % (d, wl))) for wl in WLS}
print("\nsamples and categories (ana195), share of the in-loop samples:")
for wl in WLS:
    a = A[wl]
    print("  %s: N %d, runs %d, digests %s; %s" % (wl, a["N"], len(a["runs"]), sorted({r[1] for r in a["runs"]}),
          ", ".join("%s %.1f%%" % (k, 100 * v / a["N"]) for k, v in sorted(a["cats"].items(), key=lambda x: -x[1]))))
own = lambda a, k: a["byte"].get(k, 0) + a["c"].get(k, 0)
files = sorted({k for a in A.values() for k in list(a["byte"]) + list(a["c"]) + list(a["incl"])},
               key=lambda k: -sum(own(A[wl], k) / A[wl]["N"] for wl in WLS))
ck = lambda k: k.replace("sa/", "satassume/").rsplit("/", 1)[-1]
print("\n| file | " + " | ".join("%s own (bytecode + C) | %s incl" % (w, w) for w in WLS) + " | own summed | calls dev/fuzz/budget/wiring |")
print("|---|" + "---|" * (2 * len(WLS) + 2))
for k in files[:int(sys.argv[2]) if len(sys.argv) > 2 else 30]:
    cells = []
    for wl in WLS:
        a = A[wl]
        cells.append("%.2f%% (%.2f + %.2f) | %.1f%%" % (100 * own(a, k) / a["N"], 100 * a["byte"].get(k, 0) / a["N"],
                     100 * a["c"].get(k, 0) / a["N"], 100 * a["incl"].get(k, 0) / a["N"]))
    calls = "/".join(str(sum(v for f, v in C[wl]["cprof_calls"].items() if f.split("/")[-1] == k.split("/")[-1] and "/" in f and "/" in k) or "-") for wl in WLS)
    print("| %s | %s | %.2f%% | %s |" % (k, " | ".join(cells), sum(100 * own(A[wl], k) / A[wl]["N"] for wl in WLS), calls))
print("\nSymPy and stdlib own time by the nearest repository file on the stack (share of samples):")
for wl in WLS:
    a = A[wl]
    u = sorted(((f, sum(v.values())) for f, v in a["under"].items()), key=lambda x: -x[1])[:8]
    print("  %s: %s" % (wl, ", ".join("%s %.2f%%" % (f, 100 * n / a["N"]) for f, n in u)))
print("\nown time by function, top 14 per workload:")
for wl in WLS:
    a = A[wl]
    print("  %s: %s" % (wl, ", ".join("%s %.2f%%" % (f, 100 * n / a["N"]) for f, n in sorted(a["ownf"].items(), key=lambda x: -x[1])[:14])))
