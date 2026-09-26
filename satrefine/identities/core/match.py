"""Pattern matching for table rows (:func:`bindings`, :func:`subst`).

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
matrix patterns
    matched by the hook of :mod:`..compat.matrix_match` (:data:`.hooks.match`;
    :data:`.hooks.non_scalar` and :data:`.hooks.commutative` also come from there);
anything else
    structural: same head, same arity, arguments matched pairwise; atoms
    and constants must be equal.  Bindings to ``0`` or ``1`` are legal.
"""
from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Any, Callable, Iterable, Iterator, NamedTuple

from sympy import S, Symbol
from sympy.core import Add, Basic, Mul
from sympy.core.function import AppliedUndef, UndefinedFunction
from sympy.core.operations import LatticeOp

from . import hooks

Binding = dict[Any, Any]

REBUILD = "__rebuild__"
"""Binding key holding how a partial match puts its result back (kept
arguments of a ``Max``, the other factors of a ``MatMul``)."""


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
    if isinstance(pattern, (Add, Mul)) and not isinstance(pattern, hooks.non_scalar):
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


def _match(pattern: Any, target: Any, assumptions: Any, b: Binding, top: bool = False) -> Iterator[Binding]:
    if isinstance(pattern, _Part):
        return  # only meaningful inside a two-symbol sum or product
    if pattern.is_Symbol:
        nb = _bind(b, pattern, target)
        if nb is not None:
            yield nb
        return
    if pattern.is_Atom:
        if pattern == target:
            yield b
        return
    for hook in hooks.match:                                          # a pattern kind the hooks know
        found = hook(pattern, target, assumptions, b, top)
        if found is not None:
            yield from found
            return
    if top and isinstance(pattern, LatticeOp) and len(pattern.args) == 2 \
            and all(a.is_Symbol for a in pattern.args):                    # Max(a, b) of any arity
        if not isinstance(target, pattern.func):
            return
        pa, pb = pattern.args
        T = list(target.args)
        for i, j in itertools.permutations(range(len(T)), 2):
            nb = _bind(b, pa, T[i])
            nb = _bind(nb, pb, T[j]) if nb is not None else None
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
    if isinstance(pattern, (Add, Mul)) and not isinstance(pattern, hooks.non_scalar):
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
            sel = [t for t in terms if hooks.dispatcher.ask(a.predicate(t), assumptions) is True]
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
    if isinstance(pattern, hooks.commutative) and 2 <= len(pattern.args) <= 3:
        seen: set = set()
        for perm in itertools.permutations(target.args):
            if perm in seen:
                continue
            seen.add(perm)
            yield from _match_seq(pattern.args, perm, assumptions, b)
        return
    yield from _match_seq(pattern.args, target.args, assumptions, b)


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
