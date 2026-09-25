"""The dispatcher rebuilds a node from refined children with
``_simple.rebuild`` (issue #10, B8; was a needs/ test, done in ``_dispatch._step``).

``_dispatch._step`` used to rebuild with ``new = expr.func(*args)``.  For ``acot`` and
``acoth`` SymPy's ``eval`` then pulls a sign out of the refined argument
(``acot(-z) -> -acot(z)``), which is wrong at ``z = 0``: ``acot(Abs(z))``
under ``Q.nonpositive(z)`` becomes ``-acot(z)``, ``-pi/2`` at ``z = 0`` where
the input is ``pi/2``.  The fix is one line in ``_step``::

    new = _simple.rebuild(expr.func, args, assumptions)   # was: expr.func(*args)

``_simple.rebuild`` (track B, ri/bounds) keeps ``acot``/``acoth`` of a
non-numeric argument unevaluated unless ``ask`` proves it nonzero, and is
``func(*args)`` otherwise.  Every case below passes in both modes.
"""
from __future__ import annotations

import pytest
from sympy import Abs, Max, Min, Q, acot, acoth, pi, I, sqrt, symbols

from satrefine import refine
from satrefine.handlers_identities import _dispatch

z = symbols("z")
MODES = {"generated": _dispatch.tables, "live": _dispatch.live}
CASES = [
    (acoth(sqrt(z**2)), Q.nonpositive(z)),
    (acoth(Abs(z)), Q.nonpositive(z)),
    (acot(Abs(z)), Q.nonpositive(z)),
    (acot(sqrt(z**2)), Q.nonpositive(z)),
    (acot(Max(z, -z)), Q.nonpositive(z)),
    (acot(Min(z, -z)), Q.nonnegative(z)),
    (acoth(I*Abs(z)), Q.nonpositive(z)),       # SymPy builds -I*acot(Abs(z)); the old result was I*acot(z)
]


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("expr, assumptions", CASES, ids=[str(c) for c in CASES])
def test_acot_acoth_of_a_rewritten_negation_keeps_its_value_at_zero(mode, expr, assumptions):
    with MODES[mode]():
        result = refine(expr, assumptions)
    assert result.subs(z, 0) == expr.subs(z, 0)


@pytest.mark.parametrize("mode", sorted(MODES))
def test_the_sign_still_comes_out_when_the_argument_is_nonzero(mode):
    with MODES[mode]():
        assert refine(acot(Abs(z)), Q.negative(z)) == -acot(z)
        assert refine(acoth(Abs(z)), Q.negative(z)) == -acoth(z)
