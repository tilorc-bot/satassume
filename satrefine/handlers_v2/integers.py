"""Handlers for ``floor``, ``ceiling`` and ``frac``.

``floor``/``ceiling`` rules (the vendored SymPy handler
:func:`satrefine._upstream.refine_floor_ceiling`, checked and kept):

F1  ``floor(x) -> x`` when ``x`` is an integer or infinite (``floor(oo) ==
    oo``, ``floor(zoo) == zoo``).
F2  ``floor(n + y) -> n + floor(y)`` for provably integer terms ``n`` and
    for terms that are themselves ``floor``/``ceiling`` values (Gaussian
    integers for complex arguments; ``floor(z + g) == floor(z) + g`` holds
    for every Gaussian integer ``g`` under SymPy's componentwise
    definition).

``frac`` rules (``frac(x) == x - floor(x)``, so ``frac`` is 1-periodic):

Q1  ``frac(x) -> 0`` when ``x`` is an integer.
Q2  ``frac(n + y) -> frac(y)`` for provably integer terms ``n``.
Q3  ``frac(x) -> x`` when ``0 <= x < 1`` is stated as relations.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Add, Basic, S
from sympy.functions.elementary.integers import frac

from .. import _upstream
from .._upstream import handlers_dict
from ._common import Assumptions, holds, relation_holds


def refine_frac(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.integer(x), assumptions):                                # Q1
        return S.Zero
    if isinstance(x, Add):                                              # Q2
        rest = [term for term in x.args if not holds(Q.integer(term), assumptions)]
        if len(rest) < len(x.args):
            return frac(Add(*rest))
    if relation_holds(Q.ge(x, S.Zero), assumptions) and relation_holds(Q.lt(x, S.One), assumptions):  # Q3
        return x
    return None


handlers_dict['floor'] = _upstream.refine_floor_ceiling
handlers_dict['ceiling'] = _upstream.refine_floor_ceiling
handlers_dict['frac'] = refine_frac
