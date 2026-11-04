"""hand.py: shadow on pairs the workloads may not reach, called from a satassume-looking frame; then answers for queries
over those objects, base vs each mode (run as: hand.py MODE). Prints a table row per pair and the answers."""
import json
import sys

import ids_core
from sympy import Dummy, Eq, Float, Integer, Q, Rational, S, Symbol, Wild, oo, pi, sqrt
from satassume import sympy_api

mode = sys.argv[1]
x, xr, xp, xr2 = Symbol("x"), Symbol("x", real=True), Symbol("x", positive=True), Symbol("x", real=True)
y = Symbol("y")
d1, d2 = Dummy("x"), Dummy("x")
PAIRS = [("Integer 1 / Float 1.0", Integer(1), Float(1.0)), ("Integer 0 / Float 0.0", Integer(0), Float(0.0)),
         ("Rational 1/2 / Float 0.5", Rational(1, 2), Float(0.5)), ("Float prec 15 / 30", Float(0.5, 15), Float(0.5, 30)),
         ("Float 1.5 same prec, two objects", Float(1.5), Float(1.5)), ("Float 0.0 / -0.0", Float(0.0), Float(-0.0)),
         ("Integer 1 / int 1", Integer(1), 1), ("Integer 1 / True", Integer(1), True), ("Integer 1 / float 1.0", Integer(1), 1.0),
         ("Float 0.5 / float 0.5", Float(0.5), 0.5), ("Rational 1/2 / float 0.5", Rational(1, 2), 0.5),
         ("S.true / True", S.true, True), ("S.true / int 1", S.true, 1), ("S.true / Integer 1", S.true, Integer(1)),
         ("S.false / Integer 0", S.false, Integer(0)), ("Symbol x / x real", x, xr), ("x real / x real (cached)", xr, xr2),
         ("x real / x positive", xr, xp), ("Dummy x / Dummy x", d1, d2), ("Symbol x / Dummy x", x, d1), ("Symbol x / str x", x, "x"),
         ("x+1 / x+1.0", x + 1, x + Float(1.0)), ("2*x / 2.0*x", 2 * x, Float(2.0) * x), ("x+1 built twice", x + 1, 1 + x),
         ("Eq(x,y) / Eq(y,x)", Eq(x, y), Eq(y, x)), ("Q.positive(x) twice", Q.positive(x), Q.positive(x)),
         ("Q.lt(x,y) / Q.gt(y,x)", Q.lt(x, y), Q.gt(y, x)), ("oo / float inf", oo, float("inf")), ("pi / float pi", pi, 3.141592653589793),
         ("sqrt(2) / 2**(1/2)", sqrt(2), Integer(2) ** Rational(1, 2))]
if mode != "base":
    ids_core.install(mode)
# compile the comparisons as if from a satassume file, so the wrappers treat them as sites
g = {}
exec(compile("def eq(a,b): return a == b\ndef h(a): return hash(a)\n", ids_core.SA + "/_hand_site.py", "exec"), g)
rows = []
for name, a, b in PAIRS:
    before = sum(v[0] for k, v in ids_core.T.bad.items() if k[0] != "true_crosstype")
    r = g["eq"](a, b)
    rr = g["eq"](b, a)
    after = sum(v[0] for k, v in ids_core.T.bad.items() if k[0] != "true_crosstype")
    rows.append([name, bool(r), bool(rr), after - before])
qs = [(Q.positive(xp), True), (Q.real(xr), True), (Q.positive(xr), True), (Q.positive(x + 1), Q.positive(x)), (Q.positive(x + Float(1.0)), Q.positive(x)),
      (Q.eq(x, 1), Q.eq(x, Float(1.0))), (Q.eq(x, Float(1.0)), Q.eq(x, 1)), (Q.gt(x, Rational(1, 2)), Q.gt(x, Float(0.5))), (Q.gt(x, Float(0.5)), Q.gt(x, Rational(1, 2))),
      (Q.positive(d1), Q.positive(d2)), (Q.positive(xr), Q.positive(x)), (Q.lt(x, y), Q.gt(y, x)), (Q.eq(x, y) , Q.eq(y, x)),
      (Q.zero(x - Float(0.0)), Q.zero(x)), (Q.gt(x, Float(0.5, 15)), Q.gt(x, Float(0.5, 30)))]
ans = []
for p, a in qs:
    try:
        ans.append(sympy_api.ask(p, a))
    except Exception as e:  # noqa: BLE001
        ans.append("raise " + type(e).__name__)
print(json.dumps(dict(mode=mode, rows=rows, answers=ans, bad=[(k[0], k[1]) for k in ids_core.T.bad if k[0] != "true_crosstype"])))
