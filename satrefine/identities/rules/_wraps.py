"""Branch bookkeeping written out: the wraps.

An identity such as ``log(exp(z)) = principal(z)`` holds everywhere because
its right side carries the map back onto the principal branch explicitly.
Under assumptions, ``refine`` collapses the ``floor`` inside the wrap (to a
number or a known integer) and the conditional rule appears.  Each wrap
below states the interval it maps onto; the tests check them numerically.
"""
from __future__ import annotations

from typing import Any

from sympy import Abs, I, S, floor, im, pi


def principal(w: Any) -> Any:
    """The representative of ``w`` with imaginary part in ``(-pi, pi]``.

    ``exp(w)`` has principal logarithm ``principal(w)``.  Sawtooth of period
    ``2*pi*I`` in the imaginary direction; the floor argument is written as
    an ``Add`` (``1/2 - im(w)/(2*pi)``) so the floor handler can split off
    its integer terms.
    """
    return w + 2*pi*I*floor(S.Half - im(w)/(2*pi))


def sawtooth(t: Any, period: Any = pi) -> Any:
    """``t`` wrapped onto ``[-period/2, period/2)`` for real ``t``.

    ``atan(tan(t)) = sawtooth(t, pi)`` and ``acot(cot(t))`` likewise; with
    ``period=1`` this is ``t - round(t)``.
    """
    return t - period*floor(t/period + S.Half)


def reflect_half(t: Any) -> Any:
    """``t`` reflected onto ``[-pi/2, pi/2]`` for real ``t``: the triangle wave
    ``asin(sin(t))``, equal to ``(-1)**k*(t - k*pi)`` with ``k = floor(t/pi + 1/2)``."""
    k = floor(t/pi + S.Half)
    return (-1)**k*(t - k*pi)


def reflect_full(t: Any) -> Any:
    """``t`` reflected onto ``[0, pi]`` for real ``t``: ``acos(cos(t)) = Abs(sawtooth(t, 2*pi))``."""
    return Abs(sawtooth(t, 2*pi))


def fractional(x: Any) -> Any:
    """``x - floor(x)``, in ``[0, 1)`` for real ``x``: the integer sawtooth of ``frac``."""
    return x - floor(x)
