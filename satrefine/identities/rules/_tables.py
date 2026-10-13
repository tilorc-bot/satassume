"""Helpers the table modules share (the authors' side of the engine).

The family modules import everything they use from here: the engine's
table API (``Row``, ``part``, ``exponent``, the marker ``by_cases`` for a
condition that may hold only by cases), the wrap ``principal`` and the
helpers below.  A family module states rows only; which handlers serve which
key, with which orderings, is :mod:`..wiring`.

``ZERO`` is the generic row ``f(x) -> f(0)`` for a zero ``x``; :mod:`..wiring`
puts it first in the tables of the families that use it.
"""
from __future__ import annotations

from sympy import And, Function, Q, S, Symbol, exp, im, re, true

from ..core.match import exponent, part
from ..core.prove import by_cases
from ..core.rewrite import Row
from ..core.spec import assume as _assume_row
from ._wraps import principal

__all__ = ["ZERO", "Row", "add_rules", "by_cases", "derive", "equal", "exponent", "gaussian_integer", "part",
           "principal", "rational_part"]


_F = Function('F')
_x = Symbol('x')

ZERO = (_F(_x), _F(0), Q.zero(_x))
"""``f(x) == f(0)`` when ``x`` is zero; ``f(0)`` evaluates in SymPy (``cot(0)`` is ``zoo``)."""


def equal(a, b):
    """``a == b`` in either form the assumptions may state it: ``Q.zero(a - b)`` or
    ``Q.eq(a, b)``.  Neither is derived from the other when a side may be a non-real
    number, so a hypothesis written with only one would miss the other."""
    return Q.zero(a - b) | Q.eq(a, b)


def gaussian_integer(u):
    """``u`` is an integer or a Gaussian integer (integral real and imaginary parts).
    Both are spelled out because ``ask`` does not derive one from the other, and SymPy
    takes the floor of a complex number part by part, so ``floor(y)`` of a finite ``y``
    is a Gaussian integer (issue #19)."""
    return Q.integer(u) | (Q.integer(re(u)) & Q.integer(im(u)))


def rational_part(name: str) -> Symbol:
    """A pattern symbol binding the rational number term of a sum (``3/2`` in
    ``x + 3/2``), never a symbol, so that ``Mod(h, 2)`` on the right side evaluates."""
    return part(name, lambda t: S(bool(t.is_Rational)))


def derive(facts: list[Row], exp_forms: list[Row]) -> list[Row]:
    """Compose each ``g(exp(z))`` fact with each exponential form ``(L, W, domain)``
    (``L == exp(W)`` wherever ``domain`` holds) into the row ``g(L) == rhs[z := W]``
    under both domains.  The facts themselves are kept too.

    For example ``log(exp(z)) == principal(z)`` with the form ``(b**e, e*log(b), ...)``
    gives ``log(b**e) == principal(e*log(b))``, and with the product forms
    ``(y*r, log(y) + log(r), true)`` and ``(y*r, log(-y) + log(-r), true)`` it gives the
    two rows for ``log(y*r)``; the second is how a negative factor's sign moves to the
    other factor (``log(x*y) = log(-x) + log(-y)`` for negative ``x`` and ``y``).  Under
    assumptions the ``floor`` inside ``principal`` collapses and the familiar rule
    appears (``log(x**a) = a*log(x)`` for positive ``x`` and real ``a``)."""
    rows: list[Row] = []
    for lhs, rhs, *rest in facts:        # a fact may leave its domain to the family's assumptions
        dom = rest[0] if rest else true
        rows.append((lhs, rhs, dom))
        if lhs.args and isinstance(lhs.args[0], exp) and lhs.args[0].args[0].is_Symbol:
            zz = lhs.args[0].args[0]
            for L, W, dom_d in exp_forms:
                rows.append((lhs.func(L, *lhs.args[1:]), rhs.xreplace({zz: W}), And(dom, dom_d)))
    return rows


def add_rules(assume, rows: list) -> list[Row]:
    """``rows`` with the facts in ``assume`` added to the condition of each row whose
    left side holds all their variables, on top of the family's ``ASSUMED`` (if any): the
    hypotheses of these rows ("here n is even", "for 0 <= a < d").  A row fires only
    where its hypotheses are proved.  The rows returned are ordinary rows, so a row
    keeps its facts in every table it is reused in."""
    return [_assume_row(row, assume) for row in rows]
