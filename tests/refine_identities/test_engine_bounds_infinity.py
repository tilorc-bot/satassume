"""Stated bounds are bounds on the extended reals (issue #10, B1-B8).

A relation such as ``Q.gt(x, 1)`` holds at ``x = oo``, so it proves
``Q.extended_real(x)`` and the ``extended_*`` signs, never ``Q.real(x)`` or a
finite sign (``positive``, ``nonnegative``, ``negative``, ``nonpositive``,
``nonzero``).  Those need infinity excluded on the side that matters: by a
finite bound there (or ``x < oo``), by a sign fact (``Q.positive(x - 1)``
holds only for a finite ``x``) or by ``ask`` (``Q.finite(x)``, ``Q.real(x)``).
Before the fix, ``_engine._from_bounds`` read any bound as finite; the
reproductions below (B1-B7) gave wrong results at ``x = oo``.  Each runs in
both identity modes.  B8 (``acot``/``acoth`` of a rewritten ``-z`` at
``z = 0``) is the guarded rebuild in ``_simple.rebuild``; the end-to-end test
waits for the dispatcher to call it (``needs/test_bounds_acot_rebuild.py``).
"""
from __future__ import annotations

import pytest
from sympy import (Abs, Eq, KroneckerDelta, Ne, Piecewise, Q, RisingFactorial, acot, acoth, acsch, csch, exp, gamma,
                   log, oo, pi, sign, symbols)

from satrefine import refine
from satrefine.identities.core import driver as _dispatch
from satrefine.identities.core.rewrite import provable
from satrefine.identities.rules._simple import rebuild

x, y, n, z = symbols("x y n z")
MODES = {"generated": _dispatch.tables, "live": _dispatch.live}

# (input, assumptions): wrong at x = oo before the fix, unchanged now
UNSOUND_AT_INFINITY = [
    (Piecewise((0, x < oo), (1, True)), Q.gt(x, 1)),                  # B1: 1 at x = oo
    (Piecewise((0, x < oo), (1, True)), Q.ge(x, oo)),                 # B1b: x = oo is the only point
    (Piecewise((0, Eq(x, 2*x)), (1, True)), Q.gt(x, 1)),              # B2: Eq(oo, oo) is True
    (Piecewise((0, Ne(x, 2*x)), (1, True)), Q.gt(x, 1)),
    (KroneckerDelta(x, 2*x), Q.gt(x, 1)),                             # B3: both indices oo
    (KroneckerDelta(x, 3*x + 1), Q.lt(x, -1)),
    (KroneckerDelta(x + 1, 2*x), Q.lt(x, -1)),
    (sign(exp(-x)), Q.gt(x, 1)),                                      # B4: sign(exp(-oo)) = 0
    (sign(exp(x)), Q.lt(x, -1)),
    (sign(exp(x)), Q.ge(x, -oo) & Q.le(x, -5)),
    (log(x**n), Q.gt(x, 1) & Q.real(n)),                              # B5: log(1) vs 0*oo at n = 0
    (acsch(csch(x)), Q.gt(x, 1)),                                     # B6: acsch(0) = zoo
    (acsch(csch(x)), Q.lt(x, -1)),
    (RisingFactorial(x, y), Q.gt(x, 1)),                              # B7: oo vs nan at y = 1
]

# (input, assumptions, result): the same rewrites where x is finite still fire
FINITE = [
    (log(x**n), Q.positive(x - 1) & Q.real(n), n*log(x)),             # a sign fact makes x finite
    (log(x**n), Q.gt(x, 1) & Q.lt(x, 5) & Q.real(n), n*log(x)),       # bounds on both sides
    (log(x**n), Q.gt(x, 1) & Q.finite(x) & Q.real(n), n*log(x)),      # ask proves x finite
    (log(x**n), Q.gt(x, 1) & Q.real(x) & Q.real(n), n*log(x)),
    (sign(exp(-x)), Q.gt(x, 1) & Q.real(x), 1),
    (acsch(csch(x)), Q.gt(x, 1) & Q.lt(x, 3), x),
    (KroneckerDelta(x, 2*x), Q.gt(x, 1) & Q.finite(x), 0),
    (Piecewise((0, x < oo), (1, True)), Q.gt(x, 1) & Q.finite(x), 0),
    (Piecewise((0, Eq(x, 2*x)), (1, True)), Q.gt(x, 1) & Q.lt(x, 2), 1),
    (RisingFactorial(x, y), Q.positive(x - 1), gamma(x + y)/gamma(x)),
    (Abs(x), Q.gt(x, 1) & Q.real(x), x),
]


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("expr, assumptions", UNSOUND_AT_INFINITY, ids=[str(c) for c in UNSOUND_AT_INFINITY])
def test_a_one_sided_bound_does_not_prove_finiteness(mode, expr, assumptions):
    with MODES[mode]():
        assert refine(expr, assumptions) == expr


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("expr, assumptions, expected", FINITE, ids=[str(c[:2]) for c in FINITE])
def test_rewrites_still_fire_where_the_bounds_are_finite(mode, expr, assumptions, expected):
    with MODES[mode]():
        assert refine(expr, assumptions) == expected


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


def test_acot_acoth_rebuilt_unevaluated_when_the_argument_may_be_zero():
    """B8: ``acot(-z)`` auto-evaluates to ``-acot(z)``, wrong at ``z = 0``
    (``acot(0) = pi/2``); likewise ``acoth``.  The guarded rebuild keeps the
    head unless ``ask`` proves the argument nonzero."""
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
