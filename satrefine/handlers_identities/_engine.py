"""Engine for handlers stated as tables.

Two table kinds, one row shape ``(lhs, rhs, condition)``:

* an **identity** row (:func:`identity_handler`) holds wherever ``condition``
  (its *domain*) does; its right side carries the branch bookkeeping
  explicitly (see :mod:`._wraps`).  It fires when the domain is provable,
  the refined right side contains none of the *opaque* heads (``floor``,
  ``im``, ``arg`` by default) and a rewrite ordering strictly decreases;
* a **rule** row (:func:`rule_handler`) is a conditional rewrite: it fires
  when ``condition`` (its *hypothesis*) is provable through
  ``_upstream.ask``; the right side is substituted as is.

Patterns are ordinary SymPy expressions over plain symbols:

``x``
    a symbol binds anything (the same symbol twice must bind equal parts);
``p*r``, ``a + b`` (two symbols)
    one factor or term against the rest, once per factor or term
    (linear; no commutative search); a non-product does not match ``p*r``;
``e*log(b)``, ``w*conjugate(w)*r`` (a *rest* symbol beside structure)
    a product or sum of any arity with exactly one plain symbol that
    appears nowhere else in it: the other parts are matched against that
    many factors (terms) of a target of the same head, in every order, and
    the rest symbol binds the product (sum) of the remaining ones (``1`` or
    ``0`` when none remain);
``w*conjugate(w)`` (at the top of a left side, no rest symbol)
    also matches that many factors of a longer product (terms of a longer
    sum); the right side replaces them and the other factors are kept;
``n*unit + r`` (``n``, ``r`` symbols; ``unit`` constant, e.g. ``pi/2``)
    ``n`` binds the sum of the coefficients of ``unit`` over the terms whose
    ratio to ``unit`` is free of ``pi`` and ``I`` (as ``handlers_v3``'s
    ``split_shift``), ``r`` the remaining terms; then, if the coefficients
    have several terms (``I*pi*(n + y)`` counts as two), each single one
    against the rest;
``part('a', pred) + b``, ``part('a', pred) * b``
    ``a`` binds the sum (product) of the terms (factors) for which
    ``pred(term)`` is provable, ``b`` the rest (``0`` or ``1`` when empty);
    no binding when no term qualifies; a non-sum is one term;
``F(x)`` with ``F = Function('F')``
    a head wildcard: matches the applied function the row is registered
    for, ``F`` binds its class and may appear in the right side;
``Max(a, b)``, ``Min(a, b)`` (two symbols, at the top of a left side)
    every ordered pair of two distinct arguments of a ``Max``/``Min`` of any
    arity; the right side replaces the pair and the other arguments are
    kept (``Max(x, y, z) -> Max(rhs, z)``);
``Z`` a ``MatrixSymbol``
    binds a plain ``MatrixSymbol`` only, and its shape symbols bind that
    matrix's shape; ``Z + R``, ``HadamardProduct(Z, R)`` bind one atom
    term and the rest (the rest binds ``R`` with its shape); ``c*Z`` over a
    ``MatMul`` binds one scalar factor and the product of the others;
    a ``MatMul`` of matrix factors (at the top of a left side) matches any
    run of adjacent factors, the right side replaces the run and the other
    factors stay in order, simplified with ``doit(deep=False)``;
anything else
    structural: same head, same arity, arguments matched pairwise; atoms
    and constants must be equal.  Bindings to ``0`` or ``1`` are legal.

Conditions are decided connective by connective (:func:`provable`): an
``And`` needs every part provable and stops at the first that is not, an
``Or`` one, atoms are asked one at a time through ``_upstream.ask``
(relations last: they are the expensive ones) and an ``ask`` that raises
(SymPy's relation theory does, on consistent facts) counts as not provable.  A sign or realness atom ``ask`` leaves open is
decided from the bounds the assumptions state on its argument
(``Q.real(t)`` and ``Q.nonpositive(t)`` under ``Q.ge(t, -pi) & Q.le(t,
0)``, ``Q.integer(t/pi + 1/2)`` refuted under ``Q.gt(t, -pi/2) & Q.lt(t,
pi/2)``; see :func:`._simple.stated_bounds`).  The bounds are on the
extended reals: ``Q.gt(t, 1)`` holds at ``t = oo``, so a bound proves
``Q.extended_real`` and the ``extended_*`` signs, and ``Q.real`` or a finite
sign only when infinity is excluded too (:func:`_from_bounds`; issue #10,
B1-B7).  A rule row may carry a fourth element ``unless``:
it fires only if ``unless`` is *not* provable.  Rows are tried in table
order.

The conditions of a ``Piecewise`` (a definition's right side, or any
``Piecewise`` refined) are decided by :func:`decide`: relations (``Q.ge``,
``Q.lt``, ``Q.eq``, ``Q.ne``, ..., and relationals ``x >= y``) through an
order vocabulary (:data:`ORDER`) of proof forms from signs and infinite
endpoints and from stated relations, the latter unused when an argument is
known infinite (SymPy's ``ask`` proves ``Q.eq(x, y)`` for ``x = -oo`` and
``y <= 0``).  A candidate with a ``Piecewise`` the input did not have is
not a rewrite (the conditions are undecided) and no case split is tried
on it; a table may also switch case splits off (``splits=False``).

:func:`derive` composes a ``g(exp(z))`` fact with exponential forms
``(L, W, domain)`` (``L == exp(W)``) into rows for ``g(L)``.  The dispatcher
these handlers run under is :mod:`._dispatch`.
"""
from __future__ import annotations

import itertools
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Callable, Iterable, Iterator, NamedTuple

from sympy import (Abs, And, Dummy, I, Not, Or, Piecewise, Q, S, Symbol, arg, ceiling, count_ops, exp, expand_mul,
                   floor, im, log, nan, simplify, zoo)
from sympy.assumptions import AppliedPredicate
from sympy.core import Add, Basic, Expr, Mul, Pow
from sympy.core.sympify import sympify
from sympy.core.function import AppliedUndef, UndefinedFunction
from sympy.core.operations import LatticeOp
from sympy.core.relational import Relational
from sympy.matrices.expressions import HadamardProduct, MatAdd, MatMul, MatrixExpr, MatrixSymbol

from .. import _upstream
from .._upstream import handlers_dict
from . import _dispatch, _simple
from ._dispatch import refine  # the driver identity handlers evaluate candidates with
from ._wraps import principal  # re-exported for tables

Row = tuple[Basic, Basic, Basic]
Binding = dict[Any, Any]
Measure = Callable[[Any, Any], tuple]

