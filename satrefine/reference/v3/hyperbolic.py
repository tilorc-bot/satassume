"""Refine handlers for the hyperbolic functions ``sinh``, ``cosh``, ``tanh``,
``coth``, ``sech`` and ``csch``.

Every handler writes the argument as ``arg = m*(pi*I/2) + x`` with
:func:`~._common.split_shift` (``m`` free of ``pi`` and ``I``, ``x`` the
rest, which may be any complex expression) and then uses the
``2*pi*I``-periodicity of the family.  No rule needs ``x`` to be real.

Period rules, precondition ``n = m/2`` an integer (that is, the argument is
``x + n*pi*I``):

* ``n`` even (``m = 0 mod 4``): every function returns ``f(x)``.
* ``n`` odd (``m = 2 mod 4``): ``sinh -> -sinh(x)``, ``cosh -> -cosh(x)``,
  ``sech -> -sech(x)``, ``csch -> -csch(x)``; ``tanh``/``coth`` unchanged.
* ``n`` only known to be an integer: ``tanh -> tanh(x)``,
  ``coth -> coth(x)`` (period ``pi*I``).  ``sinh``, ``cosh``, ``sech``,
  ``csch`` are left alone, except at an exact point (``x == 0``) below.

Half-period rules, precondition ``m`` odd (argument ``x + m*pi*I/2``):

* ``m`` odd, nothing more known: ``tanh -> coth(x)``, ``coth -> tanh(x)``.
* ``m = 1 mod 4``: ``sinh -> I*cosh(x)``, ``cosh -> I*sinh(x)``,
  ``sech -> -I*csch(x)``, ``csch -> -I*sech(x)``.
* ``m = 3 mod 4``: ``sinh -> -I*cosh(x)``, ``cosh -> -I*sinh(x)``,
  ``sech -> I*csch(x)``, ``csch -> I*sech(x)``.

``m mod 4`` is known when ``m`` is a literal odd integer or when
``(m - 1)/2`` has a known parity (even: 1 mod 4, odd: 3 mod 4).

Exact points, precondition ``x == 0`` (the remainder is literally zero):

* ``m = 2n``, ``n`` integer: ``sinh -> 0``, ``tanh -> 0``,
  ``coth -> zoo``, ``csch -> zoo``; ``cosh`` and ``sech`` give ``1``/``-1``
  for a known parity and ``(-1)**n`` otherwise.
* ``m`` odd: ``cosh -> 0``, ``coth -> 0``, ``tanh -> zoo``,
  ``sech -> zoo``; with ``m mod 4`` known, ``sinh -> I`` / ``-I`` and
  ``csch -> -I`` / ``I`` (for ``1`` / ``3 mod 4``).

``zoo`` is returned only at the pole itself (remainder zero); a nonzero
remainder never produces ``zoo``.  Since SymPy evaluates ``f(k*pi*I)`` to a
trigonometric function on construction, the exact-point rules only fire for
unevaluated inputs.  ``f(-y)`` is normalised by SymPy itself and not handled
here.  Shifts by real multiples of ``pi`` are not shifts of the period and
never fire (``split_shift`` keeps such terms in the remainder).
"""
from __future__ import annotations

from typing import Any, Callable

from sympy import I, S, pi, zoo
from sympy.core.expr import Expr
from sympy.functions.elementary.hyperbolic import (
    cosh, coth, csch, sech, sinh, tanh)

from ...identities.compat.upstream import handlers_dict
from ._common import is_integer, parity, split_shift

# Result classes of the shift.
_PERIOD_EVEN = "0 mod 4"      # x + n*pi*I, n even
_PERIOD_ODD = "2 mod 4"       # x + n*pi*I, n odd
_PERIOD_INT = "integer"       # x + n*pi*I, parity unknown
_HALF_ONE = "1 mod 4"         # x + m*pi*I/2, m = 1 mod 4
_HALF_THREE = "3 mod 4"       # x + m*pi*I/2, m = 3 mod 4
_HALF_ODD = "odd"             # x + m*pi*I/2, m odd, residue unknown


