"""Engine for handlers stated as identities.

A handler is a table of rows ``(lhs, rhs, domain)``: ``lhs == rhs`` wherever
``domain`` holds, with the free symbols of ``lhs`` universally quantified.
The right side carries the branch bookkeeping explicitly (see
:func:`principal`), so the rows have no case-split hypotheses; the cases
appear when ``refine`` collapses the bookkeeping under the assumptions.

:func:`identity_handler` turns such a table into a dispatcher handler.
:func:`derive` composes a ``log(exp(z))`` fact with exponential forms of
other heads, so ``log(b**e)`` and ``log(p*r)`` need not be written down.
:func:`refine` is the vendored driver with one fix, used to evaluate
candidates; the vendored ``refine`` stays the public entry point.
"""
from __future__ import annotations

from typing import Any, Callable, Iterator

from sympy import And, I, Q, S, Wild, arg, exp, floor, im, log, pi, true
from sympy.core import Add, Basic, Expr, Mul, Pow

from .. import _upstream
from .._upstream import handlers_dict

Row = tuple[Basic, Basic, Basic]


def refine(expr: Any, assumptions: Any = True) -> Any:
    """The vendored ``refine`` with one fix.

    After a node is rebuilt from refined children, the constructor may
    auto-evaluate into a different structure (``im`` of a product becomes a
    sum of ``re``, ``im`` and ``arg`` terms).  The vendored driver then
    dispatches on the new head without refining the children it just
    created; this one refines the new node again.
    """
    if not isinstance(expr, Basic):
        return expr
    if not expr.is_Atom:
        args = [refine(a, assumptions) for a in expr.args]
        new = expr.func(*args)
        if new.is_Atom or new.func is not expr.func or new.args != tuple(args):
            return refine(new, assumptions) if new != expr else expr
        expr = new
    if hasattr(expr, "_eval_refine"):
        ref = expr._eval_refine(assumptions)
        if ref is not None:
            return ref
    handler = handlers_dict.get(expr.__class__.__name__)
    if handler is None:
        return expr
    new = handler(expr, assumptions)
    if new is None or new == expr:
        return expr
    if not isinstance(new, Expr):
        return new
    return refine(new, assumptions)


def principal(w: Any) -> Any:
    """The representative of ``w`` whose imaginary part lies in ``(-pi, pi]``.

    ``exp(w)`` has principal logarithm ``principal(w)``; the floor is the
    branch bookkeeping that the assumptions are expected to collapse.
    """
    return w + 2*pi*I*floor(S.Half - im(w)/(2*pi))


def _is_negation(a: Any) -> bool:
    return isinstance(a, Mul) and a.could_extract_minus_sign() and not isinstance(-a, Mul)


def measure(e: Any, assumptions: Any) -> tuple[int, int]:
    """Rewrite ordering; a candidate is accepted only if this strictly decreases.

    First the number of factors under logarithms of exponentials, powers and
    products (a plain negation does not count as a product), then the number
    of logarithms whose argument is not provably positive.  This is what
    keeps ``log(-x)`` in place under ``Q.negative(x)`` while ``log(x)``
    becomes ``log(-x) + I*pi``, and what makes the identities terminate.
    """
    logs = [l.args[0] for l in e.atoms(log)]
    structural = sum(len(a.args) if isinstance(a, Mul) and not _is_negation(a)
                     else int(isinstance(a, (exp, Pow))) for a in logs)
    bad = sum(_upstream.ask(Q.positive(a), assumptions) is not True for a in logs)
    return (structural, bad)


def bindings(pattern: Any, target: Any) -> Iterator[dict[Any, Any]]:
    """Ways to match ``pattern`` (over plain symbols) against ``target``.

    A symbol binds anything.  A product of two symbols binds one factor of a
    product against the rest, once per factor.  Any other head must equal
    the target's head and is matched structurally.
    """
    if pattern.is_Symbol:
        yield {pattern: target}
    elif isinstance(pattern, Mul):
        if isinstance(target, Mul) and len(pattern.args) == 2 and all(s.is_Symbol for s in pattern.args):
            w1, w2 = pattern.args
            for f in target.args:
                yield {w1: f, w2: Mul(*[g for g in target.args if g is not f])}
    elif isinstance(target, pattern.func):
        wilds = {s: Wild(s.name, exclude=[]) for s in pattern.free_symbols}
        m = target.match(pattern.xreplace(wilds))
        if m is not None:
            yield {s: m[w] for s, w in wilds.items()}


def identity_handler(identities: list[Row], opaque: tuple = (floor, im, arg)) -> Callable[[Any, Any], Any]:
    """Compile a table of rows into a handler for the dispatcher.

    For each row and each binding of its left side: the domain must be
    provable, the substituted right side is refined with this handler
    switched off (its own logarithms are rewritten by the dispatcher after
    acceptance, under the same ordering), no ``opaque`` head may survive,
    and :func:`measure` must strictly decrease.
    """
    busy = [False]

    def handler(expr: Any, assumptions: Any) -> Any:
        if busy[0]:
            return None
        m0 = measure(expr, assumptions)
        for lhs, rhs, domain in identities:
            for m in bindings(lhs.args[0], expr.args[0]):
                if domain is not true and _upstream.ask(domain.xreplace(m), assumptions) is not True:
                    continue
                busy[0] = True
                try:
                    cand = refine(rhs.xreplace(m), assumptions)
                finally:
                    busy[0] = False
                if cand.has(*opaque):
                    continue
                if measure(cand, assumptions) < m0:
                    return cand
        return None

    handler.identities = identities  # type: ignore[attr-defined]
    return handler


def derive(facts: list[Row], exp_forms: list[Row]) -> list[Row]:
    """Compose each ``f(exp(z))`` fact with each exponential form.

    An exponential form ``(L, W, domain)`` states ``L == exp(W)``; composing
    gives the row ``f(L) == rhs[z := W]`` under both domains.
    """
    rows: list[Row] = []
    for lhs, rhs, dom in facts:
        rows.append((lhs, rhs, dom))
        inner = lhs.args[0]
        if isinstance(inner, exp) and inner.args[0].is_Symbol:
            zz = inner.args[0]
            for L, W, dom_d in exp_forms:
                rows.append((lhs.func(L), rhs.xreplace({zz: W}), And(dom, dom_d)))
    return rows
