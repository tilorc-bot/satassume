"""Deciding conditions: the connectives, the order vocabulary, and the bounds.

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
B1-B7).

The conditions of a ``Piecewise`` (a definition's right side, or any
``Piecewise`` refined) are decided by :func:`decide`: relations (``Q.ge``,
``Q.lt``, ``Q.eq``, ``Q.ne``, ..., and relationals ``x >= y``) through an
order vocabulary (:data:`ORDER`) of proof forms from signs and infinite
endpoints and from stated relations, the latter unused when an argument is
known infinite (SymPy's ``ask`` proves ``Q.eq(x, y)`` for ``x = -oo`` and
``y <= 0``).  A candidate with a ``Piecewise`` the input did not have is
not a rewrite (the conditions are undecided) and no case split is tried
on it; a table may also switch case splits off (``splits=False``).
"""
from __future__ import annotations

from typing import Any

from sympy import And, Not, Or, Q, S, ceiling, floor
from sympy.assumptions import AppliedPredicate
from sympy.core import Basic
from sympy.core.relational import Relational

from ... import _upstream
from ..rules import _simple


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
