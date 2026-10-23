"""Verbatim copies of ``_mul_rules`` and ``ipi_rules`` from
``satassume/templates/core.py`` at 876f37d, before they became tables
(issue #97, P6).  Test-only: ``tests/test_template_tables.py`` compares the
clauses the tables emit with the clauses these functions emit.  The copy of
``_pow_rules`` went with ``POW_TABLE`` (#294: Pow's rows are compared with
``tests/_legacy_pow_rules.py``).  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show 876f37d:satassume/templates/core.py``)."""
from itertools import combinations

from sympy import S

from satassume.knowledge.templates._common import SIGN_FLIP, Rules, lits
from satassume.knowledge.templates.core import (
    _COEFF_BACK,
    _MUL_CLOSED,
    MAX_ONEOUT,
    MAX_PAIRS,
)


def mul_rules(n, consts):
    R = Rules()
    rule = R.rule
    N = n
    A = range(n)

    for pred in _MUL_CLOSED:
        rule(lits(A, pred), (N, pred, True))
    # Extended reals, all finite or all nonzero (no 0*oo).
    rule([*lits(A, 'extended_real'), *lits(A, 'finite')], (N, 'extended_real', True))
    rule([*lits(A, 'extended_real'), *lits(A, 'zero', False)], (N, 'extended_real', True))
    # A commutative product has a commutative factor k when every other
    # factor is a nonzero number: k is the product divided by them.  Not
    # in general: ``0*A == 0`` (#47), and ``A*B`` is 1 for ``B = A**-1``.
    if n <= MAX_ONEOUT:
        for k in A:
            rest = [j for j in A if j != k]
            rule([(N, 'commutative', True), *lits(rest, 'complex'), *lits(rest, 'zero', False)],
                 (k, 'commutative', True))

    # Zero: some zero factor with the rest finite; nonzero: all nonzero and
    # at most one of them non-commutative (non-commutative values have zero
    # divisors: ``A*B == 0`` and ``A**2 == 0`` for nilpotent ``A = B``).
    for k in A:
        rule([(k, 'zero', True), *lits([j for j in A if j != k], 'finite')], (N, 'zero', True))
    if n <= MAX_ONEOUT:
        for k in A:
            rule(lits([j for j in A if j != k], 'commutative'), [*lits(A, 'zero'), (N, 'zero', False)])
    else:
        rule(lits(A, 'commutative'), [*lits(A, 'zero'), (N, 'zero', False)])

    # Hermitian product of commuting hermitian factors.
    rule([*lits(A, 'commutative'), *lits(A, 'hermitian')], (N, 'hermitian', True))

    # Polar: all polar, or one polar factor and the rest positive.
    rule(lits(A, 'polar'), (N, 'polar', True))
    for k in A:
        rule([(k, 'polar', True), *lits([j for j in A if j != k], 'positive')],
             (N, 'polar', True))

    if n >= 2:
        rule(lits(A, 'prime'), (N, 'composite', True))

    # All factors negative / nonpositive / imaginary: parity of n.
    even_n = n % 2 == 0
    rule(lits(A, 'extended_negative'),
         (N, 'extended_positive' if even_n else 'extended_negative', True))
    rule(lits(A, 'nonpositive'), (N, 'nonnegative' if even_n else 'nonpositive', True))
    rule(lits(A, 'imaginary'), (N, 'nonzero' if even_n else 'imaginary', True))
    rule(lits(A, 'odd'), (N, 'odd', True))

    if n <= MAX_ONEOUT:
        for k in A:
            rest = [j for j in A if j != k]
            # One infinite factor and the rest nonzero -> infinite.
            rule([(k, 'infinite', True), *lits(rest, 'zero', False)], (N, 'infinite', True))
            # Exactly one negative factor (rest positive) -> negative.
            rule([(k, 'extended_negative', True), *lits(rest, 'extended_positive')],
                 (N, 'extended_negative', True))
            rule([(k, 'nonpositive', True), *lits(rest, 'nonnegative')], (N, 'nonpositive', True))
            # One even factor and the rest integers -> even.
            rule([(k, 'even', True), *lits(rest, 'integer')], (N, 'even', True))
            # One composite factor and the rest integers -> not prime (the
            # product is 0, negative, or a multiple of a composite).
            rule([(k, 'composite', True), *lits(rest, 'integer')], (N, 'prime', False))
            # One irrational factor and the rest nonzero rationals -> irrational.
            rule([(k, 'irrational', True), *lits(rest, 'rational'), *lits(rest, 'zero', False)],
                 (N, 'irrational', True))
            # One transcendental factor and the rest nonzero algebraics ->
            # transcendental (the algebraic numbers are a field).
            rule([(k, 'transcendental', True), *lits(rest, 'algebraic'), *lits(rest, 'zero', False)],
                 (N, 'transcendental', True))
            # One non-real factor and the rest nonzero extended reals -> not real.
            rule([(k, 'extended_real', False), *lits(rest, 'extended_nonzero')],
                 (N, 'extended_real', False))
            # One imaginary factor and the rest nonzero finite reals -> imaginary;
            # with the rest merely real the product may also be zero.
            rule([(k, 'imaginary', True), *lits(rest, 'real'), *lits(rest, 'zero', False)],
                 (N, 'imaginary', True))
            rule([(k, 'imaginary', True), *lits(rest, 'real')],
                 [(N, 'imaginary', True), (N, 'zero', True)])
            if n == 2:
                # i*a*(c + i*d) has real part -a*d and imaginary part a*c:
                # the product is real iff the other factor is imaginary or
                # zero, and imaginary iff the other factor is a nonzero real.
                l = rest[0]
                rule([(k, 'imaginary', True), (l, 'complex', True), (N, 'extended_real', True)],
                     [(l, 'imaginary', True), (l, 'zero', True)])
                rule([(k, 'imaginary', True), (l, 'complex', True), (N, 'imaginary', True)],
                     (l, 'real', True))

    if 3 <= n <= MAX_PAIRS:
        # Sign of a product with m negative factors, 2 <= m < n (one negative
        # factor is above, all negative is above).
        for m in range(2, n):
            for neg in combinations(A, m):
                rest = [j for j in A if j not in neg]
                sign = 'extended_positive' if m % 2 == 0 else 'extended_negative'
                rule([*lits(neg, 'extended_negative'), *lits(rest, 'extended_positive')],
                     (N, sign, True))
                sign = 'nonnegative' if m % 2 == 0 else 'nonpositive'
                rule([*lits(neg, 'nonpositive'), *lits(rest, 'nonnegative')], (N, sign, True))
        for k, l in combinations(A, 2):
            rest = [j for j in A if j != k and j != l]
            rule([(k, 'imaginary', True), (l, 'imaginary', True),
                  *lits(rest, 'real'), *lits(rest, 'zero', False)], (N, 'nonzero', True))

    # Numeric coefficient c*x: transfer facts back from the product to x.
    if n == 2 and 0 in consts and consts[0].is_Number:
        c = consts[0]
        if c.is_finite and c.is_extended_real and not c.is_zero:
            flip = c.is_negative
            for pred in _COEFF_BACK:
                rule([(N, pred, True)], (1, SIGN_FLIP.get(pred, pred) if flip else pred, True))
            if c.is_Rational:
                rule([(N, 'rational', True)], (1, 'rational', True))
                rule([(N, 'algebraic', True)], (1, 'algebraic', True))
                if c.q == 2:
                    # (p/2)*x for integer x is an integer iff x is even.
                    R.equiv([(1, 'integer', True)], (N, 'integer', True), (1, 'even', True))
                elif c is S.NegativeOne:
                    for pred in ('integer', 'even', 'odd'):
                        rule([(N, pred, True)], (1, pred, True))
    return R.rules


