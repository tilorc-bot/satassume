"""The combined backend's guard on SymPy's ``Q.extended_real`` handler for powers.

SymPy calls ``sqrt(z)`` extended real for a negative ``z``; the guard
(``_extended_real_true_checked`` in ``satrefine/identities/compat/backend.py``)
keeps a ``True`` for a power only for an integer exponent, or an extended
nonnegative base and a real exponent.  Without it, ``conjugate(a) -> a`` for
``Q.extended_real(a)`` fires on ``sqrt(z)`` when satassume leaves the query
open (a relation against a float) (issue #67).
"""
from __future__ import annotations

from sympy import Q, Symbol, conjugate, sqrt

from satrefine import refine
from satrefine.identities.compat import backend

z = Symbol('z')


def test_conjugate_of_root_of_negative():
    with backend.using("combined"):
        assert refine(conjugate(sqrt(z)), Q.negative(z) & Q.le(z, 1.5)) == -sqrt(z)


def test_guarded_answer():
    assert backend._guarded_sympy_ask(Q.extended_real(sqrt(z)), Q.negative(z)) is None
    assert backend._guarded_sympy_ask(Q.extended_real(z**2), Q.negative(z)) is True
