"""Round 3, items B1 and B2: where the cone path and node visits spend
their time, as a share of the cold pass.

    PYTHONHASHSEED=0 PYTHONPATH=.:/path/to/sympy python agent-reports/scripts/cone_node_split.py \
        stream.pkl MODE [PLAIN_SECONDS [CONE_INDEX_FILE]]

MODE ``b1``: ``Engine.ask`` is replaced by an instrumented copy of itself
(the code of ``satassume/engine.py`` at ``9e8c3eb``, timers added, logic
unchanged; answers are checked against the recording).  For every
contextual query on a *polluted* reused session (the only queries that can
take the cone path) it times the first attempt in that session
(``_literal``, propagation, escalation, second propagation) and, for those
that go on to the cone, the cone's parts (fresh session + ``assume_formula``,
``_literal``, ``escalate``, search, the swap).  It classifies the polluted
queries by outcome of the first attempt and by whether the proposition's
nodes were already visited in the polluted session before the query.

MODE ``b1oracle``: the bound for skipping the first attempt.  Reads the
indices of the queries that ended on the cone path (written by a ``b1`` run
given CONE_INDEX_FILE) and lets exactly those skip the first attempt and
build the cone at once; answers are checked.  Its pass time against a
``b1`` pass is the most an oracle that knew in advance could save.

MODES ``p0``, ``p1``, ``p2``: the two sketches of the plan, as
``ask_policy`` (see its docstring), and ``p0`` the same copy with neither;
prints the pass time and the answer mismatches.  Compare interleaved runs.

MODE ``b2x``: the template clause emission split: ``_compile_patterns``
(slot bases and the allocation of child blocks, the demand filter,
demand/frontier bookkeeping), ``_emit_pattern`` (shifting the pattern's
clauses, ``Solver.add_internal``), and every new block allocation by
``VarTable.node_base`` from any caller (33 ``P`` atoms per node).

MODE ``b2``: ``Session.node`` is replaced by an instrumented copy (same
source, timers around each step) and ``Engine.ask``'s cone branch is
tagged, so every node visit's cost is split into: lookup (``base.get``,
SymPy hash/eq), variable allocation (``VarTable.node_base``: 33 ``P``
atoms), template lookup (``clause_templates``: memo hit or template run),
extension node facts, rule block (``add_pattern``), cached facts, template
clause emission (``_compile_patterns``), formula templates (``_compile`` /
``_compile_pending``); plus the already-visited path and
``escalate``'s total (it includes the node visits it makes, so it overlaps
the node rows).  Totals are given for all sessions and for the cone
sessions (the session a cone query builds after its first attempt).

PLAIN_SECONDS, if given, is the unwrapped cold pass on the same machine
(the denominator for the shares); otherwise the instrumented pass is used.
"""
import pickle, sys, time
from collections import Counter, deque

stream = pickle.load(open(sys.argv[1], "rb"))
mode = sys.argv[2]
plain = float(sys.argv[3]) if len(sys.argv) > 3 else None
import satassume.sympy_api as api
from satassume import engine as E
from satassume.engine import Engine, Session, want_of
from satassume.formula import P, atoms_of
from satassume.rules import NPRED, PRED_INDEX, RULE_INTERNAL

pc = time.perf_counter
T = Counter()   # seconds
N = Counter()   # counts


CUR = [0]


def replay():
    bad = 0
    t0 = pc()
    for i, (p, a, r) in enumerate(stream):
        CUR[0] = i
        try:
            got = api.ask(p, a)
        except ValueError:
            got = "err"
        if got is not r and got != "err":
            bad += 1
            if bad <= 5:
                print(f"  mismatch at {i}: ask({p}, {a}) recorded {r}, got {got}")
    return pc() - t0, bad


# ---------------------------------------------------------------------------
# B1: the first attempt on the polluted session
# ---------------------------------------------------------------------------

