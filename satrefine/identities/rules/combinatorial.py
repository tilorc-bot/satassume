"""``factorial``, ``binomial``, ``RisingFactorial``, ``FallingFactorial`` and
``gamma`` as rule tables.

Each row is ``(lhs, rhs)`` or ``(lhs, rhs, hypothesis)``, compiled by
:func:`..core.rewrite.rule_handler`: the row fires when its hypothesis, with
the facts ``ASSUMED`` about the variables of its left side, is provable
through the dispatcher's ``ask``.  The rules are those stated in
``handlers_v3/combinatorial.py`` (236 lines), every one agreeing with
SymPy's own evaluation at every point its hypothesis allows (0, negative
integers and poles included, where both sides are ``zoo``).  **16 rows**
replacing 236 lines: 2 shared by ``binomial``/``rf``/``ff``, then factorial 2,
gamma 2, binomial 4, rf 3, ff 3.

Spellings.  v3 decides ``a == b`` as ``Q.zero(a - b)`` or the relation
``Q.eq(a, b)``, and order as a sign of the difference or a relation; the
hypotheses below spell both, e.g. ``Q.zero(z) | Q.eq(z, 0)``.

Minimizations against v3:

* ``z == 0 -> 1`` and ``z == 1 -> x`` hold for ``binomial``, ``rf`` and
  ``ff`` alike: two rows over a generic two-argument head ``G``, shared by
  the three tables.
* Rules of one function with the same right side are one row with a
  disjunctive hypothesis (``binomial``: ``n`` a negative integer and
  ``0 <= y < n`` are one ``-> 0`` row; ``rf``: its two ``-> 0`` rules).
* ``rf(x, z) -> gamma(x + z)/gamma(x)`` for a positive integer ``x`` is
  turned into factorials by the ``gamma`` rows, not by a row of its own.

Pattern forms used beyond the current engine (requested in
``tests/refine_identities/needs/test_combinatorial_needs.py``): two-argument
heads with both arguments bound, and literal ``0``/``1`` bindings; ``ask``
raising ``ValueError`` on a relation read as "not provable".

Not expressible as rows: none.  The refusals of v3 (no ``gamma`` form for
a nonpositive integer ``x`` in ``rf``, no ``binomial(y, y) -> 1`` for a
possibly negative integer ``y``, half-integer ``gamma`` left alone) are the
hypotheses' missing cases.
Checked (adversarial pass, 2026-09-24): every row at 0, +-1, negative
integers, half-integers, non-real points and +-oo, with ``Q.eq`` against
``-oo``, old-style symbols, plus ``python -m satrefine.tools.refine_differential`` seeds 2,
3, 7 (1,500 cases each).  Found: ``~Q.integer`` admits ``oo``, where
``binomial(y, y) -> 1`` and ``binomial(y, y - 1) -> y`` are wrong
(``binomial(oo, oo) = nan``) and so is ``rf(x, z) -> gamma(x + z)/gamma(x)``
(``rf(oo, 2) = oo``); those branches now need ``Q.finite``.  v3 shares the
defect, so the battery's three ``~Q.integer``-only cases are misses.  Not
defects: the ``binomial`` pole row for infinite ``z`` (``binomial(-3, oo) =
zoo``), the ``rf`` zero row and ``rf(1, z)`` for infinite ``z``, the ``z ==
0``/``z == 1`` rows for an infinite first argument.  Unverified: the gamma
ratio where SymPy leaves ``rf`` of a non-integer ``z`` unevaluated
(``rf(1/2, -1/2)``, ``rf(-I, I)``: no value to compare; the ratio is the
definition).
"""
from __future__ import annotations

from sympy import (Function, Q, S, binomial, factorial, ff, gamma, rf,
                   symbols)

from ._tables import Family, Rules

x, y, z = symbols('x y z')   # arbitrary: x and y are first arguments, z the second
G = Function('G')        # generic head: binomial, rf and ff share these rows


def _eq(u, v):
    return Q.zero(u - v) | Q.eq(u, v)


def _lt(u, v):
    """``u < v`` as a sign of either difference or as a relation (the engines
    do not always relate ``Q.positive(v - u)`` to ``Q.negative(u - v)``)."""
    return Q.positive(v - u) | Q.negative(u - v) | Q.lt(u, v)


def _le(u, v):
    return Q.nonnegative(v - u) | Q.nonpositive(u - v) | Q.le(u, v)


