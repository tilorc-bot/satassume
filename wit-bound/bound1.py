"""BOUND for cross-session witness reuse (sa-wit-1).

For every Solver._solve that searches (ring miss) in a contextual session,
would a model found by an earlier session of the same (assumption set,
theory scope) satisfy the call after completion over the new session's
extra variables?  Context variables (<= N0, the count after
Engine._build_context) are assumed to coincide; this is verified per key
by a fingerprint of the context (clauses, root trail, blocks, VarTable).

    PYTHONHASHSEED=0 PYTHONPATH=<checkout>:<sympy> python bound1.py stream.pkl out.json [K]
"""
import pickle, sys, time, json, collections, hashlib
from satassume import engine as E
from satassume.sat import solver as SV
from satassume.sympy_api import ask

clock = time.perf_counter
K = int(sys.argv[3]) if len(sys.argv) > 3 else 4
stream = pickle.load(open(sys.argv[1], "rb"))

store = collections.defaultdict(list)   # key -> [(sid, model list)]
fps = {}
checkfp = {}
checkmv = {}                                 # key -> context fingerprint
C = collections.Counter()
T = collections.Counter()
rows = []
cur = {"key": None, "ctx": None, "phase": None, "sid": 0, "solver": None}
sid_counter = [0]


def fingerprint(s):
    S = s.solver
    root = S._trail_lim[0] if S._trail_lim else len(S._trail)
    h = hashlib.blake2b(digest_size=16)
    h.update(repr([list(c) for c in S._clauses]).encode())
    h.update(repr(S._trail[:root]).encode())
    h.update(repr(S._rb_bases).encode())
    h.update(repr(sorted((repr(k), v) for k, v in s.table.__dict__.items()
                         if isinstance(v, dict)) if False else 0).encode())
    h.update(repr(sorted(map(repr, s.base.items()))).encode())
    h.update(repr((S._nvars, len(S._theories), S._n_registered)).encode())
    return h.hexdigest()


orig_build = E.Engine._build_context
orig_check = E.Engine._complete_check
orig_ask = E.Engine._ask
orig_solve = SV.Solver._solve


def build(self, assumptions, proposition=None):
    scope = E.theory_scope(assumptions, proposition, self._extensions)
    key = (assumptions, scope)
    cur["phase"] = "check"; cur["key"] = key
    sid_counter[0] += 1
    cur["sid"] = sid_counter[0]
    t = clock()
    s, lits = orig_build(self, assumptions, proposition)
    S = s.solver
    root = S._trail_lim[0] if S._trail_lim else len(S._trail)
    ctx = (S._nvars, len(S._clauses), root, len(S._rb_bases), len(S._theories), S._n_registered)
    tf = clock()
    fp = fingerprint(s)
    T["fingerprint"] += clock() - tf
    old = fps.get(key)
    if old is None:
        fps[key] = (fp, ctx)
        C["keys"] += 1
    elif old[0] != fp:
        C["fp_mismatch"] += 1
    else:
        C["fp_match"] += 1
    S._bctx = (key, ctx, cur["sid"])
    cur["phase"] = None
    return s, lits


E.Engine._build_context = build


def ask_(self, s, lits, proposition, contextual):
    cur["phase"] = "query" if contextual else "free"
    cur["qid"] = cur.get("qid", 0) + 1
    try:
        return orig_ask(self, s, lits, proposition, contextual)
    finally:
        cur["phase"] = None


E.Engine._ask = ask_


def tclass(S):
    out = []
    for t in S._theories:
        n = type(t).__name__[:3]
        if n == "LRA":
            n += ("i" if t._ints else "") + ("c" if t._fields else "")
            if t._fields: n += "C" if t.certified else "u"
        out.append(n)
    return "+".join(out)


def fullcheck(S, lits, mv):
    """exact check of mv (filled, complete) against every problem clause,
    block, root literal and lits of S: the cost of re-validating a stored
    check model from scratch (theories not included)."""
    n = len(mv)
    for l in lits:
        v = l >> 1
        if v > n or mv[v - 1] is not (not l & 1): return False
    trail = S._trail
    root = S._trail_lim[0] if S._trail_lim else len(trail)
    for i in range(root):
        l = trail[i]; v = l >> 1
        if v > n or mv[v - 1] is not (not l & 1): return False
    for c in S._clauses:
        for l in c:
            v = l >> 1
            if v <= n and mv[v - 1] is (not l & 1): break
        else:
            return False
    return S._ring_blocks(mv, S._rb_bases)


def filled(S, mv):
    mv = list(mv)
    for v in range(1, len(mv) + 1):
        if mv[v - 1] is None:
            S._fill(mv, v)
    for v in range(1, len(mv) + 1):
        if mv[v - 1] is None:
            mv[v - 1] = False      # unassigned non-block non-inert: free
    return mv


