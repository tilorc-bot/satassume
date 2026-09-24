"""Simple rules the identity rows reduce their bookkeeping through.

Registered by the package ``__init__`` on ``re``, ``im``, ``arg``, ``Abs``,
``floor``, ``ceiling`` and ``Piecewise`` before the family modules load, so
a family module that registers one of these keys overrides them and should
chain to the function here (``return simple_im(expr, assumptions)`` at the
end of its handler) to keep the reductions.  Each rule chains to the
vendored handler when it does not apply.

Rules:

``re``/``im``/``arg``/``Abs`` of exponentials, logarithms and products
    ``re(exp w) = exp(re w)*cos(im w)``, ``im(exp w) = exp(re w)*sin(im w)``,
    ``Abs(exp w) = exp(re w)``, ``arg(exp w) = sawtooth(im w, 2*pi)``;
    ``re(log w) = log(Abs w)``, ``im(log w) = arg w``;
    ``re``/``im`` distribute over sums and pull real factors out of
    products; ``Abs`` distributes over products; ``arg(x) = +-pi/2`` when
    ``-I*x`` is positive or negative (the imaginary axis).
``floor``/``ceiling`` of a bounded head
    ``floor(a*h(y) + c)`` with numeric ``a``, ``c`` and ``h`` in
    :data:`BOUNDS` (``arg``, ``atan``, ``acot``, ``asin``, ``acos``) is a
    constant when the floor is constant over the image of ``h``'s range;
    ``arg`` is open at ``pi`` when ``y`` is provably not negative.
``Piecewise``
    branches are refined under the assumptions plus their own condition;
    ``Piecewise`` itself drops decided conditions and merges equal
    branches.
"""
from __future__ import annotations

from typing import Any

from sympy import (Abs, Add, Dummy, I, Mul, Piecewise, Q, S, acos, acot, arg, asin, atan, ceiling, cos,
                   exp, floor, im, log, pi, re, sin)
from sympy.core import Basic
from sympy.logic.boolalg import Boolean

from .. import _upstream
from ._wraps import sawtooth

# head -> (lo, hi, lo_open, hi_open) of its range on real (nonzero for arg) arguments
BOUNDS: dict = {
    arg:  (-pi, pi, True, False),
    atan: (-pi/2, pi/2, True, True),
    acot: (-pi/2, pi/2, True, False),
    asin: (-pi/2, pi/2, False, False),
    acos: (S.Zero, pi, False, False),
}


def _range(node: Any, assumptions: Any) -> tuple | None:
    """The range of a bounded head applied to its argument, or ``None``."""
    head = node.func
    if head not in BOUNDS:
        return None
    lo, hi, lo_open, hi_open = BOUNDS[head]
    y = node.args[0]
    if head is arg:
        if _upstream.ask(Q.negative(y), assumptions) is False:
            hi_open = True                       # not on the negative real axis
    elif head in (asin, acos):
        if _upstream.ask(Q.real(node), assumptions) is not True:
            return None
    elif _upstream.ask(Q.real(y), assumptions) is not True:
        return None
    return lo, hi, lo_open, hi_open


def _constant_over(fn: Any, a: Any, c: Any, rng: tuple) -> Any | None:
    """``fn`` (floor or ceiling) of ``a*t + c`` when it is constant for ``t`` in ``rng``."""
    lo, hi, lo_open, hi_open = rng
    L, U = a*lo + c, a*hi + c
    if a < 0:
        L, U, lo_open, hi_open = U, L, hi_open, lo_open
    if fn is floor:
        at_low = floor(L)
        at_high = U - 1 if (hi_open and U.is_integer) else floor(U)
    else:
        at_low = L + 1 if (lo_open and L.is_integer) else ceiling(L)
        at_high = ceiling(U)
    if at_low.is_number and at_high.is_number and at_low == at_high:
        return at_low
    return None


def floor_of_bounded(expr: Basic, assumptions: Any) -> Basic | None:
    """``floor``/``ceiling`` of ``a*h(y) + c`` for a bounded head ``h``."""
    fn, inner = expr.func, expr.args[0]
    nodes = [n for n in inner.atoms(*BOUNDS) if n in inner.atoms(*BOUNDS)]
    for node in nodes:
        t = Dummy("t")
        e = inner.xreplace({node: t}).expand()
        a = e.coeff(t)
        c = (e - a*t).expand()
        if a == 0 or not a.is_number or not c.is_number or c.has(t):
            continue
        rng = _range(node, assumptions)
        if rng is None:
            continue
        value = _constant_over(fn, a, c, rng)
        if value is not None:
            return value
    return None


