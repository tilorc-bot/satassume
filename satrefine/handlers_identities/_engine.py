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
``ValueError`` counts as not provable.  A sign or realness atom ``ask`` leaves open is
decided from the bounds the assumptions state on its argument
(``Q.real(t)`` and ``Q.nonpositive(t)`` under ``Q.ge(t, -pi) & Q.le(t,
0)``; see :func:`._simple.stated_bounds`): a stated bound carries
realness, as in ``handlers_v3``.  A rule row may carry a fourth element ``unless``:
it fires only if ``unless`` is *not* provable.  Rows are tried in table
order.

:func:`derive` composes a ``g(exp(z))`` fact with exponential forms
``(L, W, domain)`` (``L == exp(W)``) into rows for ``g(L)``.  The dispatcher
these handlers run under is :mod:`._dispatch`.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Iterable, Iterator

from sympy import (Abs, And, Dummy, I, Not, Or, Q, S, Symbol, arg, count_ops, exp, expand_mul, floor, im, log,
                   nan, simplify, zoo)
from sympy.assumptions import AppliedPredicate
from sympy.core import Add, Basic, Expr, Mul, Pow
from sympy.core.function import AppliedUndef, UndefinedFunction
from sympy.core.operations import LatticeOp
from sympy.matrices.expressions import HadamardProduct, MatAdd, MatMul, MatrixExpr, MatrixSymbol

from .. import _upstream
from .._upstream import handlers_dict
from . import _dispatch, _simple
from ._dispatch import refine  # the driver identity handlers evaluate candidates with
from ._wraps import principal  # re-exported for tables

Row = tuple[Basic, Basic, Basic]
Binding = dict[Any, Any]
Measure = Callable[[Any, Any], tuple]

__all__ = ["REBUILD", "Row", "bindings", "derive", "identity_handler", "rule_handler", "part",
           "principal", "provable", "refine", "subst", "default_measure", "handlers_dict"]


# ----------------------------------------------------------------------------
# conditions
# ----------------------------------------------------------------------------

def provable(cond: Any, assumptions: Any) -> bool | None:
    """Decide ``cond`` connective by connective; ``None`` when undecided."""
    if cond is S.true or cond is True:
        return True
    if cond is S.false or cond is False:
        return False
    if isinstance(cond, And):
        for c in sorted(cond.args, key=_ask_cost):     # relations last, and only if the rest holds
            p = provable(c, assumptions)
            if p is not True:
                return p                                 # False, or undecided: not provable either way
        return True
    if isinstance(cond, Or):
        undecided = False
        for c in sorted(cond.args, key=_ask_cost):
            p = provable(c, assumptions)
            if p is True:
                return True
            undecided |= p is None
        return None if undecided else False
    if isinstance(cond, Not):
        inner = provable(cond.args[0], assumptions)
        return None if inner is None else not inner
    try:
        answer = _upstream.ask(cond, assumptions)
    except ValueError:            # SymPy's relation ask on consistent sign facts
        return None
    if answer is None and isinstance(cond, AppliedPredicate) and cond.function in _BOUND_DECIDED \
            and len(cond.arguments) == 1:
        return _from_bounds(cond.function, cond.arguments[0], assumptions)
    return True if answer is True else (False if answer is False else None)


_BOUND_DECIDED = (Q.real, Q.extended_real, Q.positive, Q.nonnegative, Q.negative, Q.nonpositive, Q.nonzero)


def _ask_cost(cond: Any) -> int:
    """Relations (``Q.lt`` and friends) go through SymPy's SAT search over the whole
    expression and are asked last."""
    return 1 if isinstance(cond, AppliedPredicate) and cond.function in (Q.ge, Q.gt, Q.le, Q.lt) else 0


