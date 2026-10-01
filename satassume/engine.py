"""The assumptions engine.

One ``Engine`` answers two kinds of question with one propositional core:

* **contextual** queries, ``engine.ask(formula, assumptions)``, behind
  ``ask(Q.positive(expr), assumptions)`` (see :mod:`satassume.sympy_api`
  for the scope).  Assumptions enter the solver as solver assumptions
  (MiniSat style) under a selector literal, never as permanent clauses, so
  nothing derived under them leaks into the cache.
* **context-free** queries, ``engine.is_(expr, 'positive')``, used for
  ``ask`` without assumptions and by the corpus tools.  Answers are cached
  per expression node, so repeated queries cost a dictionary lookup, the
  way the old ``expr.is_positive`` works; replacing that old system with
  this path is the long-term goal, not the current scope.

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

Everything the engine keeps between queries (the fact caches, the reused
sessions, the answer and split memos) is a function of the registry state:
the registered clause-generating functions (``satassume.extensions``), the
structural templates and the theory adapters.  Every change of that state
starts a new registry epoch (:mod:`satassume.epoch`); every query compares
the epoch its caches were filled under with the current one
(``Engine._check_version``) and drops them all on a change, so an answer
never depends on what was registered when an earlier query ran.  A reused
session that a query under it made raise, or whose clause set the query's
own nodes made unsatisfiable at root, is dropped (``dead_sessions``): the
next query under the same assumptions builds a fresh one, as a fresh
engine would, so that query alone raises.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .compile import VarTable, compile_formula, formula_literal
from .epoch import EPOCH as _EPOCH, bump as _bump
from .formula import P, atoms_of
from .relations import RELATION_ATOMS, Relations, Uninterpreted
from .rules import NPRED, PRED_INDEX, PREDICATES, RULE_CLAUSES, RULE_INTERNAL
from .solver import BOTTOM, BlockOwner, Solver

Node = Any


#: the verdicts of an assumption set (``Engine.verdict``): only
#: ``INCONSISTENT`` makes a query raise; ``UNKNOWN`` (a theory gave up, the
#: cone was truncated, the check could not conclude) never does
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
UNKNOWN = "unknown"


class InconsistentAssumptions(ValueError):
    pass


#: Engine(writeback=...) policies (Session.writeback); the first is the default
_WRITEBACK = ("root-only", "provenance", "all")

#: the home of a root literal whose provenance was not established cheaply
#: (Session._home_of)
_FOREIGN = object()
#: a missing memo entry (Session._home_of, Session._cone)
_NO_STEP = object()


def _kid(atom):
    """The object an atom of a template makes part of the cone: the
    argument of a vocabulary atom, a custom atom itself (its extension
    facts are its own, Session._custom)."""
    return atom.expr if atom.pred in PRED_INDEX else atom


# --------------------------------------------------------------------------
# Fact caches
# --------------------------------------------------------------------------

class DictCache:
    """Context-free facts per node, owned by the engine, bounded in size.

    Where facts come from (the trust principle):

    * the engine's inputs from SymPy objects are only what the structural
      templates read: the assumptions a ``Symbol`` was *declared* with
      (``assumptions0``, see ``satassume/templates/atoms.py``) and the
      old-system properties of objects with a fixed value (numbers, ``pi``,
      ``oo``, ...), where every non-None property is a static fact;
    * everything else is derived by the engine, and only the facts the
      solver derives at decision level 0 (from the rule base, the templates
      and the facts above, never from a query's assumptions) are stored
      here.

    The cache is keyed by the node (hash and ``==``), so structurally equal
    nodes share facts, which is sound because a node's context-free facts
    depend only on its structure and declared assumptions.

    The facts also depend on the registrations in force (a vocabulary
    handler adds facts to a node's block, a template derives them), so the
    cache records the registry epoch (:mod:`satassume.epoch`) it was created
    under and every engine using it drops its contents when that epoch is
    over (``Engine._check_version``); a cache shared between engines, or
    given to an engine created after a registration, is dropped like the
    engine's own.

    The engine never reads or writes SymPy's per-object ``_assumptions``.
    Reading it would import whatever SymPy's ``_eval_is_*`` handlers cached
    as if it were unconditional (they can be wrong: ``(0**n).is_finite`` is
    True for a plain ``n``, although ``0**-1`` is ``zoo``; with that fact
    ``Q.negative(n)`` looked inconsistent).  Writing to it would change
    ``expr.is_*`` for SymPy users, and a ``Symbol``'s ``_assumptions`` is
    one ``StdFactKB`` shared by every symbol created with the same
    assumptions, so a derived fact about ``n`` would become a fact about
    every plain symbol.
    """

    def __init__(self, maxsize: int = 200_000):
        self.store: Dict[Node, Dict[str, Optional[bool]]] = {}
        self.maxsize = maxsize
        #: the registry epoch the facts were derived under
        self._epoch = _EPOCH[0]

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


class AnswerMemo(dict):
    """Answers of whole queries, bounded in size (cleared when full), and
    cleared by the engine when the registry epoch changes
    (``Engine._check_version``)."""

    def __init__(self, maxsize: int = 100_000):
        super().__init__()
        self.maxsize = maxsize

    def put(self, key, value) -> None:
        if len(self) >= self.maxsize:
            self.clear()
        self[key] = value


#: Former default cache, which used SymPy's per-object ``_assumptions`` as
#: storage; it read facts SymPy's handlers had cached as unconditional and
#: wrote derived facts into fact bases shared between symbols (see
#: ``DictCache``).  Kept as a name so existing imports keep working.
ObjectCache = DictCache


# --------------------------------------------------------------------------
# Session: one incremental solver over a growing set of nodes
# --------------------------------------------------------------------------

class Session:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.solver = Solver()
        #: Engine(writeback="provenance"): record clause owners
        #: (``solver.owner`` around every emission) for its rule; under the
        #: other policies no provenance bookkeeping runs at all
        self.track = engine._writeback == "provenance"
        self.solver.track_owners = self.track
        # the single-node rule base, propagated by the solver from shared
        # tables instead of 79 clauses per node (Solver.register_block)
        self.solver.set_rule_block(RULE_INTERNAL, NPRED)
        self.table = VarTable()
        self.base: Dict[Node, int] = {}      # visited node -> variable of PREDICATES[0]
        self.read_pos = 0                    # cursor into solver.root_trail()
        self.nclauses = 0
        self.frontier: deque = deque()
        self.pending: Dict[Node, list] = {}   # node -> template formulas not yet compiled
        self.pending_c: Dict[Node, list] = {}  # node -> (clauses, bases) pairs not yet emitted
        self.demand: Dict[Node, set] = {}     # node -> predicate indices the query needs
        self.deferred: List[Node] = []        # derived nodes, visited only by escalate()
        self.n_assumption_nodes = 0           # nodes visited by assume_formula()
        #: nodes that are closed irrational constants (pi, 1/pi); they do
        #: not count as pollution (Engine.cone_threshold)
        self.n_constants = 0
        #: the verdict of the assumption set from the complete check run at
        #: construction (``Engine._context_session``); None outside it
        self.verdict: Optional[str] = None
        self.n_assumption_constants = 0
        self.literals: Dict[Any, int] = {}    # compound formula -> Tseitin literal
        self.assumption_formula = None       # the formula of assume_formula()
        #: relation atoms and their theories (satassume.relations); created
        #: at the first user formula when the engine has relation support
        self.relations: Optional[Relations] = None
        #: sums under a sign atom -> their free symbols (:meth:`_affine_links`)
        self._sign_sums: Dict[Any, frozenset] = {}
        #: the Relations object once predicate transfer is engaged
        #: (Relations._engage_transfer); None on every other path
        self.xfer = None
        # -- provenance writeback (see writeback) --
        #: node (or custom atom) -> ``(kids, weight)`` (:meth:`_struct`):
        #: the objects its templates (its extension facts) mention, one
        #: level of the structural cone, and its cost to a fresh session's
        #: budget; a function of the object and the registry, computed on
        #: demand (only for objects a writeback decision needs), whether or
        #: not this session visited the object
        self.kids: Dict[Any, Any] = {}
        #: object -> its structural cone (a frozenset, the object included)
        #: if its weight fits ``discovery_budget``, else None (:meth:`_cone`)
        self._cones: dict = {}
        self._cone_budget = engine.discovery_budget
        #: a budget cut dropped work: :meth:`_discover` or :meth:`escalate`
        #: stopped on the discovery budget with unvisited nodes (new, or
        #: with parked templates) on its frontier, or :meth:`escalate`
        #: stopped with parked templates or derived nodes left.  Once set,
        #: it stays.  The session may lack part of a cone in a way
        #: ``incomplete`` misses: it writes nothing back
        #: (:meth:`writeback`, ``Engine.is_``) and its set's complete check
        #: gives ``UNKNOWN`` (``Engine._complete_check``).  Frontier nodes
        #: already visited with nothing parked do not count: dropping them
        #: drops no work.
        self.truncated = False
        #: the session asserted a cached fact (``engine.cache``,
        #: ``custom_cache``): Engine._put_result
        self.used_cache = False
        self._prov_memo: dict = {}           # var -> owners (Solver.provenance)
        #: var -> its home (see _home_of), _FOREIGN if not established
        self._home: dict = {}

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
            if demanded is not None and (node in self.pending or node in self.pending_c):
                if self.track:
                    solver = self.solver
                    prev_owner = solver.owner
                    solver.owner = node
                    try:
                        self._compile_pending(node, demanded)
                    finally:
                        solver.owner = prev_owner
                else:
                    self._compile_pending(node, demanded)
            return b
        table = self.table
        b = table.node_base(node)
        self.base[node] = b
        if getattr(node, "is_number", False) and not node.is_Rational \
                and not node.free_symbols:
            self.n_constants += 1
        table.new_nodes = []
        constructing = self.engine._constructing
        constructing.add(node)
        if not self.track:
            self._visit(node, b, demanded)
            constructing.discard(node)
            return b
        solver = self.solver
        prev_owner = solver.owner
        solver.owner = node
        try:
            self._visit(node, b, demanded)
        finally:
            solver.owner = prev_owner
            constructing.discard(node)
        return b

    def _visit(self, node: Node, b: int, demanded) -> None:
        """The body of :meth:`node` (``solver.owner`` is ``node`` if the
        session tracks owners)."""
        engine = self.engine
        # 1. structural templates, and vocabulary predicates registered for
        #    the node's class (satassume.extensions)
        if engine.clause_templates is not None:
            compiled, formulas = engine.clause_templates(node)
        else:
            compiled, formulas = (), engine._templates(node)
        ext = engine._extensions
        if ext is not None and ext._vocab:
            formulas = list(formulas) + ext.node_facts(node)
        items = [(f, atoms_of(f)) for f in formulas] if formulas else None
        # 2. single-node rule base (registered with the solver's rule-block
        #    propagator, no clauses), unless the node is a constant whose
        #    closed unit facts decide everything the rule base could say
        if not (len(compiled) == 1 and compiled[0].pattern.complete and not formulas):
            # the node's own literals its patterns are about to mention
            # (see _split), so that registering does not start them lazy
            own = 0
            if compiled:
                want = None if demanded is None else want_of(demanded)
                for comp in compiled:
                    k0 = comp.pattern.node
                    for k, m in _split(comp.pattern.clauses, want)[3]:
                        if k == k0:
                            own |= m
            self.solver.register_block(b, own)
        else:
            self.solver.ensure_vars(b + NPRED - 1)
        # 3. cached context-free facts
        facts = engine.cache.facts(node)
        if facts:
            self.used_cache = True
            self._add_clauses([[b + PRED_INDEX[p]] if v else [-(b + PRED_INDEX[p])]
                               for p, v in facts.items() if v is not None and p in PRED_INDEX])
        if compiled:
            self._compile_patterns(node, compiled, demanded)
        if items:
            if demanded is None:
                self._compile(node, items)
            else:
                self.pending[node] = items
                self._compile_pending(node, demanded)

    def _add_clauses(self, clauses) -> None:
        self.nclauses += len(clauses)
        self.solver.add_clauses(clauses)

    # -- compiled template patterns (the fast path) -------------------------
    def _compile_patterns(self, node: Node, compiled, demanded) -> None:
        """Emit the clauses of the compiled patterns of ``node`` (see
        ``satassume.templates._common.Pattern``): allocate the variable
        blocks of the objects the patterns mention, emit the clauses about
        a demanded predicate of the node now and park the rest, schedule the
        newly seen direct arguments (frontier) and derived nodes (deferred).
        """
        table = self.table
        base_of = table.base_of
        demand = self.demand
        want = None if demanded is None else want_of(demanded)
        for comp in compiled:
            objs, pat = comp.objs, comp.pattern
            bases = [0] * len(objs)
            new = []
            for k in pat.used:
                o = objs[k]
                bb = base_of.get(o)
                if bb is None:
                    bb = table.node_base(o)
                    new.append(k)
                bases[k] = 2 * bb
            _, now, later, ment = _split(pat.clauses, want)
            if later is not None:
                self.pending_c.setdefault(node, []).append((later, bases))
            if now:
                self._emit_pattern(now, bases, ment)
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
        table.new_nodes = []

    def _emit_pattern(self, clauses, bases, ment=None) -> None:
        """``bases[k]`` is twice the base variable of slot ``k``; ``ment``
        the slots' mention masks of ``clauses`` (see :func:`_split`)."""
        if ment is None:
            ment = _split(clauses, None)[3]
        self.nclauses += len(clauses)
        solver = self.solver
        solver.ensure_vars(len(self.table))
        solver.add_internal([[bases[k] + off for k, off in li] for _, _, li in clauses],
                            [(bases[k] >> 1, m) for k, m in ment])

    def _compile(self, node: Node, items) -> None:
        """Compile ``(formula, atoms)`` pairs of ``node``; schedule the
        children they mention with the predicates demanded of them.

        A template may mention a *derived* node that is not a direct
        argument (``2*e`` of a power, ``x - 1`` of a logarithm).  Such nodes
        are only visited by :meth:`escalate`, so a query decided by the
        direct structure never pays for them; when the assumptions mention
        the derived node it is already visited and its atoms are shared.
        """
        table = self.table
        emit = self._emit
        demand = self.demand
        for f, atoms in items:
            for atom in atoms:
                if atom.expr != node and atom.pred in PRED_INDEX:
                    d = demand.get(atom.expr)
                    if d is None:
                        d = demand[atom.expr] = set()
                    d.add(PRED_INDEX[atom.pred])
            compile_formula(f, table, emit)
        self._flush(node)

    def _flush(self, node: Node = None) -> None:
        """Schedule the nodes newly mentioned by compiled formulas, and run
        the clause generators of newly seen custom atoms.  ``node`` is the
        node whose templates were compiled (its direct arguments go to the
        frontier, other nodes are deferred); None schedules everything."""
        table = self.table
        while table.new_custom:
            atoms, table.new_custom = table.new_custom, []
            for atom in atoms:
                self._custom(atom)
        direct = getattr(node, 'args', None) if node is not None else None
        for child in table.new_nodes:
            if child in self.base:
                continue
            if direct is not None and child not in direct:
                self.deferred.append(child)
            else:
                self.frontier.append(child)
        table.new_nodes = []

    def _custom(self, atom: P) -> None:
        """A custom-predicate atom was allocated: assert its cached value
        and the formulas its registered functions generate."""
        engine = self.engine
        v = engine.custom_cache.get(atom.expr, atom.pred)
        var = self.table.custom[atom]
        solver = self.solver
        prev_owner = solver.owner
        track = self.track
        if v is not None:
            self.used_cache = True
            if track:
                # a cached custom fact is the atom's own (a relation atom's:
                # its interpretation is glue, so unowned)
                solver.owner = BOTTOM if atom.pred in RELATION_ATOMS else atom
                try:
                    self._emit([var if v else -var])
                finally:
                    solver.owner = prev_owner
            else:
                self._emit([var if v else -var])
        if atom.pred in RELATION_ATOMS and engine._relation_specs:
            rel = self.relations
            if rel is None:
                rel = self.relations = Relations(self, engine._relation_specs)
                if self.assumption_formula is not None:
                    # unary atoms of the assumptions become link candidates
                    rel.note_formula(atoms_of(self.assumption_formula))
            rel.enqueue(atom)
            return
        ext = engine._extensions
        if ext is None:
            return
        if not track:
            for f in ext.facts_for(atom):
                compile_formula(f, self.table, self._emit)
            return
        solver.owner = atom
        try:
            for f in ext.facts_for(atom):
                compile_formula(f, self.table, self._emit)
        finally:
            solver.owner = prev_owner

    def _compile_pending(self, node: Node, demanded) -> None:
        """Compile the parked formulas and clauses of ``node`` that mention
        a predicate in the neighbourhood of ``demanded`` (indices).  The
        caller sets ``solver.owner`` to ``node`` if the session tracks
        owners."""
        want = want_of(demanded)
        pend_c = self.pending_c.get(node)
        if pend_c:
            keep = []
            for clauses, bases in pend_c:
                _, now, later, ment = _split(clauses, want)
                if now:
                    self._emit_pattern(now, bases, ment)
                    if later is not None:
                        keep.append((later, bases))
                else:
                    keep.append((clauses, bases))
            if keep:
                self.pending_c[node] = keep
            else:
                del self.pending_c[node]
        pend = self.pending.get(node)
        if not pend:
            return
        now, later = [], []
        for item in pend:
            f, atoms = item
            for a in atoms:
                if a.expr == node and PRED_INDEX.get(a.pred) in want:
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
        nodes its templates mention, up to ``budget`` new nodes.

        A visited node with nothing parked is only recorded (the discovery
        below would skip it at once)."""
        if demanded is not None:
            self.demand.setdefault(node, set()).update(PRED_INDEX[p] for p in demanded)
        if node in self.base and node not in self.pending and node not in self.pending_c:
            if self.frontier:
                self.frontier = deque()
            return
        self.frontier = deque([node])
        self._discover(demanded, budget)

    def _discover(self, demanded=None, budget: Optional[int] = None) -> None:
        budget = self.engine.discovery_budget if budget is None else budget
        added = 0
        pending, pending_c = self.pending, self.pending_c
        while self.frontier and added < budget:
            n = self.frontier.popleft()
            if n in self.base and n not in pending and n not in pending_c:
                continue
            self.node(n, None if demanded is None else self.demand.get(n, set()))
            added += 1
        if self.frontier:
            base = self.base
            if any(n not in base or n in pending or n in pending_c for n in self.frontier):
                self.truncated = True
        self.frontier = deque()

    @property
    def incomplete(self) -> bool:
        """True while :meth:`escalate` has something left to do."""
        return bool(self.pending or self.pending_c or self.deferred)

    def escalate(self, budget: Optional[int] = None) -> None:
        """Compile every parked formula and visit every derived node (full
        instantiation of the cone)."""
        budget = self.engine.discovery_budget if budget is None else budget
        added = 0
        solver = self.solver
        prev_owner = solver.owner
        track = self.track
        while (self.pending or self.pending_c or self.deferred or self.frontier) \
                and added < budget:
            if self.pending_c:
                node, pend = self.pending_c.popitem()
                if not track:
                    for clauses, bases in pend:
                        self._emit_pattern(clauses, bases)
                else:
                    solver.owner = node
                    try:
                        for clauses, bases in pend:
                            self._emit_pattern(clauses, bases)
                    finally:
                        solver.owner = prev_owner
                added += 1
            elif self.pending:
                node, formulas = self.pending.popitem()
                if not track:
                    self._compile(node, formulas)
                else:
                    solver.owner = node
                    try:
                        self._compile(node, formulas)
                    finally:
                        solver.owner = prev_owner
                added += 1
            elif self.frontier:
                n = self.frontier.popleft()
                if n not in self.base:
                    self.node(n, None)
                    added += 1
            else:
                n = self.deferred.pop()
                if n not in self.base:
                    self.node(n, None)
                    added += 1
        if self.pending or self.pending_c or self.deferred or self.frontier:
            base = self.base
            if self.pending or self.pending_c or any(n not in base for n in self.deferred) \
                    or any(n not in base for n in self.frontier):
                self.truncated = True
        self.frontier = deque()

    # -- root facts -> cache ------------------------------------------------
    def writeback(self) -> None:
        """Write the new root facts to the context-free caches, by the
        policy ``Engine(writeback=...)``:

        ``"root-only"`` (default)
            Nothing here: ``Engine._put_result`` writes the answer of an
            ``Engine.is_`` session and the other facts about its queried
            node, when a fresh ``is_`` is known to give them
            (``Engine._put_root_only``); contextual sessions write nothing.
            No provenance bookkeeping runs (``Session.track``).
        ``"provenance"`` (opt-in)
            A fact about node ``D`` (or custom atom ``D``) is written only if
            the session is not budget-truncated, its *provenance* (the
            owners of the clauses in its reason DAG, ``Solver.provenance``,
            the root facts that shortened a clause included) lies in
            ``cone(D)`` (``D``'s own rule block, templates, extension facts
            and cached facts, and those of the objects its templates
            mention, transitively: :meth:`_struct`), never a learnt or theory
            clause, relation glue or the assumptions (``BOTTOM``), and
            ``cone(D)`` *fits the discovery budget* (:meth:`_cone`).  Every
            clause of ``cone(D)`` is then loaded by a fresh
            ``Engine.is_(D, ...)``, which runs out of budget neither in
            discovery nor in escalation (:meth:`_cone` says why), and unit
            propagation is confluent, so that query derives the fact, or is
            decided by propagation before it escalates, soundly and so the
            same way: the cache stays a memo of ``is_`` (DESIGN.md 2.4; by
            induction, cached facts of ``cone(D)`` asserted here are
            themselves such memos, entailed by their own cones).  Neither
            condition depends on the session's own budget or history: facts
            of an earlier writeback of a session that a later escalation
            truncates satisfy both too.  More cache reuse than
            ``"root-only"`` (facts about every node of a session, contextual
            ones included), at the measured cost of the owner bookkeeping
            and the cone tests.
        ``"all"``
            Every root literal, as before the provenance rule.  History-
            dependent (a fact found with another node's template, a learnt
            clause or relation glue is served later as a context-free fact):
            kept for measurement only.

        Refusals are counted in ``Engine.stats``: ``writeback_refused``
        (provenance outside the cone), ``writeback_budget`` (the cone does
        not fit the budget).
        """
        engine = self.engine
        policy = engine._writeback
        if policy == "root-only":
            return
        trail = self.solver.root_trail()
        start = self.read_pos
        self.read_pos = len(trail)
        if start == len(trail):
            return
        if policy != "all":
            if self.truncated:
                return
            self._sync_budget()
        slots = self.table.slots
        cache = engine.cache
        custom = engine.custom_cache
        if policy == "all":
            for lit in trail[start:]:
                v = abs(lit)
                atom = slots[v]
                if type(atom) is tuple:
                    # a node block's variable (VarTable.slots): P(pred, node)
                    node, b = atom
                    cache.put(node, PREDICATES[v - b], lit > 0)
                elif atom is not None:
                    if atom.pred in PRED_INDEX:
                        cache.put(atom.expr, atom.pred, lit > 0)
                    else:
                        custom.put(atom.expr, atom.pred, lit > 0)
            return
        stats = engine.stats
        cone_of = self._cone
        home_of = self._home_of
        for lit in trail[start:]:
            v = abs(lit)
            atom = slots[v]
            if type(atom) is tuple:
                # a node block's variable (VarTable.slots): P(pred, node)
                subject, b = atom
                pred = PREDICATES[v - b]
                c, key = cache, subject
            elif atom is None:
                continue                        # auxiliary: never written
            else:
                pred = atom.pred
                if pred in PRED_INDEX:
                    subject = key = atom.expr
                    c = cache
                elif pred in RELATION_ATOMS:
                    continue                    # interpreted by glue: never written
                else:
                    subject, key, c = atom, atom.expr, custom
            d = c.facts(key)
            if d is not None and pred in d:
                continue                        # cached: no home needed
            if cone_of(subject) is None:
                stats["writeback_budget"] += 1
                continue
            if home_of(v, subject) is _FOREIGN and not self._walk(v, subject):
                stats["writeback_refused"] += 1
                continue
            c.put(key, pred, lit > 0)

    def _sync_budget(self) -> None:
        """Drop the cone and home memos if ``Engine.discovery_budget``
        changed since they were filled (whether a cone fits depends on it)."""
        budget = self.engine.discovery_budget
        if budget != self._cone_budget:
            self._cone_budget = budget
            self._cones.clear()
            self._home.clear()

    def _subject(self, v: int):
        """What the root literal of ``v`` is about, for :meth:`_home_of`:
        its node, its custom atom, or None (an auxiliary variable, a
        relation atom: never written back)."""
        atom = self.table.slots[v]
        if type(atom) is tuple:
            return atom[0]
        if atom is None:
            return None
        pred = atom.pred
        if pred in PRED_INDEX:
            return atom.expr
        if pred in RELATION_ATOMS:
            return None
        return atom

    def _home_of(self, v: int, subject) -> Any:
        """The *home* of the root assignment of ``v``: an object ``H``
        with ``provenance(v) <= cone(H)`` (``H`` included), or ``_FOREIGN``
        when that is not established by this cheap test (the caller then
        walks).

        The test looks at one step of the reason DAG only: the owner ``o``
        of ``v``'s reason (its rule block's node, its template's node, ...)
        and the homes of its antecedents (computed first, the same way,
        with their own subjects; memoized, so each root literal is looked
        at once per session, and only literals some writeback needs).  ``H``
        is ``subject`` (the node or custom atom ``v`` is about), or ``o``
        for an auxiliary variable.  If ``o`` and every antecedent's home
        are in ``cone(H)``, then, by induction over the reason DAG (root
        reasons only point to earlier root literals), every owner of
        ``v``'s reason DAG is in ``cone(H)``: an antecedent's provenance
        lies in ``cone(h)`` and ``cone(h) <= cone(H)`` for ``h`` in
        ``cone(H)`` (cones are closed under :meth:`_struct`'s kids).  So
        ``home == D`` implies exactly what the provenance rule of
        :meth:`writeback` asks for ``D``, without the walk; the common case
        (a fact found by ``D``'s own rule block, templates and its
        children's facts) costs one reason lookup and a few set hits.  A
        subject whose cone does not fit the budget gets no home (its cone
        is not kept): conservative, the walk decides.
        """
        home = self._home
        h = home.get(v)
        if h is not None:
            return h
        root_step = self.solver.root_step
        slots = self.table.slots
        cone_of = self._cone
        subject_of = self._subject
        steps: dict = {}
        stack = [(v, subject)]
        while stack:
            u, subj = stack[-1]
            if u in home:
                stack.pop()
                continue
            step = steps.get(u, _NO_STEP)
            if step is _NO_STEP:
                step = steps[u] = root_step(u)
                if step is not None:
                    todo = [a for a in step[1] if a not in home]
                    if todo:
                        stack.extend([(a, subject_of(a)) for a in todo])
                        continue
            h = _FOREIGN
            if step is not None:
                o, ants = step
                if type(o) is BlockOwner:
                    o = slots[o.base][0]        # a rule block: its node
                H = o if subj is None else subj
                cone = cone_of(H)
                if cone is not None and o in cone:
                    for a in ants:
                        if home[a] not in cone:
                            break
                    else:
                        h = H
            home[u] = h
            stack.pop()
        return home[v]

    def _walk(self, v: int, node) -> bool:
        """The exact provenance test for a fact about ``node`` whose home
        was not established: every owner of its reason DAG is in
        ``cone(node)``, which fits the budget (the caller checked).  On
        success ``node`` becomes its home."""
        prov = self.solver.provenance(v, self._prov_memo)
        if BOTTOM in prov:
            return False
        cone = self._cone(node)
        if cone is None:
            return False
        slots = self.table.slots
        for o in prov:
            if type(o) is BlockOwner:
                o = slots[o.base][0]
            if o not in cone:
                return False
        self._home[v] = node
        return True

    def _in_cone(self, node, o) -> bool:
        """``o`` is in ``cone(node)`` (``node`` included), and that cone
        fits the budget (:meth:`_cone`; otherwise False)."""
        cone = self._cone(node)
        return cone is not None and o in cone

    def _struct(self, o):
        """``(kids, weight)`` of a cone object ``o``, memoized in
        ``self.kids``.  ``kids``: the objects ``o``'s templates mention
        (compiled patterns and formulas, extension vocabulary facts; for a
        custom atom, its extension facts), parked and derived ones too: a
        function of ``o`` and the registry, read from the templates whether
        or not this session visited ``o``.  ``weight``: what ``o`` can cost
        a fresh session's discovery budget (see :meth:`_cone`): 1 for a
        node, 2 for a node with both compiled patterns and formulas (both
        can be parked, and escalation counts each), 0 for a custom atom
        (its extension facts are compiled when it is allocated, outside the
        budget).  None for a relation atom: its glue visits nodes with
        budgets of its own (``Relations``), so a cone holding one never
        fits."""
        kids = self.kids
        r = kids.get(o)
        if r is not None:
            return r
        engine = self.engine
        ext = engine._extensions
        if isinstance(o, P):
            # an object of a cone that is a P is a custom or relation atom
            # (_kid maps vocabulary atoms to their argument)
            if o.pred in RELATION_ATOMS:
                return None
            k = set()
            if ext is not None:
                for f in ext.facts_for(o):
                    k.update(_kid(a) for a in atoms_of(f))
                k.discard(o)
            r = kids[o] = (k, 0)
            return r
        constructing = engine._constructing
        mine = o not in constructing
        if mine:
            constructing.add(o)                 # as Session.node does
        try:
            if engine.clause_templates is not None:
                compiled, formulas = engine.clause_templates(o)
            else:
                compiled, formulas = (), engine.templates(o)
            if ext is not None and ext._vocab:
                formulas = list(formulas) + ext.node_facts(o)
        finally:
            if mine:
                constructing.discard(o)
        k = set()
        for comp in compiled:
            objs, pat = comp.objs, comp.pattern
            k.update(objs[i] for i in pat.used if i != pat.node)
        for f in formulas:
            k.update(_kid(a) for a in atoms_of(f))
        k.discard(o)
        r = kids[o] = (k, 2 if compiled and formulas else 1)
        return r

    def _cone(self, d):
        """The structural cone of ``d`` (``d`` and every object reachable
        through :meth:`_struct`'s kids) as a frozenset, if its *weight* (the
        sum of the objects' weights) is at most ``Engine.discovery_budget``;
        None otherwise (or if it holds a relation atom).  Memoized per
        session (:meth:`_sync_budget` drops it if the budget changes).

        Why the weight bounds a fresh ``Engine.is_(d, p)`` (and
        ``_is_custom`` for a custom atom ``d``): its discovery
        (:meth:`_discover`) visits nodes breadth-first from ``d`` through
        the children its templates schedule, each node once (a node enters
        the frontier when its variables are allocated, which happens once),
        so it visits only nodes of ``cone(d)``, at most one budget unit
        each; with no relation atom in the cone nothing else visits nodes.
        Its escalation (:meth:`escalate`, a budget of its own) counts one
        unit per node with parked clauses, one per node with parked
        formulas (nodes visited by discovery only; escalation visits with
        nothing parked) and one per node it visits: at most the weight.
        So if the weight is at most the budget, neither phase stops with
        work left: the session loads all of ``cone(d)`` before it searches,
        and is never budget-limited."""
        cones = self._cones
        if d in cones:
            return cones[d]
        budget = self._cone_budget
        struct = self._struct
        seen = {d}
        stack = [d]
        total = 0
        r = None
        while stack:
            o = stack.pop()
            st = struct(o)
            if st is None:
                break
            k, w = st
            total += w
            known = cones.get(o, _NO_STEP) if o is not d else _NO_STEP
            if known is None:
                break                           # a sub-cone that does not fit
            if known is not _NO_STEP:
                # a known (closed) sub-cone: count its objects, no expansion
                for x in known:
                    if x not in seen:
                        seen.add(x)
                        total += self.kids[x][1]
            else:
                for x in k:
                    if x not in seen:
                        seen.add(x)
                        stack.append(x)
            if total > budget:
                break
        else:
            r = frozenset(seen)
        cones[d] = r
        return r

    # -- queries -------------------------------------------------------------
    def query_literal(self, lit: int, assumptions: Iterable[int] = (),
                      search: bool = True) -> Optional[bool]:
        solver = self.solver
        if self.xfer is not None:
            self.xfer.sync_transfer()
        if not solver.propagate():
            raise InconsistentAssumptions("rule base or cached facts are inconsistent")
        self.writeback()
        # the query literal is read: its variable's rule-block implication
        # must be on the trail (Solver.mention)
        solver.mention((lit,))
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
        self.assumption_formula = f
        self._ensure_atoms(f)
        s = self.table.aux()

        def emit(clause):
            self._emit(clause + [-s])
        compile_formula(f, self.table, emit)
        self._flush()
        self._discover()
        if self.relations is not None:
            self._relations(f)
        else:
            self._affine_links(f, keep=True)
        self.n_assumption_nodes = len(self.base)
        self.n_assumption_constants = self.n_constants
        return [s]

    def literal_of(self, f) -> int:
        lit = self.literals.get(f)
        if lit is not None:
            return lit
        self._ensure_atoms(f)
        lit = formula_literal(f, self.table, self._emit)
        self._flush()
        self._discover()
        if self.relations is not None:
            self._relations(f)
        else:
            self._affine_links(f)
        self.literals[f] = lit
        return lit

    # -- relations (satassume.relations) ---------------------------------------
    def _relations(self, f) -> None:
        """Interpret the relation atoms ``f`` brought in, link and share;
        raises ``Uninterpreted`` if a relation of ``f`` has no theory.  Only
        called once the session has a relation atom (``self.relations``
        is created by :meth:`_custom`), so the unary path pays one test."""
        rel = self.relations
        atoms = atoms_of(f)
        rel.note_formula(atoms)
        if rel.active or rel.queue:
            rel.process(atoms)

    def _affine_links(self, f, keep: bool = False) -> None:
        """Start the relation machinery without a relation atom when two sign
        atoms, of the assumptions or of ``f``, are on different sums sharing
        a symbol (``Q.positive(x - 1)`` and ``Q.negative(1 - x)``): only the
        relation glue links a sign fact to its linear form
        (``extended_positive(e) <-> 0 < e``,
        :meth:`satassume.relations.Relations._link`), so without a relation
        atom LRA never compared the two sums.  Called while the session has
        no relations; the sums of the assumptions are kept (``keep``), a
        query's are not."""
        engine = self.engine
        if not engine._relation_specs:
            return
        atoms = atoms_of(f)
        new = [a.expr for a in atoms if a.pred in _SIGN_PREDS and getattr(a.expr, "is_Add", False)]
        if not new:
            return
        sums = self._sign_sums if keep else dict(self._sign_sums)
        hit = False
        for e in new:
            if e in sums:
                continue
            symbols = e.free_symbols
            if not symbols:
                continue
            hit = hit or any(symbols & other for other in sums.values())
            sums[e] = symbols
        if not hit:
            return
        rel = self.relations = Relations(self, engine._relation_specs)
        if self.assumption_formula is not None:
            rel.note_formula(atoms_of(self.assumption_formula))
        rel.note_formula(atoms)
        rel.active = True
        rel.process(atoms)

    def _ensure_atoms(self, f) -> None:
        """Visit the nodes of the vocabulary atoms of ``f``.  Custom atoms
        are allocated when ``f`` is compiled (see :meth:`_custom`)."""
        for atom in atoms_of(f):
            if atom.pred in PRED_INDEX:
                self.ensure(atom.expr, {atom.pred})


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


def _check_writeback(value: str) -> str:
    if value not in _WRITEBACK:
        raise ValueError(f"writeback must be one of {_WRITEBACK}, not {value!r}")
    return value


def _check_uninterpreted(value: str) -> str:
    if value not in ("none", "free"):
        raise ValueError(f"uninterpreted must be 'none' or 'free', not {value!r}")
    return value


class Engine:
    """See module docstring.

    Parameters
    ----------
    templates : callable(node) -> iterable of formulas, or None
        Structural clause generators.  Defaults to the SymPy template
        registry if importable, else no templates.
    cache : DictCache
        Where context-free facts live.  Defaults to a fresh ``DictCache``;
        SymPy's ``_assumptions`` are never used (see ``DictCache``).
    discovery_budget : int
        Maximum new nodes visited per query.
    session_limit : int
        A reused contextual session is replaced once it has visited this
        many nodes.
    cone_search : bool
        Search (CDCL) decides every variable of a session, so a query that
        needs search in a reused session holding nodes of earlier queries is
        searched in a fresh session over its own cone instead; the cost of
        search then depends on the query, not on what was asked before under
        the same assumptions.  Propagation-decided queries keep reusing the
        session.  The cone session then replaces the polluted one as the
        reused session of these assumptions, so one rebuild serves the
        following searches too.
    cone_threshold : int
        The cone search only pays when the reused session holds more than
        this many nodes beyond those of the assumptions: rebuilding a
        session (re-grounding the assumptions, their relations and theory
        atoms) costs about as much as searching a session a few nodes
        larger than the cone.  Measured on the refine query stream: a
        search in a session polluted by 1-3 nodes costs 0.9-1.1 ms, the
        cone search 1.3-1.7 ms; from about 8 extra nodes on, the reused
        search costs more (2.4 ms at 8-15, 3.7 ms at 16-31, 6.3 ms beyond),
        since CDCL decides every variable of the session.  Nodes that are
        closed irrational constants (``pi``, ``1/pi`` of ``x/pi``) do not
        count: their facts are context-free, nearly all fixed at the root.
        Counting them sent twice as many queries under assumption sets with
        ``pi`` to a cone rebuild, which cost about 10% of their time.
    keep_sessions : int
        How many contextual sessions (distinct assumption sets) to keep.
    extensions : satassume.extensions.Extensions or None
        Registered clause-generating functions for custom predicates and
        for vocabulary predicates on new classes.  Defaults to the global
        registry ``satassume.extensions.extensions``.
    relations : sequence of satassume.relations.AdapterSpec, or None
        Theory adapters for relation atoms.  None: the LRA and EUF adapters
        if present (with the SymPy templates only); ``[]``: relations are
        out of scope.  Kept as the tuple ``relation_specs``; assigning it
        (or ``extensions``) after construction drops the caches.
    transfer : bool
        Share unary facts between terms EUF puts in one class
        (:mod:`satassume.transfer`): ``Q.positive(y)`` from ``Q.eq(x, y) &
        Q.positive(x)``, ``Q.prime(x)`` from ``Q.eq(x, 2)``.  Engaged only in
        sessions with an equality atom.
    uninterpreted : ``"free"`` or ``"none"``
        What a relation of the query or the assumptions that no theory
        interprets (a Float or ``AccumBounds`` bound) does: ``"free"``
        (default) leaves it a free Boolean, so the rest of the assumptions
        still answers (and an inconsistent rest raises); this only drops
        what the relation says, which is sound.  ``"none"`` is the old
        behaviour, opt-in: ``ask`` returns None.
    relevance : bool
        ``sympy_api.ask`` answers a query under the assumption conjuncts
        connected to it only (see ``sympy_api._relevant``), once the whole
        set is known to be consistent; False: always under the whole set.
    writeback : ``"root-only"``, ``"provenance"`` or ``"all"``
        Which root facts of a session go to the context-free caches
        (``Session.writeback``, ``_put_root_only``): ``"root-only"``
        (default) only the answer and the queried node's facts of an
        ``is_`` session, with no bookkeeping; ``"provenance"`` (opt-in:
        a memo too, more cache reuse, at a measured cost) every fact
        derived from its own node's structural cone only; ``"all"`` every
        root literal (history-dependent; for measurement only).  A
        budget-truncated session writes nothing but under ``"all"``, and
        under the other two a fact is written only when a fresh ``is_`` of
        it is known to load all it needs (``Session._cone``).  A setting:
        assigning a different value drops this engine's caches
        (``_settings_changed``).
    """

    def __init__(self, templates=None, cache: Optional[DictCache] = None,
                 discovery_budget: int = 400,
                 session_limit: int = 2000, keep_sessions: int = 16,
                 cone_search: bool = True, extensions=None, relations=None,
                 cone_threshold: int = 3, transfer: bool = True,
                 uninterpreted: str = "free", relevance: bool = True,
                 writeback: str = "root-only"):
        clause_templates = None
        if templates is None:
            import importlib.util
            if importlib.util.find_spec("sympy") is None:  # pragma: no cover
                templates = lambda node: ()
            else:
                # a broken template package must not turn into silent Nones
                from .templates import registry
                templates = registry.facts_for
                clause_templates = registry.clauses_for
                registry.warm_up()
        if extensions is None:
            from .extensions import extensions
        if relations is None:
            from .relations import default_specs
            relations = default_specs() if clause_templates is not None else []
        self._relation_specs: tuple = tuple(relations)
        self._templates = templates
        #: ``node -> (compiled patterns, formulas)``; the fast path the SymPy
        #: template registry provides.  None: ``templates`` (formulas) only.
        self.clause_templates = clause_templates
        self._extensions = extensions
        #: context-free facts (``DictCache``); set at construction
        self.cache = cache if cache is not None else DictCache()
        self.custom_cache = DictCache()
        # the settings: properties whose setters drop this engine's caches
        # on a real change (``_settings_changed``); construction assigns
        # the fields and drops nothing
        self._discovery_budget = discovery_budget
        self._session_limit = session_limit
        self._keep_sessions = keep_sessions
        self._cone_search = cone_search
        self._cone_threshold = cone_threshold
        self._transfer = transfer
        self._uninterpreted = _check_uninterpreted(uninterpreted)
        self._writeback = _check_writeback(writeback)
        #: ``(proposition, assumptions) -> answer`` of the SymPy-level ``ask``
        #: (satassume.sympy_api), bounded; cleared when registrations change
        self.answers = AnswerMemo()
        self._relevance = relevance
        #: SymPy assumptions -> their split into components
        #: (``sympy_api._Split``), cleared together with ``answers``
        self.splits = AnswerMemo(20_000)
        self._context_sessions: "OrderedDict[Any, Tuple[Session, List[int]]]" = OrderedDict()
        self._constructing: set = set()
        #: assumption formulas whose session construction raised
        #: ``Uninterpreted`` -> its message (see :meth:`_context_session`)
        self._failed: Dict[Any, str] = {}
        #: assumption formula -> its verdict (``CONSISTENT``,
        #: ``INCONSISTENT`` or ``UNKNOWN``), from one complete check per set
        #: (see :meth:`_context_session`); bounded, cleared with the sessions
        self._verdict: Dict[Any, str] = {}
        #: the registry epoch (:mod:`satassume.epoch`) the engine-level
        #: caches were filled under; -1 until the first query
        self._epoch = -1
        self.stats = {"queries": 0, "cache_hits": 0, "escalations": 0,
                      "searches": 0, "cone_searches": 0, "sessions": 0,
                      "relevant": 0, "consistency_checks": 0, "theory_gave_up": 0,
                      "version_clears": 0, "dead_sessions": 0, "set_checks": 0,
                      "writeback_refused": 0, "writeback_budget": 0,
                      "budget_limited": 0}
        #: whether the last query's session ran out of discovery budget
        #: (its answer is sound but may be less definite than with a larger
        #: budget, and it wrote nothing back); False after a cache hit
        self.last_budget_limited = False

    def _fresh_session(self) -> Session:
        self.stats["sessions"] += 1
        return Session(self)

    # -- the registry epoch ---------------------------------------------------
    @property
    def extensions(self):
        """The registry of clause-generating functions
        (``satassume.extensions.Extensions``) or None.  Assigning another
        one starts a new registry epoch: every cache is dropped."""
        return self._extensions

    @extensions.setter
    def extensions(self, ext) -> None:
        if ext is not self._extensions:
            self._extensions = ext
            _bump()

    @property
    def relation_specs(self) -> tuple:
        """The theory adapters for relation atoms
        (``satassume.relations.AdapterSpec``), as a tuple; empty: relations
        are out of scope.  Assigning a different sequence starts a new
        registry epoch: every cache is dropped.  A tuple, so the adapters
        cannot change behind the epoch's back."""
        return self._relation_specs

    @relation_specs.setter
    def relation_specs(self, specs) -> None:
        specs = tuple(specs)
        if specs != self._relation_specs:
            self._relation_specs = specs
            _bump()

    @property
    def discovery_budget(self):
        """Setting: nodes one discovery or escalation step may add.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._discovery_budget

    @discovery_budget.setter
    def discovery_budget(self, value) -> None:
        if value != self._discovery_budget:
            self._discovery_budget = value
            self._settings_changed()

    @property
    def session_limit(self):
        """Setting: largest contextual session (in nodes) reused for a query.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._session_limit

    @session_limit.setter
    def session_limit(self, value) -> None:
        if value != self._session_limit:
            self._session_limit = value
            self._settings_changed()

    @property
    def keep_sessions(self):
        """Setting: how many contextual sessions are kept.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._keep_sessions

    @keep_sessions.setter
    def keep_sessions(self, value) -> None:
        if value != self._keep_sessions:
            self._keep_sessions = value
            self._settings_changed()

    @property
    def cone_search(self):
        """Setting: search the cone of a polluted contextual session.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._cone_search

    @cone_search.setter
    def cone_search(self, value) -> None:
        if value != self._cone_search:
            self._cone_search = value
            self._settings_changed()

    @property
    def cone_threshold(self):
        """Setting: constants beyond the assumptions' that pollute a session.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._cone_threshold

    @cone_threshold.setter
    def cone_threshold(self, value) -> None:
        if value != self._cone_threshold:
            self._cone_threshold = value
            self._settings_changed()

    @property
    def transfer(self):
        """Setting: engage predicate transfer (satassume.transfer).  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._transfer

    @transfer.setter
    def transfer(self, value) -> None:
        if value != self._transfer:
            self._transfer = value
            self._settings_changed()

    @property
    def uninterpreted(self) -> str:
        """Setting: ``"none"`` or ``"free"`` (relations no theory reads are
        free atoms).  Assigning a different value drops this engine's
        caches (``_settings_changed``)."""
        return self._uninterpreted

    @uninterpreted.setter
    def uninterpreted(self, value) -> None:
        value = _check_uninterpreted(value)
        if value != self._uninterpreted:
            self._uninterpreted = value
            self._settings_changed()

    @property
    def writeback(self) -> str:
        """Setting: the writeback policy, ``"root-only"``, ``"provenance"``
        or ``"all"`` (see the class docstring).  Assigning a different value
        drops this engine's caches (``_settings_changed``): facts written
        under ``"all"`` are not memos."""
        return self._writeback

    @writeback.setter
    def writeback(self, value) -> None:
        value = _check_writeback(value)
        if value != self._writeback:
            self._writeback = value
            self._settings_changed()

    @property
    def relevance(self):
        """Setting: drop assumption components irrelevant to the proposition.  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._relevance

    @relevance.setter
    def relevance(self, value) -> None:
        if value != self._relevance:
            self._relevance = value
            self._settings_changed()

    @property
    def templates(self):
        """Setting: ``node -> formulas``, the structural templates.
        Assigning another function drops this engine's caches
        (``_settings_changed``) and, as for ``Engine(templates=...)``, turns
        off the compiled fast path (``clause_templates``)."""
        return self._templates

    @templates.setter
    def templates(self, value) -> None:
        if value is not self._templates:
            self._templates = value
            self.clause_templates = None
            self._settings_changed()

    def _settings_changed(self) -> None:
        """A setting of this engine changed (the setters call this on a real
        change only): drop what this engine computed under the old value.
        Settings are not part of the registry epoch, so other engines keep
        their caches.  Before the first query (``_epoch == -1``) there is
        nothing to drop.  Otherwise this drops what :meth:`_check_version`
        drops for the engine (the contextual sessions, the answer and split
        memos, the ``Uninterpreted`` memo, the verdict memo), counted in
        ``stats["version_clears"]``, and the stores of the engine's fact
        caches (``cache``, ``custom_cache``): their facts can depend on
        ``templates``, ``discovery_budget`` (truncated sessions),
        ``transfer``, ``uninterpreted`` and ``writeback``, as can a set's
        verdict.  A ``DictCache`` shared with other engines is cleared for
        them too: a needless clear for them, never a stale answer.
        :data:`satassume.epoch.EPOCH` is untouched."""
        if self._epoch >= 0:
            self.stats["version_clears"] += 1
            self._context_sessions.clear()
            self.answers.clear()
            self.splits.clear()
            self._failed.clear()
            self._verdict.clear()
            self.cache.store.clear()
            self.custom_cache.store.clear()

    def _check_version(self) -> None:
        """Drop every engine-level cache filled under an earlier registry
        epoch (:mod:`satassume.epoch`): the fact caches, the contextual
        sessions, the answer and split memos, the ``Uninterpreted`` memo
        and the verdict memo all hold results computed under the registrations in force at the
        time.  The entry of every query calls this when the engine's epoch
        is not the current one (``if self._epoch != _EPOCH[0]``); a
        ``DictCache`` records its own epoch, so a cache shared between
        engines, or given to an engine created after a registration, is
        dropped by the first engine that looks.  Nothing is counted before
        the engine's first query, so registering before using an engine
        costs nothing."""
        epoch = _EPOCH[0]
        if self._epoch != epoch:
            if self._epoch >= 0:
                self.stats["version_clears"] += 1
                self._context_sessions.clear()
                self.answers.clear()
                self.splits.clear()
                self._failed.clear()
                self._verdict.clear()
            self._epoch = epoch
        for cache in (self.cache, self.custom_cache):
            if cache._epoch != epoch:
                cache.store.clear()
                cache._epoch = epoch

    def _context_session(self, assumptions) -> Tuple[Session, List[int]]:
        if self._epoch != _EPOCH[0]:
            self._check_version()
        hit = self._context_sessions.get(assumptions)
        if hit is not None and not hit[0].solver.propagate():
            # dead: a query's own nodes made the clause set unsatisfiable at
            # root, and the query left some other way than by raising
            # InconsistentAssumptions (an Uninterpreted relation, an error)
            del self._context_sessions[assumptions]
            self.stats["dead_sessions"] += 1
            hit = None
        if hit is not None and _gave_up(hit[0]):
            # a theory stopped answering in an earlier query (see
            # satassume.theory, "Giving up"): start over with a working one
            del self._context_sessions[assumptions]
            self.stats["theory_gave_up"] += 1
            hit = None
        if hit is not None and len(hit[0].base) <= self.session_limit:
            self._context_sessions.move_to_end(assumptions)
            return hit
        failed = self._failed
        msg = failed.get(assumptions)
        if msg is not None:
            # the construction below would raise this again: whether it
            # does depends only on the assumptions' relation atoms and the
            # registry epoch, which _check_version has just compared
            raise Uninterpreted(msg)
        if self._verdict.get(assumptions) is INCONSISTENT:
            # the construction below would raise this again (it is the same
            # every time, see _build_context); the memo only saves the work
            raise InconsistentAssumptions("inconsistent assumptions")
        try:
            s, lits = self._build_context(assumptions)
        except Uninterpreted as e:
            if len(failed) >= 10_000:
                failed.clear()
            failed[assumptions] = str(e)
            raise
        v = s.verdict
        if len(self._verdict) >= 20_000:
            self._verdict.clear()
        self._verdict[assumptions] = v
        if v is INCONSISTENT:
            raise InconsistentAssumptions("inconsistent assumptions")
        self._context_sessions[assumptions] = (s, lits)
        while len(self._context_sessions) > self.keep_sessions:
            self._context_sessions.popitem(last=False)
        return s, lits

    def _build_context(self, assumptions) -> Tuple[Session, List[int]]:
        """Build the contextual session of ``assumptions`` and run the set's
        complete check (:meth:`_complete_check`) in it; its verdict is
        ``s.verdict``.  Every construction of a set's session, the first
        or a rebuild (eviction, ``session_limit``, a dead session, a theory
        that gave up), takes exactly these steps, whether a verdict is
        memoized or not, so the session the queries use never depends on
        what ran before.  What the check leaves in the session (the
        escalated cone, learnt clauses) is a function of the set alone.

        If the check makes a theory give up (or errors), the session is
        replaced by a plain one (assumptions only, no check): a session
        whose theory gave up is useless to the queries (satassume.theory,
        "Giving up"), and the plain build is just as deterministic."""
        self.stats["set_checks"] += 1
        s = self._fresh_session()
        lits = s.assume_formula(assumptions)
        try:
            v = self._complete_check(s, lits)
        except Uninterpreted:
            raise
        except Exception:
            # the check could not conclude (an error in a theory, an
            # undecidable constant): not evidence either way, and the
            # session is in an unknown state
            v = None
        if v is INCONSISTENT:
            s.verdict = v
            return s, lits
        if v is None or _gave_up(s):
            s = self._fresh_session()
            lits = s.assume_formula(assumptions)
            v = UNKNOWN
        s.verdict = v
        return s, lits

    def verdict(self, assumptions) -> str:
        """The verdict of the assumption set ``assumptions`` (a formula):
        ``CONSISTENT``, ``INCONSISTENT`` or ``UNKNOWN``, from the complete
        check (:meth:`_complete_check`) run when its contextual session is
        built.  Builds that session if it has none (the set's queries use
        it); raises ``Uninterpreted`` as that construction does, never
        ``InconsistentAssumptions``."""
        try:
            s, _ = self._context_session(assumptions)
        except InconsistentAssumptions:
            return INCONSISTENT
        return s.verdict

    @staticmethod
    def _complete_check(s: Session, lits: List[int]) -> str:
        """Whether the assumptions ``lits`` of the just-built session ``s``
        are consistent with the facts: the whole cone of the assumptions
        (derived nodes and parked clauses included), propagation, then
        search.  ``INCONSISTENT`` only on a conflict, which is sound even
        if a theory gave up afterwards (its earlier conflicts were valid,
        satassume.theory); ``UNKNOWN`` if no conflict was found but a
        theory gave up or the cone is truncated by the discovery budget
        (then a model of the clauses is no model of the set);
        ``CONSISTENT`` otherwise."""
        solver = s.solver
        if s.xfer is not None:
            s.xfer.sync_transfer()
        if not solver.propagate() or solver.implied(lits) is None:
            return INCONSISTENT
        if s.incomplete:
            s.escalate()
            if s.xfer is not None:
                s.xfer.sync_transfer()
            if not solver.propagate() or solver.implied(lits) is None:
                return INCONSISTENT
        # Solver.solve returns a bool: it raises only on a malformed
        # literal or a theory protocol error (RuntimeError), neither of
        # which is a conflict; the caller maps them to UNKNOWN
        if not solver.solve(lits):
            return INCONSISTENT
        if _gave_up(s) or s.incomplete or s.truncated:
            return UNKNOWN
        return CONSISTENT

    # -- context-free ---------------------------------------------------------
    def is_(self, node: Node, pred: str) -> Optional[bool]:
        """Context-free truth value of ``pred(node)``; cached on the node
        (custom predicates: in the engine's own cache)."""
        if self._epoch != _EPOCH[0]:
            self._check_version()
        if pred not in PRED_INDEX:
            return self._is_custom(node, pred)
        facts = self.cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            self.last_budget_limited = False
            return facts[pred]
        if node in self._constructing:
            # re-entrant query from a template evaluating this very node
            return None
        self.stats["queries"] += 1
        s = self._fresh_session()
        s.ensure(node, {pred})
        lit = s.base[node] + PRED_INDEX[pred]
        r = s.query_literal(lit, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(lit, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, search=True)
        self._put_result(s, self.cache, node, node, pred, r)
        return r

    def _put_result(self, s: Session, cache: DictCache, subject, node, pred: str, r) -> None:
        """Cache the answer ``r`` of the context-free query ``pred(node)``
        (``subject``: ``node``, or the custom atom), unless a fresh engine's
        same query could answer otherwise (``"all"`` caches it anyway).
        A session that ran out of discovery budget caches nothing: ``r`` is
        a function of the budget's cut, not of the node alone.  Otherwise
        ``"root-only"``: :meth:`_put_root_only`.  ``"provenance"``: ``r``
        is not cached if it was decided before escalation with work still
        parked or deferred (``s.incomplete``) and ``cone(subject)`` does not
        fit the budget (``Session._cone``).  The fresh query discovers the
        same nodes and parks the same clauses (both depend on the node and
        the predicate only, not on cached values), but without this
        engine's cached facts it may have to escalate, and that escalation
        could run out of budget.  Otherwise the fresh query either escalates
        exactly as this one did (no truncation) or does not need to, and
        answers ``r``: the same clauses up to cached facts, which are memos
        entailed by them, and a complete search.  A session that engaged
        relation glue (only through extension facts naming relation atoms)
        is cached only through the cone rule, which refuses cones with
        relation atoms."""
        self.last_budget_limited = s.truncated
        policy = self._writeback
        if s.truncated:
            self.stats["budget_limited"] += 1
            if policy != "all":
                return
        elif policy == "root-only":
            self._put_root_only(s, cache, subject, node, pred, r)
            return
        elif policy == "provenance" and (s.incomplete or s.relations is not None):
            s._sync_budget()
            if s._cone(subject) is None:
                self.stats["writeback_budget"] += 1
                return
        cache.put(node, pred, r)

    def _put_root_only(self, s: Session, cache: DictCache, subject, node, pred: str, r) -> None:
        """``writeback="root-only"``: cache the answer ``r`` of the
        non-truncated session ``s`` of ``Engine.is_(node, pred)`` and the
        session's other root facts about ``node`` (a vocabulary query), each
        only when a fresh engine's ``is_`` of it answers the same.  Every
        value written is, besides, entailed by the clauses of the node's
        structural cone (cached facts asserted in ``s`` are such values,
        by induction).  Let ``V`` be the nodes ``s`` visited.

        * ``s`` is *complete* (nothing parked or deferred, no relation
          glue): it compiled every template of every node of ``V`` (and the
          extension facts of every custom atom they mention), so ``V`` holds
          every node any compilation from ``node`` allocates: ``V`` is
          ``node``'s cone.  A fresh ``is_(node, pred)`` discovers and parks
          as ``s`` did (cached values decide neither), so it escalates
          exactly when ``s`` did (it propagates less), without truncation,
          and answers ``r`` (``s``'s clauses minus cached facts entailed by
          them, a complete search).  So ``r`` is written.  A fresh
          ``is_(node, q)`` of another predicate visits only nodes of ``V``,
          each once in discovery (at most ``|V|`` units of budget) and, in
          escalation, spends one unit per node with parked clauses, one per
          node with parked formulas and one per node it visits (at most
          ``2|V|``): if ``2|V| <= discovery_budget`` it is never truncated,
          so it loads every clause of ``V`` before it searches and answers
          the value ``s`` derived.  Otherwise the exact test
          ``Session._cone`` decides.
        * ``s`` is incomplete: it was decided by propagation before
          escalation.  If it asserted no cached fact, it *is* the fresh
          session (nothing else of the engine enters a session), so ``r``
          is written; the other facts need ``Session._cone``.  If it
          asserted cached facts, a fresh session may need an escalation
          that runs out of budget: everything needs ``Session._cone``.

        Cone tests run only when there is something to write that the
        cheap tests do not settle; refusals count in ``writeback_budget``.
        No provenance bookkeeping, no walk: the queried node's facts of a
        session in which only its cone took part."""
        complete = s.relations is None and not s.incomplete
        if complete or (s.relations is None and not s.used_cache):
            cache.put(node, pred, r)
            todo = None
        else:
            todo = [(pred, r)]
        if subject is node:
            facts = cache.facts(node)
            for p, v in s.solver.root_values(s.base[node], NPRED):
                p = PREDICATES[p]
                if p != pred and (facts is None or p not in facts):
                    if todo is None:
                        todo = []
                    todo.append((p, v))
        if not todo:
            return
        if not (complete and 2 * len(s.base) <= self._discovery_budget):
            s._sync_budget()
            if s._cone(subject) is None:
                self.stats["writeback_budget"] += 1
                return
        for p, v in todo:
            cache.put(node, p, v)

    def _is_custom(self, node: Node, pred: str) -> Optional[bool]:
        if self._epoch != _EPOCH[0]:
            self._check_version()
        facts = self.custom_cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            self.last_budget_limited = False
            return facts[pred]
        self.stats["queries"] += 1
        s = self._fresh_session()
        atom = P(pred, node)
        lit = s.literal_of(atom)
        r = s.query_literal(lit, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(lit, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, search=True)
        self._put_result(s, self.custom_cache, atom, node, pred, r)
        return r

    # -- contextual -----------------------------------------------------------
    def ask(self, proposition, assumptions=None) -> Optional[bool]:
        """Truth value of ``proposition`` (a formula over ``P`` atoms) given
        ``assumptions`` (a formula or None).  Raises
        ``InconsistentAssumptions`` if the assumptions contradict the facts.
        """
        if self._epoch != _EPOCH[0]:
            self._check_version()
        self.stats["queries"] += 1
        lits: List[int] = []
        contextual = assumptions is not None and assumptions is not True
        if contextual:
            s, lits = self._context_session(assumptions)
        else:
            s = self._fresh_session()
        try:
            return self._ask(s, lits, proposition, assumptions, contextual)
        except InconsistentAssumptions:
            if contextual:
                self._drop_dead(assumptions)
            raise

    def _drop_dead(self, assumptions) -> None:
        """A query raised under a reused session.  Whether the raise
        belongs to this query alone (its own nodes made the clause set
        unsatisfiable, at root or only under the assumptions: a non-total
        template block, an extension emitting contradictory facts) or to
        the assumptions (they contradict the facts), the session must not
        answer later queries under these assumptions: it is dropped, and
        the next query builds a fresh one, as a fresh engine would.  An
        inconsistent assumption set therefore raises for every query, from
        a fresh session each time."""
        if self._context_sessions.pop(assumptions, None) is not None:
            self.stats["dead_sessions"] += 1

    def _ask(self, s: Session, lits: List[int], proposition, assumptions,
             contextual: bool) -> Optional[bool]:
        polluted = (len(s.base) - s.n_assumption_nodes
                    - (s.n_constants - s.n_assumption_constants)) > self.cone_threshold
        q = self._literal(s, proposition)
        r = s.query_literal(q, lits, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(q, lits, search=False)
        if r is None:
            self.stats["searches"] += 1
            if contextual and polluted and self.cone_search:
                self.stats["cone_searches"] += 1
                s0 = s
                s = self._fresh_session()
                lits = s.assume_formula(assumptions)
                q = self._literal(s, proposition)
                s.escalate()
                r = s.query_literal(q, lits, search=True)
                # the cone session (assumptions + this query's cone, and
                # what the search learned) replaces the polluted one, so the
                # next searches under these assumptions start small again
                if self._context_sessions.get(assumptions, (None,))[0] is s0:
                    # the verdict is a function of the set alone: carry it
                    # over rather than run the check again (every context
                    # session is built by _build_context, so s0 has one)
                    s.verdict = (s0.verdict if s0.verdict is not None
                                 else self._verdict.get(assumptions))
                    self._context_sessions[assumptions] = (s, lits)
                    if r is not None:
                        # "under these assumptions, q" is entailed by the
                        # clause set (the selector guards the assumptions),
                        # so a repeat is answered by propagation
                        s._emit([-lits[0], q if r else -q])
                self._note_budget(s)
                return r
            r = s.query_literal(q, lits, search=True)
        self._note_budget(s)
        return r

    def _note_budget(self, s: Session) -> None:
        self.last_budget_limited = s.truncated
        if s.truncated:
            self.stats["budget_limited"] += 1

    @staticmethod
    def _literal(s: Session, proposition) -> int:
        if isinstance(proposition, P) and proposition.pred in PRED_INDEX:
            s.ensure(proposition.expr, {proposition.pred})
            if s.relations is not None:
                s._relations(proposition)
            else:
                s._affine_links(proposition)
            return s.base[proposition.expr] + PRED_INDEX[proposition.pred]
        return s.literal_of(proposition)


#: the predicates whose atoms the relation glue links to order atoms
#: (``extended_positive``, ``extended_negative``, ``zero``) and those that imply
#: or refute them for a finite argument
_SIGN_PREDS = frozenset({
    "positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero",
    "extended_positive", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero"})


# --------------------------------------------------------------------------
# rule-base neighbourhood used by demand-driven instantiation
# --------------------------------------------------------------------------

_NEIGH: Dict[int, frozenset] = {}
_WANT: Dict[frozenset, frozenset] = {}


def _gave_up(s: Session) -> bool:
    """A theory of the session's solver gave up (satassume.theory)."""
    for t in s.solver._theories:
        if getattr(t, "gave_up", False):
            return True
    return False


def neighbourhood(pred) -> frozenset:
    """``pred`` (a name or index) plus every predicate sharing a rule
    clause with it, as indices."""
    i = PRED_INDEX[pred] if isinstance(pred, str) else pred
    n = _NEIGH.get(i)
    if n is None:
        acc = {i}
        for c in RULE_CLAUSES:
            idx = [abs(l) - 1 for l in c]
            if i in idx:
                acc.update(idx)
        n = _NEIGH[i] = frozenset(acc)
    return n


_SPLIT: dict = {}


def _split(clauses, want):
    """``(clauses, now, later, ment)``: the pattern clauses about a
    predicate of ``want`` (all of them if ``want`` is None), the rest (None
    if empty) and the mention masks of ``now`` per slot, ``((k, mask),
    ...)`` with bits ``off`` and ``off ^ 1`` for each literal offset (see
    ``Solver.mention_blocks``).  Memoized per clause list and ``want``:
    the lists are the patterns' own or earlier results, kept alive here."""
    key = (id(clauses), want)
    r = _SPLIT.get(key)
    if r is not None and r[0] is clauses:
        return r
    if want is None:
        now, later = clauses, None
    else:
        now = [c for c in clauses if c[1] & want]
        later = [c for c in clauses if not (c[1] & want)] or None
        if later is None:
            now = clauses
    acc: dict = {}
    for _, _, li in now:
        for k, off in li:
            acc[k] = acc.get(k, 0) | (3 << (off & ~1))
    r = (clauses, now, later, tuple(acc.items()))
    if len(_SPLIT) >= 100_000:
        _SPLIT.clear()
    _SPLIT[key] = r
    return r


def want_of(demanded) -> frozenset:
    """Union of the neighbourhoods of the demanded predicate indices."""
    key = frozenset(demanded)
    w = _WANT.get(key)
    if w is None:
        acc = set()
        for i in key:
            acc.update(neighbourhood(i))
        w = _WANT[key] = frozenset(acc)
    return w