def refine_floor(expr: Basic, assumptions: Any) -> Basic | None:
    value = floor_of_bounded(expr, assumptions)
    if value is not None:
        return value
    return _upstream.refine_floor_ceiling(expr, assumptions)


def _real_factors(a: Any, assumptions: Any) -> tuple[list, list]:
    real = [f for f in a.args if _upstream.ask(Q.real(f), assumptions)]
    return real, [f for f in a.args if f not in real]


def refine_re(expr: Basic, assumptions: Any) -> Basic | None:
    a = expr.args[0]
    if isinstance(a, exp):
        w = a.args[0]
        return exp(re(w))*cos(im(w))
    if isinstance(a, log):
        return log(Abs(a.args[0]))
    if isinstance(a, Add):
        return Add(*[re(t) for t in a.args])
    if isinstance(a, Mul):
        real, rest = _real_factors(a, assumptions)
        if real and rest:
            return Mul(*real)*re(Mul(*rest))
    return _upstream.refine_re(expr, assumptions)


def refine_im(expr: Basic, assumptions: Any) -> Basic | None:
    a = expr.args[0]
    if isinstance(a, exp):
        w = a.args[0]
        return exp(re(w))*sin(im(w))
    if isinstance(a, log):
        return arg(a.args[0])
    if isinstance(a, Add):
        return Add(*[im(t) for t in a.args])
    if isinstance(a, Mul):
        real, rest = _real_factors(a, assumptions)
        if real and rest:
            return Mul(*real)*im(Mul(*rest))
    return _upstream.refine_im(expr, assumptions)


def refine_arg(expr: Basic, assumptions: Any) -> Basic | None:
    a = expr.args[0]
    if isinstance(a, exp):
        return sawtooth(im(a.args[0]), 2*pi)
    if _upstream.ask(Q.positive(-I*a), assumptions):
        return pi/2
    if _upstream.ask(Q.negative(-I*a), assumptions):
        return -pi/2
    return _upstream.refine_arg(expr, assumptions)


def refine_abs(expr: Basic, assumptions: Any) -> Basic | None:
    a = expr.args[0]
    if isinstance(a, exp):
        return exp(re(a.args[0]))
    if isinstance(a, Mul) and len(a.args) > 1:
        return Mul(*[Abs(f) for f in a.args])
    return _upstream.refine_abs(expr, assumptions)


def refine_piecewise(expr: Basic, assumptions: Any) -> Basic | None:
    from ._dispatch import refine
    pairs = []
    for value, cond in expr.args:
        extra = cond if isinstance(cond, Boolean) and cond not in (S.true, S.false) else None
        try:
            pairs.append((refine(value, assumptions & extra if extra is not None else assumptions), cond))
        except ValueError:                       # the branch condition contradicts the assumptions
            continue
    if not pairs:
        return None
    return Piecewise(*pairs)


SIMPLE_RULES = {"re": refine_re, "im": refine_im, "arg": refine_arg, "Abs": refine_abs,
                "floor": refine_floor, "ceiling": refine_floor, "Piecewise": refine_piecewise}


def refine_Pow_guarded(expr: Basic, assumptions: Any) -> Basic | None:
    """The vendored ``Pow`` handler with its crash caught (temporary).

    SymPy's ``refine_Pow`` raises ``AttributeError`` on ``(-1)**(n + 1/2)``
    under a parity assumption (its rebuilt power auto-evaluates to a product
    it then reads ``.exp`` from), and is unsound on ``sqrt(x**2)`` for an
    imaginary ``x`` and ``sqrt(x**3)`` for a real one.  This wrapper only
    stops the crash so the battery can run; the ``power_exp_log`` family
    module replaces the key and the unsound rules with it.
    """
    try:
        return _upstream.refine_Pow(expr, assumptions)
    except AttributeError:
        return None


def install(handlers_dict: dict) -> None:
    """Register the simple rules; family modules loaded later override them."""
    for key, handler in SIMPLE_RULES.items():
        handlers_dict[key] = handler
    handlers_dict["Pow"] = refine_Pow_guarded
