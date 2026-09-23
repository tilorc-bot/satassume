"""Assumption-driven ``refine`` handlers for the trigonometric family.

Registry keys: ``sin``, ``cos``, ``tan``, ``cot``, ``sec``, ``csc``, ``sinc``.

Every argument is written as ``arg = N*pi/2 + r`` (``split_shift`` with unit
``pi/2``).  The additive terms of ``N`` that are known integers with a known
parity are collected into ``K``; if the remaining terms together are a known
integer of known parity they join ``K`` too, otherwise they stay in ``r``
(as ``term*pi/2``).  ``r`` is arbitrary: all identities below are exact over
the whole complex plane (``r`` need not be real) and at poles, where both
sides are ``zoo`` in SymPy's convention.  Nothing is done unless ``K != 0``
or a zero rule applies.

Shift rules (precondition: ``K`` integer of known parity):

* ``K`` residue mod 4 known (literal, or by asking ``Q.even(K/2)`` when
  ``K`` is even, ``Q.even((K-1)/2)`` when ``K`` is odd)::

      K mod 4     0        1        2        3
      sin       sin r    cos r   -sin r   -cos r
      cos       cos r   -sin r   -cos r    sin r
      sec       sec r   -csc r   -sec r    csc r
      csc       csc r    sec r   -csc r   -sec r

* only the parity of ``K`` known: the same with a sign ``(-1)**e``,
  ``e`` an integer: ``K`` even: ``f(r+K*pi/2) = (-1)**(K/2) f(r)`` for
  f in sin, cos, sec, csc; ``K`` odd: ``sin -> (-1)**((K-1)/2) cos r``,
  ``cos -> (-1)**((K+1)/2) sin r``, ``sec -> (-1)**((K+1)/2) csc r``,
  ``csc -> (-1)**((K-1)/2) sec r``.
* ``tan``/``cot`` (period ``pi``, parity suffices): ``K`` even: unchanged
  function of ``r``; ``K`` odd: ``tan -> -cot r``, ``cot -> -tan r``.

Hence, for integer ``k``: ``sin(k*pi) -> 0``, ``cos(k*pi) -> (-1)**k``
(``+-1`` when the parity is known), ``cos(2*k*pi) -> 1``,
``tan(k*pi) -> 0``, ``cot(k*pi) -> zoo`` (pole), ``sin(x + k*pi) ->
(-1)**k sin(x)``, and so on.  An argument ``x + k*pi/2`` with only
``Q.integer(k)`` is left alone (parity of ``k`` unknown).

Zero rules (precondition: ``Q.zero(r)``): ``r`` is replaced by ``0``, so
``sin(0) = tan(0) = 0``, ``cos(0) = sec(0) = 1``, ``cot(0) = csc(0) = zoo``.

``sin``/``cos`` of an infinite extended-real argument give
``AccumBounds(-1, 1)`` (SymPy's own value for ``sin(oo)``; kept from the
vendored ``refine_sin_cos``).

``sinc`` (precondition: ``arg = N*pi/2`` exactly, i.e. ``Q.zero(r)``):
``sinc(0) -> 1``; ``N`` nonzero even (``sinc(k*pi)``, ``k`` nonzero
integer) ``-> 0``; ``N`` odd ``-> sin(N*pi/2)/(N*pi/2)`` refined by the
rules above.  ``sinc(x)`` with ``Q.zero(x)`` ``-> 1``.

Not implemented: shifts of ``sinc`` with a nonzero remainder (no simpler
form), shifts by ``pi*I`` multiples (those belong to the hyperbolic family),
and ``AccumBounds`` for tan/cot/sec/csc at infinity.  The ``-x`` symmetry is
left to SymPy's automatic evaluation.
"""
from __future__ import annotations

from typing import Any

from sympy import Add, Pow, S, expand
from sympy.assumptions import Q
from sympy.calculus.accumulationbounds import AccumBounds
from sympy.core.expr import Expr
from sympy.functions.elementary.trigonometric import (
    cos, cot, csc, sec, sin, sinc, tan,
)

from .. import _upstream
from .._upstream import handlers_dict
from ._common import is_integer, parity, split_shift

_HALF_PI = S.Pi / 2

# (function, K mod 4) -> (sign, function of r)
_TABLE = {
    sin: {0: (1, sin), 1: (1, cos), 2: (-1, sin), 3: (-1, cos)},
    cos: {0: (1, cos), 1: (-1, sin), 2: (-1, cos), 3: (1, sin)},
    sec: {0: (1, sec), 1: (-1, csc), 2: (-1, sec), 3: (1, csc)},
    csc: {0: (1, csc), 1: (1, sec), 2: (-1, csc), 3: (-1, sec)},
}
# sign exponent offset when only the parity of K is known:
# K odd: f(r + K*pi/2) = (-1)**((K + off)/2) * g(r)
_ODD_OFFSET = {sin: (-1, cos), cos: (1, sin), sec: (1, csc), csc: (-1, sec)}


