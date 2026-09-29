"""Persistent-solver plan, stage 0: assumption-set structure, growth of one
solver holding everything, and the active-clause ratio per search.

    PYTHONHASHSEED=0 PYTHONPATH=.:/home/tilo/sympy python gs0_measure.py STREAM OUT.json

Run from a satassume checkout (``main``).  Replays the refine stream through
``satassume.sympy_api.ask`` (answers checked against the recording) with the
engine instrumented from outside; nothing in ``satassume/`` changes.

What a persistent solver would hold is modelled as the **union over all
sessions of their clauses, in canonical form**: a literal of a node block is
``(node, predicate index)``, a custom or relation atom is the atom, and an
auxiliary variable is named by the formula whose compilation allocated it
(``assume_formula(f)`` or ``literal_of(f)``) and its index within that
compilation, so the same formula grounded in two sessions yields the same
clauses (one persistent solver would ground it once, under one selector).
Auxiliary variables allocated elsewhere (the guarded twin variables of
``relations._interpret``) are named per session, so they are counted once
per session: an overcount.  Unit clauses the fact cache adds
(``Session._add_clauses``) are counted separately (they would be root facts),
as are rule blocks (one per distinct node).  Learnt clauses are not counted.

Per search (``Solver.entails`` call): the answering session's canonical
clause count (the clauses a scoped search over this query's cone and
assumptions would have to satisfy; exact for cone sessions, an upper bound
by at most ``cone_threshold`` extra nodes otherwise) against the union at
that moment.  Their ratio is the plan's "active-clause ratio".
"""
from __future__ import annotations

import json
import pickle
import statistics
import sys
import time
from collections import Counter

from sympy import And

import satassume.engine as E
from satassume.compile import VarTable
from satassume.solver import Solver
from satassume.relations import RELATION_ATOMS

# ---------------------------------------------------------------------------
# Part A: assumption sets of consecutive queries (stream only)

def conjuncts(a):
    if a is True or a is None:
        return frozenset()
    try:
        from sympy.logic.boolalg import BooleanTrue
        if isinstance(a, BooleanTrue):
            return frozenset()
    except ImportError:  # pragma: no cover
        pass
    return frozenset(a.args) if isinstance(a, And) else frozenset([a])


def part_a(stream):
    sets = [conjuncts(a) for _, a, _ in stream]
    rel = Counter()
    for prev, cur in zip(sets, sets[1:]):
        if cur == prev:
            rel["identical"] += 1
        elif not cur and not prev:
            rel["identical"] += 1
        elif cur < prev:
            rel["subset"] += 1
        elif cur > prev:
            rel["superset"] += 1
        elif cur & prev:
            rel["overlap"] += 1
        else:
            rel["disjoint"] += 1
    # runs: maximal stretches of consecutive queries whose sets pairwise
    # share the run's base (the intersection so far) -- a run breaks when the
    # intersection would become empty (or on a change from/to no assumptions)
    runs = []
    base, members = None, []
    for s in sets:
        if base is None:
            base, members = s, [s]
            continue
        nb = base & s
        if (nb or (not base and not s)) and bool(base) == bool(s):
            base = nb
            members.append(s)
        else:
            runs.append((base, members))
            base, members = s, [s]
    runs.append((base, members))
    deltas = [len(m - b) for b, ms in runs for m in ms]
    run_len = [len(ms) for _, ms in runs]
    conj = Counter(c for s in set(sets) for c in s)
    return {
        "queries": len(sets),
        "with_assumptions": sum(1 for s in sets if s),
        "consecutive_relation": dict(rel),
        "distinct_sets": len(set(sets)),
        "distinct_nonempty_sets": len({s for s in sets if s}),
        "distinct_conjuncts": len(conj),
        "conjuncts_per_set_median": statistics.median(len(s) for s in set(sets) if s),
        "conjuncts_per_set_max": max(len(s) for s in sets),
        "runs": len(runs),
        "run_length_median": statistics.median(run_len),
        "run_length_mean": sum(run_len) / len(run_len),
        "run_length_max": max(run_len),
        "distinct_bases": len({b for b, _ in runs}),
        "delta_size_hist": dict(sorted(Counter(deltas).items())),
    }


