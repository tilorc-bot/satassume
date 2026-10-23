"""Verbatim copies of the ``exp`` and ``log`` generators and of
``exp_templates`` from ``satassume/knowledge/templates/functions.py`` at
d149951, before they became rows in ``templates/exp_log.py`` (#249).
Test-only: ``tests/test_exp_log_rows.py`` compares the clauses the rows
emit with the clauses these functions emit, and the pattern keys and slot
objects of ``exp_templates`` with those of the template from the rows.
``exp_templates`` is not registered here (``@registry.register(exp)`` is
left out: a test module's template would count as a user's).  Do not edit
them to follow a later rule change; change the test's reference instead
(``git show d149951:satassume/knowledge/templates/functions.py``)."""
from satassume.knowledge.templates._common import Rules, const_key, facts
from satassume.knowledge.templates.core import ipi_rules, ipi_split
from satassume.knowledge.templates.functions import M, N, X

from _legacy_helpers import _table


_EXP = (
    (('extended_real',), 'extended_real'),
    (('extended_real',), 'extended_nonnegative'),
    (('real',), 'positive'),
    (('finite',), 'finite'),
    (('finite',), ('zero', False)),
    (('complex',), 'complex'),
    (('extended_negative',), 'complex'),
    (('algebraic', ('zero', False)), 'transcendental'),
    (('infinite', 'extended_negative'), 'zero'),
    (('infinite', 'extended_positive'), 'infinite'),
    (('infinite', 'extended_positive'), 'extended_positive'),
)

_LOG = (
    (('extended_positive',), 'extended_real'),
    (('positive',), 'real'),
    (('zero',), 'infinite'),
    (('zero',), ('extended_real', False)),
    (('complex', ('zero', False)), 'complex'),
    (('finite', ('zero', False)), 'finite'),
    (('infinite',), 'infinite'),
    (('infinite', 'extended_real'), 'extended_positive'),
    (('negative',), ('extended_real', False)),
    (('complex', ('extended_real', False)), ('extended_real', False)),
)


def _exp(R, c, ipi=None):
    _table(R, _EXP)
    # exp(0) == 1
    R.rule([(X, 'zero', True)], (N, 'odd', True))
    R.rule([(X, 'zero', True)], (N, 'positive', True))
    if ipi is not None:
        c, has_s = ipi
        ipi_rules(R.rule, c, M if has_s else None, N)


def exp_templates(expr):
    """``exp(x)``; for ``x == I*pi*c*s`` (``c`` rational) the value is a
    root of unity or on the unit circle, described in terms of ``s``."""
    x = expr.args[0]
    consts = {}
    objs = [x, expr]
    ipi = None
    if x.is_Atom and x.is_number:
        consts[X] = x
        key = ('exp', const_key(x))
    else:
        split = ipi_split(x)
        if split is not None:
            c, s_ = split
            ipi = (c, s_ is not None)
            if s_ is not None:
                objs.append(s_)
                if s_.is_Atom and s_.is_number:
                    consts[M] = s_
        key = ('exp', None, ipi, const_key(objs[M]) if M in consts else None)

    def build():
        R = Rules()
        _exp(R, consts.get(X), ipi)
        return R.rules

    return facts(key, build, consts, tuple(objs), N)


def _log(R, c):
    _table(R, _LOG)
    # log(x) == 0 iff x == 1; log(x) > 0 iff x > 1 for positive x.
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(M, 'extended_positive', True)], (N, 'extended_positive', True))
    R.rule([(M, 'negative', True), (X, 'positive', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (N, 'positive', True)], (M, 'positive', True))
    R.rule([(X, 'positive', True), (N, 'negative', True)], (M, 'negative', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


# Not verbatim: the slot x - 1 of log's registration at d149951
# (``slots=_minus_one``), as templates/_rows.py's rules() records it for
# rows.
_log.shifts = (-1,)
