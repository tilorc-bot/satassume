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
``n*unit + r`` (``n``, ``r`` symbols; ``unit`` constant, e.g. ``pi/2``)
    ``n`` binds the sum of the coefficients of ``unit`` over the terms whose
    ratio to ``unit`` is free of ``pi`` and ``I`` (as ``handlers_v3``'s
    ``split_shift``), ``r`` the remaining terms; then, if several terms had
    the unit, each single such term against the rest;
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
``And`` needs every part provable, an ``Or`` one, atoms are asked one at a
time through ``_upstream.ask`` and an ``ask`` that raises ``ValueError``
counts as not provable.  A rule row may carry a fourth element ``unless``:
it fires only if ``unless`` is *not* provable.  Rows are tried in table
order.

:func:`derive` composes a ``g(exp(z))`` fact with exponential forms
``(L, W, domain)`` (``L == exp(W)``) into rows for ``g(L)``.  The dispatcher
these handlers run under is :mod:`._dispatch`.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Iterable, Iterator

from sympy import Abs, And, I, Not, Or, Q, S, Symbol, arg, count_ops, exp, floor, im, log
from sympy.core import Add, Basic, Expr, Mul, Pow
from sympy.core.function import AppliedUndef, UndefinedFunction
from sympy.core.operations import LatticeOp
from sympy.matrices.expressions import HadamardProduct, MatAdd, MatMul, MatrixExpr, MatrixSymbol

from .. import _upstream
from .._upstream import handlers_dict
from . import _dispatch
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
        parts = [provable(c, assumptions) for c in cond.args]
        return True if all(p is True for p in parts) else (False if any(p is False for p in parts) else None)
    if isinstance(cond, Or):
        parts = [provable(c, assumptions) for c in cond.args]
        return True if any(p is True for p in parts) else (False if all(p is False for p in parts) else None)
    if isinstance(cond, Not):
        inner = provable(cond.args[0], assumptions)
        return None if inner is None else not inner
    try:
        answer = _upstream.ask(cond, assumptions)
    except ValueError:            # SymPy's relation ask on consistent sign facts
        return None
    return True if answer is True else (False if answer is False else None)


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
        obj = Symbol.__new__(cls, name)
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
            if len(with_unit) > 1:
                candidates += [(ratio, target - t) for t, ratio in with_unit]
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
    return isinstance(a, Mul) and a.could_extract_minus_sign() and not isinstance(-a, Mul)


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
            if _is_negation(a):
                a = -a
            if isinstance(a, (Add, Mul)):
                structure += len(a.args)
            elif not a.is_Atom and not isinstance(a, Abs):   # Abs is the canonical form rows produce
                structure += 1
        bad = sum(_upstream.ask(Q.positive(n.args[0]), assumptions) is not True for n in nodes if n.args)
        return (structure, bad, count_ops(e))
    return measure


# ----------------------------------------------------------------------------
# handlers
# ----------------------------------------------------------------------------

def _heads_of(rows: Iterable[Row]) -> set[type]:
    return {lhs.func for lhs, _, _ in rows if not isinstance(lhs, AppliedUndef) and not lhs.is_Atom}


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
    splitting = [False]

    def handler(expr: Any, assumptions: Any) -> Any:
        if busy[0]:
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
                if cand.has(*opaque) and not splitting[0]:
                    splitting[0] = True
                    try:
                        merged = case_split(expr, cand, assumptions, opaque)
                    finally:
                        splitting[0] = False
                    if merged is not None:
                        cand = merged
                if cand.has(*opaque):
                    continue
                if m(cand, assumptions) < m0:
                    return cand
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
    """Sign cases for a symbol under an opaque head and whether zero is excluded, or ``None``."""
    ask = _upstream.ask
    if ask(Q.real(s), assumptions) is True:
        if ask(Q.positive(s), assumptions) is not None or ask(Q.negative(s), assumptions) is not None:
            return None
        return [Q.positive(s), Q.negative(s)], ask(Q.zero(s), assumptions) is False
    if ask(Q.imaginary(s), assumptions) is True:
        if ask(Q.positive(-I*s), assumptions) is not None:
            return None
        return [Q.positive(-I*s), Q.negative(-I*s)], True
    return None


def case_split(expr: Any, cand: Any, assumptions: Any, opaque: tuple = (floor, im, arg)) -> Any | None:
    """Resolve leftover bookkeeping by a sign split on one symbol under it.

    For a symbol of known reality but unknown sign under an opaque head,
    refine ``cand`` under each sign case; if every case collapses and the
    results agree, that is the answer.  If they differ, try to generalize
    the positive case's result by ``Abs`` (``x -> Abs(x)``, or ``-x ->
    Abs(x)`` in the negative case) and accept the generalization when it
    refines back to every case's result.  When zero is not excluded, the
    result must also agree with ``expr`` at ``s = 0`` by evaluation.  This
    is the two-branch case split whose branches agree, without
    materializing a ``Piecewise``.
    """
    syms: set = set()
    for node in cand.atoms(*opaque):
        syms |= node.free_symbols
    for s in sorted(syms, key=str):
        split = _split_branches(s, assumptions)
        if split is None:
            continue
        branches, zero_excluded = split
        # stage one: only the bookkeeping nodes, which may be constant across the cases
        values: dict | None = {}
        for node in cand.atoms(*opaque):
            vals = []
            for br in branches:
                try:
                    vals.append(refine(node, And(assumptions, br)))
                except ValueError:
                    vals = None
                    break
            if vals is None or any(v.has(*opaque) for v in vals) or any(v != vals[0] for v in vals):
                values = None
                break
            values[node] = vals[0]
        if values:
            E = refine(cand.xreplace(values), assumptions)
            if not E.has(*opaque) and (zero_excluded or expr.subs(s, 0) == E.subs(s, 0)):
                return E
        # stage two: the whole candidate, generalized by Abs
        results = []
        for br in branches:
            try:
                r = refine(cand, And(assumptions, br))
            except ValueError:
                results = None
                break
            if r.has(*opaque):
                results = None
                break
            results.append(r)
        if results is None:
            continue
        guesses = [results[0]] if all(r == results[0] for r in results) else []
        guesses += [results[0].xreplace({s: Abs(s)}), results[1].xreplace({-s: Abs(s)})]
        for E in guesses:
            if not all(refine(E, And(assumptions, br)) == r for br, r in zip(branches, results)):
                continue
            if not zero_excluded and expr.subs(s, 0) != E.subs(s, 0):
                continue
            return E
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
