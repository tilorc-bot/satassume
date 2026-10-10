"""The assumptions engine.

One ``Engine`` answers two kinds of question with one propositional core:

* **contextual** queries, ``engine.ask(formula, assumptions)``, behind
  ``ask(Q.positive(expr), assumptions)`` (see :mod:`satassume.sympy_api`
  for the scope).  Assumptions enter the solver as solver assumptions
  (MiniSat style) under a selector literal, never as permanent clauses, so
  nothing derived under them leaks into the cache.
* **context-free** queries, ``engine.is_(expr, 'positive')``, used for
  ``ask`` without assumptions and by the corpus tools.  ``is_`` memoizes
  its own answer per expression node and registry epoch (True or False,
  never None), so repeated queries cost a dictionary lookup, the way the
  old ``expr.is_positive`` works; replacing that old system with this
  path is the long-term goal, not the current scope.

Both go through a ``Session``: an incremental solver plus a table mapping
``(predicate, node)`` atoms to variables.  Visiting a node instantiates the
single-node rule base for it, asserts the structural templates registered
for its class, and schedules the child nodes those templates mention.
Nothing cached enters a session (no cached fact is asserted as a unit
clause), so the clause set a query runs over is a function of the query,
the registry and the settings alone.  Search (CDCL) only runs when
root-level propagation is inconclusive.

Every query gets a session of its own.  A context-free query's discovery
only visits the cone of the queried expression, so search cost is bounded
by the size of that expression and never by what was asked before.  A
contextual query builds the session of its assumption set
(``Engine._build_context``: the set's clauses and one complete
consistency check of the set), answers in it, and discards it.  What the
engine keeps of a set between queries is a function of the set alone:
its verdict (``CONSISTENT``, ``INCONSISTENT`` or ``UNKNOWN``, from the
check) and, for a set whose construction raised ``Uninterpreted``, the
message.  So the solver state a query runs in, the search path it takes
and the budget it has (integer branch and bound, :mod:`satassume.theories.lra.lra`,
"Integrality"; giving up on a constant, :mod:`satassume.sat.theory`) are
those a fresh engine's same query has, whatever was asked before under
the same or any other set: history independence by construction (see
``docs/design.md``, "History independence").  The settings
``keep_sessions``, ``session_limit``, ``cone_search`` and
``cone_threshold`` of the earlier design (one reused session per set,
replaced by a cone search when polluted) selected no code path after
issue #97 P1 and were removed in P7; the per-query build costs about 1.3x
on the refine stream (issue #97).

Everything the engine keeps between queries (the fact caches, the verdict
and ``Uninterpreted`` memos, the answer and split memos) is a function of
the registry state: the registered clause-generating functions
(``satassume.knowledge.extensions``), the structural templates and the theory
adapters.  Every change of that state starts a new registry epoch
(:mod:`satassume.state.epoch`); every query compares the epoch its caches were
filled under with the current one (``Engine._check_version``) and drops
them all on a change, so an answer never depends on what was registered
when an earlier query ran.

The relation glue of a session (links, the clauses of relation atoms to
unary atoms, predicate transfer) sits behind selectors; the set's glue is
asserted at the root and a query assumes only the selectors its own
proposition adds (``Session.assumption_lits``; :mod:`satassume.relations`,
"Switched glue").  The selectors of the assumptions form a stable prefix
whose solver levels the set's check leaves in place for the query
(``Solver.implied(..., hold=k)``; ``Engine._ask`` releases the levels
above it before the query adds clauses).

The fact caches (``cache``, ``custom_cache``) are pure memos of ``is_``:
``Engine.is_(node, pred)`` (and ``_is_custom``) stores its own answer,
True or False, never None, under the registry epoch it was derived in
(``_put_result``); nothing else writes to them and no session reads them.
``writeback`` stays as the name of the setting: ``"root-only"`` (the
default) memoizes, ``"none"`` does not.  The ``"provenance"`` and
``"all"`` policies of #53 stage 3 (``Session.writeback``: root facts of
whole sessions, with owner tracking and a provenance test per fact) were
removed by issue #97 (P2).
"""
from __future__ import annotations

from collections import OrderedDict, deque
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .knowledge.compile import VarTable, basis_formula, compile_formula, formula_literal
from .state.epoch import EPOCH as _EPOCH, bump as _bump
from .state.memos import Memos, adopt as _adopt_memo, owner_memos
from .sat.formula import FALSE, Not, P, TRUE, atoms_of
from .relations import (RELATION_ATOMS, Relations, Uninterpreted, _is_number,
                        glue_atoms, glue_objects, link_objects, under_of,
                        zero_args, zero_twin)
from .knowledge.rules import (BASIS_INDEX, BASIS_OF, DEF_LITS, NPRED, PRED_INDEX, RULE_CLAUSES, RULE_INTERNAL,
                    basis_lits, def_implications)
from .scope import (EMPTY as _EMPTY_SCOPE, SIGN_PREDS as _SIGN_PREDS, Scope,
                    affine_pair as _affine_pair, scope_of_atoms, theory_scope)
from .sat.solver import Solver
from .theories.sign import sign_adapter as _sign

Node = Any

#: the per-engine memos: attributes of :class:`Engine` that hold what the
#: engine computed (all keyed on the epoch and the engine's settings,
#: dropped by ``Engine._check_version`` and ``Engine._settings_changed``).
#: The fact caches are the engine's own unless a ``DictCache`` was passed
#: to several engines on purpose.
ENGINE_MEMOS: Tuple[str, ...] = (
    "answers", "splits", "_kids", "_cones", "_qcones", "_glue_adapters",
    "_failed", "_verdict", "_xbasis", "cache.store", "custom_cache.store",
)


def engine_memos(engine) -> Memos:
    """The :class:`Memos` of ``engine`` (``Engine.memos``):
    its memo attributes (:data:`ENGINE_MEMOS`), held through a weak
    reference so the object keeps no engine alive."""
    return owner_memos(engine, ENGINE_MEMOS, "settings")


#: the verdicts of an assumption set (``Engine.verdict``): only
#: ``INCONSISTENT`` makes a query raise; ``UNKNOWN`` (a theory gave up or
#: ran out of its branch budget, the set's cone is over the discovery
#: budget, the check could not conclude) never does
CONSISTENT = "consistent"
INCONSISTENT = "inconsistent"
UNKNOWN = "unknown"


class InconsistentAssumptions(ValueError):
    pass


#: Engine(writeback=...) policies (Engine._put_result); the first is the
#: default
_WRITEBACK = ("root-only", "none")
#: policies removed by issue #97 (P2): the fact cache is a memo of
#: ``Engine.is_`` only, no session writes its root facts back
_REMOVED_WRITEBACK = ("provenance", "all")

#: the cap of discovery and escalation in the engine's sessions: none (the
#: discovery budget is a test on the query's structural cone, made before
#: any session work: Engine._within_budget)
_UNCAPPED = float("inf")


def _noncommutative(term) -> bool:
    """Whether ``term`` has a non-commutative subterm (``Symbol('A',
    commutative=False)``, ``re(A)``): see :func:`satassume.knowledge.domain._noncommutative`.
    Such a term may stand for a matrix, while the rule base and the
    templates assume numbers (``commutative`` is true by definition,
    ``rules.DEFINITIONS``); the engine answers None about it (``sympy_api``
    keeps it out of scope before it reaches the engine)."""
    from .knowledge.domain import _noncommutative as nc
    return nc(term)


