"""Helpers the table modules share (the authors' side of the engine).

The family modules import everything they use from here: the engine's
table API (``Row``, ``identity_handler``, ``rule_handler``, ``part``,
re-exported from :mod:`..core`), the wrap ``principal`` and the helpers below.

``chain`` registers several handlers on one key: rule rows are tried
before identity rows, and because only the identity handler switches
itself off while evaluating a candidate, nested nodes of the same head are
still reduced by the rules inside a candidate.  ``ZERO`` is the one generic
row every unary family registers.  ``node_measure`` is the ordering the
complex-part identities use: fewer nodes of the family first, then smaller
arguments, so ``Abs(x*y)`` is left alone unless a factor resolves.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from sympy import Function, Q, Symbol
from sympy.core import Add, Mul

from ..core.rewrite import Row, _is_negation, derive, identity_handler, part, rule_handler, size
from ._wraps import principal

__all__ = ["ZERO", "Row", "chain", "compile_rule", "compile_table", "derive", "exp_node_measure", "identity_handler",
           "negative_number_base_measure", "node_measure", "part", "principal", "rule_handler"]

Handler = Callable[[Any, Any], Any]


def chain(*handlers: Handler) -> Handler:
    """One handler from several: the first non-``None`` result wins."""
    def handler(expr: Any, assumptions: Any) -> Any:
        for h in handlers:
            out = h(expr, assumptions)
            if out is not None:
                return out
        return None
    handler.parts = handlers  # type: ignore[attr-defined]
    return handler


_F = Function('F')
_x = Symbol('x')

ZERO = (_F(_x), _F(0), Q.zero(_x))
"""``f(x) == f(0)`` when ``x`` is zero; ``f(0)`` evaluates in SymPy (``cot(0)`` is ``zoo``)."""


def node_measure(heads: Iterable[type]) -> Callable[[Any, Any], tuple]:
    """``(nodes, structure, size)``: the number of nodes whose head is in
    ``heads``, the factors or terms under them, then ``count_ops`` (:func:`._engine.size`)."""
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


def compile_rule(lhs: Any, rhs: Any, hyp: Any, unless: Any = None) -> Callable[[Any, Any], Any]:
    """One rule row as a handler (see :func:`..core.rewrite.rule_handler`)."""
    return rule_handler([(lhs, rhs, hyp, unless)])


def compile_table(rules: Iterable) -> Callable[[Any, Any], Any]:
    """A rule table as a handler; rows ``(lhs, rhs, hypothesis[, unless])`` in table order."""
    return rule_handler(list(rules))
