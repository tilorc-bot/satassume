import json,collections,sys
for path in sys.argv[1:]:
    R=[json.loads(l) for l in open(path)]
    C=collections.Counter(); Q=set(); P=set()
    for r in R:
        rr=[r.get(f"rerun{n}") for n in (200,2000,20000) if r.get(f"rerun{n}")]
        last=rr[-1]
        ub=r.get("unbounded",{})
        anyub=any(x is True for v in ub.values() for x in v)
        npos=sum(1 for i in r["ints"] if i[3]>0); nneg=len(r["ints"])-npos
        C[(r["fields"], len(r["terms"]), npos, nneg, len(r["dis"]), anyub, last[0], last[1])]+=1
        Q.add(r["q"]); P.add(json.dumps([r["bounds"],sorted(map(str,r["ints"])),sorted(map(str,r["dis"]))],sort_keys=True))
    print(path, len(R), "exh;", len(Q), "queries;", len(P), "distinct problems")
    print("  count (fields, terms, +int, -int, diseq, unbounded, rerun outcome, nodes)")
    for k,v in sorted(C.items(),key=lambda x:-x[1]): print("  ",v,k)
