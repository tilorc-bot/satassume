"""Persistent-solver plan, stage 0: logged time by why a session was built.

    python gs0_session_split.py LOG

Top-level queries (``nested == 0``) grouped by ``session_new`` and by
whether any session was built during the query (``built``); ms and share.
"""
import json
import sys
from collections import defaultdict

rows = [json.loads(line) for line in open(sys.argv[1])]
top = [r for r in rows if r.get("nested", 0) == 0]
total = sum(r["ms"] for r in top)
g = defaultdict(lambda: [0, 0.0])
for r in top:
    k = f"{r['session_new']}, built {'>0' if r.get('built') else '0'}"
    g[k][0] += 1
    g[k][1] += r["ms"]
print(f"{sys.argv[1]}: {len(top)} top-level queries, {total:.0f} ms")
for k, (n, ms) in sorted(g.items(), key=lambda kv: -kv[1][1]):
    print(f"  {k:28s} {n:6d} {ms:8.0f} ms {100*ms/total:5.1f}%")
b = sum(r["ms"] for r in top if r.get("built"))
print(f"  queries that built a session: {sum(1 for r in top if r.get('built'))}, {b:.0f} ms, {100*b/total:.1f}%")
