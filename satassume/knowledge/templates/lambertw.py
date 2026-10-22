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

from ._rows import closed, f, for_all, x, y

RULES = (
    # Zero only at 0
    #     w*exp(w) == x: w == 0 gives x == 0, on every branch
    for_all((LambertW,),
        Q.zero(f(x)) >> Q.zero(x),
        Q.zero(f(x, y)) >> Q.zero(x)),

    # Infinite at infinity
    #     LambertW(oo) == oo, on every branch
    for_all((LambertW,),
        Q.infinite(x) >> Q.infinite(f(x)),
        (Q.integer(y) & Q.infinite(x)) >> Q.infinite(f(x, y))),

    # Lindemann
    #     a nonzero algebraic w would make exp(w) == x/w algebraic
    #     (Lindemann-Weierstrass), and w != 0 for x != 0
    for_all((LambertW,),
        (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x)),
        (Q.integer(y) & Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x, y))),

    # Not real off the reals
    #     a real w makes x == w*exp(w) real; finite at a finite x != 0
    for_all((LambertW,),
        (Q.complex(x) & ~Q.extended_real(x)) >> ~Q.extended_real(f(x)),
        (Q.integer(y) & Q.complex(x) & ~Q.extended_real(x)) >> (
            Q.complex(f(x, y)) & ~Q.extended_real(f(x, y)))),

    # Zero at 0
    #     on the principal branch
    for_all((LambertW,),
        Q.zero(x) >> Q.zero(f(x)),
        (Q.zero(y) & Q.zero(x)) >> Q.zero(f(x, y))),

    # Entire on the principal branch
    #     W_0 is finite at every finite x
    for_all((LambertW,),
        closed(f, Q.complex),
        (Q.zero(y) & Q.complex(x)) >> Q.complex(f(x, y))),

    # Positive on the positive reals
    #     on the principal branch: w*exp(w) increases from 0 on w > 0
    for_all((LambertW,),
        Q.positive(x) >> Q.positive(f(x)),
        (Q.zero(y) & Q.positive(x)) >> Q.positive(f(x, y))),

    # Negative on [-1/E, 0)
    #     on the branches 0 (in [-1, 0)) and -1 (in (-oo, -1])
    for_all((LambertW,),
        (Q.negative(x) & Q.ge(x, -1/E)) >> Q.negative(f(x)),
        (Q.zero(y) & Q.negative(x) & Q.ge(x, -1/E)) >> Q.negative(f(x, y)),
        (Q.eq(y, -1) & Q.negative(x) & Q.ge(x, -1/E)) >> Q.negative(f(x, y))),

    # Not real below -1/E
    #     w*exp(w) >= -1/E for real w, so no branch is real there; here
    #     for the branches 0 and -1
    for_all((LambertW,),
        (Q.negative(x) & Q.lt(x, -1/E)) >> ~Q.extended_real(f(x)),
        (Q.zero(y) & Q.negative(x) & Q.lt(x, -1/E)) >> ~Q.extended_real(f(x, y)),
        (Q.eq(y, -1) & Q.negative(x) & Q.lt(x, -1/E)) >> ~Q.extended_real(f(x, y))),

    # oo at oo
    #     on the principal branch
    for_all((LambertW,),
        (Q.infinite(x) & Q.extended_positive(x)) >> Q.extended_positive(f(x)),
        (Q.zero(y) & Q.infinite(x) & Q.extended_positive(x)) >> Q.extended_positive(f(x, y))),

    # Not real on the positive reals, on the branch -1
    #     W_-1 is real on [-1/E, 0) only
    for_all((LambertW,),
        (Q.eq(y, -1) & Q.positive(x)) >> ~Q.extended_real(f(x, y))),

    # -oo at 0 off the principal branch
    #     SymPy's value: LambertW(0, k) == -oo for k != 0
    for_all((LambertW,),
        (Q.integer(y) & ~Q.zero(y) & Q.zero(x)) >> (
            Q.infinite(f(x, y)) & Q.extended_negative(f(x, y)))),

    # Not real on the reals off the branches 0 and -1
    #     only W_0 and W_-1 take real values at a real x != 0
    for_all((LambertW,),
        (Q.integer(y) & ~Q.zero(y) & Q.ne(y, -1) & Q.real(x) & ~Q.zero(x)) >> (
            ~Q.extended_real(f(x, y)))),
)
