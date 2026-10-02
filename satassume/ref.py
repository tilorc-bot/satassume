"""``ask_ref``: the reference implementation of ``docs/spec.md``.

``ask_ref(p, A, extensions)`` answers a query exactly as the specification
defines it, as one function of the query and the registry: the whole clause
set of ``cone(p) | cone(A)`` is built eagerly (no demand-driven parking, no
deferred derived nodes, no fact or answer memo, no budget), in one fresh
solver, and the answer is one complete entailment check.  The one memo is
``_RefEngine._is_memo``, the nested context-free queries of section 9,
created per ``ask_ref`` call: no state crosses calls.  It is the
session-independent clause set the harness compares the engine against
(spec, open point 4).  It uses neither ``satassume.engine.Engine`` nor
``satassume.engine.Session``; the relation glue (``satassume.relations``)
is driven through a small stand-in object that offers only what the glue
reads of a session.

Which spec section each function implements:

* section 1 (routing: constant route, translation, ``TRUE``/``FALSE``,
  ``Unsupported``, inconsistent ``A``): :func:`ask_ref`, :func:`_routed`.
  SPEC-DIFF (1.2, 9.3): a constant proposition the constant's facts leave
  None is answered under ``A`` as ``sympy_api._ask`` does (family C), so
  an inconsistent set raises for it; the spec's "``A`` is ignored" is
  older than that (P5b-fix2 report).  The relevance
  split (1.3, section 7) is *not* applied: ``ask_ref`` answers under the
  whole of ``A``, which by monotonicity is the same as or more definite
  than the engine's answer under the relevant part, and raises exactly
  when the whole set is inconsistent (which is what certification decides
  in the engine too): raising is a property of the set, decided even when
  ``p`` carries an uninterpreted relation (``Uninterpreted`` gives None
  only after the set's verdict).
* section 2 (translation): :func:`_translate`, through
  ``sympy_api._formula`` / ``to_formula`` and ``relations.relation_atom``.
* section 3 (theory scope, P3's syntactic definition): :func:`theory_scope`,
  over the glue atoms of ``A`` and ``p`` (:func:`_glue_atoms_of`): a
  ``zero(t)`` whose ``t`` is under an application of ``A`` or ``p`` counts
  as its twin ``eq(t, 0)`` (``relations.glue_atoms``, PR #107).
* section 4 (the node cone): the eager closure of :meth:`_RefSession.node`
  over the frontier (:meth:`_RefSession._discover`); derived nodes are
  visited like direct arguments.  No separate cone computation is needed:
  the visited nodes *are* ``cone(p) | cone(A)`` (plus the glue's link
  objects when ``glue`` holds).
* section 5.1 (rule base per node) and 5.2 (template clauses per node):
  :meth:`_RefSession._visit`, :meth:`_RefSession._emit_pattern`,
  :meth:`_RefSession._compile`.  Nothing is parked.
* section 5.3 (cached unit facts): deliberately absent.  The spec's
  property says they change no answer; ``ask_ref`` is what that property
  is checked against.
* section 5.4 (the assumption selector): :meth:`_RefSession.assume_formula`.
* section 5.5 (glue and theory clauses): :meth:`_RefSession.glue` and
  :func:`_assumption_lits` (which selectors the one query assumes).
* section 5.6 (custom atoms): :meth:`_RefSession._custom` (no custom
  cache; the registered functions' formulas only).
* section 6 (the literal of ``p``): :meth:`_RefSession.literal_of`.
* section 8 (the answer as entailment): :func:`_answer`.
* section 9 (undecidable constants): nothing to implement here, the
  templates and theories do it; :meth:`_RefEngine.is_` gives the glue the
  context-free facts of a closed side (``Relations._closed_extended_real``,
  ``_number_basis``) by a nested context-free reference query;
  ``_RefEngine.is_`` gives None where that query's set is inconsistent
  (``Engine.is_`` lets the conflict propagate; reachable only with a
  contradicting extension fact on a closed term).
* section 8's "at most two searches" is design.md's wording;
  ``Solver.entails`` runs up to two searches plus a witness check (no
  effect on the answer).
* section 10 (budgets): not applied, by design.

Where the spec says today's code differs from the definition implemented
here (section 3, open point 1), the difference is marked ``SPEC-DIFF`` in
the code and listed in the P5b report.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .compile import VarTable, compile_formula, formula_literal
from .formula import FALSE, P, TRUE, atoms_of
from .relations import RELATION_ATOMS, Relations, Uninterpreted, _is_number, glue_atoms
from .rules import NPRED, PRED_INDEX, RULE_INTERNAL
from .solver import Solver

__all__ = ["ask_ref", "ref_outcome", "theory_scope", "RefInfo"]

#: the sign predicates whose atoms on sums start the glue (engine._SIGN_PREDS)
_SIGN_PREDS = frozenset({
    "positive", "negative", "nonnegative", "nonpositive", "nonzero", "zero",
    "extended_positive", "extended_negative", "extended_nonnegative",
    "extended_nonpositive", "extended_nonzero"})


class RefInfo:
    """What one :func:`ask_ref` call built (for tools and tests): pass a
    fresh one as ``info=`` and read it afterwards.  No module-level state
    keeps the last one (``harness.state`` inventories module containers)."""
    __slots__ = ("nodes", "clauses", "scope", "gave_up", "exhausted",
                 "undecidable", "route", "searched")

    def __init__(self) -> None:
        self.nodes = 0
        self.clauses = 0
        self.scope: Tuple[bool, bool, frozenset] = (False, False, frozenset())
        self.gave_up = False
        self.exhausted = False
        self.undecidable = False
        self.route = ""
        self.searched = False

    def __repr__(self) -> str:
        g, t, linked = self.scope
        return (f"RefInfo(route={self.route}, nodes={self.nodes}, clauses={self.clauses}, "
                f"scope=({g}, {t}, {len(linked)} terms), gave_up={self.gave_up}, "
                f"exhausted={self.exhausted}, undecidable={self.undecidable})")


# --------------------------------------------------------------------------
# section 3: theory scope
# --------------------------------------------------------------------------

def theory_scope(a_atoms, p_atoms) -> Tuple[bool, bool, frozenset]:
    """``(glue, transfer, linked_terms)`` of the atoms of ``A`` and ``p``
    (spec section 3, P3's definition):

    * ``glue`` iff a relation atom occurs, or two sign atoms (of ``A`` and
      ``p`` together) are on different ``Add`` nodes sharing a free symbol;
    * ``transfer`` iff an ``eq`` atom occurs;
    * ``linked_terms``: the arguments of the vocabulary atoms and the
      sides of the relation atoms, numbers excluded.

    SPEC-DIFF (open point 1): the engine's ``Relations.wants_transfer``
    also counts an order atom whose reverse ``_trichotomy`` paired; the
    budget's link test counts two sign-atom sums over disjoint symbols.
    Neither is counted here."""
    atoms = tuple(a_atoms) + tuple(p_atoms)
    glue = False
    transfer = False
    linked = set()
    sums: Dict[Any, frozenset] = {}
    for a in atoms:
        if a.pred in RELATION_ATOMS:
            glue = True
            if a.pred == "eq":
                transfer = True
            for e in a.expr:
                if not _is_number(e):
                    linked.add(e)
        elif a.pred in PRED_INDEX:
            e = a.expr
            if not _is_number(e):
                linked.add(e)
            if a.pred in _SIGN_PREDS and getattr(e, "is_Add", False) and e not in sums:
                symbols = getattr(e, "free_symbols", frozenset())
                if symbols:
                    if any(symbols & other for other in sums.values()):
                        glue = True
                    sums[e] = frozenset(symbols)
    return glue, transfer, frozenset(linked)


# --------------------------------------------------------------------------
# the stand-ins: what the relation glue reads of an engine and a session
# --------------------------------------------------------------------------

class _RefEngine:
    """The settings the glue reads of an engine (``s.engine.transfer``,
    ``s.engine.uninterpreted``), its memo dict (``_number_basis`` keeps
    ``_xbasis`` in ``engine.__dict__``) and ``is_`` for context-free facts
    of closed terms (spec section 9), answered by a nested reference query
    with no assumptions and no glue."""

    def __init__(self, extensions, specs, transfer: bool, uninterpreted: str) -> None:
        self._extensions = extensions
        self._relation_specs = tuple(specs)
        self.transfer = transfer
        self.uninterpreted = uninterpreted
        self._is_memo: Dict[Tuple[Any, str], Optional[bool]] = {}

    def is_(self, node, pred: str) -> Optional[bool]:
        key = (node, pred)
        memo = self._is_memo
        if key in memo:
            return memo[key]
        s = _RefSession(self)
        q = s.literal_of(P(pred, node))
        s._discover()
        try:
            r = _entails(s, q, [])
        except ValueError:
            r = None
        memo[key] = r
        return r


class _RefSession:
    """One eager clause set.  Not ``satassume.engine.Session``: it holds a
    solver, a variable table and the visited nodes, and offers the glue
    (``Relations``) what it calls on a session.  Every node is visited
    whole (all its patterns and formulas, section 5.1 and 5.2) and every
    node a template or the glue mentions is visited too (section 4)."""

    def __init__(self, engine: _RefEngine) -> None:
        self.engine = engine
        self.solver = Solver()
        self.solver.set_rule_block(RULE_INTERNAL, NPRED)
        self.table = VarTable()
        self.base: Dict[Any, int] = {}
        self.nclauses = 0
        self.frontier: List[Any] = []
        self.relations: Optional[Relations] = None
        self.xfer = None                 # Relations sets it when transfer engages
        self.sel = 0
        self.literals: Dict[Any, int] = {}
        self._visiting: set = set()

    # -- what Relations calls -------------------------------------------
    def _emit(self, clause: List[int]) -> None:
        self.nclauses += 1
        self.solver.add_clause(clause)

    def var(self, pred: str, node) -> int:
        return self.node(node) + PRED_INDEX[pred]

    def ensure(self, node, demanded=None, budget=None) -> None:
        self.node(node)

    def _flush(self) -> None:
        """Run the clause generators of newly allocated custom atoms and
        schedule newly mentioned nodes (section 5.6, section 4)."""
        table = self.table
        while table.new_custom:
            atoms, table.new_custom = table.new_custom, []
            for atom in atoms:
                self._custom(atom)
        if table.new_nodes:
            self.frontier.extend(n for n in table.new_nodes if n not in self.base)
            table.new_nodes = []

    def _discover(self) -> None:
        """Visit everything on the frontier until the cone is closed."""
        self._flush()
        while self.frontier:
            n = self.frontier.pop()
            if n not in self.base:
                self.node(n)
            self._flush()

    # -- section 4 and 5: nodes and their clauses ---------------------------
    def node(self, node) -> int:
        b = self.base.get(node)
        if b is not None:
            return b
        b = self.table.node_base(node)
        self.base[node] = b
        self._visit(node, b)
        return b

    def _visit(self, node, b: int) -> None:
        from .templates import registry
        # 5.2: the templates of the node's class, and the vocabulary
        # extensions registered for the class
        compiled, formulas = registry.clauses_for(node)
        ext = self.engine._extensions
        if ext is not None:
            nf = ext.node_facts(node)
            if nf:
                formulas = list(formulas) + nf
        # 5.1: the rule base, unless a complete unit pattern decides it all
        if not (len(compiled) == 1 and compiled[0].pattern.complete and not formulas):
            own = 0
            for comp in compiled:
                k0 = comp.pattern.node
                for _, _, li in comp.pattern.clauses:
                    for k, off in li:
                        if k == k0:
                            own |= 3 << (off & ~1)
            self.solver.register_block(b, own)
        else:
            self.solver.ensure_vars(b + NPRED - 1)
        # 5.2: every clause of every pattern, now; derived nodes are visited
        # like direct arguments (section 4: "kids whatever holds")
        for comp in compiled:
            self._emit_pattern(comp)
        if formulas:
            self._compile(formulas)
        self._flush()

    def _emit_pattern(self, comp) -> None:
        table = self.table
        objs, pat = comp.objs, comp.pattern
        bases = [0] * len(objs)
        for k in pat.used:
            bases[k] = 2 * table.node_base(objs[k])
        acc: Dict[int, int] = {}
        clauses = []
        for _, _, li in pat.clauses:
            clauses.append([bases[k] + off for k, off in li])
            for k, off in li:
                acc[k] = acc.get(k, 0) | (3 << (off & ~1))
        self.nclauses += len(clauses)
        solver = self.solver
        solver.ensure_vars(len(table))
        solver.add_internal(clauses, [(bases[k] >> 1, m) for k, m in acc.items()])

    def _compile(self, formulas) -> None:
        for f in formulas:
            compile_formula(f, self.table, self._emit)

    def _custom(self, atom: P) -> None:
        """A custom atom was allocated: a relation atom goes to the glue
        when the scope has one (5.5); any other gets the formulas of its
        registered functions (5.6)."""
        if atom.pred in RELATION_ATOMS:
            if self.relations is not None:
                self.relations.enqueue(atom)
            # SPEC-DIFF (open point 2): without ``glue`` in the scope a
            # relation atom a template or extension made stays a free
            # Boolean here; the engine creates the glue for it and keeps it
            # inert by selectors.
            return
        ext = self.engine._extensions
        if ext is None:
            return
        for f in ext.facts_for(atom):
            compile_formula(f, self.table, self._emit)

    # -- section 5.4 and 6: the assumptions and the literal ------------------
    def assume_formula(self, f) -> List[int]:
        for atom in atoms_of(f):
            if atom.pred in PRED_INDEX:
                self.node(atom.expr)
        s = self.table.aux()
        self.sel = s

        def emit(clause):
            self._emit(clause + [-s])
        compile_formula(f, self.table, emit)
        self._discover()
        return [s]

    def literal_of(self, f) -> int:
        lit = self.literals.get(f)
        if lit is not None:
            return lit
        if isinstance(f, P) and f.pred in PRED_INDEX:
            lit = self.node(f.expr) + PRED_INDEX[f.pred]
        else:
            for atom in atoms_of(f):
                if atom.pred in PRED_INDEX:
                    self.node(atom.expr)
            lit = formula_literal(f, self.table, self._emit)
        self._discover()
        self.literals[f] = lit
        return lit

    # -- section 5.5: the glue ----------------------------------------------
    def glue(self, a_atoms, p_atoms) -> Relations:
        """Create the glue for the scope ``glue = True`` and process the
        user atoms of ``A`` and ``p``: links of every vocabulary argument,
        interpretation of every relation atom, shared equalities, transfer
        when an equality engages it."""
        rel = self.relations
        if rel is None:
            rel = self.relations = Relations(self, self.engine._relation_specs)
            rel.active = True
            # relation atoms allocated before the glue existed
            for atom in list(self.table.custom):
                if atom.pred in RELATION_ATOMS and atom not in rel.status:
                    rel.enqueue(atom)
        atoms = tuple(a_atoms) + tuple(p_atoms)
        rel.note_formula(atoms)
        rel.process(atoms)
        self._discover()
        # the glue may have visited nodes whose templates made relation
        # atoms: interpret them too, until nothing is queued
        while rel.queue or rel._pending_links or self.frontier:
            rel.process(())
            self._discover()
        return rel


# --------------------------------------------------------------------------
# section 1, 2: routing and translation
# --------------------------------------------------------------------------

def _translate(p, A, rel: bool):
    """``(prop, assum)`` formulas of a SymPy ``p`` and ``A`` (section 2);
    ``assum`` None when ``A`` is ``True``; raises ``Unsupported`` as
    ``sympy_api._formula`` does."""
    from .sympy_api import _formula
    prop = _formula(p, rel)
    assum = None if A is True else _formula(A, rel, True)
    return prop, assum


def _assumption_lits(s: _RefSession, rel: Optional[Relations], atoms, transfer: bool) -> List[int]:
    """The literals the one query assumes (section 5.4, 5.5): the
    selector of ``A``, the selectors of the links and relation atoms of
    ``A`` and ``p``, and transfer's selector when ``transfer`` holds."""
    lits = [s.sel] if s.sel else []
    if rel is None:
        return lits
    lits.extend(rel.selectors_of(atoms))
    if transfer and rel.xfer_sel is not None:
        lits.append(rel.xfer_sel)
    return lits


def _entails(s: _RefSession, q: int, lits: List[int]) -> Optional[bool]:
    """Section 8: ``C & L |= q``, ``C & L |= ~q`` or neither; raises
    ``ValueError`` when ``C & L`` is unsatisfiable."""
    solver = s.solver
    if s.xfer is not None:
        s.xfer.sync_transfer()
    elif s.relations is not None and s.relations.xfer is not None:
        s.relations.sync_transfer()
    if not solver.propagate():
        raise ValueError("inconsistent assumptions")
    return solver.entails(q, lits)


def _glue_atoms_of(a_atoms, p_atoms, rel: bool) -> Tuple[tuple, tuple]:
    """The atoms the scope and the glue read ``A`` and ``p`` by (section 3,
    5.5; ``relations.glue_atoms``, PR #107): each formula's atoms followed
    by the twins ``eq(t, 0)`` of the ``zero(t)`` atoms (``t`` no number) of
    ``A`` and ``p`` whose ``t`` is under an application of an undefined
    function in ``A`` or ``p``.  ``A``'s twins are those of ``A`` alone
    (``Session.assumption_lits``); ``p``'s are those of the pair
    (``Session._glue_of``).  Without relation specs nothing is read."""
    a_atoms, p_atoms = tuple(a_atoms), tuple(p_atoms)
    if not rel:
        return a_atoms, p_atoms
    return glue_atoms(a_atoms), glue_atoms(p_atoms, a_atoms)


def _answer(prop, assum, engine: _RefEngine, info: RefInfo) -> Optional[bool]:
    """Sections 3 to 8 for translated formulas."""
    a_atoms = atoms_of(assum) if assum is not None else ()
    p_atoms = atoms_of(prop)
    # section 3 over the glue atoms: a twin is an eq atom, so it gives
    # glue and transfer and links t, as Q.eq(t, 0) in the formula would
    a_atoms, p_atoms = _glue_atoms_of(a_atoms, p_atoms, bool(engine._relation_specs))
    glue, transfer, linked = theory_scope(a_atoms, p_atoms)
    if not engine._relation_specs:
        glue = transfer = False
    info.scope = (glue, transfer, linked)
    s = _RefSession(engine)
    if glue:
        # created first, so that relation atoms are queued as they are
        # allocated (Session._custom does the same)
        s.relations = Relations(s, engine._relation_specs)
        s.relations.active = True
        # the twins are atoms of no compiled formula: allocated here, as
        # Session._ensure_twins does, so that 5.5 processes them as user
        # equalities of their formula (the link clause zero(t) <-> eq(t, 0)
        # of t ties each to its zero atom)
        for atom in a_atoms + p_atoms:
            if atom.pred in RELATION_ATOMS and atom not in s.table.custom:
                s.table.var(atom)
        s._flush()
    if assum is not None:
        s.assume_formula(assum)
    q = s.literal_of(prop)
    rel = None
    if glue:
        rel = s.glue(a_atoms, p_atoms)
    s._discover()
    lits = _assumption_lits(s, rel, a_atoms + p_atoms, transfer)
    info.nodes = len(s.base)
    info.clauses = s.nclauses
    try:
        r = _entails(s, q, lits)
    finally:
        theories = s.solver._theories
        info.gave_up = any(getattr(t, "gave_up", False) for t in theories)
        info.exhausted = any(getattr(t, "exhausted", False) for t in theories)
        info.undecidable = any(getattr(t, "undecidable", False) for t in theories)
    return r


def ask_ref(p, A=True, extensions=None, *, relations=None, transfer: bool = True,
            uninterpreted: str = "free", info: Optional[RefInfo] = None) -> Optional[bool]:
    """The specification's answer to ``ask(p, A)``: ``True``, ``False`` or
    ``None``; raises ``ValueError`` for inconsistent assumptions, like
    ``satassume.sympy_api.ask`` (section 1).

    ``p`` and ``A`` are SymPy Booleans (``A`` may be ``True``).
    ``extensions``: the :class:`satassume.extensions.Extensions` registry
    whose registrations are in force (default: the global one the engine
    uses, so the harness's register/unregister events apply).
    ``relations``: the adapter specs (default: ``relations.default_specs()``,
    the default engine's); ``transfer`` and ``uninterpreted`` as the
    engine settings of the same names.  ``info``: a :class:`RefInfo` to
    fill with what the call built (route, nodes, clauses, scope, theory
    flags)."""
    from .sympy_api import Unsupported, _is_constant_proposition
    if info is None:
        info = RefInfo()
    if extensions is None:
        from .extensions import extensions as _ext
        extensions = _ext
    if relations is None:
        from .relations import default_specs
        relations = default_specs()
    from . import templates as _templates        # noqa: F401 (registers the templates)
    engine = _RefEngine(extensions, relations, transfer, uninterpreted)
    rel = bool(engine._relation_specs)
    # 1.2: a constant proposition is answered without the assumptions; one
    # the constant's facts do not decide is then answered under them like
    # any other (sympy_api._ask, nightly family C: the set's verdict counts,
    # so an inconsistent set raises).  SPEC-DIFF: section 1.2 says "A is
    # ignored", which is _ask before family C; P5b-fix2 report.
    if _is_constant_proposition(p):
        info.route = "constant"
        r = _routed(p, True, engine, rel, info)
        if r is not None or A is True:
            return r
        info.route = "constant+set"
    else:
        info.route = "engine"
    return _routed(p, A, engine, rel, info)


def _routed(p, A, engine: _RefEngine, rel: bool, info: RefInfo) -> Optional[bool]:
    """Sections 1.4 to 8 for a routed ``(p, A)``."""
    from .sympy_api import Unsupported
    # 1.4 and section 2: translation
    try:
        prop, assum = _translate(p, A, rel)
    except Unsupported:
        return None
    if prop is TRUE:
        return True
    if prop is FALSE:
        return False
    if assum is TRUE:
        assum = None
    if assum is FALSE:
        raise ValueError("inconsistent assumptions")
    try:
        return _answer(prop, assum, engine, info)
    except Uninterpreted:
        # 1.4, 7, 10 rule 1: raising is the set's verdict, independent of
        # ``p``.  ``FALSE``'s literal under ``s`` is forced false, so this
        # raises exactly when ``C(A) & s`` is unsat and returns False otherwise.
        if assum is not None:
            try:
                _answer(FALSE, assum, engine, RefInfo())
            except Uninterpreted:
                pass                # UNKNOWN, as the engine's verdict
        return None


def ref_outcome(prop, assum=True, extensions=None, **settings) -> str:
    """:func:`ask_ref` in the string form of ``harness.outcomes.outcome``:
    ``"True"``, ``"False"``, ``"None"``, ``"ValueError"`` or
    ``"Error:<Type>"``."""
    try:
        r = ask_ref(prop, assum, extensions, **settings)
    except ValueError:
        return "ValueError"
    except RecursionError:
        return "Error:RecursionError"
    except Exception as e:  # noqa: BLE001 - any other exception is a defect
        return f"Error:{type(e).__name__}"
    if r is True:
        return "True"
    if r is False:
        return "False"
    if r is None:
        return "None"
    return f"Value:{r!r}"
