"""Known gaps: queries satassume answers None where a definite answer is true.

Every case is a strict xfail, so a change that closes a gap fails here with
XPASS: move the case to the tests of the feature that closed it, and update
the "Known gaps" section of README.md (or the issue named in the reason).
None of these is a wrong answer; each expected answer holds for every value
the assumptions allow.  Each query runs in a fresh engine, so the answers
do not depend on earlier queries.
"""
from __future__ import annotations

import pytest
from sympy import Function, Q, log, pi, re, im, symbols
from sympy.calculus.accumulationbounds import AccumBounds

from satassume.engine import Engine
from satassume.sympy_api import ask

a, b, m, x = symbols('a b m x')
f = Function('f')


def _gap(name, reason, prop, assum, expected):
    return pytest.param(prop, assum, expected, id=name,
                        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason))


CASES = [
    # An unread relation (Float or AccumBounds bound) makes the whole query None;
    # Engine(uninterpreted="free") answers these.
    _gap("float-bound", "#64: unread relation", Q.real(m), Q.odd(m) & Q.ge(m, 1.5), True),
    _gap("accumbounds-bound", "#64: unread relation", Q.real(m), Q.odd(m) & Q.ge(x, AccumBounds(0, 1)), True),
    _gap("float-bound-2", "#64: unread relation", Q.real(x), Q.nonnegative(x) & Q.le(x, 1.5), True),
    # Differences whose sides are not known to be real.
    _gap("negated-difference", "#42: a - b is -(b - a)", Q.negative(a - b), Q.positive(b - a), True),
    _gap("zero-difference", "#42: a - b is -(b - a)", Q.zero(b - a), Q.zero(a - b), True),
    _gap("eq-finite-sides", "#42: equal finite sides", Q.zero(a - b), Q.eq(a, b) & Q.finite(a) & Q.finite(b), True),
    # Gaussian integers.
    _gap("gaussian-integer", "#19: integral parts are finite", Q.finite(x), Q.integer(re(x)) & Q.integer(im(x)), True),
    # README "Known gaps": no issue, neither SymPy system answers these either,
    # except the first (SymPy's ask substitutes the zero symbol).
    _gap("substitute-zero", "no 'equals 1' fact; pinned symbols are not substituted",
         Q.integer(1/(m + 1)), Q.zero(m), True),
    _gap("constant-interface-eq", "no interface equality for constant terms",
         Q.eq(f(x), f(pi)), Q.eq(2*x, 2*pi), True),
    _gap("constant-spellings", "one value in two spellings is two constants",
         Q.eq(x, 3), Q.eq(x, log(8)/log(2)), True),
    _gap("tiny-constant", "a tiny constant is not shown positive",
         Q.positive(x), Q.gt(x, pi**-(10**20)), True),
]


@pytest.mark.parametrize("prop, assum, expected", CASES)
def test_known_gap(prop, assum, expected):
    assert ask(prop, assum, engine=Engine()) is expected
