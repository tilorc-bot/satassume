"""Structural templates for ``Add``, ``Mul`` and ``Pow``.

Every rule relates predicates of the node ``y`` to predicates of its
arguments and is a theorem about the *value* of the node under SymPy's
conventions (``1/0 = zoo``, ``0**0 = 1``, ``oo - oo = nan`` is "unknown").
The rules mirror SymPy's ``_eval_is_*`` methods in
``sympy/core/{add,mul,power}.py`` except where those are unsound under
value semantics (noted inline).  The notation is described in
:mod:`.dsl`; ``python tools/dump_rules.py 'x**2'`` prints what a given
expression gets.

The rule base is relied on for everything it can derive (``positive ==
extended_positive & finite``, ``zero == extended_nonnegative &
extended_nonpositive``, ...), and "transfer" facts from the node back to an
argument are emitted only for numeric coefficients, which is what the old
assumption system relies on (``-x``, ``2*x``, ``x/2``).
"""
from __future__ import annotations

from itertools import product

from sympy import S
from sympy.core.add import Add
from sympy.core.intfunc import integer_nthroot
from sympy.core.mul import Mul
from sympy.core.power import Pow
from sympy.functions.elementary.exponential import exp

from ..formula import Not, P
from ._common import SIGN_FLIP, VOCAB
from .dsl import any_of, given, integer_at_least_2, none_of, template

#: Largest arity for per-argument rules of Mul (O(n^2) literals).
MAX_ONEOUT = 6
#: Largest arity for rules enumerating pairs of arguments.
MAX_PAIRS = 4
#: Largest arity for subtraction rules and parity case enumeration of Add.
MAX_ADD_SMALL = 3


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

#: Closed under addition.  ``real``, ``zero`` and the finite sign
#: predicates are derived by the rule base from these.
ADD_CLOSED = (
    'extended_real', 'complex', 'integer', 'rational', 'algebraic', 'finite',
    'hermitian', 'antihermitian', 'commutative',
    'extended_positive', 'extended_negative',
    'extended_nonnegative', 'extended_nonpositive',
)

#: Closed under subtraction of finite values.  (The contrapositives give "one
#: non-integer term makes a non-integer sum" etc., and with the rule base
#: also irrational, transcendental and noninteger sums.)
ADD_SUBTRACT = ('real', 'complex', 'integer', 'rational', 'algebraic', 'finite')


@template(Add, nary=True)
def add_rules(terms, y):
    """``y == terms[0] + terms[1] + ...``"""
    n = len(terms)

    for pred in ADD_CLOSED:
        yield terms[pred] >> y[pred]
    if n > MAX_ADD_SMALL:
        yield terms.even >> y.even
    yield terms.imaginary >> (y.imaginary | y.zero)     # I + (-I) == 0
    for t in terms:
        yield y.commutative >> t.commutative            # SymPy's convention

    for t, rest in terms.each_with_rest():
        # One strictly signed term among same-signed terms.
        yield (t.extended_positive & rest.extended_nonnegative) >> y.extended_positive
        yield (t.extended_negative & rest.extended_nonpositive) >> y.extended_negative
        # An imaginary term plus finite reals is not real.
        yield (t.imaginary & rest.real) >> ~y.extended_real
        if n <= MAX_ADD_SMALL:
            for pred in ADD_SUBTRACT:
                # t == y - rest
                yield (y[pred] & rest[pred]) >> t[pred]
        elif n <= MAX_ONEOUT:
            yield (t.odd & rest.even) >> y.odd
        if n <= MAX_ONEOUT:
            # A nonzero real part (finite or infinite) cannot be cancelled
            # by imaginary terms.
            yield (t.extended_nonzero & rest.imaginary) >> ~y.imaginary
            # Infinite sums: ``oo - oo``, ``oo + zoo``, ``oo*I - oo*I`` and
            # the like are nan ("unknown"); every other infinite sum is
            # infinite (``oo + I``, ``oo + oo*I``, ``zoo + 1``, ``-oo + I``).
            # So an infinite term that is not -oo makes the sum infinite
            # unless another term is -oo, and symmetrically.
            yield (t.infinite & ~t.negative_infinite
                   & none_of(rest).negative_infinite) >> y.infinite
            if t.is_const:
                # oo plus terms that are >= 0 or finite real is oo.
                yield (t.positive_infinite & rest.extended_nonnegative) >> y.extended_positive
                yield (t.positive_infinite & rest.real) >> y.extended_positive
            yield (t.infinite & ~t.positive_infinite
                   & none_of(rest).positive_infinite) >> y.infinite
            if t.is_const:
                yield (t.negative_infinite & rest.extended_nonpositive) >> y.extended_negative
                yield (t.negative_infinite & rest.real) >> y.extended_negative

    # Parity of a sum of integers, case by case.
    if n <= MAX_ADD_SMALL:
        for parities in product(('even', 'odd'), repeat=n):
            odd = parities.count('odd') % 2 == 1
            yield given(*(t[p] for t, p in zip(terms, parities))) >> (y.odd if odd else y.even)
    # A sum of two or more positive even integers is at least 4.
    if n >= 2:
        yield (terms.even & terms.positive) >> y.composite