def ask_b1(self, proposition, assumptions=None):
    self.stats["queries"] += 1
    lits = []
    contextual = assumptions is not None and assumptions is not True
    if contextual:
        s, lits = self._context_session(assumptions)
    else:
        s = self._fresh_session()
    polluted = len(s.base) - s.n_assumption_nodes > self.cone_threshold
    watch = contextual and polluted and self.cone_search
    if ORACLE is not None and watch and CUR[0] in ORACLE:
        return cone_now(self, s, proposition, assumptions)
    if watch:
        extra = len(s.base) - s.n_assumption_nodes
        seen = all(a.expr in s.base for a in atoms_of(proposition) if a.pred in PRED_INDEX)
        t0 = pc()
    q = self._literal(s, proposition)
    if watch:
        t1 = pc()
    r = s.query_literal(q, lits, search=False)
    escalated = False
    if r is None and s.incomplete:
        self.stats["escalations"] += 1
        if watch:
            t2 = pc()
        s.escalate()
        if watch:
            t3 = pc()
            T["attempt_escalate"] += t3 - t2
        escalated = True
        r = s.query_literal(q, lits, search=False)
    if watch:
        t4 = pc()
        T["attempt_literal"] += t1 - t0
        T["attempt_all"] += t4 - t0
        key = ("seen" if seen else "new") + ("/esc" if escalated else "/prop")
        if r is not None:
            N["answered:" + key] += 1
            T["answered:" + key] += t4 - t0
        else:
            N["cone:" + key] += 1
            T["cone_attempt:" + key] += t4 - t0
        N["extra_nodes_sum"] += extra
    if r is None:
        self.stats["searches"] += 1
        if contextual and polluted and self.cone_search:
            self.stats["cone_searches"] += 1
            s0 = s
            c0 = pc()
            s = self._fresh_session()
            lits = s.assume_formula(assumptions)
            c1 = pc()
            q = self._literal(s, proposition)
            c2 = pc()
            s.escalate()
            c3 = pc()
            r = s.query_literal(q, lits, search=True)
            c4 = pc()
            if self._context_sessions.get(assumptions, (None,))[0] is s0:
                self._context_sessions[assumptions] = (s, lits)
                if r is not None:
                    s._emit([-lits[0], q if r else -q])
            c5 = pc()
            T["cone_assume"] += c1 - c0; T["cone_literal"] += c2 - c1
            T["cone_escalate"] += c3 - c2; T["cone_search"] += c4 - c3
            T["cone_swap"] += c5 - c4
            N["cone_answer:" + repr(r)] += 1
            CONE_IDX.append(CUR[0])
            return r
        if watch:
            N["search_in_polluted"] += 1   # cone_search off: never on the stream
        r = s.query_literal(q, lits, search=True)
    return r


ORACLE = None
CONE_IDX = []


def cone_now(self, s0, proposition, assumptions):
    """Oracle mode: a query known (from a b1 run) to end on the cone path
    skips the first attempt and builds the cone at once (same code as the
    cone branch)."""
    self.stats["searches"] += 1
    self.stats["cone_searches"] += 1
    c0 = pc()
    s = self._fresh_session()
    lits = s.assume_formula(assumptions)
    c1 = pc()
    q = self._literal(s, proposition)
    c2 = pc()
    s.escalate()
    c3 = pc()
    r = s.query_literal(q, lits, search=True)
    c4 = pc()
    if self._context_sessions.get(assumptions, (None,))[0] is s0:
        self._context_sessions[assumptions] = (s, lits)
        if r is not None:
            s._emit([-lits[0], q if r else -q])
    c5 = pc()
    T["cone_assume"] += c1 - c0; T["cone_literal"] += c2 - c1
    T["cone_escalate"] += c3 - c2; T["cone_search"] += c4 - c3
    T["cone_swap"] += c5 - c4
    N["cone_answer:" + repr(r)] += 1
    N["oracle_skipped"] += 1
    return r


POLICY = None


