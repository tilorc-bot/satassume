"""Prototype counts: links deferred/built per None / definite query session and
per set check; solves; answer digest.  Usage: protocount.py dev | fuzz SEED"""
import sys, json, collections, hashlib
from satassume import engine as E, relations as R
L = R.LSTATS
ROWS = collections.defaultdict(collections.Counter)

def snap():
    return dict(L)

def diff(a, b):
    return {k: b.get(k, 0) - a.get(k, 0) for k in b if b.get(k, 0) != a.get(k, 0)}

_cc0 = E.Engine._complete_check
def _cc(s, lits):
    a = snap(); v = _cc0(s, lits); d = diff(a, snap())
    rel = s.relations
    if rel is not None and (rel.unbuilt or d.get("built")):
        r = ROWS["check"]; r["n"] += 1; r["pending"] += len(rel.unbuilt) + d.get("built", 0)
        for k, x in d.items(): r[k] += x
    return v
E.Engine._complete_check = staticmethod(_cc)

_ask0 = E.Engine._ask
def _ask(self, s, lits, prop, contextual):
    a = snap(); r = _ask0(self, s, lits, prop, contextual); d = diff(a, snap())
    rel = s.relations
    if rel is not None and (rel.unbuilt or d.get("built") or rel.link_sel):
        row = ROWS["none" if r is None else "definite"]; row["n"] += 1
        row["links"] += len(rel.link_sel); row["unbuilt_end"] += len(rel.unbuilt)
        for k, x in d.items(): row[k] += x
    return r
E.Engine._ask = _ask

from evalbench.common import workload, ask_all
from satassume import sympy_api
if sys.argv[1] == "fuzz":
    from evalbench.fuzz import queries
    pairs = queries(int(sys.argv[2]))
else:
    pairs = workload(sys.argv[1])
ans = ask_all(sympy_api.ask, pairs)
print(json.dumps(dict(digest=hashlib.sha256(json.dumps(ans).encode()).hexdigest()[:16],
                      total=L, rows=ROWS), default=dict))
json.dump(ans, open("/tmp/claude-1000/-home-tilo-dev-satassume/609d1f5c-0bec-4d50-ab36-e4366bfeb14d/scratchpad/ans-%s-%s.json" % (sys.argv[1], R.LAZY), "w"))
