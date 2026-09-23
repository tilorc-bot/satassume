"""The assumptions engine.

One ``Engine`` answers two kinds of question with one propositional core:

* **context-free** queries, ``engine.is_(expr, 'positive')``, which replace
  the old ``expr.is_positive``.  Answers are cached per expression node, so
  repeated queries cost a dictionary lookup, exactly like the old system.
* **contextual** queries, ``engine.ask(formula, assumptions)``, which replace
  ``ask(Q.positive(expr), assumptions)``.  Assumptions enter the solver as
  solver assumptions (MiniSat style) under a selector literal, never as
  permanent clauses, so nothing derived under them leaks into the cache.

Both go through a ``Session``: an incremental solver plus a table mapping
``(predicate, node)`` atoms to variables.  Visiting a node instantiates the
single-node rule base for it, asserts its already-cached facts as unit
clauses, asserts the structural templates registered for its class, and
schedules the child nodes those templates mention.  Everything the solver
assigns at decision level 0 is a context-free fact and is written back to the
cache, so one query about ``x + y`` also caches facts about ``x`` and ``y``.
Search (CDCL) only runs when root-level propagation is inconclusive.

A context-free query gets a session of its own: discovery only visits the
cone of the queried expression, so search cost is bounded by the size of
that expression and never by what was asked before.  Contextual queries
reuse a session while the assumptions stay the same, which is the
incremental case (many questions under one ``assuming(...)`` block).
"""
from __future__ import annotations

from collections import OrderedDict, deque
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .compile import VarTable, compile_formula, formula_literal
from .formula import P, atoms_of
from .rules import NPRED, PREDICATES, PRED_INDEX, RULE_CLAUSES, RULE_INTERNAL
from .solver import Solver

Node = Any


class InconsistentAssumptions(ValueError):
    pass


# --------------------------------------------------------------------------
# Fact caches
# --------------------------------------------------------------------------

class DictCache:
    """Context-free facts per node, bounded in size, for use without SymPy."""

    def __init__(self, maxsize: int = 200_000):
        self.store: Dict[Node, Dict[str, Optional[bool]]] = {}
        self.maxsize = maxsize

    def facts(self, node: Node) -> Optional[Dict[str, Optional[bool]]]:
        return self.store.get(node)

    def get(self, node: Node, pred: str, default=None):
        d = self.store.get(node)
        return default if d is None else d.get(pred, default)

    def put(self, node: Node, pred: str, value: Optional[bool]) -> None:
        d = self.store.get(node)
        if d is None:
            if len(self.store) >= self.maxsize:
                self.store.clear()
            d = self.store[node] = {}
        d[pred] = value


class ObjectCache(DictCache):
    """Use the node's own ``_assumptions`` dict (SymPy's per-object FactKB)
    as the cache when it has one, falling back to a bounded dict otherwise.

    This is what makes the engine a drop-in for the old system: a cache hit is
    the same dictionary lookup ``expr.is_positive`` performs today, and the
    knowledge base symbols share per assumption signature is reused as-is.
    """

    def facts(self, node):
        d = getattr(node, '_assumptions', None)
        return d if d is not None else super().facts(node)

    def get(self, node, pred, default=None):
        d = getattr(node, '_assumptions', None)
        if d is not None:
            return d.get(pred, default)
        return super().get(node, pred, default)

    def put(self, node, pred, value):
        d = getattr(node, '_assumptions', None)
        if d is not None:
            if d is getattr(node, 'default_assumptions', None):
                # copy-on-write, mirroring sympy.core.assumptions.make_property
                d = node._assumptions = d.copy()
            d[pred] = value
        else:
            super().put(node, pred, value)


# --------------------------------------------------------------------------
# Session: one incremental solver over a growing set of nodes
# --------------------------------------------------------------------------

