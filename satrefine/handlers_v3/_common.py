"""Helpers shared by the ``handlers_v3`` modules.

Handlers ask predicate questions only through ``_upstream.ask`` (imported as
a module attribute, so test harnesses can patch it) and return ``None`` when
nothing applies.  These helpers do the two chores several families share:
splitting an argument into a rational multiple of a unit (``pi``, ``pi/2``,
``pi*I``) plus a remainder, and asking about the parity of that multiple.
"""
from __future__ import annotations

from typing import Any

from sympy import Add, S
from sympy.assumptions import Q
from sympy.core.expr import Expr

from .. import _upstream


def split_shift(arg: Expr, unit: Expr) -> tuple[Expr, Expr]:
    """Write ``arg`` as ``k*unit + rest`` and return ``(k, rest)``.

    Terms of ``arg`` (as an ``Add``) whose ratio to ``unit`` is an expression
    with no ``unit``-like content left, i.e. ``term/unit`` is free of ``pi``
    and ``I`` when ``unit`` contains them, are collected into ``k``; the
    others form ``rest``.  ``k`` is an ``Expr`` (an Integer, a Rational, a
    symbol, ``2*n``, ...), not necessarily an integer: the caller must ask.

    >>> from sympy import pi, I, symbols
    >>> x, n = symbols('x n')
    >>> split_shift(x + n*pi, pi)
    (n, x)
    >>> split_shift(x + 3*pi/2, pi/2)
    (3, x)
    >>> split_shift(x + n*pi*I, pi*I)
    (n, x)
    """
    k = S.Zero
    rest = S.Zero
    for term in Add.make_args(arg):
        ratio = (term / unit).cancel()
        if not ratio.has(S.Pi) and not ratio.has(S.ImaginaryUnit):
            k += ratio
        else:
            rest += term
    return k, rest


def parity(k: Expr, assumptions: Any) -> str | None:
    """``'even'``, ``'odd'`` or ``None`` for the integer-valued ``k``.

    Asks ``Q.even(k)`` and ``Q.odd(k)`` through ``_upstream.ask``; ``None``
    also when ``k`` is not known to be an integer.
    """
    if k.is_Integer:
        return "even" if int(k) % 2 == 0 else "odd"
    if _upstream.ask(Q.even(k), assumptions):
        return "even"
    if _upstream.ask(Q.odd(k), assumptions):
        return "odd"
    return None


def is_integer(k: Expr, assumptions: Any) -> bool | None:
    """Whether ``k`` is an integer, by literal value or by asking."""
    if k.is_Integer:
        return True
    if k.is_Rational:
        return False
    return _upstream.ask(Q.integer(k), assumptions)