def ask_policy(self, proposition, assumptions=None):
    """Engine.ask with one of the two B1 sketches (modes ``p1``, ``p2``):

    p1  polluted session: after propagation fails, skip the escalation in
        the polluted session and go to the cone at once;
    p2  polluted session and a proposition atom whose node the polluted
        session has not visited: build the cone session before touching the
        polluted one, then run the usual propagation / escalation / search
        in it (it replaces the polluted session as the cone does today).
    """
    self.stats["queries"] += 1
    lits = []
    contextual = assumptions is not None and assumptions is not True
    if contextual:
        s, lits = self._context_session(assumptions)
    else:
        s = self._fresh_session()
    polluted = len(s.base) - s.n_assumption_nodes > self.cone_threshold
    if POLICY == "p2" and contextual and polluted and self.cone_search and not all(
            a.expr in s.base for a in atoms_of(proposition) if a.pred in PRED_INDEX):
        N["p2_early_cone"] += 1
        s0 = s
        s = self._fresh_session()
        lits = s.assume_formula(assumptions)
        if self._context_sessions.get(assumptions, (None,))[0] is s0:
            self._context_sessions[assumptions] = (s, lits)
        polluted = False
        q = self._literal(s, proposition)
        r = s.query_literal(q, lits, search=False)
        if r is None and s.incomplete:
            s.escalate()
            r = s.query_literal(q, lits, search=False)
        if r is None:
            N["p2_searched"] += 1
            r = s.query_literal(q, lits, search=True)
            if r is not None and self._context_sessions.get(assumptions, (None,))[0] is s:
                s._emit([-lits[0], q if r else -q])
        return r
    q = self._literal(s, proposition)
    r = s.query_literal(q, lits, search=False)
    skip = POLICY == "p1" and contextual and polluted and self.cone_search
    if r is None and s.incomplete and not skip:
        self.stats["escalations"] += 1
        s.escalate()
        r = s.query_literal(q, lits, search=False)
    if r is None:
        self.stats["searches"] += 1
        if contextual and polluted and self.cone_search:
            N["cone"] += 1
            s0 = s
            s = self._fresh_session()
            lits = s.assume_formula(assumptions)
            q = self._literal(s, proposition)
            s.escalate()
            r = s.query_literal(q, lits, search=True)
            if self._context_sessions.get(assumptions, (None,))[0] is s0:
                self._context_sessions[assumptions] = (s, lits)
                if r is not None:
                    s._emit([-lits[0], q if r else -q])
            return r
        r = s.query_literal(q, lits, search=True)
    return r


# ---------------------------------------------------------------------------
# B2: the cost of a node visit
# ---------------------------------------------------------------------------

in_cone = [False]


def node_b2(self, node, demanded=None):
    tag = "cone:" if in_cone[0] else "rest:"
    t0 = pc()
    b = self.base.get(node)
    if b is not None:
        if demanded is not None and (node in self.pending or node in self.pending_c):
            t1 = pc()
            self._compile_pending(node, demanded)
            T[tag + "revisit_compile_pending"] += pc() - t1
            N[tag + "revisit_compile_pending"] += 1
        T[tag + "revisit_total"] += pc() - t0
        N[tag + "revisit"] += 1
        return b
    table = self.table
    t1 = pc()
    b = table.node_base(node)
    self.base[node] = b
    table.new_nodes = []
    t2 = pc()
    constructing = self.engine._constructing
    constructing.add(node)
    engine = self.engine
    ct = engine.clause_templates
    if ct is not None:
        hit = node in ct.__self__._clauses_cache
        compiled, formulas = ct(node)
    else:
        hit = None
        compiled, formulas = (), engine.templates(node)
    t3 = pc()
    ext = engine.extensions
    if ext is not None and ext._vocab:
        formulas = list(formulas) + ext.node_facts(node)
    t4 = pc()
    if not (len(compiled) == 1 and compiled[0].pattern.complete and not formulas):
        self.solver.add_pattern(RULE_INTERNAL, b, NPRED)
        self.nclauses += len(RULE_INTERNAL)
        N[tag + "blocks"] += 1
    else:
        self.solver.ensure_vars(b + NPRED - 1)
        N[tag + "constants"] += 1
    t5 = pc()
    facts = engine.cache.facts(node)
    if facts:
        self._add_clauses([[b + PRED_INDEX[p]] if v else [-(b + PRED_INDEX[p])]
                           for p, v in facts.items() if v is not None and p in PRED_INDEX])
        N[tag + "with_cached_facts"] += 1
    t6 = pc()
    if compiled:
        self._compile_patterns(node, compiled, demanded)
    t7 = pc()
    if formulas:
        items = [(f, atoms_of(f)) for f in formulas]
        if demanded is None:
            self._compile(node, items)
        else:
            self.pending[node] = items
            self._compile_pending(node, demanded)
        N[tag + "with_formulas"] += 1
    t8 = pc()
    constructing.discard(node)
    T[tag + "lookup"] += t1 - t0
    T[tag + "alloc"] += t2 - t1
    T[tag + "templates_" + ("hit" if hit else "miss")] += t3 - t2
    N[tag + "templates_" + ("hit" if hit else "miss")] += 1
    T[tag + "ext_node_facts"] += t4 - t3
    T[tag + "rule_block"] += t5 - t4
    T[tag + "cached_facts"] += t6 - t5
    T[tag + "template_clauses"] += t7 - t6
    T[tag + "formula_templates"] += t8 - t7
    T[tag + "new_total"] += pc() - t0
    N[tag + "new"] += 1
    return b