__all__ = ["REBUILD", "Row", "bindings", "decide", "derive", "identity_handler", "rule_handler", "part",
           "principal", "provable", "refine", "subst", "default_measure", "handlers_dict"]


# ----------------------------------------------------------------------------
# conditions
# ----------------------------------------------------------------------------

def provable(cond: Any, assumptions: Any, order: bool = False) -> bool | None:
    """Decide ``cond`` connective by connective; ``None`` when undecided.

    With ``order`` (how :func:`decide` refines ``Piecewise`` conditions), the
    relation atoms ``Q.ge``, ``Q.gt``, ``Q.le``, ``Q.lt``, ``Q.eq``, ``Q.ne``
    and SymPy relationals (``x >= y``) are decided by :func:`_order` instead
    of a bare ``ask``, and an ``And`` with an undecided part is still refuted
    by a later part."""
    if cond is S.true or cond is True:
        return True
    if cond is S.false or cond is False:
        return False
    if isinstance(cond, And):
        undecided = False
        for c in sorted(cond.args, key=_ask_cost):     # relations last, and only if the rest holds
            p = provable(c, assumptions, order)
            if p is False or p is None and not order:
                return p                                 # undecided: not provable either way
            undecided |= p is None                       # (a condition goes on looking for a refutation)
        return None if undecided else True
    if isinstance(cond, Or):
        undecided = False
        for c in sorted(cond.args, key=_ask_cost):
            p = provable(c, assumptions, order)
            if p is True:
                return True
            undecided |= p is None
        return None if undecided else False
    if isinstance(cond, Not):
        inner = provable(cond.args[0], assumptions, order)
        return None if inner is None else not inner
    if order:
        relation = _as_relation(cond)
        if relation is not None:
            return _order(*relation, assumptions)
    return _ask_atom(cond, assumptions)


def decide(cond: Any, assumptions: Any) -> bool | None:
    """Decide a condition of a ``Piecewise`` branch: :func:`provable` with
    relations decided by the order vocabulary (:func:`_order`)."""
    return provable(cond, assumptions, order=True)


def _ask_atom(cond: Any, assumptions: Any) -> bool | None:
    """One ``ask``; a sign or realness atom it leaves open is tried on the stated bounds."""
    try:
        answer = _upstream.ask(cond, assumptions)
    except (ValueError, TypeError, AssertionError):   # SymPy's relation ask (LRA) raising on consistent facts
        return None
    if answer is None and isinstance(cond, AppliedPredicate) and cond.function in _BOUND_DECIDED \
            and len(cond.arguments) == 1:
        return _from_bounds(cond.function, cond.arguments[0], assumptions)
    return True if answer is True else (False if answer is False else None)


# the order vocabulary: proof forms of u <= v, u < v, u = v, u != v for (u, v),
# from unary facts (signs, an infinite endpoint) and from stated relations
def _le_by_signs(u: Any, v: Any) -> Any:
    return ((Q.extended_nonpositive(u) & Q.extended_nonnegative(v))
            | (Q.infinite(v) & Q.extended_nonnegative(v) & Q.extended_real(u))
            | (Q.infinite(u) & Q.extended_nonpositive(u) & Q.extended_real(v)))


def _lt_by_signs(u: Any, v: Any) -> Any:
    return ((Q.extended_negative(u) & Q.extended_nonnegative(v))
            | (Q.extended_nonpositive(u) & Q.extended_positive(v))
            | (Q.positive_infinite(v) & Q.real(u)) | (Q.negative_infinite(u) & Q.real(v)))


ORDER: dict = {   # relation -> (proof from signs, proofs from relations: atoms asked one at a time)
    'le': (_le_by_signs, lambda u, v: (Q.le(u, v), Q.lt(u, v), Q.eq(u, v))),   # le follows from neither
    'lt': (_lt_by_signs, lambda u, v: (Q.lt(u, v),)),                          # lt nor eq in SymPy's ask
    'eq': (lambda u, v: ((Q.positive_infinite(u) & Q.positive_infinite(v))     # the same infinity
                         | (Q.negative_infinite(u) & Q.negative_infinite(v))),
           lambda u, v: (Q.zero(u - v), Q.eq(u, v), Q.eq(v, u))),
    'ne': (lambda u, v: S.false,
           lambda u, v: (Q.nonzero(u - v), Q.ne(u, v), Q.ne(v, u), Q.lt(u, v), Q.lt(v, u))),
}
_NEGATION = {'le': ('lt', True), 'lt': ('le', True), 'eq': ('ne', False), 'ne': ('eq', False)}
_RELATIONS = {Q.le: ('le', False), Q.lt: ('lt', False), Q.ge: ('le', True), Q.gt: ('lt', True),
              Q.eq: ('eq', False), Q.ne: ('ne', False)}   # predicate -> (relation, arguments swapped)
_RELATIONALS = {'<=': Q.le, '<': Q.lt, '>=': Q.ge, '>': Q.gt, '==': Q.eq, '!=': Q.ne}


def _as_relation(cond: Any) -> tuple | None:
    """``(name, u, v)`` with ``name`` a key of :data:`ORDER`, for a relation atom or relational."""
    if isinstance(cond, Relational) and cond.rel_op in _RELATIONALS:
        cond = _RELATIONALS[cond.rel_op](*cond.args)
    if not (isinstance(cond, AppliedPredicate) and cond.function in _RELATIONS):
        return None
    (name, swapped), (u, v) = _RELATIONS[cond.function], cond.arguments
    return (name, v, u) if swapped else (name, u, v)


def _order(name: str, u: Any, v: Any, assumptions: Any) -> bool | None:
    """Decide the relation ``name`` of ``(u, v)``: ``True`` when one of its proof
    forms is provable, ``False`` when one of its negation's is."""
    if _holds(name, u, v, assumptions):
        return True
    negation, swap = _NEGATION[name]
    return False if _holds(negation, *((v, u) if swap else (u, v)), assumptions) else None


def _holds(name: str, u: Any, v: Any, assumptions: Any) -> bool:
    by_signs, by_relations = ORDER[name]
    if provable(by_signs(u, v), assumptions) is True:
        return True
    if provable(Q.infinite(u) | Q.infinite(v), assumptions) is True:
        return False    # SymPy's relation ask is unsound at infinity: Q.eq(x, y) "True" for x = -oo, y <= 0
    stated = _states_relations(assumptions)
    return any(_ask_atom(atom, assumptions) is True for atom in by_relations(u, v)
               if stated or atom.function not in (Q.eq, Q.ne))


