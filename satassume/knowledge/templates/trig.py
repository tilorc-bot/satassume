"""``sin``, ``cos``, ``tan``, ``cot``, ``sec`` and ``csc``.

Each row is a theorem about the value under SymPy's conventions, ``zoo``
at a pole (``tan(pi/2)``, ``cot(0)``, ``sec(pi/2)``, ``csc(0)``) and
``AccumBounds`` or ``nan`` at an infinite argument, where no row claims
anything (``real`` implies ``finite``).  The
transcendence rows follow from Lindemann-Weierstrass: ``exp(I*a)`` is
transcendental for an algebraic ``a != 0``.  Facts the rule base derives
(``positive`` from ``extended_positive & finite``) are not repeated.
"""
from __future__ import annotations

from sympy import Q, cos, cot, csc, sec, sin, symbols, tan

from ._rows import rules
from .functions import _pi_trig, _unary
from .registry import registry

x = symbols('x')

SIN = (
    Q.real(x) >> Q.real(sin(x)),
    Q.complex(x) >> Q.complex(sin(x)),
    Q.finite(x) >> Q.finite(sin(x)),                # sin(oo*I) == oo*I
    Q.zero(x) >> Q.zero(sin(x)),
    Q.imaginary(x) >> Q.imaginary(sin(x)),
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(sin(x)),
)

COS = (
    Q.real(x) >> Q.real(cos(x)),
    Q.complex(x) >> Q.complex(cos(x)),
    Q.finite(x) >> Q.finite(cos(x)),
    Q.zero(x) >> (Q.odd(cos(x)) & Q.positive(cos(x))),
    Q.imaginary(x) >> Q.positive(cos(x)),           # cos(I*t) == cosh(t)
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(cos(x)),
)

TAN = (
    Q.real(x) >> ~Q.imaginary(tan(x)),
    Q.zero(x) >> Q.zero(tan(x)),
    Q.imaginary(x) >> Q.imaginary(tan(x)),
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(tan(x)),
    (Q.real(x) & Q.finite(tan(x))) >> Q.real(tan(x)),
    # Im tan(x + I*y) == sinh(2*y)/(cos(2*x) + cosh(2*y)) != 0 for y != 0
    (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(tan(x)),
)

COT = (
    Q.real(x) >> ~Q.imaginary(cot(x)),
    Q.imaginary(x) >> Q.imaginary(cot(x)),          # cot(I*t) == -I*coth(t)
    Q.zero(x) >> (Q.infinite(cot(x)) & ~Q.extended_real(cot(x))),
    # finite at an algebraic x != 0, as sin(x) == 0 only at multiples of pi
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(cot(x)),
    Q.algebraic(x) >> ~Q.algebraic(cot(x)),
    (Q.real(x) & Q.finite(cot(x))) >> Q.real(cot(x)),
    (Q.finite(x) & ~Q.extended_real(x)) >> ~Q.extended_real(cot(x)),    # cot == 1/tan
    (Q.complex(x) & Q.finite(cot(x))) >> Q.complex(cot(x)),
)

SEC = (
    Q.real(x) >> ~Q.imaginary(sec(x)),
    Q.complex(x) >> ~Q.zero(sec(x)),                # cos is finite at a finite point
    Q.zero(x) >> (Q.odd(sec(x)) & Q.positive(sec(x))),
    Q.imaginary(x) >> Q.positive(sec(x)),           # sec(I*t) == 1/cosh(t)
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(sec(x)),
    (Q.real(x) & Q.finite(sec(x))) >> Q.real(sec(x)),
    (Q.complex(x) & Q.finite(sec(x))) >> Q.complex(sec(x)),
)

CSC = (
    Q.real(x) >> ~Q.imaginary(csc(x)),
    Q.complex(x) >> ~Q.zero(csc(x)),
    Q.zero(x) >> (Q.infinite(csc(x)) & ~Q.extended_real(csc(x))),
    Q.imaginary(x) >> Q.imaginary(csc(x)),          # csc(I*t) == -I/sinh(t)
    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(csc(x)),
    (Q.real(x) & Q.finite(csc(x))) >> Q.real(csc(x)),
    (Q.complex(x) & Q.finite(csc(x))) >> Q.complex(csc(x)),
)


registry.register(sin)(_pi_trig('sin', rules(sin, SIN, __name__), False))
registry.register(cos)(_pi_trig('cos', rules(cos, COS, __name__), True))
for _head, _table in ((tan, TAN), (cot, COT), (sec, SEC), (csc, CSC)):
    registry.register(_head)(_unary(_head.__name__, rules(_head, _table, __name__)))
