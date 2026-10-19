"""Unit facts for ``ComplexRootOf``: an indexed root of an integer polynomial.

``CRootOf(p, k)`` orders the roots of ``p`` (squarefree over ``ZZ``; SymPy
stores an irreducible factor) with the real ones first, ascending, then the
non-real ones.  Root ``k`` is real iff ``k`` is below the number of real
roots, and its sign is read from the numbers of negative and positive real
roots; a non-real root is imaginary when every non-real root is, and not
when none is (:func:`satassume.knowledge.realroots.root_facts`, exact Sturm
counts).  Every root is algebraic and finite.  SymPy's ``CRootOf`` takes an
undecided ``is_real`` for "not real" (``_get_interval``), so ``real`` must
be decided (#180 C-CROOT).
"""
from __future__ import annotations

from sympy.polys.rootoftools import ComplexRootOf

from ..realroots import root_facts
from ._common import units
from .registry import registry


def _coefficients(expr):
    """The integer coefficients of ``expr``'s polynomial, highest first, or
    None if its domain is not ``ZZ``."""
    poly = expr.poly
    if not poly.domain.is_ZZ:
        return None
    return tuple(int(c) for c in poly.rep.to_list())


def _facts(coeffs, index):
    out = [('algebraic', True), ('finite', True)]
    r = root_facts(coeffs, index) if coeffs is not None else None
    if r is None:
        return out
    out.append(('extended_real', r['real']))
    if r['sign'] is not None:
        out.append({-1: ('negative', True), 0: ('zero', True), 1: ('positive', True)}[r['sign']])
    if r['imaginary'] is not None:
        out.append(('imaginary', r['imaginary']))
    return out


@registry.register(ComplexRootOf)
def crootof_units(expr):
    coeffs = _coefficients(expr)
    index = int(expr.index)
    return units(('crootof', coeffs, index), lambda: _facts(coeffs, index), expr)
