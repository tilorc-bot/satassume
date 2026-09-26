"""Helpers the table modules share (the authors' side of the engine).

The family modules import everything they use from here: the engine's
table API (``Row``, ``part`` and the spec classes ``Family``, ``Rules``,
``Identities``, re-exported from :mod:`..core`), the wrap ``principal`` and
the helpers below.

``ZERO`` is the one generic row every unary family registers.  ``node_measure`` is the ordering the
complex-part identities use: fewer nodes of the family first, then smaller
arguments, so ``Abs(x*y)`` is left alone unless a factor resolves.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from sympy import And, Function, Q, Symbol, exp
from sympy.core import Add, Mul

from ..core.match import part
from ..core.rewrite import Row, _is_negation, size
from ..core.spec import Family, Identities, Rules
from ._wraps import principal

__all__ = ["ZERO", "Family", "Identities", "Row", "Rules", "derive", "exp_node_measure",
           "negative_number_base_measure", "node_measure", "part", "principal"]


_F = Function('F')
_x = Symbol('x')

ZERO = (_F(_x), _F(0), Q.zero(_x))
"""``f(x) == f(0)`` when ``x`` is zero; ``f(0)`` evaluates in SymPy (``cot(0)`` is ``zoo``)."""


def node_measure(heads: Iterable[type]) -> Callable[[Any, Any], tuple]:
    """``(nodes, structure, size)``: the number of nodes whose head is in
    ``heads``, the factors or terms under them, then ``count_ops`` (:func:`..core.rewrite.size`)."""
    heads = tuple(heads)

    def measure(e: Any, assumptions: Any) -> tuple:
        nodes = list(e.atoms(*heads))
        structure = 0
        for node in nodes:
            a = node.args[0] if node.args else node
            if _is_negation(a):
                continue
            if isinstance(a, (Add, Mul)):
                structure += len(a.args)
            elif not a.is_Atom:
                structure += 1
        return (len(nodes), structure, size(e))
    return measure


def exp_node_measure(e: Any, assumptions: Any) -> tuple:
    """``(exp nodes, size)``: the ordering for ``exp(a + b) -> exp(a)*exp(b)``, which
    must fire only when a factor evaluates away (``exp(log(Abs(p)))``)."""
    from sympy import exp
    return (len(e.atoms(exp)), size(e))


def negative_number_base_measure(e: Any, assumptions: Any) -> tuple:
    """``(powers of a negative number, size)``: the ordering for ``c**n -> (-c)**n``
    rows, which must not fire for a symbolic base (SymPy's ``Pow._eval_refine``
    rewrites ``(-x)**n`` back to ``-x**n`` for odd ``n``, a cycle)."""
    from sympy.core import Pow
    negative = sum(1 for node in e.atoms(Pow) if node.base.is_number and node.base.is_negative)
    return (negative, size(e))


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
