"""classes.py: per-test classes for every test that fails under ids live (serial or xdist) and not in base. Writes results/suite-classes.tsv; prints the summary."""
import collections
import re
import sys

sys.path.insert(0, ".")
from classify import load

R = {n: load(n) for n in "base live liveser eqonly hashonly repo all allser allrand repox3 sax3".split()}
b = set(R["base"])
u = (set(R["live"]) | set(R["liveser"])) - b
rows = []
for t in sorted(u):
    src = R["liveser"].get(t) or R["live"][t]
    timing = re.search(r"fast|linear_time|performance", t) and "<" in src[0]
    if t in R["all"] and t in R["allser"] and t in R["allrand"]:
        c = "real: int vs Integer key"
    elif timing:
        c = "artifact: wall-clock limit, wrappers"
    elif t not in R["repo"]:
        c = "artifact: container crosses test/satassume"
    elif t not in R["repox3"]:
        c = "artifact: container crosses satassume/SymPy (3 named functions)"
    elif t not in R["all"] and t not in R["allser"] and t not in R["allrand"]:
        c = "cleared only by all frames"
    else:
        c = "unexplained"
    order = "both" if t in R["live"] and t in R["liveser"] else "xdist only" if t in R["live"] else "serial only"
    rows.append((c, order, t))
with open("results/suite-classes.tsv", "w") as f:
    f.write("class\tlive failed in\ttest\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
print(len(rows), collections.Counter(r[0] for r in rows).most_common())
print(collections.Counter((r[0][:30], r[1]) for r in rows).most_common())
left = [r[2] for r in rows if r[0] in ("cleared only by all frames", "unexplained")]
for t in left[:16]:
    print("LEFT", t.split(".")[-1][:60], "|", R["repox3"].get(t, ("?",))[0].splitlines()[0][:100])
print("repox3 beyond base", len(set(R["repox3"]) - b), "not in union", len(set(R["repox3"]) - b - u), "sax3 beyond base", len(set(R["sax3"]) - b), "of union", len(set(R["sax3"]) & u), "new", len(set(R["sax3"]) - b - u))
print("hashonly of union", len(set(R["hashonly"]) & u), "new", [x.split('::')[-1][:40] for x in set(R["hashonly"]) - b - u][:8])