# ---------------------------------------------------------------------------
# Parts B and C: instrumented replay

G_clauses: set = set()          # canonical clauses, union over sessions
G_cache_units: set = set()
G_nodes: set = set()            # nodes with a variable block
G_blocks: set = set()           # nodes with a registered rule block
G_custom: set = set()           # custom / relation atoms
G_rel: set = set()              # relation atoms (theory atoms)
G_aux: set = set()
sessions: list = []             # per session: dict of stats
searches: list = []
state = {"cache": False, "query": -1}


class SState:
    __slots__ = ("sid", "auxkey", "ctx", "ctxn", "clauses", "cone")

    def __init__(self, sid):
        self.sid = sid
        self.auxkey = {}
        self.ctx = []
        self.ctxn = Counter()
        self.clauses = set()
        self.cone = False


_orig_init = E.Session.__init__


def _init(self, engine):
    _orig_init(self, engine)
    st = SState(len(sessions))
    sessions.append(st)
    self._gs = st
    self.solver._gs_session = self
    self.table._gs_session = self


E.Session.__init__ = _init

_orig_aux = VarTable.aux


def _aux(self):
    v = _orig_aux(self)
    s = getattr(self, "_gs_session", None)
    if s is not None:
        st = s._gs
        ctx = st.ctx[-1] if st.ctx else ("session", st.sid)
        k = st.ctxn[ctx]
        st.ctxn[ctx] += 1
        key = ("aux", ctx, k)
        st.auxkey[v] = key
        G_aux.add(key)
    return v


VarTable.aux = _aux


def _with_ctx(name, kind):
    orig = getattr(E.Session, name)

    def wrapped(self, f, *a, **k):
        st = self._gs
        ctx = (kind, f)
        st.ctx.append(ctx)
        st.ctxn[ctx] = 0          # a formula compiled again restarts its names
        try:
            return orig(self, f, *a, **k)
        finally:
            st.ctx.pop()
    setattr(E.Session, name, wrapped)


_with_ctx("assume_formula", "assume")
_with_ctx("literal_of", "literal")


def canon(session, lit):
    v = abs(lit)
    slot = session.table.slots[v]
    if type(slot) is tuple:
        node, b = slot
        G_nodes.add(node)
        key = (node, v - b)
    elif slot is not None:
        G_custom.add(slot)
        if slot.pred in RELATION_ATOMS:
            G_rel.add(slot)
        key = slot
    else:
        key = session._gs.auxkey.get(v, ("aux", ("unnamed", session._gs.sid), v))
    return (lit > 0, key)


def record(solver, clauses):
    s = getattr(solver, "_gs_session", None)
    if s is None:
        return
    st = s._gs
    for c in clauses:
        cc = frozenset(canon(s, l) for l in c)
        if state["cache"]:
            G_cache_units.add(cc)
        else:
            G_clauses.add(cc)
            st.clauses.add(cc)


_ac, _acs, _ai = Solver.add_clause, Solver.add_clauses, Solver.add_internal


def add_clause(self, lits):
    lits = list(lits)
    record(self, [lits])
    return _ac(self, lits)


def add_clauses(self, clauses):
    clauses = [list(c) for c in clauses]
    record(self, clauses)
    return _acs(self, clauses)


def add_internal(self, clauses):
    clauses = [list(c) for c in clauses]
    # internal encoding: 2*v for v, 2*v + 1 for -v
    record(self, [[-(l >> 1) if l & 1 else (l >> 1) for l in c] for c in clauses])
    return _ai(self, clauses)


Solver.add_clause, Solver.add_clauses, Solver.add_internal = add_clause, add_clauses, add_internal

_orig_addc = E.Session._add_clauses


