"""Handler for ``Mul``.

Only products in which a *pair* of factors combines are rewritten; general
products are left alone.

Rules:

M1  ``z**n * conjugate(z)**n -> Abs(z)**(2*n)`` for a positive integer
    ``n`` (the two factors are matched with the smaller common exponent).
    ``z*conjugate(z) == |z|**2`` holds for every complex ``z``, so no
    assumption is needed.
M2  ``sign(z)*Abs(z) -> z``: an identity for every complex ``z``
    (including ``0``).
M3  ``x*sign(x) -> Abs(x)`` when ``x`` is real.  For complex ``z``,
    ``z*sign(z) == z**2/|z|`` is not ``|z|``, so the assumption is needed.
"""
from __future__ import annotations

from sympy.assumptions import Q
from sympy.core import Basic, Mul, S
from sympy.functions.elementary.complexes import Abs, conjugate, sign

from .._upstream import handlers_dict
from ._common import Assumptions, holds, integer_valued


def _powers(expr: Basic) -> dict[Basic, Basic]:
    return {base: integer_valued(e) for base, e in expr.as_powers_dict().items()}


def _rebuild(powers: dict[Basic, Basic]) -> Basic:
    return Mul(*[base**e for base, e in powers.items() if e != 0])


def _conjugate_pairs(powers: dict[Basic, Basic]) -> Basic | None:
    """Rule M1 on the power table; returns the rebuilt product or ``None``."""
    changed = False
    for base in list(powers):
        if isinstance(base, conjugate) or base not in powers:
            continue
        partner = conjugate(base)
        if partner not in powers or partner == base:
            continue
        exponents = (powers[base], powers[partner])
        if not all(e.is_Integer and e.is_positive for e in exponents):
            continue
        n = min(exponents)
        powers[base] -= n
        powers[partner] -= n
        powers[Abs(base)] = powers.get(Abs(base), S.Zero) + 2 * n
        changed = True
    return _rebuild(powers) if changed else None


def _sign_pairs(powers: dict[Basic, Basic], assumptions: Assumptions) -> Basic | None:
    """Rules M2 and M3 on the power table."""
    for base, e in powers.items():
        if not (isinstance(base, sign) and e == 1):
            continue
        z = base.args[0]
        if powers.get(Abs(z)) == 1:                                     # M2
            del powers[base], powers[Abs(z)]
            powers[z] = powers.get(z, S.Zero) + 1
            return _rebuild(powers)
        if powers.get(z) == 1 and holds(Q.real(z), assumptions):        # M3
            del powers[base], powers[z]
            powers[Abs(z)] = powers.get(Abs(z), S.Zero) + 1
            return _rebuild(powers)
    return None


def refine_Mul(expr: Basic, assumptions: Assumptions) -> Basic | None:
    powers = _powers(expr)
    paired = _conjugate_pairs(powers)
    if paired is not None:
        return paired
    return _sign_pairs(powers, assumptions)


handlers_dict['Mul'] = refine_Mul
