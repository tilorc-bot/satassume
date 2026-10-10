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
from .sign import ADD, ALL, MUL, PRED_MASK, PREDS, SignTheory

_OFFSETS = tuple(BASIS_INDEX[p] for p in PREDS)

#: When a session engages the theory, and with which nodes
#: (``Session.sign_sync``): ``'cap'`` (the default) once its cone holds a
#: sum or product over the arity caps of the templates, with those nodes
#: only; ``'escalate'`` also, with every sum and product, for each query
#: that propagation (and escalation) left open, before the search;
#: ``'always'`` with every sum and product from the start; ``'off'``
#: never.  On the refine stream 'escalate' adds no answer and costs +29%
#: (``tools/ab.py``), 'cap' +0.4% (docs/theories.md, "SIGN").
ENGAGE = 'cap'


def over_cap(node) -> bool:
    """Whether the templates of ``node`` (an Add or a Mul) are capped:
    the sign rows of Mul stop at ``MAX_PAIRS`` factors (``negsets``), those
    of Add at ``MAX_ONEOUT`` terms (infinite sums).  Such nodes have no
    sign rows (``templates.core.sign_owns``): this theory decides them."""
    from ...knowledge.templates.core import sign_owns
    return sign_owns(bool(node.is_Mul), len(node.args))


def const_mask(c) -> int:
    """The atom set of an atomic number from its static ``is_*`` facts."""
    m = ALL
    for p, pred in enumerate(PREDS):
        v = getattr(c, 'is_' + pred, None)
        if v is True:
            m &= PRED_MASK[p]
        elif v is False:
            m &= ~PRED_MASK[p]
    return m


#: 1-based basis index -> index in PREDS (-1: not one of them)
_PIDX = tuple(_OFFSETS.index(k - 1) if k - 1 in _OFFSETS else -1
              for k in range(max(_OFFSETS) + 2))


def def_mask(d):
    """The atom set of a derived definition ``d = (op, lits)`` (signed
    1-based basis indices, ``rules.DEF_LITS``), or None if it reads a
    basis predicate other than the six."""
    op, ls = d
    m = ALL if op == '&' else 0
    for l in ls:
        p = _PIDX[abs(l)] if abs(l) < len(_PIDX) else -1
        if p < 0:
            return None
        pm = PRED_MASK[p] if l > 0 else ALL & ~PRED_MASK[p]
        m = m & pm if op == '&' else m | pm
    return m


class SignAdapter:
    """The theory of one session and the nodes it was told."""

    def __init__(self, session):
        self.session = session
        self.theory = SignTheory()
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
            t = self.terms[e] = th.term(const_mask(e))
            return t
        t = self.terms[e] = th.term()
        s = self.session
        b = s.node(e)
        solver = s.solver
        for p, k in enumerate(_OFFSETS):
            solver.register_atom(th, b + k, (t, PRED_MASK[p]))
        return t

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
            m = def_mask(d)
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
