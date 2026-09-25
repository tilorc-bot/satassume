"""Turn SymPy relation atoms into :mod:`satassume.lra` payloads.

This is the only LRA module that imports SymPy.  Interpreted atoms:

* ``Q.lt/le/gt/ge/eq/ne(a, b)`` (applied predicates with two arguments),
* the Relationals ``a < b``, ``a <= b``, ``a > b``, ``a >= b``,
  ``Eq(a, b)``, ``Ne(a, b)``,
* ``Q.is_true(r)`` for such a Relational ``r``.

Rules
-----

``a - b`` is linearised structurally (no ``expand``, no simplification):
sums are split, a product with a rational numeric factor is scaled
(``2*(x + y)`` is ``2*x + 2*y``), and every other subexpression with free
symbols (``x``, ``x*y``, ``sin(x)``, ``x**2``, ``f(x)``) is an *opaque
term*, an independent real variable for the theory.  Treating a nonlinear
term as a variable is a relaxation, so it is sound (only incomplete).

The atom is not interpreted (``None``) if

* an argument is not a scalar ``Expr`` (booleans, tuples, matrices,
  matrix expressions), or the arity is not 2;
* anything in it is ``nan``, ``oo``, ``-oo`` or ``zoo`` (even inside an
  opaque term, e.g. ``x + oo`` or ``sin(x + oo)``);
* a numeric coefficient or constant is not a SymPy ``Rational``: floats,
  ``I``, ``pi``, ``sqrt(2)``, ``E``, and any subexpression without free
  symbols that is not a rational number (``f(1)``, ``sin(1)``).

No SymPy assumptions are consulted.  **The caller vouches that every opaque
term (see :func:`terms`) is a finite real**: the theory reads
``not (a < b)`` as ``a >= b`` and ``Q.lt(x, x + 1)`` as true, which is only
right for finite reals.  The engine guarantees this with bridge clauses
``real(u1) & ... & real(uk) -> (atom <-> theory atom)``.  That is why
:func:`terms` includes terms that cancel (``x`` in ``Q.lt(x, x + 1)``).

Equalities and disequalities alone would even be sound over the complex
numbers (a rational linear system with disequalities that has a complex
solution has a real one), but order atoms need real terms, so the one rule
above covers both.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

from sympy import S
from sympy.assumptions.assume import AppliedPredicate
from sympy.assumptions.ask import Q
from sympy.core.add import Add
from sympy.core.expr import Expr
from sympy.core.mul import Mul
from sympy.core.relational import (Equality, GreaterThan, LessThan,
                                   StrictGreaterThan, StrictLessThan,
                                   Unequality)
from sympy.core.sorting import default_sort_key

from .lra import LRATheory, Negated

__all__ = ["LRAAdapter", "to_constraint", "terms", "interpret", "relation"]

_PRED = {Q.lt: "lt", Q.le: "le", Q.gt: "gt", Q.ge: "ge", Q.eq: "eq",
         Q.ne: "ne"}
_REL = {StrictLessThan: "lt", LessThan: "le", StrictGreaterThan: "gt",
        GreaterThan: "ge", Equality: "eq", Unequality: "ne"}
_BAD = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


class _Unhandled(Exception):
    pass


def relation(atom) -> tuple[str, Any, Any] | None:
    """``(name, lhs, rhs)`` for a supported relation atom, name one of
    ``lt le gt ge eq ne``; None otherwise."""
    if isinstance(atom, AppliedPredicate):
        f = atom.function
        if f == Q.is_true:
            return relation(atom.arguments[0]) if len(atom.arguments) == 1 else None
        name = _PRED.get(f)
        if name is None or len(atom.arguments) != 2:
            return None
        return (name,) + tuple(atom.arguments)
    name = _REL.get(type(atom))
    if name is None:
        return None
    return name, atom.lhs, atom.rhs


def _lin(e, scale: Fraction, out: dict, const: list) -> None:
    """Add ``scale * e`` to the linear form ``out`` (term -> coefficient)
    and ``const[0]``."""
    if not isinstance(e, Expr) or getattr(e, "is_Matrix", False) \
            or getattr(e, "is_MatrixExpr", False):
        raise _Unhandled(e)
    if not e.free_symbols:
        if e.is_Rational:
            const[0] += scale * Fraction(int(e.p), int(e.q))
            return
        raise _Unhandled(e)
    if e.is_Add:
        for a in e.args:
            _lin(a, scale, out, const)
        return
    if e.is_Mul:
        coeff = S.One
        rest = []
        for f in e.args:
            if f.free_symbols:
                rest.append(f)
            elif f.is_Rational:
                coeff *= f
            else:
                raise _Unhandled(f)          # I*x, pi*x, 0.5*x, sqrt(2)*x
        if coeff != 1:
            _lin(Mul(*rest), scale * Fraction(int(coeff.p), int(coeff.q)),
                 out, const)
            return
        if len(rest) == 1:
            _lin(rest[0], scale, out, const)
            return
    out[e] = out.get(e, Fraction(0)) + scale


def _linear(name, lhs, rhs):
    """``(form, constant)`` with form ``{term: coeff}`` (zeros kept) for
    ``lhs - rhs``; raises _Unhandled."""
    for side in (lhs, rhs):
        if not isinstance(side, Expr) or side.has(*_BAD):
            raise _Unhandled(side)
    form: dict = {}
    const = [Fraction(0)]
    _lin(lhs, Fraction(1), form, const)
    _lin(rhs, Fraction(-1), form, const)
    return form, const[0]


def to_constraint(atom):
    """Interpret ``atom``.

    Returns ``(payload, positive)`` where ``payload`` is an
    :mod:`satassume.lra` record ``(terms, constant, strict, equality)`` and
    ``positive`` is False when the atom is the negation of the payload
    (``Q.ne``/``Ne``); ``True``/``False`` when the relation has no terms
    left (its value for all finite reals); None when not interpreted.

    ``Q.lt(x, y)`` and ``Q.gt(y, x)`` give equal payloads, as do
    ``Q.eq(x, y)`` and ``Q.eq(y, x)``.
    """
    r = interpret(atom)
    return None if r is None else r[0]


def _constraint(name, form, k):
    if name in ("gt", "ge"):                 # a > b  <=>  b - a < 0
        form = {t: -c for t, c in form.items()}
        k = -k
        name = "lt" if name == "gt" else "le"
    items = sorted(((t, c) for t, c in form.items() if c),
                   key=lambda tc: default_sort_key(tc[0]))
    if name in ("eq", "ne") and items and items[0][1] < 0:
        items = [(t, -c) for t, c in items]
        k = -k
    positive = name != "ne"
    # sum(items) + k OP 0  <=>  sum(items) OP -k
    if not items:
        value = {"lt": k < 0, "le": k <= 0, "eq": k == 0, "ne": k != 0}[name]
        return value
    payload = (tuple(items), -k, name == "lt", name in ("eq", "ne"))
    return payload, positive


def interpret(atom):
    """``(to_constraint(atom), terms(atom))`` from a single linearisation,
    or None when the atom is not interpreted."""
    rel = relation(atom)
    if rel is None:
        return None
    try:
        form, k = _linear(*rel)
    except (_Unhandled, TypeError, ValueError):
        return None
    return _constraint(rel[0], form, k), sorted(form, key=default_sort_key)


def terms(atom) -> list | None:
    """The opaque terms of ``atom`` (including ones that cancel, e.g.
    ``[x]`` for ``Q.lt(x, x + 1)``), in a canonical order; ``[]`` for a
    purely numeric relation; None if the atom is not interpreted."""
    r = interpret(atom)
    return None if r is None else r[1]


#: atom -> interpret(atom), shared by every adapter (keyed by the SymPy
#: atom itself: equal atoms linearise identically)
_INTERPRETED: dict = {}
_INTERPRETED_MAX = 100_000


class LRAAdapter:
    """Registers SymPy relation atoms with one :class:`LRATheory`.

    ``register(solver, var, atom)`` interprets ``atom``; on success it
    attaches the theory to ``solver`` (first time only; an adapter serves
    one solver, a second one raises ValueError), registers solver
    variable ``var`` for it and returns True.  A relation without terms is
    registered as a ground atom (the theory fixes its value).  ``Q.ne`` is
    accepted too (``var`` then means the disequality).  Returns False, and
    registers nothing, when the atom is not interpreted.
    """

    def __init__(self, theory: LRATheory | None = None) -> None:
        self.theory = theory if theory is not None else LRATheory()
        self._solver = None
        self._shared: set = set()

    def register(self, solver, var: int, atom, interpreted=None) -> bool:
        """``interpreted``: optionally the result of :func:`interpret`
        for ``atom`` already at hand (saves a second linearisation).

        An adapter owns one theory and so serves a single solver: a
        second solver raises ValueError (the theory's bounds would leak
        between them)."""
        it = self.interpret(atom) if interpreted is None else interpreted
        if it is None:
            return False
        r, atom_terms = it
        if r is True or r is False:
            payload: Any = ((), Fraction(0) if r else Fraction(-1), False, False)
        else:
            payload, positive = r
            if not positive:
                payload = Negated(payload)
        if self._solver is not solver:
            if self._solver is not None:
                raise ValueError("an LRAAdapter serves a single solver")
            if not any(t is self.theory for t in solver.theories()):
                solver.attach_theory(self.theory)
            self._solver = solver
        solver.register_atom(self.theory, var, payload)
        self._shared.update(atom_terms)
        return True

    def interpret(self, atom):
        """``(constraint, terms)`` in one call (see :func:`interpret`),
        memoized across adapters: it is a pure function of the atom (the
        result is shared, never mutate it)."""
        try:
            return _INTERPRETED[atom]
        except KeyError:
            if len(_INTERPRETED) >= _INTERPRETED_MAX:
                _INTERPRETED.clear()
            r = _INTERPRETED[atom] = interpret(atom)
            return r
        except TypeError:                   # unhashable: do not cache
            return interpret(atom)

    def terms(self, atom) -> list | None:
        """:func:`terms` through the cache; None: not interpreted."""
        r = self.interpret(atom)
        return None if r is None else r[1]

    def to_constraint(self, atom):
        """:func:`to_constraint` through the cache."""
        r = self.interpret(atom)
        return None if r is None else r[0]

    def shared_terms(self) -> set:
        """Every opaque term of every atom registered through this adapter."""
        return set(self._shared)
