"""Alternative bound: within one query, the second solve of Solver.entails
(the None case) from the first model with the query literal flipped.

Per entails/entails_all call in a contextual query: each _solve (ring hit or
search, time, sat, decisions, conflicts) and, when a search follows a SAT
solve, whether the previous model with the query variable flipped (its
block repaired from the block's models, keeping the most of the old
values) satisfies every problem clause, block and root literal.  Theory
validity is not checked: such sessions are counted apart.
"""
import pickle, sys, time, json, collections
from satassume import engine as E
from satassume.sat import solver as SV
from satassume.sympy_api import ask

clock = time.perf_counter
stream = pickle.load(open(sys.argv[1], "rb"))
rows = []
cur = {"q": None, "phase": None}
orig_solve = SV.Solver._solve
orig_entails = SV.Solver.entails
orig_ask = E.Engine._ask
orig_build = E.Engine._build_context


def build(self, *a, **k):
    t = clock()
    r = orig_build(self, *a, **k)
    cur["build"] = cur.get("build", 0) + clock() - t
    return r


E.Engine._build_context = build


def ask_(self, s, lits, proposition, contextual):
    cur["phase"] = "query"
    try:
        return orig_ask(self, s, lits, proposition, contextual)
    finally:
        cur["phase"] = None


E.Engine._ask = ask_


def filled(S, mv):
    mv = list(mv)
    for v in range(1, len(mv) + 1):
        if mv[v - 1] is None:
            S._fill(mv, v)
    return [False if x is None else x for x in mv]


def flip_ok(S, mv, lits):
    """Does mv, with the variables of the call literals forced and their
    blocks repaired, satisfy every clause, block and root literal?"""
    mv = filled(S, mv)
    n = len(mv)
    rbn = S._rb_n
    for l in lits:
        v = l >> 1
        if v > n: return "newvar"
        mv[v - 1] = not (l & 1)
    for l in lits:
        v = l >> 1
        b = S._rb_base[v]
        if b:
            seg = mv[b - 1:b - 1 + rbn]
            m = 0
            for i, x in enumerate(seg):
                m |= 1 << (2 * i + (0 if x else 1))
            best = None; bs = -1
            need = 1 << (2 * (v - b) + (l & 1))
            for x in S._rbc.models:
                if x & need:
                    sc = bin(x & m).count("1")
                    if sc > bs: bs, best = sc, x
            if best is None: return "block"
            mv[b - 1:b - 1 + rbn] = [bool((best >> (2 * i)) & 1) for i in range(rbn)]
    trail = S._trail
    root = S._trail_lim[0] if S._trail_lim else len(trail)
    for i in range(root):
        l = trail[i]; v = l >> 1
        if mv[v - 1] is not (not l & 1): return "root"
    for l in lits:
        if mv[(l >> 1) - 1] is not (not l & 1): return "lits"
    for c in S._clauses:
        for l in c:
            v = l >> 1
            if v <= n and mv[v - 1] is (not l & 1): break
        else:
            return "clause"
    return True if S._ring_blocks(mv, S._rb_bases) else "blocks"


def solve(self, lits, keep):
    e = cur.get("e")
    if e is None or cur["phase"] != "query":
        return orig_solve(self, lits, keep)
    prev = e["last_model"]
    fl = None
    tf = 0.0
    if prev is not None:
        t = clock(); fl = flip_ok(self, prev, lits); tf = clock() - t
    h0 = self._n_ring_hits; d0 = self._n_decisions; c0 = self._n_conflicts
    t = clock()
    r = orig_solve(self, lits, keep)
    dt = clock() - t
    e["solves"].append({"ring": self._n_ring_hits > h0, "sat": r, "dt": dt,
                        "dec": self._n_decisions - d0, "conf": self._n_conflicts - c0,
                        "flip": fl, "tf": tf})
    if r and self._mvals is not None:
        e["last_model"] = list(self._mvals)
    return r


SV.Solver._solve = solve


def entails(self, lit, assumptions=(), hold=None):
    cur["e"] = e = {"solves": [], "last_model": None}
    try:
        return orig_entails(self, lit, assumptions, hold)
    finally:
        cur["e"] = None
        rows.append({"nt": len(self._theories),
                     "tcl": "+".join(type(t).__name__[:3] for t in self._theories),
                     "solves": e["solves"]})


SV.Solver.entails = entails
orig_ea = SV.Solver.entails_all


def entails_all(self, lits, assumptions=(), hold=None):
    if len(lits) == 1:
        return orig_ea(self, lits, assumptions, hold)
    cur["e"] = e = {"solves": [], "last_model": None}
    try:
        return orig_ea(self, lits, assumptions, hold)
    finally:
        cur["e"] = None
        rows.append({"nt": len(self._theories), "all": True,
                     "tcl": "+".join(type(t).__name__[:3] for t in self._theories),
                     "solves": e["solves"]})


SV.Solver.entails_all = entails_all

t0 = clock()
nq = 0
for i, (p, a, r) in enumerate(stream):
    try:
        ask(p, a)
    except ValueError:
        pass
tot = clock() - t0
json.dump({"rows": rows, "tot": tot, "build": cur.get("build", 0)}, open(sys.argv[2], "w"))
print("total", round(tot, 2), "entails", len(rows))
