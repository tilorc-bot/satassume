"""``handlers_identities.hyperbolic`` against the v3 cases (see ``_rows``)."""
from __future__ import annotations

import pytest
from sympy import I, Q, S, cosh, coth, csch, pi, sech, sinh, symbols, tanh, zoo

from _rows import check_relation, check_valid, ids

x, y, k, n = symbols("x y k n")
M1, M3 = Q.odd(k) & Q.even((k - 1)/2), Q.odd(k) & Q.odd((k - 1)/2)

ROWS = [
    (sinh(x + k*pi*I), Q.even(k), sinh(x), "same"), (sinh(x + k*pi*I), Q.odd(k), -sinh(x), "same"),
    (cosh(x + k*pi*I), Q.odd(k), -cosh(x), "same"), (sech(x + k*pi*I), Q.odd(k), -sech(x), "same"),
    (csch(x + k*pi*I), Q.even(k), csch(x), "same"),
    (tanh(x + k*pi*I), Q.integer(k), tanh(x), "same"), (coth(x + k*pi*I), Q.integer(k), coth(x), "same"),
    (sinh(x + 2*n*pi*I), Q.integer(n), sinh(x), "same"),
    (sinh(x + k*pi*I/2), M1, I*cosh(x), "same"), (cosh(x + k*pi*I/2), M1, I*sinh(x), "same"),
    (sech(x + k*pi*I/2), M1, -I*csch(x), "same"), (csch(x + k*pi*I/2), M1, -I*sech(x), "same"),
    (sinh(x + k*pi*I/2), M3, -I*cosh(x), "same"), (cosh(x + k*pi*I/2), M3, -I*sinh(x), "same"),
    (sech(x + k*pi*I/2), M3, I*csch(x), "same"), (csch(x + k*pi*I/2), M3, I*sech(x), "same"),
    (sinh(x + (4*n + 1)*pi*I/2), Q.integer(n), I*cosh(x), "same"),
    (sinh(x + (4*n + 3)*pi*I/2), Q.integer(n), -I*cosh(x), "same"),
    (tanh(x + k*pi*I/2), Q.odd(k), coth(x), "same"), (coth(x + k*pi*I/2), Q.odd(k), tanh(x), "same"),
    (sinh(k*pi*I), Q.integer(k), S.Zero, "same"), (cosh(k*pi*I), Q.even(k), S.One, "same"),
    (cosh(k*pi*I), Q.odd(k), S.NegativeOne, "same"), (cosh(k*pi*I), Q.integer(k), (-1)**k, "same"),
    (coth(k*pi*I), Q.integer(k), zoo, "same"), (tanh(k*pi*I/2), Q.odd(k), zoo, "same"),
    (sinh(k*pi*I/2), M1, I, "same"), (csch(k*pi*I/2), M3, I, "same"),
    (sinh(x + k*pi*I), Q.integer(k), None, "extra: (-1)**k*sinh(x), exact (SymPy's form); v3 declines"),
    (sinh(x + k*pi*I/2), Q.odd(k), None, "extra: I*(-1)**(k/2 + 3/2)*cosh(x), exact; v3 declines"),
    (sinh(x + k*pi*I/2), Q.integer(k), None, "neither"), (sinh(x + k*pi), Q.integer(k), None, "neither"),
    (sinh(x + k*pi*I), Q.real(k), None, "neither"), (sinh(x + y), Q.integer(y), None, "neither"),
]


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_output_is_valid(expr, assumptions, team, relation):
    check_valid(expr, assumptions, values={k: [S(-3), S(-2), S(-1), S.Zero, S.One, S(2), S(3), S(4), S(5)],
                                           n: [S(-2), S(-1), S.Zero, S.One, S(2)]})


@pytest.mark.parametrize("expr, assumptions, team, relation", ROWS, ids=ids(ROWS))
def test_relation_to_team(expr, assumptions, team, relation):
    check_relation(expr, assumptions, team, relation)
