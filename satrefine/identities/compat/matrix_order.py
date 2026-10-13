"""SymPy's canonical index order of a matrix element, as a condition a row can carry.

``A[i, j] -> A[j, i]`` for a symmetric ``A`` must only go towards SymPy's
canonical order (the one ``refine_matrixelement`` uses), or the row would swap
the indices back and forth.  The order is a property of how the indices are
written, not of their values, so ``ask`` cannot decide it; :class:`_SwappedOrder`
decides it itself once the row's indices are bound.
"""
from __future__ import annotations

from sympy import S, Symbol
from sympy.logic.boolalg import BooleanFunction


class _Index(Symbol):
    """An index variable of the symmetric-swap row: :class:`_SwappedOrder` of
    two of these stays unevaluated, so the row's hypothesis is decided only
    once the indices are bound."""


class _SwappedOrder(BooleanFunction):
    """True when ``A[i, j]`` is out of SymPy's canonical index order and
    ``A[j, i]`` is in it (SymPy's ``refine_matrixelement``: keep ``A[i, j]``
    when ``i - j`` has a minus sign to extract).  It evaluates on construction,
    i.e. when the row's binding is substituted.  It asks for both directions,
    so a pair of forms both reading as unsigned (none is known) cannot swap
    back and forth."""

    @classmethod
    def eval(cls, i, j):
        if isinstance(i, _Index) or isinstance(j, _Index):
            return None
        d = i - j
        return S.true if not d.could_extract_minus_sign() and (-d).could_extract_minus_sign() else S.false
