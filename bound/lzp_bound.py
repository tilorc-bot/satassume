"""Bound for lazy clause generation of escalated work (sa-lzp-1).

Instrumentation only (monkeypatched, no source edit).  For every
Session.escalate call, each unit of work (a node's parked pattern clauses,
a node's parked formulas, a node visit) is timed and the clauses it stores
in the solver are tagged.  A tagged clause is *hit* when, later in the same
session, it is the reason of a trail literal (it became unit) or a conflict
(it became false): exactly the clauses a lazy propagator would have to emit
on the eager run's trajectory.  Inputs that never reached the clause list
(units, root-satisfied) are counted as emitted (conservative).

Usage: python lzp_bound.py WORKLOAD [--split] [--fuzz SEED]
"""
import json
import sys
import time
from collections import defaultdict

sys.setrecursionlimit(10000)

from evalbench.common import workload, ask_all  # noqa: E402

import satassume.engine as E  # noqa: E402
from satassume.sat import solver as S  # noqa: E402
from satassume.knowledge.rules import NPRED  # noqa: E402

clock = time.perf_counter

# per-kind aggregates; kind in pc (parked patterns), pf (parked formulas),
# fr (frontier node visit), dn (derived node visit)
AGG = defaultdict(lambda: defaultdict(float))
SITE = ["?"]           # which caller escalated: check / ask / decide


class Unit:
    __slots__ = ("kind", "t", "n_in", "clauses", "hit", "vars", "site", "sat_after")

    def __init__(self, kind, site):
        self.kind, self.site = kind, site
        self.t = 0.0
        self.n_in = 0
        self.clauses = []
        self.hit = set()
        self.vars = None          # node visit: the node's block variables
        self.sat_after = False    # a model was found in this session after it


def _state(solver):
    st = getattr(solver, "_lzp", None)
    if st is None:
        st = solver._lzp = {"tag": {}, "units": [], "cur": None}
    return st


# -- count inputs ---------------------------------------------------------
_emit0 = E.Session.emit
_emitp0 = E.Session._emit_pattern


def emit(self, clause):
    u = _state(self.solver)["cur"]
    if u is not None:
        u.n_in += 1
    return _emit0(self, clause)


def _emit_pattern(self, clauses, bases, ment=None):
    u = _state(self.solver)["cur"]
    if u is not None:
        u.n_in += len(clauses)
    return _emitp0(self, clauses, bases, ment)


E.Session.emit = emit
E.Session._emit_pattern = _emit_pattern


def _run_unit(self, kind, fn, *a):
    solver = self.solver
    st = _state(solver)
    u = Unit(kind, SITE[0])
    prev = st["cur"]
    st["cur"] = u
    n0 = len(solver._clauses)
    t = clock()
    try:
        fn(*a)
    finally:
        u.t = clock() - t
        st["cur"] = prev
    if TIMING:
        AGG["timing"][kind + "_t"] += u.t
        AGG["timing"][kind + "_units"] += 1
        AGG["timing"][kind + "_in"] += u.n_in
        return u
    tag = st["tag"]
    for c in solver._clauses[n0:]:
        if id(c) not in tag:
            tag[id(c)] = u
            u.clauses.append(c)
    st["units"].append(u)
    if prev is not None:          # nested (should not happen in escalate)
        prev.t -= u.t
    return u


def escalate(self, budget=None):
    """Session.escalate with each unit of work timed and tagged (same steps)."""
    assert budget is None
    t0 = clock()
    while self.pending or self.pending_c or self.deferred or self.frontier:
        if self.pending_c:
            node, pend = self.pending_c.popitem()

            def f():
                for clauses, bases in pend:
                    self._emit_pattern(clauses, bases)
            _run_unit(self, "pc", f)
        elif self.pending:
            node, formulas = self.pending.popitem()
            _run_unit(self, "pf", self._compile, node, formulas)
        elif self.frontier:
            n = self.frontier.popleft()
            if n not in self.base:
                u = _run_unit(self, "fr", self.node, n, None)
                b = self.base[n]
                u.vars = range(b, b + NPRED)
        else:
            n = self.deferred.pop()
            if n not in self.base:
                u = _run_unit(self, "dn", self.node, n, None)
                b = self.base[n]
                u.vars = range(b, b + NPRED)
    from collections import deque
    self.frontier = deque()
    if not TIMING:
        _scan_trail(self.solver, 0)


E.Session.escalate = escalate


def _scan_trail(solver, start):
    st = getattr(solver, "_lzp", None)
    if st is None or not st["tag"]:
        return
    tag = st["tag"]
    reason = solver._reason
    trail = solver._trail
    for i in range(start, len(trail)):
        r = reason[trail[i] >> 1]
        if r is not None and r.__class__ is not int:
            u = tag.get(id(r))
            if u is not None:
                u.hit.add(id(r))


_prop0 = S.Solver._propagate


def _propagate(self):
    st = getattr(self, "_lzp", None)
    if st is None or not st["tag"]:
        return _prop0(self)
    n = len(self._trail)
    confl = _prop0(self)
    _scan_trail(self, n)
    if confl is not None:
        u = st["tag"].get(id(confl))
        if u is not None:
            u.hit.add(id(confl))
    return confl


