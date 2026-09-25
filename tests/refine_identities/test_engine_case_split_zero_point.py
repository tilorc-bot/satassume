"""Request from "defs" (engine): the case split's check at ``s = 0`` must not
raise when the left side is undefined there.

:func:`._engine.case_split` compares ``expr`` and the merged candidate at
``s = 0`` when zero is not excluded (:func:`._engine._agree_at`), by
``expr.xreplace({s: 0})``.  For ``Rem(a, b)`` split on ``b`` that builds
``Rem(a, 0)``, and SymPy's ``Rem.eval`` raises ``ZeroDivisionError``
(``Mod`` returns ``nan``); the exception escapes ``refine``.  Wanted: a point
where the left side cannot be built or evaluated counts as disagreement
(the split declines, or tries the next symbol).

``integer_funcs`` works around it by stating ``Q.nonzero(b)`` in its ``Rem``
identity row's domain (true anyway: ``Rem(a, 0)`` is undefined), so the
split excludes zero.  Found while generating that table: the generator
specializes the row's left side with the domain's conjuncts dropped one
profile at a time and hit the raise.
"""
from __future__ import annotations

from sympy import Q, Rem, sign, symbols

from satrefine.handlers_identities._engine import identity_handler

a, b, x, y = symbols('a b x y')


def test_split_at_a_point_where_the_left_side_raises():
    handler = identity_handler([(Rem(a, b), b*sign(a/b)/2, Q.odd(2*a/b))], opaque=(sign,))
    expr = Rem(x, y)
    out = handler(expr, Q.odd(2*x/y) & Q.nonnegative(x) & Q.nonnegative(y))   # must not raise ZeroDivisionError
    assert out is None or out.has(y)
