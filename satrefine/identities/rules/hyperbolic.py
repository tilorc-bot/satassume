"""``sinh``, ``cosh``, ``tanh``, ``coth``, ``sech`` and ``csch``: shifts by multiples of ``pi*I/2``."""
from __future__ import annotations

from sympy import I, Q, cosh, coth, csch, pi, sech, sinh, symbols, tanh

from ._tables import Row, add_rules

n, r = symbols('n r')

RULES: list[Row] = (
    add_rules({Q.even(n)}, [
        (sinh(n*pi*I/2 + r), (-1)**(n/2)*sinh(r)),
        (cosh(n*pi*I/2 + r), (-1)**(n/2)*cosh(r)),
        (sech(n*pi*I/2 + r), (-1)**(n/2)*sech(r)),
        (csch(n*pi*I/2 + r), (-1)**(n/2)*csch(r)),
        (tanh(n*pi*I/2 + r), tanh(r)),
        (coth(n*pi*I/2 + r), coth(r)),
    ])
    + add_rules({Q.odd(n)}, [
        (sinh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*cosh(r)),
        (cosh(n*pi*I/2 + r), I*(-1)**((n - 1)/2)*sinh(r)),
        (sech(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*csch(r)),
        (csch(n*pi*I/2 + r), -I*(-1)**((n - 1)/2)*sech(r)),
        (tanh(n*pi*I/2 + r), coth(r)),
        (coth(n*pi*I/2 + r), tanh(r)),
    ])
)
