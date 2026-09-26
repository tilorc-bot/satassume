"""Numeric verification of generated rules: at a sample point of the hypothesis
and at every edge point (:data:`EDGE_POINTS` plus a family's own) that satisfies it."""
from __future__ import annotations

import itertools
from typing import Any, Iterable

from sympy import And, AppliedPredicate, I, Q, S, nan, zoo

from ..testing.harness import _numerically_equal, _sample_satisfies

SAMPLE = {Q.positive: 2.3, Q.negative: -1.7, Q.nonnegative: 0.6, Q.real: 0.6, Q.imaginary: 1.9*I,
          Q.complex: 1.2 + 0.7*I, Q.even: 4, Q.odd: 3, Q.integer: 5}

EDGE_POINTS: tuple = (S.Zero, S.One, S.NegativeOne, I, -I)
"""Values every generated rule is checked at when they satisfy its hypothesis;
a family adds its branch-cut points in :data:`.specs.EDGE_POINTS`."""


def sample_point(hyp: Any, symbols_needed: Iterable) -> dict | None:
    point = {}
    for ap in And.make_args(hyp):
        if isinstance(ap, AppliedPredicate) and ap.function in SAMPLE and ap.arguments[0].is_Symbol:
            point[ap.arguments[0]] = SAMPLE[ap.function]
    for s in symbols_needed:                     # a variable without a hypothesis: any complex value
        point.setdefault(s, SAMPLE[Q.complex])
    return point


def _agree(lhs: Any, rhs: Any, point: dict) -> bool | None:
    left, right = lhs.subs(point), rhs.subs(point)
    if left in (nan, zoo) or right in (nan, zoo):
        return left == right
    try:
        return _numerically_equal(left, right)
    except Exception:  # noqa: BLE001
        return None


def verify(lhs: Any, rhs: Any, hyp: Any, edges: Iterable = ()) -> bool | None:
    """``True``/``False`` at one sample point of the hypothesis and at every edge point
    (:data:`EDGE_POINTS` plus ``edges``) satisfying it; ``None`` if no point is known."""
    syms = sorted(lhs.free_symbols, key=str)
    point = sample_point(hyp, syms)
    verdict: bool | None = None
    if point is not None and _sample_satisfies(hyp, point):   # a profile on b/2 gives b no sample
        verdict = _agree(lhs, rhs, point)
        if verdict is False:
            return False
    values = list(dict.fromkeys((*EDGE_POINTS, *edges)))
    for combo in itertools.product(values, repeat=len(syms)):
        sample = dict(zip(syms, combo))
        if not _sample_satisfies(hyp, sample):
            continue
        ok = _agree(lhs, rhs, sample)
        if ok is False:
            return False
        if ok is True and verdict is None:
            verdict = True
    return verdict
