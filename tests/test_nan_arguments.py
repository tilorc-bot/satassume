"""Function rules at an argument that may be nan (#180 final review F3).

The nan convention (design.md, "Extended reals and nan in templates";
#189; spec.md, "Truth standard"): nan is no number, so a function of nan
has no facts.  The identities ``rf(x, 0) = 1``, ``owens_t(h, 0) = 0`` and
the pole of ``zeta(1, a)`` are stated for numbers, so they say nothing of
``rf(nan, 0)``, ``owens_t(nan, 0)`` and ``zeta(1, nan)``.  An argument that
holds an explicit nan or infinity in a part carrying a value
(``domain.may_be_nan``) gets no template fact (``registry.opaque``); a
rule ignoring an argument requires it to be complex or extended real, as
``x + y`` has no value at ``x = oo, y = -oo``.  What SymPy evaluates these
terms to is not the oracle (#247).
"""
from __future__ import annotations

import pytest
from sympy import (Abs, Add, Mul, Pow, Q, RisingFactorial, FallingFactorial, S, Symbol, binomial, nan, oo,
                   sign, sin, symbols, zeta)

from satassume import Engine
from satassume.engine import PRED_INDEX
from satassume.knowledge.domain import may_be_nan
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
        assert may_be_nan(v)


@pytest.mark.parametrize("v", [r, er, c, S(2), oo])
@pytest.mark.parametrize("rule", _rules(), ids=lambda t: t[0].__name__)
def test_rule_kept_for_numbers(rule, v):
    # by definition: rf(v, 0) and ff(v, 0) are empty products, 1;
    # owens_t(v, 0) is an integral over [0, 0], 0; zeta(1, v) is the pole
    # of the Hurwitz zeta function at s = 1
    _, make, pred = rule
    e = make(v)
    assert ask(pred(e)) is True


@pytest.mark.parametrize("e", [Abs(nan, evaluate=False), sign(nan, evaluate=False),
                               sin(nan, evaluate=False), binomial(nan, 0, evaluate=False),
                               zeta(nan, evaluate=False)])
def test_applied_to_nan_gets_no_facts(e):
    preds = [p for p in PRED_INDEX if p != 'commutative']
    assert fresh().is_many(e, preds) == [None]*len(preds)



def _may_be_nan_arguments():
    from sympy import (Contains, Eq, ImmutableMatrix, Integral, Interval, Limit, Piecewise, Subs, Sum,
                       Trace, UnevaluatedExpr)
    # #231: arithmetic holding an explicit nan or infinity may have no
    # value (oo - oo is undefined, not zero, which made Abs(oo - oo)
    # extended_positive)
    z = Add(oo, -oo, evaluate=False)
    return [z, Add(nan, x, evaluate=False), Abs(nan, evaluate=False), Mul(0, oo, evaluate=False),
            Add(x, oo, -oo, evaluate=False), sin(z, evaluate=False), Pow(z, 2, evaluate=False),
            # #235 review: a Piecewise branch value, an integrand
            Piecewise((z, x > 0), (1, True)), Sum(z, (y, 1, 2)), Integral(z, (y, 0, 1)),
            # re-review R1: every part that carries a value -- the expression
            # and the point of a Subs, the expression of a Limit, the content
            # of an UnevaluatedExpr, the limits of an integral or a sum
            Subs(nan, x, 1), Subs(x, x, nan), Subs(z, y, 1), Limit(nan, y, 0), Limit(z, y, 0),
            UnevaluatedExpr(nan), UnevaluatedExpr(Subs(y, y, nan)), Integral(y, (y, -oo, oo)),
            Sum(y, (y, -oo, oo)), Piecewise((Subs(nan, y, 1), x > 0), (1, True)),
            # #236 review: a condition decides whether there is a value
            Piecewise((1, Eq(z, 0, evaluate=False))), Piecewise((1, Contains(z, Interval(0, 1), evaluate=False))),
            Trace(ImmutableMatrix([[oo, 0], [0, -oo]]))]


@pytest.mark.parametrize("v", _may_be_nan_arguments())
@pytest.mark.parametrize("cls", [Abs, sign, sin])
def test_applied_to_may_be_nan_gets_no_facts(cls, v):
    e = cls(v, evaluate=False)
    assert may_be_nan(v)
    preds = [p for p in PRED_INDEX if p != 'commutative']
    assert fresh().is_many(e, preds) == [None]*len(preds)


def test_issue_231_reproducers():
    z = Add(oo, -oo, evaluate=False)
    assert fresh().is_many(Abs(z, evaluate=False), ['extended_nonnegative', 'extended_positive',
                                                    'zero']) == [None, None, None]
    assert fresh().is_many(sign(z, evaluate=False), ['complex', 'finite']) == [None, None]
    assert fresh().is_(Abs(Abs(nan, evaluate=False), evaluate=False), 'extended_real') is None
    assert fresh().is_(Abs(Add(nan, x, evaluate=False), evaluate=False), 'extended_real') is None


def test_facts_kept_without_explicit_special_values():
    # the range of an Idx (an atom) is a label
    from sympy import Idx, Indexed, IndexedBase, Integral, Piecewise, exp
    i = Idx('i', (0, oo))
    for v in (x, x + 1, Integral(exp(-x), (x, 0, 1)), Piecewise((x, x < 1), (1, True)), oo, i,
              Indexed(IndexedBase('a'), i)):
        assert fresh().is_(Abs(v), 'extended_nonnegative') is True, v
    assert fresh().is_(sign(x), 'finite') is True


def test_rereview_r1_reproducers():
    from sympy import Eq, Integral, Limit, Subs, UnevaluatedExpr
    z = Add(oo, -oo, evaluate=False)
    for v in (Subs(nan, x, 1), Limit(nan, x, 0), UnevaluatedExpr(nan), Subs(z, x, 1), Limit(z, x, 0)):
        a, s = Abs(v, evaluate=False), sign(v, evaluate=False)
        assert may_be_nan(v)
        assert ask(Q.extended_nonnegative(a)) is None, v
        assert ask(Q.finite(s)) is None, v
    # evaluated: Abs keeps an unevaluated integral, which diverges (the
    # integral of r over the real line has no value)
    a = Abs(Integral(r, (r, -oo, oo)))
    assert isinstance(a, Abs)
    assert fresh().is_many(a, ['extended_nonnegative', 'extended_real']) == [None, None]
    # an integral over an infinite range may be nan: its limits are values
    from sympy import Piecewise, exp
    assert fresh().is_(Abs(Integral(exp(-x), (x, 0, oo))), 'extended_nonnegative') is None
    # #236 review: a Piecewise without a True branch has no value where no
    # condition holds, and a condition on oo - oo, which has no value, may
    # hold nowhere
    pw = Piecewise((1, Eq(z, 0, evaluate=False)))
    assert may_be_nan(pw)
    assert fresh().is_(Abs(pw, evaluate=False), 'extended_nonnegative') is None
    assert ask(Q.finite(sign(pw, evaluate=False))) is None
