"""Verbatim copies of the ``Abs``, ``re``, ``im``, ``sign`` and
``conjugate`` generators from ``satassume/knowledge/templates/functions.py``
at d149951, before they became rows in ``templates/complex_parts.py``
(#249).  Test-only: ``tests/test_complex_parts_rows.py`` compares the
clauses the rows emit with the clauses these functions emit.  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates.functions import N, X

from _legacy_helpers import _equiv, _table


def _abs(R, c):
    R.rule([], (N, 'extended_real', True))
    R.rule([], (N, 'extended_nonnegative', True))
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(N, 'finite', True)], (X, 'finite', True))
    R.rule([(X, 'infinite', True)], (N, 'extended_positive', True))
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))
    _equiv(R, [(X, 'extended_real', True)], ('integer', 'rational', 'even', 'odd', 'algebraic'))
    # Abs(x) == x for x >= 0.
    _equiv(R, [(X, 'extended_nonnegative', True)], ('prime', 'composite'))


# ``re`` and ``im`` are not extended real for every argument:
# ``re(zoo) = im(zoo) = nan``.  The vocabulary cannot tell ``zoo`` from
# ``oo*I`` (``re(oo*I) = 0``) or ``oo + oo*I``, so an infinite non-real
# argument gets no claim; a finite argument gives a real part, an extended
# real one gives itself (``re``) or zero (``im``).
def _re(R, c):
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'extended_real', True)], (N, 'extended_real', True))
    R.rule([(X, 'imaginary', True)], (N, 'zero', True))
    R.rule([(X, 'zero', True)], (N, 'zero', True))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))
    _equiv(R, [(X, 'extended_real', True)], (
        'zero', 'extended_positive', 'extended_negative', 'integer', 'rational',
        'even', 'odd', 'algebraic', 'finite', 'prime', 'composite'))


def _im(R, c):
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'extended_real', True)], (N, 'zero', True))
    R.rule([(X, 'imaginary', True)], (N, 'nonzero', True))
    # a finite argument is read as a complex number x + I*y (above: im is real)
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'zero', False))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))


_SIGN = (
    (('extended_real',), 'integer'),
    (('imaginary',), 'imaginary'),
    (('extended_positive',), 'positive'),
    (('extended_positive',), 'odd'),
    (('extended_negative',), 'negative'),
    (('extended_negative',), 'odd'),
    (('extended_nonnegative',), 'nonnegative'),
    (('extended_nonpositive',), 'nonpositive'),
    (('algebraic',), 'algebraic'),
)


def _sign(R, c):
    R.rule([], (N, 'complex', True))
    _table(R, _SIGN)
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'extended_real', True), (N, 'positive', True)], (X, 'extended_positive', True))
    R.rule([(X, 'extended_real', True), (N, 'negative', True)], (X, 'extended_negative', True))


# Invariant under conjugation; the rule base derives the rest (real, the
# finite sign predicates, nonzero, infinite, irrational, transcendental...).
_CONJUGATE_INVARIANT = (
    'extended_real', 'finite', 'zero', 'extended_positive', 'extended_negative',
    'integer', 'rational', 'even', 'odd', 'algebraic', 'complex', 'imaginary',
    'prime', 'composite', 'commutative', 'hermitian', 'antihermitian',
)


def _conjugate(R, c):
    _equiv(R, [], _CONJUGATE_INVARIANT)
