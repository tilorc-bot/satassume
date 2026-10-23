"""``Add``: ``f(*terms)`` is the sum of its terms (#299).

Values follow SymPy's conventions: ``oo - oo``, ``oo + zoo`` and ``oo +
nan`` are ``nan`` ("unknown"), so two infinite terms decide nothing
without their directions, and a sum is an extended real only without both
``oo`` and ``-oo`` among its terms.  The rules mirror SymPy's
``_eval_is_*`` methods of ``sympy/core/add.py`` except where those are
unsound under value semantics (noted under the rows).

``f(term, *terms)`` picks one term at any position and ``terms`` are the
others; ``f(term, other, *terms)`` picks two, and ``f(number, *terms)`` a
constant term (an atomic number).  The template states the strict-sign
rows past 32 terms as one formula each, and adds the rules of the sums of
a special shape, which are not rows (``wiring.addition``: half-integer
coefficients, ``c0 + c1*u``, ``c0 + c1/v`` and ``I*(c_1*x_1 + ...)``, in
``core``).  A row with ``at_most`` is left out of wider sums, a limit on
the cost.
"""
from __future__ import annotations

from sympy import Add, Q

from ._rows import count, every, f, for_all, number, other, some, term, terms, third

RULES = (
    # --- closed under addition ---

    # Closed under addition
    #     real, zero and the finite signs follow from these and finite (the
    #     rule base); extended_real is below: oo - oo is nan
    for_all((Add,),
        every(Q.complex, terms) >> Q.complex(f(*terms)),
        every(Q.integer, terms) >> Q.integer(f(*terms)),
        every(Q.rational, terms) >> Q.rational(f(*terms)),
        every(Q.algebraic, terms) >> Q.algebraic(f(*terms)),
        every(Q.finite, terms) >> Q.finite(f(*terms)),
        every(Q.hermitian, terms) >> Q.hermitian(f(*terms)),
        every(Q.antihermitian, terms) >> Q.antihermitian(f(*terms)),
        every(Q.commutative, terms) >> Q.commutative(f(*terms)),
        every(Q.extended_positive, terms) >> Q.extended_positive(f(*terms)),
        every(Q.extended_negative, terms) >> Q.extended_negative(f(*terms)),
        every(Q.extended_nonnegative, terms) >> Q.extended_nonnegative(f(*terms)),
        every(Q.extended_nonpositive, terms) >> Q.extended_nonpositive(f(*terms))),

    # Extended real without both oo and -oo
    #     extended real terms, none of them oo, or none of them -oo
    for_all((Add,),
        (every(Q.extended_real, terms) & every(~Q.positive_infinite, terms))
        >> Q.extended_real(f(*terms)),
        (every(Q.extended_real, terms) & every(~Q.negative_infinite, terms))
        >> Q.extended_real(f(*terms))),

    # Imaginary or zero: imaginary terms
    #     I + (-I) == 0
    for_all((Add,),
        every(Q.imaginary, terms) >> (Q.imaginary(f(*terms)) | Q.zero(f(*terms)))),

    # --- sign ---

    # Positive: a positive term, the others nonnegative
    #     likewise negative; past 32 terms this is one formula (wiring)
    for_all((Add,),
        (some(Q.extended_positive, terms) & every(Q.extended_nonnegative, terms))
        >> Q.extended_positive(f(*terms)),
        (some(Q.extended_negative, terms) & every(Q.extended_nonpositive, terms))
        >> Q.extended_negative(f(*terms))),

    # --- real, imaginary ---

    # Not real: an imaginary term, the others real
    for_all((Add,),
        (Q.imaginary(term) & every(Q.real, terms)) >> ~Q.extended_real(f(term, *terms)),
        at_most=32),

    # Extended real term of an extended real sum, the others real
    #     with r the sum of the others: a term oo or -oo is the sum, a
    #     finite real one gives a real sum, and one that is not extended
    #     real (finite and not real, zoo, or an infinity off the real axis
    #     such as oo*I) a sum that is not extended real (nan + r is nan).
    #     So x - z > 0, which says extended_real(x - z), gives
    #     extended_real(x), as x > z does (#53)
    for_all((Add,),
        (Q.extended_real(f(term, *terms)) & every(Q.real, terms)) >> Q.extended_real(term),
        at_most=32),

    # Not imaginary: a nonzero term, the others imaginary
    #     imaginary terms do not cancel a nonzero real part, finite or
    #     infinite
    for_all((Add,),
        (Q.extended_nonzero(term) & every(Q.imaginary, terms))
        >> ~Q.imaginary(f(term, *terms)), at_most=6),

    # --- a term from the sum ---

    # A term has the fact of the sum and of the others
    #     closed under subtraction of finite values; the contrapositives
    #     give a sum that is not an integer from one term that is not, and
    #     with the closure rows sums that are irrational or transcendental
    for_all((Add,),
        (Q.real(f(term, *terms)) & every(Q.real, terms)) >> Q.real(term),
        (Q.complex(f(term, *terms)) & every(Q.complex, terms)) >> Q.complex(term),
        (Q.integer(f(term, *terms)) & every(Q.integer, terms)) >> Q.integer(term),
        (Q.rational(f(term, *terms)) & every(Q.rational, terms)) >> Q.rational(term),
        (Q.algebraic(f(term, *terms)) & every(Q.algebraic, terms)) >> Q.algebraic(term),
        (Q.finite(f(term, *terms)) & every(Q.finite, terms)) >> Q.finite(term), at_most=3),

    # Commutative term of a commutative sum, the others finite and commutative
    #     the term is the sum minus finite numbers; not in general: A - B
    #     is 0 for B == A, and A + B is 1 for B == 1 - A
    for_all((Add,),
        (Q.commutative(f(term, *terms)) & every(Q.commutative, terms) & every(Q.finite, terms))
        >> Q.commutative(term), at_most=6),

    # --- integers ---

    # Even: even terms
    for_all((Add,),
        every(Q.even, terms) >> Q.even(f(*terms))),

    # Odd: one odd term, the others even
    for_all((Add,),
        (Q.odd(term) & every(Q.even, terms)) >> Q.odd(f(term, *terms)), at_most=6),

    # Two or three odd terms, the others even: the parity by their number
    for_all((Add,),
        (Q.odd(term) & Q.odd(other) & every(Q.even, terms)) >> Q.even(f(term, other, *terms)),
        (Q.odd(term) & Q.odd(other) & Q.odd(third) & every(Q.even, terms))
        >> Q.odd(f(term, other, third, *terms)), at_most=3),

    # Composite: two positive even terms or more
    #     at least 4; two or more: a number of terms that is a prime or
    #     composite (a node of one term, which SymPy does not build, is that
    #     term)
    for_all((Add,),
        (every(Q.even, terms) & every(Q.positive, terms) & Q.prime(count(terms)))
        >> Q.composite(f(*terms)),
        (every(Q.even, terms) & every(Q.positive, terms) & Q.composite(count(terms)))
        >> Q.composite(f(*terms))),

    # Prime or composite: two positive integer terms or more
    #     at least 2; two or more as above
    for_all((Add,),
        (every(Q.integer, terms) & every(Q.positive, terms) & Q.prime(count(terms)))
        >> (Q.prime(f(*terms)) | Q.composite(f(*terms))),
        (every(Q.integer, terms) & every(Q.positive, terms) & Q.composite(count(terms)))
        >> (Q.prime(f(*terms)) | Q.composite(f(*terms)))),

    # --- infinite ---

    # Infinite: an infinite term, the others finite
    #     oo + I, zoo + 1, oo*I + x for a finite x
    for_all((Add,),
        (Q.infinite(term) & every(Q.finite, terms)) >> Q.infinite(f(term, *terms)),
        at_most=6),

    # An infinite term: the sum is infinite or nan
    #     an infinite term and finite ones give an infinity, two or more
    #     infinite terms an infinity or nan (oo - oo, oo + zoo): so the sum
    #     is infinite when it is extended real (nan is not), and no complex
    #     number (x*y + oo*I, -oo + zoo)
    for_all((Add,),
        (Q.infinite(term) & Q.extended_real(f(term, *terms))) >> Q.infinite(f(term, *terms)),
        Q.infinite(term) >> ~Q.complex(f(term, *terms)), at_most=6),

    # oo: a term oo, the others extended real and not -oo
    #     likewise -oo; any term, not only a constant (a symbol declared
    #     positive_infinite is oo).  The others cannot be weaker: oo - oo and
    #     oo + zoo are nan, and oo + I is an infinity off the real axis
    for_all((Add,),
        (Q.positive_infinite(term) & every(Q.extended_real, terms)
         & every(~Q.negative_infinite, terms)) >> Q.positive_infinite(f(term, *terms)),
        (Q.negative_infinite(term) & every(Q.extended_real, terms)
         & every(~Q.positive_infinite, terms)) >> Q.negative_infinite(f(term, *terms)),
        at_most=6),

    # Positive: a constant oo, the others nonnegative or real
    #     likewise negative for a constant -oo
    for_all((Add,),
        (Q.positive_infinite(number) & every(Q.extended_nonnegative, terms))
        >> Q.extended_positive(f(number, *terms)),
        (Q.positive_infinite(number) & every(Q.real, terms))
        >> Q.extended_positive(f(number, *terms)),
        (Q.negative_infinite(number) & every(Q.extended_nonpositive, terms))
        >> Q.extended_negative(f(number, *terms)),
        (Q.negative_infinite(number) & every(Q.real, terms))
        >> Q.extended_negative(f(number, *terms)), at_most=6),
)