class Session:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.solver = Solver()
        self.table = VarTable()
        self.base: Dict[Node, int] = {}      # visited node -> variable of PREDICATES[0]
        self.read_pos = 0                    # cursor into solver.root_trail()
        self.oracle_done: Dict[Node, set] = {}
        self.nclauses = 0
        self.frontier: deque = deque()
        self.pending: Dict[Node, list] = {}   # node -> template formulas not yet compiled
        self.demand: Dict[Node, set] = {}     # node -> predicates the query needs about it

    # -- variables -------------------------------------------------------
    def var(self, pred: str, node: Node) -> int:
        return self.node(node) + PRED_INDEX[pred]

    def _emit(self, clause: List[int]) -> None:
        self.nclauses += 1
        self.solver.add_clause(clause)

    def node(self, node: Node, demanded=None) -> int:
        """Visit ``node`` if new; return its base variable.

        ``demanded`` is the set of predicates about ``node`` that the current
        query is interested in (``None`` means all).  Template formulas that
        do not mention a demanded predicate of the node are parked in
        ``self.pending`` and only compiled by :meth:`escalate`, so the common
        case (a direct structural rule decides the query) never pays for the
        long tail of rules.
        """
        b = self.base.get(node)
        if b is not None:
            if demanded is not None and node in self.pending:
                self._compile_pending(node, demanded)
            return b
        table = self.table
        b = table.node_base(node)
        self.base[node] = b
        constructing = self.engine._constructing
        constructing.add(node)
        emit = self._emit
        # 1. single-node rule base (bulk path, no per-clause sanitising)
        self.solver.add_pattern(RULE_INTERNAL, b, NPRED)
        self.nclauses += len(RULE_INTERNAL)
        # 2. cached context-free facts
        facts = self.engine.cache.facts(node)
        if facts:
            for p, v in facts.items():
                if v is not None and p in PRED_INDEX:
                    emit([b + PRED_INDEX[p] if v else -(b + PRED_INDEX[p])])
        # 3. structural templates
        items = [(f, atoms_of(f)) for f in self.engine.templates(node)]
        if items:
            if demanded is None:
                self._compile(node, items)
            else:
                self.pending[node] = items
                self._compile_pending(node, demanded)
        constructing.discard(node)
        return b

    def _compile(self, node: Node, items) -> None:
        """Compile ``(formula, atoms)`` pairs of ``node``; schedule the
        children they mention with the predicates demanded of them."""
        table = self.table
        emit = self._emit
        demand = self.demand
        for f, atoms in items:
            for atom in atoms:
                if atom.expr != node:
                    d = demand.get(atom.expr)
                    if d is None:
                        d = demand[atom.expr] = set()
                    d.add(atom.pred)
            compile_formula(f, table, emit)
        for child in table.new_nodes:
            if child not in self.base:
                self.frontier.append(child)
        table.new_nodes = []

    def _compile_pending(self, node: Node, demanded) -> None:
        pend = self.pending.get(node)
        if not pend:
            return
        want = set()
        for p in demanded:
            want.update(neighbourhood(p))
        now, later = [], []
        for item in pend:
            f, atoms = item
            for a in atoms:
                if a.expr == node and a.pred in want:
                    now.append(item)
                    break
            else:
                later.append(item)
        if later:
            self.pending[node] = later
        else:
            del self.pending[node]
        if now:
            self._compile(node, now)

    def ensure(self, node: Node, demanded=None, budget: Optional[int] = None) -> None:
        """Demand-driven discovery: visit ``node`` and, breadth-first, the
        nodes its templates mention, up to ``budget`` new nodes."""
        budget = self.engine.discovery_budget if budget is None else budget
        if demanded is not None:
            self.demand.setdefault(node, set()).update(demanded)
        self.frontier = deque([node])
        added = 0
        while self.frontier and added < budget:
            n = self.frontier.popleft()
            if n in self.base and n not in self.pending:
                continue
            self.node(n, None if demanded is None else self.demand.get(n, set()))
            added += 1
        self.frontier = deque()

    def escalate(self, budget: Optional[int] = None) -> None:
        """Compile every parked formula (full instantiation of the cone)."""
        budget = self.engine.discovery_budget if budget is None else budget
        added = 0
        while self.pending and added < budget:
            node, formulas = self.pending.popitem()
            self._compile(node, formulas)
            added += 1
            while self.frontier and added < budget:
                n = self.frontier.popleft()
                if n not in self.base:
                    self.node(n, None)
                    added += 1
        self.frontier = deque()

    # -- root facts -> cache ------------------------------------------------
    def writeback(self) -> None:
        trail = self.solver.root_trail()
        atom_of = self.table.atom_of
        cache = self.engine.cache
        for lit in trail[self.read_pos:]:
            atom = atom_of[abs(lit)]
            if atom is not None:
                cache.put(atom.expr, atom.pred, lit > 0)
        self.read_pos = len(trail)

    # -- queries -------------------------------------------------------------
    def query_literal(self, lit: int, assumptions: Iterable[int] = (),
                      search: bool = True) -> Optional[bool]:
        solver = self.solver
        if not solver.propagate():
            raise InconsistentAssumptions("rule base or cached facts are inconsistent")
        self.writeback()
        assumptions = list(assumptions)
        if assumptions:
            # consistency of the assumptions is checked first, even when the
            # query is already decided at root, mirroring sympy.ask
            implied = solver.implied(assumptions)
            if implied is None:
                raise InconsistentAssumptions("inconsistent assumptions")
            s = set(implied)
            if lit in s:
                return True
            if -lit in s:
                return False
        else:
            v = solver.value(lit)
            if v is not None:
                return v
        if not search:
            return None
        try:
            r = solver.entails(lit, assumptions)
        except ValueError as e:
            raise InconsistentAssumptions(str(e)) from e
        self.writeback()
        return r

    def assume_formula(self, f) -> List[int]:
        """Turn a formula into solver assumption literals: its clauses are
        guarded by a fresh selector variable ``s`` and ``s`` is assumed."""
        for atom in atoms_of(f):
            self.ensure(atom.expr, {atom.pred})
        s = self.table.aux()

        def emit(clause):
            self._emit(clause + [-s])
        compile_formula(f, self.table, emit)
        return [s]

    def literal_of(self, f) -> int:
        for atom in atoms_of(f):
            self.ensure(atom.expr, {atom.pred})
        return formula_literal(f, self.table, self._emit)


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------

