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
"""
from __future__ import annotations

from collections import OrderedDict, deque
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .compile import VarTable, compile_formula, formula_literal
from .formula import P, atoms_of
from .relations import RELATION_ATOMS, Relations, Uninterpreted
from .rules import NPRED, PRED_INDEX, PREDICATES, RULE_CLAUSES, RULE_INTERNAL
from .solver import Solver

Node = Any


class InconsistentAssumptions(ValueError):
    pass


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
    """Answers of whole queries, bounded in size (cleared when full).
    ``state`` is the registration state the answers were computed under."""

    def __init__(self, maxsize: int = 100_000):
        super().__init__()
        self.maxsize = maxsize
        self.state = None

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
        self.n_assumption_constants = 0
        self.literals: Dict[Any, int] = {}    # compound formula -> Tseitin literal
        self.assumption_formula = None       # the formula of assume_formula()
        #: relation atoms and their theories (satassume.relations); created
        #: at the first user formula when the engine has relation support
        self.relations: Optional[Relations] = None
        #: the Relations object once predicate transfer is engaged
        #: (Relations._engage_transfer); None on every other path
        self.xfer = None

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
        engine = self.engine
        # 1. structural templates, and vocabulary predicates registered for
        #    the node's class (satassume.extensions)
        if engine.clause_templates is not None:
            compiled, formulas = engine.clause_templates(node)
        else:
            compiled, formulas = (), engine.templates(node)
        ext = engine.extensions
        if ext is not None and ext._vocab:
            formulas = list(formulas) + ext.node_facts(node)
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
            self._add_clauses([[b + PRED_INDEX[p]] if v else [-(b + PRED_INDEX[p])]
                               for p, v in facts.items() if v is not None and p in PRED_INDEX])
        if compiled:
            self._compile_patterns(node, compiled, demanded)
        if formulas:
            items = [(f, atoms_of(f)) for f in formulas]
            if demanded is None:
                self._compile(node, items)
            else:
                self.pending[node] = items
                self._compile_pending(node, demanded)
        constructing.discard(node)
        return b

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
        if v is not None:
            self._emit([var if v else -var])
        if atom.pred in RELATION_ATOMS and engine.relation_specs:
            rel = self.relations
            if rel is None:
                rel = self.relations = Relations(self, engine.relation_specs)
                if self.assumption_formula is not None:
                    # unary atoms of the assumptions become link candidates
                    rel.note_formula(atoms_of(self.assumption_formula))
            rel.enqueue(atom)
            return
        ext = engine.extensions
        if ext is None:
            return
        for f in ext.facts_for(atom):
            compile_formula(f, self.table, self._emit)

    def _compile_pending(self, node: Node, demanded) -> None:
        """Compile the parked formulas and clauses of ``node`` that mention
        a predicate in the neighbourhood of ``demanded`` (indices)."""
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
        nodes its templates mention, up to ``budget`` new nodes."""
        if demanded is not None:
            self.demand.setdefault(node, set()).update(PRED_INDEX[p] for p in demanded)
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
        while (self.pending or self.pending_c or self.deferred or self.frontier) \
                and added < budget:
            if self.pending_c:
                node, pend = self.pending_c.popitem()
                for clauses, bases in pend:
                    self._emit_pattern(clauses, bases)
                added += 1
            elif self.pending:
                node, formulas = self.pending.popitem()
                self._compile(node, formulas)
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
        self.frontier = deque()

    # -- root facts -> cache ------------------------------------------------
    def writeback(self) -> None:
        trail = self.solver.root_trail()
        slots = self.table.slots
        cache = self.engine.cache
        custom = self.engine.custom_cache
        for lit in trail[self.read_pos:]:
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
        self.read_pos = len(trail)

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

    def _ensure_atoms(self, f) -> None:
        """Visit the nodes of the vocabulary atoms of ``f``.  Custom atoms
        are allocated when ``f`` is compiled (see :meth:`_custom`)."""
        for atom in atoms_of(f):
            if atom.pred in PRED_INDEX:
                self.ensure(atom.expr, {atom.pred})


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
    relations : list of satassume.relations.AdapterSpec, or None
        Theory adapters for relation atoms.  None: the LRA and EUF adapters
        if present (with the SymPy templates only); ``[]``: relations are
        out of scope.
    transfer : bool
        Share unary facts between terms EUF puts in one class
        (:mod:`satassume.transfer`): ``Q.positive(y)`` from ``Q.eq(x, y) &
        Q.positive(x)``, ``Q.prime(x)`` from ``Q.eq(x, 2)``.  Engaged only in
        sessions with an equality atom.
    uninterpreted : ``"none"`` or ``"free"``
        What a relation of the query or the assumptions that no theory
        interprets does: ``"none"`` (default) makes ``ask`` return None;
        ``"free"`` leaves it a free Boolean, so the rest of the assumptions
        still answers (and an inconsistent rest raises).
    relevance : bool
        ``sympy_api.ask`` answers a query under the assumption conjuncts
        connected to it only (see ``sympy_api._relevant``), once the whole
        set is known to be consistent; False: always under the whole set.
    """

    def __init__(self, templates=None, cache: Optional[DictCache] = None,
                 discovery_budget: int = 400,
                 session_limit: int = 2000, keep_sessions: int = 16,
                 cone_search: bool = True, extensions=None, relations=None,
                 cone_threshold: int = 3, transfer: bool = True,
                 uninterpreted: str = "none", relevance: bool = True):
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
        #: adapter specs for relation atoms (satassume.relations); empty:
        #: relations are out of scope, as before
        self.relation_specs = list(relations)
        self.templates = templates
        #: ``node -> (compiled patterns, formulas)``; the fast path the SymPy
        #: template registry provides.  None: ``templates`` (formulas) only.
        self.clause_templates = clause_templates
        self.extensions = extensions
        self.cache = cache if cache is not None else DictCache()
        self.custom_cache = DictCache()
        self.discovery_budget = discovery_budget
        self.session_limit = session_limit
        self.keep_sessions = keep_sessions
        self.cone_search = cone_search
        self.cone_threshold = cone_threshold
        self.transfer = transfer
        if uninterpreted not in ("none", "free"):
            raise ValueError(f"uninterpreted must be 'none' or 'free', not {uninterpreted!r}")
        self.uninterpreted = uninterpreted
        #: ``(proposition, assumptions) -> answer`` of the SymPy-level ``ask``
        #: (satassume.sympy_api), bounded; cleared when registrations change
        self.answers = AnswerMemo()
        self.relevance = relevance
        #: SymPy assumptions -> their split into components
        #: (``sympy_api._Split``), cleared together with ``answers``
        self.splits = AnswerMemo(20_000)
        self._context_sessions: "OrderedDict[Any, Tuple[Session, List[int]]]" = OrderedDict()
        self._constructing: set = set()
        #: assumption formulas whose session construction raised
        #: ``Uninterpreted`` -> its message, valid under ``_failed_state``
        #: (see :meth:`_context_session`)
        self._failed: Dict[Any, str] = {}
        self._failed_state = None
        self.stats = {"queries": 0, "cache_hits": 0, "escalations": 0,
                      "searches": 0, "cone_searches": 0, "sessions": 0,
                      "relevant": 0, "consistency_checks": 0}

    def _fresh_session(self) -> Session:
        self.stats["sessions"] += 1
        return Session(self)

    def _registry_state(self):
        """What decides whether building a session for a set of assumptions
        raises ``Uninterpreted``: the theory adapters (and, conservatively,
        the registered clause-generating functions)."""
        ext = self.extensions
        return (ext, ext.version if ext is not None else 0, tuple(self.relation_specs))

    def _context_session(self, assumptions) -> Tuple[Session, List[int]]:
        hit = self._context_sessions.get(assumptions)
        if hit is not None and len(hit[0].base) <= self.session_limit:
            self._context_sessions.move_to_end(assumptions)
            return hit
        failed = self._failed
        if failed:
            msg = failed.get(assumptions)
            if msg is not None:
                if self._failed_state == self._registry_state():
                    # the construction below would raise this again: whether
                    # it does depends only on the assumptions' relation atoms
                    # and the adapters (Relations.process)
                    raise Uninterpreted(msg)
                failed.clear()
        s = self._fresh_session()
        try:
            lits = s.assume_formula(assumptions)
        except Uninterpreted as e:
            state = self._registry_state()
            if self._failed_state != state or len(failed) >= 10_000:
                failed.clear()
                self._failed_state = state
            failed[assumptions] = str(e)
            raise
        self._context_sessions[assumptions] = (s, lits)
        while len(self._context_sessions) > self.keep_sessions:
            self._context_sessions.popitem(last=False)
        return s, lits

    # -- context-free ---------------------------------------------------------
    def is_(self, node: Node, pred: str) -> Optional[bool]:
        """Context-free truth value of ``pred(node)``; cached on the node
        (custom predicates: in the engine's own cache)."""
        if pred not in PRED_INDEX:
            return self._is_custom(node, pred)
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
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(lit, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, search=True)
        self.cache.put(node, pred, r)
        return r

    def _is_custom(self, node: Node, pred: str) -> Optional[bool]:
        facts = self.custom_cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            return facts[pred]
        self.stats["queries"] += 1
        s = self._fresh_session()
        lit = s.literal_of(P(pred, node))
        r = s.query_literal(lit, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            r = s.query_literal(lit, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, search=True)
        self.custom_cache.put(node, pred, r)
        return r

    # -- contextual -----------------------------------------------------------
    def ask(self, proposition, assumptions=None) -> Optional[bool]:
        """Truth value of ``proposition`` (a formula over ``P`` atoms) given
        ``assumptions`` (a formula or None).  Raises
        ``InconsistentAssumptions`` if the assumptions contradict the facts.
        """
        self.stats["queries"] += 1
        lits: List[int] = []
        contextual = assumptions is not None and assumptions is not True
        if contextual:
            s, lits = self._context_session(assumptions)
        else:
            s = self._fresh_session()
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
                    self._context_sessions[assumptions] = (s, lits)
                    if r is not None:
                        # "under these assumptions, q" is entailed by the
                        # clause set (the selector guards the assumptions),
                        # so a repeat is answered by propagation
                        s._emit([-lits[0], q if r else -q])
                return r
            r = s.query_literal(q, lits, search=True)
        return r

    @staticmethod
    def _literal(s: Session, proposition) -> int:
        if isinstance(proposition, P) and proposition.pred in PRED_INDEX:
            s.ensure(proposition.expr, {proposition.pred})
            if s.relations is not None:
                s._relations(proposition)
            return s.base[proposition.expr] + PRED_INDEX[proposition.pred]
        return s.literal_of(proposition)


# --------------------------------------------------------------------------
# rule-base neighbourhood used by demand-driven instantiation
# --------------------------------------------------------------------------

_NEIGH: Dict[int, frozenset] = {}
_WANT: Dict[frozenset, frozenset] = {}


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

