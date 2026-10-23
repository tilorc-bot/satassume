"""``Mul``: ``f(*factors)`` is the product of its factors (#299).

Values follow SymPy's conventions: ``0*oo`` is ``nan`` ("unknown"), so a
product with a zero factor is zero only when the other factors are finite,
and ``1/0 == zoo``.  The rules mirror SymPy's ``_eval_is_*`` methods of
``sympy/core/mul.py`` except where those are unsound under value semantics
(noted under the rows).  Non-commutative factors have zero divisors
(``A*B == 0`` and ``A**2 == 0`` for a nilpotent ``A == B``), so the rows
that divide by a factor ask for commutative or numeric factors.

``f(factor, *factors)`` picks one factor at any position and ``factors``
are the others; ``f(coefficient, factor)`` is a product of two factors
whose first is a SymPy ``Number`` (the numeric coefficient of ``2*x``,
``-x``, ``x/2``), and ``f(-1, factor)`` is ``-x``.  The template applies
the rows to each tuple of factors ``core._mul_factor_sets`` gives (the
arguments, then products derived from them), adds ``a/v**k``
(``core._quotient_templates``), and past 32 factors states the zero row
as one formula (``wiring.product``).  A row with ``at_most`` is left out
of wider products, a limit on the cost.
"""
from __future__ import annotations

from sympy import Equivalent, Mul, Q
from sympy.assumptions.assume import Predicate

from ._rows import coefficient, count, every, f, factor, factors, for_all, other, some, third

