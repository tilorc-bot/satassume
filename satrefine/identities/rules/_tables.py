"""Helpers the table modules share (the authors' side of the engine).

The family modules import everything they use from here: the engine's
table API (``Row``, ``part``, ``exponent``, the orderings ``node_measure`` and
``count_measure`` with their tie-breaker ``size``, and the spec classes ``Family``, ``Rules``, ``Identities``,
re-exported from :mod:`..core`), the wrap ``principal`` and the helpers below.

``ZERO`` is the one generic row every unary family registers; the orderings
tables pass as ``measure=`` are in :mod:`..core.measure`.
"""
from __future__ import annotations

from sympy import And, Function, Q, Symbol, exp

from ..core.match import exponent, part
from ..core.measure import count_measure, node_measure, size
from ..core.rewrite import Row
from ..core.spec import Family, Identities, Rules
from ._wraps import principal

__all__ = ["ZERO", "Family", "Identities", "Row", "Rules", "count_measure", "derive", "exponent", "node_measure", "part",
           "principal", "size"]


_F = Function('F')
_x = Symbol('x')

ZERO = (_F(_x), _F(0), Q.zero(_x))
"""``f(x) == f(0)`` when ``x`` is zero; ``f(0)`` evaluates in SymPy (``cot(0)`` is ``zoo``)."""


def derive(facts: list[Row], exp_forms: list[Row]) -> list[Row]:
    """Compose each ``g(exp(z))`` fact with each exponential form ``(L, W, domain)``
    (``L == exp(W)``) into the row ``g(L) == rhs[z := W]`` under both domains."""
    rows: list[Row] = []
    for lhs, rhs, dom in facts:
        rows.append((lhs, rhs, dom))
        if lhs.args and isinstance(lhs.args[0], exp) and lhs.args[0].args[0].is_Symbol:
            zz = lhs.args[0].args[0]
            for L, W, dom_d in exp_forms:
                rows.append((lhs.func(L, *lhs.args[1:]), rhs.xreplace({zz: W}), And(dom, dom_d)))
    return rows
