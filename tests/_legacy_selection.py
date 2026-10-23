"""Verbatim copy of ``satassume/knowledge/templates/selection.py`` at eaaa6d2,
before Max, Min and Piecewise became rows (``templates/selection.py``,
#299).  Test-only: ``tests/test_selection_rows.py`` checks with the SAT
solver that the rows entail exactly what these templates emit.  Do not
edit it to follow a later rule change
(``git show eaaa6d2:satassume/knowledge/templates/selection.py``).

Copied unchanged, except that the imports are absolute and the templates
are not registered (no ``@registry.register``).  The legacy docstring:

Structural templates for nodes whose value is one of a few given
expressions: ``Max``, ``Min`` and ``Piecewise`` (#180, C-NOTMPL).

The value of ``Max(a_1, ..., a_n)`` and ``Min(...)`` is one of its
arguments (SymPy requires them to be comparable; ``Max(I, x)`` raises, and
so does ``Max(x, 1).subs(x, I)``: a non-real argument gives no value), and
the value of a ``Piecewise`` whose last condition is ``True`` is one of its
expressions.  So a literal that holds of every candidate holds of the node
(*selection* rules).  A ``Piecewise`` without a final ``True`` is ``nan``
where no condition holds (``Piecewise((1, x < 1)).subs(x, 2)``) and gets
no rule.

The selection rules are stated for the basis predicates in both polarities
(the positive literal of a derived conjunction such as ``real`` follows),
and for the negative literal of the derived conjunctions (``odd`` false of
an even and of a non-integer argument), the latter only while its clauses
over the basis stay within ``MAX_EXPAND`` (a premise ``!odd(a_i)`` is a
disjunction, so ``n`` of them expand to ``2**n`` clauses).

``Max`` is at least each argument, ``Min`` at most: one positive argument
makes ``Max`` positive, one negative argument makes ``Min`` negative.
"""
from __future__ import annotations

from sympy import S
from sympy.core.expr import Expr
from sympy.functions.elementary.miscellaneous import Max, Min
from sympy.functions.elementary.piecewise import Piecewise

from satassume.knowledge.rules import DEFINITIONS
from satassume.knowledge.templates._common import (
    MAX_EXPAND, Rules, consts_of, facts, pattern_key,
)

_BASIS = (
    'algebraic', 'complex', 'composite', 'even', 'extended_negative', 'extended_positive',
    'extended_real', 'finite', 'imaginary', 'integer', 'prime', 'rational', 'zero',
)
_DERIVED = (
    'odd', 'real', 'positive', 'negative', 'nonnegative', 'nonpositive', 'nonzero',
    'irrational', 'noninteger', 'transcendental',
)


def _selection(R, n):
    """Values 0 .. n-1, node n."""
    for pred in _BASIS:
        for pos in (True, False):
            R.rule([(i, pred, pos) for i in range(n)], (n, pred, pos))
    for pred in _DERIVED:
        width = DEFINITIONS[pred].count('&') + 1      # conjuncts over the basis
        if width ** n <= MAX_EXPAND:
            R.rule([(i, pred, False) for i in range(n)], (n, pred, False))


def _bound(R, n, preds):
    """One argument with ``pred`` gives the node ``pred`` (an upper bound
    of ``Max``, a lower bound of ``Min``)."""
    for pred in preds:
        for i in range(n):
            R.rule([(i, pred, True)], (n, pred, True))


_MAX_BOUND = ('extended_positive', 'extended_nonnegative')
_MIN_BOUND = ('extended_negative', 'extended_nonpositive')


def _template(tag, values, expr, bound=()):
    n = len(values)
    consts = consts_of(values)

    def build():
        R = Rules()
        _selection(R, n)
        _bound(R, n, bound)
        return R.rules

    return facts(pattern_key(tag, n, consts), build, consts, (*values, expr), n)


def max_templates(expr):
    return _template('Max', expr.args, expr, _MAX_BOUND)


def min_templates(expr):
    return _template('Min', expr.args, expr, _MIN_BOUND)


def piecewise_templates(expr):
    args = expr.args
    if not args or args[-1].cond is not S.true:
        return None
    values = tuple(a.expr for a in args)
    if not all(isinstance(v, Expr) for v in values):
        return None                     # a Piecewise of Booleans
    return _template('Piecewise', values, expr)
