"""Checker 2 (for the engine owner): a miss v3 handles.  The order
vocabulary has no proof of ``u = v`` for two arguments at the same infinite
endpoint, so an equality condition between two ``+oo`` (or two ``-oo``)
arguments stays undecided.

``Piecewise((1, Eq(x, y)), (0, True))`` under ``Q.positive_infinite(x) &
Q.positive_infinite(y)``: v3 gives ``1`` (``oo == oo``); identities leaves it
unchanged.  The ``eq`` row of ``ORDER`` proves nothing from signs
(``S.false``), and the relation forms are switched off for a known infinite
argument (the ``-oo`` guard, correctly: SymPy's ``Q.eq`` is unsound there).
A sign form ``(Q.positive_infinite(u) & Q.positive_infinite(v)) |
(Q.negative_infinite(u) & Q.negative_infinite(v))`` would decide it
(v3 gives ``1`` for the ``-oo`` pair too).  Checked: ``Eq(oo, oo)`` and
``Eq(-oo, -oo)`` are ``True``.  Not asked for: ``KroneckerDelta(i, j)``
under the same facts (SymPy leaves ``KroneckerDelta(oo, oo)`` unevaluated,
so it has no value to compare).
"""
from __future__ import annotations

from sympy import Eq, Piecewise, Q, symbols

from satrefine import refine

x, y = symbols('x y')


def test_equal_positive_infinities_decide_eq():
    pw = Piecewise((1, Eq(x, y)), (0, True))
    assert refine(pw, Q.positive_infinite(x) & Q.positive_infinite(y)) == 1
    assert refine(pw, Q.negative_infinite(x) & Q.negative_infinite(y)) == 1
