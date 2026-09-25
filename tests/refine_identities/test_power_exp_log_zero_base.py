"""Engine owner's request (for whoever owns ``power_exp_log``): a zero base
under a negative exponent.

``refine(log(1/x), Q.zero(x))`` used to give ``zoo`` for some hash seeds (the
battery counted it as "other form", v3 gives ``-log(x)``, also ``zoo`` at
``x = 0``).  That ``zoo`` came from exploring the positive-sign branch of a
case split under ``Q.zero(x)``, where it is inconsistent and the backend
answers anything; the engine no longer explores such a branch (see
``test_engine_hash_seed.py``), so the case is now a miss in both modes.  The
sound route is a ``Pow`` row: ``b**e = zoo`` for ``b`` zero and ``e``
negative (extended real), after which ``log(zoo)`` evaluates.
"""
from __future__ import annotations

from sympy import Q, Symbol, log, zoo

from satrefine import refine

x = Symbol('x')


def test_reciprocal_of_zero_is_complex_infinity():
    assert refine(1/x, Q.zero(x)) == zoo


def test_log_of_reciprocal_of_zero():
    assert refine(log(1/x), Q.zero(x)) == zoo
