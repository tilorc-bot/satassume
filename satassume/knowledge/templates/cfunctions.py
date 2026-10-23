"""``expm1`` and ``log1p`` of ``sympy.codegen.cfunctions`` (#180).

SymPy does not import ``sympy.codegen`` itself, so ``templates/__init__.py``
declares this family with the class names (``TemplateRegistry.lazy``), and
it is compiled when the first node of one of them is met.

``expm1(x) == exp(x) - 1`` and ``log1p(x) == log(x + 1)`` on the principal
branch.  SymPy's values kept as they are: ``expm1(-oo) == -1``,
``expm1(oo) == oo``, ``log1p(-1) == zoo`` and ``log1p(+-oo) == oo``.
"""
from __future__ import annotations

from sympy import Equivalent, Q
from sympy.codegen.cfunctions import expm1, log1p

from ._rows import argument, closed, f, for_all

RULES = (
    # Entire
    #     exp(x) - 1 has no poles
    for_all((expm1,),
        closed(f, Q.finite) & closed(f, Q.complex)),

    # The sign of the argument
    #     exp is increasing on the extended reals and exp(0) == 1; off the
    #     reals expm1(2*I*pi) == 0
    for_all((expm1,),
        Q.extended_real(argument) >> (
            Equivalent(Q.extended_positive(f(argument)), Q.extended_positive(argument))
            & Equivalent(Q.extended_negative(f(argument)), Q.extended_negative(argument))
            & Equivalent(Q.zero(f(argument)), Q.zero(argument)))),

    # Minus one at -oo
    #     odd; negative by the sign of the argument
    for_all((expm1,),
        (Q.infinite(argument) & Q.extended_negative(argument)) >> Q.odd(f(argument))),

    # Infinite at oo
    for_all((expm1,),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> Q.infinite(f(argument))),

    # Lindemann
    #     exp(a) is transcendental for an algebraic a != 0
    #     (Lindemann-Weierstrass), and so is exp(a) - 1
    for_all((expm1,),
        (Q.algebraic(argument) & ~Q.zero(argument)) >> Q.transcendental(f(argument))),

    # Zero only at 0
    #     log(y) == 0 iff y == 1
    for_all((log1p,),
        Equivalent(Q.zero(f(argument)), Q.zero(argument))),

    # The sign of the argument beyond -1
    #     log is increasing on the positive reals and log(1) == 0
    for_all((log1p,),
        closed(f, Q.positive),
        (Q.negative(argument) & Q.gt(argument, -1)) >> Q.negative(f(argument))),

    # Pole at -1
    #     log1p(-1) == zoo; the sign premise on argument keeps the block
    #     total (nothing relates the slot argument + 1 to argument)
    for_all((log1p,),
        (Q.negative(argument) & Q.eq(argument, -1)) >> (
            Q.infinite(f(argument)) & ~Q.extended_real(f(argument)))),

    # Not real below -1
    #     the logarithm of a negative number has the imaginary part pi
    for_all((log1p,),
        (Q.negative(argument) & Q.lt(argument, -1)) >> ~Q.extended_real(f(argument))),

    # Complex except at -1
    for_all((log1p,),
        (Q.complex(argument) & Q.ne(argument, -1)) >> Q.complex(f(argument))),

    # Infinite at an infinity
    #     log1p(+-oo) == oo
    for_all((log1p,),
        closed(f, Q.infinite),
        (Q.infinite(argument) & Q.extended_positive(argument))
        >> Q.extended_positive(f(argument))),

    # Lindemann
    #     log(y) for an algebraic y != 0, 1 is transcendental: exp(b) == y
    #     with an algebraic b != 0 contradicts Lindemann-Weierstrass
    for_all((log1p,),
        (Q.algebraic(argument) & ~Q.zero(argument) & Q.ne(argument, -1))
        >> Q.transcendental(f(argument))),
)