# ---------------------------------------------------------------------------
# Mul
# ---------------------------------------------------------------------------

#: Closed under multiplication.  ``real`` and ``positive`` are derived by
#: the rule base (``extended_* & finite``).
MUL_CLOSED = (
    'extended_real', 'complex', 'integer', 'rational', 'algebraic', 'finite',
    'commutative', 'extended_positive', 'nonnegative',
)

#: For a nonzero real numeric coefficient ``c``: ``pred(c*x) -> pred(x)``
#: (sign predicates flipped for negative ``c``).  The forward directions
#: follow from the closure and per-factor rules.
COEFF_BACK = (
    'positive', 'negative', 'nonnegative', 'nonpositive',
    'extended_positive', 'extended_negative', 'real', 'extended_real',
    'finite', 'complex', 'imaginary',
)


@template(Mul, nary=True)
def mul_rules(factors, y):
    """``y == factors[0] * factors[1] * ...``"""
    n = len(factors)

    for pred in MUL_CLOSED:
        yield factors[pred] >> y[pred]
    for f in factors:
        yield y.commutative >> f.commutative

    for f, rest in factors.each_with_rest():
        yield (f.zero & rest.finite) >> y.zero
    yield y.zero >> any_of(factors).zero

    yield (factors.commutative & factors.hermitian) >> y.hermitian
    yield factors.polar >> y.polar
    for f, rest in factors.each_with_rest():
        yield (f.polar & rest.positive) >> y.polar

    if n >= 2:
        yield factors.prime >> y.composite

    # All factors negative / nonpositive / imaginary: the sign is the
    # parity of n.
    even_n = n % 2 == 0
    yield factors.extended_negative >> (y.extended_positive if even_n else y.extended_negative)
    yield factors.nonpositive >> (y.nonnegative if even_n else y.nonpositive)
    yield factors.imaginary >> (y.nonzero if even_n else y.imaginary)
    yield factors.odd >> y.odd

    if n <= MAX_ONEOUT:
        for f, rest in factors.each_with_rest():
            yield (f.infinite & none_of(rest).zero) >> y.infinite
            # Exactly one negative factor.
            yield (f.extended_negative & rest.extended_positive) >> y.extended_negative
            yield (f.nonpositive & rest.nonnegative) >> y.nonpositive
            yield (f.even & rest.integer) >> y.even
            # The product is 0, negative, or a multiple of a composite.
            yield (f.composite & rest.integer) >> ~y.prime
            yield (f.irrational & rest.rational & none_of(rest).zero) >> y.irrational
            yield (~f.extended_real & rest.extended_nonzero) >> ~y.extended_real
            # With the other factors merely real the product may be zero.
            yield (f.imaginary & rest.real & none_of(rest).zero) >> y.imaginary
            yield (f.imaginary & rest.real) >> (y.imaginary | y.zero)
            if n == 2:
                # I*a*(c + I*d) has real part -a*d and imaginary part a*c:
                # the product is real iff the other factor is imaginary or
                # zero, and imaginary iff the other factor is a nonzero real.
                g, = rest
                yield (f.imaginary & g.complex & y.extended_real) >> (g.imaginary | g.zero)
                yield (f.imaginary & g.complex & y.imaginary) >> g.real

    if 3 <= n <= MAX_PAIRS:
        # The sign of a product with 2 <= m < n negative factors (one and
        # all are above).
        for m in range(2, n):
            for negative, rest in factors.subsets(m):
                even_m = m % 2 == 0
                yield (negative.extended_negative & rest.extended_positive) >> (
                    y.extended_positive if even_m else y.extended_negative)
                yield (negative.nonpositive & rest.nonnegative) >> (
                    y.nonnegative if even_m else y.nonpositive)
        for (f, g), rest in factors.subsets(2):
            yield (f.imaginary & g.imaginary & rest.real & none_of(rest).zero) >> y.nonzero

    # A numeric coefficient c*x: transfer facts back from the product to x.
    if n == 2 and factors[0].is_const and factors[0].value.is_Number:
        c, x = factors[0].value, factors[1]
        if c.is_finite and c.is_extended_real and not c.is_zero:
            for pred in COEFF_BACK:
                yield y[pred] >> x[SIGN_FLIP.get(pred, pred) if c.is_negative else pred]
            if c.is_Rational:
                yield y.rational >> x.rational
                yield y.algebraic >> x.algebraic
                if c.q == 2:
                    # (p/2)*x for integer x is an integer iff x is even.
                    yield x.integer >> y.integer.iff(x.even)
                elif c is S.NegativeOne:
                    yield y.integer >> x.integer
                    yield y.even >> x.even
                    yield y.odd >> x.odd


