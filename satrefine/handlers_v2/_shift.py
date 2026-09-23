"""Shift-by-half-periods machinery for the trigonometric and hyperbolic
handlers.

An argument is split as ``rem + k*unit/2`` (``unit`` is ``pi`` or ``pi*I``)
with ``k`` an integer of known parity (see
:func:`satrefine.handlers_v2._common.split_shift`).  Each function then
has a quarter-period table:

* for even ``k`` the function is unchanged up to a factor
  ``(-1)**(k/2)`` (or exactly unchanged for ``tan``, ``cot``, ``tanh``,
  ``coth``);
* for odd ``k`` it turns into its co-function times a factor that is
  ``(-1)**((k-1)/2)`` or ``(-1)**((k+1)/2)``, possibly times ``I``.

:func:`shift_rule` builds a handler from such a table; the ``(-1)**m``
factors are normalised with :func:`satrefine.handlers_v2.pow.minus_one_power`
so that ``(-1)**((n-1)/2)`` prints as ``(-1)**((n+3)/2)`` exactly as SymPy's
own handler does.
"""
from __future__ import annotations

from typing import Callable

from sympy.core import Basic, S

from ._common import Assumptions, Handler, split_shift
from .pow import minus_one_power

Case = Callable[[Basic, Basic, Assumptions], Basic]
"""``(rem, k, assumptions) -> result`` for one parity of ``k``."""


def even_case(func: Callable[[Basic], Basic], sign_power: bool = True) -> Case:
    """``f(rem + k*unit/2) -> (-1)**(k/2) * f(rem)`` (or just ``f(rem)``)."""
    def case(rem: Basic, k: Basic, assumptions: Assumptions) -> Basic:
        value = func(rem)
        if sign_power:
            value = minus_one_power(k / 2, assumptions) * value
        return value
    return case


def odd_case(cofunc: Callable[[Basic], Basic], offset: int | None,
             factor: Basic = S.One) -> Case:
    """``f(rem + k*unit/2) -> factor * (-1)**((k + offset)/2) * cofunc(rem)``.

    ``offset`` is ``-1`` or ``+1`` (or ``None`` for no sign power)."""
    def case(rem: Basic, k: Basic, assumptions: Assumptions) -> Basic:
        value = factor * cofunc(rem)
        if offset is not None:
            value = minus_one_power((k + offset) / 2, assumptions) * value
        return value
    return case


def shift_rule(unit: Basic, even: Case, odd: Case) -> Handler:
    """Build ``handler(expr, assumptions)`` applying the shift table."""
    def handler(expr: Basic, assumptions: Assumptions) -> Basic | None:
        split = split_shift(expr.args[0], unit, assumptions)
        if split is None:
            return None
        rem, k, k_is_even = split
        if k_is_even:
            return even(rem, k, assumptions)
        return odd(rem, k, assumptions)
    return handler