class Engine:
    """See module docstring.

    Parameters
    ----------
    templates : callable(node) -> iterable of formulas, or None
        Structural clause generators.  Defaults to the SymPy template
        registry if importable, else no templates.
    cache : DictCache
        Where context-free facts live.  Defaults to ``ObjectCache``.
    oracle : bool
        When True, and a context-free query is still unknown after propagation
        and search, fall back to the node's old-system ``_eval_is_*`` handlers
        (SymPy's ``_prop_handler`` map) as unit-clause oracles, walking the
        rule-base prerequisites like ``sympy.core.assumptions._ask`` does.
        This makes the engine complete relative to the old system on day one
        while templates replace handlers class by class.
    discovery_budget : int
        Maximum new nodes visited per query.
    session_limit : int
        A reused contextual session is replaced once it has visited this
        many nodes.
    keep_sessions : int
        How many contextual sessions (distinct assumption sets) to keep.
    """

    def __init__(self, templates=None, cache: Optional[DictCache] = None,
                 oracle: bool = False, discovery_budget: int = 400,
                 session_limit: int = 2000, keep_sessions: int = 4):
        if templates is None:
            try:
                from .templates import registry
                templates = registry.facts_for
            except Exception:  # pragma: no cover - SymPy not installed
                templates = lambda node: ()
        self.templates = templates
        self.cache = cache if cache is not None else ObjectCache()
        self.oracle = oracle
        self.discovery_budget = discovery_budget
        self.session_limit = session_limit
        self.keep_sessions = keep_sessions
        self._context_sessions: "OrderedDict[Any, Tuple[Session, List[int]]]" = OrderedDict()
        self._constructing: set = set()
        self.stats = {"queries": 0, "cache_hits": 0, "escalations": 0,
                      "searches": 0, "oracle_calls": 0, "sessions": 0}

    def _fresh_session(self) -> Session:
        self.stats["sessions"] += 1
        return Session(self)

    def _context_session(self, assumptions) -> Tuple[Session, List[int]]:
        hit = self._context_sessions.get(assumptions)
        if hit is not None and len(hit[0].base) <= self.session_limit:
            self._context_sessions.move_to_end(assumptions)
            return hit
        s = self._fresh_session()
        lits = s.assume_formula(assumptions)
        self._context_sessions[assumptions] = (s, lits)
        while len(self._context_sessions) > self.keep_sessions:
            self._context_sessions.popitem(last=False)
        return s, lits

    # -- context-free ---------------------------------------------------------
    def is_(self, node: Node, pred: str) -> Optional[bool]:
        """Context-free truth value of ``pred(node)``; cached on the node."""
        facts = self.cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            return facts[pred]
        if node in self._constructing:
            # re-entrant query from a template evaluating this very node
            return None
        self.stats["queries"] += 1
        s = self._fresh_session()
        s.ensure(node, {pred})
        lit = s.base[node] + PRED_INDEX[pred]
        r = s.query_literal(lit, search=False)
        if r is None and s.pending:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(lit, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, search=True)
        if r is None and self.oracle:
            r = self._oracle(s, node, pred)
        self.cache.put(node, pred, r)
        return r

    def _oracle(self, s: Session, node: Node, pred: str) -> Optional[bool]:
        handlers = getattr(node, '_prop_handler', None)
        if not handlers:
            return None
        if s.pending:
            s.escalate()
        done = s.oracle_done.setdefault(node, set())
        b = s.base[node]
        lit = b + PRED_INDEX[pred]
        solver = s.solver
        for p in prereq_order(pred):
            h = handlers.get(p)
            if h is None or p in done:
                continue
            pv = b + PRED_INDEX[p]
            if solver.value(pv) is not None:
                # already decided: sympy's _ask never calls the handler then
                # (class-level constants shadow inherited handlers, and the
                # inherited handler may be wrong for this class)
                continue
            done.add(p)
            self.stats["oracle_calls"] += 1
            v = h(node)
            if v is None:
                continue
            s._emit([pv if v else -pv])
            r = s.query_literal(lit, search=False)
            if r is not None:
                return r
        return s.query_literal(lit, search=True)

    # -- contextual -----------------------------------------------------------
    def ask(self, proposition, assumptions=None) -> Optional[bool]:
        """Truth value of ``proposition`` (a formula over ``P`` atoms) given
        ``assumptions`` (a formula or None).  Raises
        ``InconsistentAssumptions`` if the assumptions contradict the facts.
        """
        self.stats["queries"] += 1
        lits: List[int] = []
        if assumptions is not None and assumptions is not True:
            s, lits = self._context_session(assumptions)
        else:
            s = self._fresh_session()
        if isinstance(proposition, P):
            s.ensure(proposition.expr, {proposition.pred})
            q = s.base[proposition.expr] + PRED_INDEX[proposition.pred]
        else:
            q = s.literal_of(proposition)
        r = s.query_literal(q, lits, search=False)
        if r is None and s.pending:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(q, lits, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(q, lits, search=True)
        return r


# --------------------------------------------------------------------------
# prerequisite order for the oracle walk (mirrors FactRules.prereq)
# --------------------------------------------------------------------------

_PREREQ: Dict[str, List[str]] = {}
_NEIGH: Dict[str, frozenset] = {}


def neighbourhood(pred: str) -> frozenset:
    """``pred`` plus every predicate sharing a rule clause with it."""
    n = _NEIGH.get(pred)
    if n is None:
        i = PRED_INDEX[pred]
        acc = {pred}
        for c in RULE_CLAUSES:
            idx = [abs(l) - 1 for l in c]
            if i in idx:
                acc.update(PREDICATES[j] for j in idx)
        n = _NEIGH[pred] = frozenset(acc)
    return n


def prereq_order(pred: str) -> List[str]:
    """``pred`` first, then every predicate that can influence it through the
    rule base, breadth-first by rule distance."""
    cached = _PREREQ.get(pred)
    if cached is not None:
        return cached
    adj: Dict[int, set] = {i: set() for i in range(NPRED)}
    for c in RULE_CLAUSES:
        idx = [abs(l) - 1 for l in c]
        for i in idx:
            adj[i].update(j for j in idx if j != i)
    start = PRED_INDEX[pred]
    order = [start]
    seen = {start}
    q = deque([start])
    while q:
        i = q.popleft()
        for j in sorted(adj[i]):
            if j not in seen:
                seen.add(j)
                order.append(j)
                q.append(j)
    res = [PREDICATES[i] for i in order]
    _PREREQ[pred] = res
    return res
