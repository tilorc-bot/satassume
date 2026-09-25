"""Stage 0: count SymPy fallbacks of the refine ``combined`` backend.

    python facts_scoreboard_fallbacks.py /work/src/facts-logs/scoreboard

Reads ``combined-*/queries.jsonl`` written by ``facts_scoreboard_plugin``
(``how == "sympy-fallback"`` marks a query satassume answered None, or
raised on, and SymPy was asked) and ``combined-*/junit-combined.xml``.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/work/src/refine-mono/tools")
from refine_scoreboard import parse_junit, PASSING  # noqa: E402

L = Path(sys.argv[1])
REL = re.compile(r"Q\.(eq|ne|lt|le|gt|ge)\(")
MAT = ("symmetric", "orthogonal", "diagonal", "singular", "unitary", "unit_triangular", "invertible",
       "triangular", "lower_triangular", "upper_triangular", "fullrank", "square", "normal",
       "positive_definite", "integer_elements", "real_elements", "complex_elements")


def kind(p, a):
    s = p + " " + a
    if REL.search(s):
        return "relation"
    if any(f"Q.{m}(" in s for m in MAT) or re.search(r"Q\.\w+\([A-Z]\b", s):
        return "matrix"
    return "scalar"


print("| run | passed | failed | queries | fallbacks | distinct (p,a) | distinct fallbacks | fallbacks by kind (all) |")
print("|---|---:|---:|---:|---:|---:|---:|---|")
for d in sorted(L.glob("combined-*")):
    q = [json.loads(line) for line in (d / "queries.jsonl").open()]
    fb = [r for r in q if r["how"] == "sympy-fallback"]
    dq = {(r["p"], r["a"]) for r in q}
    dfb = {(r["p"], r["a"]) for r in fb}
    kinds = Counter(kind(p, a) for p, a in (( r["p"], r["a"]) for r in fb))
    res, *_ = parse_junit(d / "junit-combined.xml")
    c = Counter(res.values())
    print(f"| {d.name} | {sum(c[o] for o in PASSING)} | {c['failed'] + c['error']} | {len(q)} | {len(fb)} | "
          f"{len(dq)} | {len(dfb)} | {dict(kinds)} |")
