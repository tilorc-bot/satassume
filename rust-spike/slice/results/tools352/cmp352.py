"""cmp352.py A.jsonl B.jsonl (sa-port-352): two diff352.py runs (arms native and python) query by query: the answer,
Engine.stats (witness_certified among them), last_budget_limited and every call of `witnesses` with its result (the
certified set and the points). Exit 0 only if all are equal."""
import json, sys
a, b = ([json.loads(l) for l in open(p)] for p in sys.argv[1:3])
bad = [(x["q"], [k for k in ("a", "stats", "bl", "w") if x[k] != y[k]]) for x, y in zip(a, b) if x != y]
cert = lambda rows: dict(rows[-1]["stats"]).get("witness_certified") if rows else None
got = lambda rows: (sum(len(r["w"]) for r in rows), sum(1 for r in rows for c in r["w"] if c is not None))
print(json.dumps(dict(n=(len(a), len(b)), differ=len(bad), first=bad[:5], certified=(cert(a), cert(b)), calls_results=(got(a), got(b)))))
sys.exit(1 if bad or len(a) != len(b) else 0)
