"""Session nodes onto :class:`.sign.SignTheory` (issue #149, T1 stage 1).

A term is a session node with the six sign basis variables of its block
registered as theory atoms (``mention=True``: the rule block writes them,
so ``prime(x)`` reaches the theory as ``extended_positive(x)``), or an
atomic number (``2``, ``pi``, ``I``, ``oo``, ``zoo``) with a fixed atom
set read from its static ``is_*`` properties.  No SymPy import: only the
attributes of the terms are read.
"""
from __future__ import annotations

from ...knowledge.rules import BASIS_INDEX
from .lattice import ADD, MUL
from .sign import ALL, PRED_MASK, PREDS, SignTheory


def over_cap(node) -> bool:
    """Whether the templates of ``node`` (an Add or a Mul) are capped:
    the sign rows of Mul stop at ``MAX_PAIRS`` factors (``negsets``), those
    of Add at ``MAX_ONEOUT`` terms (infinite sums).  Such nodes have no
    sign rows (``templates.core.sign_owns``): this theory decides them.
    A session engages the theory with these nodes only
    (``Session.node_theories_sync``; docs/theories.md, "SIGN", for the
    measured alternatives)."""
    from ...knowledge.templates.core import sign_owns
    return sign_owns(bool(node.is_Mul), len(node.args))


