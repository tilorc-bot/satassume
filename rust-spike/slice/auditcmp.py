"""auditcmp.py DIR: compare audit.py runs against dev/fuzz-h0-s0."""
import json, sys, glob, os
from collections import Counter
d = sys.argv[1]
for wl in ("dev", "fuzz"):
    b = json.load(open(f"{d}/{wl}-h0-s0.json"))
    print(f"## {wl}: G={b['G']} callers={b['callers']} custom={b['custom']} ext={b['ext']} specs={b['specs']} glue_memo={b['glue_memo']}")
    print(f"sessions reentrant queries: {sum(1 for r in b['res'] if r['reent'])}; objects {len(b['kids'])}; cones {len(b['cones'])}, None {sum(1 for c in b['cones'].values() if c[0] is None)}")
    for f in sorted(glob.glob(f"{d}/{wl}-h*-s*.json")):
        n = os.path.basename(f)[:-5]
        if n == f"{wl}-h0-s0": continue
        o = json.load(open(f))
        ans = sum(x['a'] != y['a'] for x, y in zip(b['res'], o['res']))
        same_n = [(x, y) for x, y in zip(b['res'], o['res']) if len(x['sess']) == len(y['sess'])]
        cl = sum([s[0] for s in x['sess']] != [s[0] for s in y['sess']] for x, y in same_n)
        at = sum([s[1] for s in x['sess']] != [s[1] for s in y['sess']] for x, y in same_n)
        lr = sum(x['lra'] != y['lra'] for x, y in same_n)
        allb = Counter(s[1] for x in b['res'] for s in x['sess'] if s[2]); allo = Counter(s[1] for x in o['res'] for s in x['sess'] if s[2])
        kk = set(b['kids']) & set(o['kids']); kd = [k for k in kk if b['kids'][k] != o['kids'][k]]
        ck = set(b['cones']) & set(o['cones'])
        nn = sum((b['cones'][k][0] is None) != (o['cones'][k][0] is None) for k in ck)
        fit = sum(b['cones'][k][0] is not None and b['cones'][k] != o['cones'][k] for k in ck)
        over = sum(b['cones'][k][0] is None and o['cones'][k][0] is None and b['cones'][k] != o['cones'][k] for k in ck)
        print(f"{n}: answers differ {ans}; queries same #sessions {len(same_n)}: clause-seq differ {cl}, atom-seq differ {at}, LRA-out differ {lr}; "
              f"atom-seq multiset only-in-base {sum((allb-allo).values())} of {sum(allb.values())}; "
              f"kids shared {len(kk)} differ {len(kd)} only-base {len(set(b['kids'])-kk)} only-other {len(set(o['kids'])-kk)}; cones shared {len(ck)}, None-ness differ {nn}, fitting differ {fit}, over-budget fields differ {over}")
        for k in kd[:2]: print("   kid diff", k[:100], str(b['kids'][k])[:160], str(o['kids'][k])[:160])
