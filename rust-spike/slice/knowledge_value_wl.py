"""A workload for `value_units`, as `knowledge_fresh.py value`. dev and fuzz hold no call to a function of VALUE_AT_INTEGER or to
multigamma, so a MATCH on them says nothing about this path. Each row goes through `functions._value_units` or `special.py`:
integer arguments on both sides of the limit of 200, other constants, a value that is also an input term (`value:input`), and a
symbol beside the node, so the facts reach a theory.
"""
from sympy import Float, Integer, Q, Rational, Symbol, multigamma

from satassume.knowledge.templates.wiring import VALUE_AT_INTEGER

PREDS = (Q.positive, Q.negative, Q.zero, Q.integer, Q.even, Q.odd, Q.prime, Q.rational)
#: The limit itself and one past it, on both sides, around a run of small values.
INTEGERS = (-250, -201, -200, -199, -100, *range(-5, 31), 50, 100, 150, 199, 200, 201, 250)
OTHER_CONSTANTS = (Rational(1, 2), Rational(-3, 2), Float(2.0), Float(-1.0), Float(2.5))


def queries():
    x = Symbol('x', positive=True)
    out = []
    for fn in VALUE_AT_INTEGER:
        for c in (*map(Integer, INTEGERS), *OTHER_CONSTANTS):
            node = fn(c, evaluate=False)
            out.extend((p(node), True) for p in PREDS)
            out.append((Q.positive(x * node), Q.positive(x)))
            out.append((Q.eq(node, x), Q.negative(x)))
            if c.is_Integer and -30 <= c <= 30:
                try:
                    v = fn(c)
                except (ValueError, TypeError, ArithmeticError):
                    continue
                if v.is_Integer:
                    # The value is an input term here too.
                    out.append((Q.positive(node + v), True))
                    out.append((Q.eq(node, v), True))
    for a in (Integer(-1), Integer(1), Integer(2), Integer(5), Rational(1, 2), Float(-1.0), Float(2.5)):
        for k in (1, 2, 3):
            node = multigamma(a, k, evaluate=False)
            out.extend((p(node), True) for p in PREDS)
    return out