def _states_relations(assumptions: Any) -> bool:
    """Whether the assumptions contain a relation.  Without one, ``Q.eq`` and ``Q.ne``
    atoms are not asked: SymPy's equality reasoning costs about 0.6 s per query
    and the ``u - v`` zero/nonzero and ``Q.lt`` forms cover what it could prove."""
    return isinstance(assumptions, Basic) and (
        any(p.function in _RELATIONS for p in assumptions.atoms(AppliedPredicate))
        or bool(assumptions.atoms(Relational)))


_BOUND_DECIDED = (Q.real, Q.extended_real, Q.positive, Q.nonnegative, Q.negative, Q.nonpositive, Q.nonzero,
                  Q.extended_positive, Q.extended_nonnegative, Q.extended_negative, Q.extended_nonpositive,
                  Q.extended_nonzero, Q.integer)


def _ask_cost(cond: Any) -> int:
    """Relations (``Q.lt`` and friends) go through SymPy's SAT search over the whole
    expression and are asked last."""
    return 1 if isinstance(cond, AppliedPredicate) and cond.function in (Q.ge, Q.gt, Q.le, Q.lt) else 0


def _from_bounds(predicate: Any, u: Any, assumptions: Any) -> bool | None:
    """``True`` when the bounds stated on ``u`` prove ``predicate(u)``, else ``None``
    (``False`` for an integer refuted by an interval holding no integer).

    **Infinity.**  A stated interval is one of the extended reals: a relation
    (``Q.gt(u, 1)``, even ``Q.ge(u, oo)``, which forces ``u = oo``) holds at an
    infinite ``u``.  It proves ``Q.extended_real(u)`` and the ``extended_*``
    signs; ``Q.real`` and the finite signs (``positive``, ``nonnegative``,
    ``negative``, ``nonpositive``, ``nonzero``) imply ``u`` finite, so they
    also need each infinity the sign leaves possible excluded: by a finite
    endpoint on that side (or an open ``oo`` endpoint, ``Q.lt(u, oo)``), by a
    sign fact among the bounds (``Q.positive(u - 1)`` holds only for a finite
    ``u``: :func:`._simple.stated_finite`), or by ``ask`` proving
    ``Q.finite(u)``.  Before this, a one-sided bound read as finite gave wrong
    results at ``u = +-oo`` (issue #10, B1-B7: Piecewise conditions,
    ``KroneckerDelta``, ``sign(exp(-x))``, ``log(x**n)``, ``acsch(csch(x))``,
    ``RisingFactorial``).  The relation decider (:func:`_order`) reaches the
    bounds only through these atoms (``Q.real(u)`` in a ``u < oo`` proof,
    ``Q.nonzero(u - v)`` for ``u != v``), so it is covered by the same rule.

    **Contradictions.**  The engine derives facts of its own on top of
    ``ask``, so it can prove both ``P`` and ``not P`` although ``ask`` never
    does.  The paths, and what the engine does on each:

    * *bounds against bounds*: stated signs and stated relations are folded
      into one interval (:func:`._simple.stated_bounds`); when it is empty
      (``Q.negative(k) & Q.gt(k, pi/2)``) every sign followed from it, and rows
      conditioned on opposite signs undid each other forever (issue #10,
      B9).  An empty interval now proves nothing (:func:`._simple._checked`,
      also for :func:`._simple.full_bounds` and the floor rules);
    * *bounds against ask*: the bounds are consulted only when ``ask``
      leaves the atom open, so a clash needs ``ask`` to prove a fact that the
      stated interval rules out (``Q.gt(k, 1)`` with an implied
      ``Q.negative(k)``, or ``Q.imaginary(k)``): the assumptions are then
      inconsistent.  It is not detected (that would cost a query per proof
      from bounds);
    * *the relation decider* (:func:`_order`) tries a relation's proof forms
      before its negation's, so each question gets one answer, but under
      inconsistent assumptions ``Eq(u, v)`` and ``Ne(u, v)`` may both be decided
      ``True`` as separate questions;
    * *ask against itself* (an unsound or adversarial backend): nothing to
      detect it with.

    Under inconsistent assumptions every result is correct, so the engine
    does not raise for them (it cannot detect them all, and refine must not
    depend on the backend detecting them either); what it must do is stop,
    and the dispatcher's termination guard guarantees that whatever is
    proved (``_dispatch``, *Termination*)."""
    found = _simple.stated_finite(u, assumptions)
    if found is None:
        return None
    (lo, hi, lo_open, hi_open), finite = found
    if predicate is Q.extended_real:
        return True
    if predicate is Q.integer:                 # refuted when the interval holds no integer
        if lo is None or hi is None:
            return None
        first = ceiling(lo) + (1 if lo_open and lo.is_integer else 0)
        last = floor(hi) - (1 if hi_open and hi.is_integer else 0)
        return False if (first - last).is_positive else None
    # the interval is one of extended reals: the finite predicates also need each
    # infinity the sign leaves possible excluded, by a finite endpoint on its side
    # (or ``u < oo``), by a sign fact (``finite``) or by ``ask`` (issue #10, B1-B7)
    no_pos_inf = hi is not None and (hi.is_finite or (hi is S.Infinity and hi_open) or hi is S.NegativeInfinity)
    no_neg_inf = lo is not None and (lo.is_finite or (lo is S.NegativeInfinity and lo_open) or lo is S.Infinity)
    above = lo is not None and bool(lo.is_extended_positive or (lo.is_zero and lo_open))
    at_least = lo is not None and bool(lo.is_extended_nonnegative)
    below = hi is not None and bool(hi.is_extended_negative or (hi.is_zero and hi_open))
    at_most = hi is not None and bool(hi.is_extended_nonpositive)
    extended = {Q.extended_positive: above, Q.extended_nonnegative: at_least, Q.extended_negative: below,
                Q.extended_nonpositive: at_most, Q.extended_nonzero: above or below}
    if predicate in extended:
        return True if extended[predicate] else None
    holds = {Q.real: True, Q.positive: above, Q.nonnegative: at_least, Q.negative: below,
             Q.nonpositive: at_most, Q.nonzero: above or below}[predicate]
    if not holds:
        return None
    if finite:
        return True
    excluded = {Q.real: no_pos_inf and no_neg_inf,           # above/below already exclude one side
                Q.positive: no_pos_inf, Q.nonnegative: no_pos_inf, Q.negative: no_neg_inf,
                Q.nonpositive: no_neg_inf,
                Q.nonzero: (above and no_pos_inf) or (below and no_neg_inf)}[predicate]
    if excluded:
        return True
    return True if _ask_finite(u, assumptions) else None


