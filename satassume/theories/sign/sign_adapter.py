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

#: When a session engages the theory (``Session.sign_sync``): ``'cap'``
#: only when its cone holds a sum or product over the arity caps of the
#: templates; ``'escalate'`` also for every query that propagation (and
#: escalation) left open, before the search; ``'always'`` whenever the
#: cone holds a sum or product; ``'off'`` never.
ENGAGE = 'escalate'


def over_cap(node) -> bool:
    """Whether the templates of ``node`` (an Add or a Mul) are capped:
    the sign rows of Mul stop at ``MAX_PAIRS`` factors (``negsets``), those
    of Add at ``MAX_ONEOUT`` terms (infinite sums)."""
    from ...knowledge.templates.core import MAX_ONEOUT, MAX_PAIRS
    return len(node.args) > (MAX_PAIRS if node.is_Mul else MAX_ONEOUT)


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


class SignAdapter:
    """The theory of one session and the nodes it was told."""

    def __init__(self, session):
        self.session = session
        self.theory = SignTheory()
        session.solver.attach_theory(self.theory)
        self.terms = {}
        self.done = set()

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
            solver.register_atom(th, b + k, (t, p))
        return t

    def add(self, node) -> None:
        """Tell the theory the sum or product ``node``."""
        if node in self.done:
            return
        self.done.add(node)
        t = self.term(node)
        args = [self.term(a) for a in node.args]
        self.theory.add_node(ADD if node.is_Add else MUL, t, args)
