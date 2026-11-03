"""Counters and phase times, by wrapping satassume's methods (best effort:
a method a candidate renamed or removed is skipped and listed in
``missing``, so a counter that reads 0 there is not evidence).

Counters (deterministic for a fixed input and PYTHONHASHSEED):

* every key of ``Engine.stats`` (queries, cache_hits, sessions, set_checks,
  escalations, searches, relevant, consistency_checks, ...), as deltas;
* ``context_builds``: calls of ``Engine._build_context``;
* ``solver_*``: the summed ``Solver.stats()`` of every session created
  (propagations, conflicts, decisions, learned, restarts, vars, clauses,
  theory_decisions, ...), read when the query that created it ends.

Phases (exclusive time: a nested phase's time is not also its parent's):
``front`` (sympy_api outside the engine), ``build`` (``_context_session``,
``_fresh_session``, ``verdict``: the set's session and complete check),
``prepare`` (``prepare_query``, ``assumption_lits``), ``propagate``
(``query_literal(search=False)``), ``escalate`` (``Session.escalate``),
``search`` (``query_literal(search=True)``), ``engine`` (the rest of
``Engine.ask``/``is_``/``is_many``).
"""
import time
from collections import defaultdict

clock = time.perf_counter


class Phases:
    def __init__(self):
        self.stack = []
        self.acc = defaultdict(float)
        self.t = clock()

    def wrap(self, cat, fn):
        tm = self

        def w(*a, **k):
            now = clock()
            if tm.stack:
                tm.acc[tm.stack[-1]] += now - tm.t
            tm.t = now
            tm.stack.append(cat)
            try:
                return fn(*a, **k)
            finally:
                now = clock()
                tm.acc[tm.stack.pop()] += now - tm.t
                tm.t = now
        w.__wrapped__ = fn
        return w


def install(phases=True, counters=True):
    """Patch satassume; returns (ask, collector) where collector.snapshot()
    gives the counters so far and collector.phases the Phases object."""
    from satassume import engine as E
    from satassume import sympy_api as A
    missing = []

    class C:
        pass
    col = C()
    col.missing = missing
    col.phases = Phases() if phases else None
    col.extra = defaultdict(int)
    col.live = []

    def patch(owner, name, cat):
        f = getattr(owner, name, None)
        if f is None:
            missing.append(f"{owner.__name__}.{name}")
            return
        setattr(owner, name, col.phases.wrap(cat, f))

    if counters:
        fs = getattr(E.Engine, "_fresh_session", None)
        if fs is None:
            missing.append("Engine._fresh_session")
        else:
            def fresh(self, *a, **k):
                s = fs(self, *a, **k)
                col.live.append(s)
                return s
            E.Engine._fresh_session = fresh
        bc = getattr(E.Engine, "_build_context", None)
        if bc is None:
            missing.append("Engine._build_context")
        else:
            def build(self, *a, **k):
                col.extra["context_builds"] += 1
                return bc(self, *a, **k)
            E.Engine._build_context = build

    if phases:
        for n in ("ask", "is_", "is_many"):
            patch(E.Engine, n, "engine")
        for n in ("_context_session", "_fresh_session", "verdict"):
            patch(E.Engine, n, "build")
        patch(E.Session, "prepare_query", "prepare")
        patch(E.Session, "assumption_lits", "prepare")
        patch(E.Session, "escalate", "escalate")
        ql = getattr(E.Session, "query_literal", None)
        if ql is None:
            missing.append("Session.query_literal")
        else:
            qs, qp = col.phases.wrap("search", ql), col.phases.wrap("propagate", ql)

            def query_literal(self, lit, assumptions=(), search=True, *a, **k):
                return (qs if search else qp)(self, lit, assumptions, search, *a, **k)
            E.Session.query_literal = query_literal

    def harvest():
        for s in col.live:
            sol = getattr(s, "solver", None)
            st = getattr(sol, "stats", None)
            if callable(st):
                for k, v in st().items():
                    if isinstance(v, int):
                        col.extra["solver_" + k] += v
        col.live.clear()

    base_ask = A.ask
    ask = col.phases.wrap("front", base_ask) if phases else base_ask

    def ask_and_harvest(p, a):
        try:
            return ask(p, a)
        finally:
            if counters:
                harvest()

    def snapshot():
        eng = A.default_engine()
        out = {k: v for k, v in eng.stats.items() if isinstance(v, int)}
        out.update(col.extra)
        return out
    col.snapshot = snapshot
    return ask_and_harvest, col
