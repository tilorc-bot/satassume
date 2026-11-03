import json, collections, sys
d = json.load(open(sys.argv[1])); rows = d["rows"]; tot = d["tot"]
print("pass", round(tot,2), d["C"], {k: round(v,2) for k,v in d["T"].items()})
C = collections.Counter(); T = collections.Counter()
for r in rows:
    k = (r["ph"], "ring" if r["ring"] else "search", "theory" if r["nt"] else "plain")
    C[k] += 1; T[k] += r["dt"]
    if not r["ring"]:
        k2 = (r["ph"], "theory" if r["nt"] else "plain", "hit" if r["hit"] is not None else ("nocand" if not r["nc"] else "miss"))
        C[k2] += 1; T[k2] += r["dt"]; T[k2+("tc",)] += r["tc"]
        if r["ph"]=="check": 
            k3=("check", "theory" if r["nt"] else "plain", "prev" if r.get("prev") else "first"); C[k3]+=1; T[k3]+=r["dt"]
for k in sorted(C, key=str):
    print(k, C[k], f"{T[k]:.3f}s {100*T[k]/tot:.1f}%", f"check {T[k+('tc',)]:.3f}s" if k+('tc',) in T else "")
w = collections.Counter(r["why"][0] for r in rows if r["why"] and r["hit"] is None)
print("miss reasons(first cand)", w)
print("hit index", collections.Counter(r["hit"] for r in rows if r["hit"] is not None))