def compile_patterns_b2x(self, node, compiled, demanded):
    """Session._compile_patterns with timers (b2x)."""
    t0 = pc()
    table = self.table
    base_of = table.base_of
    demand = self.demand
    want = None if demanded is None else want_of(demanded)
    ta = tf = tb = 0.0
    for comp in compiled:
        objs, pat = comp.objs, comp.pattern
        a0 = pc()
        bases = [0] * len(objs)
        new = []
        for k in pat.used:
            o = objs[k]
            bb = base_of.get(o)
            if bb is None:
                bb = table.node_base(o)
                new.append(k)
            bases[k] = 2 * bb
        a1 = pc()
        ta += a1 - a0
        if want is None:
            self._emit_pattern(pat.clauses, bases)
        else:
            now = [c for c in pat.clauses if c[1] & want]
            if len(now) < len(pat.clauses):
                later = [c for c in pat.clauses if not (c[1] & want)]
                self.pending_c.setdefault(node, []).append((later, bases))
            if now:
                f1 = pc()
                tf += f1 - a1
                self._emit_pattern(now, bases)
                a1 = pc()
        b0 = pc()
        tf += b0 - a1 if want is not None and not now else 0.0
        for k, preds in pat.child_preds.items():
            d = demand.get(objs[k])
            if d is None:
                demand[objs[k]] = set(preds)
            else:
                d.update(preds)
        for k in new:
            if k < pat.node:
                self.frontier.append(objs[k])
            elif k > pat.node:
                self.deferred.append(objs[k])
        tb += pc() - b0
    table.new_nodes = []
    T["cp:total"] += pc() - t0
    T["cp:slots_and_child_alloc"] += ta
    T["cp:want_filter"] += tf
    T["cp:demand_frontier"] += tb
    N["cp:calls"] += 1
    N["cp:patterns"] += len(compiled)


def emit_pattern_b2x(self, clauses, bases):
    t0 = pc()
    self.nclauses += len(clauses)
    solver = self.solver
    solver.ensure_vars(len(self.table))
    shifted = [[bases[k] + off for k, off in li] for _, _, li in clauses]
    t1 = pc()
    solver.add_internal(shifted)
    t2 = pc()
    T["ep:shift"] += t1 - t0
    T["ep:add_internal"] += t2 - t1
    N["ep:calls"] += 1
    N["ep:clauses"] += len(clauses)


from satassume.compile import VarTable
orig_node_base = VarTable.node_base


def node_base_b2x(self, node):
    b = self.base_of.get(node)
    if b is not None:
        return b
    t0 = pc()
    b = orig_node_base(self, node)
    T["alloc:new_blocks"] += pc() - t0
    N["alloc:new_blocks"] += 1
    return b


orig_esc = Session.escalate


def escalate_b2(self, budget=None):
    N[("cone:" if in_cone[0] else "rest:") + "escalate"] += 1
    t0 = pc()
    try:
        return orig_esc(self, budget)
    finally:
        T[("cone:" if in_cone[0] else "rest:") + "escalate_total"] += pc() - t0


orig_fresh = Engine._fresh_session
orig_ask = Engine.ask


def ask_b2(self, proposition, assumptions=None):
    # the cone branch starts at the second fresh session of a contextual query
    state = {"n": 0}

    def fresh():
        state["n"] += 1
        if assumptions is not None and assumptions is not True and state["n"] >= 1 \
                and state.get("ctx_done"):
            in_cone[0] = True
        return orig_fresh(self)
    orig_ctx = self._context_session

    def ctx(a):
        try:
            return orig_ctx(a)
        finally:
            state["ctx_done"] = True
    self._fresh_session = fresh
    self._context_session = ctx
    try:
        return orig_ask(self, proposition, assumptions)
    finally:
        in_cone[0] = False
        del self._fresh_session, self._context_session


if mode in ("p1", "p2", "p0"):
    # p0: the same copy with no policy (the control for p1 / p2)
    POLICY = mode
    Engine.ask = ask_policy
    dt, bad = replay()
    print(f"{mode}: pass {dt:.3f}s, mismatches {bad}; {dict(N)}")
    sys.exit(0)
if mode == "b2x":
    Session._compile_patterns = compile_patterns_b2x
    Session._emit_pattern = emit_pattern_b2x
    VarTable.node_base = node_base_b2x
    dt, bad = replay()
    D = plain or dt
    print(f"b2x: instrumented pass {dt:.3f}s, mismatches {bad}; shares of {D:.3f}s")
    print("  counts:", {k: v for k, v in N.items()})
    for k in sorted(T):
        print(f"  {k:28s} {1000 * T[k]:7.1f} ms  {100 * T[k] / D:5.2f}%")
    sys.exit(0)
