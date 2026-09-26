"""The guarded rebuild of ``acot``/``acoth`` (issue #10, B8; ``compat/sympy_fixes.rebuild``).

The driver rebuilds a node from refined children with ``rebuild`` instead of
``expr.func(*args)``: for ``acot`` and ``acoth`` SymPy's ``eval`` pulls a sign
out of the argument (``acot(-z) -> -acot(z)``), which is wrong at ``z = 0``
(``acot(0) = pi/2``).  ``rebuild`` keeps the head unless ``ask`` proves the
argument nonzero.  The end-to-end cases are rows ``#10 B8`` of
``regressions.py``.
"""
from __future__ import annotations

from sympy import Abs, Q, acot, acoth, pi, symbols

from satrefine.identities.compat.sympy_fixes import rebuild

z = symbols("z")


def test_acot_acoth_rebuilt_unevaluated_when_the_argument_may_be_zero():
    for f in (acot, acoth):
        kept = rebuild(f, (-z,), Q.nonpositive(z))
        assert kept.func is f and kept.args == (-z,)
        assert kept.subs(z, 0) == f(0)
        assert rebuild(f, (-z,), Q.negative(z)) == -f(z)
        assert rebuild(f, (z,), Q.nonpositive(z)) == f(z)
        assert rebuild(f, (-pi,), True) == f(-pi)                      # numbers evaluate as usual
    kept = rebuild(acoth, (-3*z,), True)
    assert kept.func is acoth
    assert rebuild(Abs, (-z,), True) == Abs(z)
