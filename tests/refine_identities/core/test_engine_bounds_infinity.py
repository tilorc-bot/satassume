"""Stated bounds are bounds on the extended reals (issue #10, B1-B8).

A relation such as ``Q.gt(x, 1)`` holds at ``x = oo``, so it proves
``Q.extended_real(x)`` and the ``extended_*`` signs, never ``Q.real(x)`` or a
finite sign (``positive``, ``nonnegative``, ``negative``, ``nonpositive``,
``nonzero``).  Those need infinity excluded on the side that matters: by a
finite bound there (or ``x < oo``), by a sign fact (``Q.positive(x - 1)``
holds only for a finite ``x``) or by ``ask`` (``Q.finite(x)``, ``Q.real(x)``).
Before the fix, ``_engine._from_bounds`` read any bound as finite.  The
reproductions (B1-B7), wrong at ``x = oo`` then, and the rewrites that must
still fire where ``x`` is finite are rows of ``regressions.py``; B8 is
``compat/test_sympy_fixes_rebuild.py``.  Here: what a bound proves.
"""
from __future__ import annotations

from sympy import Q, oo, pi, symbols

from satrefine.identities.core.prove import provable

x = symbols("x")


def test_what_a_bound_proves():
    """The predicate level: extended facts from any bound, finite ones only with infinity excluded."""
    gt1 = Q.gt(x, 1)
    for p in (Q.extended_real, Q.extended_positive, Q.extended_nonnegative, Q.extended_nonzero):
        assert provable(p(x), gt1) is True
    for p in (Q.real, Q.positive, Q.nonnegative, Q.nonzero):
        assert provable(p(x), gt1) is None
        assert provable(p(x), Q.ge(x, oo)) is None                       # forces x = oo
        assert provable(p(x), gt1 & Q.lt(x, 7)) is True
        assert provable(p(x), gt1 & Q.lt(x, oo)) is True                 # x < oo excludes oo
        assert provable(p(x), gt1 & Q.le(x, oo)) is None
        assert provable(p(x), Q.positive(x - 1)) is True                 # a sign fact is finite
        assert provable(p(x), gt1 & Q.finite(x)) is True
    for p in (Q.negative, Q.nonpositive, Q.nonzero, Q.real):
        assert provable(p(x), Q.lt(x, -1)) is None
        assert provable(p(x), Q.lt(x, -1) & Q.ge(x, -pi)) is True
    assert provable(Q.extended_negative(x), Q.lt(x, -1)) is True
    # the bounds of an affine expression: one side stated on it, the other on the symbol
    assert provable(Q.nonpositive(x - 2*pi), Q.le(x, 2*pi) & Q.ge(x, pi)) is True
    assert provable(Q.nonpositive(x - 2*pi), Q.le(x, 2*pi)) is None
    assert provable(Q.extended_nonpositive(x - 2*pi), Q.le(x, 2*pi)) is True
    assert provable(Q.negative(1 - x), Q.positive(x - 1)) is True
