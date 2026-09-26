"""Inconsistent assumptions: a top-level ``refine`` returns its input (B9's behaviour, kept).

Filed as ``needs/test_default_inconsistent_assumptions.py`` by the default switch
(phase 3, track D), which asked for the ``ValueError`` that SymPy's ``refine``,
the old ``handlers`` and v3 let through from ``ask``.  Decided in phase 3
(``agent-reports/2026-09-26-phase3-fixes-report.md``) to keep returning the input:

* SymPy's own ``test_refine.py`` has no case with inconsistent assumptions, so
  there is no SymPy expectation to match (its ``ValueError`` comes from ``ask``
  and is tested only for ``ask``);
* whether SymPy's ``refine`` raises depends on whether some handler happens to
  ask a question that exposes the contradiction: ``refine(x + 1, Q.positive(x) &
  Q.negative(x))`` returns ``x + 1``, ``refine(sin(x), ...)`` raises.  The engine
  here asks different questions in different orders (and the satassume backend
  detects other contradictions than SymPy's), so raising would make the
  outcome depend on the engine path;
* every expression is a correct refinement under inconsistent assumptions, and
  the input is the one that needs no work (B9, ``_dispatch.refine``; nested
  calls still see the ``ValueError``, so a case split drops an inconsistent
  branch).
"""
from __future__ import annotations

import pytest
from sympy import Abs, Q, conjugate, gamma
from sympy.abc import n, x

from satrefine import backend, refine

CASES = [
    (conjugate(x), Q.infinite(x) & Q.real(x)),
    (Abs(x), Q.positive(x) & Q.negative(x)),
    (gamma(n), Q.infinite(n) & Q.integer(n)),
]


@pytest.mark.parametrize("ask_backend", ["sympy", "satassume", "combined"])
@pytest.mark.parametrize("expr, assumptions", CASES, ids=["conjugate-infinite-real", "abs-positive-negative",
                                                          "gamma-infinite-integer"])
def test_returns_the_input(ask_backend, expr, assumptions):
    with backend.using(ask_backend):
        assert refine(expr, assumptions) == expr