def _from_bounds(predicate: Any, u: Any, assumptions: Any) -> bool | None:
    """``True`` when the bounds stated on ``u`` prove ``predicate(u)``, else ``None``."""
    bounds = _simple.stated_bounds(u, assumptions)
    if bounds is None:
        return None
    lo, hi, lo_open, hi_open = bounds
    if predicate in (Q.real, Q.extended_real):
        return True
    above = lo is not None and (lo.is_positive or (lo.is_zero and lo_open))
    at_least = lo is not None and lo.is_nonnegative
    below = hi is not None and (hi.is_negative or (hi.is_zero and hi_open))
    at_most = hi is not None and hi.is_nonpositive
    holds = {Q.positive: above, Q.nonnegative: at_least, Q.negative: below, Q.nonpositive: at_most,
             Q.nonzero: above or below}[predicate]
    return True if holds else None


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
            for t in target.args:
                if not isinstance(t, MatrixSymbol):
                    continue
                others = [g for g in target.args if g is not t]
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
            for f in target.args:
                if _is_matrix(f):
                    continue
                others = [g for g in target.args if g is not f]
                rest = others[0] if len(others) == 1 else MatMul(*others)
                nb = _bind(b, scalars[0], f)
                nb = _bind_matrix(nb, matrices[0], rest) if nb is not None else None
                if nb is not None:
                    yield nb
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
                others = [t for t in T if t is not ti and t is not tj]
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
        rest_syms = [a for a in pattern.args if a.is_Symbol and not isinstance(a, _Part)
                     and not any(o.has(a) for o in pattern.args if o is not a)]
        if len(rest_syms) == 1 and not any(isinstance(a, _Part) for a in pattern.args) \
                and _is_unit_coefficient_form(pattern) is None:               # structure beside a rest symbol
            if not isinstance(target, pattern.func):
                return
            rest_sym = rest_syms[0]
            others = [a for a in pattern.args if a is not rest_sym]
            for chosen in itertools.permutations(range(len(target.args)), len(others)):
                picked = [target.args[i] for i in chosen]
                remaining = [t for i, t in enumerate(target.args) if i not in chosen]
                for nb in _match_seq(others, picked, assumptions, b):
                    nb = _bind(nb, rest_sym, pattern.func(*remaining))
                    if nb is not None:
                        yield nb
            return
        if top and not rest_syms and isinstance(target, pattern.func) and len(target.args) > len(pattern.args) \
                and not any(isinstance(a, _Part) for a in pattern.args):    # a sub-product of a longer product
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
            for f in target.args:
                rest = pattern.func(*[g for g in target.args if g is not f])
                nb = _bind(b, p1, f)
                nb = _bind(nb, p2, rest) if nb is not None else None
                if nb is not None:
                    yield nb
            return
        form = _is_unit_coefficient_form(pattern)
        if form is not None:                                          # n*unit + r
            n, unit, r = form
            terms = Add.make_args(target)
            with_unit = []
            for t in terms:
                ratio = (t/unit).cancel()
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
    heads = {k: v for k, v in binding.items() if isinstance(k, UndefinedFunction)}
    syms = {k: v for k, v in binding.items() if isinstance(k, Basic) and not isinstance(k, UndefinedFunction)}
    out = expr.xreplace(syms) if syms else expr
    if heads:
        out = out.replace(lambda e: isinstance(e, AppliedUndef) and e.func in heads,
                          lambda e: heads[e.func](*e.args))
    if rebuild and REBUILD in binding:
        out = binding[REBUILD](out)
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
                structure += len(a.args)
            elif not a.is_Atom:
                structure += 1
        # positivity is asked for atom-like arguments only (log(x) versus log(-x));
        # a structured argument counts as bad without a question, structure decides
        bad = sum(not (a.is_Atom or _is_negation(a)) or _upstream.ask(Q.positive(a), assumptions) is not True
                  for a in (n.args[0] for n in nodes if n.args))
        return (structure, bad, count_ops(e))
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
    try:
        flat = expand_mul(cand)
    except Exception:  # noqa: BLE001
        return cand
    return flat if count_ops(flat) < count_ops(cand) else cand


_splitting: list[bool] = [False]
"""Whether a case split is exploring its branches (nested splits are not tried:
a branch's bookkeeping must collapse by itself, which keeps the cost linear)."""