def _ask_finite(u: Any, assumptions: Any) -> bool:
    """Whether ``ask`` proves ``u`` finite (what a bound on the extended reals leaves open)."""
    try:
        return _upstream.ask(Q.finite(u), assumptions) is True
    except (ValueError, TypeError, AssertionError):
        return False


REBUILD = "__rebuild__"
"""Binding key holding how a partial match puts its result back (kept
arguments of a ``Max``, the other factors of a ``MatMul``)."""


# ----------------------------------------------------------------------------
# patterns
# ----------------------------------------------------------------------------

class _Part(Symbol):
    """A symbol that binds the part of a sum or product satisfying a predicate."""
    __slots__ = ("predicate",)

    def __new__(cls, name: str, predicate: Callable[[Any], Any]):
        obj = Symbol.__xnew__(cls, name)   # uncached: two families may both use the name 'c'
        obj.predicate = predicate
        return obj

    def _hashable_content(self):
        return (self.name, id(self.predicate))


def part(name: str, predicate: Callable[[Any], Any]) -> Symbol:
    """A pattern symbol binding the terms (factors) for which ``predicate(term)`` is provable."""
    return _Part(name, predicate)


def _is_unit_coefficient_form(pattern: Any) -> tuple[Any, Any, Any] | None:
    """``(n, unit, r)`` when ``pattern`` is ``n*unit + r`` with symbols ``n``, ``r``."""
    if not (isinstance(pattern, Add) and len(pattern.args) == 2):
        return None
    for term, rest in ((pattern.args[0], pattern.args[1]), (pattern.args[1], pattern.args[0])):
        if rest.is_Symbol and not isinstance(rest, _Part) and isinstance(term, Mul):
            syms = [s for s in term.free_symbols if not isinstance(s, _Part)]
            if len(syms) == 1 and term.free_symbols == {syms[0]}:
                n = syms[0]
                unit = (term/n).cancel()
                if not unit.has(n) and rest != n:
                    return n, unit, rest
    return None


class _Shape(NamedTuple):
    """What :func:`_match` needs to know about a pattern besides the target,
    computed once per pattern (:func:`_shape`)."""
    unit_form: tuple[Any, Any, Any] | None   # :func:`_is_unit_coefficient_form`
    rest: tuple                              # positions of the arguments of a sum or product that are
                                             # symbols standing for "the rest" (positions, not the symbols:
                                             # an equal pattern met later may hold other, equal objects)
    has_part: bool                           # an argument is a :func:`part`


_shapes: dict = {}


def _shape(pattern: Any) -> _Shape:
    """The :class:`_Shape` of ``pattern``, remembered (patterns are the rows' left
    sides and their subterms, a fixed set).  It holds nothing that must be
    identical to a part of ``pattern``: SymPy's cache may be cleared, so an equal
    pattern built later can consist of other objects."""
    try:
        return _shapes[pattern]
    except KeyError:
        pass
    unit_form = None
    rest: tuple = ()
    has_part = False
    if isinstance(pattern, (Add, Mul)) and not isinstance(pattern, MatrixExpr):
        args = pattern.args
        has_part = any(isinstance(a, _Part) for a in args)
        rest = tuple(i for i, a in enumerate(args) if a.is_Symbol and not isinstance(a, _Part)
                     and not any(o.has(a) for o in args if o is not a))
        unit_form = _is_unit_coefficient_form(pattern)
    shape = _shapes[pattern] = _Shape(unit_form, rest, has_part)
    return shape


def _bind(b: Binding, key: Any, value: Any) -> Binding | None:
    if key in b:
        return b if b[key] == value else None
    return {**b, key: value}


def _is_matrix(e: Any) -> bool:
    return isinstance(e, MatrixExpr)


def _bind_matrix(b: Binding, pattern: Any, target: Any) -> Binding | None:
    """Bind a ``MatrixSymbol`` pattern to a matrix expression and its shape symbols."""
    if not _is_matrix(target):
        return None
    nb = _bind(b, pattern, target)
    for dim, size in zip(pattern.shape, target.shape):
        if nb is None:
            return None
        nb = _bind(nb, dim, size) if dim.is_Symbol else (nb if dim == size else None)
    return nb


