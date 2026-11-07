"""merge_shards.py OUT SHARD...: shards of one live.py --fork run as one file, with the total a whole run would write."""
import hashlib, json, sys
out, shards = sys.argv[1], sys.argv[2:]
rows, tots = [], []
for f in shards:
    for l in open(f):
        r = json.loads(l)
        (tots.append(r["total"]) if "total" in r else rows.append(r))
assert len(tots) == len(shards), (len(tots), len(shards))
rows.sort(key=lambda r: r["q"])
assert len({r["q"] for r in rows}) == len(rows)
t = dict(tots[0])
for k in ("queries","solvers","python_solvers_made","traced_made","traced_dropped","addr_masked"):
    t[k] = sum(x[k] for x in tots)
for k in ("reentry","entry_raises","answers","lra_groups"):
    d = {}
    for x in tots:
        for a, v in x[k].items():
            d[a] = d.get(a, 0) + v
    t[k] = d
assert len({x.get("so_sha") for x in tots}) == 1
t["answers_sha"] = hashlib.sha256(json.dumps([r["ans"] for r in rows]).encode()).hexdigest()[:16]
with open(out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
    f.write(json.dumps(dict(total=t)) + "\n")
print(out.split("/")[-1], len(rows), t["answers_sha"], "py_made", t["python_solvers_made"], "made", t["traced_made"], "reentry", sum(t["reentry"].values()))