def identity_handler(rows: list[Row], *, measure: Measure | None = None,
                     opaque: tuple = (floor, im, arg)) -> Callable[[Any, Any], Any]:
    """A handler from identity rows ``(lhs, rhs, domain)``.

    For each row and binding: the domain must be provable; the substituted
    right side is refined with this handler switched off (its own nodes are
    rewritten by the dispatcher after acceptance, under the same ordering);
    no ``opaque`` head may survive; and ``measure`` must strictly decrease.
    """
    rows = list(rows)
    static_heads = _heads_of(rows)
    busy = [False]

    def handler(expr: Any, assumptions: Any) -> Any:
        if busy[0] or _dispatch.identities_off[0]:
            return None
        m = measure or default_measure(static_heads | {expr.func})
        m0 = m(expr, assumptions)
        for lhs, rhs, domain in rows:
            for b in bindings(lhs, expr, assumptions):
                if provable(subst(domain, b), assumptions) is not True:
                    continue
                busy[0] = True
                try:
                    cand = refine(subst(rhs, b, rebuild=True), assumptions)
                finally:
                    busy[0] = False
                cand = _distributed(cand)
                if cand.has(floor):
                    merged = endpoint_split(expr, cand, assumptions)
                    if merged is not None:
                        cand = merged
                if cand.has(*opaque) and not _splitting[0] and _dispatch.splits_left[0] > 0:
                    _dispatch.splits_left[0] -= 1
                    _splitting[0] = True        # no split inside a split's exploration: the
                    try:                        # branches must collapse by themselves
                        merged = case_split(expr, cand, assumptions, opaque)
                    finally:
                        _splitting[0] = False
                    if merged is not None:
                        cand = merged
                if cand.has(*opaque):
                    continue
                if m(cand, assumptions) < m0:
                    # nested nodes of this head were left alone while the candidate was
                    # evaluated; rewrite them now so the result is assembled (and
                    # distributed) here rather than piecewise by the dispatcher
                    return _distributed(refine(cand, assumptions))
        return None

    handler.rows = rows      # type: ignore[attr-defined]
    handler.kind = "identity"  # type: ignore[attr-defined]
    return handler


def rule_handler(rows: list) -> Callable[[Any, Any], Any]:
    """A handler from rule rows ``(lhs, rhs, hypothesis[, unless])``, tried in
    table order: bind, prove the hypothesis, check ``unless`` is not provable,
    substitute (rebuilding a partial match)."""
    rows = [tuple(row) + (None,) * (4 - len(row)) for row in rows]

    def handler(expr: Any, assumptions: Any) -> Any:
        for lhs, rhs, hyp, unless in rows:
            for b in bindings(lhs, expr, assumptions):
                if provable(subst(hyp, b), assumptions) is not True:
                    continue
                if unless is not None and provable(subst(unless, b), assumptions) is True:
                    continue
                out = subst(rhs, b, rebuild=True)
                if out != expr:
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
        if pos is True or neg is True:
            return None
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
    left, right = expr.xreplace(point), cand.xreplace(point)
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
    """
    syms: set = set()
    for node in cand.atoms(*opaque):
        syms |= node.free_symbols
    ask = _upstream.ask
    for s in sorted(syms, key=str):
        if ask(Q.imaginary(s), assumptions) is True and ask(Q.positive(-I*s), assumptions) is None:
            # s = I*t with t real and nonzero: the sign cases are then real-sign
            # reasoning, which the provers do (they do not relate Q.negative(-I*s)
            # to Q.positive(I*s)); the answer is mapped back with t = -I*s
            t = Dummy("t")
            merged = case_split(expr.xreplace({s: I*t}), cand.xreplace({s: I*t}),
                                And(assumptions, Q.real(t), ~Q.zero(t)), opaque)
            if merged is not None:
                return merged.xreplace({t: -I*s})
            continue
        split = _split_branches(s, assumptions)
        if split is None:
            continue
        cases, zero_excluded = split
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
                    vals.append(_explore(node, And(assumptions, br)))
                except ValueError:
                    vals = None
                    break
            if vals is None or any(v.has(*opaque) for v in vals):
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
