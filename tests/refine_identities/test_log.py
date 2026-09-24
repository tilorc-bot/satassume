"""The identity-based ``log`` handler on the 27 inputs of the three-implementation
comparison (``agent-reports/2026-09-23-refine-three-implementations.md``).

Each row carries the parallel team's (``handlers_v3``) output and how this
package relates to it: ``same`` (same form), ``different`` (fires, correct,
another form), ``extra`` (fires where the team declined), ``neither``, or
``miss`` (the team fires, this package cannot; each miss names the prover
capability it waits on and is an expected failure).
"""
from __future__ import annotations

import pytest
from sympy import Abs, I, Q, Rational, exp, log, pi, simplify, sqrt, symbols

from satrefine import refine
from satrefine.harness import assert_refinement_valid

x, y, t, n = symbols("x y t n")

ROWS = [  # (input, assumptions, team output or None, relation)
    (log(exp(x)), Q.real(x), x, "same"),
    (log(exp(x)), Q.complex(x), None, "neither"),
    (log(exp(x)), Q.positive(x), x, "same"),
    (log(x**2), Q.positive(x), 2*log(x), "same"),
    (log(x**2), Q.real(x), 2*log(Abs(x)), "miss: two-branch case split on the sign of x"),
    (log(x**2), Q.negative(x), 2*log(-x), "same"),
    (log(x**2), Q.imaginary(x), 2*log(Abs(x)) + I*pi, "miss: two-branch case split on the quadrant of x"),
    (log(x**n), Q.real(x) & Q.even(n), None, "neither"),
    (log(x**n), Q.negative(x) & Q.odd(n), n*log(-x) + I*pi, "different"),
    (log(x**y), Q.positive(x) & Q.real(y), y*log(x), "same"),
    (log(x**y), Q.positive(x) & Q.complex(y), None, "neither"),
    (log(x*y), Q.positive(x) & Q.positive(y), log(x) + log(y), "same"),
    (log(x*y), Q.positive(x) & Q.negative(y), log(x) + log(-y) + I*pi, "same"),
    (log(x*y), Q.negative(x) & Q.negative(y), log(-x) + log(-y), "same"),
    (log(x*y), Q.positive(x) & Q.complex(y), log(x) + log(y), "miss: arg(y) in (-pi, pi] inside floor"),
    (log(2*x), Q.positive(x), log(x) + log(2), "same"),
    (log(x*y*t), Q.positive(x) & Q.negative(y) & Q.negative(t), log(-t) + log(x) + log(-y), "same"),
    (log(1/x), Q.positive(x), -log(x), "same"),
    (log(1/x), Q.negative(x), -log(-x) + I*pi, "same"),
    (log(1/x), Q.imaginary(x), -log(x), "miss: arg(x) in (-pi, pi) inside floor"),
    (log(-x), Q.negative(x), None, "neither"),
    (log(x), Q.negative(x), log(-x) + I*pi, "same"),
    (log(Abs(x)), Q.real(x), None, "neither"),
    (log(sqrt(x)), Q.positive(x), log(x)/2, "same"),
    (log(x**Rational(1, 3)), Q.negative(x), None, "extra"),
    (log(exp(I*t)), Q.real(t), None, "neither"),
    (log(exp(x + I*t)), Q.real(x) & Q.real(t), None, "neither"),
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
        assert simplify(refined - team) == 0
    elif relation == "different":
        assert refined != expr and refined != team
    elif relation == "extra":
        assert refined != expr
    else:
        assert refined == expr


def test_identity_rows_are_four():
    from satrefine.handlers_identities.log import EXP_FORMS, IDENTITIES, LOG_FACTS
    assert len(LOG_FACTS) == 2 and len(EXP_FORMS) == 2 and len(IDENTITIES) == 4


def test_im_of_product_of_logarithm_reduces():
    """The bookkeeping the identities depend on: needs the simple ``im`` rules
    and the fixed driver (the vendored driver leaves ``re``/``im``/``arg`` of
    the parts behind)."""
    from sympy import im
    from satrefine.handlers_identities._engine import refine as fixed_refine
    b, e = symbols("b e")
    assert fixed_refine(im(e*log(b)), Q.negative(b) & Q.even(e)) == pi*e
