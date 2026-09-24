"""``handlers_identities.trig`` against the v3 cases (see ``_rows``)."""
from __future__ import annotations

import pytest
from sympy import I, Q, S, cos, cot, csc, pi, sec, sin, sinc, symbols, tan, zoo
from sympy.calculus.accumulationbounds import AccumBounds

from _rows import check_relation, check_valid, ids

x, k, n = symbols("x k n")
ODD, EVEN, INT = Q.odd(k), Q.even(k), Q.integer(k)
K0, K1 = Q.even(k) & Q.even(k/2), Q.odd(k) & Q.even((k - 1)/2)
K2, K3 = Q.even(k) & Q.odd(k/2), Q.odd(k) & Q.odd((k - 1)/2)

ROWS = [
    (sin(x + k*pi), EVEN, sin(x), "same"), (sin(x + k*pi), ODD, -sin(x), "same"),
    (sin(x + k*pi), INT, (-1)**k*sin(x), "same"),
    (cos(x + k*pi), EVEN, cos(x), "same"), (cos(x + k*pi), ODD, -cos(x), "same"),
    (sin(x + k*pi/2), K0, sin(x), "same"), (sin(x + k*pi/2), K1, cos(x), "same"),
    (sin(x + k*pi/2), K2, -sin(x), "same"), (sin(x + k*pi/2), K3, -cos(x), "same"),
    (cos(x + k*pi/2), K1, -sin(x), "same"), (cos(x + k*pi/2), K3, sin(x), "same"),
    (sec(x + k*pi/2), K1, -csc(x), "same"), (csc(x + k*pi/2), K1, sec(x), "same"),
    (sec(x + k*pi/2), K3, csc(x), "same"), (csc(x + k*pi/2), K3, -sec(x), "same"),
    (sin(x + k*pi/2), ODD, (-1)**((k - 1)/2)*cos(x), "same"),
    (cos(x + k*pi/2), EVEN, (-1)**(k/2)*cos(x), "same"),
    (tan(x + k*pi), INT, tan(x), "same"), (cot(x + k*pi), INT, cot(x), "same"),
    (tan(x + k*pi/2), ODD, -cot(x), "same"), (cot(x + k*pi/2), ODD, -tan(x), "same"),
    (sin(k*pi), INT, S.Zero, "same"), (cos(k*pi), INT, (-1)**k, "same"),
    (cos(k*pi), EVEN, S.One, "same"), (cos(2*k*pi), INT, S.One, "same"),
    (tan(k*pi), INT, S.Zero, "same"), (cot(k*pi), INT, zoo, "same"),
    (cos(x + n*pi/2 + k*pi), Q.integer(n) & ODD, -cos(x + n*pi/2), "same"),
    (sinc(k*pi), INT & Q.nonzero(k), S.Zero, "same"), (sinc(2*k*pi), INT & Q.nonzero(k), S.Zero, "same"),
    (sinc(x + pi/2), Q.zero(x), 2/pi, "same"), (sinc(x + 3*pi/2), Q.zero(x), -2/(3*pi), "same"),
    (sin(x), Q.zero(x), S.Zero, "same"), (cos(x), Q.zero(x), S.One, "same"), (cot(x), Q.zero(x), zoo, "same"),
    (csc(x), Q.zero(x), zoo, "same"), (sinc(x), Q.zero(x), S.One, "same"),
    (cos(x + k*pi), Q.zero(x) & ODD, S.NegativeOne, "same"),
    (sin(x + k*pi/2), INT, None, "neither"), (sin(x + k*pi/2), Q.real(k), None, "neither"),
    (sin(x + k*pi*I), INT, None, "neither"), (sinc(k*pi), INT, None, "neither"),
    (sinc(k*pi), EVEN, None, "neither"), (sinc(x + k*pi), EVEN, None, "neither"),
    (sin(x), Q.infinite(x) & Q.extended_real(x), AccumBounds(-1, 1), "same"),
    (sin(x), Q.infinite(x), None, "neither"),
]


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_output_is_valid(expr, assumptions, team, relation):
    if assumptions is not True and (assumptions.has(Q.infinite) or assumptions.has(Q.zero)):
        pytest.skip("no finite default sample")
    check_valid(expr, assumptions, relation=relation, values={k: [S(-3), S(-2), S(-1), S.Zero, S.One, S(2), S(3), S(4)]})


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_relation_to_team(expr, assumptions, team, relation):
    check_relation(expr, assumptions, team, relation)
