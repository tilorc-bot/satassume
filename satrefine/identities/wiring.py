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

from sympy import (Abs, Heaviside, KroneckerDelta, Max, Min, Mod, Piecewise, Pow, acos, acoth, acsch, arg, asin, asinh,
                   atan, atan2, atanh, count_ops, exp, floor, frac, im, log, re, sign)
from sympy.core import Mul
from sympy.functions.elementary.miscellaneous import Rem

from . import family_module_name
from .core.measure import count_measure, node_measure, size
from .core.spec import Family, Identities, Rules, complete_module
from .rules._tables import ZERO

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


# ---- complex_parts --------------------------------------------------------------

def complex_parts(m) -> Family:
    from .rules.power_exp_log import EXP_FORMS   # not owned by complex_parts (counted in power_exp_log)
    rules = Rules([ZERO] + m.RULES)   # also arg: arg(0) is nan, which is what arg(x) is at x = 0

    def definition(head, **kw):
        return Identities(_headed(m.DEFINITIONS, head), **kw)

    def identity(head, **kw):
        return Identities(_headed(m.IDENTITIES, head), measure=node_measure((head,)), **kw)

    def splits(head):
        return Identities(_headed(m.SPLITS, head), measure=node_measure((head,)))

    # the splits get a handler of their own so they can fire inside a derived row's candidate
    return Family({'Abs': (rules, Identities(_headed(m.IDENTITIES, Abs), measure=node_measure((Abs, re))),
                           definition(Abs, opaque=(sign,))),
                   're': rules,
                   'im': rules,
                   'arg': (rules, identity(arg, opaque=(floor, im)),   # arg is the result, not bookkeeping
                           definition(arg, opaque=(sign,))),
                   'sign': (rules, splits(sign)),
                   'conjugate': rules,
                   'Mul': Rules([row for row in m.RULES if isinstance(row[0], Mul)])},
                  facts=m.FACTS + m.SPLITS, exp_forms=EXP_FORMS, rules=[ZERO] + m.RULES, ranges=m.RANGES,
                  assumed=m.ASSUMED)


# ---- integer_funcs --------------------------------------------------------------

def integer_funcs(m) -> Family:
    return Family({'floor': Rules(m.FLOOR),
                   'ceiling': Rules(m.CEILING),
                   'frac': (Rules(m.FRAC), Identities(m.FRAC_DEFINITION, measure=node_measure((frac,)))),
                   'Mod': (Rules(m.MOD), Identities(m.MOD_HALF, measure=node_measure((Mod,)), opaque=(floor, sign))),
                   'Rem': (Rules(m.REM), Identities(m.REM_HALF, measure=node_measure((Rem,)), opaque=(floor, sign)))},
                  facts=m.FACTS, rules=m.RULES, assumed=m.ASSUMED)


# ---- inverse --------------------------------------------------------------------

def inverse(m) -> Family:
    rules = Rules([ZERO] + m.RULES)

    def identity(head, opaque=(floor, im)):
        return Identities(_headed(m.FACTS, head), measure=node_measure((head,)), opaque=opaque)

    return Family({**{head.__name__: (rules, identity(head))
                      for head in (asin, acos, atan, asinh, atanh, acoth, acsch)},
                   'acosh': rules, 'asech': rules,
                   'atan2': identity(atan2, opaque=(floor, im, Piecewise))},
                  facts=m.FACTS, rules=[ZERO] + m.RULES, ranges=m.RANGES, assumed=m.ASSUMED)


# ---- minmax_deltas --------------------------------------------------------------

def minmax_measure(e, assumptions):
    """Arguments of the family's heads, then size: a definition fires when it drops one."""
    return (sum(len(n.args) for n in e.atoms(Max, Min, KroneckerDelta, Heaviside)), count_ops(e))


def minmax_deltas(m) -> Family:
    def definitions(head):   # no case split (see the module docstring)
        return Identities(_headed(m.FACTS, head), measure=minmax_measure, opaque=(), splits=False)

    return Family({'Max': (Rules(_headed(m.INFINITE, Max)), definitions(Max)),
                   'Min': (Rules(_headed(m.INFINITE, Min)), definitions(Min)),
                   'KroneckerDelta': definitions(KroneckerDelta),
                   'Heaviside': definitions(Heaviside),
                   'DiracDelta': Rules(m.DIRAC)},
                  facts=m.FACTS, rules=m.RULES, assumed=m.ASSUMED)


# ---- power_exp_log --------------------------------------------------------------

def negative_number_base_measure(e, assumptions):
    """``(powers of a negative number, size)``: the ordering for ``c**n -> (-c)**n``
    rows, which must not fire for a symbolic base (SymPy's ``Pow._eval_refine``
    rewrites ``(-x)**n`` back to ``-x**n`` for odd ``n``, a cycle)."""
    negative = sum(1 for node in e.atoms(Pow) if node.base.is_number and node.base.is_negative)
    return (negative, size(e))


def power_exp_log(m) -> Family:
    rules, zero = Rules(m.RULES), Rules([ZERO])
    return Family({'log': (zero, Identities(m.IDENTITIES), Rules(m.LOG_RULES)),   # LOG_RULES after the identities
                   'Pow': (rules,
                           Identities([row for row in m.FACTS if isinstance(row[0], Pow)],
                                      measure=node_measure((Pow, exp)), opaque=(floor, im, arg, log)),
                           Identities(m.NEGATIVE_BASE, measure=negative_number_base_measure)),
                   'exp': (zero, rules, Identities([row for row in m.FACTS if isinstance(row[0], exp)],
                                                   measure=count_measure((exp,))))},
                  facts=m.FACTS + m.NEGATIVE_BASE, exp_forms=m.LOG_FORMS, rules=[ZERO] + m.RULES + m.LOG_RULES,
                  assumed=m.ASSUMED)


WIRED: dict = {"complex_parts": complex_parts, "integer_funcs": integer_funcs, "inverse": inverse,
               "minmax_deltas": minmax_deltas, "power_exp_log": power_exp_log}
"""The families that mix rule and identity tables: ``family -> (module -> Family)``."""