# ---------------------------------------------------------------------------
# Pow
# ---------------------------------------------------------------------------

#: Ways to say "b is not 0 or 1" (for Gelfond-Schneider).
NOT_0_OR_1 = ('irrational', 'noninteger', 'negative', 'prime', 'composite')
#: Ways to say "b is real with |b| not 0 or 1".
NOT_0_OR_UNIT = ('irrational', 'noninteger', 'prime', 'composite')


def pow_shape(expr):
    """The derived objects and parameters of ``b**e``:

    * ``u``: the argument when ``b`` is ``exp(u)`` or ``E**u``;
    * ``s``, param ``c``: ``e == I*pi*c*s`` for base ``E`` (``c`` rational,
      ``s`` absent when it is 1);
    * ``two_e``: ``2*e`` for a symbolic exponent;
    * ``b_minus_1``, ``b_plus_1``: for a symbolic base and exponent;
    * ``same``: ``b`` is ``e``; ``angle``: ``b == exp(I*pi*angle)`` for
      ``b`` in ``I, -I, -1``."""
    b, e = expr.args
    s = c = None
    if b is S.Exp1 and not (e.is_Atom and e.is_number):
        split = ipi_split(e)
        if split is not None:
            c, s = split
    symbolic = not e.is_number
    both_symbolic = symbolic and not b.is_number
    objects = {
        'u': _exp_arg(b),
        's': s,
        'two_e': Mul(S(2), e) if symbolic else None,
        'b_minus_1': b - S.One if both_symbolic else None,
        'b_plus_1': b + S.One if both_symbolic else None,
    }
    return objects, {'same': b is e, 'angle': _unit_angle(b), 'c': c}


def _unit_power_extra(expr, params):
    angle = params['angle']
    if angle is not None and expr.args[1].is_number:
        return _unit_power_units(angle, expr.args[1], expr)
    return None


