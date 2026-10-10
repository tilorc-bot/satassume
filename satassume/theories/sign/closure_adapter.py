"""Session nodes onto :class:`.closure.ClosureTheory` (issue #149, T3).

As :mod:`.sign_adapter` (the shared :class:`.sign_adapter.ClassAdapter`):
a term is a session node with the seven closure basis variables of its
block registered as theory atoms, or an atomic number with a fixed atom
set read from its static ``is_*`` properties.  A ``Float`` is read for
``finite``, ``extended_real`` and ``zero`` only: SymPy calls ``2.0`` not
an integer, so its ring memberships are left open (no claim), as the
relation glue leaves Floats unread.  No SymPy import.
"""
from __future__ import annotations

from .closure import ALL, PRED_MASK, PREDS, ClosureTheory
from .sign_adapter import ClassAdapter

_FLOAT_READ = frozenset(("finite", "extended_real", "zero"))


def over_cap(node) -> bool:
    """Whether the closure rows of ``node`` (an Add or a Mul) are left to
    this theory (``templates.core.closure_owns``): the sums over
    ``MAX_ADD_SMALL`` terms, where the subtraction rows stop, and the
    products over ``MAX_PAIRS`` factors, where the field rows stop."""
    from ...knowledge.templates.core import closure_owns
    return closure_owns(bool(node.is_Mul), len(node.args))


class ClosureAdapter(ClassAdapter):
    THEORY = ClosureTheory
    PREDS = PREDS
    PRED_MASK = PRED_MASK
    ALL = ALL

    @staticmethod
    def over_cap(node) -> bool:
        return over_cap(node)

    @staticmethod
    def _const_fact(c, pred):
        if getattr(c, 'is_Float', False) and pred not in _FLOAT_READ:
            return None
        return getattr(c, 'is_' + pred, None)
