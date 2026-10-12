"""``factorial``, ``binomial``, ``RisingFactorial``, ``FallingFactorial`` and
``gamma`` as rule tables.

Every row agrees with SymPy's own evaluation at every point its hypothesis
allows (0, negative integers and poles included, where both sides are
``zoo``).

Spellings.  v3 decides ``a == b`` as ``Q.zero(a - b)`` or the relation
``Q.eq(a, b)``; the hypotheses below spell both (``_eq``), since satassume
relates neither to the other when a side may be a finite non-real number
(``f`` below).  Order is the relation alone (``Q.lt``, ``Q.le``): every
ordered side here is an integer, where satassume proves the relation from
either sign of the difference and from the relation.

Merged rows:

* ``z == 0 -> 1`` and ``z == 1 -> x`` hold for ``binomial``, ``rf`` and
  ``ff`` alike: two rows over a generic two-argument head ``G`` (``SMALL_K``),
  which serve all three.
* Rules of one function with the same right side are one row with a
  disjunctive hypothesis (``binomial``: ``n`` a negative integer and
  ``0 <= y < n`` are one ``-> 0`` row; ``rf``: its two ``-> 0`` rules).
* ``rf(x, z) -> gamma(x + z)/gamma(x)`` for a positive integer ``x`` is
  turned into factorials by the ``gamma`` rows, not by a row of its own.

Pattern forms the rows rely on: two-argument heads with both arguments
bound, and literal ``0``/``1`` bindings; ``ask`` raising ``ValueError`` on a
relation read as "not provable".

The refusals of v3 (no ``gamma`` form for a nonpositive integer ``x`` in
``rf``, no ``binomial(y, y) -> 1`` for a possibly negative integer ``y``,
half-integer ``gamma`` left alone) are the hypotheses' missing cases.
Unverified: the gamma ratio where SymPy leaves ``rf`` of a non-integer ``z``
unevaluated (``rf(1/2, -1/2)``, ``rf(-I, I)``: no value to compare; the ratio
is the definition).
"""
from __future__ import annotations

from sympy import (Function, Q, S, binomial, factorial, ff, gamma, rf,
                   symbols)

from ._tables import add_rules

x, y, z = symbols('x y z')   # arbitrary: x and y are first arguments, z the second
G = Function('G')        # generic head: binomial, rf and ff share these rows


def _eq(u, v):
    return Q.zero(u - v) | Q.eq(u, v)


bit, f, g, h, inf, m, n, one, p, q, zero = symbols('bit f g h inf m n one p q zero')

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {
    _eq(zero, 0),
    _eq(one, 1),
    _eq(bit, 0) | _eq(bit, 1),
    Q.integer(n),
    ~Q.integer(h),
    Q.integer(q) & Q.lt(q, 0),
    Q.integer(m) & Q.nonnegative(m),
    Q.integer(p) & Q.lt(0, p),
    Q.positive_infinite(inf),
    # f is nonnegative or a finite non-integer: not a negative integer (binomial(-1, -1) = 0)
    # and not infinite (binomial(oo, oo) = nan, and oo is not an integer)
    Q.nonnegative(f) | (~Q.integer(f) & Q.finite(f)),
    # g is positive or a finite non-integer: gamma(g) is finite and nonzero (never a
    # nonpositive integer: rf(-2, 2) = 2; never oo: rf(oo, 2) = oo, gamma(oo)/gamma(oo) is not)
    Q.positive(g) | (~Q.integer(g) & Q.finite(g)),
}

SMALL_K = add_rules(set(), [
    # binomial(y, 0) = rf(x, 0) = ff(x, 0) = 1, for every first argument.
    (G(x, zero), S.One),
    # binomial(y, 1) = y, rf(x, 1) = ff(x, 1) = x.
    (G(x, one), x),
])

FACTORIAL = add_rules(set(), [
    # 0! = 1! = 1.
    (factorial(bit), S.One),
    # q! is a pole at every negative integer (not rewritten to gamma elsewhere).
    (factorial(q), S.ComplexInfinity),
    # factorial(oo) = oo (gamma grows without bound along the positive axis).
    (factorial(inf), S.Infinity),
])

GAMMA = (
    add_rules(set(), [
        # gamma(p) = (p - 1)! at positive integers (so gamma(m + 1) = m! for m >= 0).
        (gamma(p), factorial(p - 1)),
    ])
    + add_rules({Q.le(n, 0)}, [
        # gamma has a pole at every nonpositive integer (half-integers are left alone).
        (gamma(n), S.ComplexInfinity),
    ])
)

BINOMIAL = (
    add_rules({_eq(f, z)}, [
        (binomial(f, z), S.One),             # binomial(f, f) = 1
    ])
    + add_rules({_eq(z, f - 1)}, [
        (binomial(f, z), f),                 # binomial(f, f - 1) = f
    ])
    + add_rules({Q.lt(n, 0) | (Q.integer(y) & Q.nonnegative(y) & Q.lt(y, n))}, [
        # 0 for a negative integer n whatever y is (SymPy's convention), and for
        # integers 0 <= y < n (the product y (y-1) ... hits 0).
        (binomial(y, n), S.Zero),
    ])
    + add_rules(set(), [
        # A pole: q a negative integer and h not an integer.
        (binomial(q, h), S.ComplexInfinity),
    ])
)

RISING = (
    add_rules(set(), [
        # rf(1, z) = gamma(z + 1) = z!, for every z.
        (rf(one, z), factorial(z)),
    ])
    + add_rules({(Q.integer(x) & Q.integer(z) & Q.le(x, 0) & Q.lt(0, x + z))
                 | (Q.integer(x) & Q.lt(x, 0) & ~Q.integer(z))}, [
        # 0 when the product x (x+1) ... (x+z-1) contains the factor 0 (x <= 0 < x + z,
        # integers), and SymPy's 0 for a negative integer x and non-integer z.
        (rf(x, z), S.Zero),
    ])
    + add_rules(set(), [
        # rf(g, z) = gamma(g + z)/gamma(g) where gamma(g) is finite and nonzero.
        (rf(g, z), gamma(g + z)/gamma(g)),
    ])
)

FALLING = (
    add_rules({_eq(x, n)}, [
        (ff(x, n), factorial(n)),            # ff(n, n) = n! for integer n (both sides zoo at negative integers)
    ])
    + add_rules({Q.lt(m, n)}, [
        (ff(m, n), S.Zero),                  # 0 for integers 0 <= m < n
    ])
    + add_rules({Q.le(n, m)}, [
        # ff(m, n) = m!/(m - n)! for integers 0 <= m, n <= m (negative n included:
        # ff(3, -2) = 1/20 = 3!/5!).
        (ff(m, n), factorial(m)/factorial(m - n)),
    ])
)

RULES: list[tuple] = SMALL_K + FACTORIAL + GAMMA + BINOMIAL + RISING + FALLING
