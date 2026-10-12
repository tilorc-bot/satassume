"""Helpers the table modules share (the authors' side of the engine).

The family modules import everything they use from here: the engine's
table API (``Row``, ``part``, ``exponent``, the marker ``by_cases`` for a
condition that may hold only by cases), the wrap ``principal`` and the
helpers below.  A family module states rows only; which handlers serve which
key, with which orderings, is :mod:`..wiring`.

``ZERO`` is the generic row ``f(x) -> f(0)`` for a zero ``x``, used by the
unary families that want it: in their ``RULES`` (``trig``, ``hyperbolic``) or
added in :mod:`..wiring` (``complex_parts``, ``inverse``, ``power_exp_log``).
"""
from __future__ import annotations

from sympy import And, Function, Q, Symbol, exp, true

from ..core.match import exponent, part
from ..core.prove import by_cases
from ..core.rewrite import Row
from ..core.spec import assume as _assume_row
from ._wraps import principal

__all__ = ["ZERO", "Row", "add_rules", "by_cases", "derive", "exponent", "part", "principal"]


_F = Function('F')
_x = Symbol('x')

ZERO = (_F(_x), _F(0), Q.zero(_x))
"""``f(x) == f(0)`` when ``x`` is zero; ``f(0)`` evaluates in SymPy (``cot(0)`` is ``zoo``)."""


def derive(facts: list[Row], exp_forms: list[Row]) -> list[Row]:
    """Compose each ``g(exp(z))`` fact with each exponential form ``(L, W, domain)``
    (``L == exp(W)``) into the row ``g(L) == rhs[z := W]`` under both domains."""
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
    left side holds all their variables, on top of the family's ``ASSUMED``: the
    hypotheses of these rows ("here n is even", "for 0 <= a < d").  A row fires only
    where its hypotheses are proved.  The rows returned are ordinary rows, so a row
    keeps its facts in every table it is reused in."""
    return [_assume_row(row, assume) for row in rows]
