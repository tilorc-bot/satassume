"""Parity of integrality atoms: linear equations over GF(2) (#315).

LRA's integrality atoms ``f in Z`` (``Integral(terms, offset)``) are
decided by the bounds of ``f`` and by branch and bound, which needs
bounded variables: nothing there relates ``u in Z``, ``(u - 1)/2 in Z``
(``u`` odd) and ``u/2 + 1/2 in Z`` for an unbounded ``u``.  This module
does.  Let ``f = sum(c_i*u_i) + k`` with every ``2*c_i`` and ``2*k`` an
integer and every ``u_i`` asserted integral (by an atom ``u_i in Z``).
Then ``2*f`` is an integer, ``f in Z`` iff ``2*f`` is even, and with
``p_i = u_i mod 2``::

    f in Z      iff  sum((2*c_i mod 2) * p_i) = 2*k mod 2      (GF(2))
    f not in Z  iff  sum((2*c_i mod 2) * p_i) = 2*k mod 2 + 1

So every asserted literal of such an ``f``, true or false, is a linear
equation over GF(2) in the parities of its variables, and a set of them
has an integral solution iff the system is consistent (each ``p_i`` can
be realised by any integer of that parity; the equations constrain
nothing else).  :func:`conflict` runs Gaussian elimination, each row
carrying the literals it came from; ``0 = 1`` is a conflict explained by
those literals and the integrality literals of the variables used.

A general modulus (``f`` with a coefficient of denominator 4: ``u/4 in
Z``, that is ``u = 0 mod 4``) needs a Hermite or Smith normal form over
the integers; it is not done.  The forms here are LRA's rational ones: a
form with a constant of the field (an ``Element``) has no parity row.
"""
from __future__ import annotations

from fractions import Fraction

__all__ = ["row_of", "unit_of", "conflict"]


def row_of(lin: dict, var_of, k):
    """``(vars, mask, kappa)`` for the form ``sum(c*t for t, c in
    lin.items()) + k``, with ``var_of(t)`` the variable of a term: every
    ``2*c`` and ``2*k`` an integer (all Fractions), ``vars`` the variables
    with a nonzero coefficient, ``mask`` the bits of those with an odd
    ``2*c``, ``kappa = 2*k mod 2``; else None."""
    if type(k) is not Fraction or (2 * k).denominator != 1:
        return None
    vs = []
    mask = 0
    for t, c in lin.items():
        if type(c) is not Fraction:
            return None
        d = 2 * c
        if d.denominator != 1:
            return None
        v = var_of(t)
        vs.append(v)
        if d.numerator % 2:
            mask |= 1 << v
    return tuple(vs), mask, (2 * k).numerator % 2


def unit_of(lin: dict, var_of, k):
    """The variable ``v`` if the form is ``+-v + k`` with an integer ``k``
    (its atom says ``v in Z``), else None."""
    if len(lin) != 1 or type(k) is not Fraction or k.denominator != 1:
        return None
    (t, c), = lin.items()
    if type(c) is not Fraction or abs(c) != 1:
        return None
    return var_of(t)


def conflict(units: dict, rows):
    """A conflict clause (negated literals) of the parity rows ``rows``,
    ``(vars, mask, kappa, literal)`` each (``literal`` true or false, as
    asserted), given ``units``: variable -> a true literal saying it is an
    integer; or None.  A row with a variable not in ``units`` is left out
    (its ``2*f`` need not be an integer)."""
    pivots: dict = {}
    for vs, mask, kappa, lit in rows:
        src = {lit}
        for v in vs:
            u = units.get(v)
            if u is None:
                break
            src.add(u)
        else:
            rhs = kappa ^ (lit < 0)
            while mask:
                b = mask.bit_length() - 1
                p = pivots.get(b)
                if p is None:
                    pivots[b] = (mask, rhs, src)
                    break
                mask ^= p[0]
                rhs ^= p[1]
                src = src | p[2]
            else:
                if rhs:
                    return sorted(-l for l in src)
    return None
