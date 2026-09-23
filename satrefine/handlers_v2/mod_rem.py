"""Handlers for ``Mod`` and ``Rem``.

SymPy defines ``Mod(a, b) == a - b*floor(a/b)`` (result has the sign of
``b``) and ``Rem(a, b) == a - b*trunc(a/b)`` (result has the sign of
``a``).  Both are ``nan`` for ``b == 0``.

``Mod`` rules:

D1  ``Mod(a, b) -> 0`` when ``a`` is zero and ``b`` provably nonzero.
D2  ``Mod(a, b) -> 0`` when ``a/b`` is an integer (and ``a`` is not merely
    zero, which would say nothing about ``b``; ``Mod(0, 0)`` is ``nan``).
D3  ``Mod(a + t, b) -> Mod(a, b)`` for additive terms ``t`` with ``t/b`` a
    provable integer (``floor(a/b + k) == floor(a/b) + k``).
D4  ``Mod(a, 2) -> 1`` when ``a`` is odd (``-> 0`` for even ``a`` follows
    from D2).
D5  ``Mod(a, b) -> a`` when ``0 <= a < b`` (``a`` nonnegative, ``b``
    positive, and the relation ``a < b`` stated) or ``b < a <= 0``.

``Rem`` rules:

M1  ``Rem(a, b) -> 0`` when ``a`` is zero and ``b`` provably nonzero.
M2  ``Rem(a, b) -> 0`` when ``a/b`` is an integer.
M3  ``Rem(a, 2) -> -1`` when ``a`` is a negative odd integer.
M4  ``Rem(a, b) -> Mod(a, b)`` when ``a`` and ``b`` have the same sign
    (``a >= 0, b > 0`` or ``a <= 0, b < 0``): then ``a/b >= 0`` and
    truncation equals ``floor``.  The ``Mod`` rules take it from there
    (``Rem(a, 2) -> 1`` for nonnegative odd ``a``, ``Rem(a, b) -> a`` for
    ``0 <= a < b``).

Dropping integer multiples of ``b`` from ``a`` (D3) is *not* done for
``Rem``: ``Rem(-1 + 2, 2) == 1`` but ``Rem(-1, 2) == -1``.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Add, Basic, S
from sympy.core.mod import Mod

from .._upstream import handlers_dict
from ._common import Assumptions, holds, is_nonzero, relation_holds


def _common_zero(a: Basic, b: Basic, assumptions: Assumptions) -> bool:
    """Rules D1/M1 and D2/M2: the remainder is provably zero."""
    if holds(Q.zero(a), assumptions):
        return is_nonzero(b, assumptions)
    return holds(Q.integer(a / b), assumptions)


def _same_sign(a: Basic, b: Basic, assumptions: Assumptions) -> bool:
    return ((holds(Q.nonnegative(a), assumptions) and holds(Q.positive(b), assumptions))
            or (holds(Q.nonpositive(a), assumptions) and holds(Q.negative(b), assumptions)))


def refine_Mod(expr: Basic, assumptions: Assumptions) -> Basic | None:
    a, b = expr.args
    if _common_zero(a, b, assumptions):                                 # D1, D2
        return S.Zero
    if isinstance(a, Add):                                              # D3
        rest = [term for term in a.args if not holds(Q.integer(term / b), assumptions)]
        if len(rest) < len(a.args):
            return Mod(Add(*rest), b)
    if b == 2 and holds(Q.odd(a), assumptions):                         # D4
        return S.One
    if _same_sign(a, b, assumptions):                                   # D5
        if holds(Q.positive(b), assumptions) and relation_holds(Q.lt(a, b), assumptions):
            return a
        if holds(Q.negative(b), assumptions) and relation_holds(Q.gt(a, b), assumptions):
            return a
    return None


def refine_Rem(expr: Basic, assumptions: Assumptions) -> Basic | None:
    a, b = expr.args
    if _common_zero(a, b, assumptions):                                 # M1, M2
        return S.Zero
    if b == 2 and holds(Q.odd(a), assumptions) and holds(Q.negative(a), assumptions):  # M3
        return S.NegativeOne
    if _same_sign(a, b, assumptions):                                   # M4
        return Mod(a, b)
    return None


handlers_dict['Mod'] = refine_Mod
handlers_dict['Rem'] = refine_Rem