def _match(pattern: Any, target: Any, assumptions: Any, b: Binding, top: bool = False) -> Iterator[Binding]:
    if isinstance(pattern, _Part):
        return  # only meaningful inside a two-symbol sum or product
    if isinstance(pattern, MatrixSymbol):                            # a plain matrix atom
        if isinstance(target, MatrixSymbol):
            nb = _bind_matrix(b, pattern, target)
            if nb is not None:
                yield nb
        return
    if pattern.is_Symbol:
        nb = _bind(b, pattern, target)
        if nb is not None:
            yield nb
        return
    if pattern.is_Atom:
        if pattern == target:
            yield b
        return
    if isinstance(pattern, (MatAdd, HadamardProduct)) and len(pattern.args) == 2 \
            and all(isinstance(a, MatrixSymbol) for a in pattern.args):   # one atom term and the rest
        if not isinstance(target, pattern.func):
            return
        # the pattern's argument order is canonical, not the author's, so either
        # symbol may be the atom and the other the rest
        for atom, rest_sym in (pattern.args, pattern.args[::-1]):
            for k, t in enumerate(target.args):
                if not isinstance(t, MatrixSymbol):
                    continue
                others = target.args[:k] + target.args[k + 1:]   # by position: an equal copy stays
                if not others:
                    continue                                        # a one-term sum has no rest
                rest = others[0] if len(others) == 1 else pattern.func(*others)
                nb = _bind_matrix(b, atom, t)
                nb = _bind_matrix(nb, rest_sym, rest) if nb is not None else None
                if nb is not None:
                    yield nb
        return
    if isinstance(pattern, MatMul):
        scalars = [a for a in pattern.args if not _is_matrix(a)]
        matrices = [a for a in pattern.args if _is_matrix(a)]
        if len(scalars) == 1 and scalars[0].is_Symbol and len(matrices) == 1 \
                and isinstance(matrices[0], MatrixSymbol):                   # c*Z: a scalar factor and the rest
            if not isinstance(target, MatMul):
                return
            for k, f in enumerate(target.args):
                if _is_matrix(f):
                    continue
                others = target.args[:k] + target.args[k + 1:]
                rest = others[0] if len(others) == 1 else MatMul(*others)
                nb = _bind(b, scalars[0], f)
                nb = _bind_matrix(nb, matrices[0], rest) if nb is not None else None
                if nb is not None:     # the right side in canonical form (scalars in front, combined)
                    yield {**nb, REBUILD: (lambda r: r.doit(deep=False) if isinstance(r, MatrixExpr) else r)}
            return
        if not scalars and isinstance(target, MatMul):                    # a run of adjacent factors
            k = len(matrices)
            T = list(target.args)
            for i in range(len(T) - k + 1):
                run = T[i:i + k]
                if not all(_is_matrix(f) for f in run):
                    continue
                before, after = T[:i], T[i + k:]
                if (before or after) and not top:
                    continue
                for nb in _match_seq(matrices, run, assumptions, b):
                    if before or after:
                        nb = {**nb, REBUILD: (lambda r, before=before, after=after:
                                              MatMul(*before, r, *after).doit(deep=False))}
                    else:
                        nb = {**nb, REBUILD: (lambda r: r.doit(deep=False) if isinstance(r, MatrixExpr) else r)}
                    yield nb
            return
    if top and isinstance(pattern, LatticeOp) and len(pattern.args) == 2 \
            and all(a.is_Symbol for a in pattern.args):                    # Max(a, b) of any arity
        if not isinstance(target, pattern.func):
            return
        pa, pb = pattern.args
        T = list(target.args)
        for i, ti in enumerate(T):
            for j, tj in enumerate(T):
                if i == j:
                    continue
                nb = _bind(b, pa, ti)
                nb = _bind(nb, pb, tj) if nb is not None else None
                if nb is None:
                    continue
                others = [t for k, t in enumerate(T) if k != i and k != j]
                if others:
                    nb = {**nb, REBUILD: (lambda r, others=others, head=pattern.func: head(r, *others))}
                yield nb
        return
    if isinstance(pattern, AppliedUndef):                        # head wildcard
        F = pattern.func
        if F in b:
            if not isinstance(target, b[F]):
                return
            nb = b
        else:
            if target.is_Atom or not target.args:
                return
            nb = {**b, F: target.func}
        if len(target.args) != len(pattern.args):
            return
        yield from _match_seq(pattern.args, target.args, assumptions, nb)
        return
    if isinstance(pattern, (Add, Mul)) and not isinstance(pattern, MatrixExpr):
        shape = _shape(pattern)
        if len(shape.rest) == 1 and not shape.has_part and shape.unit_form is None:   # structure beside a rest symbol
            if not isinstance(target, pattern.func):
                return
            at = shape.rest[0]
            rest_sym = pattern.args[at]
            others = pattern.args[:at] + pattern.args[at + 1:]
            for chosen in itertools.permutations(range(len(target.args)), len(others)):
                picked = [target.args[i] for i in chosen]
                remaining = [t for i, t in enumerate(target.args) if i not in chosen]
                for nb in _match_seq(others, picked, assumptions, b):
                    nb = _bind(nb, rest_sym, pattern.func(*remaining))
                    if nb is not None:
                        yield nb
            return
        if top and not shape.rest and isinstance(target, pattern.func) and len(target.args) > len(pattern.args) \
                and not shape.has_part:                                     # a sub-product of a longer product
            for chosen in itertools.permutations(range(len(target.args)), len(pattern.args)):
                picked = [target.args[i] for i in chosen]
                remaining = [t for i, t in enumerate(target.args) if i not in chosen]
                for nb in _match_seq(pattern.args, picked, assumptions, b):
                    yield {**nb, REBUILD: (lambda r, remaining=remaining, head=pattern.func: head(r, *remaining))}
            return
    if isinstance(pattern, (Add, Mul)) and len(pattern.args) == 2:
        p1, p2 = pattern.args
        parts = [p for p in (p1, p2) if isinstance(p, _Part)]
        if len(parts) == 1 and all(p.is_Symbol for p in (p1, p2)):    # partition
            a = parts[0]
            other = p2 if a is p1 else p1
            terms = target.args if isinstance(target, pattern.func) else (target,)
            sel = [t for t in terms if _upstream.ask(a.predicate(t), assumptions) is True]
            if not sel:
                return
            rest = [t for t in terms if t not in sel]
            nb = _bind(b, a, pattern.func(*sel))
            nb = _bind(nb, other, pattern.func(*rest)) if nb is not None else None
            if nb is not None:
                yield nb
            return
        if p1.is_Symbol and p2.is_Symbol and not parts:               # one plus rest
            if not isinstance(target, pattern.func):
                return
            for k, f in enumerate(target.args):
                rest = pattern.func(*(target.args[:k] + target.args[k + 1:]))
                nb = _bind(b, p1, f)
                nb = _bind(nb, p2, rest) if nb is not None else None
                if nb is not None:
                    yield nb
            return
        form = _shape(pattern).unit_form
        if form is not None:                                          # n*unit + r
            n, unit, r = form
            terms = Add.make_args(target)
            with_unit = []
            for t in terms:
                ratio = _ratio(t, unit)
                if not ratio.has(S.Pi) and not ratio.has(S.ImaginaryUnit):
                    with_unit.append((t, ratio))
            if not with_unit:
                return
            k = Add(*[ratio for _, ratio in with_unit])
            rest = Add(*[t for t in terms if t not in [u for u, _ in with_unit]])
            seen = set()
            candidates = [(k, rest)]
            coefficients = [c for _, ratio in with_unit for c in Add.make_args(ratio.expand())]
            if len(coefficients) > 1:
                candidates += [(c, (target - c*unit).expand()) for c in coefficients]
            for kk, rr in candidates:
                if kk == 0 or (kk, rr) in seen:
                    continue
                seen.add((kk, rr))
                nb = _bind(b, n, kk)
                nb = _bind(nb, r, rr) if nb is not None else None
                if nb is not None:
                    yield nb
            return
    # structural; a commutative head of small arity is matched in every argument order
    if target.is_Atom or not isinstance(target, pattern.func) or len(target.args) != len(pattern.args):
        return
    if isinstance(pattern, _COMMUTATIVE) and 2 <= len(pattern.args) <= 3:
        seen: set = set()
        for perm in itertools.permutations(target.args):
            if perm in seen:
                continue
            seen.add(perm)
            yield from _match_seq(pattern.args, perm, assumptions, b)
        return
    yield from _match_seq(pattern.args, target.args, assumptions, b)


_COMMUTATIVE = (Add, Mul, MatAdd, HadamardProduct, LatticeOp)


@lru_cache(maxsize=4096)
def _ratio(term: Any, unit: Any) -> Any:
    """``term/unit``, cancelled: the coefficient of ``unit`` in ``term`` for the
    ``n*unit + r`` form.  Remembered: the terms met are few, and ``cancel``
    is most of the cost of that form."""
    return (term/unit).cancel()