@template(Pow, shape=pow_shape, extra=_unit_power_extra)
def pow_rules(b, e, y, *, u, s, two_e, b_minus_1, b_plus_1, same, angle, c):
    """``y == b**e``; see :func:`pow_shape` for the other names."""
    # --- sign ---
    yield (b.positive & e.real) >> y.positive
    yield (b.extended_positive & e.positive) >> y.extended_positive
    yield (b.extended_positive & e.extended_real) >> y.extended_nonnegative
    yield (b.extended_nonnegative & e.extended_nonnegative) >> y.extended_nonnegative
    yield (b.extended_nonnegative & e.extended_real) >> ~y.extended_negative
    yield (b.extended_real & e.even) >> ~y.extended_negative
    yield (b.nonzero & e.even) >> y.positive
    # (-oo)**(-2) == 0, so the extended version needs a nonnegative exponent.
    yield (b.extended_negative & e.even & e.nonnegative) >> y.extended_positive
    yield (b.negative & e.odd) >> y.negative
    yield (b.extended_negative & e.odd) >> y.extended_nonpositive
    yield (b.extended_nonpositive & e.odd) >> ~y.extended_positive
    yield (y.positive & b.real & e.odd) >> b.positive
    yield (y.negative & b.real & e.odd) >> b.negative

    # --- zero base, zero exponent (b**0 == 1, also for zoo and nan) ---
    yield (b.zero & e.extended_positive) >> y.zero
    yield (b.zero & e.extended_nonpositive) >> ~y.zero
    yield (b.zero & e.extended_negative) >> y.infinite
    yield e.zero >> y.positive
    # SymPy leaves ``oo**0.0`` unevaluated and calls it non-integer.
    yield (e.zero & b.finite) >> y.odd

    # --- zero / nonzero / finite / infinite ---
    yield (~b.zero & b.finite & e.finite) >> ~y.zero
    yield (b.infinite & e.negative) >> y.zero
    yield (~b.zero & e.nonnegative) >> ~y.zero
    yield (b.finite & e.negative) >> ~y.zero
    yield (b.finite & e.finite & e.nonnegative) >> y.finite
    yield (b.finite & e.finite & ~b.zero) >> y.finite
    yield (b.infinite & e.positive) >> y.infinite

    # --- integer / rational ---
    yield (b.integer & e.integer & e.nonnegative) >> y.integer
    yield (b.even & e.integer & e.positive) >> y.even
    yield (b.odd & e.integer & e.nonnegative) >> y.odd
    yield (b.rational & ~b.integer & e.rational & e.positive) >> ~y.integer
    yield (b.rational & e.integer & e.nonnegative) >> y.rational
    yield (b.rational & e.integer & ~b.zero) >> y.rational

    # --- extended real / imaginary ---
    yield (b.extended_nonzero & e.integer) >> y.extended_real
    yield (b.extended_real & e.integer & e.nonnegative) >> y.extended_real
    yield (b.negative & e.real & ~e.integer) >> ~y.extended_real
    yield (b.extended_real & e.integer) >> ~y.imaginary
    yield (b.extended_real & e.extended_real & ~e.rational) >> ~y.imaginary
    yield (b.positive & e.extended_real) >> ~y.imaginary
    yield (b.imaginary & e.even) >> y.nonzero
    yield (b.imaginary & e.odd) >> y.imaginary

    # --- complex ---
    yield (b.complex & e.complex & ~b.zero) >> y.complex
    yield (b.complex & e.complex & e.nonnegative) >> y.complex

    # --- prime ---
    yield (b.integer & e.prime) >> ~y.prime
    yield (b.integer & e.even & e.positive) >> ~y.prime

    # --- algebraic ---
    yield (b.algebraic & e.rational & ~b.zero) >> y.algebraic
    yield (b.algebraic & e.rational & e.positive) >> y.algebraic
    yield (b.transcendental & e.rational & ~e.zero) >> ~y.algebraic

    # --- polar / commutative ---
    yield b.polar >> y.polar
    yield (b.commutative & e.commutative) >> y.commutative
    yield y.commutative >> b.commutative
    yield y.commutative >> e.commutative

    if b.value is S.Exp1:
        yield from exp_rules(e, y, s=s, c=c)

    if same:
        # x**x
        yield b.extended_nonnegative >> y.extended_positive
    if e.value is S.One:
        for pred in sorted(VOCAB - {'commutative'}):
            yield y[pred].iff(b[pred])
    # A power of a composite is 1, a fraction or composite.
    yield (b.composite & e.integer) >> ~y.prime
    # For algebraic b = r*exp(I*phi) != 0 and algebraic e = I*t, b**e is
    # exp(-t*phi)*exp(I*t*log(r)) with r algebraic; t*log(r) in pi*Q with
    # t algebraic nonzero forces log(r)/(I*pi) algebraic, hence rational
    # (Gelfond-Schneider), hence r == 1.  So b**e is never imaginary, and
    # it is real iff |b| == 1 (then it is positive).
    yield (b.algebraic & ~b.zero & e.imaginary & e.algebraic) >> ~y.imaginary
    for pred in NOT_0_OR_UNIT:
        yield (b[pred] & b.algebraic & e.imaginary & e.algebraic) >> ~y.extended_real
    if angle is not None:
        # I, -I, -1 to an imaginary power
        yield e.imaginary >> y.positive
    if u is not None:
        # (exp(u))**e == exp(e*(u - 2*pi*I*k)) is positive for imaginary u, e.
        yield (u.imaginary & e.imaginary) >> y.positive
    if b_minus_1 is not None:
        # An integer other than 0 and +-1 to a negative integer power is a
        # fraction (0 gives zoo).
        yield given(b.integer, e.integer, e.negative,
                    ~b_minus_1.zero, ~b_plus_1.zero) >> ~y.integer
    if two_e is not None:
        # Real base, rational exponent: imaginary iff the base is negative
        # and the exponent is half an odd integer.
        yield (b.extended_real & e.rational & ~two_e.integer) >> ~y.imaginary
        yield (b.negative & e.rational & two_e.integer & ~e.integer) >> y.imaginary

    ev = e.value
    if ev is not None and ev.is_Rational and not ev.is_Integer:
        if ev.q == 2:
            # b**(k/2) for real b is imaginary iff b is a negative real.
            yield b.extended_real >> y.imaginary.iff(b.negative)
            yield b.extended_real >> ~y.extended_negative
        else:
            yield b.extended_real >> ~y.imaginary
        if ev.p == 1:
            # (b**(1/q))**q == b: a non-real base gives a non-real root.
            yield ~b.extended_real >> ~y.extended_real
        elif ev.p == -1:
            # Likewise for 1/b**(1/q), but zoo**(-1/2) == 0 is real.
            yield (~b.extended_real & b.finite) >> ~y.extended_real
        bv = b.value
        if bv is not None and bv.is_Rational and bv.is_positive:
            # b**(p/q) with gcd(p, q) == 1 is rational iff b is a perfect
            # q-th power (exact integer arithmetic).
            if not (integer_nthroot(bv.p, ev.q)[1] and integer_nthroot(bv.q, ev.q)[1]):
                yield y.irrational
    if ev is S.NegativeOne:
        # 1/b is rational iff b is (nonzero) rational.
        yield b.irrational >> y.irrational

    bv = b.value
    if bv is not None:
        if bv is S.NegativeOne:
            yield e.integer >> y.odd
        elif bv.is_Integer and (bv.p >= 2 or bv.p <= -2):
            # |b|**e < 1 for negative e.
            yield e.negative >> ~y.integer
        if bv.is_algebraic and bv.is_zero is False and bv is not S.One:
            # Gelfond-Schneider.
            yield e.algebraic >> y.algebraic.iff(e.rational)
        if bv.is_Number and bv.is_finite:
            # Exact comparisons of a number with 1 (no assumptions involved).
            if abs(bv) > 1:
                yield e.extended_negative >> y.finite
                yield e.negative_infinite >> y.zero
                yield e.positive_infinite >> y.infinite
            elif bv.is_zero is False and abs(bv) < 1:
                yield e.extended_positive >> y.finite
                yield e.positive_infinite >> y.zero
                yield e.negative_infinite >> y.infinite
    if ev is not None:
        if ev.is_Integer and ev.p >= 2:
            # b**e for integer b >= 2 is composite.
            for b_at_least_2 in integer_at_least_2(b):
                yield b_at_least_2 >> y.composite
        if ev.is_algebraic and ev.is_rational is False:
            # Gelfond-Schneider.
            for pred in NOT_0_OR_1:
                yield (b[pred] & b.algebraic) >> ~y.algebraic


