"""Verbatim copies of the ``factorial2``, ``subfactorial``, ``catalan``,
``andre``, ``partition``, ``genocchi``, ``RisingFactorial``,
``FallingFactorial`` and ``binomial`` generators from
``satassume/knowledge/templates/combinatorial.py`` at d149951, before they
became rows in ``templates/combinatorial.py`` (#249).  Test-only:
``tests/test_combinatorial_rows.py`` compares the clauses the rows emit
with the clauses these functions emit.  Do not edit them to follow a
later rule change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/combinatorial.py``)."""
from satassume.knowledge.templates.functions import _table

X, N = 0, 1


def _factorial2(R, c):
    R.rule([(X, 'integer', True), (2, 'nonnegative', True)], (N, 'positive', True))
    R.rule([(X, 'integer', True), (2, 'nonnegative', True)], (N, 'integer', True))
    # odd n >= -3: an odd integer; any odd n: a rational, never even
    R.rule([(X, 'odd', True), (3, 'nonnegative', True)], (N, 'odd', True))
    _table(R, (
        (('odd',), 'rational'), (('odd',), ('zero', False)), (('odd',), ('even', False)),
        (('zero',), 'odd'), (('zero',), 'positive'),
        (('even', 'positive'), 'even'), (('even', 'positive'), 'positive'),
    ))


def _subfactorial(R, c):
    _table(R, (
        (('integer', 'nonnegative'), 'integer'), (('integer', 'nonnegative'), 'nonnegative'),
        (('odd', 'nonnegative'), 'even'), (('even', 'nonnegative'), 'odd'),
    ))


def _catalan(R, c):
    _table(R, (
        (('nonnegative',), 'positive'),
        (('integer', 'nonnegative'), 'integer'),
    ))
    R.rule([(X, 'integer', True), (2, 'positive', True)], (N, 'composite', True))


def _andre(R, c):
    _table(R, ((('integer', 'nonnegative'), 'integer'), (('integer', 'nonnegative'), 'positive')))


def _partition(R, c):
    _table(R, (
        (('integer',), 'integer'), (('integer',), 'nonnegative'),
        (('integer', 'negative'), 'zero'), (('integer', 'nonnegative'), 'positive'),
    ))


def _genocchi(R, c):
    _table(R, (
        (('integer', 'nonnegative'), 'integer'),
        (('zero',), 'zero'),
        (('even', 'positive'), 'odd'),
    ))
    R.rule([(X, 'odd', True), (2, 'zero', True)], (N, 'odd', True))
    R.rule([(X, 'odd', True), (2, 'zero', True)], (N, 'negative', True))
    R.rule([(X, 'odd', True), (2, 'positive', True)], (N, 'zero', True))
    R.rule([(X, 'even', True), (X, 'positive', True), (3, 'even', True)], (N, 'positive', True))
    R.rule([(X, 'even', True), (X, 'positive', True), (3, 'odd', True)], (N, 'negative', True))


_K = ((1, 'integer', True), (1, 'nonnegative', True))


def _rising_falling(R, n, positive):
    for pred in ('integer', 'rational', 'real'):
        R.rule([(0, pred, True), *_K], (2, pred, True))
    if positive:
        R.rule([(0, 'positive', True), *_K], (2, 'positive', True))
    else:
        # ff(n, k) == n!/(n - k)! for k <= n, 0 for k > n
        R.rule([(0, 'integer', True), (0, 'nonnegative', True), *_K], (2, 'nonnegative', True))
    # 1 at k = 0 for every x but nan, which SymPy propagates first
    # (rf(x + y, 0) is nan at x = oo, y = -oo); zoo is left out
    for xp in ('complex', 'extended_real'):
        R.rule([(0, xp, True), (1, 'zero', True)], (2, 'odd', True))
        R.rule([(0, xp, True), (1, 'zero', True)], (2, 'positive', True))


def _binomial(R, n):
    R.rule([(0, 'integer', True), (1, 'integer', True)], (2, 'integer', True))
    R.rule([(1, 'integer', True), (1, 'negative', True)], (2, 'zero', True))
    R.rule([(1, 'zero', True)], (2, 'odd', True))
    R.rule([(1, 'zero', True)], (2, 'positive', True))
    R.rule([(0, 'integer', True), (0, 'nonnegative', True), (1, 'integer', True)],
           (2, 'nonnegative', True))
    # binomial(n, k) == (-1)**k*binomial(k - n - 1, k) for n < 0
    R.rule([(0, 'integer', True), (1, 'even', True)], (2, 'nonnegative', True))