def _match_seq(patterns: Iterable[Any], targets: Iterable[Any], assumptions: Any, b: Binding) -> Iterator[Binding]:
    patterns, targets = list(patterns), list(targets)
    if not patterns:
        yield b
        return
    for nb in _match(patterns[0], targets[0], assumptions, b):
        yield from _match_seq(patterns[1:], targets[1:], assumptions, nb)


def bindings(pattern: Any, target: Any, assumptions: Any = True) -> Iterator[Binding]:
    """Ways to match ``pattern`` against ``target`` (see the module docstring)."""
    yield from _match(pattern, target, assumptions, {}, top=True)


def subst(expr: Any, binding: Binding, rebuild: bool = False) -> Any:
    """Substitute a binding: symbols by ``xreplace``, head wildcards by their class;
    with ``rebuild``, put a partial match's result back into what was kept."""
    out = expr
    if binding:
        items = [item for item in binding.items() if item[0] is not REBUILD]
        try:
            out = _substituted(expr, frozenset(items))
        except TypeError:          # an unhashable part (a mutable matrix)
            out = _substituted.__wrapped__(expr, items)
    if rebuild and REBUILD in binding:
        out = binding[REBUILD](out)
    return out


@lru_cache(maxsize=8192)
def _substituted(expr: Any, items: Iterable) -> Any:
    """:func:`subst` without the rebuild, remembered: the rows' hypotheses and
    right sides are substituted with the same bindings many times (every pass
    of the fixed point, every branch of a split), and each substitution
    rebuilds and re-evaluates the expression."""
    heads = {k: v for k, v in items if isinstance(k, UndefinedFunction)}
    syms = {k: v for k, v in items if isinstance(k, Basic) and not isinstance(k, UndefinedFunction)}
    out = expr.xreplace(syms) if syms else expr
    if heads:
        out = out.replace(lambda e: isinstance(e, AppliedUndef) and e.func in heads,
                          lambda e: heads[e.func](*e.args))
    return out


# ----------------------------------------------------------------------------
# ordering
# ----------------------------------------------------------------------------

def _is_negation(a: Any) -> bool:
    """A unit-modulus number (``-1``, ``I``, ``-I``) times an atom: ``-x``, ``-I*x``.

    Such an argument counts as the atom in the orderings, so that
    ``log(x) -> log(-I*x) + I*pi/2`` on the positive imaginary axis is as
    small as ``log(x) -> log(-x) + I*pi`` on the negative real axis."""
    if not isinstance(a, Mul):
        return False
    units = [f for f in a.args if f.is_number and abs(f) == 1]
    rest = [f for f in a.args if f not in units]
    return len(units) >= 1 and len(rest) == 1 and rest[0].is_Atom


def _provably_positive(a: Any, assumptions: Any) -> bool:
    """``a > 0``; for a negation ``-u`` also through ``u < 0`` (the provers do not
    negate the sign of a product: ``Q.positive(-x*y)`` under ``Q.negative(x*y)``)."""
    if _upstream.ask(Q.positive(a), assumptions) is True:
        return True
    return a.could_extract_minus_sign() and _upstream.ask(Q.negative(-a), assumptions) is True


def default_measure(heads: Iterable[type]) -> Measure:
    """The generic rewrite ordering for a table registered on ``heads``.

    ``(structure, badness, size)``: for every node whose head is in
    ``heads``, the number of factors or terms of its argument (a plain
    negation counts as one), or one for a non-atomic argument; then the
    number of such nodes whose argument is not provably positive; then
    ``count_ops`` as a tie-breaker.  A candidate is accepted only if this
    strictly decreases, which is what makes identity rows terminate.  Tables
    pass ``measure=`` to :func:`identity_handler` for their own ordering.
    """
    heads = tuple(heads)

    def measure(e: Any, assumptions: Any) -> tuple:
        nodes = [n for n in e.atoms(*heads)] if heads else []
        structure = 0
        for n in nodes:
            a = n.args[0] if n.args else n
            if _is_negation(a) or isinstance(a, Abs):   # Abs is the canonical form rows produce
                continue
            if isinstance(a, (Add, Mul)):
                structure += len([f for f in a.args if not (f.is_number and abs(f) == 1)])   # -x*y is x*y
            elif not a.is_Atom:
                structure += 1
        bad = sum(not _provably_positive(n.args[0], assumptions) for n in nodes if n.args)
        return (structure, bad, size(e))
    return measure


# ----------------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------------

def _heads_of(rows: Iterable[Row]) -> set[type]:
    return {lhs.func for lhs, _, _ in rows if not isinstance(lhs, AppliedUndef) and not lhs.is_Atom}


def _distributed(cand: Any) -> Any:
    """``cand`` with products distributed over sums when that makes it smaller
    (``n*(log(-x) + I*pi) - I*pi*n`` is ``n*log(-x)``; a rewrite that only
    grows, such as a binomial, is left alone)."""
    if not isinstance(cand, Expr) or not cand.has(Add):
        return cand
    return _distributed_expr(cand)


@lru_cache(maxsize=4096)
def _distributed_expr(cand: Expr) -> Expr:
    """:func:`_distributed` of an expression, remembered (a candidate is
    distributed again every time its row is tried)."""
    try:
        flat = expand_mul(cand)
    except Exception:  # noqa: BLE001
        return cand
    return flat if size(flat) < size(cand) else cand


@lru_cache(maxsize=8192)
def size(e: Any) -> int:
    """``count_ops(e)``, remembered: the tie-breaker of every rewrite ordering,
    measured again for the same expressions in every pass."""
    return count_ops(e)


_splitting: list[bool] = [False]
"""Whether a case split is exploring its branches (nested splits are not tried:
a branch's bookkeeping must collapse by itself, which keeps the cost linear)."""


@contextmanager
def _switched_off(flag: list) -> Iterator[None]:
    """Set ``flag[0]`` inside the block and record it in the dispatcher's
    :data:`._dispatch.state` (results refined inside differ, so they are cached apart)."""
    flag[0] = True
    _dispatch.state.append(id(flag))
    try:
        yield
    finally:
        _dispatch.state.pop()
        flag[0] = False