# ---------------------------------------------------------------------------
# exp (also E**x)
# ---------------------------------------------------------------------------

def ipi_split(arg):
    """``arg == I*pi*c*s`` structurally (a ``Mul`` with one ``I`` factor, one
    ``pi`` factor, rational coefficients ``c`` and other factors ``s``):
    returns ``(c, s)`` with ``s`` None when there are no other factors, else
    None."""
    if not arg.is_Mul:
        return None
    c = S.One
    rest = []
    seen_i = seen_pi = False
    for f in arg.args:
        if f is S.ImaginaryUnit and not seen_i:
            seen_i = True
        elif f is S.Pi and not seen_pi:
            seen_pi = True
        elif f.is_Rational:
            c *= f
        else:
            rest.append(f)
    if not (seen_i and seen_pi):
        return None
    return c, (None if not rest else rest[0] if len(rest) == 1 else Mul(*rest))


def exp_shape(expr):
    """For ``exp(x)``: ``x == I*pi*c*s`` (``c`` rational, ``s`` absent when
    it is 1), else ``c`` and ``s`` are None."""
    x = expr.args[0]
    s = c = None
    if not (x.is_Atom and x.is_number):
        split = ipi_split(x)
        if split is not None:
            c, s = split
    return {'s': s}, {'c': c}


