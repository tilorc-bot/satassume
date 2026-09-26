"""Case splits: leftover bookkeeping resolved by a sign split on one symbol
(:func:`case_split`) or at a closed endpoint of a step node's interval (:func:`endpoint_split`).
The heads involved are roles in :mod:`.hooks` (``opaque``, ``modulus``, ``step``, ``two_valued``)."""
from __future__ import annotations

from typing import Any

from sympy import And, Dummy, I, Q, S, count_ops, nan, simplify, zoo

from . import driver as _dispatch
from . import hooks
from .driver import refine


def _split_branches(s: Any, assumptions: Any) -> tuple[list, bool] | None:
    """Sign cases for a symbol under an opaque head and whether zero is excluded, or ``None``.

    A real symbol of unknown sign splits into its positive and negative
    cases; a nonnegative (nonpositive) one has a single case, the positive
    (negative) one, and the check at zero decides the rest.  An imaginary
    symbol is handled by :func:`case_split` as ``I`` times a real one."""
    ask = hooks.dispatcher.ask
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


def _in_every_case(e: Any, assumptions: Any, branches: list, opaque: tuple) -> list | None:
    """``e`` explored under each branch, or ``None`` when a branch is inconsistent
    or leaves an ``opaque`` node (the later branches are not tried)."""
    out = []
    for br in branches:
        try:
            v = _explore(e, And(assumptions, br))
        except ValueError:
            return None
        if v.has(*opaque):
            return None
        out.append(v)
    return out


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
    linked, rest = {s}, list(groups)
    while True:
        joined = [g for g in rest if g & linked]
        if not joined:
            return linked
        linked = linked.union(*joined)
        rest = [g for g in rest if not g <= linked]


def case_split(expr: Any, cand: Any, assumptions: Any, opaque: tuple | None = None) -> Any | None:
    """Resolve leftover bookkeeping by a sign split on one symbol under it.

    For a symbol of known reality but unknown sign under an opaque head
    (``None``: :data:`.hooks.opaque`), refine ``cand`` under each sign case;
    if every case collapses and the results agree, that is the answer.  If
    they differ, try to generalize each case's result by the modulus head
    (:data:`.hooks.modulus`, ``Abs``: what ``Abs(x)`` is in that case, ``x``,
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
    if opaque is None:
        opaque = hooks.opaque
    syms: set = set()
    for node in cand.atoms(*opaque):
        syms |= node.free_symbols
    ask = hooks.dispatcher.ask
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
            vals = _in_every_case(node, assumptions, branches, opaque)
            if vals is None:                     # the node fails in a case: the other cases cannot help
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
        results = _in_every_case(cand, assumptions, branches, opaque)
        if results is None:
            continue
        guesses = [results[0]] if all(_same(r, results[0]) for r in results) else []
        if hooks.modulus is not None:
            guesses += [r.xreplace({rep: hooks.modulus(s)}) for (_, rep), r in zip(cases, results)]
        for E in guesses:
            if not all(_same(_explore(E, And(assumptions, br)), r) for br, r in zip(branches, results)):
                continue
            if not zero_excluded and not _agree_at(expr, E, {s: S.Zero}, assumptions):
                continue
            return E
    return None


def endpoint_split(expr: Any, cand: Any, assumptions: Any) -> Any | None:
    """Resolve a step node (:data:`.hooks.step`, ``floor``) that is constant on its
    argument's interval except at one closed endpoint (:data:`.hooks.two_valued`,
    :func:`..rules._simple.floor_two_valued`): take the interior
    value when ``cand`` takes the same value at the endpoint under both, so the
    closed interval of a wrap (``asin(sin(t))`` on ``[-pi/2, pi/2]``) collapses
    although its floor jumps at the boundary.  ``None`` when nothing applies."""
    step = hooks.step
    if step is None:
        return None
    for node in sorted(cand.atoms(step), key=count_ops):
        info = hooks.two_valued(node, assumptions)
        if info is None:
            continue
        value, u, endpoint, alternative = info
        interior, boundary = cand.xreplace({node: value}), cand.xreplace({node: alternative})
        if _agree_at(interior, boundary, {u: endpoint}, assumptions):
            merged = _explore(interior, assumptions)
            if merged.has(step):
                again = endpoint_split(expr, merged, assumptions)
                return merged if again is None else again
            return merged
    return None
