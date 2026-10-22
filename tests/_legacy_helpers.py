"""Helpers of the legacy generators (``tests/_legacy_*_rules.py``) that the
templates no longer use, verbatim from
``satassume/knowledge/templates/functions.py`` at f9291ab."""
from satassume.knowledge.templates.functions import N, X


def _finite_value(R, pred):
    """``pred(x) & finite(node) -> pred(node)``: the value is a number of
    the kind or ``zoo`` (at a pole)."""
    R.rule([(X, pred, True), (N, 'finite', True)], (N, pred, True))
