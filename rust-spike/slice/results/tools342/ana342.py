"""ana342.py DIR BASE NEW (sa-port-342): the tables from cnt342.py's rows DIR/SHA-WL-CAP[-nob].json (CAP 32 or 0):
the reasons table of BASE and NEW per workload and cap; the pi class (BASE: `atom: constant pi`; NEW: compiled with
values in Q[pi]) with what NEW makes of it, with and without (2b); and the checks the comparison rests on: the same
answers and the same calls of the check, in the same order, in every run."""
import json, sys
from collections import Counter
d, base, new = sys.argv[1:4]
L = lambda sha, wl, cap, nob="": json.loads(open(f"{d}/{sha}-{wl}-{cap}{nob}.json").read())
for wl in ("dev", "fuzz"):
    runs = {(s, c, n): L(s, wl, c, n) for s, c, n in [(base, 32, ""), (base, 0, ""), (new, 32, ""), (new, 0, ""), (new, 32, "-nob"), (new, 0, "-nob")]}
    one = runs[(base, 32, "")]
    for k, r in runs.items():
        assert r["witness"] is True and r["cap"] == k[1] and r["nob"] == bool(k[2]) and f"tree-{k[0]}" in r["tree"], k
    same = all(r["digest"] == one["digest"] and [c[0] for c in r["rows"]] == [c[0] for c in one["rows"]] for r in runs.values())
    print(f"## {wl}: {one['n']} queries, {one['nones']} None answers, {one['fires']} calls of the check; answers and calls equal in all six runs: {same}")
    print("| why | base cap 32 | new cap 32 | base uncapped | new uncapped |")
    print("|---|---|---|---|---|")
    cols = [runs[(base, 32, "")]["why"], runs[(new, 32, "")]["why"], runs[(base, 0, "")]["why"], runs[(new, 0, "")]["why"]]
    keys = sorted(set().union(*cols), key=lambda k: (k != "certified", -max(c.get(k, 0) for c in cols), k))
    for k in keys:
        print("|", k, "|", " | ".join(str(c.get(k, 0)) for c in cols), "|")
    for cap in (32, 0):
        b, n, nb = runs[(base, cap, "")]["rows"], runs[(new, cap, "")]["rows"], runs[(new, cap, "-nob")]["rows"]
        pib = [i for i, c in enumerate(b) if c[3] == "atom: constant pi"]
        pin = [i for i, c in enumerate(n) if c[5]]
        cls = sorted(set(pib) | set(pin))
        print(f"pi class, cap {cap or 'none'}: base `atom: constant pi` {len(pib)} calls; new compiled in Q[pi] {len(pin)}; "
              f"in one and not the other {len(set(pib) ^ set(pin))}")
        print("  new, by reason:", dict(Counter(n[i][3] for i in cls).most_common()))
        print("  new without (2b), by reason:", dict(Counter(nb[i][3] for i in cls).most_common()),
              "; _PiPoly roots dropped", sum(nb[i][6] for i in cls), "in", sum(1 for i in cls if nb[i][6]), "calls")
        print("  certified in the class: with (2b)", sum(n[i][1] for i in cls), ", without", sum(nb[i][1] for i in cls),
              "; certified outside the class: base", sum(c[1] for i, c in enumerate(b) if i not in set(cls)),
              ", new", sum(c[1] for i, c in enumerate(n) if i not in set(cls)),
              "; calls outside the class whose row changed", sum(1 for i in range(len(b)) if i not in set(cls) and b[i][:5] != n[i][:5]))
    print()
