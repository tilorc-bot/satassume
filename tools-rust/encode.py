"""enc mode of rc.py: what building the data that crosses the boundary costs, per boundary
call, in Python. Run and timed at each outermost boundary call; no answer depends on it.

The encoding is a flat integer table, one row per distinct expression node:
class id, number of arguments, argument ids; a Rational carries p and q, a Symbol a
global id, any other atom just its class. A formula is a pre-order of operator ids and,
for an atom, predicate id and expression ids. The table ends as bytes (one copy).

  q      the query's own formulas, a fresh table for this call (no memo across calls).
  intern the same, with one process-wide table: only nodes never seen before are written,
         and the atoms' roots still go through one dict probe each.
  cl     the closure: every node and atom the call's sessions actually touched, derived
         ones included, fresh table for this call. A lower bound on what a fully
         resolved-in-advance session needs, since it holds what search and demand reached,
         not what an eager enumeration of the cone would reach; patterns and linear forms
         are not in it. Measured after the call (the set is only known then).
"""
import sys
import time
from array import array

from satassume.engine import Engine
from satassume.sat.formula import Formula, P
from sympy import Basic, Rational, Symbol

pc = time.perf_counter
MASK = (1 << 62) - 1
CLS = {}
SYM = {}
PRED = {}
OP = {}


class St:
    t = {"q": None, "intern": None, "cl": None}
    nodes = {"q": 0, "intern": 0, "cl": 0}
    bytes_ = {"q": 0, "intern": 0, "cl": 0}
    calls = 0
    sessions = []
    snaps = None
    global_memo = {}


def enc_expr(e, memo, out):
    i = memo.get(e)
    if i is not None:
        return i
    if isinstance(e, Basic):
        cid = CLS.get(type(e))
        if cid is None:
            cid = CLS[type(e)] = len(CLS)
        args = e.args
        if args:
            ids = [enc_expr(a, memo, out) for a in args]
            out.append(cid)
            out.append(len(ids))
            out.extend(ids)
        elif isinstance(e, Rational):
            out.extend((cid, 0, int(e.p) & MASK, int(e.q) & MASK))
        elif isinstance(e, Symbol):
            s = SYM.get(e)
            if s is None:
                s = SYM[e] = len(SYM)
            out.extend((cid, 0, s))
        else:
            out.extend((cid, 0))
    elif type(e) is tuple:
        ids = [enc_expr(a, memo, out) for a in e]
        out.append(-1)
        out.append(len(ids))
        out.extend(ids)
    else:                   # a predicate name or other opaque payload
        out.extend((-2, hash(e) & MASK))
    i = memo[e] = len(memo)
    return i


def enc_formula(f, memo, out, roots):
    if type(f) is P:
        p = PRED.get(f.pred)
        if p is None:
            p = PRED[f.pred] = len(PRED)
        roots.append(p)
        roots.append(enc_expr(f.expr, memo, out))
    elif isinstance(f, Formula):
        o = OP.get(type(f))
        if o is None:
            o = OP[type(f)] = len(OP)
        roots.append(-o - 1)
        roots.append(len(f.args))
        for a in f.args:
            enc_formula(a, memo, out, roots)
    else:
        roots.append(-1000)


def _finish(out, roots):
    return array("q", out).tobytes(), array("q", roots).tobytes()


def _roots(name, a):
    if name in ("is_", "is_many"):
        return (P(a[1] if isinstance(a[1], str) else "basis", a[0]),)
    return tuple(x for x in a if x is not None and x is not True)


def install(B, snaps, n):
    St.snaps = snaps
    for k in St.t:
        St.t[k] = [0.0] * n

    fresh = Engine._fresh_session

    def capture(self, *a, **k):
        s = fresh(self, *a, **k)
        St.sessions.append(s)
        return s
    Engine._fresh_session = capture

    def enter(name, a):
        q = len(snaps) // 2
        St.calls += 1
        fs = _roots(name, a)
        t0 = pc()
        memo, out, roots = {}, [], []
        for f in fs:
            enc_formula(f, memo, out, roots)
        b1, b2 = _finish(out, roots)
        t1 = pc()
        St.t["q"][q] += t1 - t0
        St.nodes["q"] += len(memo)
        St.bytes_["q"] += len(b1) + len(b2)
        out, roots = [], []
        for f in fs:
            enc_formula(f, St.global_memo, out, roots)
        b1, b2 = _finish(out, roots)
        St.t["intern"][q] += pc() - t1
        St.bytes_["intern"] += len(b1) + len(b2)

    def leave(name, a):
        q = len(snaps) // 2
        sessions, St.sessions = St.sessions, []
        t0 = pc()
        memo, out, roots = {}, [], []
        for s in sessions:
            table = s.table
            for node in table.base_of:
                enc_expr(node, memo, out)
            for atom in table.custom:
                enc_formula(atom, memo, out, roots)
        b1, b2 = _finish(out, roots)
        St.t["cl"][q] += pc() - t0
        St.nodes["cl"] += len(memo)
        St.bytes_["cl"] += len(b1) + len(b2)

    B.enter = enter
    B.leave = leave


def report(ans):
    St.nodes["intern"] = len(St.global_memo)
    out = {"calls": St.calls, "nodes": St.nodes, "bytes": St.bytes_}
    for k, v in St.t.items():
        out[k] = {"none": round(sum(d for d, r in zip(v, ans) if r is None), 5),
                  "def": round(sum(d for d, r in zip(v, ans) if r is not None), 5)}
    return out