bit, f, g, h, inf, l, m, n, one, p, q, zero = symbols('bit f g h inf l m n one p q zero')

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {
    _eq(zero, 0),                                  # zero is 0
    _eq(one, 1),                                   # one is 1
    _eq(bit, 0) | _eq(bit, 1),                     # bit is 0 or 1
    Q.integer(n),                                  # n is an integer
    ~Q.integer(h),                                 # h is not an integer
    Q.integer(q) & _lt(q, 0),                      # q is negative, here a negative integer
    Q.integer(m) & Q.nonnegative(m),               # m is an integer, here nonnegative
    Q.integer(p) & _lt(0, p),                      # p is positive, here a positive integer
    Q.integer(l) & _le(l, 0),                      # l is a nonpositive integer
    Q.positive_infinite(inf),                      # inf is oo
    # f is nonnegative or a finite non-integer: not a negative integer (binomial(-1, -1) = 0)
    # and not infinite (binomial(oo, oo) = nan, and oo is not an integer)
    Q.nonnegative(f) | (~Q.integer(f) & Q.finite(f)),
    # g is positive or a finite non-integer: gamma(g) is finite and nonzero (never a
    # nonpositive integer: rf(-2, 2) = 2; never oo: rf(oo, 2) = oo, gamma(oo)/gamma(oo) is not)
    Q.positive(g) | (~Q.integer(g) & Q.finite(g)),
}

SMALL_K = [
    # binomial(y, 0) = rf(x, 0) = ff(x, 0) = 1, for every first argument.
    (G(x, zero), S.One),
    # binomial(y, 1) = y, rf(x, 1) = ff(x, 1) = x.
    (G(x, one), x),
]

FACTORIAL = [
    # 0! = 1! = 1.
    (factorial(bit), S.One),
    # q! is a pole at every negative integer (not rewritten to gamma elsewhere).
    (factorial(q), S.ComplexInfinity),
    # factorial(oo) = oo (gamma grows without bound along the positive axis).
    (factorial(inf), S.Infinity),
]

GAMMA = [
    # gamma(p) = (p - 1)! at positive integers (so gamma(m + 1) = m! for m >= 0).
    (gamma(p), factorial(p - 1)),
    # gamma has a pole at every nonpositive integer (half-integers are left alone).
    (gamma(l), S.ComplexInfinity),
]

BINOMIAL = SMALL_K + [
    # binomial(f, f) = 1.
    (binomial(f, z), S.One, _eq(f, z)),
    # binomial(f, f - 1) = f.
    (binomial(f, z), f, _eq(z, f - 1)),
    # 0 for a negative integer n whatever y is (SymPy's convention), and for
    # integers 0 <= y < n (the product y (y-1) ... hits 0).
    (binomial(y, n), S.Zero, _lt(n, 0) | (Q.integer(y) & Q.nonnegative(y) & _lt(y, n))),
    # A pole: q a negative integer and h not an integer.
    (binomial(q, h), S.ComplexInfinity),
]

RISING = SMALL_K + [
    # rf(1, z) = gamma(z + 1) = z!, for every z.
    (rf(one, z), factorial(z)),
    # 0 when the product x (x+1) ... (x+z-1) contains the factor 0 (x <= 0 < x + z,
    # integers), and SymPy's 0 for a negative integer x and non-integer z.
    (rf(x, z), S.Zero, (Q.integer(x) & Q.integer(z) & _le(x, 0) & _lt(0, x + z))
                       | (Q.integer(x) & _lt(x, 0) & ~Q.integer(z))),
    # rf(g, z) = gamma(g + z)/gamma(g) where gamma(g) is finite and nonzero.
    (rf(g, z), gamma(g + z)/gamma(g)),
]

FALLING = SMALL_K + [
    # ff(n, n) = n! for integer n (both sides zoo at negative integers).
    (ff(x, n), factorial(n), _eq(x, n)),
    # 0 for integers 0 <= m < n.
    (ff(m, n), S.Zero, _lt(m, n)),
    # ff(m, n) = m!/(m - n)! for integers 0 <= m, n <= m (negative n included:
    # ff(3, -2) = 1/20 = 3!/5!).
    (ff(m, n), factorial(m)/factorial(m - n), _le(n, m)),
]

RULES: list[tuple] = SMALL_K + FACTORIAL + GAMMA + [
    row for table in (BINOMIAL, RISING, FALLING) for row in table[len(SMALL_K):]]

SPEC = Family({'factorial': Rules(FACTORIAL), 'binomial': Rules(BINOMIAL), 'RisingFactorial': Rules(RISING),
               'FallingFactorial': Rules(FALLING), 'gamma': Rules(GAMMA)},
              rules=RULES, assumed=ASSUMED)
