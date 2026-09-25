"""Per-query log of the refine-stream replay (``refine_replay.py --log``).

Instruments satassume from the outside by wrapping methods on the classes
(nothing in ``satassume/`` is changed and nothing is imported by the replay
unless ``--log`` is given).  One JSON object per query, in stream order:

    i            stream index
    path         stages taken, in order: "memo" (answer memo in
                 sympy_api.ask), "propagation" (Session.query_literal without
                 search), "escalation" (Session.escalate), "cone" (Engine.ask
                 built a cone session; the cone's own escalate is part of
                 this stage and not logged separately), "search"
                 (Session.query_literal with search, i.e. Solver.entails)
    outcome      true | false | null | "error" (ValueError: inconsistent)
    session      id of the session that answered (null if none did)
    session_new  why a session was built for this query: "reused" (the
                 contextual session was reused), "first" (first time these
                 assumptions are seen), "evicted" (seen before, the session
                 was dropped from the LRU, or rebuilt because it outgrew
                 Engine.session_limit; see "evict_reason"), "cone" (the
                 answering session is a cone rebuild), "context_free"
                 (Engine.is_ / Engine.ask without assumptions: a fresh
                 session per query, by design); null if no session
    vars         answering session's solver variable count after the query
    root_len     its root trail length after the query
    solves       one per Solver._solve call during the query:
                   target     "not_p" / "p" (Solver.entails' two searches,
                              A & ~P then A & P), "other" otherwise
                   role       with target "other": "consistency" (entails'
                              check that A alone is satisfiable) or "solve"
                              (any other caller; then "lits" holds the
                              assumption literals)
                   result     "sat" | "unsat"
                   decisions, conflicts, restarts   Solver.stats() deltas
                   nvars      the solver's variable count at the call
                   nassum     number of assumption literals passed
                   model      with --log-models and result "sat": the signed
                              variable ints true in the model
                   depth      only if > 1: the solve belongs to an engine
                              query nested inside this one
                 The not_p / p tagging reads the last literal ``Solver.entails``
                 passes to ``_solve`` (``¬P`` or ``P`` after the assumption
                 literals).  The four scripts under ``agent-reports/2026-09-perf-rounds/scripts/``
                 copy that rule, so a change to how ``entails`` calls
                 ``_solve`` must update all five.
    ms           wall time of the query in milliseconds (includes the
                 logging overhead, a few percent)
    via          where sympy_api.ask sent the query: "memo", "ask"
                 (Engine.ask), "is_" (Engine.is_), "is_custom", "is_cache"
                 (Engine.is_ answered from the fact cache), "none" (out of
                 scope, or a trivially true/false proposition)
    nested       number of engine queries nested inside this one (templates
                 re-entering the engine); 0 normally
    built        number of sessions built during the query (all depths)
    session_error  only if building the contextual session raised: the
                 exception's class name ("Uninterpreted": the assumptions
                 hold a relation no theory interprets, so the session is
                 never stored and is rebuilt on every such query; those
                 queries then show session_new "evicted" or "first", an
                 empty path and session null)
    evict_reason "lru" (dropped by Engine.keep_sessions) or "limit" (outgrew
                 Engine.session_limit); only with session_new "evicted"
"""
import json, time

import satassume.sympy_api as api
from satassume.engine import Engine, Session
from satassume.solver import Solver


class _Ctx:
    def __init__(self):
        self.models = False
        self.reset(-1)

    def reset(self, i):
        self.i = i
        self.path = []
        self.via = None
        self.depth = 0
        self.nested = 0
        self.session = None
        self.session_new = None
        self.in_ctx_session = False
        self.evict_reason = None
        self.session_error = None
        self.built = 0
        self.solves = []
        self.entails = None         # (solver, internal target literal, #assumptions)


ctx = _Ctx()
_next_id = [0]
_seen_assumptions = set()


def _stage(name):
    if ctx.depth <= 1:
        ctx.path.append(name)


_installed = [False]


