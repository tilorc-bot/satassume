"""Handler for ``conjugate``.

Rules (``conjugate(x)`` is the expression):

C1  ``conjugate(x) -> x`` when ``x`` is real.
C2  ``conjugate(x) -> -x`` when ``x`` is imaginary.
C3  ``conjugate(b**e) -> conjugate(b)**e`` when ``e`` is an integer: for
    integer powers no branch cut is involved.
C4  ``conjugate(b**e) -> conjugate(b)**conjugate(e)`` when ``b`` is
    provably *not* a negative real (``ask(Q.negative(b))`` is ``False``):
    off the branch cut of ``log``, ``conjugate(log(b)) == log(conjugate(b))``
    and hence ``conjugate(exp(e*log(b))) == exp(conjugate(e)*log(conjugate(b)))``.
C5  ``conjugate(log(b)) -> log(conjugate(b))`` under the same precondition.

SymPy already pushes ``conjugate`` through ``Add``, ``Mul``, ``exp`` and the
entire-function ``sin``, ``cos``, ``gamma`` and so on, so the refined inner
``conjugate(x)`` takes care of ``conjugate(sin(x))`` with real ``x``.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Pow
from sympy.functions.elementary.complexes import conjugate
from sympy.functions.elementary.exponential import log

from .._upstream import handlers_dict
from ._common import Assumptions, fails, holds


def refine_conjugate(expr: Basic, assumptions: Assumptions) -> Basic | None:
    x = expr.args[0]
    if holds(Q.real(x), assumptions):                                   # C1
        return x
    if holds(Q.imaginary(x), assumptions):                              # C2
        return -x
    if isinstance(x, Pow):
        b, e = x.base, x.exp
        if holds(Q.integer(e), assumptions):                            # C3
            return conjugate(b)**e
        if fails(Q.negative(b), assumptions):                           # C4
            return conjugate(b)**conjugate(e)
    if isinstance(x, log) and fails(Q.negative(x.args[0]), assumptions):  # C5
        return log(conjugate(x.args[0]))
    return None


handlers_dict['conjugate'] = refine_conjugate
