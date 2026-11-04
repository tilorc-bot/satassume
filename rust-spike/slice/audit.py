"""audit.py WL SHUFFLE OUT.json: one pass with monkeypatches only (run under a chosen PYTHONHASHSEED; SHUFFLE 0 = recorded query order).
Records per query: answer, re-entrant engine queries, and per solver a digest of its add_clause sequence, its register_atom sequence
(theory, var, str(payload)) and LRA propagate outputs. At the end: registered extensions, and per cone object its kids and cone.
compare with auditcmp.py."""
import hashlib, json, random, sys
from collections import Counter
wl, shuf, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
from evalbench.common import workload
from sympy import srepr
from satassume import sympy_api, engine as E
from satassume.sat import solver as SV
from satassume.theories.lra import lra as L
from satassume.knowledge import extensions as X
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)
order = list(range(len(pairs)))
if shuf:
    random.Random(shuf).shuffle(order)

class S:
    dig = {}   # id(solver) -> [clauses hash, atoms hash, lra hash, n atoms]
    q = Counter(); lra = None
G = Counter(); CALLERS = Counter(); CUSTOM = Counter()
def h(sv):
    d = S.dig.get(id(sv))
    if d is None:
        d = S.dig[id(sv)] = [hashlib.sha1(), hashlib.sha1(), hashlib.sha1(), 0, sv]
    return d
oac = SV.Solver.add_clause
def ac(self, *a, **k):
    h(self)[0].update(repr(a).encode()); return oac(self, *a, **k)
SV.Solver.add_clause = ac
ora = SV.Solver.register_atom
def ra(self, theory, var, payload, *a, **k):
    d = h(self); d[1].update(f"{type(theory).__name__}|{var}|{payload}\n".encode()); d[3] += 1
    return ora(self, theory, var, payload, *a, **k)
SV.Solver.register_atom = ra
olp = L.LRATheory.propagate
def lp(self):
    r = olp(self)
    if r:
        S.lra = S.lra or hashlib.sha1(); S.lra.update(repr(r).encode())
    return r
L.LRATheory.propagate = lp
for name in ("is_", "is_many"):
    o = getattr(E.Engine, name)
    def w(self, node, *a, _o=o, _n=name, **k):
        G[_n] += 1
        if self._constructing:
            G[_n + "_reentrant"] += 1; S.q["reent"] += 1
            f = sys._getframe(1)
            CALLERS[f"{f.f_code.co_filename.split('satassume/')[-1]}:{f.f_lineno}"] += 1
            if node in self._constructing:
                G[_n + "_hit_constructing"] += 1
        return _o(self, node, *a, **k)
    setattr(E.Engine, name, w)
oc = E.Engine._is_custom
def cu(self, node, pred):
    CUSTOM[str(pred)] += 1; return oc(self, node, pred)
E.Engine._is_custom = cu
off = X.Extensions.facts_for
def ff(self, *a, **k):
    G["facts_for"] += 1; r = off(self, *a, **k)
    if r: G["facts_for_nonempty"] += 1
    return r
X.Extensions.facts_for = ff

res = [None] * len(pairs)
for i in order:
    p, a = pairs[i]
    S.dig = {}; S.q = Counter(); S.lra = None
    try:
        r = sympy_api.ask(p, a); r = r if r in (True, False, None) else repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    res[i] = dict(a=r, sess=[(d[0].hexdigest()[:12], d[1].hexdigest()[:12], d[3]) for d in S.dig.values()],
                  lra=S.lra.hexdigest()[:12] if S.lra else "", reent=S.q["reent"])
eng = sympy_api.default_engine() if callable(getattr(sympy_api, "default_engine", None)) else sympy_api.default_engine
ext = eng._extensions
def key(o):
    try:
        return srepr(o)
    except Exception:
        return repr(o)
kids = {key(o): (sorted(key(x) for x in k), w) for o, (k, w) in eng._kids.items()}
cones = {key(o): (None if c is None else sorted(key(x) for x in c), w, rel) for o, (c, w, rel) in eng._cones.items()}
ei = None if ext is None else dict(type=type(ext).__name__, has_node_facts=ext.has_node_facts,
      attrs={n: len(v) for n, v in vars(ext).items() if hasattr(v, "__len__")}, default=len(getattr(X, "_DEFAULT", ()) or ()))
qc = {key(k): (v[0] is None, v[1], v[2]) for k, v in eng._qcones.items()} if False else len(eng._qcones)
json.dump(dict(res=res, G=G, callers=CALLERS, custom=CUSTOM, ext=ei, kids=kids, cones=cones, n_qcones=qc,
               specs=[getattr(s, "name", str(s)) for s in (eng._relation_specs or ())], glue_memo=sorted(eng._glue_adapters)), open(out, "w"))
print(wl, shuf, "digest", hashlib.sha256(json.dumps([x["a"] for x in res]).encode()).hexdigest()[:16], dict(G), "ext", ei)