RULES = (
    # --- closed under multiplication ---

    # Closed under multiplication
    #     real and positive follow from extended_real and extended_positive
    #     and finite (the rule base); extended_real is below: 0*oo is nan
    for_all((Mul,),
        every(Q.complex, factors) >> Q.complex(f(*factors)),
        every(Q.integer, factors) >> Q.integer(f(*factors)),
        every(Q.rational, factors) >> Q.rational(f(*factors)),
        every(Q.algebraic, factors) >> Q.algebraic(f(*factors)),
        every(Q.finite, factors) >> Q.finite(f(*factors)),
        every(Q.commutative, factors) >> Q.commutative(f(*factors)),
        every(Q.extended_positive, factors) >> Q.extended_positive(f(*factors)),
        every(Q.nonnegative, factors) >> Q.nonnegative(f(*factors)),
        every(Q.odd, factors) >> Q.odd(f(*factors))),

    # Extended real without 0*oo
    #     all factors finite, or all nonzero
    for_all((Mul,),
        (every(Q.extended_real, factors) & every(Q.finite, factors))
        >> Q.extended_real(f(*factors)),
        (every(Q.extended_real, factors) & every(~Q.zero, factors))
        >> Q.extended_real(f(*factors))),

    # Hermitian product of commuting hermitian factors
    for_all((Mul,),
        (every(Q.commutative, factors) & every(Q.hermitian, factors))
        >> Q.hermitian(f(*factors))),

    # Polar product of polar factors
    for_all((Mul,),
        every(Predicate('polar'), factors) >> Predicate('polar')(f(*factors))),

    # Polar: one polar factor, the others positive
    for_all((Mul,),
        (Predicate('polar')(factor) & every(Q.positive, factors))
        >> Predicate('polar')(f(factor, *factors)), at_most=32),

    # --- zero ---

    # Zero: a zero factor, the others finite
    #     past 32 factors this is one formula (wiring)
    for_all((Mul,),
        (some(Q.zero, factors) & every(Q.finite, factors)) >> Q.zero(f(*factors))),

    # Nonzero: nonzero commuting factors
    #     a product of non-commutative values may be zero (A*B == 0)
    for_all((Mul,),
        every(Q.commutative, factors) >> (some(Q.zero, factors) | ~Q.zero(f(*factors)))),

    # Nonzero: nonzero factors, at most one of them not commutative
    for_all((Mul,),
        every(Q.commutative, factors)
        >> (Q.zero(factor) | some(Q.zero, factors) | ~Q.zero(f(factor, *factors))),
        at_most=6),

    # Commutative factor of a commutative product
    #     when the others are nonzero numbers, the factor is the product
    #     divided by them; not in general: 0*A == 0 (#47), and A*B is 1 for
    #     B == A**-1
    for_all((Mul,),
        (Q.commutative(f(factor, *factors)) & every(Q.complex, factors)
         & every(~Q.zero, factors)) >> Q.commutative(factor), at_most=6),

    # --- integers ---

    # Composite: a product of primes
    #     a product has two factors or more
    for_all((Mul,),
        every(Q.prime, factors) >> Q.composite(f(*factors))),

    # Composite: two integers of at least 2
    #     an integer of at least 2 is a prime, a composite or a positive
    #     even number
    for_all((Mul,),
        (Q.prime(factor) & Q.prime(other)) >> Q.composite(f(factor, other, *factors)),
        (Q.prime(factor) & Q.composite(other)) >> Q.composite(f(factor, other, *factors)),
        (Q.prime(factor) & Q.even(other) & Q.positive(other))
        >> Q.composite(f(factor, other, *factors)),
        (Q.composite(factor) & Q.composite(other)) >> Q.composite(f(factor, other, *factors)),
        (Q.composite(factor) & Q.even(other) & Q.positive(other))
        >> Q.composite(f(factor, other, *factors)),
        (Q.even(factor) & Q.positive(factor) & Q.even(other) & Q.positive(other))
        >> Q.composite(f(factor, other, *factors)), at_most=2),

    # Even: one even factor, the others integers
    for_all((Mul,),
        (Q.even(factor) & every(Q.integer, factors)) >> Q.even(f(factor, *factors)),
        at_most=6),

    # Not prime: one composite factor, the others integers
    #     the product is 0, negative, or a multiple of a composite
    for_all((Mul,),
        (Q.composite(factor) & every(Q.integer, factors)) >> ~Q.prime(f(factor, *factors)),
        at_most=6),

    # --- sign ---

    # All factors negative: the sign by their number
    #     likewise all nonpositive, and all imaginary (I*I == -1)
    for_all((Mul,),
        (every(Q.extended_negative, factors) & Q.even(count(factors)))
        >> Q.extended_positive(f(*factors)),
        (every(Q.extended_negative, factors) & Q.odd(count(factors)))
        >> Q.extended_negative(f(*factors)),
        (every(Q.nonpositive, factors) & Q.even(count(factors)))
        >> Q.nonnegative(f(*factors)),
        (every(Q.nonpositive, factors) & Q.odd(count(factors)))
        >> Q.nonpositive(f(*factors)),
        (every(Q.imaginary, factors) & Q.even(count(factors))) >> Q.nonzero(f(*factors)),
        (every(Q.imaginary, factors) & Q.odd(count(factors))) >> Q.imaginary(f(*factors))),

    # One negative factor, the others positive: negative
    #     likewise one nonpositive factor, the others nonnegative
    for_all((Mul,),
        (Q.extended_negative(factor) & every(Q.extended_positive, factors))
        >> Q.extended_negative(f(factor, *factors)),
        (Q.nonpositive(factor) & every(Q.nonnegative, factors))
        >> Q.nonpositive(f(factor, *factors)), at_most=6),

    # Two or three negative factors, the others positive: the sign by their number
    #     likewise nonpositive factors, the others nonnegative
    for_all((Mul,),
        (Q.extended_negative(factor) & Q.extended_negative(other)
         & every(Q.extended_positive, factors))
        >> Q.extended_positive(f(factor, other, *factors)),
        (Q.extended_negative(factor) & Q.extended_negative(other)
         & Q.extended_negative(third) & every(Q.extended_positive, factors))
        >> Q.extended_negative(f(factor, other, third, *factors)),
        (Q.nonpositive(factor) & Q.nonpositive(other) & every(Q.nonnegative, factors))
        >> Q.nonnegative(f(factor, other, *factors)),
        (Q.nonpositive(factor) & Q.nonpositive(other) & Q.nonpositive(third)
         & every(Q.nonnegative, factors))
        >> Q.nonpositive(f(factor, other, third, *factors)), at_most=4),

    # --- infinite ---

    # Infinite: one infinite factor, the others nonzero
    for_all((Mul,),
        (Q.infinite(factor) & every(~Q.zero, factors)) >> Q.infinite(f(factor, *factors)),
        at_most=6),

    # --- irrational, transcendental ---

    # Irrational: one irrational factor, the others nonzero rationals
    for_all((Mul,),
        (Q.irrational(factor) & every(Q.rational, factors) & every(~Q.zero, factors))
        >> Q.irrational(f(factor, *factors)), at_most=6),

    # Transcendental: one transcendental factor, the others nonzero algebraics
    #     the algebraic numbers are a field; likewise one factor that is not
    #     algebraic (possibly infinite or not a complex number): else it
    #     would be the product divided by the others, algebraic (#180 S7)
    for_all((Mul,),
        (Q.transcendental(factor) & every(Q.algebraic, factors) & every(~Q.zero, factors))
        >> Q.transcendental(f(factor, *factors)),
        (~Q.algebraic(factor) & every(Q.algebraic, factors) & every(~Q.zero, factors))
        >> ~Q.algebraic(f(factor, *factors)), at_most=6),

    # --- real, imaginary ---

    # Not real: one factor that is not extended real, the others nonzero extended reals
    for_all((Mul,),
        (~Q.extended_real(factor) & every(Q.extended_nonzero, factors))
        >> ~Q.extended_real(f(factor, *factors)), at_most=6),

    # Imaginary: one imaginary factor, the others nonzero reals
    #     with the others merely real the product may also be zero; and back,
    #     the factor is the product over the nonzero reals
    for_all((Mul,),
        (Q.imaginary(factor) & every(Q.real, factors) & every(~Q.zero, factors))
        >> Q.imaginary(f(factor, *factors)),
        (Q.imaginary(factor) & every(Q.real, factors))
        >> (Q.imaginary(f(factor, *factors)) | Q.zero(f(factor, *factors))),
        (every(Q.real, factors) & every(~Q.zero, factors) & Q.imaginary(f(factor, *factors)))
        >> Q.imaginary(factor), at_most=6),

    # Two imaginary factors, the others nonzero reals: nonzero
    for_all((Mul,),
        (Q.imaginary(factor) & Q.imaginary(other) & every(Q.real, factors)
         & every(~Q.zero, factors)) >> Q.nonzero(f(factor, other, *factors)), at_most=4),

    # An imaginary factor times another, the others nonzero reals
    #     i*a*(c + i*d) has real part -a*d and imaginary part a*c: the
    #     product is real iff the other factor is imaginary or zero, and
    #     imaginary iff the other factor is a nonzero real
    for_all((Mul,),
        (Q.imaginary(factor) & Q.complex(other) & every(Q.real, factors)
         & every(~Q.zero, factors) & Q.extended_real(f(factor, other, *factors)))
        >> (Q.imaginary(other) | Q.zero(other)),
        (Q.imaginary(factor) & Q.complex(other) & every(Q.real, factors)
         & every(~Q.zero, factors) & Q.imaginary(f(factor, other, *factors)))
        >> Q.real(other), at_most=4),

    # --- a numeric coefficient: c*x ---

    # Positive coefficient: the factor has the facts of the product
    #     the forward directions follow from the rows above
    for_all((Mul,),
        (Q.positive(coefficient) & Q.positive(f(coefficient, factor))) >> Q.positive(factor),
        (Q.positive(coefficient) & Q.negative(f(coefficient, factor))) >> Q.negative(factor),
        (Q.positive(coefficient) & Q.nonnegative(f(coefficient, factor)))
        >> Q.nonnegative(factor),
        (Q.positive(coefficient) & Q.nonpositive(f(coefficient, factor)))
        >> Q.nonpositive(factor),
        (Q.positive(coefficient) & Q.extended_positive(f(coefficient, factor)))
        >> Q.extended_positive(factor),
        (Q.positive(coefficient) & Q.extended_negative(f(coefficient, factor)))
        >> Q.extended_negative(factor),
        (Q.positive(coefficient) & Q.real(f(coefficient, factor))) >> Q.real(factor),
        (Q.positive(coefficient) & Q.extended_real(f(coefficient, factor)))
        >> Q.extended_real(factor),
        (Q.positive(coefficient) & Q.finite(f(coefficient, factor))) >> Q.finite(factor),
        (Q.positive(coefficient) & Q.complex(f(coefficient, factor))) >> Q.complex(factor),
        (Q.positive(coefficient) & Q.imaginary(f(coefficient, factor)))
        >> Q.imaginary(factor)),

    # Negative coefficient: the factor has the opposite sign of the product
    for_all((Mul,),
        (Q.negative(coefficient) & Q.positive(f(coefficient, factor))) >> Q.negative(factor),
        (Q.negative(coefficient) & Q.negative(f(coefficient, factor))) >> Q.positive(factor),
        (Q.negative(coefficient) & Q.nonnegative(f(coefficient, factor)))
        >> Q.nonpositive(factor),
        (Q.negative(coefficient) & Q.nonpositive(f(coefficient, factor)))
        >> Q.nonnegative(factor),
        (Q.negative(coefficient) & Q.extended_positive(f(coefficient, factor)))
        >> Q.extended_negative(factor),
        (Q.negative(coefficient) & Q.extended_negative(f(coefficient, factor)))
        >> Q.extended_positive(factor),
        (Q.negative(coefficient) & Q.real(f(coefficient, factor))) >> Q.real(factor),
        (Q.negative(coefficient) & Q.extended_real(f(coefficient, factor)))
        >> Q.extended_real(factor),
        (Q.negative(coefficient) & Q.finite(f(coefficient, factor))) >> Q.finite(factor),
        (Q.negative(coefficient) & Q.complex(f(coefficient, factor))) >> Q.complex(factor),
        (Q.negative(coefficient) & Q.imaginary(f(coefficient, factor)))
        >> Q.imaginary(factor)),

    # Nonzero rational coefficient: the factor is rational or algebraic with the product
    for_all((Mul,),
        (Q.rational(coefficient) & ~Q.zero(coefficient) & Q.rational(f(coefficient, factor)))
        >> Q.rational(factor),
        (Q.rational(coefficient) & ~Q.zero(coefficient) & Q.algebraic(f(coefficient, factor)))
        >> Q.algebraic(factor)),

    # Half an odd integer times an integer: an integer iff the integer is even
    for_all((Mul,),
        (Q.rational(coefficient) & Q.integer(2*coefficient) & ~Q.integer(coefficient)
         & Q.integer(factor))
        >> Equivalent(Q.integer(f(coefficient, factor)), Q.even(factor))),

    # Minus a factor: integer, even and odd with the product
    for_all((Mul,),
        Q.integer(f(-1, factor)) >> Q.integer(factor),
        Q.even(f(-1, factor)) >> Q.even(factor),
        Q.odd(f(-1, factor)) >> Q.odd(factor)),
)