def ipi_rules(rule, c, iS, N):
    """Rules for ``node == exp(I*pi*c*s)``: a root of unity when ``s`` is an
    integer, on the unit circle when ``s`` is real.  ``iS`` is the slot of
    ``s`` (None: ``s == 1``)."""
    if iS is None:
        if c.is_integer:
            rule([], (N, 'odd', True))
            rule([], (N, 'positive' if c.p % 2 == 0 else 'negative', True))
        elif c.q == 2:
            rule([], (N, 'imaginary', True))
            rule([], (N, 'algebraic', True))
        else:
            for lit in ((N, 'algebraic', True), (N, 'extended_real', False),
                        (N, 'imaginary', False), (N, 'zero', False)):
                rule([], lit)
        return
    rule([(iS, 'integer', True)], (N, 'algebraic', True))
    rule([(iS, 'real', True)], (N, 'complex', True))
    rule([(iS, 'real', True)], (N, 'zero', False))
    if c.is_integer:
        rule([(iS, 'integer', True)], (N, 'odd', True))
        if c.p % 2 == 0:
            rule([(iS, 'integer', True)], (N, 'positive', True))
        else:
            rule([(iS, 'even', True)], (N, 'positive', True))
            rule([(iS, 'odd', True)], (N, 'negative', True))
            rule([(iS, 'integer', True), (N, 'positive', True)], (iS, 'even', True))
            rule([(iS, 'integer', True), (N, 'negative', True)], (iS, 'odd', True))
    elif c.q == 2:
        rule([(iS, 'even', True)], (N, 'odd', True))
        rule([(iS, 'odd', True)], (N, 'imaginary', True))