def install(models=False):
    """Install the wrappers (once; a second call only updates ``models``:
    wrapping the entry points twice would break the depth tracking and leave
    ``path`` empty and ``session_new`` null)."""
    ctx.models = models
    if _installed[0]:
        return
    _installed[0] = True

    # -- sympy_api: memo vs engine ------------------------------------------
    orig_api_ask = api._ask

    def _ask(proposition, assumptions, eng):
        ctx.via = "none"
        return orig_api_ask(proposition, assumptions, eng)
    api._ask = _ask

    # -- Engine entry points (depth tracking) ---------------------------------
    def entry(name, orig):
        def w(self, *a, **k):
            ctx.depth += 1
            if ctx.depth == 1:
                ctx.via = name
            else:
                ctx.nested += 1
            try:
                return orig(self, *a, **k)
            finally:
                ctx.depth -= 1
        return w
    orig_is = Engine.is_

    wrapped_is = entry("is_", orig_is)
    from satassume.rules import PRED_INDEX

    def is_(self, node, pred):
        if pred not in PRED_INDEX:
            return self._is_custom(node, pred)      # wrapped below
        facts = self.cache.facts(node)
        hit = facts is not None and pred in facts
        r = wrapped_is(self, node, pred)
        if hit and ctx.depth == 0 and ctx.via == "is_":
            ctx.via = "is_cache"
        return r
    Engine.is_ = is_
    Engine._is_custom = entry("is_custom", Engine._is_custom)
    Engine.ask = entry("ask", Engine.ask)

    # -- sessions -----------------------------------------------------------------
    orig_ctx_session = Engine._context_session

    def _context_session(self, assumptions):
        if ctx.depth == 1:
            hit = self._context_sessions.get(assumptions)
            if hit is not None and len(hit[0].base) <= self.session_limit:
                ctx.session_new = "reused"
            elif assumptions in _seen_assumptions:
                ctx.session_new = "evicted"
                ctx.evict_reason = "limit" if hit is not None else "lru"
            else:
                ctx.session_new = "first"
            _seen_assumptions.add(assumptions)
        ctx.in_ctx_session = True
        try:
            return orig_ctx_session(self, assumptions)
        except Exception as ex:
            if ctx.depth == 1:
                ctx.session_error = type(ex).__name__
            raise
        finally:
            ctx.in_ctx_session = False
    Engine._context_session = _context_session

    orig_fresh = Engine._fresh_session

    def _fresh_session(self):
        s = orig_fresh(self)
        _next_id[0] += 1
        s._log_id = _next_id[0]
        ctx.built += 1
        if ctx.depth == 1 and not ctx.in_ctx_session:
            if "propagation" in ctx.path:
                ctx.path.append("cone")
                ctx.session_new = "cone"
            else:
                ctx.session_new = "context_free"
        return s
    Engine._fresh_session = _fresh_session

    orig_ql = Session.query_literal

    def query_literal(self, lit, assumptions=(), search=True):
        if ctx.depth <= 1:
            ctx.session = self
            ctx.path.append("search" if search else "propagation")
        return orig_ql(self, lit, assumptions, search)
    Session.query_literal = query_literal

    orig_esc = Session.escalate

    def escalate(self, budget=None):
        if "cone" not in ctx.path:
            _stage("escalation")
        return orig_esc(self, budget)
    Session.escalate = escalate

    # -- solver -------------------------------------------------------------------
    orig_entails = Solver.entails

    def entails(self, lit, assumptions=()):
        assumptions = list(assumptions)
        v = -lit if lit < 0 else lit
        prev = ctx.entails
        ctx.entails = (self, 2 * v + 1 if lit < 0 else 2 * v, len(assumptions))
        try:
            return orig_entails(self, lit, assumptions)
        finally:
            ctx.entails = prev
    Solver.entails = entails

    orig_solve = Solver._solve

    def _solve(self, lits, keep):
        d0, c0, r0 = self._n_decisions, self._n_conflicts, self._n_restarts
        nvars = self._nvars
        res = orig_solve(self, lits, keep)
        rec = {"target": "other", "result": "sat" if res else "unsat",
               "decisions": self._n_decisions - d0, "conflicts": self._n_conflicts - c0,
               "restarts": self._n_restarts - r0, "nvars": nvars, "nassum": len(lits)}
        e = ctx.entails
        if e is not None and e[0] is self:
            _, l, k = e
            if len(lits) == k + 1 and lits[-1] == l ^ 1:
                rec["target"] = "not_p"
            elif len(lits) == k + 1 and lits[-1] == l:
                rec["target"] = "p"
            elif len(lits) == k:
                rec["role"] = "consistency"
            else:
                rec["role"] = "solve"
                rec["lits"] = [Solver._to_ext(x) for x in lits]
        else:
            rec["role"] = "solve"
            rec["lits"] = [Solver._to_ext(x) for x in lits]
        if rec["target"] != "other":
            rec["nassum"] -= 1
        if ctx.depth > 1:
            rec["depth"] = ctx.depth
        if res and ctx.models:
            m = self._model
            rec["model"] = [v if b else -v for v, b in m.items() if b is not None]
        ctx.solves.append(rec)
        return res
    Solver._solve = _solve


def run(stream, out_path, models=False):
    """Replay ``stream`` once with the log on; write ``out_path``; return
    ``(seconds, mismatches)``."""
    install(models)
    bad = []
    t_all = time.perf_counter()
    with open(out_path, "w") as out:
        for i, (p, a, r) in enumerate(stream):
            ctx.reset(i)
            ctx.via = "memo"
            outcome = None
            t0 = time.perf_counter()
            try:
                got = api.ask(p, a)
                outcome = got
            except ValueError as ex:
                got = ex
                outcome = "error"
            ms = 1000 * (time.perf_counter() - t0)
            path = ctx.path
            if ctx.via == "memo":
                path = ["memo"]
            s = ctx.session
            rec = {"i": i, "path": path, "outcome": outcome,
                   "session": getattr(s, "_log_id", None) if s is not None else None,
                   "session_new": ctx.session_new,
                   "vars": s.solver._nvars if s is not None else None,
                   "root_len": None, "solves": ctx.solves, "ms": round(ms, 4),
                   "via": ctx.via, "nested": ctx.nested}
            if s is not None:
                sv = s.solver
                rec["root_len"] = sv._trail_lim[0] if sv._trail_lim else len(sv._trail)
            if ctx.session_new == "evicted":
                rec["evict_reason"] = ctx.evict_reason
            if ctx.session_error is not None:
                rec["session_error"] = ctx.session_error
            rec["built"] = ctx.built
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            if got is not r:
                bad.append((i, p, a, r, got))
    return time.perf_counter() - t_all, bad