def _noncommutative_atoms(*formulas) -> bool:
    """Whether a vocabulary atom of ``formulas`` (None skipped) has a
    non-commutative term (:func:`_noncommutative`)."""
    return any(a.pred in PRED_INDEX and _noncommutative(a.expr)
               for f in formulas if f is not None for a in atoms_of(f))


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
      (``assumptions0``, see ``satassume/knowledge/templates/atoms.py``) and the
      old-system properties of objects with a fixed value (numbers, ``pi``,
      ``oo``, ...), where every non-None property is a static fact;
    * everything else is derived by the engine: the cache holds the answers
      of ``Engine.is_`` (a context-free query, decided in a session over
      the node's own cone: the rule base, the templates and the facts
      above, never a query's assumptions), True or False, never None
      (``Engine._put_result``).  Nothing else writes here, and no session
      reads it: the engine's sessions assert no cached fact, so the cache
      is a pure memo of ``is_`` (a fresh engine's same query gives the
      same answer; the harness ``audit`` mode checks it).

    The cache is keyed by the node (hash and ``==``), so structurally equal
    nodes share facts, which is sound because a node's context-free facts
    depend only on its structure and declared assumptions.

    The memo key.  An entry is ``(node, pred)`` under the registry epoch
    and the engine settings the facts were derived under: the cache
    records the epoch (:mod:`satassume.state.epoch`, ``_epoch``) and the
    settings fingerprint (``_settings``: the engine's ``templates``,
    ``transfer`` and ``uninterpreted``, the settings a context-free
    session's clause set reads; ``Engine._settings_fingerprint``).  Every
    engine using the cache compares both at each query and drops the
    whole store on a mismatch (``Engine._check_version``), so a cache
    shared between engines, given to an engine created after a
    registration, or written under other settings, starts empty for the
    engine that looks; two engines with the same settings share hits.
    A cache no engine has looked at (``_settings`` None) holds only what
    its owner seeded by hand (``put``) and is adopted as it is.
    The other settings are not in the key: ``discovery_budget`` decides
    whether a query is answered, not its value (``Engine.is_`` tests the
    cone before the lookup, and the session runs uncapped); ``writeback``
    decides whether the answer is stored; ``relevance`` concerns
    contextual queries only.

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
        #: the settings fingerprint (``Engine._settings_fingerprint``) the
        #: facts were derived under; None until an engine looks
        self._settings = None

    def sync(self, epoch: int, settings: tuple) -> None:
        """Bring the store up to ``epoch`` and ``settings``
        (``Engine._check_version``): empty it if it was filled under
        another epoch or other settings, then record both.  A cache no
        engine has looked at yet (``_settings`` None: it holds only what
        the caller seeded by hand) is adopted as it is."""
        if self._epoch != epoch or (self._settings is not None
                                    and self._settings != settings):
            self.store.clear()
        self._epoch = epoch
        self._settings = settings

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
    def __init__(self, engine: "Engine", scope: Scope = _EMPTY_SCOPE):
        self.engine = engine
        #: the theory scope the session is built for (``scope.theory_scope``
        #: of its query): the relation glue and predicate transfer exist
        #: from construction iff the scope says so (#97 P3)
        self.scope = scope
        self.solver = Solver()
        # no owner bookkeeping: nothing asks the solver for provenance
        # (the provenance writeback of #53 stage 3 was removed by #97 P2)
        self.solver.track_owners = False
        # the single-node rule base, propagated by the solver from the
        # exact closure of each node's block (Solver.register_block)
        self.solver.set_rule_block(RULE_INTERNAL, NPRED)
        self.table = VarTable()
        self.base: Dict[Node, int] = {}      # visited node -> variable of BASIS[0]
        self.frontier: deque = deque()
        self.pending: Dict[Node, list] = {}   # node -> template formulas not yet compiled
        self.pending_c: Dict[Node, list] = {}  # node -> (clauses, bases) pairs not yet emitted
        self.demand: Dict[Node, set] = {}     # node -> predicate indices the query needs
        self.deferred: List[Node] = []        # derived nodes, visited only by escalate()
        #: the verdict of the assumption set from the complete check run at
        #: construction (``Engine._build_context``); None outside it
        self.verdict: Optional[str] = None
        self.literals: Dict[Any, int] = {}    # compound formula -> Tseitin literal
        self.defvars: Dict[Any, int] = {}     # (derived predicate, node) -> its variable
        #: (definition, node) -> [variable, directions emitted (1: var ->
        #: definition, 2: definition -> var)]: the shared literal of a
        #: derived atom of several basis literals (:meth:`dvar`)
        self._dv: Dict[Any, list] = {}
        self._dv_node: Dict[Any, list] = {}  # node -> [(definition, variable)] linked
        #: whether asserted negated conjunctions get their shared literal
        #: (assume_formula: a set with many of them)
        self._neg_shared = False
        self.assumption_formula = None       # the formula of assume_formula()
        self._a_raw = ()                     # its atoms (atoms_of)
        self._a_zs = ()                      # their zero_args
        self._a_under = None                 # their under_of (lazily)
        #: the selector guarding the assumption formula's clauses (0: none)
        self.sel = 0
        #: the stable prefix of the last :meth:`assumption_lits`: the
        #: assumption literals the solver keeps between queries
        self.n_hold = 0
        #: group selectors of :meth:`assumption_lits` (key -> [var, implied
        #: selectors, stamp]; key True: the set's glue at the root,
        #: :meth:`_set_glue`)
        self._groups: Dict[Any, list] = {}
        #: the atoms of the assumption formula and its relation atoms (None:
        #: not computed yet)
        self._a_all: Optional[tuple] = None
        self._a_atoms: frozenset = frozenset()
        #: relation atoms and their theories (satassume.relations); created
        #: at construction when the scope has the glue (below), else by
        #: ``_custom`` for a relation atom outside the scope (counted)
        self.relations: Optional[Relations] = None
        #: the set's terms wait to be linked after the set's check
        #: (:meth:`link_set`): the glue the query's scope brings beyond the
        #: set's own must not take part in the check
        self._link_pending = False
        #: the Relations object once predicate transfer is engaged
        #: (Relations._engage_transfer); None on every other path
        self.xfer = None
        #: a budget cut dropped work: :meth:`escalate`, called with an
        #: explicit ``budget``, stopped with unvisited nodes (new, or with
        #: parked templates) on its frontier, or with parked templates or
        #: derived nodes left.  The engine never passes one:
        #: a query whose structural cone exceeds ``discovery_budget`` is
        #: answered None before any session work (``Engine._within_budget``)
        #: and every other query runs discovery and escalation uncapped, so
        #: a session the engine uses is never truncated (``Engine._note_budget``
        #: checks it).  If set (a direct caller), its set's complete check
        #: gives ``UNKNOWN``.
        self.truncated = False
        #: the sign theory once engaged (``sign_sync``), the sums and
        #: products visited since its last sync, and whether one of them
        #: is over the templates' arity caps (``sign_adapter.over_cap``)
        self.sign = None
        self._sign_nodes: List[Node] = []
        self._sign_over = False
        if scope.glue and engine._relation_specs:
            # the theory scope of the query is known at construction: the
            # glue (and transfer, if the scope says so) exists before any
            # atom is allocated, as a fresh engine for the query has it
            self.relations = Relations(self, engine._relation_specs)

    # -- variables -------------------------------------------------------

    def var(self, pred: str, node: Node) -> int:
        """The variable of ``pred(node)``: the node's block variable of a
        basis predicate; for a derived predicate (``rules.DEFINITIONS``)
        its definitional variable, allocated with the clauses of its
        definition the first time it is asked for."""
        i = BASIS_INDEX.get(pred)
        if i is not None:
            return self.node(node) + i
        if len(DEF_LITS[pred][1]) > 1:
            return self._dvar(DEF_LITS[pred], node, 3)
        key = (pred, node)
        v = self.defvars.get(key)
        if v is None:
            b = self.node(node)
            op, ls = basis_lits(pred)
            lits = [b + l - 1 if l > 0 else -(b - l - 1) for l in ls]
            v = self.defvars[key] = self.table.aux()
            self.solver.ensure_vars(v)
            emit = self.emit
            if op == '&':
                for l in lits:
                    emit([-v, l])
                emit([v] + [-l for l in lits])
            else:
                for l in lits:
                    emit([-l, v])
                emit([-v] + lits)
        return v

    def dvar(self, dn: tuple, need: str = 'both') -> int:
        """The literal of the derived atom ``dn = (definition, node)`` (see
        :func:`satassume.knowledge.compile._def`) shared by all its
        occurrences (the assumptions, the proposition, :meth:`var`), with
        the directions ``need`` of its definition emitted (``'pos'``: the
        variable implies the definition, ``'neg'``: the converse,
        ``'both'``; see :func:`satassume.knowledge.compile.compile_formula`).  A
        definition of one basis literal (``infinite``) is that literal.
        ``need='basis'``: ``dn`` is a basis or custom atom under a
        connective of a formula, and the result its variable; a basis one
        is linked like a derived one (``extended_positive ->
        extended_nonnegative``, :meth:`_link`)."""
        if need == 'basis':
            v = self.table.var(dn)
            i = BASIS_INDEX.get(dn.pred)
            if i is not None:
                self._link(('&', (i + 1,)), dn.expr, v)
            return v
        d, node = dn
        op, ls = d
        if need in ('negunit', 'posunit'):
            # a negated conjunction (an asserted disjunction) of the
            # assumptions: its own literal only in a set with many (one
            # clause and a variable more each, against a search conflict
            # each when a wide proposition holds them; see assume_formula)
            if not self._neg_shared or len(ls) < 2:
                return None
            need = 'neg' if need == 'negunit' else 'pos'
        if len(ls) == 1:
            b = self.node(node)
            v = b + ls[0] - 1 if ls[0] > 0 else -(b - ls[0] - 1)
            self._link(d, node, v)
            return v
        return self._dvar(d, node, 3 if need == 'both' else 1 if need == 'pos' else 2, True)

    def _dvar(self, d: tuple, node: Node, need: int, link: bool = False) -> int:
        key = (d, node)
        e = self._dv.get(key)
        b = self.node(node)
        emit = self.emit
        if e is None:
            v = self.table.aux()
            self.solver.ensure_vars(v)
            e = self._dv[key] = [v, 0, False]
        v, have, linked = e
        if link and not linked:
            e[2] = True
            self._link(d, node, v)
        missing = need & ~have
        if missing:
            op, ls = d
            lits = [b + l - 1 if l > 0 else -(b - l - 1) for l in ls]
            if op == '&':
                if missing & 1:
                    for l in lits:
                        emit([-v, l])
                if missing & 2:
                    emit([v] + [-l for l in lits])
            else:
                if missing & 2:
                    for l in lits:
                        emit([-l, v])
                if missing & 1:
                    emit([-v] + lits)
            e[1] = have | need
        return v

    def _link(self, d, node: Node, v: int) -> None:
        """Link literal ``v`` of definition ``d`` (``(op, literals)``; a
        basis atom is ``('&', (i,))``) at ``node`` to the node's other
        linked literals by the binary clauses the rule base gives
        (``positive -> nonnegative``, ``extended_positive ->
        extended_nonnegative``), so a unit on one propagates to the others
        as with a variable per predicate; without it a wide formula of one
        against a wide formula of the other costs a search conflict per
        disjunct.  Only for the literals of formulas (``dv``), not for
        those relations and decisions ask for (:meth:`var`).  Clauses
        between two single literals are the rule base's, and those between
        a definition and one of its own literals are its definition's."""
        others = self._dv_node.setdefault(node, [])
        if (d, v) in others:
            return
        own = {abs(l) for l in d[1]}
        for d2, v2 in others:
            if len(d[1]) == 1 and (len(d2[1]) == 1 or own <= {abs(l) for l in d2[1]}):
                continue
            if len(d2[1]) == 1 and abs(d2[1][0]) in own:
                continue
            for s1, s2 in def_implications(d, d2):
                self.emit([s1 * v, s2 * v2])
        others.append((d, v))

    def query_lit(self, pred: str, node: Node):
        """What :meth:`query_literal` decides for ``pred(node)``: the
        variable of a basis predicate, the basis literal of a derived one
        defined by a single literal, else ``(op, literals)``, the
        definition over the node's block (no variable, no clauses)."""
        i = BASIS_INDEX.get(pred)
        if i is not None:
            return self.node(node) + i
        b = self.node(node)
        op, ls = basis_lits(pred)
        lits = tuple(b + l - 1 if l > 0 else -(b - l - 1) for l in ls)
        if len(lits) == 1:
            return lits[0]
        return op, lits

    def prepare_query(self, proposition):
        """Make the session ready to answer ``proposition`` and return what
        :meth:`query_literal` then decides (``Engine._ask``; not to be
        confused with :meth:`query_lit`, which only reads a visited
        node's block, or :meth:`query_literal`, which decides): for a
        vocabulary atom, :meth:`query_lit` of it
        once its node is visited for its predicate, the twins ``eq(t, 0)``
        of its zero atom are allocated and the glue has read it (no
        variable of its own); for any other formula, :meth:`literal_of`."""
        if isinstance(proposition, P) and proposition.pred in PRED_INDEX:
            self.ensure(proposition.expr, {proposition.pred})
            if self._ensure_twins((proposition,)):    # twins eq(t, 0)
                self._flush()
            if self.relations is not None:
                self._relations(proposition)
            return self.query_lit(proposition.pred, proposition.expr)
        return self.literal_of(proposition)

    def emit(self, clause: List[int]) -> None:
        """Add ``clause`` (signed variables of this session's table) to the
        session's solver: how the glue (``relations``) and the compilers
        add clauses to a session."""
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
        table.new_nodes = []
        constructing = self.engine._constructing
        constructing.add(node)
        try:
            self._visit(node, b, demanded)
        finally:
            constructing.discard(node)
        return b

    def _visit(self, node: Node, b: int, demanded) -> None:
        """The body of :meth:`node`."""
        engine = self.engine
        # 1. structural templates, and vocabulary predicates registered for
        #    the node's class (satassume.knowledge.extensions)
        if engine.clause_templates is not None:
            compiled, formulas = engine.clause_templates(node)
        else:
            compiled, formulas = (), engine._templates(node)
        ext = engine._extensions
        if ext is not None and ext.has_node_facts:
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
        # (no cached fact enters a session: the fact cache is a memo of
        # Engine.is_, read by it alone)
        if compiled:
            self._compile_patterns(node, compiled, demanded)
        if items:
            if demanded is None:
                self._compile(node, items)
            else:
                self.pending[node] = items
                self._compile_pending(node, demanded)
        if (getattr(node, 'is_Add', False) or getattr(node, 'is_Mul', False)) and node.args:
            self._sign_nodes.append(node)
            if not self._sign_over and _sign.over_cap(node):
                self._sign_over = True

    # -- compiled template patterns (the fast path) -------------------------
    def _compile_patterns(self, node: Node, compiled, demanded) -> None:
        """Emit the clauses of the compiled patterns of ``node`` (see
        ``satassume.knowledge.templates._common.Pattern``): allocate the variable
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
        emit = self.emit
        demand = self.demand
        for f, atoms in items:
            for atom in atoms:
                if atom.expr != node and atom.pred in PRED_INDEX:
                    d = demand.get(atom.expr)
                    if d is None:
                        d = demand[atom.expr] = set()
                    d.update(BASIS_OF[atom.pred])
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
        """A custom-predicate atom was allocated: assert the formulas its
        registered functions generate (a cached value of it is a memo of
        ``Engine._is_custom`` and does not enter the session)."""
        engine = self.engine
        if atom.pred in RELATION_ATOMS and engine._relation_specs:
            rel = self.relations
            if rel is None:
                # outside the session's scope: a session built for a set
                # alone and asked a relation (tests), or a relation atom of
                # a node fact (``Extensions.node_facts``, fired over the
                # cone, which the syntax does not foresee; the facts of
                # custom atoms are in the scope, ``scope.extension_atoms``);
                # counted (stats["scope_misses"])
                engine.stats["scope_misses"] += 1
                rel = self.relations = Relations(self, engine._relation_specs)
                if self.assumption_formula is not None:
                    # unary atoms of the assumptions become link candidates
                    rel.note_formula(atoms_of(self.assumption_formula))
            rel.enqueue(atom)
            return
        ext = engine._extensions
        if ext is None:
            return
        for f in ext.facts_for(atom):
            compile_formula(f, self.table, self.emit)

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
                if a.expr == node and not BASIS_OF.get(a.pred, _NO_BASIS).isdisjoint(want):
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

    def ensure(self, node: Node, demanded=None) -> None:
        """Demand-driven discovery: visit ``node`` and, breadth-first, the
        nodes its templates mention, uncapped (the engine's queries passed
        ``Engine._within_budget``).

        A visited node with nothing parked is only recorded (the discovery
        below would skip it at once)."""
        if demanded is not None:
            d = self.demand.setdefault(node, set())
            for p in demanded:
                d.update(BASIS_OF[p])
        if node in self.base and node not in self.pending and node not in self.pending_c:
            if self.frontier:
                self.frontier = deque()
            return
        self.frontier = deque([node])
        self._discover(demanded)

    def discover(self) -> None:
        """Visit what the clauses emitted since the last visit mention: run
        the clause generators of newly allocated custom atoms, then visit
        the newly mentioned nodes breadth-first, uncapped.  Called after a
        user formula is compiled and by the relation glue after it adds
        clauses (``Relations.process``)."""
        self._flush()
        self._discover()

    def _discover(self, demanded=None) -> None:
        pending, pending_c = self.pending, self.pending_c
        while self.frontier:
            n = self.frontier.popleft()
            if n in self.base and n not in pending and n not in pending_c:
                continue
            self.node(n, None if demanded is None else self.demand.get(n, set()))
        self.frontier = deque()

    @property
    def incomplete(self) -> bool:
        """True while :meth:`escalate` has something left to do."""
        return bool(self.pending or self.pending_c or self.deferred)

    def escalate(self, budget: Optional[int] = None) -> None:
        """Compile every parked formula and visit every derived node (full
        instantiation of the cone).  ``budget`` caps the steps (a parked
        node's patterns or formulas compiled, a new node visited); None is
        no cap, which is how the engine calls it.  Work left over when the
        budget runs out sets ``truncated``; the frontier is emptied either
        way."""
        if budget is None:
            budget = _UNCAPPED
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
        if self.pending or self.pending_c or self.deferred or self.frontier:
            base = self.base
            if self.pending or self.pending_c or any(n not in base for n in self.deferred) \
                    or any(n not in base for n in self.frontier):
                self.truncated = True
        self.frontier = deque()

    def sign_sync(self, open_query: bool = False) -> bool:
        """Engage the sign theory (``satassume.theories.sign``) as
        ``sign_adapter.ENGAGE`` says and tell it the sums and products
        visited since the last sync; ``open_query``: the query is open after
        propagation and escalation.  True iff something was registered."""
        nodes = self._sign_nodes
        if not nodes:
            return False
        if self.sign is None:
            mode = _sign.ENGAGE
            if not (mode == 'always' or self._sign_over and mode != 'off'
                    or open_query and mode == 'escalate'):
                return False
            self.sign = _sign.SignAdapter(self)
        self._sign_nodes = []
        for n in nodes:
            self.sign.add(n)
        return True

    # -- queries -------------------------------------------------------------
    def query_literal(self, lit, assumptions: Iterable[int] = (),
                      search: bool = True) -> Optional[bool]:
        if type(lit) is tuple:
            # a derived predicate (query_lit): a disjunction is decided as
            # the negation of the conjunction of the negated literals
            op, ls = lit
            if op == '|':
                r = self._query_all([-l for l in ls], assumptions, search)
                return None if r is None else not r
            return self._query_all(list(ls), assumptions, search)
        solver = self.solver
        if self.xfer is not None:
            self.xfer.sync_transfer()
        if not solver.propagate():
            raise InconsistentAssumptions("rule base or declared facts (templates) are inconsistent")
        # the query literal is read: its variable's rule-block implication
        # must be on the trail (Solver.mention)
        solver.mention((lit,))
        assumptions = list(assumptions)
        # the solver keeps the levels of all the assumptions and continues
        # from the longest prefix the next call shares (the set's
        # selectors, then the query's: see assumption_lits); the engine
        # releases the query's before the next query adds clauses
        # (Solver.release).  Holding fewer or more levels changes what is
        # reused, never an answer
        if assumptions:
            # consistency of the assumptions is checked before any answer,
            # even when the query is already decided at root, mirroring
            # sympy.ask: by propagation first, then (below, or in
            # Solver.entails) by a model of the clauses under them
            implied = solver.implied(assumptions)
            if implied is None:
                raise InconsistentAssumptions("inconsistent assumptions")
            s = set(implied)
            r = True if lit in s else False if -lit in s else None
            if r is not None:
                # settled by propagation: returned only once the assumptions
                # are known consistent with the clauses (as Solver.entails
                # does), since propagation need not find a conflict
                if not solver.consistent(assumptions):
                    raise InconsistentAssumptions("inconsistent assumptions")
                return r
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
        return r

    def _query_all(self, ls: List[int], assumptions, search: bool) -> Optional[bool]:
        """:meth:`query_literal` of the conjunction of ``ls``."""
        solver = self.solver
        if self.xfer is not None:
            self.xfer.sync_transfer()
        if not solver.propagate():
            raise InconsistentAssumptions("rule base or declared facts (templates) are inconsistent")
        solver.mention(ls)
        assumptions = list(assumptions)
        if assumptions:
            implied = solver.implied(assumptions)
            if implied is None:
                raise InconsistentAssumptions("inconsistent assumptions")
            s = set(implied)
            vals = [True if l in s else False if -l in s else None for l in ls]
            if (False in vals or all(vals)) and not solver.consistent(assumptions):
                raise InconsistentAssumptions("inconsistent assumptions")
        else:
            vals = [solver.value(l) for l in ls]
        if False in vals:
            return False
        if all(vals):
            return True
        if not search:
            return None
        try:
            return solver.entails_all(ls, assumptions)
        except ValueError as e:
            raise InconsistentAssumptions(str(e)) from e

    def assume_formula(self, f) -> List[int]:
        """Turn a formula into solver assumption literals: its clauses are
        guarded by a fresh selector variable ``s`` and ``s`` is assumed."""
        self.assumption_formula = f
        self._a_raw = atoms_of(f)
        self._a_zs = zero_args(self._a_raw)
        self._a_under = None
        self._a_all = None
        self._ensure_atoms(f)
        s = self.table.aux()
        self.sel = s
        # many derived atoms of several basis literals: their negations,
        # if asserted, get the atoms' shared literals (Session.dvar), which
        # a wide proposition over them then meets by propagation instead
        # of one search conflict per atom; a function of the set
        self._neg_shared = sum(1 for a in self._a_raw if len(DEF_LITS.get(a.pred, ((), ()))[1]) > 1) >= _NEG_SHARED

        def emit(clause):
            self.emit(clause + [-s])
        compile_formula(f, self.table, emit, self.dvar)
        self.discover()
        if self.relations is not None:
            if theory_scope(f, None, self.engine._extensions).glue:
                # the set's own scope has the glue (a relation atom, an
                # affine pair or a zero twin of the set, or a relation atom
                # of its extension facts, the same scope the session is
                # built with for the set alone): its links and interpreted
                # relations are part of the set and of the set's check
                self._relations(f)
            else:
                # the glue is the query's: the set's terms are linked after
                # the set's check (link_set, Engine._build_context), so the
                # check and its verdict are a function of the set
                self._link_pending = True
        return [s]

    def link_set(self) -> None:
        """Link the set's terms for the query's glue once the set's check
        has run (``_link_pending``, :meth:`assume_formula`): the arguments
        of the set's vocabulary atoms get their links under the query's
        scope, as the lazy order linked them at the query's first relation
        atom.  Called by :meth:`Engine._build_context`; idempotent."""
        if self._link_pending:
            self._link_pending = False
            self._relations(self.assumption_formula)

    def assumption_lits(self, prop=None) -> List[int]:
        """The solver assumptions of a query ``prop`` (None: the set's own
        check) under this session's assumption formula: the formula's
        selector, then a group selector for the glue the set activates
        (none when the set holds a relation atom: that glue is then on at
        the root, :meth:`_set_glue`), then the selectors ``prop`` activates
        beyond the set's.  ``n_hold`` is set to the length of the stable
        prefix (everything that depends on the set only), whose levels the
        solver keeps from the set's check to the query (``Engine._ask``
        releases the others before the query adds clauses,
        ``Solver.release``)."""
        lits = [self.sel] if self.sel else []
        self.n_hold = len(lits)
        rel = self.relations
        if rel is None:
            return lits
        # the set's terms are linked before any query (link_set): the
        # session is built by _build_context, never queried half-built
        assert prop is None or not self._link_pending, "Session.link_set"
        a_all = self._a_all
        if a_all is None:
            # a zero(t) whose t is under an application of the set counts
            # as its twin eq(t, 0) (relations.glue_atoms): root glue, a
            # function of the set alone
            a_all = self._a_all = glue_atoms(self._a_raw)
            self._a_atoms = frozenset(x for x in a_all if x.pred in RELATION_ATOMS)
        a_atoms = self._a_atoms
        a_rel = bool(a_atoms)
        # and the query's: the twins of the zero(t) of p and of the set
        # whose t is under an application of p or of the set, a function
        # of (p, a); those the set has alone are in seen below
        p_all = self._glue_of(atoms_of(prop)) if prop is not None else ()
        p_atoms = [x for x in p_all if x.pred in RELATION_ATOMS]
        p_rel = bool(p_atoms)
        if not (a_rel or p_rel or _affine_pair(a_all + tuple(p_all))):
            # no relation and no affine pair (scope.affine_pair): the glue
            # the session has for its query's scope stays switched off (for
            # the set's own check, prop None, whatever the query's scope)
            return lits
        a_x = a_rel and rel.wants_transfer(a_atoms)
        if a_rel:
            # The set's own glue is fixed at the root.  This session
            # answers only queries under ``a`` (Engine._context_session
            # keys it by the set), and with a relation atom in ``a`` the
            # early return above never fires: the set's selectors
            # (Relations.selectors_of(a), and transfer's when ``a``
            # itself makes an equality) are assumed by every query the
            # session ever answers, its own check included.  Glue that is
            # on in every query is not history: a fresh session for
            # (p, a) has Act(a) | Act(p); this one has Act(a) at the root
            # and Act(p) - Act(a) switched on by the query's selectors
            # below, and the switched-off glue of earlier queries is inert
            # (I3, as in the module docstring of satassume.relations).
            # What these selectors guard is a function of ``a`` alone:
            # the links of a's terms (made while ``a`` was processed,
            # their integrality, twins and share sources included), the
            # clauses of a's equality atoms, a's numbers' congruence
            # sources and transfer.  Glue a query made with an atom or
            # term of ``a`` keeps a selector of the query: a _trichotomy
            # pair with one atom of the query is guarded by both atoms'
            # selectors, an interface equality (_share) by the share
            # variables of both terms, which the query's links imply.  A
            # root unit only differs from an assumption in what the
            # solver keeps: it survives restarts and the held levels, so
            # transfer is not switched on again (a rescan) per level.  A
            # root unit of the glue is never a context-free fact: no
            # session writes to the caches.
            seen = self._set_glue(a_all, a_x)
        else:
            # Without a relation atom in ``a`` the set's links are on only
            # in the queries that call for them (``p`` holds a relation or
            # makes an affine pair): one group selector stands for them,
            # so the solver assumes them at one level (_group_sel); assumed
            # or not, it is exactly as if its members were
            seen = ()
            if a_all:
                ga = self._group_sel(None, a_all)
                if ga:
                    lits.append(ga)
                    seen = self._groups[None][1]
        self.n_hold = len(lits)             # the stable prefix
        if p_all:
            # the query's delta: its selectors the set's glue does not hold
            lits.extend(x for x in rel.selectors_of(p_all) if x not in seen)
            xs = rel.xfer_sel
            if xs is not None and p_rel and not a_x and rel.wants_transfer(
                    a_atoms.union(p_atoms)):
                lits.append(xs)
        return lits

    def _set_glue(self, a_all, xfer: bool) -> set:
        """Assert as root units the selectors of the glue of the assumption
        formula, whose atoms are ``a_all`` (``Relations.selectors_of`` and,
        if ``xfer``, transfer's), that are not yet; return the set of them.
        Only for a formula with a relation atom, whose glue every query of
        the session assumes (see :meth:`assumption_lits`).  Recomputed only
        when a selector the formula may still get was allocated since: of
        a term of it not linked yet, of a relation atom of it with none
        yet (an order atom gets one when a query brings its reverse,
        Relations._trichotomy), or transfer's."""
        rel = self.relations
        g = self._groups.get(True)
        if g is None:
            # [selectors, stamp, a term may still get one, an atom may]
            g = self._groups[True] = [set(), None, True, True]
        have = g[0]
        stamp = (len(rel.link_sel) + len(rel.num_sel) if g[2] else -1,
                 len(rel.atom_sel) if g[3] else -1,
                 rel.xfer_sel if xfer else None)
        if stamp == g[1]:
            return have
        want = set(rel.selectors_of(a_all))
        if xfer and rel.xfer_sel is not None:
            want.add(rel.xfer_sel)
        new = want - have
        if new:
            for x in sorted(new):
                self.emit([x])
            have |= new
        lsel, nsel, asel, status = rel.link_sel, rel.num_sel, rel.atom_sel, rel.status
        tp = ap = False
        for x in a_all:
            if x.pred in PRED_INDEX:
                e = x.expr
                if e not in lsel and e not in nsel and not _is_number(e):
                    tp = True
            elif x.pred in RELATION_ATOMS:
                if x not in asel:
                    ap = True
                if status.get(x) is not False and any(
                        e not in lsel and not _is_number(e) for e in x.expr):
                    tp = True
        g[2], g[3] = tp, ap
        g[1] = (len(lsel) + len(nsel) if tp else -1, len(asel) if ap else -1,
                rel.xfer_sel if xfer else None)
        return have

    def _group_sel(self, key, atoms) -> int:
        """A selector that implies the selectors a formula with the atoms
        ``atoms`` activates (``Relations.selectors_of``): one per session
        and ``key`` (None: the assumption formula), its implications
        extended as selectors are allocated; 0 if there is none.  The
        members are recomputed only when the session allocated selectors
        since."""
        rel = self.relations
        groups = self._groups
        g = groups.get(key)
        stamp = (len(rel.link_sel), len(rel.atom_sel), len(rel.num_sel), rel.xfer_sel)
        if g is not None and g[2] == stamp:
            return g[0]
        want = set(rel.selectors_of(atoms))
        if g is None:
            if not want:
                groups[key] = [0, set(), stamp]
                return 0
            v = self.table.aux()
            self.solver.ensure_vars(v)
            g = groups[key] = [v, set(), stamp]
            self.solver.set_inert(v)
        elif not g[0]:
            if not want:
                g[2] = stamp
                return 0
            g[0] = self.table.aux()
            self.solver.ensure_vars(g[0])
            self.solver.set_inert(g[0])
        v, have = g[0], g[1]
        for x in sorted(want - have):
            self.emit([-v, x])
        have |= want
        g[2] = stamp
        return v

    def literal_of(self, f) -> int:
        lit = self.literals.get(f)
        if lit is not None:
            return lit
        self._ensure_atoms(f)
        lit = formula_literal(f, self.table, self.emit, self.dvar)
        self.discover()
        if self.relations is not None:
            self._relations(f)
        self.literals[f] = lit
        return lit

    # -- relations (satassume.relations) ---------------------------------------
    def _relations(self, f) -> None:
        """Interpret the relation atoms ``f`` brought in, link and share;
        raises ``Uninterpreted`` if a relation of ``f`` has no theory.  Only
        called once the session has a ``Relations`` object (built with
        the scope, or by :meth:`_custom` outside it), so the unary path
        pays one test."""
        rel = self.relations
        atoms = atoms_of(f)
        rel.note_formula(atoms)
        if rel.active or rel.queue:
            # the twins of zero atoms are user equalities of f
            # (relations.glue_atoms, allocated by _ensure_atoms)
            rel.process(self._glue_of(atoms))

    def _glue_of(self, atoms) -> tuple:
        """The atoms the relation glue reads a formula of this session by
        (``relations.glue_atoms``), ``atoms`` and the twins of zero atoms:
        for the assumption formula its own; for a query ``p``, those of
        ``p`` and the set together (a ``zero(n)`` of the set whose ``n`` is
        under an application of ``p``), a function of ``(p, a)``.  The
        session's set is fixed (``Engine._context_session`` keys it by the
        set), so a formula's twins are the same in every query."""
        a_zs = self._a_zs
        if not a_zs and not any(x.pred == "zero" for x in atoms):
            return atoms
        u = self._a_under
        if u is None:
            u = self._a_under = under_of(self._a_raw)
        return glue_atoms(atoms, cinfo=(a_zs, u))

    def _ensure_atoms(self, f) -> None:
        """Visit the nodes of the vocabulary atoms of ``f``.  Custom atoms
        are allocated when ``f`` is compiled (see :meth:`_custom`); the
        twin ``eq(t, 0)`` of a ``zero(t)`` atom (``relations.glue_atoms``)
        here, with an engine with relation specs: the first one makes the
        session's relations (:meth:`_custom`, at the next ``_flush``)."""
        atoms = atoms_of(f)
        for atom in atoms:
            if atom.pred in PRED_INDEX:
                self.ensure(atom.expr, {atom.pred})
        self._ensure_twins(atoms)

    def _ensure_twins(self, atoms) -> bool:
        """Allocate the twins of the zero atoms the glue reads a formula
        with the atoms ``atoms`` with (:meth:`_glue_of`); whether it has
        any."""
        if not self.engine._relation_specs:
            return False
        g = self._glue_of(atoms)
        if g is atoms:
            return False
        var = self.table.var
        for atom in g[len(atoms):]:
            var(atom)
        return True


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


def _check_writeback(value: str) -> str:
    if value in _REMOVED_WRITEBACK:
        raise ValueError(f"writeback={value!r} was removed by issue #97 (P2): the fact "
                         f"cache is a memo of Engine.is_ only; use one of {_WRITEBACK}")
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
        The largest structural cone a query may have: a query whose cone,
        ``cone(p) | cone(a)`` (templates, derived nodes, extension facts
        and relation glue, weighted as ``_struct`` explains), weighs
        more is answered None before any session work, and so is every
        query under a set whose own cone does (its verdict is ``UNKNOWN``);
        ``last_budget_limited`` tells.  A function of the query alone
        (``_within_budget``); every other query runs discovery and
        escalation uncapped, so nothing is truncated: a session loads at
        most the query's cone (the set's and the proposition's).
    extensions : satassume.knowledge.extensions.Extensions or None
        Registered clause-generating functions for custom predicates and
        for vocabulary predicates on new classes.  Defaults to the global
        registry ``satassume.knowledge.extensions.extensions``.
    relations : sequence of satassume.relations.AdapterSpec, or None
        Theory adapters for relation atoms.  None: the LRA and EUF adapters
        if present (with the SymPy templates only); ``[]``: relations are
        out of scope.  Kept as the tuple ``relation_specs``; assigning it
        (or ``extensions``) after construction drops the caches.
    transfer : bool
        Share unary facts between terms EUF puts in one class
        (:mod:`satassume.theories.transfer`): ``Q.positive(y)`` from ``Q.eq(x, y) &
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
        connected to it only (see ``sympy_api._relevant``) unless the whole
        set is found inconsistent (then under the whole set, which raises);
        a consistent or unknown set answers under the part.  False: always
        under the whole set.
    writeback : ``"root-only"`` or ``"none"``
        Whether ``Engine.is_`` memoizes its answer in the context-free
        caches (``_put_result``): ``"root-only"`` (default) stores the
        answer of ``is_(node, pred)`` under ``node`` (and of a custom
        atom's query in ``custom_cache``), True or False, never None;
        ``"none"`` stores nothing (for measurement).  Nothing else writes
        to the caches and no session reads them, so the cache is a pure
        memo of ``is_`` at every budget.  ``"provenance"`` and ``"all"``
        (root facts of whole sessions, #53 stage 3) were removed by issue
        #97 (P2) and raise ``ValueError``.  A setting:
        assigning a different value drops this engine's caches
        (``_settings_changed``).
    """

    def __init__(self, templates=None, cache: Optional[DictCache] = None,
                 discovery_budget: int = 400,
                 extensions=None, relations=None, transfer: bool = True,
                 uninterpreted: str = "free", relevance: bool = True,
                 writeback: str = "root-only"):
        clause_templates = None
        if templates is None:
            try:
                from .knowledge.templates import registry
            except ModuleNotFoundError as e:  # pragma: no cover
                # a broken template package must not turn into silent
                # Nones: only a missing SymPy means "no templates"
                if e.name != "sympy":
                    raise
                templates = lambda node: ()
            else:
                templates = registry.facts_for
                clause_templates = registry.clauses_for
        if extensions is None:
            from .knowledge.extensions import extensions
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
        #: always empty since issue #97 (no contextual session is kept
        #: between queries); the tests assert that it stays empty
        self._context_sessions: "OrderedDict[Any, Tuple[Session, List[int]]]" = OrderedDict()
        self._constructing: set = set()
        #: the structural cones of the discovery budget (``_struct``,
        #: ``_cone_info``, ``_query_cone``): object -> ``(kids, weight)``,
        #: object -> ``(cone or None, weight, has relation atom)``, formula
        #: -> its cone record; functions of the object, the registry and
        #: the settings, dropped with the other caches
        self._kids: Dict[Any, Any] = {}
        self._cones: Dict[Any, Any] = {}
        self._qcones: Dict[Any, Any] = {}
        #: adapters that only read linear forms for the glue's weight
        #: (``relations.glue_objects``), by spec name
        self._glue_adapters: Dict[str, Any] = {}
        #: assumption formulas whose session construction raised
        #: ``Uninterpreted`` -> its message (see :meth:`_context_session`)
        self._failed: Dict[Any, str] = {}
        #: assumption formula -> its verdict (``CONSISTENT``,
        #: ``INCONSISTENT`` or ``UNKNOWN``), from one complete check per set
        #: (see :meth:`_context_session`); bounded, cleared with the sessions
        self._verdict: Dict[Any, str] = {}
        #: number -> its basis of facts for predicate transfer
        #: (``relations._number_basis``): read from this engine's own
        #: ``is_many``, so it depends on the settings and the registry epoch
        #: and is dropped with the other set memos
        self._xbasis: Dict[Any, Any] = {}
        #: the registry epoch (:mod:`satassume.state.epoch`) the engine-level
        #: caches were filled under; -1 until the first query
        self._epoch = -1
        #: this engine's memos, by name (:func:`engine_memos`)
        self.memos = engine_memos(self)
        #: the fingerprint of the settings ``is_`` depends on
        #: (``_settings_fingerprint``), part of the fact caches' memo key
        self._settings_key = self._settings_fingerprint()
        #: counters; ``theory_gave_up``: contextual queries whose session's
        #: theory gave up (satassume.sat.theory, "Giving up"), answered None
        self.stats = {"queries": 0, "cache_hits": 0, "escalations": 0,
                      "searches": 0, "sessions": 0,
                      "relevant": 0, "consistency_checks": 0, "theory_gave_up": 0,
                      "version_clears": 0, "set_checks": 0,
                      "budget_limited": 0, "scope_misses": 0}
        #: whether the last query was over the discovery budget (its
        #: structural cone outweighs ``discovery_budget``: answered None,
        #: no session touched); a function of the query, cache hit or not
        self.last_budget_limited = False

    def _fresh_session(self, scope: Scope = _EMPTY_SCOPE) -> Session:
        self.stats["sessions"] += 1
        return Session(self, scope)

    # -- the registry epoch ---------------------------------------------------
    @property
    def extensions(self):
        """The registry of clause-generating functions
        (``satassume.knowledge.extensions.Extensions``) or None.  Assigning another
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
        """Setting: the largest structural cone (``cone(p) | cone(a)``,
        weighed by ``_within_budget``) of a query that is answered; heavier
        queries are None (``last_budget_limited``).  Assigning a different
        value drops this engine's caches (``_settings_changed``)."""
        return self._discovery_budget

    @discovery_budget.setter
    def discovery_budget(self, value) -> None:
        if value != self._discovery_budget:
            self._discovery_budget = value
            self._settings_changed()

    @property
    def transfer(self):
        """Setting: engage predicate transfer (satassume.theories.transfer).  Assigning a different
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
        """Setting: whether ``is_`` memoizes its answer, ``"root-only"``
        or ``"none"`` (see the class docstring; ``"provenance"`` and
        ``"all"`` are removed).  Assigning a different value drops this
        engine's caches (``_settings_changed``), like every setting."""
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
        their caches.  The settings fingerprint (``_settings_fingerprint``)
        is recomputed in every case; a fact cache whose fingerprint differs
        is dropped at the engine's next query (``_check_version``), so a
        change before the first query (``_epoch == -1``) drops a cache
        filled by another engine too.  After the first query this also
        drops what :meth:`_check_version` drops for the engine (the answer
        and split memos, the ``Uninterpreted`` memo, the verdict memo, the
        numbers' transfer bases ``_xbasis``: ``_drop_set_memos``),
        counted in ``stats["version_clears"]``, and the stores of the
        engine's fact caches (``cache``, ``custom_cache``): their facts can
        depend on ``templates``, ``transfer`` and ``uninterpreted``, and a
        set's verdict on those, ``discovery_budget`` (which cones fit) and
        ``writeback``.  A ``DictCache`` shared with other engines is
        cleared for them too: a needless clear for them, never a stale
        answer.  :data:`satassume.state.epoch.EPOCH` is untouched.  The
        structural cone memos of the budget test are dropped in every
        case."""
        self._settings_key = self._settings_fingerprint()
        self._drop_cones()
        if self._epoch >= 0:
            self._drop_set_memos()
            self.cache.store.clear()
            self.custom_cache.store.clear()

    def _check_version(self) -> None:
        """Drop every engine-level cache filled under an earlier registry
        epoch (:mod:`satassume.state.epoch`): the fact caches, the answer and
        split memos, the ``Uninterpreted`` memo, the verdict memo and the
        numbers' transfer bases (``_xbasis``; all but the fact caches via
        ``_drop_set_memos``) hold results computed under the registrations
        in force at the time.  The entry of every query calls this when the engine's epoch
        is not the current one (``if self._epoch != _EPOCH[0]``), and
        ``is_`` also when a fact cache's settings fingerprint is not the
        engine's (one tuple comparison per query): a ``DictCache`` records
        its own epoch and fingerprint (``DictCache._epoch``,
        ``_settings``), so a cache shared between engines, given to an
        engine created after a registration, or written under other
        settings (``templates``, ``transfer``, ``uninterpreted``) is
        dropped by the first engine that looks and starts empty for it.
        Nothing is counted before the engine's first query, so registering
        before using an engine costs nothing."""
        epoch = _EPOCH[0]
        if self._epoch != epoch:
            self._drop_cones()
            if self._epoch >= 0:
                self._drop_set_memos()
            self._epoch = epoch
        self.cache.sync(epoch, self._settings_key)
        self.custom_cache.sync(epoch, self._settings_key)

    def _settings_fingerprint(self) -> tuple:
        """The settings a context-free query's answer depends on, as the
        part of the fact caches' memo key (``DictCache._settings``):
        ``(templates, transfer, uninterpreted)``, compared with ``==``
        (``templates`` by identity, as its setter does)."""
        return (self._templates, self._transfer, self._uninterpreted)

    def _drop_set_memos(self) -> None:
        """Drop the memos of whole queries and sets (the answer and split
        memos, the ``Uninterpreted`` and verdict memos, the numbers'
        transfer bases), counted in ``stats["version_clears"]``: what an
        epoch or a settings change invalidates besides the fact caches and
        the cones."""
        self.stats["version_clears"] += 1
        self.answers.clear()
        self.splits.clear()
        self._failed.clear()
        self._verdict.clear()
        self._xbasis.clear()

    # -- the discovery budget: a test on the query's structural cone ----------
    def _drop_cones(self) -> None:
        self._kids.clear()
        self._cones.clear()
        self._qcones.clear()
        self._glue_adapters.clear()

    def _struct(self, o):
        """``(kids, weight)`` of a cone object ``o``, memoized per engine
        (``_kids``, dropped with the other caches).  ``kids``: the objects
        ``o``'s templates mention (compiled patterns and formulas, extension
        vocabulary facts; for a custom atom, its extension facts; for a
        relation atom of an engine with adapters, what its glue can visit,
        ``relations.glue_objects``), parked and derived ones too: a function
        of ``o``, the registry and the settings, read whether or not a
        session visited ``o``.  ``weight``: 1 for a node, 2 for a node with
        both compiled patterns and formulas (both can be parked, and
        escalation handles each), 0 for a custom or relation atom (no node
        of its own)."""
        kids = self._kids
        r = kids.get(o)
        if r is not None:
            return r
        if len(kids) >= 200_000:
            kids.clear()
        ext = self._extensions
        if isinstance(o, P):
            # an object of a cone that is a P is a custom or relation atom
            # (_kid maps vocabulary atoms to their argument)
            if o.pred in RELATION_ATOMS and self._relation_specs:
                r = kids[o] = (glue_objects(o, self._relation_specs, self._glue_adapters), 0)
                return r
            k = set()
            if ext is not None:
                for f in ext.facts_for(o):
                    k.update(_kid(a) for a in atoms_of(f))
                k.discard(o)
            r = kids[o] = (k, 0)
            return r
        constructing = self._constructing
        mine = o not in constructing
        if mine:
            constructing.add(o)                 # as Session.node does
        try:
            if self.clause_templates is not None:
                compiled, formulas = self.clause_templates(o)
            else:
                compiled, formulas = (), self.templates(o)
            if ext is not None and ext.has_node_facts:
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

    def _cone_info(self, d):
        """``(cone, weight, rel)`` for the cone object ``d``: its structural
        cone (``d`` and every object reachable through :meth:`_struct`'s
        kids) as a frozenset and its weight (the sum of the objects'
        weights) if that is at most ``discovery_budget``, else ``(None, w,
        rel)`` with ``w`` past the budget; ``rel``: the cone holds a relation
        atom (meaningful when it fits).  Memoized per engine."""
        cones = self._cones
        r = cones.get(d)
        if r is not None:
            return r
        budget = self._discovery_budget
        struct = self._struct
        seen = {d}
        stack = [d]
        total = 0
        rel = False
        over = False
        while stack:
            o = stack.pop()
            k, w = struct(o)
            total += w
            if type(o) is P and o.pred in RELATION_ATOMS:
                rel = True
            known = cones.get(o) if o is not d else None
            if known is not None:
                kc, _kw, krel = known
                if kc is None:
                    over = True                 # a sub-cone that does not fit
                    break
                rel = rel or krel
                # a known (closed) sub-cone: count its objects, no expansion
                for x in kc:
                    if x not in seen:
                        seen.add(x)
                        total += struct(x)[1]
            else:
                for x in k:
                    if x not in seen:
                        seen.add(x)
                        stack.append(x)
            if total > budget:
                over = True
                break
        r = (None, max(total, budget + 1), rel) if over else (frozenset(seen), total, rel)
        if len(cones) >= 100_000:
            cones.clear()
        cones[d] = r
        return r

    def _query_cone(self, f, link: bool):
        """``(cone, weight, rel, sums, zs)`` for a formula ``f`` (a query or an
        assumption set): the union of the cones of its atoms' objects
        (:func:`_kid`) and, with ``link`` (the session's relation glue
        runs), of the objects of the link of every vocabulary argument
        (``relations.link_objects``); cone None if it outweighs the budget.
        ``sums``: the sums under its sign atoms (``scope.affine_pair``);
        ``zs``: the arguments of its zero atoms (``relations.zero_args``).
        Memoized per engine."""
        key = (f, link)
        qc = self._qcones
        r = qc.get(key)
        if r is not None:
            return r
        atoms = atoms_of(f)
        # with the twins of f's zero atoms (relations.glue_atoms): their
        # glue is the session's, and they make the query relational (the
        # twins p and a call for only together: _within_budget)
        objs = {_kid(a) for a in (glue_atoms(atoms) if self._relation_specs else atoms)}
        if link:
            specs, memo = self._relation_specs, self._glue_adapters
            for a in atoms:
                if a.pred in PRED_INDEX:
                    objs |= link_objects(a.expr, specs, memo)
        sums = frozenset(a.expr for a in atoms if a.pred in _SIGN_PREDS
                         and getattr(a.expr, "is_Add", False)
                         and getattr(a.expr, "free_symbols", None))
        r = self._union(objs) + (sums, zero_args(atoms))
        if len(qc) >= 50_000:
            qc.clear()
        qc[key] = r
        return r

    def _union(self, objs):
        """``(cone, weight, rel)`` of the union of the cones of ``objs``
        (cone None if it outweighs the budget)."""
        budget = self._discovery_budget
        struct = self._struct
        cone = frozenset()
        weight = 0
        rel = False
        for o in objs:
            c, w, r = self._cone_info(o)
            if c is None:
                return None, w, r
            rel = rel or r
            if not cone:
                cone, weight = c, w
                continue
            new = c - cone
            if new:
                weight += w if len(new) == len(c) else sum(struct(x)[1] for x in new)
                if weight > budget:
                    return None, weight, rel
                cone = cone | new
        return cone, weight, rel

    def _within_budget(self, proposition, assumptions=None) -> bool:
        """The discovery budget's test (``discovery_budget``): whether the
        structural cone of the query, ``cone(proposition) |
        cone(assumptions)`` (assumptions None: a query without them),
        weighs at most the budget; with the links of the relation glue
        when the query's session runs it (a relation atom in the cone, or
        two sign atoms on sums, ``scope.affine_pair``; conservative).
        Decided from the structure alone, before any session work, so a
        function of the query, the registry and the settings: never of the
        sessions, the caches or earlier queries.  A query that passes runs
        discovery and escalation uncapped (never truncated): its session
        visits at most its cone."""
        _c, _w, rel, sums, zp = self._query_cone(proposition, False)
        cross = ()
        if assumptions is not None:
            _c, _w, rel_a, sums_a, za = self._query_cone(assumptions, False)
            rel = rel or rel_a
            sums = sums | sums_a
            if (zp or za) and self._relation_specs:
                # the twins of zero atoms only p and a together call for
                # (a zero(n) of a, n under an application of p:
                # Session._glue_of), which neither cone counts
                up, ua = under_of(atoms_of(proposition)), under_of(atoms_of(assumptions))
                cross = [zero_twin(e) for e in dict.fromkeys(zp + za)
                         if not (e in zp and e in up) and not (e in za and e in ua)
                         and (e in up or e in ua)]
                rel = rel or bool(cross)
        link = bool(self._relation_specs) and (rel or len(sums) >= 2)
        cp, wp, _r, _s, _z = self._query_cone(proposition, link)
        if cp is None:
            return False
        if assumptions is None:
            return True
        ca, wa, _r, _s, _z = self._query_cone(assumptions, link)
        if ca is None:
            return False
        if cross:
            cx, wx, _r = self._union({_kid(x) for x in cross})
            if cx is None:
                return False
            ca, wa = ca | cx, wa + wx
        if wp + wa <= self._discovery_budget:
            return True
        struct = self._struct
        return wp + sum(struct(x)[1] for x in ca if x not in cp) <= self._discovery_budget

    def _over_budget(self) -> None:
        """A query over the discovery budget: None, no session touched."""
        self.last_budget_limited = True
        self.stats["budget_limited"] += 1
        return None

    def _context_session(self, assumptions, proposition=None) -> Tuple[Session, List[int]]:
        """The session a contextual query within the budget is answered
        in, with its assumption literals: built for this query by
        :meth:`_build_context` and discarded by the caller (nothing is
        stored in ``_context_sessions``).  Raises ``Uninterpreted`` or
        ``InconsistentAssumptions`` as the construction does; both are
        functions of the set and the registry epoch, so they are memoized
        (``_failed``, ``_verdict``) and raised again without a build."""
        if self._epoch != _EPOCH[0]:
            self._check_version()
        if self._verdict.get(assumptions) is INCONSISTENT:
            # the construction below would raise this again (it is the same
            # every time, see _build_context); the memo only saves the work
            raise InconsistentAssumptions("inconsistent assumptions")
        s, lits = self._build_context_memoized(assumptions, proposition)
        if s.verdict is INCONSISTENT:
            raise InconsistentAssumptions("inconsistent assumptions")
        return s, lits

    def _build_context_memoized(self, assumptions, proposition=None) -> Tuple[Session, List[int]]:
        """:meth:`_build_context` behind the set's memos, for
        :meth:`_context_session` and :meth:`verdict`: a set whose
        construction raised ``Uninterpreted`` raises it again without a
        build (whether it does depends only on the assumptions' relation
        atoms and the registry epoch, which the caller has just compared);
        otherwise the set's verdict is recorded (``_verdict``)."""
        failed = self._failed
        msg = failed.get(assumptions)
        if msg is not None:
            raise Uninterpreted(msg)
        try:
            s, lits = self._build_context(assumptions, proposition)
        except Uninterpreted as e:
            if len(failed) >= 10_000:
                failed.clear()
            failed[assumptions] = str(e)
            raise
        verdicts = self._verdict
        if len(verdicts) >= 20_000:
            verdicts.clear()
        verdicts[assumptions] = s.verdict
        return s, lits

    def _build_context(self, assumptions, proposition=None) -> Tuple[Session, List[int]]:
        """Build the contextual session of ``assumptions`` and run the set's
        complete check (:meth:`_complete_check`) in it; its verdict is
        ``s.verdict``.  Every construction of a set's session (one per
        contextual query, and one per :meth:`verdict` without a memo)
        takes exactly these steps, whether a verdict is memoized or not,
        so the session a query uses never depends on what ran before.
        What the check leaves in the session (the escalated cone, learnt
        clauses, the branch and bound's lemmas) is a function of the set
        alone.

        If the check makes a theory give up (or errors), the session is
        replaced by a plain one (assumptions only, no check): a session
        whose theory gave up is useless to the queries (satassume.sat.theory,
        "Giving up"), and the plain build is just as deterministic."""
        self.stats["set_checks"] += 1
        # the theory scope of the query (``proposition`` None: of the set
        # alone); the set's check runs before the query's glue links the
        # set's terms (Session.link_set, below) and assumes only the set's
        # own glue, so its verdict is a function of the set whatever the
        # query's scope
        scope = theory_scope(assumptions, proposition, self._extensions)
        s = self._fresh_session(scope)
        lits = s.assume_formula(assumptions)
        try:
            v = self._complete_check(s, s.assumption_lits())
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
            s = self._fresh_session(scope)
            lits = s.assume_formula(assumptions)
            v = UNKNOWN
        s.verdict = v
        s.link_set()
        return s, lits

    def verdict(self, assumptions) -> str:
        """The verdict of the assumption set ``assumptions`` (a formula):
        ``CONSISTENT``, ``INCONSISTENT`` or ``UNKNOWN``, from the complete
        check (:meth:`_complete_check`) run when its contextual session is
        built; raises ``Uninterpreted`` as that construction does, never
        ``InconsistentAssumptions``.

        Answered from the verdict memo; else the session is built by
        :meth:`_build_context` and only its verdict is kept.  A query under
        the set builds its own session by the same steps (see
        :meth:`_build_context`), so what a query sees does not depend on
        whether a verdict was asked first.  The caller of a verdict is
        mostly the relevance layer deciding whether a set may raise before
        it answers under a part of it.  A set whose structural cone outweighs ``discovery_budget``
        is ``UNKNOWN`` without any session (every query under it is over
        the budget too: ``_within_budget``).  A set with a vocabulary atom
        about a non-commutative term is ``UNKNOWN`` (out of scope, as for
        :meth:`ask`: ``_noncommutative``)."""
        if self._epoch != _EPOCH[0]:
            self._check_version()
        if _noncommutative_atoms(assumptions):
            return UNKNOWN
        if not self._within_budget(assumptions):
            return UNKNOWN
        v = self._verdict.get(assumptions)
        if v is not None:
            return v
        return self._build_context_memoized(assumptions)[0].verdict

    @staticmethod
    def _complete_check(s: Session, lits: List[int]) -> str:
        """Whether the assumptions ``lits`` of the just-built session ``s``
        are consistent with the facts: the whole cone of the assumptions
        (derived nodes and parked clauses included), propagation, then
        search.  ``INCONSISTENT`` only on a conflict, which is sound even
        if a theory gave up afterwards (its earlier conflicts were valid,
        satassume.sat.theory); ``UNKNOWN`` if no conflict was found but a
        theory gave up or ran out of its branch budget (an integral
        conflict may be hidden), or the session is truncated (only with an
        explicit budget; a set over the discovery budget never gets here,
        see :meth:`verdict`; then a model of the clauses is no model of the
        set); ``CONSISTENT`` otherwise.  The session is kept either way:
        what the check left in it is a function of the set."""
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
        if s.sign_sync():
            if not solver.propagate() or solver.implied(lits) is None:
                return INCONSISTENT
        # Solver.solve returns a bool: it raises only on a malformed
        # literal or a theory protocol error (RuntimeError), neither of
        # which is a conflict; the caller maps them to UNKNOWN
        if not solver.solve(lits):
            return INCONSISTENT
        if _gave_up(s) or _exhausted(s) or s.incomplete or s.truncated:
            return UNKNOWN
        return CONSISTENT

    # -- context-free ---------------------------------------------------------
    def is_(self, node: Node, pred: str) -> Optional[bool]:
        """Context-free truth value of ``pred(node)``, memoized per node
        and registry epoch in ``cache`` (custom predicates: in
        ``custom_cache``), True or False only (``_put_result``).  None if
        the cone of ``node`` outweighs ``discovery_budget``
        (``last_budget_limited``), whatever is cached."""
        if self._epoch != _EPOCH[0] or self.cache._settings != self._settings_key:
            self._check_version()
        if pred not in PRED_INDEX:
            return self._is_custom(node, pred)
        if node in self._constructing:
            # re-entrant query from a template evaluating this very node
            return None
        if _noncommutative(node):
            return None
        c = self._cones.get(node)
        if c is None:
            c = self._cone_info(node)
        if c[0] is None:
            return self._over_budget()
        facts = self.cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            self.last_budget_limited = False
            return facts[pred]
        if not BASIS_OF[pred]:
            # true or false by definition (``commutative``): no session,
            # memoized as _put_result would
            self.last_budget_limited = False
            r = basis_lits(pred)[0] == '&'
            if self._writeback == "root-only":
                self.cache.put(node, pred, r)
            return r
        self.stats["queries"] += 1
        s = self._fresh_session()
        s.ensure(node, {pred})
        r = self._decide(s, s.query_lit(pred, node))
        self._put_result(s, self.cache, node, pred, r)
        return r

    def is_many(self, node: Node, preds: Sequence[str]) -> List[Optional[bool]]:
        """``[self.is_(node, p) for p in preds]``, with the built-in
        predicates not cached decided in one session that demands all of
        them instead of one session each.  Same answers and same cache
        contents (``_put_result``): see :meth:`_decide` for why the
        predicates a session demands do not change its answers."""
        if self._epoch != _EPOCH[0] or self.cache._settings != self._settings_key:
            self._check_version()
        out: List[Optional[bool]] = [None] * len(preds)
        todo = []
        noncomm = _noncommutative(node)
        for k, pred in enumerate(preds):
            if pred not in PRED_INDEX:
                out[k] = self._is_custom(node, pred)
            elif not noncomm:
                todo.append(k)
        if not todo or node in self._constructing:
            return out
        c = self._cones.get(node)
        if c is None:
            c = self._cone_info(node)
        if c[0] is None:
            for _ in todo:
                self._over_budget()
            return out
        facts = self.cache.facts(node)
        if facts is not None:
            left = []
            for k in todo:
                pred = preds[k]
                if pred in facts:
                    self.stats["cache_hits"] += 1
                    self.last_budget_limited = False
                    out[k] = facts[pred]
                else:
                    left.append(k)
            todo = left
        left = []
        for k in todo:
            if BASIS_OF[preds[k]]:
                left.append(k)
            else:
                # true or false by definition (``commutative``)
                self.last_budget_limited = False
                r = out[k] = basis_lits(preds[k])[0] == '&'
                if self._writeback == "root-only":
                    self.cache.put(node, preds[k], r)
        todo = left
        if not todo:
            return out
        self.stats["queries"] += len(todo)
        s = self._fresh_session()
        s.ensure(node, {preds[k] for k in todo})
        cache = self.cache
        for k in todo:
            pred = preds[k]
            r = out[k] = self._decide(s, s.query_lit(pred, node))
            self._put_result(s, cache, node, pred, r)
        return out

    def _decide(self, s: Session, lit: int, lits=()) -> Optional[bool]:
        """The context-free answer of the literal ``lit`` of a fresh
        session ``s`` (``is_``, ``is_many``, ``_is_custom``, which passes
        the selectors ``lits`` of the glue its atom activates): unit
        propagation; if that leaves it open and ``s`` is incomplete,
        propagation again after the escalation that instantiates the whole
        cone; then a complete search.

        Why ``is_many`` may decide several predicates of a node in one
        session, which demands all of them: an answer by propagation is
        an entailment of clauses of the node's cone, and a predicate
        still open after propagation (and after the escalation, if
        anything was parked) is decided by a complete search, so the
        answer is the verdict of the cone's clauses on that predicate
        whichever predicates the session demanded, and whatever the
        session learned deciding the others.  ``tests/
        test_transfer_numbers.py`` checks this against a loop of ``is_``
        under every harness preset."""
        s.sign_sync()
        r = s.query_literal(lit, lits, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.escalate()
            s.sign_sync()
            r = s.query_literal(lit, lits, search=False)
        if r is None and s.sign_sync(True):
            r = s.query_literal(lit, lits, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(lit, lits, search=True)
        return r

    def _put_result(self, s: Session, cache: DictCache, node, pred: str, r) -> None:
        """Memoize the answer ``r`` of the context-free query ``pred(node)``
        in ``cache``, keyed on ``node`` under the current registry epoch
        and settings fingerprint (``DictCache._epoch``, ``_settings``,
        ``_check_version``): True or False only, never None.

        Why the cache is a pure memo of ``is_``: ``s`` asserted no cached
        fact (sessions never read the caches), so its clause set depends
        on the node, the predicates it demands, the registry and the
        settings only (discovery, parking and escalation); ``s`` passed
        the budget test (``_within_budget``), ran uncapped and is never
        truncated, and its answer is an entailment of that clause set (or
        a complete search's verdict).  For ``is_`` that clause set is the
        one a fresh engine's ``is_(node, pred)`` builds, so the fresh
        query answers ``r`` too; for ``is_many``, whose session demands
        several predicates, the fresh query answers ``r`` by the argument
        in :meth:`_decide`.  Re-entrancy: the
        one input of ``s`` a fresh engine could see differently is the
        unmemoized None that ``is_`` answers for a node in
        ``_constructing`` (a template evaluating that very node asks about
        it), which a nested ``is_`` from relation glue inside ``s`` would
        receive if its cone reached an ancestor under construction; that
        needs a cycle through the templates, and no reachable case is
        known (issue #97 P2 review, N2), so this is accepted, not proved.
        Under
        ``writeback="none"`` nothing is stored."""
        if s.truncated:
            raise RuntimeError("a session of a query within the budget was truncated")
        self.last_budget_limited = False
        if r is None or self._writeback != "root-only":
            return
        cache.put(node, pred, r)

    def _is_custom(self, node: Node, pred: str) -> Optional[bool]:
        if self._epoch != _EPOCH[0] or self.custom_cache._settings != self._settings_key:
            self._check_version()
        atom = P(pred, node)
        if self._cone_info(atom)[0] is None:
            return self._over_budget()
        facts = self.custom_cache.facts(node)
        if facts is not None and pred in facts:
            self.stats["cache_hits"] += 1
            self.last_budget_limited = False
            return facts[pred]
        self.stats["queries"] += 1
        s = self._fresh_session(theory_scope(None, atom, self._extensions))
        lit = s.literal_of(atom)
        # under the glue a relation atom activates
        r = self._decide(s, lit, s.assumption_lits(atom))
        self._put_result(s, self.custom_cache, node, pred, r)
        return r

    # -- contextual -----------------------------------------------------------
    def ask(self, proposition, assumptions=None) -> Optional[bool]:
        """Truth value of ``proposition`` (a formula over ``P`` atoms) given
        ``assumptions`` (a formula or None).  Raises
        ``InconsistentAssumptions`` if the assumptions contradict the facts.

        Build, answer, discard: a contextual query is answered in the
        session of its set built for it (:meth:`_context_session`,
        :meth:`_build_context`), a context-free one in a fresh session; the
        session is dropped when the query ends, so a query's answer and
        cost depend on the query, the set and the registry, never on the
        queries before it (the module docstring).
        """
        if self._epoch != _EPOCH[0]:
            self._check_version()
        self.stats["queries"] += 1
        # never the previous query's flag, even if this one raises
        self.last_budget_limited = False
        lits: List[int] = []
        contextual = assumptions is not None and assumptions is not True
        if _noncommutative_atoms(proposition, assumptions if contextual else None):
            # out of scope (_noncommutative): None, never a raise
            return None
        if not self._within_budget(proposition, assumptions if contextual else None):
            # whether a set raises is a function of the set alone: one that
            # fits the budget and is INCONSISTENT raises for every query
            # under it, over the budget or not (a set over the budget is
            # UNKNOWN: never raises).  verdict() is memoized; it raises
            # Uninterpreted as the session construction of a query within
            # the budget would.
            if (contextual and self._within_budget(assumptions)
                    and self.verdict(assumptions) is INCONSISTENT):
                raise InconsistentAssumptions("inconsistent assumptions")
            return self._over_budget()
        if not contextual:
            # a predicate true or false by definition (``commutative``,
            # rules.DEFINITIONS) of a term: decided without a session,
            # after the budget test as in is_ (a query over the budget is
            # None for an atom and its negation alike)
            a = proposition.args[0] if isinstance(proposition, Not) else proposition
            c = basis_formula(a) if isinstance(a, P) else None
            if c is TRUE or c is FALSE:
                return (c is TRUE) != isinstance(proposition, Not)
        if contextual:
            s, lits = self._context_session(assumptions, proposition)
        else:
            s = self._fresh_session(theory_scope(None, proposition, self._extensions))
        return self._ask(s, lits, proposition, contextual)

    def _ask(self, s: Session, lits: List[int], proposition, contextual: bool) -> Optional[bool]:
        """Answer ``proposition`` in the session ``s`` just built for it:
        propagation, escalation of the query's cone if that was not
        enough, then search."""
        # the solver holds the levels of the set's check (the stable
        # prefix of the assumptions); release the others before this query
        # adds clauses
        s.solver.release(s.n_hold)
        q = s.prepare_query(proposition)
        # the set's selector and the selectors the query activates (also
        # for a context-free query)
        lits = s.assumption_lits(proposition)
        s.sign_sync()
        r = s.query_literal(q, lits, search=False)
        if r is None and s.incomplete:
            self.stats["escalations"] += 1
            s.solver.release(s.n_hold)
            s.escalate()
            s.sign_sync()
            r = s.query_literal(q, lits, search=False)
        if r is None and s.sign_sync(True):
            r = s.query_literal(q, lits, search=False)
        if r is None:
            self.stats["searches"] += 1
            r = s.query_literal(q, lits, search=True)
        if contextual and _gave_up(s):
            self.stats["theory_gave_up"] += 1
        self._note_budget(s)
        return r

    def _note_budget(self, s: Session) -> None:
        # the query passed _within_budget, so its session ran uncapped
        assert not s.truncated, "a session of a query within the budget was truncated"
        self.last_budget_limited = s.truncated
        if s.truncated:
            self.stats["budget_limited"] += 1


#: fewest derived atoms of several basis literals in an assumption set for
#: which asserted negations of them get their shared literals
_NEG_SHARED = 8


# --------------------------------------------------------------------------
# rule-base neighbourhood used by demand-driven instantiation
# --------------------------------------------------------------------------

_NEIGH: Dict[int, frozenset] = {}
_NO_BASIS: frozenset = frozenset()
_WANT: Dict[frozenset, frozenset] = {}
_adopt_memo(__name__, "_NEIGH")
_adopt_memo(__name__, "_WANT")


def _gave_up(s: Session) -> bool:
    """A theory of the session's solver gave up (satassume.sat.theory)."""
    for t in s.solver.theories():
        if getattr(t, "gave_up", False):
            return True
    return False


def _exhausted(s: Session) -> bool:
    """A theory of the session's solver ran out of its branch budget
    since the flag was last cleared (satassume.theories.lra.lra, "Integrality")."""
    for t in s.solver.theories():
        if getattr(t, "exhausted", False):
            return True
    return False


def neighbourhood(pred) -> frozenset:
    """``pred`` (a name or index) plus every predicate sharing a rule
    clause with it, as indices."""
    if isinstance(pred, str):
        acc = set()
        for i in BASIS_OF[pred]:
            acc.update(neighbourhood(i))
        return frozenset(acc)
    i = pred
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
_adopt_memo(__name__, "_SPLIT")


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
    """The demanded basis predicate indices, as the set a pattern clause
    must mention to be emitted before escalation.  (The union of their
    rule-base neighbourhoods, which the 33-predicate rule base used, is
    most of the basis: :func:`neighbourhood`.)"""
    key = frozenset(demanded)
    w = _WANT.get(key)
    if w is None:
        w = _WANT[key] = key
    return w

