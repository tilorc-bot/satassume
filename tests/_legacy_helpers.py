"""Helpers of the legacy generators (``tests/_legacy_*_rules.py``) that the
templates no longer use, verbatim from
``satassume/knowledge/templates/functions.py`` at f9291ab (``_x``, ``_n``,
``_table``, ``_equiv`` and ``_TRANSCENDENTAL`` until 8b47aa8)."""
from satassume.knowledge.templates.functions import N, X


def _x(spec):
    return (X, spec, True) if isinstance(spec, str) else (X, spec[0], spec[1])


def _n(spec):
    return (N, spec, True) if isinstance(spec, str) else (N, spec[0], spec[1])


def _table(R, rows):
    for prem, concl in rows:
        R.rule([_x(p) for p in prem], _n(concl))


def _equiv(R, cond, preds):
    """``cond -> (pred(node) <-> pred(arg))`` for each pred."""
    for pred in preds:
        R.equiv(cond, (N, pred, True), (X, pred, True))


_TRANSCENDENTAL = (('algebraic', ('zero', False)), 'transcendental')


def _finite_value(R, pred):
    """``pred(x) & finite(node) -> pred(node)``: the value is a number of
    the kind or ``zoo`` (at a pole)."""
    R.rule([(X, pred, True), (N, 'finite', True)], (N, pred, True))


#: Slot of ``x + 1`` in the inverse functions' generators (``slots=_minus_plus_one``).
P1 = 3

# verbatim from satassume/knowledge/templates/special.py at d149951 (the
# Airy templates still use _ENTIRE there)

#: an extended real argument: the node's sign is the argument's
_SIGNS = ('extended_positive', 'extended_negative', 'zero')

_ENTIRE = ((('finite',), 'finite'), (('complex',), 'complex'))
