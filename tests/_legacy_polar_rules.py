"""Verbatim copies of the ``exp_polar``, ``polar_lift`` and
``principal_branch`` generators from
``satassume/knowledge/templates/functions.py`` at d149951, before they
became rows in ``templates/polar.py`` (#249).  Test-only:
``tests/test_polar_rows.py`` compares the clauses the rows emit with the
clauses these functions emit.  Do not edit them to follow a later rule
change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates.functions import N, X


def _polar(R, n):
    """Arguments 0 (and 1, the period, for ``n == 2``), node ``n``."""
    R.rule([(0, 'finite', True)] + ([(1, 'positive', True)] if n == 2 else []), (n, 'polar', True))


def _exp_polar(R, c):
    _polar(R, N)
    R.rule([(X, 'real', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'rational', True))
    R.rule([(X, 'real', True), (X, 'algebraic', True), (X, 'zero', False)],
           (N, 'transcendental', True))