@template(exp, shape=exp_shape)
def exp_rules(x, y, *, s, c):
    """``y == exp(x)``; for ``x == I*pi*c*s`` the value is a root of unity
    or on the unit circle, stated in terms of ``s``.  Also used for
    ``E**x``."""
    yield x.extended_real >> y.extended_real
    yield x.extended_real >> y.extended_nonnegative
    yield x.real >> y.positive
    yield x.complex >> y.complex
    yield x.extended_negative >> y.complex
    yield x.finite >> y.finite
    yield x.finite >> ~y.zero
    # Lindemann-Weierstrass.
    yield (x.algebraic & ~x.zero) >> y.transcendental
    yield (x.infinite & x.extended_negative) >> y.zero
    yield (x.infinite & x.extended_positive) >> (y.infinite & y.extended_positive)
    yield x.zero >> (y.odd & y.positive)                # exp(0) == 1

    if c is None:
        return
    if s is None:
        # exp(I*pi*c)
        if c.is_integer:
            yield y.odd
            yield y.positive if c.p % 2 == 0 else y.negative
        elif c.q == 2:
            yield y.imaginary
            yield y.algebraic
        else:
            yield y.algebraic
            yield ~y.extended_real
            yield ~y.imaginary
            yield ~y.zero
        return
    yield s.integer >> y.algebraic
    yield s.real >> y.complex
    yield s.real >> ~y.zero
    if c.is_integer:
        yield s.integer >> y.odd
        if c.p % 2 == 0:
            yield s.integer >> y.positive
        else:
            yield s.even >> y.positive
            yield s.odd >> y.negative
            yield (s.integer & y.positive) >> s.even
            yield (s.integer & y.negative) >> s.odd
    elif c.q == 2:
        yield s.even >> y.odd
        yield s.odd >> y.imaginary


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _unit_angle(b):
    """``theta/pi`` as a Rational for the constants ``I``, ``-I``, ``-1``
    (``b == exp(I*pi*theta/pi)``), else None."""
    if b is S.ImaginaryUnit:
        return S.Half
    if b is S.NegativeOne:
        return S.One
    if b.is_Mul and b.args == (S.NegativeOne, S.ImaginaryUnit):
        return -S.Half
    return None


def _unit_power_units(angle, e, expr):
    """Unit facts for ``b**e`` with ``b == exp(I*pi*angle)`` (``I``, ``-I``,
    ``-1``) and a numeric exponent ``e == a + I*t``: the value is
    ``exp(-t*pi*angle) * exp(I*pi*a*angle)``, so it is real iff
    ``a*angle`` is an integer (positive for even, negative for odd) and
    imaginary iff ``a*angle`` is half an odd integer.  Only exact real
    parts (atomic numbers) are used."""
    a, t = e.as_real_imag()
    if not (a.is_Atom and a.is_number and t.is_Atom and t.is_number):
        return []
    out = [Not(P('zero', expr)), P('finite', expr), P('complex', expr)]
    if a.is_Rational:
        phi = a * angle
        if phi.is_Integer:
            out.append(P('positive' if phi.p % 2 == 0 else 'negative', expr))
        elif phi.q == 2:
            out.append(P('imaginary', expr))
        else:
            out.append(Not(P('extended_real', expr)))
            out.append(Not(P('imaginary', expr)))
    elif a.is_irrational:
        out.append(Not(P('extended_real', expr)))
        out.append(Not(P('imaginary', expr)))
    return out


def _exp_arg(b):
    """``u`` if ``b`` is ``exp(u)`` or ``E**u``, else None."""
    if b.is_Pow:
        return b.args[1] if b.args[0] is S.Exp1 else None
    if b.is_Function and isinstance(b, exp):
        return b.args[0]
    return None
