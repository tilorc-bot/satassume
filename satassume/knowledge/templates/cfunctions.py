"""Structural templates for ``expm1`` and ``log1p`` of
``sympy.codegen.cfunctions`` (#180, C-NOTMPL).

SymPy does not import ``sympy.codegen`` itself, so this module is declared
with the class names (:meth:`TemplateRegistry.lazy`) and imported when the
first node of one of them is met.

``expm1(x) == exp(x) - 1`` (``expm1(-oo) == -1``, ``expm1(oo) == oo``) and
``log1p(x) == log(x + 1)`` on the principal branch (``log1p(-1) == zoo``,
``log1p(+-oo) == oo``).  The argument is index 0, the node index 1,
``x + 1`` index 2.
"""
from __future__ import annotations

from sympy import S
from sympy.codegen.cfunctions import expm1, log1p

from .functions import _TRANSCENDENTAL, _equiv, _table, _unary, shifted
from .registry import registry

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


registry.register(expm1)(_unary('expm1', _expm1))
registry.register(log1p)(_unary('log1p', _log1p, slots=lambda x: (shifted(x, S.One),)))
