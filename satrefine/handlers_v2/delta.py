"""Handlers for ``DiracDelta``, ``KroneckerDelta`` and ``Heaviside``.

``DiracDelta`` rules:

V1  ``DiracDelta(x[, k]) -> 0`` when ``x`` is real and nonzero (SymPy's
    ``DiracDelta`` evaluates to ``0`` at every nonzero number).
    The scaling law ``DiracDelta(c*x) == DiracDelta(x)/Abs(c)`` is a
    distributional identity that does not hold pointwise at ``x == 0`` for
    SymPy's function object, so it is not applied.

``KroneckerDelta`` rules:

W1  ``KroneckerDelta(i, j) -> 1`` when ``i - j`` is zero and no
    ``delta_range`` is given (with a range the value is ``0`` outside it).
W2  ``KroneckerDelta(i, j) -> 0`` when ``i - j`` is provably nonzero, or
    one index is an integer and the other provably not.

``Heaviside`` rules (the vendored SymPy handler
:func:`satrefine._upstream.refine_Heaviside`, checked and kept):

Z1  ``Heaviside(x, H0) -> 1`` for positive ``x``, ``-> 0`` for negative
    ``x``, ``-> H0`` for zero ``x``.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, S

from .. import _upstream
from .._upstream import handlers_dict
from ._common import Assumptions, fails, holds, is_nonzero


def refine_DiracDelta(expr: Basic, assumptions: Assumptions) -> Basic | None:
    if holds(Q.nonzero(expr.args[0]), assumptions):                     # V1
        return S.Zero
    return None


def refine_KroneckerDelta(expr: Basic, assumptions: Assumptions) -> Basic | None:
    i, j = expr.args[0], expr.args[1]
    difference = i - j
    if len(expr.args) == 2 and holds(Q.zero(difference), assumptions):  # W1
        return S.One
    if is_nonzero(difference, assumptions):                             # W2
        return S.Zero
    for a, b in ((i, j), (j, i)):
        if holds(Q.integer(a), assumptions) and fails(Q.integer(b), assumptions):
            return S.Zero
    return None


handlers_dict['DiracDelta'] = refine_DiracDelta
handlers_dict['KroneckerDelta'] = refine_KroneckerDelta
handlers_dict['Heaviside'] = _upstream.refine_Heaviside
