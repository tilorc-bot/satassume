"""Lightweight propositional formulas over opaque atoms.

Atoms are ``P(pred, expr)``: a predicate name applied to an opaque, hashable
expression (a SymPy object in practice, but this module never imports SymPy).
Formulas are compiled to integer clauses by :mod:`satassume.compile`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Tuple


@dataclass(frozen=True)
class P:
    """Atomic proposition ``pred(expr)``."""
    pred: str
    expr: Any

    def __repr__(self) -> str:
        return f"{self.pred}({self.expr})"

    def __invert__(self) -> "Not":
        return Not(self)

    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __rshift__(self, other):
        return Implies(self, other)


class Formula:
    __slots__ = ("args",)

    def __init__(self, *args):
        self.args = tuple(args)

    def __repr__(self):
        return f"{type(self).__name__}{self.args}"

    def __eq__(self, other):
        return type(self) is type(other) and self.args == other.args

    def __hash__(self):
        return hash((type(self).__name__, self.args))

    def __invert__(self):
        return Not(self)

    def __and__(self, other):
        return And(self, other)

    def __or__(self, other):
        return Or(self, other)

    def __rshift__(self, other):
        return Implies(self, other)


class And(Formula):
    pass


class Or(Formula):
    pass


class Not(Formula):
    def __init__(self, arg):
        super().__init__(arg)


class Implies(Formula):
    def __init__(self, a, b):
        super().__init__(a, b)


class Equivalent(Formula):
    def __init__(self, *args):
        super().__init__(*args)


class Exclusive(Formula):
    """At most one of the arguments is true (pairwise exclusion)."""


TRUE = True
FALSE = False

Node = Any


def allargs(pred: str, args: Iterable[Node]):
    """``pred`` holds for every argument."""
    args = tuple(args)
    return And(*[P(pred, a) for a in args]) if args else TRUE


def anyarg(pred: str, args: Iterable[Node]):
    """``pred`` holds for at least one argument."""
    args = tuple(args)
    return Or(*[P(pred, a) for a in args]) if args else FALSE


def exactlyonearg(pred: str, args: Iterable[Node]):
    """``pred`` holds for exactly one argument."""
    args = tuple(args)
    if not args:
        return FALSE
    atoms = [P(pred, a) for a in args]
    return And(Or(*atoms), Exclusive(*atoms))


def atoms_of(f) -> Tuple[P, ...]:
    """All atoms occurring in a formula, in first-seen order."""
    out = []
    seen = set()

    def walk(g):
        if isinstance(g, P):
            if g not in seen:
                seen.add(g)
                out.append(g)
        elif isinstance(g, Formula):
            for a in g.args:
                walk(a)

    walk(f)
    return tuple(out)
