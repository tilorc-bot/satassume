"""Handlers for ``asin``, ``acos``, ``atan`` and ``atan2``.

SymPy's principal branches: ``asin`` maps ``[-1, 1]`` onto
``[-pi/2, pi/2]``, ``acos`` onto ``[0, pi]``, ``atan`` maps the reals onto
``(-pi/2, pi/2)``.  Rules:

I1  ``f(x) -> f(0)`` when ``x`` is zero (``asin(0) == 0``,
    ``acos(0) == pi/2``, ``atan(0) == 0``).
I2  Inversion on the principal range, which needs relations (so it fires
    only when the assumptions state them literally):
      * ``asin(sin(x)) -> x`` for ``-pi/2 <= x <= pi/2``;
      * ``asin(cos(x)) -> pi/2 - x`` for ``0 <= x <= pi``;
      * ``acos(cos(x)) -> x`` for ``0 <= x <= pi``;
      * ``acos(sin(x)) -> pi/2 - x`` for ``-pi/2 <= x <= pi/2``;
      * ``atan(tan(x)) -> x`` for ``-pi/2 < x < pi/2``;
      * ``atan(cot(x)) -> pi/2 - x`` for ``0 < x < pi``.
I3  ``atan(1/x) -> pi/2 - atan(x)`` for positive ``x`` and
    ``-> -pi/2 - atan(x)`` for negative ``x`` (``atan(z) + atan(1/z) ==
    sign(re(z))*pi/2`` off the imaginary axis; the assumption pins the
    sign).
I4  ``atan2(y, x)`` for real ``y``, ``x`` by quadrant: the vendored SymPy
    handler (:func:`satrefine._upstream.refine_atan2`), each of whose
    seven cases is the textbook definition and was checked.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Pow, S
from sympy.functions.elementary.trigonometric import atan, cos, cot, sin, tan

from .. import _upstream
from .._upstream import handlers_dict
from ._common import Assumptions, first_of, holds, relation_holds, zero_argument


def _between(x: Basic, low: Basic, high: Basic, assumptions: Assumptions,
             strict: bool = False) -> bool:
    """``low <= x <= high`` (or strict) provable from the assumptions."""
    if strict:
        return (relation_holds(Q.gt(x, low), assumptions)
                and relation_holds(Q.lt(x, high), assumptions))
    return (relation_holds(Q.ge(x, low), assumptions)
            and relation_holds(Q.le(x, high), assumptions))


def _invert_asin(expr: Basic, assumptions: Assumptions) -> Basic | None:
    inner = expr.args[0]
    if isinstance(inner, sin) and _between(inner.args[0], -S.Pi / 2, S.Pi / 2, assumptions):
        return inner.args[0]
    if isinstance(inner, cos) and _between(inner.args[0], S.Zero, S.Pi, assumptions):
        return S.Pi / 2 - inner.args[0]
    return None


def _invert_acos(expr: Basic, assumptions: Assumptions) -> Basic | None:
    inner = expr.args[0]
    if isinstance(inner, cos) and _between(inner.args[0], S.Zero, S.Pi, assumptions):
        return inner.args[0]
    if isinstance(inner, sin) and _between(inner.args[0], -S.Pi / 2, S.Pi / 2, assumptions):
        return S.Pi / 2 - inner.args[0]
    return None


def _invert_atan(expr: Basic, assumptions: Assumptions) -> Basic | None:
    inner = expr.args[0]
    if isinstance(inner, tan) and _between(inner.args[0], -S.Pi / 2, S.Pi / 2,
                                           assumptions, strict=True):
        return inner.args[0]
    if isinstance(inner, cot) and _between(inner.args[0], S.Zero, S.Pi,
                                           assumptions, strict=True):
        return S.Pi / 2 - inner.args[0]
    return None


def _reciprocal_atan(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """Rule I3."""
    inner = expr.args[0]
    if not (isinstance(inner, Pow) and inner.exp is S.NegativeOne):
        return None
    x = inner.base
    if holds(Q.positive(x), assumptions):
        return S.Pi / 2 - atan(x)
    if holds(Q.negative(x), assumptions):
        return -S.Pi / 2 - atan(x)
    return None


refine_asin = first_of(zero_argument, _invert_asin)
refine_acos = first_of(zero_argument, _invert_acos)
refine_atan = first_of(zero_argument, _invert_atan, _reciprocal_atan)

handlers_dict['asin'] = refine_asin
handlers_dict['acos'] = refine_acos
handlers_dict['atan'] = refine_atan
handlers_dict['atan2'] = _upstream.refine_atan2
