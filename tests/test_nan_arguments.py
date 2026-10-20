"""Function rules at an argument that may be nan (#180 final review F3).

SymPy's functions return nan for a nan argument before any identity holds
(``rf(nan, 0)``, ``owens_t(nan, 0)`` and ``zeta(1, nan)`` are nan, not 1, 0
and zoo), and no predicate holds of nan.  An explicit nan argument gets no
template fact (``registry.opaque``); a rule ignoring an argument requires it
to be complex or extended real, as ``x + y`` is nan at ``x = oo, y = -oo``.
"""
from __future__ import annotations

import pytest
from sympy import (Abs, Add, Q, RisingFactorial, FallingFactorial, S, Symbol, binomial, nan, oo,
                   sign, sin, symbols, zeta)

from satassume import Engine
from satassume.engine import PRED_INDEX
from satassume.sympy_api import ask

try:
    from sympy import owens_t
except ImportError:  # SymPy < 1.15
    owens_t = None

x, y = symbols('x y')
r = Symbol('r', real=True)
er = Symbol('er', extended_real=True)
c = Symbol('c', complex=True)
rf, ff = RisingFactorial, FallingFactorial
NAN_VALUED = [nan, Add(oo, -oo, evaluate=False)]


def fresh():
    return Engine()


def _rules():
    """``(f, the term at argument v, the fact claimed)``: the rules that
    ignored an argument."""
    out = [(rf, lambda v: rf(v, 0, evaluate=False), Q.positive),
           (ff, lambda v: ff(v, 0, evaluate=False), Q.positive),
           (zeta, lambda v: zeta(1, v, evaluate=False), Q.infinite)]
    if owens_t is not None:
        out.append((owens_t, lambda v: owens_t(v, 0, evaluate=False), Q.zero))
    return out


@pytest.mark.parametrize("v", NAN_VALUED + [x + y])
@pytest.mark.parametrize("rule", _rules(), ids=lambda t: t[0].__name__)
def test_rule_needs_a_number(rule, v):
    _, make, pred = rule
    e = make(v)
    assert ask(pred(e)) is None
    if v in NAN_VALUED:
        assert e.doit() is S.NaN


@pytest.mark.parametrize("v", [r, er, c, S(2), oo])
@pytest.mark.parametrize("rule", _rules(), ids=lambda t: t[0].__name__)
def test_rule_kept_for_numbers(rule, v):
    _, make, pred = rule
    e = make(v)
    assert ask(pred(e)) is True
    if v.is_number:
        assert e.doit() is {'positive': S.One, 'zero': S.Zero, 'infinite': S.ComplexInfinity}[pred.name]


@pytest.mark.parametrize("e", [Abs(nan, evaluate=False), sign(nan, evaluate=False),
                               sin(nan, evaluate=False), binomial(nan, 0, evaluate=False),
                               zeta(nan, evaluate=False)])
def test_applied_to_nan_gets_no_facts(e):
    preds = [p for p in PRED_INDEX if p != 'commutative']
    assert fresh().is_many(e, preds) == [None]*len(preds)

