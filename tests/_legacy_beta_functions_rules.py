"""Verbatim copies of the ``beta``, ``betainc`` and ``betainc_regularized``
generators from ``satassume/knowledge/templates/special.py`` at d149951,
before they became rows in ``templates/beta_functions.py`` (#249).
Test-only: ``tests/test_beta_functions_rows.py`` compares the clauses the
rows emit with the clauses these functions emit.  Do not edit them to
follow a later rule change; change the test's reference instead (``git
show d149951:satassume/knowledge/templates/special.py``)."""


def _beta(R, n):
    if n in (1, 2):
        R.rule([(k, 'positive', True) for k in range(n)], (n, 'positive', True))


def _betainc(R, n):
    if n != 4:
        return
    ab = [(0, 'integer', True), (0, 'positive', True), (1, 'integer', True), (1, 'positive', True)]
    for pred in ('real', 'rational'):
        R.rule([*ab, (2, pred, True), (3, pred, True)], (4, pred, True))
