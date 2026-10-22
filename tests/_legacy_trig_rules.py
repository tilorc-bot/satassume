"""Verbatim copies of the ``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and
``csc`` generators from ``satassume/knowledge/templates/functions.py`` at
f9291ab, before they became rows in ``templates/trig.py`` (#249).
Test-only: ``tests/test_trig_rows.py`` compares the clauses the rows emit
with the clauses these functions emit.  Do not edit them to follow a later
rule change; change the test's reference instead (``git show
f9291ab:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates.functions import (
    N,
    X,
    _TRANSCENDENTAL,
    _finite_value,
    _table,
)

# sin(oo*I) == oo*I, so finiteness of the value needs a finite argument.
_SIN = (
    (('real',), 'real'), (('complex',), 'complex'), (('finite',), 'finite'),
    (('zero',), 'zero'), (('imaginary',), 'imaginary'), _TRANSCENDENTAL,
)
_COS = (
    (('real',), 'real'), (('complex',), 'complex'), (('finite',), 'finite'),
    (('zero',), 'odd'), (('zero',), 'positive'), (('imaginary',), 'positive'),
    _TRANSCENDENTAL,
)
_TAN = (
    # tan(pi/2) == zoo, so realness needs finiteness of the value.
    (('real',), ('imaginary', False)), (('zero',), 'zero'),
    (('imaginary',), 'imaginary'), _TRANSCENDENTAL,
)


def _sin(R, c):
    _table(R, _SIN)


def _cos(R, c):
    _table(R, _COS)


def _tan(R, c):
    _table(R, _TAN)
    R.rule([(X, 'real', True), (N, 'finite', True)], (N, 'real', True))
    # tan(x + I*y) has imaginary part sinh(2*y)/(cos(2*x) + cosh(2*y)),
    # nonzero for y != 0 (no poles off the real line); a finite argument
    # is read as a complex number, as for im
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'extended_real', False))


_COT = (
    # cot(k*pi) == zoo, so realness needs finiteness of the value.
    (('real',), ('imaginary', False)),
    (('imaginary',), 'imaginary'),          # cot(I*t) == -I*coth(t)
    (('zero',), 'infinite'),
    (('zero',), ('extended_real', False)),
    # cot(x) == cos(x)/sin(x) is finite for algebraic x != 0 (sin(x) == 0
    # only at multiples of pi) and transcendental by Lindemann-Weierstrass:
    # cot(x) == a algebraic would make exp(2*I*x) algebraic.
    (('algebraic', ('zero', False)), 'transcendental'),
    (('algebraic',), ('algebraic', False)),
)


def _cot(R, c):
    _table(R, _COT)
    R.rule([(X, 'real', True), (N, 'finite', True)], (N, 'real', True))
    # cot == 1/tan, and tan(z) is non-real and nonzero off the real line
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (N, 'finite', True)], (N, 'complex', True))


_SEC = (
    (('real',), ('imaginary', False)),     # sec(pi/2) == zoo
    (('complex',), ('zero', False)),       # cos is finite at a finite point
    (('zero',), 'odd'), (('zero',), 'positive'),
    (('imaginary',), 'positive'),          # sec(I*t) == 1/cosh(t) in (0, 1)
    _TRANSCENDENTAL,
)
_CSC = (
    (('real',), ('imaginary', False)),     # csc(k*pi) == zoo
    (('complex',), ('zero', False)),
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    (('imaginary',), 'imaginary'),         # csc(I*t) == -I/sinh(t)
    _TRANSCENDENTAL,
)


def _sec(R, c):
    _table(R, _SEC)
    _finite_value(R, 'real')
    _finite_value(R, 'complex')


def _csc(R, c):
    _table(R, _CSC)
    _finite_value(R, 'real')
    _finite_value(R, 'complex')
