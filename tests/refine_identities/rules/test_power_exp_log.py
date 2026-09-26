"""``handlers_identities.power_exp_log`` against the v3 cases.

Rows are ``(input, assumptions, v3 output or None, relation)``; ``same``
means the same form as ``handlers_v3``, ``different`` a correct other form,
``extra`` a correct firing where v3 declines, ``neither`` unchanged on
both sides, and ``miss: <capability>`` an expected failure naming what the
engine lacks.  Every output is checked numerically.
"""
from __future__ import annotations

import pytest
from sympy import (Abs, E, I, Pow, Q, Rational, S, exp, log, pi, simplify, sqrt, symbols)

from satrefine import refine
from satrefine.testing.harness import assert_refinement_valid

x, y, t, n, m, a, b = symbols("x y t n m a b")
HALF = S.Half

ROWS = [
    # log (the 27 inputs of the three-implementation comparison)
    (log(exp(x)), Q.real(x), x, "same"),
    (log(exp(x)), Q.complex(x), None, "neither"),
    (log(exp(x)), Q.positive(x), x, "same"),
    (log(x**2), Q.positive(x), 2*log(x), "same"),
    (log(x**2), Q.real(x), 2*log(Abs(x)), "same"),
    (log(x**2), Q.negative(x), 2*log(-x), "same"),
    (log(x**2), Q.imaginary(x), 2*log(Abs(x)) + I*pi, "same"),
    (log(x**n), Q.real(x) & Q.even(n), None, "neither"),
    (log(x**y), Q.positive(x) & Q.real(y), y*log(x), "same"),
    (log(x**y), Q.positive(x) & Q.complex(y), None, "neither"),
    (log(x*y), Q.positive(x) & Q.positive(y), log(x) + log(y), "same"),
    (log(x*y), Q.positive(x) & Q.negative(y), log(x) + log(-y) + I*pi, "same"),
    (log(x*y), Q.negative(x) & Q.negative(y), log(-x) + log(-y), "same"),
    (log(x*y), Q.positive(x) & Q.complex(y), log(x) + log(y), "same"),
    (log(2*x), Q.positive(x), log(x) + log(2), "same"),
    (log(x*y*t), Q.positive(x) & Q.negative(y) & Q.negative(t), log(-t) + log(x) + log(-y), "same"),
    (log(1/x), Q.positive(x), -log(x), "same"),
    (log(1/x), Q.negative(x), -log(-x) + I*pi, "same"),
    (log(1/x), Q.imaginary(x), -log(x), "same"),
    (log(-x), Q.negative(x), None, "neither"),
    (log(x), Q.negative(x), log(-x) + I*pi, "same"),
    (log(Abs(x)), Q.real(x), None, "neither"),
    (log(sqrt(x)), Q.positive(x), log(x)/2, "same"),
    (log(x**Rational(1, 3)), Q.negative(x), None, "extra"),
    (log(exp(I*t)), Q.real(t), None, "neither"),
    (log(exp(x + I*t)), Q.real(x) & Q.real(t), None, "neither"),
    (log(x**n), Q.positive(x) & Q.real(n), n*log(x), "same"),
    (log(x**n), Q.nonnegative(x) & Q.positive(n), n*log(x), "same"),
    (log(x**n), Q.negative(x) & Q.odd(n), n*log(-x) + I*pi, "same"),   # was log(-x**n) + I*pi: the bare log(x) row now comes last
    (log(x**(-2)), Q.real(x), -2*log(Abs(x)), "same"),   # the even-power rule (zoo on both sides at x = 0)
    (log(x**n), Q.even(n) & Q.nonzero(n) & Q.real(x), n*log(Abs(x)), "same"),
    (log(x**n), Q.even(n) & Q.nonzero(x), n*log(Abs(x)), "same"),
    (sqrt(x**(-2)), Q.nonzero(x), 1/Abs(x), "same"),
    (log(1/x), Q.extended_positive(x), -log(x), "extra: v3 asks Q.finite; at x = oo SymPy's log(1/oo) is zoo, -log(oo) is -oo"),
    (log(x**4), Q.imaginary(x), 4*log(Abs(x)), "same"),
    (log(exp(x)*y), Q.real(x), x + log(y), "same"),
    # Pow
    (sqrt(x**2), Q.real(x), Abs(x), "same"),
    (sqrt(x**2), Q.nonnegative(x), x, "same"),
    (sqrt(x**2), Q.nonpositive(x), -x, "same"),
    (sqrt(x**2), Q.imaginary(x), I*Abs(x), "same"),
    (sqrt(x**2), True, None, "neither"),
    (sqrt(x**2), Q.complex(x), None, "neither"),
    (Pow(Pow(x, 2), HALF), Q.real(x), Abs(x), "same"),
    (sqrt(x**3), Q.real(x), None, "neither"),
    (sqrt(x**3), Q.positive(x), x**Rational(3, 2), "same"),
    ((x**a)**b, Q.positive(x) & Q.real(a), x**(a*b), "same"),
    ((x**a)**b, Q.nonnegative(x) & Q.positive(a), x**(a*b), "same"),
    ((x**a)**b, Q.positive(x), None, "neither"),
    ((x**a)**b, Q.integer(b), x**(a*b), "same"),
    ((x**a)**b, Q.nonzero(x) & Q.even(a), Abs(x)**(a*b), "same"),
    ((x**a)**b, Q.real(x) & Q.even(a) & Q.positive(a), Abs(x)**(a*b), "same"),
    ((x**2)**Rational(1, 3), Q.real(x), Abs(x)**Rational(2, 3), "same"),
    ((x**a)**b, Q.negative(x) & Q.even(a), (-x)**(a*b), "same"),
    ((x**a)**b, Q.real(x) & Q.even(a), None, "neither"),
    ((x**6)**HALF, Q.imaginary(x), I*Abs(x)**3, "same"),
    ((x**4)**HALF, Q.imaginary(x), -x**2, "same"),
    ((x**2)**b, Q.imaginary(x), (-1)**b*Abs(x)**(2*b), "same"),
    ((x**4)**b, Q.imaginary(x), Abs(x)**(4*b), "same"),
    ((x**a)**b, Q.real(x) & Q.integer(a), None, "neither"),
    (Abs(x)**n, Q.real(x) & Q.even(n), x**n, "same"),
    (Abs(x)**2, Q.real(x), x**2, "same"),
    (Abs(x)**2, Q.imaginary(x), -x**2, "same"),
    (Abs(x)**n, Q.imaginary(x) & Q.even(n), (-1)**(n/2)*x**n, "same"),
    (Abs(x)**3, Q.real(x), None, "neither"),
    (Abs(x)**2, Q.complex(x), None, "neither"),
    ((-1)**x, Q.even(x), S.One, "same"),
    ((-1)**x, Q.odd(x), S.NegativeOne, "same"),
    ((-1)**x, Q.integer(x), None, "neither"),
    ((-1)**(x + y), Q.even(x), (-1)**y, "same"),
    ((-1)**(x + y + t), Q.odd(x) & Q.odd(t), (-1)**y, "same"),
    ((-1)**(x + y + 2), Q.odd(x), (-1)**(y + 1), "same"),
    ((-1)**(x + 3), True, (-1)**(x + 1), "same"),
    ((-1)**(-n - HALF), Q.even(n), -I, "same"),
    ((-1)**(n + m + HALF), Q.even(n) & Q.odd(m), -I, "same"),
    ((-1)**(2*n + HALF), Q.integer(n), I, "same"),
    ((-1)**((-1)**n/2 + m/2), Q.integer(n), (-1)**(m/2 + n + HALF), "same"),   # 2-periodic in the exponent
    ((-1)**((-1)**y/2 + m/2), True, None, "neither"),
    ((-2)**n, Q.even(n), 2**n, "same"),
    ((-2)**n, Q.odd(n), -2**n, "same"),
    ((-2)**n, Q.integer(n), None, "neither"),
    (2**n, Q.even(n), None, "neither"),
    (exp(x)**y, Q.real(x), exp(x*y), "same"),
    (exp(x)**y, Q.integer(y), exp(x*y), "same"),
    (exp(x)**y, True, None, "neither"),
    (Pow(E, x, evaluate=False), True, exp(x), "same"),
    (x**y, Q.positive(x) & Q.real(y), None, "neither"),
    (1/x, Q.real(x), None, "neither"),
    # exp
    (exp(x + 2*pi*I*n), Q.integer(n), exp(x), "same"),
    (exp(2*pi*I*n), Q.integer(n), S.One, "same"),
    (exp(x + pi*I*n), Q.even(n), exp(x), "same"),
    (exp(x + pi*I*n), Q.odd(n), -exp(x), "same"),
    (exp(x + pi*I*n), Q.integer(n), (-1)**n*exp(x), "same"),
    (exp(pi*I*(n + HALF)), Q.integer(n), (-1)**n*I, "same"),
    (exp(x + pi*I*n/2), Q.even(n), (-1)**(n/2)*exp(x), "same"),
    (exp(x + pi*I*n + pi*I*m), Q.even(n) & Q.odd(m), -exp(x), "same"),
    (exp(x), Q.real(x), None, "neither"),
    (exp(x + pi*I*n/2), Q.odd(n), None, "extra"),   # I*(-1)**((n - 1)/2)*exp(x) once ask proves (n - 1)/2 an integer
    (exp(x + pi*n), Q.integer(n), None, "neither"),
    (exp(x + pi*I*n), Q.rational(n), None, "neither"),
]

