"""Verbatim copies of the ``expm1`` and ``log1p`` generators from
``satassume/knowledge/templates/cfunctions.py`` at d149951, before they
became rows in ``templates/cfunctions.py`` (#249).  Test-only:
``tests/test_cfunctions_rows.py`` compares the clauses the rows emit with
the clauses these functions emit.  Do not edit them to follow a later
rule change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/cfunctions.py``)."""
from _legacy_helpers import _TRANSCENDENTAL, _equiv, _table

X, N, P1 = 0, 1, 2


_EXPM1 = (
    (('real',), 'real'), (('extended_real',), 'extended_real'),
    (('finite',), 'finite'), (('complex',), 'complex'),
    (('zero',), 'zero'),
    (('infinite', 'extended_negative'), 'negative'),
    (('infinite', 'extended_negative'), 'odd'),
    (('infinite', 'extended_positive'), 'infinite'),
    _TRANSCENDENTAL,
)


def _expm1(R, c):
    _table(R, _EXPM1)
    # exp is increasing on the extended reals and exp(0) == 1; for complex
    # x, expm1(2*I*pi) == 0
    _equiv(R, [(X, 'extended_real', True)], ('extended_positive', 'extended_negative', 'zero'))


def _log1p(R, c):
    # log(y) == 0 iff y == 1
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'real', True), (P1, 'positive', True)], (N, 'real', True))
    R.rule([(X, 'positive', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'positive', True)], (N, 'negative', True))
    # x == -1 and x < -1 (the sign premise on x keeps the block total:
    # nothing relates the slot x + 1 to x)
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'negative', True), (P1, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (P1, 'zero', False)], (N, 'complex', True))
    _table(R, (
        (('infinite',), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
    ))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (P1, 'zero', False)],
           (N, 'transcendental', True))
