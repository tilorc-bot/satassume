"""Stage 0 of the fact-lattice plan: compare refine-scoreboard runs.

    python facts_scoreboard_analyze.py /work/src/facts-logs/scoreboard [refine-mono root]

Reads ``base/junit-sympy.xml`` (the reference) and ``<run>/junit-satassume.xml``
for the runs ``old current oracle-base oracle-transfer oracle-free
oracle-both`` (see ``run_all.sh`` there), and ``<run>/queries.jsonl`` (the
plugin's query log).  Prints: per run passed/failed and losses (pass under
sympy, fail under the run), losses fixed relative to ``old``, regressions
relative to ``current``; then per loss of ``old`` its family, scope
category, the relation predicates asked, and its status in every run.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

L = Path(sys.argv[1])
ROOT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/work/src/refine-mono")
sys.path.insert(0, str(ROOT / "tools"))
from refine_scoreboard import parse_junit, PASSING  # noqa: E402

RUNS = ["old", "current", "oracle-base", "oracle-transfer", "oracle-free", "oracle-both"]
ref, _, _, _ = parse_junit(L / "base" / "junit-sympy.xml")
res, msgs, cnts = {}, {}, {}
for r in RUNS:
    j = L / r / "junit-satassume.xml"
    if j.exists():
        res[r], msgs[r], cnts[r], _ = parse_junit(j)


def ok(d, t):
    return d.get(t) in PASSING


def losses(r):
    return sorted(t for t in ref if ok(ref, t) and not ok(res[r], t))


def family(t):
    mod, name = t.split("::")
    mod = mod.rsplit(".", 1)[-1]
    if "matrix" in mod or "matrix" in name:
        return "matrix"
    for key, fam in (("max", "Min/Max"), ("min", "Min/Max"), ("kronecker", "KroneckerDelta"),
                     ("binomial", "binomial"), ("factorial", "factorial"),
                     ("inverse_trig", "inverse-trig"), ("atan", "inverse-trig")):
        if key in mod or key in name:
            return fam
    return mod.replace("test_refine_", "")


REL = re.compile(r"\bQ\.(eq|ne|lt|le|gt|ge)\(|(==|!=|<=|>=|<|>)|\b(Eq|Ne)\(")


def rels(s):
    out = set()
    for m in REL.finditer(s):
        out.add(m.group(1) or m.group(3) or m.group(2))
    return out


def qlog(r):
    q = defaultdict(list)
    p = L / r / "queries.jsonl"
    if p.exists():
        for line in p.open():
            rec = json.loads(line)
            t = rec["t"].replace("/", ".").replace(".py::", "::")
            q[t].append(rec)
    return q


print("## Runs\n")
print("| run | passed | failed | losses vs sympy | fixed vs old | regressions vs current |")
print("|---|---:|---:|---:|---:|---:|")
L_old = set(losses("old")) if "old" in res else set()
for r in RUNS:
    if r not in res:
        continue
    c = Counter(res[r].values())
    ls = set(losses(r))
    reg = [t for t in res.get("current", {}) if ok(res["current"], t) and not ok(res[r], t)]
    print(f"| {r} | {sum(c[o] for o in PASSING)} | {c['failed'] + c['error']} | {len(ls)} | "
          f"{len(L_old - ls)} | {len(reg)} |")
    for t in reg:
        print(f"|  regression: {t} | | | | | |")
    new = sorted(ls - L_old)
    for t in new:
        print(f"|  new loss vs old: {t} | | | | | |")

print("\n## Losses of old, by family and status\n")
qs = {r: qlog(r) for r in res}
fams = Counter()
print("| test | family | scope | relations asked | " + " | ".join(r for r in RUNS if r in res) + " |")
print("|---|---|---|---|" + "---|" * len(res))
for t in sorted(L_old, key=lambda t: (family(t), t)):
    fam = family(t)
    fams[fam] += 1
    c = cnts["old"].get(t, {})
    scope = ",".join(f"{k}x{v}" for k, v in sorted(c.items()) if k in ("relation", "matrix", "custom", "other", "undecided"))
    rs = set()
    for rec in qs.get("old", {}).get(t, []):
        rs |= rels(rec["p"]) | rels(rec["a"])
    status = ["pass" if ok(res[r], t) else "FAIL" for r in RUNS if r in res]
    print(f"| {t.split('::')[1]} | {fam} | {scope} | {','.join(sorted(rs))} | " + " | ".join(status) + " |")
print("\nfamilies:", dict(fams))