def _add_clauses(self, clauses):
    state["cache"] = True
    try:
        return _orig_addc(self, clauses)
    finally:
        state["cache"] = False


E.Session._add_clauses = _add_clauses

_orig_rb = Solver.register_block


def register_block(self, base):
    s = getattr(self, "_gs_session", None)
    if s is not None:
        G_blocks.add(s.table.slots[base][0])
    return _orig_rb(self, base)


Solver.register_block = register_block

_orig_entails = Solver.entails


def entails(self, lit, assumptions=()):
    s = getattr(self, "_gs_session", None)
    if s is not None:
        searches.append({"q": state["query"], "sid": s._gs.sid,
                         "active": len(s._gs.clauses), "all": len(G_clauses),
                         "vars": len(s.table), "nodes": len(s.base),
                         "cone": s._gs.cone})
    return _orig_entails(self, lit, assumptions)


Solver.entails = entails

# a cone session: mark sessions built inside Engine.ask after the first
_orig_fresh = E.Engine._fresh_session


def _fresh(self):
    s = _orig_fresh(self)
    s._gs.cone = state.get("in_ask_second", False)
    return s


E.Engine._fresh_session = _fresh
_orig_ask = E.Engine.ask


def engine_ask(self, proposition, assumptions=None):
    # a session built after the context session exists is a cone rebuild
    n0 = len(sessions)
    orig_ctx = self._context_session

    def ctx(a):
        r = orig_ctx(a)
        state["in_ask_second"] = True
        return r
    self._context_session = ctx
    try:
        return _orig_ask(self, proposition, assumptions)
    finally:
        del self._context_session
        state["in_ask_second"] = False


E.Engine.ask = engine_ask


def main():
    stream = pickle.load(open(sys.argv[1], "rb"))
    out = {"A": part_a(stream)}
    from satassume.sympy_api import ask
    growth = []
    bad = 0
    t0 = time.perf_counter()
    checkpoints = {int(len(stream) * f) for f in (0.1, 0.25, 0.5, 0.75)} | {len(stream) - 1}
    for i, (p, a, r) in enumerate(stream):
        state["query"] = i
        try:
            got = ask(p, a)
        except ValueError:
            got = "error"
        if got is not r:
            bad += 1
        if i in checkpoints:
            growth.append({"after_query": i + 1, "sessions": len(sessions),
                           "clauses": len(G_clauses), "cache_units": len(G_cache_units),
                           "nodes": len(G_nodes), "rule_blocks": len(G_blocks),
                           "custom_atoms": len(G_custom), "relation_atoms": len(G_rel),
                           "aux": len(G_aux),
                           "vars": 33 * len(G_nodes) + len(G_custom) + len(G_aux)})
    dt = time.perf_counter() - t0
    sess_cl = [len(st.clauses) for st in sessions]
    out["B"] = {
        "answers_differing_from_recording": bad, "seconds_instrumented": dt,
        "sessions": len(sessions), "cone_sessions": sum(st.cone for st in sessions),
        "growth": growth,
        "session_clauses_median": statistics.median(sess_cl),
        "session_clauses_mean": sum(sess_cl) / len(sess_cl),
        "session_clauses_sum": sum(sess_cl),
    }
    ratios = [s["active"] / s["all"] for s in searches if s["all"]]
    act = [s["active"] for s in searches]
    mid = [s for s in searches if s["q"] >= len(stream) // 2]
    out["C"] = {
        "searches": len(searches),
        "in_cone_sessions": sum(s["cone"] for s in searches),
        "active_median": statistics.median(act),
        "active_p90": sorted(act)[int(0.9 * len(act))],
        "active_max": max(act),
        "all_at_median_search": searches[len(searches) // 2]["all"],
        "ratio_median": statistics.median(ratios),
        "ratio_p90": sorted(ratios)[int(0.9 * len(ratios))],
        "ratio_max": max(ratios),
        "ratio_median_second_half": statistics.median(s["active"] / s["all"] for s in mid) if mid else None,
    }
    json.dump(out, open(sys.argv[2], "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
