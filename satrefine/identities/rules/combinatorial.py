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
hypotheses below spell both, e.g. ``Q.zero(k) | Q.eq(k, 0)``.

Minimizations against v3:

* ``k == 0 -> 1`` and ``k == 1 -> x`` hold for ``binomial``, ``rf`` and
  ``ff`` alike: two rows over a generic two-argument head ``G``, shared by
  the three tables.
* Rules of one function with the same right side are one row with a
  disjunctive hypothesis (``binomial``: ``k`` a negative integer and
  ``0 <= n < k`` are one ``-> 0`` row; ``rf``: its two ``-> 0`` rules).
* ``rf(x, k) -> gamma(x + k)/gamma(x)`` for a positive integer ``x`` is
  turned into factorials by the ``gamma`` rows, not by a row of its own.

Pattern forms used beyond the current engine (requested in
``tests/refine_identities/needs/test_combinatorial_needs.py``): two-argument
heads with both arguments bound, and literal ``0``/``1`` bindings; ``ask``
raising ``ValueError`` on a relation read as "not provable".

Not expressible as rows: none.  The refusals of v3 (no ``gamma`` form for
a nonpositive integer ``x`` in ``rf``, no ``binomial(n, n) -> 1`` for a
possibly negative integer ``n``, half-integer ``gamma`` left alone) are the
hypotheses' missing cases.
Checked (adversarial pass, 2026-09-24): every row at 0, +-1, negative
integers, half-integers, non-real points and +-oo, with ``Q.eq`` against
``-oo``, old-style symbols, plus ``python -m satrefine.tools.refine_differential`` seeds 2,
3, 7 (1,500 cases each).  Found: ``~Q.integer`` admits ``oo``, where
``binomial(n, n) -> 1`` and ``binomial(n, n - 1) -> n`` are wrong
(``binomial(oo, oo) = nan``) and so is ``rf(x, k) -> gamma(x + k)/gamma(x)``
(``rf(oo, 2) = oo``); those branches now need ``Q.finite``.  v3 shares the
defect, so the battery's three ``~Q.integer``-only cases are misses.  Not
defects: the ``binomial`` pole row for infinite ``k`` (``binomial(-3, oo) =
zoo``), the ``rf`` zero row and ``rf(1, k)`` for infinite ``k``, the ``k ==
0``/``k == 1`` rows for an infinite first argument.  Unverified: the gamma
ratio where SymPy leaves ``rf`` of a non-integer ``k`` unevaluated
(``rf(1/2, -1/2)``, ``rf(-I, I)``: no value to compare; the ratio is the
definition).
"""
from __future__ import annotations

from sympy import (Function, Q, S, binomial, factorial, ff, gamma, rf,
                   symbols)

from ._tables import Family, Rules

n, k, x = symbols('n k x')   # arbitrary: n and x are first arguments, k the second
G = Function('G')        # generic head: binomial, rf and ff share these rows


def _eq(u, v):
    return Q.zero(u - v) | Q.eq(u, v)


def _lt(u, v):
    """``u < v`` as a sign of either difference or as a relation (the engines
    do not always relate ``Q.positive(v - u)`` to ``Q.negative(u - v)``)."""
    return Q.positive(v - u) | Q.negative(u - v) | Q.lt(u, v)


def _le(u, v):
    return Q.nonnegative(v - u) | Q.nonpositive(u - v) | Q.le(u, v)


a, b, g, h, i, m, p, q, u, v, w, z = symbols('a b g h i m p q u v w z')

# Assumed throughout: a row takes each fact whose variables are all in its left side.
ASSUMED = {
    _eq(z, 0),                                     # z is 0
    _eq(u, 1),                                     # u is 1
    _eq(v, 0) | _eq(v, 1),                         # v is 0 or 1
    Q.integer(i),                                  # i is an integer
    ~Q.integer(h),                                 # h is not an integer
    Q.integer(m) & _lt(m, 0),                      # m is a negative integer
    Q.integer(a) & Q.nonnegative(a),               # a is a nonnegative integer
    Q.integer(p) & _lt(0, p),                      # p is a positive integer
    Q.integer(q) & _le(q, 0),                      # q is a nonpositive integer
    Q.positive_infinite(w),                        # w is oo
    # b is nonnegative or a finite non-integer: not a negative integer (binomial(-1, -1) = 0)
    # and not infinite (binomial(oo, oo) = nan, and oo is not an integer)
    Q.nonnegative(b) | (~Q.integer(b) & Q.finite(b)),
    # g is positive or a finite non-integer: gamma(g) is finite and nonzero (never a
    # nonpositive integer: rf(-2, 2) = 2; never oo: rf(oo, 2) = oo, gamma(oo)/gamma(oo) is not)
    Q.positive(g) | (~Q.integer(g) & Q.finite(g)),
}

SMALL_K = [
    # binomial(n, 0) = rf(x, 0) = ff(x, 0) = 1, for every first argument.
    (G(x, z), S.One),
    # binomial(n, 1) = n, rf(x, 1) = ff(x, 1) = x.
    (G(x, u), x),
]

FACTORIAL = [
    # 0! = 1! = 1.
    (factorial(v), S.One),
    # n! is a pole at every negative integer (not rewritten to gamma elsewhere).
    (factorial(m), S.ComplexInfinity),
    # factorial(oo) = oo (gamma grows without bound along the positive axis).
    (factorial(w), S.Infinity),
]

GAMMA = [
    # gamma(p) = (p - 1)! at positive integers (so gamma(n + 1) = n! for n >= 0).
    (gamma(p), factorial(p - 1)),
    # gamma has a pole at every nonpositive integer (half-integers are left alone).
    (gamma(q), S.ComplexInfinity),
]

BINOMIAL = SMALL_K + [
    # binomial(b, b) = 1.
    (binomial(b, k), S.One, _eq(b, k)),
    # binomial(b, b - 1) = b.
    (binomial(b, k), b, _eq(k, b - 1)),
    # 0 for a negative integer i whatever n is (SymPy's convention), and for
    # integers 0 <= n < i (the product n (n-1) ... hits 0).
    (binomial(n, i), S.Zero, _lt(i, 0) | (Q.integer(n) & Q.nonnegative(n) & _lt(n, i))),
    # A pole: m a negative integer and h not an integer.
    (binomial(m, h), S.ComplexInfinity),
]

RISING = SMALL_K + [
    # rf(1, k) = gamma(k + 1) = k!, for every k.
    (rf(u, k), factorial(k)),
    # 0 when the product x (x+1) ... (x+k-1) contains the factor 0 (x <= 0 < x + k,
    # integers), and SymPy's 0 for a negative integer x and non-integer k.
    (rf(x, k), S.Zero, (Q.integer(x) & Q.integer(k) & _le(x, 0) & _lt(0, x + k))
                       | (Q.integer(x) & _lt(x, 0) & ~Q.integer(k))),
    # rf(g, k) = gamma(g + k)/gamma(g) where gamma(g) is finite and nonzero.
    (rf(g, k), gamma(g + k)/gamma(g)),
]

FALLING = SMALL_K + [
    # ff(i, i) = i! for integer i (both sides zoo at negative integers).
    (ff(x, i), factorial(i), _eq(x, i)),
    # 0 for integers 0 <= a < i.
    (ff(a, i), S.Zero, _lt(a, i)),
    # ff(a, i) = a!/(a - i)! for integers 0 <= a, i <= a (negative i included:
    # ff(3, -2) = 1/20 = 3!/5!).
    (ff(a, i), factorial(a)/factorial(a - i), _le(i, a)),
]

RULES: list[tuple] = SMALL_K + FACTORIAL + GAMMA + [
    row for table in (BINOMIAL, RISING, FALLING) for row in table[len(SMALL_K):]]

SPEC = Family({'factorial': Rules(FACTORIAL), 'binomial': Rules(BINOMIAL), 'RisingFactorial': Rules(RISING),
               'FallingFactorial': Rules(FALLING), 'gamma': Rules(GAMMA)},
              rules=RULES, assumed=ASSUMED)
