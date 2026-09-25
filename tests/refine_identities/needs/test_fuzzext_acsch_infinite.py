"""``acsch(csch(Abs(z))) -> Abs(z)`` fires where ``Abs(z)`` may be infinite
(found by ``tools/refine_differential.py --ext``, seeds 21 and 24, both modes,
both backends; phase-3 fuzz extension).

The row in ``inverse.FACTS``::

    (acsch(csch(z)), _reflect_half_imag(z), ~Q.zero(z) & _OFF_CUT_LINES)
    _OFF_CUT_LINES = Q.real(z) | ~Q.integer(im(z)/pi + S.Half)

admits an infinite ``z`` whenever ``im(z)`` auto-evaluates to 0: for
``z = Abs(w)`` SymPy builds ``im(Abs(w)) = 0``, so ``~Q.integer(1/2)`` holds
whatever ``w`` is.  At ``w = +-oo`` the input is ``acsch(csch(oo)) = acsch(0) = zoo``
and the output is ``oo``: the same failure as B6 (issue #10), reached through
the row's domain instead of ``_from_bounds``.  With a plain symbol the row
does not fire (``im(x)`` stays symbolic), which is why B6's fix covers
``acsch(csch(x))`` but not this.

The ``asinh``/``atanh``/``acoth`` rows share ``_OFF_CUT_LINES`` but are right
at +-oo (``acoth(1) = oo`` etc.); only ``acsch`` has a pole (``acsch(0)``) there.
A fix is a finiteness condition on the ``acsch`` row (``Q.finite(z)``), or
``_OFF_CUT_LINES`` requiring it.  The finite case must keep firing.
"""
from __future__ import annotations

import pytest
from sympy import Abs, Q, acsch, csch, symbols

from satrefine import backend, refine
from satrefine.handlers_identities import _dispatch

z, n = symbols("z n")
MODES = {"generated": _dispatch.tables, "live": _dispatch.live}
CASES = [
    (acsch(csch(Abs(z))), Q.infinite(z)),
    (acsch(csch(Abs(z))), Q.extended_negative(z) & Q.infinite(z)),
    (acsch(csch(Abs(n))), Q.gt(n, 0)),
]


@pytest.mark.parametrize("ask_backend", ["satassume", "combined"])
@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("expr, assumptions", CASES, ids=[str(c[1]) for c in CASES])
def test_acsch_csch_does_not_fire_at_infinity(ask_backend, mode, expr, assumptions):
    with backend.using(ask_backend), MODES[mode]():
        assert refine(expr, assumptions) == expr


@pytest.mark.parametrize("mode", sorted(MODES))
def test_acsch_csch_still_fires_for_a_finite_argument(mode):
    with MODES[mode]():
        assert refine(acsch(csch(Abs(n))), Q.gt(n, 0) & Q.finite(n)) in (n, Abs(n))
