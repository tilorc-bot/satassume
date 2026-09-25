"""Summarize the query logs of ``refine_baseline_plugin`` (one per backend).

    python refine_baseline_counts.py DIR     # reads DIR/q-<backend>.jsonl

Prints, per backend, queries and answers (True/False/None), distinct
(prop, assumptions) pairs; for ``combined``, the SymPy fallbacks by the
routing reason, with SymPy's answer on them, and satassume's own
undecided answers (reason null, answer None), which the old combined
backend (refine-monorepo) also sent to SymPy.
"""
import json
import sys
from collections import Counter
from pathlib import Path

d = Path(sys.argv[1])
for b in ("sympy", "satassume", "combined"):
    p = d / f"q-{b}.jsonl"
    if not p.exists():
        continue
    rows = [json.loads(line) for line in p.open()]
    ans = Counter(str(r["ans"]) for r in rows)
    distinct = {(r["p"], r["a"]) for r in rows}
    print(f"{b}: {len(rows)} queries, {len(distinct)} distinct; answers {dict(ans)}")
    if b != "combined":
        continue
    fb = [r for r in rows if r.get("route") not in (None,)]
    by = Counter(r["route"] for r in fb)
    print(f"  SymPy fallbacks: {len(fb)} ({len({(r['p'], r['a']) for r in fb})} distinct); by reason {dict(by)}")
    for reason in sorted(by):
        sub = [r for r in fb if r["route"] == reason]
        print(f"    {reason}: SymPy answers {dict(Counter(str(r['ans']) for r in sub))}")
    und = [r for r in rows if r.get("route") is None and r["ans"] is None]
    print(f"  satassume None that stands (no SymPy call): {len(und)} "
          f"({len({(r['p'], r['a']) for r in und})} distinct)")