def identity_handler(rows: list[Row], *, measure: Measure | None = None,
                     opaque: tuple = (floor, im, arg), splits: bool = True) -> Callable[[Any, Any], Any]:
    """A handler from identity rows ``(lhs, rhs, domain[, unless])``.

    For each row and binding: the domain must be provable; the substituted
    right side is refined with this handler switched off (its own nodes are
    rewritten by the dispatcher after acceptance, under the same ordering);
    no ``Piecewise`` the input did not have may survive (a definition whose
    conditions the assumptions leave open is not a rewrite; no split is tried
    on it); a row with ``unless`` does not fire when ``unless`` is provable;
    no ``opaque`` head may survive, after a case split when
    ``splits``; and ``measure`` must strictly decrease.
    """
    rows = [tuple(sympify(t) for t in row) for row in rows]   # a generated 0 or True is a Python object
    unless = {row[:3]: row[3] for row in rows if len(row) == 4}
    rows = [row[:3] for row in rows]
    static_heads = _heads_of(rows)
    busy = [False]

    def handler(expr: Any, assumptions: Any) -> Any:
        if busy[0]:
            return None
        m = measure or default_measure(static_heads | {expr.func})
        m0 = m(expr, assumptions)
        for lhs, rhs, domain in rows:
            for b in bindings(lhs, expr, assumptions):
                if provable(subst(domain, b), assumptions) is not True:
                    continue
                if unless and (lhs, rhs, domain) in unless \
                        and provable(subst(unless[lhs, rhs, domain], b), assumptions) is True:
                    continue
                try:
                    cand = subst(rhs, b, rebuild=True)
                except NotImplementedError:   # SymPy's Piecewise rewrites a condition holding a
                    continue                  # Piecewise to ITE and needs a (x, True) branch for it
                with _switched_off(busy):
                    cand = refine(cand, assumptions)
                cand = _distributed(cand)
                if not set(cand.atoms(Piecewise)) <= set(expr.atoms(Piecewise)):
                    continue                  # an undecided definition
                if cand.has(floor):
                    merged = endpoint_split(expr, cand, assumptions)
                    if merged is not None:
                        cand = merged
                if splits and cand.has(*opaque) and not _splitting[0] and _dispatch.splits_left[0] > 0:
                    _dispatch.splits_left[0] -= 1
                    with _switched_off(_splitting):   # no split inside a split's exploration: the
                        merged = case_split(expr, cand, assumptions, opaque)   # branches must collapse by themselves
                    if merged is not None:
                        cand = merged
                if cand.has(*opaque):
                    continue
                if m(cand, assumptions) < m0:
                    _dispatch.note("identity", (lhs, rhs, domain))
                    # nested nodes of this head were left alone while the candidate was
                    # evaluated; rewrite them now so the result is assembled (and
                    # distributed) here rather than piecewise by the dispatcher
                    return _distributed(refine(cand, assumptions))
        return None

    handler.rows = rows      # type: ignore[attr-defined]
    handler.kind = "identity"  # type: ignore[attr-defined]
    return handler


def rule_handler(rows: list, *, by_binding: bool = False) -> Callable[[Any, Any], Any]:
    """A handler from rule rows ``(lhs, rhs, hypothesis[, unless])``, tried in
    table order: bind, prove the hypothesis, check ``unless`` is not provable,
    substitute (rebuilding a partial match).

    With ``by_binding``, consecutive rows with the same left side form a group
    whose bindings are tried in order, each against every row of the group:
    the first binding some row fires on wins.  The periodicity tables use it,
    so the whole coefficient of ``pi/2`` (the first binding) is tried under
    both parities before a single term of it is (``sec(x + (2*n + 1)*pi/2)``
    is one odd shift, not an even shift ``2*n`` and then a quarter turn)."""
    rows = [tuple(sympify(t) for t in row) + (None,) * (4 - len(row)) for row in rows]   # a generated 0 is an int

    def grouped() -> list[list]:     # from ``rows`` at each call: the ablation tool edits that list
        groups: list[list] = []
        for row in rows:
            if groups and groups[-1][0][0] == row[0]:
                groups[-1].append(row)
            else:
                groups.append([row])
        return groups

    def handler(expr: Any, assumptions: Any) -> Any:
        for group in (grouped() if by_binding else ((row,) for row in rows)):
            for b in bindings(group[0][0], expr, assumptions):
                for lhs, rhs, hyp, unless in group:
                    if provable(subst(hyp, b), assumptions) is not True:
                        continue
                    if unless is not None and provable(subst(unless, b), assumptions) is True:
                        continue
                    out = subst(rhs, b, rebuild=True)
                    if out != expr:
                        _dispatch.note("rule", (lhs, rhs, hyp))
                        return out
        return None

    handler.rows = rows    # type: ignore[attr-defined]
    handler.kind = "rule"  # type: ignore[attr-defined]
    return handler


# ----------------------------------------------------------------------------
# case split
# ----------------------------------------------------------------------------

def _split_branches(s: Any, assumptions: Any) -> tuple[list, bool] | None:
    """Sign cases for a symbol under an opaque head and whether zero is excluded, or ``None``.

    A real symbol of unknown sign splits into its positive and negative
    cases; a nonnegative (nonpositive) one has a single case, the positive
    (negative) one, and the check at zero decides the rest.  An imaginary
    symbol is handled by :func:`case_split` as ``I`` times a real one."""
    ask = _upstream.ask
    if ask(Q.real(s), assumptions) is True:
        pos, neg = ask(Q.positive(s), assumptions), ask(Q.negative(s), assumptions)
        if pos is True or neg is True or pos is False and neg is False:
            return None                  # no sign case, or none consistent (s is zero)
        cases = [(Q.positive(s), s), (Q.negative(s), -s)]     # (branch, what Abs(s) is in it)
        if neg is False:
            cases = cases[:1]
        elif pos is False:
            cases = cases[1:]
        return cases, ask(Q.zero(s), assumptions) is False
    return None


def _same(a: Any, b: Any) -> bool:
    """Equal, or equal after expansion (``nan``/``zoo`` compared as they are)."""
    if a == b:
        return True
    if a.has(nan, zoo) or b.has(nan, zoo):
        return False
    return (a - b).expand() == 0


def _explore(e: Any, assumptions: Any) -> Any:
    """An exploratory refinement (a branch of a split), under its own firing cap."""
    with _dispatch.exploring():
        return refine(e, assumptions)


def _agree_at(expr: Any, cand: Any, point: dict, assumptions: Any) -> bool:
    """Whether ``expr`` and ``cand`` agree at ``point``, by evaluation, refinement, or simplification."""
    try:
        left, right = expr.xreplace(point), cand.xreplace(point)
    except (ArithmeticError, ValueError, TypeError):   # undefined there (Rem(a, 0) raises): no agreement
        return False
    if _same(left, right):
        return True
    try:
        left, right = _explore(left, assumptions), _explore(right, assumptions)
    except ValueError:
        return False
    if _same(left, right):
        return True
    if left.has(nan, zoo) or right.has(nan, zoo):
        return False
    try:
        return simplify(left - right) == 0
    except Exception:  # noqa: BLE001
        return False


_real_part_dummies: dict = {}


