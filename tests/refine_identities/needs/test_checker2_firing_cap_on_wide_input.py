"""Checker 2 (for the engine owner): the firing cap counts every firing of a
top-level call, so an input with more than ``MAX_FIRINGS`` independent
rewrites crashes with ``RefineLoopError``.

``Abs(x + k)`` for ``k = 1 .. 501`` under ``Q.positive(x)``: each term fires
once (``Abs(x + k) -> x + k``), there is no loop, and v3 rewrites all 599
terms of the 1 .. 599 version (0 ``Abs`` left, 15 s).  Identities raises
``refine fired handlers more than 500 times; last rewrite Abs(x + 501) ->
x + 501``.  The cap predates step 2 (phase 1's dispatcher counts the same
way); the result cache removed repeated work, not distinct work.  Wanted:
a cap that detects loops (for example firings per node or per rewrite
chain, which the iterative ``_refine`` loop already tracks as ``chain``),
not the width of the input.
"""
from __future__ import annotations

from sympy import Abs, Add, Q, Symbol

from satrefine import refine

x = Symbol('x')


def test_many_independent_firings_do_not_hit_the_cap():
    expr = Add(*[Abs(x + k) for k in range(1, 502)])
    assert refine(expr, Q.positive(x)) == Add(*[x + k for k in range(1, 502)])
