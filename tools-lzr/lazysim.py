"""Bound for lazy links: simulate model-based link building in each query's
session (instrumentation only).  Usage: lazysim.py WORKLOAD [fuzz-seed]"""
import sys, json, collections
from sympy import S
from satassume import relations as R, engine as E
from satassume.relations import relation_atom

ST = collections.Counter()
ROWS = []

_link0 = R.Relations._link
def _link(self, e):
    _link0(self, e)
    s = self.session
    sel = self.link_sel[e]
    cv = s.table.custom
    self.__dict__.setdefault("_sim", {})[sel] = (
        s.var("extended_positive", e), s.var("extended_negative", e), s.var("zero", e),
        cv[relation_atom("lt", S.Zero, e)], cv[relation_atom("lt", e, S.Zero)],
        cv[relation_atom("eq", e, S.Zero)])
R.Relations._link = _link

def _capture(fn):
    def w(self, *a):
        cap = []
        emit = self.emit
        self.emit = cap.append
        try:
            r = fn(self, *a)
        finally:
            del self.emit
        self.__dict__.setdefault("_cap", []).extend(cap)
        return r
    return w
E.Session._set_glue = _capture(E.Session._set_glue)
E.Session._group_sel = _capture(E.Session._group_sel)

_al0 = E.Session.assumption_lits
def assumption_lits(self, prop=None):
    lits = _al0(self, prop)
    cap = getattr(self, "_cap", ())
    units = {c[0] for c in cap if len(c) == 1}
    imp = collections.defaultdict(set)
    for c in cap:
        if len(c) == 2:
            imp[-c[0]].add(c[1])
    out = []
    for x in lits[:1] + sorted(units) + lits[1:]:
        for y in (sorted(imp[x]) if x in imp else [x]):
            if y not in out:
                out.append(y)
    return out
E.Session.assumption_lits = assumption_lits

_emit0 = E.Session.emit
def _emit(self, clause):
    rel = self.relations
    if rel is not None and rel.link_sel:
        rev = rel.__dict__.get("_rev")
        if rev is None or len(rev) != len(rel.link_sel):
            rev = rel._rev = set(rel.link_sel.values())
        cl = rel.__dict__.setdefault("_simcl", collections.defaultdict(list))
        for l in clause:
            if l < 0 and -l in rev:
                cl[-l].append([x for x in clause if x != l])
    return _emit0(self, clause)
E.Session.emit = _emit

def lazy(s, base, L, extra, cnt):
    """Model-based loop: (sat?, built link selectors)."""
    sim, solver = s.relations._sim, s.solver
    built = set()
    for it in range(50):
        cnt["solves"] += 1
        if not solver.solve(base + sorted(built) + extra):
            return False, built
        M = solver.model()
        def dis(sel, M=M):
            return any(not any(M.get(abs(x)) == (x > 0) for x in c) for c in s.relations._simcl[sel])
        D = [x for x in L - built if dis(x)]
        if not D:
            return True, built
        # repair: make every unbuilt link agree with M's unary side
        agree, own = [], {}
        for x in sorted(L - built):
            p, n, z, gt, lt, eq = sim[x]
            for u, t in ((p, gt), (n, lt), (z, eq)):
                l = t if M.get(u) else -t
                agree.append(l)
                own[l] = x
        cnt["solves"] += 1
        if solver.solve(base + sorted(built) + extra + agree):
            M2 = solver.model()
            D2 = [x for x in L - built if dis(x, M2)]
            if not D2:
                return True, built
            built.update(D2)
            cnt["fallback"] += 1
            continue
        core = {own[l] for l in solver.conflict() if l in own}
        if not core:
            built.update(D)
            cnt["fallback"] += 1
        else:
            built.update(core)
    cnt["cap"] += 1
    return None, L

_ask0 = E.Engine._ask
def _ask(self, s, lits, proposition, contextual):
    r = _ask0(self, s, lits, proposition, contextual)
    rel = s.relations
    if rel is None or not getattr(rel, "_sim", None):
        return r
    try:
        q = s.prepare_query(proposition)
        full = s.assumption_lits(proposition)
        if type(q) is tuple:
            ST["skip_derived"] += 1
            return r
        sim = rel._sim
        L = {x for x in full if x in sim}
        base = [x for x in full if x not in sim]
        cnt = collections.Counter()
        setL = {x for x in s.assumption_lits(None) if x in sim} if s.sel else set()
        ok_set, b_set = lazy(s, [x for x in s.assumption_lits(None) if x not in sim], setL, [], cnt) if s.sel else (True, set())
        sp, bp = lazy(s, base, L, [q], cnt)
        sn, bn = lazy(s, base, L, [-q], cnt)
        ans = None if (sp and sn) else (True if sp else False if sn else "ValueError")
        built = b_set | bp | bn
        ROWS.append(dict(p=str(proposition), a=str(s.assumption_formula), links=len(rel._sim), active=len(L), built=len(built),
                         real=r, sim=ans, solves=cnt["solves"], fb=cnt["fallback"], cap=cnt["cap"]))
    except Exception as e:  # noqa
        ST["sim_error " + type(e).__name__] += 1
    return r
E.Engine._ask = _ask

CHK = []
_cc0 = E.Engine._complete_check
def _cc(s, lits):
    v = _cc0(s, lits)
    rel = s.relations
    if rel is not None and getattr(rel, "_sim", None):
        cnt = collections.Counter()
        L = {x for x in lits if x in rel._sim}
        ok, b = lazy(s, [x for x in lits if x not in rel._sim], L, [], cnt)
        CHK.append(dict(a=str(s.assumption_formula), v=v, sim=ok, active=len(L), built=len(b)))
    return v
E.Engine._complete_check = staticmethod(_cc)

from evalbench.common import workload, ask_all
from satassume import sympy_api
if sys.argv[1] == "pinned":
    from sympy import besselj, Q, symbols
    x, y, z = symbols("x y z"); bj = lambda t: besselj(1, t)
    a = Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.nonzero(bj(x)) & Q.positive(z - 1) & Q.negative(z - 3)
    pairs = [(p, a) for p in (Q.gt(z, 0), Q.lt(0, z), Q.positive(z), Q.zero(bj(x)))] + [(Q.zero(bj(x)), Q.zero(x) & Q.zero(y) & Q.zero(bj(y)) & Q.positive(z - 1) & Q.negative(z - 3))]
elif sys.argv[1] == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(sys.argv[2]))
else:
    pairs = workload(sys.argv[1])
ans = ask_all(sympy_api.ask, pairs)
import hashlib
print(json.dumps(dict(digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16], st=ST)))
json.dump(ROWS, open("rows-%s.json" % sys.argv[1], "w"))
n = len(ROWS)
tl = sum(x["links"] for x in ROWS); ta = sum(x["active"] for x in ROWS); tb = sum(x["built"] for x in ROWS)
mism = [x for x in ROWS if x["real"] != x["sim"]]
print(f"sessions {n} links {tl} active {ta} built {tb} ({100*tb/max(ta,1):.1f}%) mismatch {len(mism)} caps {sum(x['cap'] for x in ROWS)} fallbacks {sum(x['fb'] for x in ROWS)}")
print("mismatch sample", [(x['real'], x['sim']) for x in mism[:10]])

bad = [c for c in CHK if (c["v"] == "inconsistent") != (c["sim"] is False)]
print("checks", len(CHK), "active", sum(c["active"] for c in CHK), "built", sum(c["built"] for c in CHK), "check mismatches", len(bad), bad[:5])
if sys.argv[1] == "pinned": print(ans, CHK)