def _real_part_dummy(s: Any) -> Dummy:
    """The real symbol ``t`` with ``s = I*t`` that :func:`case_split` splits an imaginary ``s``
    on: one per ``s``, so that the explorations of every split on ``s`` in a call refine the
    same expressions and share the dispatcher's result cache (a fresh ``Dummy`` per split made
    each split redo all of them).  Distinct symbols get distinct dummies, so a split on ``t``
    nested in a split on ``s`` cannot capture it."""
    t = _real_part_dummies.get(s)
    if t is None:
        t = _real_part_dummies[s] = Dummy("t")
    return t


def _linked(s: Any, groups: list[set]) -> set:
    """``s`` and every symbol the assumptions link to it: the symbols of the conjuncts
    (``groups``, one set per conjunct) reachable from ``s`` through shared symbols."""
    linked = {s}
    rest = list(groups)
    grown = True
    while grown:
        grown = False
        keep = []
        for g in rest:
            if g & linked:
                linked |= g
                grown = True
            else:
                keep.append(g)
        rest = keep
    return linked


def case_split(expr: Any, cand: Any, assumptions: Any, opaque: tuple = (floor, im, arg)) -> Any | None:
    """Resolve leftover bookkeeping by a sign split on one symbol under it.

    For a symbol of known reality but unknown sign under an opaque head,
    refine ``cand`` under each sign case; if every case collapses and the
    results agree, that is the answer.  If they differ, try to generalize
    each case's result by ``Abs`` (what ``Abs(x)`` is in that case, ``x``,
    ``-x``, ``-I*x`` or ``I*x``, replaced by ``Abs(x)``) and accept the
    generalization when it refines back to every case's result.  An
    imaginary symbol is split as ``I`` times a real one.  When zero is not excluded, the
    result must also agree with ``expr`` at ``s = 0`` by evaluation.  This
    is the two-branch case split whose branches agree, without
    materializing a ``Piecewise``.

    **Pre-test.**  A split on ``s`` needs every opaque node of ``cand`` to
    collapse in every case.  A node none of whose symbols the assumptions
    link to ``s`` (no conjunct of the assumptions shares a symbol with it,
    transitively; :func:`_linked`) cannot: the assumptions then fall apart
    into a part on the node's symbols and a part on ``s``'s, so a case
    ``Q.positive(s)`` or ``Q.negative(s)`` adds nothing about the node, and
    the node is already what refining ``cand`` under the assumptions left
    opaque.  Such a split is not explored.  (Measured before the pre-test on
    the battery and the ``power_exp_log`` generation: 529 of 529 such nodes
    stayed opaque, and exploring them took 5% and 17% of the time.)
    """
    syms: set = set()
    for node in cand.atoms(*opaque):
        syms |= node.free_symbols
    ask = _upstream.ask
    groups = None
    for s in sorted(syms, key=str):
        if ask(Q.imaginary(s), assumptions) is True and ask(Q.positive(-I*s), assumptions) is None:
            # s = I*t with t real and nonzero: the sign cases are then real-sign
            # reasoning, which the provers do (they do not relate Q.negative(-I*s)
            # to Q.positive(I*s)); the answer is mapped back with t = -I*s
            t = _real_part_dummy(s)
            merged = case_split(expr.xreplace({s: I*t}), cand.xreplace({s: I*t}),
                                And(assumptions, Q.real(t), ~Q.zero(t)), opaque)
            if merged is not None:
                return merged.xreplace({t: -I*s})
            continue
        split = _split_branches(s, assumptions)
        if split is None:
            continue
        cases, zero_excluded = split
        if groups is None:
            groups = [c.free_symbols for c in And.make_args(assumptions)]
        linked = _linked(s, groups)
        if any(not node.free_symbols & linked for node in cand.atoms(*opaque)):
            continue                     # a node the split cannot reach (see the docstring)
        branches = [br for br, _ in cases]
        # stage one: the bookkeeping nodes alone.  A node's refinement is context-free,
        # so one that does not collapse in some case decides the split (no stage two);
        # nodes constant across the cases are substituted, differing ones need stage two
        values: dict = {}
        collapsed = consistent = True
        for node in sorted(cand.atoms(*opaque), key=count_ops):
            vals = []
            for br in branches:
                try:
                    v = _explore(node, And(assumptions, br))
                except ValueError:
                    vals = None
                    break
                if v.has(*opaque):
                    vals = None                  # the node fails in this case: the other cases cannot help
                    break
                vals.append(v)
            if vals is None:
                collapsed = False
                break
            if any(v != vals[0] for v in vals):
                consistent = False
            else:
                values[node] = vals[0]
        if not collapsed:
            continue
        if consistent:
            E = _explore(cand.xreplace(values), assumptions)
            if not E.has(*opaque) and (zero_excluded or _agree_at(expr, E, {s: S.Zero}, assumptions)):
                return E
            continue
        # stage two: the whole candidate, generalized by Abs
        results = []
        for br in branches:
            try:
                r = _explore(cand, And(assumptions, br))
            except ValueError:
                results = None
                break
            if r.has(*opaque):
                results = None
                break
            results.append(r)
        if results is None:
            continue
        guesses = [results[0]] if all(_same(r, results[0]) for r in results) else []
        guesses += [r.xreplace({rep: Abs(s)}) for (_, rep), r in zip(cases, results)]
        for E in guesses:
            if not all(_same(_explore(E, And(assumptions, br)), r) for br, r in zip(branches, results)):
                continue
            if not zero_excluded and not _agree_at(expr, E, {s: S.Zero}, assumptions):
                continue
            return E
    return None


def endpoint_split(expr: Any, cand: Any, assumptions: Any) -> Any | None:
    """Resolve a ``floor`` that is constant on its argument's interval except at
    one closed endpoint (:func:`._simple.floor_two_valued`): take the interior
    value when ``cand`` takes the same value at the endpoint under both, so the
    closed interval of a wrap (``asin(sin(t))`` on ``[-pi/2, pi/2]``) collapses
    although its floor jumps at the boundary.  ``None`` when nothing applies."""
    for node in sorted(cand.atoms(floor), key=count_ops):
        info = _simple.floor_two_valued(node, assumptions)
        if info is None:
            continue
        value, u, endpoint, alternative = info
        interior, boundary = cand.xreplace({node: value}), cand.xreplace({node: alternative})
        if _agree_at(interior, boundary, {u: endpoint}, assumptions):
            merged = _explore(interior, assumptions)
            if merged.has(floor):
                again = endpoint_split(expr, merged, assumptions)
                return merged if again is None else again
            return merged
    return None


# ----------------------------------------------------------------------------
# composition
# ----------------------------------------------------------------------------

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

