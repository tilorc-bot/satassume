"""disctab352.py OUT (sa-port-352): disc352.sh's rows: per workload the discard check's counts (armed, raised, rollbacks
checked, clean, left-something and what was left), the native witness counters of the plain and the discard run, and
plain against discard: answers and session digests that differ, rows without a session."""
import json, os, sys
X = sys.argv[1]
for wl in ("dev", "lra", "fuzz"):
    a, b = ([l.rstrip("\n").split("\t") for l in open(f"{X}/{wl}-{n}.tsv")] for n in ("plain", "disc"))
    c = json.load(open(f"{X}/{wl}-disc.json"))
    k = c["counts"]
    wp, wd = (json.load(open(f"{X}/{wl}-{n}.json.wn.json")) for n in ("plain", "disc"))
    print(f"{wl}: queries {len(a)}/{len(b)}; armed {k.get('armed')}, raised {k.get('raised')}, no site reached {k.get('no-site-reached', 0)}, rollbacks checked {k.get('checked')}, "
          f"clean {k.get('clean', 0)}, left-something {k.get('left-something', 0)}, native reads {k.get('native-read')}; left {c['left']}")
    print(f"   plain against discard: answers differ {sum(x[1] != y[1] for x, y in zip(a, b))}, digests differ {sum(x[2] != y[2] for x, y in zip(a, b))}, "
          f"rows without a session {sum(x[2] == '' for x in a)}/{sum(y[2] == '' for y in b)}")
    print(f"   native counters plain {wp}\n   native counters discard {wd}")
d = json.load(open(f"{X}/dev-noroll.json")); k = d["counts"]
print(f"dev --no-rollback (the plant), first 300: checked {k.get('checked')}, clean {k.get('clean', 0)}, left-something {k.get('left-something', 0)}; left names {len(d['left'])}")
