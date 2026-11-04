"""cover.py WL OUT.json: one recorded pass with counters per query and per engine entry; no answer changes (digest printed).

Monkeypatches only. Counts calls into each part, whether Session/knowledge/adapter Python ran while a solver search was on the
stack (a live callback a one-call-per-query boundary would have to serve), and classifies each session and query.
"""
import hashlib, inspect, json, os, sys
wl, out = sys.argv[1:3]
from evalbench.common import workload
from satassume import sympy_api, engine as E, relations as R
from satassume.sat import solver as SV, theory as TH
from satassume.theories.lra import lra as L, lra_adapter as LA
from satassume.theories.euf import euf as EU, euf_adapter as EA
from satassume.theories import transfer as TR
if wl == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(424242)
else:
    pairs = workload(wl)

class S:
    c = {}          # counters of the current query
    search = 0      # depth of solver entry calls on the stack
    sess = []       # Session objects of the current query
    entry = 0

def wrap(cls, name, tag, search=False, part=None):
    raw = inspect.getattr_static(cls, name)
    if not inspect.isfunction(raw):
        return
    def w(*a, _f=raw, _t=tag, _s=search, _p=part, **k):
        c = S.c
        c[_t] = c.get(_t, 0) + 1
        if S.search and _p:
            kk = _p + "_in_search"
            c[kk] = c.get(kk, 0) + 1
        if _s:
            if S.search == 0:
                c["solver_top"] = c.get("solver_top", 0) + 1
            S.search += 1
            try:
                return _f(*a, **k)
            finally:
                S.search -= 1
        return _f(*a, **k)
    setattr(cls, name, w)

def wrap_all(cls, tag, part=None, skip=()):
    for n, v in list(vars(cls).items()):
        if inspect.isfunction(v) and n not in skip and n not in ("__init__", "__hash__", "__eq__", "__repr__"):
            wrap(cls, n, tag, part=part)

# solver entries that may run a search or theory hooks
for n in ("propagate", "implied", "consistent", "entails", "entails_all", "mention", "release"):
    if hasattr(SV.Solver, n):
        wrap(SV.Solver, n, "solver." + n, search=n in ("propagate", "implied", "consistent", "entails", "entails_all"))
for n in ("add_clause", "new_var", "register_atom", "register_block", "attach_theory"):
    if hasattr(SV.Solver, n):
        wrap(SV.Solver, n, "solver." + n)
# every Solver method called from outside the solver (Session, Relations, adapters): what a per-call boundary would cross
class O:
    depth = 0
for n, v in list(vars(SV.Solver).items()):
    if inspect.isfunction(v) and n != "__init__":
        def outer(*a, _f=None, _n="x." + n, **k):
            if O.depth == 0:
                S.c[_n] = S.c.get(_n, 0) + 1
            O.depth += 1
            try:
                return _f(*a, **k)
            finally:
                O.depth -= 1
        outer.__kwdefaults__ = {"_f": getattr(SV.Solver, n), "_n": "x." + n}
        setattr(SV.Solver, n, outer)
# does a theory ever say anything back: conflict from assert or check, or a propagation
def said(cls, tag):
    for n in ("assert_lit", "check", "propagate"):
        if hasattr(cls, n):
            f = getattr(cls, n)
            def w(*a, _f=f, _n=n, **k):
                r = _f(*a, **k)
                hit = bool(r) if _n == "assert_lit" else (r is not None and r != [] and r != () and not (_n == "check" and r[0] is True))
                if hit:
                    S.c[tag + ".said"] = S.c.get(tag + ".said", 0) + 1
                S.c[tag + "." + _n] = S.c.get(tag + "." + _n, 0) + 1
                return r
            setattr(cls, n, w)
said(L.LRATheory, "lra"); said(EU.EUFTheory, "euf"); said(TR.TransferTheory, "transfer")
wrap_all(L.LRATheory, "lra")
wrap_all(EU.EUFTheory, "euf")
wrap_all(TR.TransferTheory, "transfer")
wrap_all(TH.EqualitySharing, "sharing")
wrap_all(R.Relations, "relations", part="relations")
wrap_all(LA.LRAAdapter, "lra_adapter", part="adapter")
wrap_all(EA.EUFAdapter, "euf_adapter", part="adapter")
for n in ("_visit", "_compile_patterns", "_compile", "_compile_pending", "_custom", "escalate", "discover"):
    wrap(E.Session, n, "session." + n, part="session")
for n in ("is_", "is_many", "ask", "verdict", "_is_custom", "_build_context"):
    wrap(E.Engine, n, "engine." + n)

# sessions and their kinds
oinit = E.Session.__init__
def sinit(self, *a, **k):
    S.c["sessions"] = S.c.get("sessions", 0) + 1
    S.sess.append(self)
    return oinit(self, *a, **k)
E.Session.__init__ = sinit

def kinds(s):
    """One session's theories at the end of its life."""
    k = set()
    for t in s.solver.theories():
        if isinstance(t, L.LRATheory):
            n_atoms = len(getattr(t, "_atoms", ()) or ()) if hasattr(t, "_atoms") else 1
            k.add("lra_const" if t._fields else "lra_rat")
        elif isinstance(t, EU.EUFTheory):
            k.add("euf")
        elif isinstance(t, TR.TransferTheory):
            k.add("transfer")
        else:
            k.add(type(t).__name__)
    if getattr(s, "relations", None) is not None:
        k.add("glue")
    return k

res = []
for i, (p, a) in enumerate(pairs):
    S.c = {}; S.sess = []; S.search = 0
    try:
        r = sympy_api.ask(p, a)
        if r is not None and r is not True and r is not False:
            r = "non-bool " + repr(r)
    except ValueError:
        r = "ValueError"
    except Exception as e:
        r = "raise " + type(e).__name__
    S.c["session_kinds"] = sorted("+".join(sorted(kinds(s))) for s in S.sess)
    res.append(dict(q=i, ans=r, c=S.c))
d = hashlib.sha256(json.dumps([x["ans"] for x in res]).encode()).hexdigest()[:16]
print(wl, "digest", d, "n", len(res))
json.dump(res, open(out, "w"))
