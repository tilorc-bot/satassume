"""hv344.py WL (sa-port-344, issue 323; counts, not times; py mode): for each call of the witness check on budget or
wiring (loaded as pc343.py loads them), what _holds returned over the points it decided: None (the assumptions do not
hold at the point, or a value is not defined there), True or False (the proposition's value at a point where they
hold). Printed per kind of call: certified, fall-through at the cap (32 points), other fall-through."""
import collections, importlib, json, os, sys
S = os.environ["SLICE_DIR"]
sys.path.append(S)
from satassume import sympy_api, witness
wl = sys.argv[1]
pairs = importlib.import_module({"budget": "budget_wl", "wiring": "knowledge_wiring_wl"}[wl]).queries()
real_w, real_h = witness.witnesses, witness._holds
cur = []
rows = []
def holds(*a):
    r = real_h(*a)
    cur.append(r)
    return r
def witnesses(p, a, eng=None):
    del cur[:]
    r = real_w(p, a, eng)
    c = collections.Counter(cur)
    rows.append((r is not None, len(cur), c[None], c[True], c[False]))
    return r
witness.witnesses, witness._holds = witnesses, holds
for p, a in pairs:
    try:
        sympy_api.ask(p, a)
    except ValueError:
        pass
out = collections.OrderedDict()
for cert, n, no, t, f in rows:
    kind = "certified" if cert else "cap" if n >= 32 else "other"
    if kind == "cap":
        kind += ": no point satisfies the assumptions" if t + f == 0 else ": proposition True at every satisfying point" if f == 0 else ": proposition False at every satisfying point" if t == 0 else ": both values seen"
    g = out.setdefault(kind, [0, 0, 0, 0, 0])
    for i, v in enumerate((1, n, no, t, f)):
        g[i] += v
print(json.dumps(dict(wl=wl, calls=len(rows), witness=witness.ENABLED[0], cap=witness.CAP[0],
                      kinds={k: dict(calls=v[0], points=v[1], none=v[2], true=v[3], false=v[4]) for k, v in out.items()}), indent=1))
