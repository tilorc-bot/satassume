"""``Max``, ``Min`` and ``Piecewise``: nodes whose value is one of a few
given expressions (#180, C-NOTMPL), as rows with a star (#299).

``f(*values)`` is a node of any number of values: the arguments of ``Max``
and ``Min``, the expressions of a ``Piecewise`` (``wiring.ARGUMENTS``).
The value of ``Max(a_1, ..., a_n)`` and ``Min(...)`` is one of its
arguments (SymPy requires them to be comparable; ``Max(I, x)`` raises, and
so does ``Max(x, 1).subs(x, I)``: a non-real argument gives no value), and
the value of a ``Piecewise`` whose last condition is ``True`` is one of its
expressions.  A ``Piecewise`` without a final ``True`` is ``nan`` where no
condition holds (``Piecewise((1, x < 1)).subs(x, 2)``), and one of
Booleans has no value of these predicates: neither gets rules (wiring).

A rule over too many clauses is left out of a wide node, not encoded
(``wiring.LEAVE_OUT_WIDE``): a premise ``~Q.odd`` of each value is a
disjunction over the basis, so ``n`` of them expand to ``2**n`` clauses.
"""
from __future__ import annotations

from sympy import Max, Min, Piecewise, Q

from ._rows import every, f, for_all, value, values

RULES = (
    # Value is one of the arguments
    #     a property of every value is one of the node, and so is its
    #     negation; the positive literal of a conjunction (real, positive)
    #     follows from those of its conjuncts
    for_all((Max, Min, Piecewise),
        every(Q.algebraic, values) >> Q.algebraic(f(*values)),
        every(~Q.algebraic, values) >> ~Q.algebraic(f(*values)),
        every(Q.complex, values) >> Q.complex(f(*values)),
        every(~Q.complex, values) >> ~Q.complex(f(*values)),
        every(Q.composite, values) >> Q.composite(f(*values)),
        every(~Q.composite, values) >> ~Q.composite(f(*values)),
        every(Q.even, values) >> Q.even(f(*values)),
        every(~Q.even, values) >> ~Q.even(f(*values)),
        every(Q.extended_negative, values) >> Q.extended_negative(f(*values)),
        every(~Q.extended_negative, values) >> ~Q.extended_negative(f(*values)),
        every(Q.extended_positive, values) >> Q.extended_positive(f(*values)),
        every(~Q.extended_positive, values) >> ~Q.extended_positive(f(*values)),
        every(Q.extended_real, values) >> Q.extended_real(f(*values)),
        every(~Q.extended_real, values) >> ~Q.extended_real(f(*values)),
        every(Q.finite, values) >> Q.finite(f(*values)),
        every(~Q.finite, values) >> ~Q.finite(f(*values)),
        every(Q.imaginary, values) >> Q.imaginary(f(*values)),
        every(~Q.imaginary, values) >> ~Q.imaginary(f(*values)),
        every(Q.integer, values) >> Q.integer(f(*values)),
        every(~Q.integer, values) >> ~Q.integer(f(*values)),
        every(Q.prime, values) >> Q.prime(f(*values)),
        every(~Q.prime, values) >> ~Q.prime(f(*values)),
        every(Q.rational, values) >> Q.rational(f(*values)),
        every(~Q.rational, values) >> ~Q.rational(f(*values)),
        every(Q.zero, values) >> Q.zero(f(*values)),
        every(~Q.zero, values) >> ~Q.zero(f(*values))),

    # Value is one of the arguments: the negation of a conjunction
    #     ~Q.odd of each value is a disjunction (even or not an integer), so
    #     these are left out of a wide node (wiring.LEAVE_OUT_WIDE)
    for_all((Max, Min, Piecewise),
        every(~Q.odd, values) >> ~Q.odd(f(*values)),
        every(~Q.real, values) >> ~Q.real(f(*values)),
        every(~Q.positive, values) >> ~Q.positive(f(*values)),
        every(~Q.negative, values) >> ~Q.negative(f(*values)),
        every(~Q.nonnegative, values) >> ~Q.nonnegative(f(*values)),
        every(~Q.nonpositive, values) >> ~Q.nonpositive(f(*values)),
        every(~Q.nonzero, values) >> ~Q.nonzero(f(*values)),
        every(~Q.irrational, values) >> ~Q.irrational(f(*values)),
        every(~Q.noninteger, values) >> ~Q.noninteger(f(*values)),
        every(~Q.transcendental, values) >> ~Q.transcendental(f(*values))),

    # Max is at least each argument
    #     one positive argument makes it positive
    for_all((Max,),
        Q.extended_positive(value) >> Q.extended_positive(f(value, *values)),
        Q.extended_nonnegative(value) >> Q.extended_nonnegative(f(value, *values))),

    # Min is at most each argument
    #     one negative argument makes it negative
    for_all((Min,),
        Q.extended_negative(value) >> Q.extended_negative(f(value, *values)),
        Q.extended_nonpositive(value) >> Q.extended_nonpositive(f(value, *values))),
)
