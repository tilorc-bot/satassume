"""Which handlers serve which ``handlers_dict`` key, family by family.

The family modules state rows only (:mod:`.rules`, :mod:`.compat.matrices`);
:func:`family_spec` makes each one's :class:`.core.spec.Family`, once, and
completes the module's tables with its ``ASSUMED`` facts.

A family of rule rows only (``trig``, ``hyperbolic``, ``combinatorial``,
``matrices``) needs no wiring: :meth:`.core.spec.Family.from_rows` serves each
key the rows of its ``RULES`` headed by that key, in table order.  The other
families mix rule and identity tables, and their wiring below makes choices
of its own: the order of the handlers of a key, the ordering (``measure``)
and ``opaque`` heads of each identity table, and which tables get ``ZERO``.
"""
from __future__ import annotations

import importlib
from functools import cache

from . import family_module_name
from .core.spec import Family, complete_module

BY_BINDING = frozenset({"trig", "hyperbolic"})
"""Rules-only families whose rows with one left side are tried binding by binding
(:func:`.core.rewrite.rule_handler`): the periodicity tables, so ``n`` is tried as
the whole coefficient of ``pi/2`` (``pi*I/2``), under both parities, before a
single term of it is (``sec(x + (2*j + 1)*pi/2)`` is one odd shift, not an even
shift and then a quarter turn).  Not the default: in ``complex_parts`` it would
change which conjugate pair of a product is reduced first."""


@cache
def family_spec(family: str) -> Family:
    """The family's spec (the module's ``RULES`` and ``ASSUMED`` for a rules-only
    family, :data:`WIRED` otherwise); making it completes the module's tables."""
    module = importlib.import_module(family_module_name(family))
    wire = WIRED.get(family)
    if hasattr(module, "SPEC"):   # a module that still wires itself
        spec = module.SPEC
    else:
        spec = wire(module) if wire else Family.from_rows(module.RULES, assumed=module.ASSUMED,
                                                          by_binding=family in BY_BINDING)
    complete_module(module, spec)
    return spec


def _headed(rows: list, head) -> list:
    """The rows of ``rows`` whose left side has the head ``head``."""
    return [row for row in rows if row[0].func is head]


WIRED: dict = {}
"""The families that mix rule and identity tables: ``family -> (module -> Family)``."""