class ClassAdapter:
    """The theory of one session and the nodes it was told, for the
    lattice of :attr:`THEORY` whose predicates (basis predicates of the
    rule block) are :attr:`PREDS` with atom sets :attr:`PRED_MASK`.  A
    subclass names those and :meth:`over_cap`, the nodes a session tells
    it (``Session.node_theories_sync``)."""

    THEORY = SignTheory
    PREDS = PREDS
    PRED_MASK = PRED_MASK
    ALL = ALL
    #: read-only basis predicates and their atom sets (registered with
    #: payload ``(t, m, True)``; :mod:`.trans` only)
    ONESIDED: tuple = ()
    ONESIDED_MASK: tuple = ()
    #: whether registering a visited term compiles its parked rows about
    #: PREDS (the engine's demand-driven compilation)
    DEMAND = True
    #: whether a session tells this theory only the nodes :meth:`engages`
    #: takes under its class scope (``scope.class_symbols``; trans)
    GATED = False

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        cls._init_tables()

    @classmethod
    def _init_tables(cls) -> None:
        offs = tuple(BASIS_INDEX[p] for p in cls.PREDS)
        cls._OFFSETS = offs
        cls._ONESIDED = tuple((BASIS_INDEX[p], m) for p, m in zip(cls.ONESIDED, cls.ONESIDED_MASK))
        cls._DEMANDED = frozenset(offs) | frozenset(k for k, _ in cls._ONESIDED)
        #: 1-based basis index -> index in PREDS (-1: not one of them)
        cls._PIDX = tuple(offs.index(k - 1) if k - 1 in offs else -1
                          for k in range(max(BASIS_INDEX.values()) + 2))

    @staticmethod
    def over_cap(node) -> bool:
        return over_cap(node)

    @staticmethod
    def kinds(cls: type) -> bool:
        """Whether :meth:`selects` may take a node of type ``cls``."""
        return bool(getattr(cls, 'is_Add', False) or getattr(cls, 'is_Mul', False))

    @staticmethod
    def engages(node, classes: frozenset) -> bool:
        """For a ``GATED`` theory: whether a session with the class scope
        ``classes`` tells it ``node``."""
        return True

    @classmethod
    def selects(cls, node) -> bool:
        """Whether a session tells this theory ``node`` (``Session._visit``,
        ``ref._node_theories``): for the sums and products, those over the
        templates' arity caps (:meth:`over_cap`)."""
        return ((getattr(node, 'is_Add', False) or getattr(node, 'is_Mul', False))
                and bool(node.args) and cls.over_cap(node))

    @classmethod
    def const_mask(cls, c) -> int:
        """The atom set of an atomic number from its static ``is_*`` facts."""
        m = cls.ALL
        for p, pred in enumerate(cls.PREDS):
            v = cls._const_fact(c, pred)
            if v is True:
                m &= cls.PRED_MASK[p]
            elif v is False:
                m &= ~cls.PRED_MASK[p]
        return m

    @staticmethod
    def _const_fact(c, pred):
        return getattr(c, 'is_' + pred, None)

    @classmethod
    def def_mask(cls, d):
        """The atom set of a derived definition ``d = (op, lits)`` (signed
        1-based basis indices, ``rules.DEF_LITS``), or None if it reads a
        basis predicate outside :attr:`PREDS`."""
        op, ls = d
        full, pidx, pmask = cls.ALL, cls._PIDX, cls.PRED_MASK
        m = full if op == '&' else 0
        for l in ls:
            p = pidx[abs(l)] if abs(l) < len(pidx) else -1
            if p < 0:
                return None
            pm = pmask[p] if l > 0 else full & ~pmask[p]
            m = m & pm if op == '&' else m | pm
        return m

    def __init__(self, session):
        self.session = session
        self.theory = self.THEORY()
        session.solver.attach_theory(self.theory)
        self.terms = {}
        self.done = set()
        self._ndv = 0           # Session._dv entries seen by sync_derived
        self._later = []        # those of nodes not yet terms

    def term(self, e) -> int:
        t = self.terms.get(e)
        if t is not None:
            return t
        th = self.theory
        if e.is_Atom and e.is_number:
            t = self.terms[e] = th.term(self.const_mask(e))
            return t
        t = self.terms[e] = th.term()
        s = self.session
        if e in s.base and not self.DEMAND:
            # visited; rows about these predicates that are parked stay
            # parked (compiled by the escalation if the query needs them)
            b = s.base[e]
        elif e in s.base and hasattr(s, 'demand'):
            # visited, maybe with the rows about these predicates parked
            # (the engine's demand-driven compilation): compile them now
            b = s.node(e, self._DEMANDED)
        else:
            b = s.node(e)
        solver = s.solver
        pmask = self.PRED_MASK
        for p, k in enumerate(self._OFFSETS):
            solver.register_atom(th, b + k, (t, pmask[p]))
        if e in self.oneside_terms:
            self._oneside(b, t)
        return t

    #: the terms that get the read-only atoms (:attr:`ONESIDED`)
    oneside_terms: frozenset = frozenset()

    def _oneside(self, b: int, t: int) -> None:
        """Register the read-only atoms of term ``t`` (base variable ``b``):
        never decided by the search for the theory's sake."""
        th, solver = self.theory, self.session.solver
        for k, m in self._ONESIDED:
            solver.register_atom(th, b + k, (t, m, True), mention=False)

    def sync_derived(self) -> None:
        """Register the derived atoms of the terms (``Session._dv``:
        ``negative_infinite(x)``, ``nonzero(x)``, ...) created since the
        last call, whose definitions are over the six predicates: the
        theory reads and writes them as one literal each, so a reason (and
        the clause learnt from it) can say ``~negative_infinite(x)``
        where the basis literals need two cases (``finite(x)`` or
        ``~extended_negative(x)``).  Their definitions are completed to
        both directions first (``Session._dvar``), so the variable is the
        definition."""
        s = self.session
        dv = getattr(s, '_dv', None)    # (ref.py's session has none)
        if dv is None:
            return
        if len(dv) == self._ndv and not self._later:
            return
        keys = self._later + list(dv)[self._ndv:]
        self._ndv = len(dv)
        self._later = []
        th, solver, terms = self.theory, s.solver, self.terms
        for key in keys:
            d, node = key
            t = terms.get(node)
            if t is None:
                self._later.append(key)
                continue
            m = self.def_mask(d)
            if m is not None:
                solver.register_atom(th, s._dvar(d, node, 3), (t, m), mention=False)

    def add(self, node) -> None:
        """Tell the theory the sum or product ``node``."""
        if node in self.done:
            return
        self.done.add(node)
        t = self.term(node)
        args = [self.term(a) for a in node.args]
        self.theory.add_node(ADD if node.is_Add else MUL, t, args)


ClassAdapter._init_tables()


class SignAdapter(ClassAdapter):
    """The sign theory (:mod:`.sign`)."""


const_mask = SignAdapter.const_mask
def_mask = SignAdapter.def_mask
