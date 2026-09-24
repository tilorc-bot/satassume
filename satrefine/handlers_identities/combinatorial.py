"""``factorial``, ``binomial``, ``RisingFactorial``, ``FallingFactorial`` and
``gamma`` as rule tables.

Each row is ``(lhs, rhs, hypothesis)``, compiled by
:func:`._specialize.compile_table`: the row fires when its hypothesis is
provable through ``_upstream.ask``.  The rules are those stated in
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
``-oo``, old-style symbols, plus ``tools/refine_differential.py`` seeds 2,
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

from .._upstream import handlers_dict
from ._specialize import compile_table

n, k, x = symbols('n k x')
G = Function('G')        # generic head: binomial, rf and ff share these rows


def _eq(u, v):
    return Q.zero(u - v) | Q.eq(u, v)


def _lt(u, v):
    """``u < v`` as a sign of either difference or as a relation (the engines
    do not always relate ``Q.positive(v - u)`` to ``Q.negative(u - v)``)."""
    return Q.positive(v - u) | Q.negative(u - v) | Q.lt(u, v)


def _le(u, v):
    return Q.nonnegative(v - u) | Q.nonpositive(u - v) | Q.le(u, v)


SMALL_K = [
    # binomial(n, 0) = rf(x, 0) = ff(x, 0) = 1, for every first argument.
    (G(x, k), S.One, _eq(k, 0)),
    # binomial(n, 1) = n, rf(x, 1) = ff(x, 1) = x.
    (G(x, k), x, _eq(k, 1)),
]

FACTORIAL = [
    # 0! = 1! = 1.
    (factorial(n), S.One, _eq(n, 0) | _eq(n, 1)),
    # n! is a pole at every negative integer (not rewritten to gamma elsewhere).
    (factorial(n), S.ComplexInfinity, Q.integer(n) & _lt(n, 0)),
]

GAMMA = [
    # gamma(x) = (x - 1)! at positive integers (so gamma(n + 1) = n! for n >= 0).
    (gamma(x), factorial(x - 1), Q.integer(x) & _lt(0, x)),
    # gamma has a pole at every nonpositive integer (half-integers are left alone).
    (gamma(x), S.ComplexInfinity, Q.integer(x) & _le(x, 0)),
]

BINOMIAL = SMALL_K + [
    # binomial(n, n) = 1 unless n is a negative integer (binomial(-1, -1) = 0)
    # or infinite (binomial(oo, oo) = nan, and oo is not an integer).
    (binomial(n, k), S.One, _eq(n, k) & (Q.nonnegative(n) | (~Q.integer(n) & Q.finite(n)))),
    # binomial(n, n - 1) = n, same proviso (binomial(-1, -2) = 0, binomial(oo, oo) = nan).
    (binomial(n, k), n, _eq(k, n - 1) & (Q.nonnegative(n) | (~Q.integer(n) & Q.finite(n)))),
    # 0 for a negative integer k whatever n is (SymPy's convention), and for
    # integers 0 <= n < k (the product n (n-1) ... hits 0).
    (binomial(n, k), S.Zero, Q.integer(k) & (_lt(k, 0)
                             | (Q.integer(n) & Q.nonnegative(n) & _lt(n, k)))),
    # A pole: n a negative integer and k not an integer.
    (binomial(n, k), S.ComplexInfinity, Q.integer(n) & _lt(n, 0) & ~Q.integer(k)),
]

RISING = SMALL_K + [
    # rf(1, k) = gamma(k + 1) = k!, for every k.
    (rf(x, k), factorial(k), _eq(x, 1)),
    # 0 when the product x (x+1) ... (x+k-1) contains the factor 0 (x <= 0 < x + k,
    # integers), and SymPy's 0 for a negative integer x and non-integer k.
    (rf(x, k), S.Zero, (Q.integer(x) & Q.integer(k) & _le(x, 0) & _lt(0, x + k))
                       | (Q.integer(x) & _lt(x, 0) & ~Q.integer(k))),
    # rf(x, k) = gamma(x + k)/gamma(x) where gamma(x) is finite and nonzero: x positive
    # or a finite non-integer (never for a nonpositive integer x: rf(-2, 2) = 2;
    # never for x = oo, which is not an integer: rf(oo, 2) = oo, gamma(oo)/gamma(oo) is not).
    (rf(x, k), gamma(x + k)/gamma(x), Q.positive(x) | (~Q.integer(x) & Q.finite(x))),
]

FALLING = SMALL_K + [
    # ff(k, k) = k! for integer k (both sides zoo at negative integers).
    (ff(x, k), factorial(k), Q.integer(k) & _eq(x, k)),
    # 0 for integers 0 <= x < k.
    (ff(x, k), S.Zero, Q.integer(x) & Q.nonnegative(x) & Q.integer(k) & _lt(x, k)),
    # ff(x, k) = x!/(x - k)! for integers 0 <= x, k <= x (negative k included:
    # ff(3, -2) = 1/20 = 3!/5!).
    (ff(x, k), factorial(x)/factorial(x - k),
     Q.integer(x) & Q.nonnegative(x) & Q.integer(k) & _le(k, x)),
]

RULES: list[tuple] = SMALL_K + FACTORIAL + GAMMA + [
    row for table in (BINOMIAL, RISING, FALLING) for row in table[len(SMALL_K):]]

handlers_dict['factorial'] = compile_table(FACTORIAL)
handlers_dict['binomial'] = compile_table(BINOMIAL)
handlers_dict['RisingFactorial'] = compile_table(RISING)
handlers_dict['FallingFactorial'] = compile_table(FALLING)
handlers_dict['gamma'] = compile_table(GAMMA)
