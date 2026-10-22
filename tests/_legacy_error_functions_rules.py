"""Verbatim copies of the ``erf``, ``erfc``, ``erfi``, ``Ei``, ``Si``,
``Shi``, ``Ci``, ``Chi``, ``fresnels`` and ``fresnelc`` generators from
``satassume/knowledge/templates/special.py`` at d149951, before they became
rows in ``templates/error_functions.py`` (#249).  Test-only:
``tests/test_error_functions_rows.py`` compares the clauses the rows emit
with the clauses these functions emit.  Do not edit them to follow a later
rule change; change the test's reference instead (``git show
d149951:satassume/knowledge/templates/special.py``)."""
from satassume.knowledge.templates.functions import X, _equiv, _table

from _legacy_helpers import _ENTIRE, _SIGNS


def _erf(R, c):
    _table(R, _ENTIRE + (
        (('extended_real',), 'real'),
        (('zero',), 'zero'),
        (('imaginary',), 'imaginary'),
        (('real', ('zero', False)), ('integer', False)),
        (('infinite', 'extended_positive'), 'odd'),
        (('infinite', 'extended_negative'), 'odd'),
    ))
    _equiv(R, [(X, 'extended_real', True)], _SIGNS)


def _erfc(R, c):
    _table(R, _ENTIRE + (
        (('extended_real',), 'real'),
        (('extended_real',), 'nonnegative'),
        (('real',), 'positive'),
        (('real', ('zero', False)), ('integer', False)),
        (('zero',), 'odd'),
        (('infinite', 'extended_positive'), 'zero'),
        (('infinite', 'extended_negative'), 'even'),
        (('infinite', 'extended_negative'), 'positive'),
        (('imaginary',), ('extended_real', False)),
        (('imaginary',), ('imaginary', False)),
    ))


def _erfi(R, c):
    _table(R, _ENTIRE + (
        (('real',), 'real'),
        (('extended_real',), 'extended_real'),
        (('infinite', 'extended_real'), 'infinite'),
        (('zero',), 'zero'),
        (('imaginary',), 'imaginary'),
    ))
    _equiv(R, [(X, 'extended_real', True)], _SIGNS)



def _ei(R, c):
    _table(R, (
        (('zero',), 'infinite'), (('zero',), 'extended_negative'),
        (('negative',), 'negative'), (('positive',), 'real'),
        (('infinite', 'extended_positive'), 'infinite'),
        (('infinite', 'extended_positive'), 'extended_positive'),
        (('infinite', 'extended_negative'), 'zero'),
        (('complex', ('zero', False)), 'complex'),
    ))



def _si(R, c):
    _table(R, _ENTIRE + ((('extended_real',), 'real'), (('zero',), 'zero'),
                        (('imaginary',), 'imaginary')))
    _equiv(R, [(X, 'extended_real', True)], _SIGNS)


def _shi(R, c):
    _table(R, _ENTIRE + ((('real',), 'real'), (('extended_real',), 'extended_real'),
                        (('infinite', 'extended_real'), 'infinite'),
                        (('zero',), 'zero'), (('imaginary',), 'imaginary')))
    _equiv(R, [(X, 'extended_real', True)], _SIGNS)


def _ci_chi(R, ci):
    _table(R, (
        (('positive',), 'real'),
        (('zero',), 'infinite'),
        (('negative',), ('extended_real', False)),
        (('complex', ('zero', False)), 'complex'),
    ))
    if ci:
        _table(R, ((('infinite', 'extended_positive'), 'zero'),
                  (('infinite', 'extended_negative'), 'imaginary')))
    else:
        _table(R, ((('infinite', 'extended_real'), 'infinite'),
                  (('infinite', 'extended_real'), 'extended_positive')))



def _fresnel(R, c):
    _table(R, _ENTIRE + (
        (('extended_real',), 'real'),
        (('zero',), 'zero'),
        (('imaginary',), 'imaginary'),
        (('infinite', 'extended_real'), 'rational'),
        (('extended_real', ('zero', False)), ('integer', False)),
    ))
    _equiv(R, [(X, 'extended_real', True)], _SIGNS)

