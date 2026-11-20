"""cmp351.py A.jsonl B.jsonl (sa-port-351): two diff351.py runs (arms native and python) query by query: the answer,
Engine.stats (witness_certified among them) and last_budget_limited after each query. Exit 0 only if all are equal."""
import json, sys
a, b = ([json.loads(l) for l in open(p)] for p in sys.argv[1:3])
bad = [(x["q"], [k for k in ("a", "stats", "bl") if x[k] != y[k]]) for x, y in zip(a, b) if x != y]
cert = lambda rows: dict(rows[-1]["stats"]).get("witness_certified") if rows else None
print(json.dumps(dict(n=(len(a), len(b)), differ=len(bad), first=bad[:5], certified=(cert(a), cert(b)))))
sys.exit(1 if bad or len(a) != len(b) else 0)
