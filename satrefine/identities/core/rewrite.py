"""Rewriting with tables: identity and rule handlers, and their orderings.

Two table kinds, one row shape ``(lhs, rhs, condition)``:

* an **identity** row (:func:`identity_handler`) holds wherever ``condition``
  (its *domain*) does; its right side carries the branch bookkeeping
  explicitly (see :mod:`._wraps`).  It fires when the domain is provable,
  the refined right side contains none of the *opaque* heads (``floor``,
  ``im``, ``arg`` by default) and a rewrite ordering strictly decreases;
* a **rule** row (:func:`rule_handler`) is a conditional rewrite: it fires
  when ``condition`` (its *hypothesis*) is provable through
  ``_upstream.ask``; the right side is substituted as is.

A rule row may carry a fourth element ``unless``: it fires only if
``unless`` is *not* provable.  Rows are tried in table order.  Patterns are
matched by :mod:`.match`, conditions decided by :mod:`.prove`, leftover
bookkeeping resolved by the case splits of :mod:`.split`; the driver these
handlers run under is :mod:`.driver`.  :func:`derive` (composing facts with
exponential forms) is a table helper, in :mod:`..rules._tables`.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Callable, Iterable, Iterator

from sympy import Abs, Piecewise, Q, arg, count_ops, expand_mul, floor, im
from sympy.core import Add, Basic, Expr, Mul
from sympy.core.function import AppliedUndef
from sympy.core.sympify import sympify

from ... import _upstream
from . import driver as _dispatch
from .driver import refine  # the driver identity handlers evaluate candidates with
from .match import Binding, bindings, subst
from .prove import provable
from .split import case_split, endpoint_split

Row = tuple[Basic, Basic, Basic]
Measure = Callable[[Any, Any], tuple]

__all__ = ["Binding", "Measure", "Row", "default_measure", "identity_handler", "rule_handler", "size"]


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
