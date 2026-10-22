"""Verbatim copies of the ``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech``
and ``csch`` generators from ``satassume/knowledge/templates/functions.py``
at f9291ab (unchanged up to d149951), before they became rows in
``templates/hyperbolic.py`` (#249).  Test-only:
``tests/test_hyperbolic_rows.py`` compares the clauses the rows emit with
the clauses these functions emit.  Do not edit them to follow a later rule
change; change the test's reference instead (``git show
f9291ab:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates.functions import (
    N,
    X,
    _TRANSCENDENTAL,
    _equiv,
    _table,
)

from _legacy_helpers import _finite_value


_SINH = (
    (('real',), 'real'), (('extended_real',), 'extended_real'),
    (('finite',), 'finite'), (('complex',), 'complex'),
    (('infinite', 'extended_real'), 'infinite'), _TRANSCENDENTAL,
)
_COSH = (
    (('real',), 'positive'), (('extended_real',), 'extended_positive'),
    (('finite',), 'finite'), (('complex',), 'complex'), (('zero',), 'odd'),
    (('imaginary',), 'real'), _TRANSCENDENTAL,
)


def _sinh(R, c):
    _table(R, _SINH)
    _equiv(R, [(X, 'extended_real', True)], ('extended_positive', 'extended_negative', 'zero'))
    R.rule([(X, 'imaginary', True)], [(N, 'imaginary', True), (N, 'zero', True)])


def _cosh(R, c):
    _table(R, _COSH)


def _tanh(R, c):
    _table(R, ((('extended_real',), 'real'), _TRANSCENDENTAL))
    for pred in ('positive', 'negative'):
        R.equiv([(X, 'extended_real', True)], (N, pred, True), (X, 'extended_' + pred, True))
    R.equiv([(X, 'extended_real', True)], (N, 'zero', True), (X, 'zero', True))


_COTH = (
    (('extended_real', ('zero', False)), 'real'),   # coth(+-oo) == +-1
    (('extended_positive',), 'positive'),           # coth(x) > 1 for x > 0
    (('extended_negative',), 'negative'),
    (('extended_real',), ('imaginary', False)),     # coth(0) == zoo
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    # coth(a) == (exp(2*a) + 1)/(exp(2*a) - 1), exp(2*a) != 1
    (('algebraic', ('zero', False)), 'transcendental'),
)


def _coth(R, c):
    _table(R, _COTH)
    _finite_value(R, 'complex')
    # coth(I*t) == -I*cot(t): imaginary, 0 (t == pi/2) or zoo (t == pi)
    R.rule([(X, 'imaginary', True)], [(N, 'extended_real', False), (N, 'zero', True)])
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], [(N, 'imaginary', True), (N, 'zero', True)])


_SECH = (
    (('extended_real',), 'real'),                   # sech(+-oo) == 0
    (('extended_real',), 'nonnegative'),
    (('real',), 'positive'),
    (('infinite', 'extended_real'), 'zero'),
    (('zero',), 'odd'),
    (('imaginary',), ('imaginary', False)),         # sech(I*t) == sec(t)
    (('complex',), ('zero', False)),
    _TRANSCENDENTAL,
)
_CSCH = (
    (('extended_real', ('zero', False)), 'real'),   # csch(+-oo) == 0
    (('positive',), 'positive'), (('negative',), 'negative'),
    (('extended_positive',), 'nonnegative'), (('extended_negative',), 'nonpositive'),
    (('infinite', 'extended_real'), 'zero'),
    (('extended_real',), ('imaginary', False)),     # csch(0) == zoo
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    (('imaginary',), ('extended_real', False)),     # csch(I*t) == -I/sin(t)
    (('complex',), ('zero', False)),
    _TRANSCENDENTAL,
)


def _sech(R, c):
    _table(R, _SECH)
    _finite_value(R, 'complex')
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], (N, 'real', True))


def _csch(R, c):
    _table(R, _CSCH)
    _finite_value(R, 'complex')
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], (N, 'imaginary', True))
