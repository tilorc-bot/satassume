"""med329.py DIR (sa-port-329, issue 323): the S1 lease's rows read. time.jsonl: median, min and spread of `s` per arm
and workload over the rounds, on against off per mode, and the digests and .so hashes seen per workload (one digest per
workload is the gate inside the timing). wit.jsonl: the check's counts and costs per arm and workload."""
import json, statistics as st, sys
d = sys.argv[1]
rows = [json.loads(l) for l in open(d + "/time.jsonl")]
by, dig, so = {}, {}, set()
for r in rows:
    by.setdefault((r["wl"], r["arm"]), []).append(r["s"])
    dig.setdefault(r["wl"], set()).add(r["digest"])
    if r.get("so"):
        so.add(r["so"])
print("digests", {k: sorted(v) for k, v in dig.items()}, "so", sorted(so))
print("wl arm n median min max on/off(median) on/off(min)")
for (wl, arm), xs in sorted(by.items()):
    off = by[(wl, arm.split("-")[0] + "-off")]
    m, mo = st.median(xs), st.median(off)
    print(wl, arm, len(xs), f"{m:.4f} {min(xs):.4f} {max(xs):.4f} {100 * (m / mo - 1):+.1f}% {100 * (min(xs) / min(off) - 1):+.1f}%")
print("wl arm fires compiled certified check_s share_of_pass check_us[med,90,99,max] med_cert med_fall tried[med,90,max] digest")
for l in open(d + "/wit.jsonl"):
    r = json.loads(l)
    print(r["wl"], r["arm"], r["fires"], r["compiled"], r["certified"], f"{r['check_s']:.4f}", f"{100 * r['check_s'] / r['s']:.1f}%",
          r["check_us"], r["check_us_cert"], r["check_us_fall"], r["tried"], r["digest"])
