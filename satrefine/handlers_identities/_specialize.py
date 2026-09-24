"""Generate conditional rules from identity rows, verify them, compile them.

:func:`specialize` runs the identity engine on a row's left side under every
assumption profile drawn from a catalog and keeps the profiles where the
branch bookkeeping collapsed, minus profiles strictly stronger than another
with the same result and rules equal under a symmetry of the left side.
:func:`verify` checks a generated rule numerically at a point satisfying
its hypothesis.  :func:`compile_rule` turns a rule into a handler that binds,
asks the hypothesis once, and substitutes: the shape of the procedural
handlers, generated instead of written.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable, Iterable

from sympy import And, AppliedPredicate, I, N, Q, arg, expand, floor, im, true

from .. import _upstream
from ._engine import Row, bindings, refine, subst

CATALOG: list = [None, Q.positive, Q.negative, Q.nonnegative, Q.real, Q.imaginary,
                 Q.even, Q.odd, Q.integer, lambda v: Q.even(v/2), lambda v: Q.odd(v/2)]

SAMPLE = {Q.positive: 2.3, Q.negative: -1.7, Q.nonnegative: 0.6, Q.real: 0.6, Q.imaginary: 1.9*I,
          Q.complex: 1.2 + 0.7*I, Q.even: 4, Q.odd: 3, Q.integer: 5}


def implies(strong: Any, weak: Any) -> bool:
    return all(_upstream.ask(a, strong) is True for a in And.make_args(weak))


def specialize(lhs: Any, domain: Any, catalog: Iterable = CATALOG) -> list[Row]:
    catalog = list(catalog)
    vars_ = sorted(lhs.free_symbols, key=str)
    found: list[tuple[Any, Any]] = []
    for choice in itertools.product(catalog, repeat=len(vars_)):
        atoms = [c(v) for c, v in zip(choice, vars_) if c is not None]
        profile = And(*atoms) if atoms else true
        try:
            rhs = refine(lhs, profile & domain)
        except ValueError:                       # inconsistent profile
            continue
        if rhs == lhs or rhs.has(floor, im, arg):
            continue
        residual = [d for d in And.make_args(domain) if not (atoms and _upstream.ask(d, profile) is True)]
        found.append((expand(rhs), And(profile, *residual)))
    kept: list[tuple[Any, Any]] = []
    for rhs, hyp in found:
        if any(rhs == rhs2 and implies(hyp, hyp2) for rhs2, hyp2 in kept):
            continue
        kept = [(rhs2, hyp2) for rhs2, hyp2 in kept if not (rhs == rhs2 and implies(hyp2, hyp))]
        kept.append((rhs, hyp))
    out: list[tuple[Any, Any]] = []
    for rhs, hyp in kept:
        perms = [dict(zip(vars_, q)) for q in itertools.permutations(vars_)]
        if any((rhs.xreplace(m), hyp.xreplace(m)) in out for m in perms if lhs.xreplace(m) == lhs):
            continue
        out.append((rhs, hyp))
    return [(lhs, rhs, hyp) for rhs, hyp in out]


def specialize_table(identities: Iterable[Row], catalog: Iterable = CATALOG) -> list[Row]:
    """Specialize every distinct left side of an identity table."""
    seen, rules = set(), []
    for lhs, _rhs, dom in identities:
        if (lhs, dom) in seen:
            continue
        seen.add((lhs, dom))
        rules += specialize(lhs, dom, catalog)
    return rules


def sample_point(hyp: Any, symbols_needed: Iterable) -> dict | None:
    point = {}
    for ap in And.make_args(hyp):
        if isinstance(ap, AppliedPredicate) and ap.function in SAMPLE and ap.arguments[0].is_Symbol:
            point[ap.arguments[0]] = SAMPLE[ap.function]
    return point if set(point) >= set(symbols_needed) else None


def verify(lhs: Any, rhs: Any, hyp: Any) -> bool | None:
    """``True``/``False`` at one sample point of the hypothesis; ``None`` if none is known."""
    point = sample_point(hyp, lhs.free_symbols)
    if point is None:
        return None
    val = N((lhs - rhs).subs(point))
    return bool(abs(val) < 1e-9) if val.is_number else None


def compile_rule(lhs: Any, rhs: Any, hyp: Any) -> Callable[[Any, Any], Any]:
    def handler(expr: Any, assumptions: Any) -> Any:
        for m in bindings(lhs, expr, assumptions):
            if any(v in (0, 1) for v in m.values()):
                continue
            if _upstream.ask(subst(hyp, m), assumptions) is True:
                return subst(rhs, m)
        return None
    return handler


def compile_table(rules: Iterable[Row]) -> Callable[[Any, Any], Any]:
    handlers = [compile_rule(*rule) for rule in rules]

    def handler(expr: Any, assumptions: Any) -> Any:
        for h in handlers:
            out = h(expr, assumptions)
            if out is not None and out != expr:
                return out
        return None
    return handler
