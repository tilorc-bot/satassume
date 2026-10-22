"""Verbatim copies of the ``erfinv``, ``erfcinv``, ``li`` and ``Li``
generators from ``satassume/knowledge/templates/special.py`` at d149951,
before they became rows in ``templates/error_functions.py`` (#249).
Test-only: ``tests/test_error_functions_2_rows.py`` compares the clauses
the rows emit with the clauses these functions emit.  Do not edit them to
follow a later rule change; change the test's reference instead (``git
show d149951:satassume/knowledge/templates/special.py``)."""
from satassume.knowledge.templates.functions import _table

X, N, M, Q = 0, 1, 2, 3


def _erfinv(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (Q, 'positive', True)], (N, 'negative', True))
    for concl in ((N, 'infinite', True), (N, 'extended_positive', True)):
        R.rule([(X, 'positive', True), (M, 'zero', True)], concl)
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'negative', True), (Q, 'zero', True)], concl)


def _erfcinv(R, c):
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    # the sign premises on z and z - 1 are implied, but the slots are
    # separate children: without them a block whose children are given
    # contradictory facts is unsatisfiable (tools/totality.py)
    R.rule([(X, 'positive', True), (M, 'positive', True), (Q, 'negative', True)], (N, 'negative', True))
    for concl in ((N, 'infinite', True), (N, 'extended_positive', True)):
        R.rule([(X, 'zero', True), (M, 'negative', True)], concl)
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'positive', True), (M, 'positive', True), (Q, 'zero', True)], concl)


def _li(R, c):
    R.rule([(X, 'zero', True)], (N, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'real', True))
    for concl in ((N, 'infinite', True), (N, 'extended_negative', True)):
        R.rule([(X, 'positive', True), (M, 'zero', True)], concl)
    _table(R, ((('infinite', 'extended_positive'), 'infinite'),
              (('infinite', 'extended_positive'), 'extended_positive')))
    R.rule([(X, 'complex', True), (M, 'zero', False)], (N, 'complex', True))


def _Li(R, c):
    R.rule([(X, 'positive', True), (M, 'zero', False)], (N, 'real', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'negative', True))
    R.rule([(M, 'positive', True), (Q, 'negative', True)], (N, 'negative', True))
    R.rule([(M, 'positive', True), (Q, 'zero', True)], (N, 'zero', True))
    R.rule([(M, 'positive', True), (Q, 'positive', True)], (N, 'positive', True))
    _table(R, ((('infinite', 'extended_positive'), 'infinite'),
              (('infinite', 'extended_positive'), 'extended_positive')))
    R.rule([(X, 'complex', True), (M, 'zero', False)], (N, 'complex', True))


# Not verbatim: the slots x + c of each generator's registration at
# d149951 (``slots=lambda x: (shifted(x, S.NegativeOne), shifted(x,
# S.One))``, ``slots=_minus(1, 2)``, ``slots=_minus(1)``), as
# templates/_rows.py's rules() records them for rows.
_erfinv.shifts = (-1, 1)
_erfcinv.shifts = (-1, -2)
_li.shifts = (-1,)
_Li.shifts = (-1, -2)
