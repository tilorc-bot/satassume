"""The generated rule table: the procedural ``log`` rules recovered from the rows."""
from __future__ import annotations

import pytest
from sympy import I, Q, log, pi, symbols

from satrefine.handlers_identities._specialize import compile_table, specialize_table, verify
from satrefine.handlers_identities.power_exp_log import IDENTITIES

z, b, e, p, r, x = symbols('z b e p r x')

EXPECTED = {   # rules the generator must produce and verify
    (log(exp_ := __import__("sympy").exp(z)), z, Q.real(z)),
    (log(b**e), e*log(b), Q.positive(b) & Q.real(e)),
    (log(b**e), e*log(-b), Q.negative(b) & Q.even(e)),
    (log(p*r), log(p) + log(r), Q.positive(r)),   # a positive factor splits off any other
    (log(p*r), log(-p) + log(-r), Q.negative(p) & Q.negative(r)),
    (log(x), log(-x) + I*pi, Q.negative(x)),
}


@pytest.fixture(scope="module")
def rules():
    return specialize_table(IDENTITIES)


def test_expected_rules_are_generated(rules):
    generated = {(lhs, rhs, hyp) for lhs, rhs, hyp in rules}
    missing = [rule for rule in EXPECTED if rule not in generated]
    assert not missing, missing


def test_generated_rules_verify_or_are_flagged(rules):
    """Every generated rule is checked numerically; a wrong one is a wrong
    ``ask`` answer reaching the floor handler (see the report), so it must
    at least be flagged rather than pass silently."""
    verdicts = {(lhs, rhs, hyp): verify(lhs, rhs, hyp) for lhs, rhs, hyp in rules}
    for rule in EXPECTED:
        assert verdicts.get(rule) is True, rule
    wrong = [rule for rule, v in verdicts.items() if v is False]
    for rule in wrong:
        assert rule not in EXPECTED


def test_compiled_table_fires_like_the_engine(rules):
    handler = compile_table([rule for rule in rules if verify(*rule)])
    assert handler(log(b**e), Q.positive(b) & Q.real(e)) == e*log(b)
    assert handler(log(x), Q.negative(x)) == log(-x) + I*pi
    assert handler(log(x), Q.positive(x)) is None
