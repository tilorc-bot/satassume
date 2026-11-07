"""`live.py port`: small queries aimed at the lines the planted port bugs in `port_mutants.py` change, where dev and ground
don't reach them or can't show them. Picked to reach those lines, so they say nothing about how often that happens."""
from sympy import Ne, Q, Rational, Symbol, pi, symbols


def queries():
    x, y = symbols("x y")
    n = symbols("n", integer=True)
    third = Rational(1, 3)
    return [
        # offset_sign: the offset reduces to [0, 1), so only an offset whose negative reduces differently can show it.
        (Q.integer(x + third), Q.integer(x - third)),
        (Q.integer(x), Q.integer(x + third)),
        (Q.integer(x + third), Q.eq(x, Rational(2, 3))),
        (Q.integer(x + third), Q.eq(x, third)),
        (Q.integer(2*x + third), Q.eq(x, Rational(1, 3))),
        (Q.integer(y - x + third), Q.eq(y - x, Rational(2, 3))),
        # negated_parity: a negated atom
        (Q.ne(x, 1), Q.eq(x, 1)),
        (Q.ne(x, 1), Q.gt(x, 1)),
        (Q.nonzero(x - 1), Q.ne(x, 1) & Q.gt(y, 0)),
        (Q.gt(x, 0), Q.ne(x, 0) & Q.ge(x, 0)),
        (Q.gt(y, x), Q.ne(x, y) & Q.le(x, y)),
        # forget_skipped: a term new to this payload, then a coefficient that moves the session
        (Q.gt(x + pi*y, 0), Q.gt(y, 0)),
        (Q.gt(x + pi*y + n, 0), Q.gt(x, 0) & Q.gt(y, 0)),
        (Q.gt(x, 0), Q.gt(y + pi*x, 1) & Q.gt(y, 2)),
        # last_object: equal terms, different objects
        (Q.gt(Symbol("z") + 1, 0), Q.gt(Symbol("z"), 0)),
        (Q.gt(x*y + 1, 0), Q.gt(y*x, 0)),
        # negated_parity again, if `Ne` comes in another way
        (Ne(x, 1), Q.eq(x, 1)),
        (Q.gt(x, 1), Ne(x, 1) & Q.ge(x, 1)),
        (Q.real(x), Ne(x, 1)),
    ]
