"""Verbatim copies of the ``erf2``, ``erfinv``, ``erfcinv``, ``expint``,
``li``, ``Li`` and ``owens_t`` generators from
``satassume/knowledge/templates/special.py`` at d149951, before they
became rows in ``templates/error_functions.py`` (#249).  Test-only: ``tests/test_error_functions_2_rows.py`` compares the clauses
the rows emit with the clauses these functions emit.  Do not edit them to
follow a later rule change; change the test's reference instead (``git
show d149951:satassume/knowledge/templates/special.py``)."""
from _legacy_helpers import _table

X, N, M, Q = 0, 1, 2, 3


def _erf2(R, n):
    """erf2(x, y) = erf(y) - erf(x)."""
    if n == 2:
        for pred, concl in (('extended_real', 'real'), ('finite', 'finite'),
                            ('complex', 'complex')):
            R.rule([(0, pred, True), (1, pred, True)], (2, concl, True))
        R.rule([(0, 'zero', True), (1, 'zero', True)], (2, 'zero', True))


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


def _expint(R, n):
    if n == 2:
        R.rule([(0, 'real', True), (1, 'positive', True)], (2, 'positive', True))


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


def _owens_t(R, n):
    if n != 2:
        return
    h, a, node = 0, 1, 2
    R.rule([(h, 'extended_real', True), (a, 'extended_real', True)], (node, 'real', True))
    # owens_t(nan, 0) is nan (and owens_t(x + y, 0) at x = oo, y = -oo)
    for hp in ('complex', 'extended_real'):
        R.rule([(h, hp, True), (a, 'zero', True)], (node, 'zero', True))
    R.rule([(h, 'infinite', True), (h, 'extended_real', True), (a, 'extended_real', True)],
           (node, 'zero', True))
    for hp in ('real', 'imaginary'):
        sign = 'extended_' if hp == 'real' else ''
        R.rule([(h, hp, True), (a, sign + 'positive', True)], (node, 'positive', True))
        R.rule([(h, hp, True), (a, sign + 'negative', True)], (node, 'negative', True))
    R.rule([(h, 'imaginary', True), (a, 'real', True)], (node, 'real', True))


# Not verbatim: the slots x + c of each generator's registration at
# d149951 (``slots=lambda x: (shifted(x, S.NegativeOne), shifted(x,
# S.One))``, ``slots=_minus(1, 2)``, ``slots=_minus(1)``), as
# templates/_rows.py's rules() records them for rows.
_erfinv.shifts = (-1, 1)
_erfcinv.shifts = (-1, -2)
_li.shifts = (-1,)
_Li.shifts = (-1, -2)
# and the number of arguments of the n-ary ones (``nary('erf2', _erf2)``
# and the like), which wiring.template takes from gen.arity
for _gen in (_erf2, _expint, _owens_t):
    _gen.arity = 2
