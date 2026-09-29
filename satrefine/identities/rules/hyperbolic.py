"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch`` as tables.

Rows: 12 rules, 1 shared zero row; ``handlers_v3/hyperbolic.py`` is 225
lines.

The family is the trigonometric periodicity table rotated: an argument
``n*pi*I/2 + r`` shifts by a quarter of the period ``2*pi*I`` ``n`` times.
For ``n`` even the shift is ``(-1)**(n/2)``; for ``n`` odd it exchanges the
function with its cofunction times ``I*(-1)**((n-1)/2)`` (``-I`` for
``sech`` and ``csch``).  ``tanh`` and ``coth`` have period ``pi*I``.  Real
multiples of ``pi`` are not shifts of the period and never bind (the
pattern form collects only terms whose ratio to ``pi*I/2`` is free of
``pi`` and ``I``).

The sign power collapses through the ``Pow`` rules once the residue of
``n`` mod 4 is known, and stays symbolic otherwise, as in the trigonometric
table: ``sinh(r + m*pi*I) = (-1)**m*sinh(r)`` under ``Q.integer(m)`` (SymPy's
and the old ``handlers``' form).  v3 fires ``sinh``, ``cosh``, ``sech`` and
``csch`` only when the residue is known (phase 3 made the rows exact with a
symbolic sign instead: rows "default: hyperbolic i*pi shift" of ``tests/refine_identities/regressions.py``).
Like the trigonometric table, the whole coefficient of ``pi*I/2`` is tried
under both parities before a single term of it (``by_binding``).

Not covered: nothing v3 states.  ``f(m*pi*I)`` auto-evaluates to a
trigonometric function in SymPy, so the exact-point rules of v3 are the
trigonometric family's rows here (``sinh(I*pi*m)`` is ``I*sin(pi*m)``,
which gives ``0`` rather than v3's unrefined form).
Checked (adversarial pass, 2026-09-24): every row with ``n`` even, odd and
of known residue mod 4, at the poles (``coth``, ``csch`` at ``n*pi*I``,
``tanh``, ``sech`` at odd multiples of ``pi*I/2``), real multiples of
``pi`` (must not bind), sums of shifts, and ``python -m satrefine.tools.refine_differential``.
Found nothing.
"""
from __future__ import annotations

from sympy import I, Q, cosh, coth, csch, pi, sech, sinh, symbols, tanh

from ._tables import ZERO, Family, Row, Rules, add_rules

# The argument is n*pi*I/2 + r.  Nothing is assumed about n throughout: each row's block states
# its parity (which also makes it an integer), and that is what tells the rows apart.  The
# table is tried by binding (``by_binding``), so both rows of a function keep the same left
# side, one block each: the even row, then the odd one.  So nothing is assumed throughout.
n, r = symbols('n r')
ASSUMED: set = set()


def _parities(even: Row, odd: Row) -> list[Row]:
    """A function's two shift rows: ``even`` for an even ``n``, ``odd`` for an odd one."""
    return add_rules([even], assuming={Q.even(n)}) + add_rules([odd], assuming={Q.odd(n)})


RULES: list[Row] = (   # the argument is n*pi*I/2 + r
    _parities(
        (sinh(n*pi*I/2 + r), (-1)**(n/2)*sinh(r)),           # sinh(r + m*pi*I) = (-1)**m sinh r
        (sinh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*cosh(r)),   # sinh(r + pi*I/2) = I cosh r
    )
    + _parities(
        (cosh(n*pi*I/2 + r), (-1)**(n/2)*cosh(r)),           # cosh(r + m*pi*I) = (-1)**m cosh r
        (cosh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*sinh(r)),   # cosh(r + pi*I/2) = I sinh r
    )
    + _parities(
        (sech(n*pi*I/2 + r), (-1)**(n/2)*sech(r)),           # sech = 1/cosh
        (sech(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*csch(r)),
    )
    + _parities(
        (csch(n*pi*I/2 + r), (-1)**(n/2)*csch(r)),           # csch = 1/sinh
        (csch(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*sech(r)),
    )
    + _parities(
        (tanh(n*pi*I/2 + r), tanh(r)),                       # tanh has period pi*I
        (tanh(n*pi*I/2 + r), coth(r)),                       # tanh(r + pi*I/2) = coth r
    )
    + _parities(
        (coth(n*pi*I/2 + r), coth(r)),                       # coth has period pi*I
        (coth(n*pi*I/2 + r), tanh(r)),                       # coth(r + pi*I/2) = tanh r
    )
)

_shift = Rules([ZERO] + RULES, by_binding=True)

SPEC = Family({'sinh': _shift, 'cosh': _shift, 'tanh': _shift, 'coth': _shift, 'sech': _shift, 'csch': _shift},
              rules=[ZERO] + RULES, assumed=ASSUMED)