import os
TIMING = os.environ.get("LZP_TIMING") == "1"
if not TIMING:
    S.Solver._propagate = _propagate

# a model found (search or witness ring) after escalation: under the exact
# final-check rule every derived node is visited then
_search0 = S.Solver._search
_ring0 = S.Solver._ring_hit


def _mark_sat(solver):
    st = getattr(solver, "_lzp", None)
    if st is not None:
        for u in st["units"]:
            u.sat_after = True


def _search(self, n):
    r = _search0(self, n)
    if r is True:
        _mark_sat(self)
    return r


def _ring_hit(self, lits):
    r = _ring0(self, lits)
    if r is not None:
        _mark_sat(self)
    return r


if not TIMING:
    S.Solver._search = _search
    S.Solver._ring_hit = _ring_hit
else:
    _ai0 = S.Solver.add_internal
    _mb0 = S.Solver.mention_blocks

    def add_internal(self, clauses, mentions=None):
        st = getattr(self, "_lzp", None)
        if st is None or st["cur"] is None:
            return _ai0(self, clauses, mentions)
        t = clock()
        try:
            return _ai0(self, clauses, mentions)
        finally:
            AGG["timing"][st["cur"].kind + "_add_internal_t"] += clock() - t

    def mention_blocks(self, pairs):
        st = getattr(self, "_lzp", None)
        if st is None or st["cur"] is None:
            return _mb0(self, pairs)
        t = clock()
        try:
            return _mb0(self, pairs)
        finally:
            AGG["timing"][st["cur"].kind + "_mention_t"] += clock() - t
    S.Solver.add_internal = add_internal
    S.Solver.mention_blocks = mention_blocks

# which caller escalates
_cc0 = E.Engine._complete_check
_ask0 = E.Engine._ask
_dec0 = E.Engine._decide


def _site(name, fn):
    def w(*a, **k):
        prev = SITE[0]
        SITE[0] = name
        try:
            return fn(*a, **k)
        finally:
            SITE[0] = prev
    return w


E.Engine._complete_check = staticmethod(_site("check", _cc0))
E.Engine._ask = _site("ask", _ask0)
E.Engine._decide = _site("decide", _dec0)

# sessions: collect at the end of their life (weakref finalizer on solver)
SESS = []
_init0 = S.Solver.__init__


def _sinit(self, *a, **k):
    _init0(self, *a, **k)
    SESS.append(self)


S.Solver.__init__ = _sinit


def harvest(cls):
    """Fold finished sessions into AGG (drop their state)."""
    for solver in SESS:
        st = getattr(solver, "_lzp", None)
        if st is None:
            continue
        units = st["units"]
        # variables of the escalated node visits
        owner = {}
        for u in units:
            if u.vars is not None:
                for v in u.vars:
                    owner[v] = u
        mentioned = set()     # node units whose vars a hit clause of another unit mentions
        for u in units:
            for c in u.clauses:
                if id(c) in u.hit:
                    for l in c:
                        w = owner.get(l >> 1)
                        if w is not None and w is not u:
                            mentioned.add(id(w))
        for u in units:
            a = AGG[u.site + "/" + cls]
            k = u.kind
            stored = len(u.clauses)
            hit = len(u.hit)
            a[k + "_units"] += 1
            a[k + "_t"] += u.t
            a[k + "_in"] += u.n_in
            a[k + "_stored"] += stored
            a[k + "_hit"] += hit
            em = hit + max(0, u.n_in - stored)
            a[k + "_emitted"] += em
            if u.n_in:
                # time attributable to never-emitted clauses (pro rata)
                a[k + "_t_unemitted"] += u.t * (1 - em / u.n_in) if em < u.n_in else 0.0
            if not em:
                a[k + "_t_unit_unhit"] += u.t
                a[k + "_units_unhit"] += 1
            if u.vars is not None:
                need_opt = id(u) in mentioned
                a[k + "_need_opt"] += need_opt
                a[k + "_need_exact"] += need_opt or u.sat_after
                if not need_opt:
                    a[k + "_t_skip_opt"] += u.t
                if not (need_opt or u.sat_after):
                    a[k + "_t_skip_exact"] += u.t
        solver._lzp = None
    SESS.clear()


def main():
    args = sys.argv[1:]
    name = args[0]
    if name == "fuzz":
        from evalbench.fuzz import queries
        pairs = queries(int(args[1]))
    else:
        pairs = workload(name)
    from satassume import sympy_api
    per = []
    t = clock()
    ans = []
    for p, a in pairs:
        t1 = clock()
        ans.extend(ask_all(sympy_api.ask, [(p, a)]))
        per.append(clock() - t1)
        if not TIMING:
            harvest("none" if ans[-1] is None else "def")
        else:
            SESS.clear()
    tot = clock() - t
    none_t = sum(x for x, r in zip(per, ans) if r is None)
    out = {"workload": name, "n": len(pairs), "seconds": tot, "none_s": none_t,
           "n_none": sum(r is None for r in ans),
           "agg": {s: dict(v) for s, v in AGG.items()}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