if mode == "b1oracle":
    # PLAIN_SECONDS is required here; the cone indices come from b1's file
    ORACLE = set(int(x) for x in open(sys.argv[4]).read().split())
    mode = "b1"
if mode == "b1":
    Engine.ask = ask_b1
    dt, bad = replay()
    D = plain or dt
    print(f"b1: instrumented pass {dt:.3f}s, mismatches {bad}; shares of {D:.3f}s")
    pol = sum(v for k, v in N.items() if k.startswith(("answered:", "cone:")))
    print(f"polluted contextual queries {pol}, mean extra nodes {N['extra_nodes_sum'] / max(pol, 1):.1f}")
    for k in sorted(k for k in N if k.startswith(("answered:", "cone:"))):
        tk = "cone_attempt:" + k[5:] if k.startswith("cone:") else k
        print(f"  {k:24s} {N[k]:6d}  attempt {1000 * T[tk]:7.1f} ms  {100 * T[tk] / D:5.2f}%")
    print(f"  attempt total {1000 * T['attempt_all']:.1f} ms ({100 * T['attempt_all'] / D:.2f}%), "
          f"of which _literal {1000 * T['attempt_literal']:.1f} ms, escalate {1000 * T['attempt_escalate']:.1f} ms")
    cone = sum(v for k, v in N.items() if k.startswith("cone_answer:"))
    print(f"cone queries {cone}: {dict((k, v) for k, v in N.items() if k.startswith('cone_answer:'))}")
    tot = 0
    for k in ("cone_assume", "cone_literal", "cone_escalate", "cone_search", "cone_swap"):
        tot += T[k]
        print(f"  {k:16s} {1000 * T[k]:7.1f} ms  {100 * T[k] / D:5.2f}%")
    ca = sum(T[k] for k in T if k.startswith("cone_attempt:"))
    print(f"  cone parts {1000 * tot:.1f} ms ({100 * tot / D:.2f}%); their first attempts "
          f"{1000 * ca:.1f} ms ({100 * ca / D:.2f}%)")
    if N["search_in_polluted"]:
        print("  search in polluted session:", N["search_in_polluted"])
    if ORACLE is None and len(sys.argv) > 4:
        open(sys.argv[4], "w").write(" ".join(map(str, CONE_IDX)))
        print(f"  cone query indices written to {sys.argv[4]}")
    if ORACLE is not None:
        print(f"  oracle: {N['oracle_skipped']} queries went to the cone without a first attempt")
elif mode == "b2":
    Session.node = node_b2
    Session.escalate = escalate_b2
    Engine.ask = ask_b2
    dt, bad = replay()
    D = plain or dt
    print(f"b2: instrumented pass {dt:.3f}s, mismatches {bad}; shares of {D:.3f}s")
    for k in list(T):
        if k.startswith(("rest:", "cone:")):
            T["all:" + k[5:]] += T[k]
    for k in list(N):
        if k.startswith(("rest:", "cone:")):
            N["all:" + k[5:]] += N[k]
    for tag in ("all:", "cone:"):
        print(f"-- {tag[:-1]} sessions: new nodes {N[tag + 'new']} (blocks {N[tag + 'blocks']}, "
              f"constants {N[tag + 'constants']}, with cached facts {N[tag + 'with_cached_facts']}, "
              f"with formula templates {N[tag + 'with_formulas']}, template memo hits "
              f"{N[tag + 'templates_hit']} / misses {N[tag + 'templates_miss']}); revisits {N[tag + 'revisit']}")
        for k in ("new_total", "lookup", "alloc", "templates_hit", "templates_miss", "ext_node_facts",
                  "rule_block", "cached_facts", "template_clauses", "formula_templates",
                  "revisit_total", "revisit_compile_pending", "escalate_total"):
            v = T[tag + k]
            n = N[tag + ("new" if k in ("new_total", "lookup", "alloc", "ext_node_facts", "rule_block",
                                        "cached_facts", "template_clauses", "formula_templates")
                         else k if k.startswith("templates") else "escalate" if k == "escalate_total"
                         else "revisit")]
            print(f"  {k:24s} {1000 * v:7.1f} ms  {100 * v / D:5.2f}%  {1e6 * v / max(n, 1):6.1f} us each")
