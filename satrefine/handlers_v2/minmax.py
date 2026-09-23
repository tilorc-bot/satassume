"""Handlers for ``Max`` and ``Min``.

Rules (``Max``; ``Min`` is the mirror image):

X1  An argument ``b`` is dropped when another argument ``a`` provably
    dominates it: ``a - b`` nonnegative, or the relation ``a >= b`` stated.
    ``Max(x, y) -> x`` for ``Q.nonnegative(x) & Q.nonpositive(y)`` needs no
    relation at all.  If one argument remains it is returned.
X2  ``Max(x, -x) -> Abs(x)`` and ``Min(x, -x) -> -Abs(x)`` for real ``x``.

Arguments are only compared pairwise, each pair asked at most twice; a
pair that is not decided is kept.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, S
from sympy.functions.elementary.complexes import Abs
from sympy.functions.elementary.miscellaneous import Max, Min

from .._upstream import handlers_dict
from ._common import Assumptions, Handler, holds, relation_holds


def _dominates(a: Basic, b: Basic, assumptions: Assumptions) -> bool:
    """``a >= b`` provable."""
    return holds(Q.nonnegative(a - b), assumptions) or relation_holds(Q.ge(a, b), assumptions)


def _extremum(func: type, keep_larger: bool, abs_sign: Basic) -> Handler:
    def handler(expr: Basic, assumptions: Assumptions) -> Basic | None:
        args = list(expr.args)
        if len(args) == 2 and args[0] == -args[1] and holds(Q.real(args[0]), assumptions):  # X2
            return abs_sign * Abs(args[0])
        kept: list[Basic] = []
        for candidate in args:                                          # X1
            others = [other for other in args if other is not candidate]
            if keep_larger:
                dropped = any(_dominates(other, candidate, assumptions) for other in others)
            else:
                dropped = any(_dominates(candidate, other, assumptions) for other in others)
            if not dropped:
                kept.append(candidate)
        if not kept or len(kept) == len(args):
            return None
        return func(*kept)
    return handler


refine_Max = _extremum(Max, True, S.One)
refine_Min = _extremum(Min, False, S.NegativeOne)

handlers_dict['Max'] = refine_Max
handlers_dict['Min'] = refine_Min