IDS = [f"{expr}|{assum}" for expr, assum, _, _ in ROWS]


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=IDS)
def test_output_is_valid(expr, assumptions, team, relation):
    refined = refine(expr, assumptions)
    if refined != expr:
        assert_refinement_valid(expr, assumptions, refined)


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=IDS)
def test_relation_to_team(expr, assumptions, team, relation):
    refined = refine(expr, assumptions)
    if relation.startswith("miss"):
        if refined == expr:
            pytest.xfail(relation)
        assert simplify(refined - team) == 0, "the miss was fixed; update the row"
    elif relation == "same":
        assert refined == team or simplify(refined - team) == 0, refined
    elif relation == "different":
        assert refined != expr and refined != team
    elif relation.startswith("extra"):
        assert refined != expr
    else:
        assert refined == expr


def test_row_counts():
    from satrefine.identities.rules import power_exp_log as m
    assert len(m.FACTS) == 4 and len(m.EXP_FORMS) == 3


CUBE_ROOT = (x**3)**Rational(1, 3)


def test_cube_root_of_cube_stays(checker_case=CUBE_ROOT):
    """The checker's finding on the vendored ``refine_Pow``: ``(x**3)**(1/3)`` is
    neither ``-x`` for negative ``x`` (the principal cube root of ``x**3`` is
    ``-x*exp(I*pi/3)`` there) nor ``Abs(x)`` for real ``x``; the rows here
    reach a ``(b**a)**e`` only for an even ``a`` or an integer ``e``."""
    from sympy import floor
    assert refine(CUBE_ROOT, Q.negative(x)) == CUBE_ROOT
    assert refine(CUBE_ROOT, Q.real(x)) == CUBE_ROOT
    assert refine(floor(CUBE_ROOT), Q.real(x)) == floor(CUBE_ROOT)
    assert (CUBE_ROOT.subs(x, -1) - 1).evalf() != 0