def complete(S, lits, M, ctx):
    """Complete M (values of context vars 1..N0) over S's other variables by
    propagation over the clauses and blocks added after the context, plus
    greedy decisions without backtracking.  True iff a total assignment
    satisfying lits, the root trail and every clause/block is found."""
    N0, C0, R0, B0 = ctx[:4]
    n = S._nvars
    a = [None] * (n + 1)
    a[1:N0 + 1] = M[:N0]
    trail = S._trail
    root = S._trail_lim[0] if S._trail_lim else len(trail)
    for i in range(R0, root):
        l = trail[i]; v = l >> 1; want = not (l & 1)
        x = a[v]
        if x is None: a[v] = want
        elif x is not want: return "root"
    for l in lits:
        v = l >> 1; want = not (l & 1)
        x = a[v]
        if x is None: a[v] = want
        elif x is not want: return "lits"
    D = S._clauses[C0:]
    nb = S._rb_bases[B0:]
    rbn = S._rb_n; rbc = S._rbc
    while True:
        changed = True
        while changed:
            changed = False
            for c in D:
                un = None; k = 0
                for l in c:
                    x = a[l >> 1]
                    if x is None:
                        k += 1; un = l
                    elif x is (not (l & 1)):
                        break
                else:
                    if k == 0: return "clause"
                    if k == 1:
                        a[un >> 1] = not (un & 1); changed = True
            for b in nb:
                m = 0
                for i in range(rbn):
                    x = a[b + i]
                    if x is not None:
                        m |= 1 << (2 * i + (0 if x else 1))
                if m:
                    cl = rbc.closure(m)
                    if cl == 0: return "block"
                    if cl != m:
                        for i in range(rbn):
                            if a[b + i] is None:
                                if cl >> (2 * i) & 1: a[b + i] = True; changed = True
                                elif cl >> (2 * i + 1) & 1: a[b + i] = False; changed = True
        # greedy decision: first unsatisfied clause, its first unassigned literal
        for c in D:
            un = None
            for l in c:
                x = a[l >> 1]
                if x is None:
                    if un is None: un = l
                elif x is (not (l & 1)):
                    break
            else:
                if un is not None:
                    a[un >> 1] = not (un & 1)
                    break
        else:
            return True


def solve(self, lits, keep):
    bctx = getattr(self, "_bctx", None)
    phase = cur["phase"]
    if phase == "check" and bctx is None:
        t = clock(); r = orig_solve(self, lits, keep); dt = clock() - t
        key = cur["key"]
        fpc = (self._nvars, len(self._clauses), len(self._trail), len(self._rb_bases), len(self._theories), self._n_registered, tuple(lits))
        prev = checkfp.get(key)
        th = self._theories
        ex = any(getattr(t, "exhausted", False) or getattr(t, "gave_up", False) for t in th)
        rows.append({"ph": "check", "ring": self._n_ring_hits > 0, "sat": r, "dt": dt, "nt": len(th), "nc": 0,
                     "hit": (0 if prev == fpc else None), "tc": 0.0, "why": [], "ex": ex,
                     "cert": [getattr(t, "certified", None) for t in th]})
        rows[-1]["tcl"] = tclass(self)
        if r and self._mvals is not None:
            mvf = filled(self, self._mvals)
            old = checkmv.get(key)
            if old is not None and prev == fpc:
                tf = clock(); ok = fullcheck(self, lits, old); rows[-1]["fc"] = clock() - tf; rows[-1]["fcok"] = ok
            checkmv[key] = mvf
        checkfp[key] = fpc
        return r
    if bctx is None or phase not in ("check", "query") or cur["key"] != bctx[0]:
        return orig_solve(self, lits, keep)
    key, ctx, sid = bctx
    h0 = self._n_ring_hits
    # test before the search (state is the pre-search state)
    cands = [m for (s2, m) in reversed(store[key]) if s2 != sid][:K]
    tc = clock()
    hit = None; why = []
    if phase == "query" and cands:
        for j, M in enumerate(cands):
            r = complete(self, lits, M, ctx)
            if r is True:
                hit = j; break
            why.append(r)
    dtc = clock() - tc
    t = clock()
    r = orig_solve(self, lits, keep)
    dt = clock() - t
    ring = self._n_ring_hits > h0
    nt = len(self._theories)
    th = self._theories
    rec = {"ex": any(getattr(t, "exhausted", False) or getattr(t, "gave_up", False) for t in th), "ph": phase, "ring": ring, "sat": r, "dt": dt, "nt": nt, "nc": len(cands),
           "hit": hit, "tc": dtc, "why": why[:1]}
    if phase == "check":
        # same key seen before with a stored model from the check of an earlier session
        rec["prev"] = bool(cands)
    rec["qid"] = cur.get("qid", 0); rec["tcl"] = tclass(self); rec["nad"] = self._n_registered - ctx[5]; rec["ntd"] = len(self._theories) - ctx[4]
    rows.append(rec)
    if r and not ring and self._mvals is not None:
        lst = store[key]
        lst.append((sid, filled(self, self._mvals)))
        if len(lst) > 16: del lst[0]
    return r


SV.Solver._solve = solve

t0 = clock()
bad = 0
for i, (p, a, r) in enumerate(stream):
    try:
        got = ask(p, a)
    except ValueError:
        got = "error"
    if got is not r and not (got == "error" and r == "error"):
        bad += 1
tot = clock() - t0
json.dump({"rows": rows, "C": dict(C), "T": dict(T), "tot": tot, "bad": bad}, open(sys.argv[2], "w"))
print("total", round(tot, 2), "bad", bad, dict(C))
