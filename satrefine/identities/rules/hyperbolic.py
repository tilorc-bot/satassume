"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch`` as tables.

The trigonometric periodicity table rotated: an argument ``n*pi*I/2 + r``
(``n`` the whole coefficient of ``pi*I/2``) is ``n`` quarter periods from
``r``.  For ``n`` even the function keeps its form with sign ``(-1)**(n/2)``;
for ``n`` odd it becomes its cofunction times ``I*(-1)**((n-1)/2)`` (``-I``
for ``sech`` and ``csch``).  The signs collapse through the ``Pow`` rules
once ``n`` mod 4 is known and stay symbolic otherwise.  Real multiples of
``pi`` never bind: the pattern form collects only terms whose ratio to
``pi*I/2`` is free of ``pi`` and ``I``.

Not covered: exact points.  SymPy evaluates ``f(m*pi*I)`` to a trigonometric
function (``sinh(I*pi*m)`` is ``I*sin(pi*m)``), so the trigonometric
family's rows handle them.
"""
from __future__ import annotations

from sympy import I, Q, cosh, coth, csch, pi, sech, sinh, symbols, tanh

from ._tables import Row, add_rules

n, r = symbols('n r')   # each block's hypothesis gives n's parity (and so integrality)

RULES: list[Row] = (
    add_rules({Q.even(n)}, [  # m = n/2:  sinh(r + m*pi*I) = (-1)**m sinh r
        (sinh(n*pi*I/2 + r), (-1)**(n/2)*sinh(r)),
        (cosh(n*pi*I/2 + r), (-1)**(n/2)*cosh(r)),
        (sech(n*pi*I/2 + r), (-1)**(n/2)*sech(r)),
        (csch(n*pi*I/2 + r), (-1)**(n/2)*csch(r)),
        (tanh(n*pi*I/2 + r), tanh(r)),                       # tanh, coth have period pi*I
        (coth(n*pi*I/2 + r), coth(r)),
    ])
    + add_rules({Q.odd(n)}, [  # sinh(r + pi*I/2) = I cosh r
        (sinh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*cosh(r)),
        (cosh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*sinh(r)),   # cosh(r + pi*I/2) = I sinh r
        (sech(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*csch(r)),
        (csch(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*sech(r)),
        (tanh(n*pi*I/2 + r), coth(r)),                       # tanh(r + pi*I/2) = coth r
        (coth(n*pi*I/2 + r), tanh(r)),                       # coth(r + pi*I/2) = tanh r
    ])
)