def _split(arg: Expr, assumptions: Any) -> tuple[Expr, str | None, Expr]:
    """Return ``(K, parity of K, r)`` with ``arg = K*pi/2 + r``.

    ``K`` collects the terms of the ``pi/2`` multiple that are known
    integers of known parity; ``K`` is ``0`` (parity ``None``) if none.
    """
    k, rest = split_shift(arg, _HALF_PI)
    if k == 0:
        return S.Zero, None, arg
    known = S.Zero
    known_odd = False
    leftover = S.Zero
    for term in Add.make_args(k):
        p = parity(term, assumptions) if is_integer(term, assumptions) else None
        if p is None:
            leftover += term
        else:
            known += term
            known_odd ^= (p == "odd")
    if leftover != 0 and is_integer(leftover, assumptions):
        p = parity(leftover, assumptions)
        if p is not None:
            known += leftover
            known_odd ^= (p == "odd")
            leftover = S.Zero
    if known == 0:
        return S.Zero, None, arg
    return known, ("odd" if known_odd else "even"), rest + leftover * _HALF_PI


def _mod4(K: Expr, par: str, assumptions: Any) -> int | None:
    """``K mod 4`` for an integer ``K`` of parity ``par``, or ``None``."""
    if K.is_Integer:
        return int(K) % 4
    half = expand(K / 2) if par == "even" else expand((K - 1) / 2)
    p = parity(half, assumptions)
    if p is None:
        return None
    return (0 if par == "even" else 1) + (2 if p == "odd" else 0)


def _zero_rest(rest: Expr, assumptions: Any) -> Expr:
    if rest != 0 and _upstream.ask(Q.zero(rest), assumptions):
        return S.Zero
    return rest


def _refine_periodic(expr: Expr, assumptions: Any) -> Expr | None:
    func = expr.func
    arg = expr.args[0]
    if func in (sin, cos) and _upstream.ask(Q.infinite(arg), assumptions) \
            and _upstream.ask(Q.extended_real(arg), assumptions):
        return AccumBounds(-1, 1)
    K, par, rest = _split(arg, assumptions)
    rest = _zero_rest(rest, assumptions)
    if K == 0:
        if rest == 0 and arg != 0:
            return func(S.Zero)
        return None
    if func in (tan, cot):
        if par == "even":
            return func(rest)
        return -(cot(rest) if func is tan else tan(rest))
    r4 = _mod4(K, par, assumptions)
    if r4 is not None:
        sign, g = _TABLE[func][r4]
        return _signed(sign, g(rest))
    if par == "even":
        return _signed(Pow(S.NegativeOne, expand(K / 2)), func(rest))
    off, g = _ODD_OFFSET[func]
    return _signed(Pow(S.NegativeOne, expand((K + off) / 2)), g(rest))


def _signed(sign: Expr, value: Expr) -> Expr:
    """``sign*value``; a pole (``zoo``) absorbs the unit sign."""
    if value is S.ComplexInfinity:
        return value
    return sign * value


def refine_sin(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``sin``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_cos(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``cos``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_tan(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``tan``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_cot(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``cot``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_sec(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``sec``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_csc(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``csc``; see the module docstring for the rules."""
    return _refine_periodic(expr, assumptions)


def refine_sinc(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``sinc``; see the module docstring for the rules."""
    arg = expr.args[0]
    if arg != 0 and _upstream.ask(Q.zero(arg), assumptions):
        return S.One
    K, par, rest = _split(arg, assumptions)
    if K == 0 or _zero_rest(rest, assumptions) != 0:
        return None
    point = K * _HALF_PI
    if par == "odd":
        value = sin(point)  # SymPy may evaluate it (e.g. sin(pi/2) = 1)
        if isinstance(value, sin):
            value = _refine_periodic(value, assumptions)
        return None if value is None else value / point
    if K.is_Integer or _upstream.ask(Q.nonzero(K), assumptions):
        return S.Zero
    return None


handlers_dict['sin'] = refine_sin
handlers_dict['cos'] = refine_cos
handlers_dict['tan'] = refine_tan
handlers_dict['cot'] = refine_cot
handlers_dict['sec'] = refine_sec
handlers_dict['csc'] = refine_csc
handlers_dict['sinc'] = refine_sinc
