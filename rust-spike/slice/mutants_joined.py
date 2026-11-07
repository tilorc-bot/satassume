"""mutants_joined.py API NESTED LIVE STEP3: one table of every mutant's score per column, from the sweep tables as written. Prints markdown.
Stops if a base row isn't "no" or a cell reads as a hang. A cell is "c" (caught), "no", or the hand-written text step 3 has."""
import sys


def rows(path, after=None):
    out = {}
    lines = open(path).read().split("\n")
    if after:
        lines = lines[lines.index(after) + 1:]
    for line in lines:
        if after and out and not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] not in ("#", "---") and not set(cells[0]) <= set("-:"):
            out[cells[0]] = cells
    return out


def mark(c):
    if c == "no":
        return "no"
    if "hang" in c or "crash" in c or c == "...":
        sys.exit(f"cell can't be scored: {c}")
    return "c"


api, nested, live = (rows(p) for p in sys.argv[1:4])
step3 = rows(sys.argv[4], "## The 10 mutants")
for t, first in ((api, 3), (nested, 2), (live, 3), (step3, 3)):
    assert all(c == "no" for c in t["base"][first:] if c != "..."), t["base"]
print("### Boundary mutants, step 4\n")
print("c: caught. API columns are the fuzzer: digest and state on step 1's corpus, then answers and state on fuzz sessions. Live columns are the real engine.\n")
print("| # | mutant | API digest | API state | API fuzz answers | API fuzz state | nested | live dev answers | live fuzz answers | live dev state | live fuzz state | columns catching |")
print("|---|---|---|---|---|---|---|---|---|---|---|---:|")
uncaught, nolive = [], []
for k in [str(i) for i in range(10, 35)]:
    cs = [mark(c) for c in api[k][3:7]] + [mark(nested[k][2])] + [mark(c) for c in live[k][3:7]]
    n = cs.count("c")
    if not n:
        uncaught.append(k)
    if "c" not in cs[5:]:
        nolive.append(k)
    print(f"| {k} | {api[k][1]} | " + " | ".join(cs) + f" | {n} |")
print(f"\nNot caught by any column: {', '.join(uncaught) or 'none'}. Not caught by a live column: {', '.join(nolive)} ({len(nolive)} of 25).\n")
print("### The 10 solver mutants, step 3's sweep on the same crate\n")
print("| # | mutant | dev digest | fuzz digest | dev state | fuzz state | API answers | API state |")
print("|---|---|---|---|---|---|---|---|")
for k in [str(i) for i in range(10)]:
    print(f"| {k} | {step3[k][1]} | " + " | ".join(step3[k][3:9]) + " |")
