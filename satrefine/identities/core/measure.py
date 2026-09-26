"""Rewrite orderings: an identity row fires only when its table's measure strictly decreases.

A measure maps ``(e, assumptions)`` to a tuple compared lexicographically.
:func:`default_measure` is the generic one (:func:`.rewrite.identity_handler`
uses it when a table names none); :func:`node_measure` and
:func:`count_measure` are the orderings tables pass as ``measure=``.  All end
with :func:`size` (``count_ops``) as the tie-breaker.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Iterable

from sympy import Q, count_ops
from sympy.core import Add, Mul

from . import hooks

Measure = Callable[[Any, Any], tuple]


@lru_cache(maxsize=8192)
def size(e: Any) -> int:
    """``count_ops(e)``, remembered: the tie-breaker of every rewrite ordering,
    measured again for the same expressions in every pass."""
    return count_ops(e)


def _is_unit(f: Any) -> bool:
    return f.is_number and abs(f) == 1


def _is_negation(a: Any) -> bool:
    """A unit-modulus number (``-1``, ``I``, ``-I``) times an atom: ``-x``, ``-I*x``.

    Such an argument counts as the atom in the orderings, so that
    ``log(x) -> log(-I*x) + I*pi/2`` on the positive imaginary axis is as
    small as ``log(x) -> log(-x) + I*pi`` on the negative real axis."""
    if not isinstance(a, Mul):
        return False
    units = [f for f in a.args if _is_unit(f)]
    rest = [f for f in a.args if f not in units]
    return len(units) >= 1 and len(rest) == 1 and rest[0].is_Atom


def _provably_positive(a: Any, assumptions: Any) -> bool:
    """``a > 0``; for a negation ``-u`` also through ``u < 0`` (the provers do not
    negate the sign of a product: ``Q.positive(-x*y)`` under ``Q.negative(x*y)``)."""
    if hooks.dispatcher.ask(Q.positive(a), assumptions) is True:
        return True
    return a.could_extract_minus_sign() and hooks.dispatcher.ask(Q.negative(-a), assumptions) is True


def _structure(nodes: Iterable, canonical: Any = (), units: bool = True) -> int:
    """The factors or terms of the nodes' arguments (without the unit factors unless
    ``units``), or one for any other non-atomic argument; a negation, or an argument
    headed by ``canonical``, counts nothing."""
    structure = 0
    for node in nodes:
        a = node.args[0] if node.args else node
        if _is_negation(a) or isinstance(a, canonical):
            continue
        if isinstance(a, (Add, Mul)):
            structure += len([f for f in a.args if units or not _is_unit(f)])
        elif not a.is_Atom:
            structure += 1
    return structure


def default_measure(heads: Iterable[type]) -> Measure:
    """The generic rewrite ordering for a table registered on ``heads``.

    ``(structure, badness, size)``: for every node whose head is in
    ``heads``, the number of factors or terms of its argument (a plain
    negation counts as one, ``-x*y`` as ``x*y``, the modulus head
    :data:`.hooks.modulus`, the canonical form rows produce, as nothing), or
    one for a non-atomic argument; then the number of such nodes whose
    argument is not provably positive; then :func:`size`.  A candidate is
    accepted only if this strictly decreases, which is what makes identity
    rows terminate.
    """
    heads = tuple(heads)

    def measure(e: Any, assumptions: Any) -> tuple:
        nodes = [n for n in e.atoms(*heads)] if heads else []
        structure = _structure(nodes, hooks.modulus or (), units=False)
        bad = sum(not _provably_positive(n.args[0], assumptions) for n in nodes if n.args)
        return (structure, bad, size(e))
    return measure


def node_measure(heads: Iterable[type]) -> Measure:
    """``(nodes, structure, size)``: the number of nodes whose head is in
    ``heads``, the factors or terms under them, then :func:`size` (the ordering
    of the complex-part identities: ``Abs(x*y)`` is left alone unless a factor resolves)."""
    heads = tuple(heads)

    def measure(e: Any, assumptions: Any) -> tuple:
        nodes = list(e.atoms(*heads))
        return (len(nodes), _structure(nodes), size(e))
    return measure


def count_measure(heads: Iterable[type]) -> Measure:
    """``(nodes, size)``: the number of nodes whose head is in ``heads``, then
    :func:`size` (``exp(a + b) -> exp(a)*exp(b)`` must fire only when a factor
    evaluates away, ``exp(log(Abs(p)))``)."""
    heads = tuple(heads)

    def measure(e: Any, assumptions: Any) -> tuple:
        return (len(e.atoms(*heads)), size(e))
    return measure
