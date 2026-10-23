"""``LambertW(x)`` and ``LambertW(x, k)``: the ``w`` with ``w*exp(w) == x``
on the branch ``k`` (``k == 0``, the principal branch, when absent).

Values follow SymPy's conventions: principal branches, ``LambertW(oo) ==
oo``, ``LambertW(0, k) == -oo`` for ``k != 0``.  ``W_0`` is real and ``>=
-1`` on ``[-1/E, oo)`` with the sign of ``x`` (``W_0(-1/E) == -1``), not
real below ``-1/E``; ``W_-1`` is real and ``<= -1`` on ``[-1/E, 0)``, not
real elsewhere on the real line; the other branches are not real at a real
``x != 0``.  ``LambertW(-1/E) == -1`` is real, though SymPy's
``is_extended_real`` says otherwise.  A node of another number of
arguments gets no facts.

SymPy defines ``LambertW`` in ``elementary/exponential``, with ``exp`` and
``log``; its rows are a family of their own, not in :mod:`.exp_log`: they
share no fact with ``exp`` and ``log``, and the first ``exp`` or ``log``
does not compile them.
"""
from __future__ import annotations

from sympy import E, LambertW, Q

from ._rows import argument, branch, closed, f, for_all

RULES = (
    # Zero only at 0
    #     w*exp(w) == x: w == 0 gives x == 0, on every branch
    for_all((LambertW,),
        Q.zero(f(argument)) >> Q.zero(argument),
        Q.zero(f(argument, branch)) >> Q.zero(argument)),

    # Infinite at infinity
    #     LambertW(oo) == oo, on every branch
    for_all((LambertW,),
        Q.infinite(argument) >> Q.infinite(f(argument)),
        (Q.integer(branch) & Q.infinite(argument)) >> Q.infinite(f(argument, branch))),

    # Lindemann
    #     a nonzero algebraic w would make exp(w) == x/w algebraic
    #     (Lindemann-Weierstrass), and w != 0 for x != 0
    for_all((LambertW,),
        (Q.algebraic(argument) & ~Q.zero(argument)) >> Q.transcendental(f(argument)),
        (Q.integer(branch) & Q.algebraic(argument) & ~Q.zero(argument))
        >> Q.transcendental(f(argument, branch))),

    # Not real off the reals
    #     a real w makes x == w*exp(w) real; finite at a finite x != 0
    for_all((LambertW,),
        (Q.complex(argument) & ~Q.extended_real(argument)) >> ~Q.extended_real(f(argument)),
        (Q.integer(branch) & Q.complex(argument) & ~Q.extended_real(argument)) >> (
            Q.complex(f(argument, branch)) & ~Q.extended_real(f(argument, branch)))),

    # Zero at 0
    #     on the principal branch
    for_all((LambertW,),
        Q.zero(argument) >> Q.zero(f(argument)),
        (Q.zero(branch) & Q.zero(argument)) >> Q.zero(f(argument, branch))),

    # Entire on the principal branch
    #     W_0 is finite at every finite x
    for_all((LambertW,),
        closed(f, Q.complex),
        (Q.zero(branch) & Q.complex(argument)) >> Q.complex(f(argument, branch))),

    # Positive on the positive reals
    #     on the principal branch: w*exp(w) increases from 0 on w > 0
    for_all((LambertW,),
        Q.positive(argument) >> Q.positive(f(argument)),
        (Q.zero(branch) & Q.positive(argument)) >> Q.positive(f(argument, branch))),

    # Negative on [-1/E, 0)
    #     on the branches 0 (in [-1, 0)) and -1 (in (-oo, -1])
    for_all((LambertW,),
        (Q.negative(argument) & Q.ge(argument, -1/E)) >> Q.negative(f(argument)),
        (Q.zero(branch) & Q.negative(argument) & Q.ge(argument, -1/E))
        >> Q.negative(f(argument, branch)),
        (Q.eq(branch, -1) & Q.negative(argument) & Q.ge(argument, -1/E))
        >> Q.negative(f(argument, branch))),

    # Not real below -1/E
    #     w*exp(w) >= -1/E for real w, so no branch is real there; here
    #     for the branches 0 and -1
    for_all((LambertW,),
        (Q.negative(argument) & Q.lt(argument, -1/E)) >> ~Q.extended_real(f(argument)),
        (Q.zero(branch) & Q.negative(argument) & Q.lt(argument, -1/E))
        >> ~Q.extended_real(f(argument, branch)),
        (Q.eq(branch, -1) & Q.negative(argument) & Q.lt(argument, -1/E))
        >> ~Q.extended_real(f(argument, branch))),

    # oo at oo
    #     on the principal branch
    for_all((LambertW,),
        (Q.infinite(argument) & Q.extended_positive(argument)) >> Q.extended_positive(f(argument)),
        (Q.zero(branch) & Q.infinite(argument) & Q.extended_positive(argument))
        >> Q.extended_positive(f(argument, branch))),

    # Not real on the positive reals, on the branch -1
    #     W_-1 is real on [-1/E, 0) only
    for_all((LambertW,),
        (Q.eq(branch, -1) & Q.positive(argument)) >> ~Q.extended_real(f(argument, branch))),

    # -oo at 0 off the principal branch
    #     SymPy's value: LambertW(0, k) == -oo for k != 0
    for_all((LambertW,),
        (Q.integer(branch) & ~Q.zero(branch) & Q.zero(argument)) >> (
            Q.infinite(f(argument, branch)) & Q.extended_negative(f(argument, branch)))),

    # Not real on the reals off the branches 0 and -1
    #     only W_0 and W_-1 take real values at a real x != 0
    for_all((LambertW,),
        (Q.integer(branch) & ~Q.zero(branch) & Q.ne(branch, -1)
         & Q.real(argument) & ~Q.zero(argument)) >> ~Q.extended_real(f(argument, branch))),
)
