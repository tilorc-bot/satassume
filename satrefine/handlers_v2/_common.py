"""Helpers shared by the ``handlers_v2`` modules.

Every predicate question goes through :func:`truth`, which calls
``satrefine._upstream.ask`` through the module attribute at call time, so
patching ``_upstream.ask`` in a test reaches every handler.  The other
helpers encode the small pieces of reasoning that several handlers need:

* :func:`holds` / :func:`fails`: "provably true" / "provably false".
* :func:`known_parity`: whether an expression is a provably even or odd
  integer.
* :func:`zero_argument`: the generic rule ``f(x) -> f(0)`` when ``x`` is
  provably zero (sound for every function; it only reuses SymPy's own value
  at ``0``).
* :func:`split_shift`: decompose an argument ``rem + k*unit/2`` where ``k``
  is an integer of known parity, the workhorse of the trigonometric and
  hyperbolic shift rules.
* :func:`positive_factors`: split a product into provably positive factors
  and the rest (``log``, ``arg``, ``sign`` and ``Pow`` pull those out).
* :func:`term_coefficient`: the coefficient of ``pi`` (or ``pi*I``) in a
  single term, when it is free of ``pi`` and ``I``.
"""
from __future__ import annotations

from typing import Any, Callable

from sympy.assumptions import Q
from sympy.core import Add, Basic, Mul, S
from sympy.core.numbers import I, pi
from sympy.core.sympify import sympify

from .. import _upstream

Assumptions = Any
Handler = Callable[[Basic, Assumptions], "Basic | None"]


def truth(proposition: Basic, assumptions: Assumptions) -> bool | None:
    """Ask the selected backend (through ``_upstream.ask``)."""
    return _upstream.ask(proposition, assumptions)


def holds(proposition: Basic, assumptions: Assumptions) -> bool:
    """``True`` only when the proposition is provably true."""
    return truth(proposition, assumptions) is True


def fails(proposition: Basic, assumptions: Assumptions) -> bool:
    """``True`` only when the proposition is provably false."""
    return truth(proposition, assumptions) is False


def relation_holds(proposition: Basic, assumptions: Assumptions) -> bool:
    """:func:`holds` for a binary relation (``Q.ge``, ``Q.lt``, ...).

    SymPy's relational ``ask`` sometimes raises ``ValueError("inconsistent
    assumptions")`` for consistent unary assumptions (for example
    ``Q.ge(x, y)`` under ``Q.positive(x) & Q.negative(y) & Q.negative(z)``);
    such an answer is taken as "unknown" rather than propagated.
    """
    try:
        return holds(proposition, assumptions)
    except ValueError:
        return False


def is_nonzero(expr: Basic, assumptions: Assumptions) -> bool:
    """Provably not zero, for real *or* complex values.

    ``Q.nonzero`` in SymPy means "real and not zero", so a complex value is
    tested through the negation of ``Q.zero`` instead.
    """
    return fails(Q.zero(expr), assumptions)


def known_parity(expr: Basic, assumptions: Assumptions) -> bool | None:
    """``True`` for a provably even integer, ``False`` for a provably odd
    one, ``None`` otherwise."""
    if holds(Q.even(expr), assumptions):
        return True
    if holds(Q.odd(expr), assumptions):
        return False
    return None


def zero_argument(expr: Basic, assumptions: Assumptions) -> Basic | None:
    """``f(x) -> f(0)`` when the single argument ``x`` is provably zero.

    Returns ``None`` unless the value at zero differs from ``expr``.
    """
    if len(expr.args) != 1:
        return None
    if not holds(Q.zero(expr.args[0]), assumptions):
        return None
    value = expr.func(S.Zero)
    if value == expr:
        return None
    return value


def term_coefficient(term: Basic, unit: Basic) -> Basic | None:
    """The ``c`` in ``term == c*unit`` when ``c`` is free of ``pi`` and ``I``.

    ``unit`` is ``pi`` (trigonometric shifts) or ``pi*I`` (hyperbolic
    shifts).  Anything else, including a coefficient that still contains
    ``pi`` or ``I``, answers ``None``.
    """
    coefficient = term.as_coefficient(unit)
    if coefficient is None or coefficient.has(pi, I):
        return None
    return coefficient


def split_shift(arg: Basic, unit: Basic, assumptions: Assumptions,
                ) -> tuple[Basic, Basic, bool] | None:
    """Split ``arg`` into ``rem + k*unit/2`` with ``k`` of known parity.

    Every additive term ``c*unit`` with ``2*c`` a provably even or odd
    integer is moved into ``k`` (the sum of those ``2*c``).  Terms whose
    ``2*c`` is an integer of unknown parity stay in ``rem``: nothing sound
    can be said about them.  Returns ``(rem, k, k_is_even)`` or ``None``
    when no term qualifies.
    """
    shift_terms: list[Basic] = []
    remaining: list[Basic] = []
    k_is_even = True
    for term in Add.make_args(arg):
        coefficient = term_coefficient(term, unit)
        if coefficient is None:
            remaining.append(term)
            continue
        half_units = 2 * coefficient
        parity = known_parity(half_units, assumptions)
        if parity is None:
            remaining.append(term)
            continue
        shift_terms.append(half_units)
        k_is_even = k_is_even == parity
    if not shift_terms:
        return None
    return Add(*remaining), Add(*shift_terms), k_is_even


def positive_factors(product: Basic, assumptions: Assumptions,
                     ) -> tuple[list[Basic], list[Basic]]:
    """Split the factors of ``product`` into provably positive ones and the
    rest, in the original order."""
    positives: list[Basic] = []
    rest: list[Basic] = []
    for factor in Mul.make_args(product):
        if holds(Q.positive(factor), assumptions):
            positives.append(factor)
        else:
            rest.append(factor)
    return positives, rest


def integer_valued(expr: Basic) -> Basic:
    """Sympify Python numbers that SymPy helpers (``as_powers_dict``) hand out."""
    return sympify(expr)


def first_of(*handlers: Handler) -> Handler:
    """Combine handlers: the first one returning a value wins."""
    def handler(expr: Basic, assumptions: Assumptions) -> Basic | None:
        for candidate in handlers:
            result = candidate(expr, assumptions)
            if result is not None:
                return result
        return None
    return handler
