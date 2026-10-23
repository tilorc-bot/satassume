"""Verbatim copies of the ``gamma``, ``loggamma``, ``polygamma``,
``digamma``, ``trigamma``, ``lowergamma`` and ``uppergamma`` generators
from ``satassume/knowledge/templates/special.py`` at d149951, before they
became rows in ``templates/gamma_functions.py`` (#249).  Test-only:
``tests/test_gamma_functions_rows.py`` compares the clauses the rows emit
with the clauses these functions emit.  Do not edit them to follow a later
rule change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/special.py``)."""
from sympy import S

from satassume.knowledge.templates.functions import N, X

from _legacy_helpers import _table

#: the slot of x - 1/2 (``slots=lambda x: (shifted(x, -S.Half),)``)
M = 2


def _gamma(R, c):
    _table(R, (
        (('positive',), 'positive'),
        (('real', ('integer', False)), 'real'),
        (('real', ('integer', False)), ('zero', False)),
        (('integer', 'nonpositive'), 'infinite'),
        (('integer', 'nonpositive'), ('extended_real', False)),
        (('complex', ('extended_real', False)), 'complex'),
        (('complex', ('extended_real', False)), ('zero', False)),
        (('infinite', 'extended_positive'), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
        (('integer', 'positive'), 'integer'),
    ))
    # x == s + 1/2 < 0 with s even lies in (s, s + 1), s == -n with n even
    R.rule([(M, 'even', True), (X, 'negative', True), (X, 'integer', False)],
           (N, 'positive', True))
    R.rule([(M, 'odd', True), (X, 'negative', True), (X, 'integer', False)],
           (N, 'negative', True))


# the slot x - 1/2 as wiring.template builds it from gen.shifts (#184)
_gamma.shifts = (-S.Half,)


def _loggamma(R, c):
    _table(R, (
        (('positive',), 'real'),
        (('real', ('integer', False)), 'complex'),
        (('negative', ('integer', False)), ('extended_real', False)),
        (('integer', 'nonpositive'), 'infinite'),
        (('complex', ('extended_real', False)), 'complex'),
        # not "non-real x -> non-real value": gamma is real on a curve
        # through its minimum x0 ~ 1.4616, so loggamma is real at
        # 7/5 + 0.6388873...*I (#194 review)
        (('infinite',), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
    ))


def _polygamma_rules(R, n, z, node, order=None):
    """``order`` is the constant order (digamma 0, trigamma 1) or None."""
    def k(*lits):
        return [(n, p, v) for p, v in lits] if order is None else []

    nonneg = k(('integer', True), ('nonnegative', True))
    R.rule([*nonneg, (z, 'positive', True)], (node, 'real', True))
    R.rule([*nonneg, (z, 'real', True), (z, 'integer', False)], (node, 'real', True))
    R.rule([*nonneg, (z, 'complex', True), (z, 'extended_real', False)], (node, 'complex', True))
    R.rule([*nonneg, (z, 'integer', True), (z, 'nonpositive', True)], (node, 'infinite', True))
    R.rule([*nonneg, (z, 'integer', True), (z, 'nonpositive', True)],
           (node, 'extended_real', False))
    if order is None or order > 0:
        odd = k(('odd', True), ('positive', True))
        even = k(('even', True), ('positive', True))
        pos = k(('integer', True), ('positive', True))
        if order is None or order % 2:
            R.rule([*odd, (z, 'positive', True)], (node, 'positive', True))
            R.rule([*odd, (z, 'real', True), (z, 'integer', False)], (node, 'positive', True))
        if order is None or not order % 2:
            R.rule([*even, (z, 'positive', True)], (node, 'negative', True))
        R.rule([*pos, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'zero', True))
    if order is None or order == 0:
        zero = k(('zero', True))
        R.rule([*zero, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'infinite', True))
        R.rule([*zero, (z, 'infinite', True), (z, 'extended_positive', True)],
               (node, 'extended_positive', True))


def _polygamma(R, n):
    if n == 2:
        _polygamma_rules(R, 0, 1, 2)


def _lowergamma(R, n):
    if n == 2:
        R.rule([(0, 'positive', True), (1, 'positive', True)], (2, 'positive', True))


def _uppergamma(R, n):
    if n == 2:
        R.rule([(0, 'real', True), (1, 'positive', True)], (2, 'positive', True))
