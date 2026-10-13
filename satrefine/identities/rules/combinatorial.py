"""``factorial``, ``binomial``, ``RisingFactorial``, ``FallingFactorial`` and ``gamma``."""
from __future__ import annotations

from sympy import Function, Q, S, binomial, factorial, ff, gamma, rf, symbols

from ._tables import add_rules, equal

x, y, z = symbols('x y z')
G = Function('G')  # any of binomial, rf and ff

bit, f, g, h, inf, m, n, one, p, q, zero = symbols('bit f g h inf m n one p q zero')

SMALL_K = add_rules({equal(zero, 0), equal(one, 1)}, [
    (G(x, zero), S.One),
    (G(x, one), x),
])

FACTORIAL = add_rules({equal(bit, 0) | equal(bit, 1),
                       Q.integer(q) & Q.lt(q, 0),
                       Q.positive_infinite(inf)}, [
    (factorial(bit), S.One),
    (factorial(q), S.ComplexInfinity),
    (factorial(inf), S.Infinity),
])

GAMMA = (
    add_rules({Q.integer(p) & Q.lt(0, p)}, [
        (gamma(p), factorial(p - 1)),
    ])
    + add_rules({Q.integer(n), Q.le(n, 0)}, [
        (gamma(n), S.ComplexInfinity),
    ])
)

BINOMIAL = (
    add_rules({Q.nonnegative(f) | (~Q.integer(f) & Q.finite(f)), equal(f, z)}, [
        (binomial(f, z), S.One),
    ])
    + add_rules({Q.nonnegative(f) | (~Q.integer(f) & Q.finite(f)), equal(z, f - 1)}, [
        (binomial(f, z), f),
    ])
    + add_rules({Q.integer(n), Q.lt(n, 0) | (Q.integer(y) & Q.nonnegative(y) & Q.lt(y, n))}, [
        (binomial(y, n), S.Zero),
    ])
    + add_rules({Q.integer(q) & Q.lt(q, 0), ~Q.integer(h)}, [
        (binomial(q, h), S.ComplexInfinity),
    ])
)

RISING = (
    add_rules({equal(one, 1)}, [
        (rf(one, z), factorial(z)),
    ])
    + add_rules({(Q.integer(x) & Q.integer(z) & Q.le(x, 0) & Q.lt(0, x + z))
                 | (Q.integer(x) & Q.lt(x, 0) & ~Q.integer(z))}, [
        (rf(x, z), S.Zero),
    ])
    + add_rules({Q.positive(g) | (~Q.integer(g) & Q.finite(g))}, [
        (rf(g, z), gamma(g + z)/gamma(g)),
    ])
)

FALLING = (
    add_rules({Q.integer(n), equal(x, n)}, [
        (ff(x, n), factorial(n)),
    ])
    + add_rules({Q.integer(m) & Q.nonnegative(m), Q.integer(n), Q.lt(m, n)}, [
        (ff(m, n), S.Zero),
    ])
    + add_rules({Q.integer(m) & Q.nonnegative(m), Q.integer(n), Q.le(n, m)}, [
        (ff(m, n), factorial(m)/factorial(m - n)),
    ])
)

RULES: list[tuple] = SMALL_K + FACTORIAL + GAMMA + BINOMIAL + RISING + FALLING
