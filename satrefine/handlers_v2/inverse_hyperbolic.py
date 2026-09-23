"""Handlers for ``asinh``, ``acosh``, ``atanh``, ``acoth``, ``asech`` and
``acsch``.

On the real line ``sinh``, ``tanh`` are bijections onto their images and
``asinh``, ``atanh`` are their inverses; ``coth`` and ``csch`` are
bijections from the nonzero reals; ``cosh`` and ``sech`` are even, with
``acosh`` and ``asech`` returning the nonnegative preimage.  Rules:

J1  ``f(x) -> f(0)`` when ``x`` is zero (SymPy's values: ``asinh(0) == 0``,
    ``acosh(0) == I*pi/2``, ``atanh(0) == 0``, ``acoth(0) == I*pi/2``,
    ``asech(0) == oo``, ``acsch(0) == zoo``).
J2  ``asinh(sinh(x)) -> x`` and ``atanh(tanh(x)) -> x`` for real ``x``.
J3  ``acosh(cosh(x)) -> Abs(x)`` and ``asech(sech(x)) -> Abs(x)`` for
    real ``x`` (``Abs(x)`` then refines to ``x`` for nonnegative ``x``).
J4  ``acoth(coth(x)) -> x`` and ``acsch(csch(x)) -> x`` for real nonzero
    ``x``.

No rule fires for complex ``x``: ``asinh(sinh(x)) == x`` needs
``im(x)`` in ``[-pi/2, pi/2]``, which cannot be asked.
"""
from __future__ import annotations

from typing import Callable

from sympy.assumptions import Q
from sympy.core import Basic
from sympy.functions.elementary.complexes import Abs
from sympy.functions.elementary.hyperbolic import cosh, coth, csch, sech, sinh, tanh

from .._upstream import handlers_dict
from ._common import Assumptions, Handler, first_of, holds, zero_argument


def _inverse_of(forward: type, image: Callable[[Basic], Basic],
                nonzero: bool = False) -> Handler:
    """``inverse(forward(x)) -> image(x)`` for real (and nonzero) ``x``."""
    def handler(expr: Basic, assumptions: Assumptions) -> Basic | None:
        inner = expr.args[0]
        if not isinstance(inner, forward):
            return None
        x = inner.args[0]
        if not holds(Q.real(x), assumptions):
            return None
        if nonzero and not holds(Q.nonzero(x), assumptions):
            return None
        return image(x)
    return handler


def _identity(x: Basic) -> Basic:
    return x


refine_asinh = first_of(zero_argument, _inverse_of(sinh, _identity))
refine_acosh = first_of(zero_argument, _inverse_of(cosh, Abs))
refine_atanh = first_of(zero_argument, _inverse_of(tanh, _identity))
refine_acoth = first_of(zero_argument, _inverse_of(coth, _identity, nonzero=True))
refine_asech = first_of(zero_argument, _inverse_of(sech, Abs))
refine_acsch = first_of(zero_argument, _inverse_of(csch, _identity, nonzero=True))

handlers_dict['asinh'] = refine_asinh
handlers_dict['acosh'] = refine_acosh
handlers_dict['atanh'] = refine_atanh
handlers_dict['acoth'] = refine_acoth
handlers_dict['asech'] = refine_asech
handlers_dict['acsch'] = refine_acsch
