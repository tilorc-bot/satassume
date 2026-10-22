"""Verbatim copies of the ``RoundFunction``, ``floor``, ``ceiling`` and
``factorial`` generators from ``satassume/knowledge/templates/functions.py``
at d149951, before they became rows in ``templates/integer_funcs.py``
(#249).  Test-only: ``tests/test_integer_funcs_rows.py`` compares the
clauses the rows emit with the clauses these functions emit.  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates._common import ge2_alternatives
from satassume.knowledge.templates.functions import (
    N,
    X,
    _equiv,
    _table,
)


def _round(R, c):
    R.equiv([], (N, 'finite', True), (X, 'finite', True))
    # NOTE: floor(1 + I/2) == 1, so "non-real -> non-integer" is unsound.
    R.rule([(X, 'real', True)], (N, 'integer', True))
    R.rule([(X, 'extended_real', True)], (N, 'extended_real', True))
    R.rule([(X, 'complex', True)], (N, 'complex', True))
    # a real value of floor/ceiling is an integer (floor(1 + I/2) == 1 is
    # real; floor(oo) == oo is not)
    R.rule([(N, 'real', True)], (N, 'integer', True))
    _equiv(R, [(X, 'integer', True)], ('even', 'odd', 'zero', 'positive', 'negative'))


def _floor(R, c):
    for pred in ('negative', 'extended_negative', 'nonnegative', 'extended_nonnegative'):
        R.rule([(X, pred, True)], (N, pred, True))


def _ceiling(R, c):
    for pred in ('positive', 'extended_positive', 'nonpositive', 'extended_nonpositive'):
        R.rule([(X, pred, True)], (N, pred, True))


_FACTORIAL = (
    (('integer', 'nonnegative'), 'positive'),
    (('integer', 'nonnegative'), 'integer'),
    (('composite',), 'composite'),
    (('zero',), 'odd'),
    (('nonnegative',), 'positive'),
    (('noninteger', 'finite'), 'real'),
    (('noninteger', 'finite'), ('zero', False)),
    (('integer', 'negative'), 'infinite'),
    (('integer', 'negative'), ('extended_real', False)),
)


def _factorial(R, c):
    _table(R, _FACTORIAL)
    for prem in ge2_alternatives(X):
        R.rule(prem, (N, 'even', True))
