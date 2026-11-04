"""inv_table.py IN.json [TOP]: summarize an inventory by site."""
import json
import sys
from collections import Counter, defaultdict
d = json.load(open(sys.argv[1]))
top = int(sys.argv[2]) if len(sys.argv) > 2 else 40
rows = [r for r in d["rows"] if r["inside"]]
s = defaultdict(lambda: dict(n=0, types=Counter()))
for r in rows:
    k = (r["kind"], r["file"].replace("satassume/", ""), r["line"], r["fn"], r["op"])
    s[k]["n"] += r["n"]
    s[k]["types"][r["a"] + ("/" + r["b"] if r["b"] else "")] += r["n"]
tot = Counter()
for k, v in s.items():
    tot[k[0]] += v["n"]
print(d["wl"], d["digest"], dict(tot), "sites", len(s))
for k, v in sorted(s.items(), key=lambda kv: -kv[1]["n"])[:top]:
    print(v["n"], *k, " ".join(f"{t}:{n}" for t, n in v["types"].most_common(4)))