def _classify(arg: Expr, assumptions: Any) -> tuple[str, Expr, Expr] | None:
    """Return ``(class, m, x)`` for ``arg = m*pi*I/2 + x``, or ``None``."""
    m, x = split_shift(arg, pi * I / 2)
    if m.is_zero:
        return None
    n = m / 2
    if is_integer(n, assumptions):
        p = parity(n, assumptions)
        if p == "even":
            return _PERIOD_EVEN, m, x
        if p == "odd":
            return _PERIOD_ODD, m, x
        return _PERIOD_INT, m, x
    if m.is_Integer:
        # literal and not even, hence odd
        return (_HALF_ONE if int(m) % 4 == 1 else _HALF_THREE), m, x
    if parity(m, assumptions) != "odd":
        return None
    p = parity((m - 1) / 2, assumptions)
    if p == "even":
        return _HALF_ONE, m, x
    if p == "odd":
        return _HALF_THREE, m, x
    return _HALF_ODD, m, x


Table = dict[str, Callable[[Expr, Expr], Expr]]
ZeroTable = dict[str, Callable[[Expr], Expr]]


def _apply(expr: Expr, assumptions: Any, table: Table,
           at_zero: ZeroTable) -> Expr | None:
    """Look up the rule for the class of ``expr.args[0]``.

    ``table`` maps a class to ``rule(x, m)``; ``at_zero`` maps a class to
    ``value(m)`` used only when the remainder ``x`` is exactly zero (the
    ``table`` rules, evaluated at ``x = 0``, already give the other exact
    values, including ``zoo`` at poles).
    """
    found = _classify(expr.args[0], assumptions)
    if found is None:
        return None
    cls, m, x = found
    if x.is_zero and cls in at_zero:
        return at_zero[cls](m)
    rule = table.get(cls)
    if rule is None:
        return None
    return rule(x, m)


_SINH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: sinh(x),
        _PERIOD_ODD: lambda x, m: -sinh(x),
        _HALF_ONE: lambda x, m: I * cosh(x),
        _HALF_THREE: lambda x, m: -I * cosh(x),
    },
    {_PERIOD_INT: lambda m: S.Zero},
)


def refine_sinh(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``sinh(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_SINH_RULES)


_COSH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: cosh(x),
        _PERIOD_ODD: lambda x, m: -cosh(x),
        _HALF_ONE: lambda x, m: I * sinh(x),
        _HALF_THREE: lambda x, m: -I * sinh(x),
    },
    {_PERIOD_INT: lambda m: S.NegativeOne ** (m / 2),
     _HALF_ODD: lambda m: S.Zero},
)


def refine_cosh(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``cosh(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_COSH_RULES)


_TANH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: tanh(x),
        _PERIOD_ODD: lambda x, m: tanh(x),
        _PERIOD_INT: lambda x, m: tanh(x),
        _HALF_ONE: lambda x, m: coth(x),
        _HALF_THREE: lambda x, m: coth(x),
        _HALF_ODD: lambda x, m: coth(x),
    },
    {},
)


def refine_tanh(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``tanh(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_TANH_RULES)


_COTH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: coth(x),
        _PERIOD_ODD: lambda x, m: coth(x),
        _PERIOD_INT: lambda x, m: coth(x),
        _HALF_ONE: lambda x, m: tanh(x),
        _HALF_THREE: lambda x, m: tanh(x),
        _HALF_ODD: lambda x, m: tanh(x),
    },
    {},
)


def refine_coth(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``coth(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_COTH_RULES)


_SECH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: sech(x),
        _PERIOD_ODD: lambda x, m: -sech(x),
        _HALF_ONE: lambda x, m: -I * csch(x),
        _HALF_THREE: lambda x, m: I * csch(x),
    },
    {_PERIOD_INT: lambda m: S.NegativeOne ** (m / 2),
     _HALF_ODD: lambda m: zoo},
)


def refine_sech(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``sech(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_SECH_RULES)


_CSCH_RULES: tuple[Table, ZeroTable] = (
    {
        _PERIOD_EVEN: lambda x, m: csch(x),
        _PERIOD_ODD: lambda x, m: -csch(x),
        _HALF_ONE: lambda x, m: -I * sech(x),
        _HALF_THREE: lambda x, m: I * sech(x),
    },
    {_PERIOD_INT: lambda m: zoo},
)


def refine_csch(expr: Expr, assumptions: Any) -> Expr | None:
    """Refine ``csch(x + m*pi*I/2)``; see the module docstring."""
    return _apply(expr, assumptions, *_CSCH_RULES)


handlers_dict['sinh'] = refine_sinh
handlers_dict['cosh'] = refine_cosh
handlers_dict['tanh'] = refine_tanh
handlers_dict['coth'] = refine_coth
handlers_dict['sech'] = refine_sech
handlers_dict['csch'] = refine_csch
