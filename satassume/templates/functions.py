"""Structural templates for elementary functions.

In every template ``x`` is the argument and ``y`` the value: ``y ==
f(x)``.  Only statements that are theorems about the value under SymPy's
conventions are emitted (``log(0) = zoo``, ``acot(0) = pi/2``, ``atan(oo) =
pi/2``, ``factorial(-1) = zoo``, principal branches, ...).  Transcendence
facts follow from the Lindemann-Weierstrass theorem.  Predicates the rule
base derives from the emitted ones (``positive`` from ``extended_positive &
finite``, ``irrational`` from ``real & !rational``, ...) are not repeated.
The notation is described in :mod:`.dsl`.
"""
from __future__ import annotations

from sympy import S
from sympy.core.function import Function
from sympy.functions.combinatorial.factorials import factorial
from sympy.functions.elementary.complexes import Abs, conjugate, im, re, sign
from sympy.functions.elementary.exponential import log
from sympy.functions.elementary.hyperbolic import cosh, sinh, tanh
from sympy.functions.elementary.integers import RoundFunction, ceiling, floor
from sympy.functions.elementary.trigonometric import (
    acos,
    acot,
    asin,
    atan,
    cos,
    cot,
    sin,
    tan,
)

from ..formula import Not, P
from .dsl import integer_at_least_2, template


def minus_one(expr):
    """Derived object ``x_minus_1 == x - 1`` for ``f(x)``."""
    return {'x_minus_1': expr.args[0] - S.One}, {}


@template(Function, nary=True)
def function_rules(args, y):
    """Any function of commutative arguments is commutative."""
    yield args.commutative >> y.commutative
    for a in args:
        yield y.commutative >> a.commutative


# ---------------------------------------------------------------------------
# log (exp is in .core, next to E**x)
# ---------------------------------------------------------------------------

@template(log, shape=minus_one)
def log_rules(x, y, *, x_minus_1):
    yield x.extended_positive >> y.extended_real
    yield x.positive >> y.real
    yield x.zero >> y.infinite
    yield x.zero >> ~y.extended_real
    yield (x.complex & ~x.zero) >> y.complex
    yield (x.finite & ~x.zero) >> y.finite
    yield x.infinite >> y.infinite
    yield (x.infinite & x.extended_real) >> y.extended_positive
    yield x.negative >> ~y.extended_real
    yield (x.complex & ~x.extended_real) >> ~y.extended_real
    # log(x) == 0 iff x == 1; log(x) > 0 iff x > 1 for positive x.
    yield y.zero.iff(x_minus_1.zero)
    yield x_minus_1.extended_positive >> y.extended_positive
    yield (x_minus_1.negative & x.positive) >> y.negative
    yield (x.positive & y.positive) >> x_minus_1.positive
    yield (x.positive & y.negative) >> x_minus_1.negative
    yield (x.algebraic & ~x.zero & ~y.zero) >> y.transcendental


# ---------------------------------------------------------------------------
# Abs / re / im / sign / conjugate
# ---------------------------------------------------------------------------

@template(Abs)
def abs_rules(x, y):
    yield y.extended_real
    yield y.extended_nonnegative
    yield x.finite >> y.real
    yield y.finite >> x.finite
    yield x.infinite >> y.extended_positive
    yield y.zero.iff(x.zero)
    yield x.algebraic >> y.algebraic
    for pred in ('integer', 'rational', 'even', 'odd', 'algebraic'):
        yield x.extended_real >> y[pred].iff(x[pred])
    # Abs(x) == x for x >= 0.
    for pred in ('prime', 'composite'):
        yield x.extended_nonnegative >> y[pred].iff(x[pred])


@template(re)
def re_rules(x, y):
    yield y.extended_real
    yield x.finite >> y.real
    yield x.imaginary >> y.zero
    yield x.zero >> y.zero
    yield x.algebraic >> y.algebraic
    # re(x) == x for real x.
    for pred in ('zero', 'extended_positive', 'extended_negative', 'integer', 'rational',
                 'even', 'odd', 'algebraic', 'finite', 'prime', 'composite'):
        yield x.extended_real >> y[pred].iff(x[pred])


@template(im)
def im_rules(x, y):
    yield y.extended_real
    yield x.finite >> y.real
    yield x.extended_real >> y.zero
    yield x.imaginary >> y.nonzero
    yield x.algebraic >> y.algebraic


@template(sign)
def sign_rules(x, y):
    yield y.complex
    yield x.extended_real >> y.integer
    yield x.imaginary >> y.imaginary
    yield x.extended_positive >> (y.positive & y.odd)          # 1
    yield x.extended_negative >> (y.negative & y.odd)          # -1
    yield x.extended_nonnegative >> y.nonnegative
    yield x.extended_nonpositive >> y.nonpositive
    yield x.algebraic >> y.algebraic
    yield y.zero.iff(x.zero)
    yield (x.extended_real & y.positive) >> x.extended_positive
    yield (x.extended_real & y.negative) >> x.extended_negative


#: Invariant under conjugation; the rule base derives the rest (real, the
#: finite sign predicates, nonzero, infinite, irrational, transcendental...).
CONJUGATE_INVARIANT = (
    'extended_real', 'finite', 'zero', 'extended_positive', 'extended_negative',
    'integer', 'rational', 'even', 'odd', 'algebraic', 'complex', 'imaginary',
    'prime', 'composite', 'commutative', 'hermitian', 'antihermitian',
)


@template(conjugate)
def conjugate_rules(x, y):
    for pred in CONJUGATE_INVARIANT:
        yield y[pred].iff(x[pred])


# ---------------------------------------------------------------------------
# floor / ceiling
# ---------------------------------------------------------------------------

@template(RoundFunction)
def round_rules(x, y):
    yield y.finite.iff(x.finite)
    # NOTE: floor(1 + I/2) == 1, so "non-real -> non-integer" is unsound.
    yield x.real >> y.integer
    yield x.extended_real >> y.extended_real
    yield x.complex >> y.complex
    for pred in ('even', 'odd', 'zero', 'positive', 'negative'):
        yield x.integer >> y[pred].iff(x[pred])


@template(floor)
def floor_rules(x, y):
    for pred in ('negative', 'extended_negative', 'nonnegative', 'extended_nonnegative'):
        yield x[pred] >> y[pred]


@template(ceiling)
def ceiling_rules(x, y):
    for pred in ('positive', 'extended_positive', 'nonpositive', 'extended_nonpositive'):
        yield x[pred] >> y[pred]


# ---------------------------------------------------------------------------
# factorial
# ---------------------------------------------------------------------------

@template(factorial)
def factorial_rules(x, y):
    yield (x.integer & x.nonnegative) >> (y.positive & y.integer)
    yield x.composite >> y.composite
    yield x.zero >> y.odd                                   # 0! == 1
    yield x.nonnegative >> y.positive
    yield (x.noninteger & x.finite) >> (y.real & ~y.zero)   # gamma(x + 1)
    yield (x.integer & x.negative) >> (y.infinite & ~y.extended_real)   # zoo
    for x_at_least_2 in integer_at_least_2(x):
        yield x_at_least_2 >> y.even


# ---------------------------------------------------------------------------
# trigonometric
# ---------------------------------------------------------------------------

@template(sin)
def sin_rules(x, y):
    # sin(oo*I) == oo*I, so finiteness of the value needs a finite argument.
    yield x.real >> y.real
    yield x.complex >> y.complex
    yield x.finite >> y.finite
    yield x.zero >> y.zero
    yield x.imaginary >> y.imaginary
    yield (x.algebraic & ~x.zero) >> y.transcendental


@template(cos)
def cos_rules(x, y):
    yield x.real >> y.real
    yield x.complex >> y.complex
    yield x.finite >> y.finite
    yield x.zero >> (y.odd & y.positive)                    # cos(0) == 1
    yield x.imaginary >> y.positive                         # cosh
    yield (x.algebraic & ~x.zero) >> y.transcendental


@template(tan)
def tan_rules(x, y):
    # tan(pi/2) == zoo, so realness needs finiteness of the value.
    yield x.real >> ~y.imaginary
    yield x.zero >> y.zero
    yield x.imaginary >> y.imaginary
    yield (x.algebraic & ~x.zero) >> y.transcendental
    yield (x.real & y.finite) >> y.real


@template(cot)
def cot_rules(x, y):
    # cot(k*pi) == zoo, so realness needs finiteness of the value.
    yield x.real >> ~y.imaginary
    yield x.imaginary >> y.imaginary                        # cot(I*t) == -I*coth(t)
    yield x.zero >> y.infinite
    yield x.zero >> ~y.extended_real
    # cot(x) == cos(x)/sin(x) is finite for algebraic x != 0 (sin(x) == 0
    # only at multiples of pi) and transcendental by Lindemann-Weierstrass:
    # cot(x) == a algebraic would make exp(2*I*x) algebraic.
    yield (x.algebraic & ~x.zero) >> y.transcendental
    yield x.algebraic >> ~y.algebraic
    yield (x.real & y.finite) >> y.real
    yield (x.complex & y.finite) >> y.complex


def _unit_interval_units(kind):
    """Unit facts for ``asin(c)``/``acos(c)`` with a rational or float ``c``
    (exact comparisons): real on [-1, 1], else ``+-pi/2 -+ I*acosh|c|``
    or ``I*acosh(c)`` / ``pi - I*acosh|c|``."""
    def units(expr, params):
        c = expr.args[0]
        if not (c.is_Rational or c.is_Float):
            return []
        out = [P('finite', expr), P('complex', expr)]
        if -1 <= c <= 1:
            out.append(P('real', expr))
            if kind == 'acos':
                out.append(P('positive' if c < 1 else 'zero', expr))
            else:
                out.append(P('positive' if c > 0 else 'negative' if c < 0 else 'zero', expr))
        else:
            out.append(Not(P('extended_real', expr)))
            if kind == 'acos' and c > 1:
                out.append(P('imaginary', expr))
            else:
                out.append(Not(P('imaginary', expr)))
        return out
    return units


@template(asin, shape=minus_one, extra=_unit_interval_units('asin'))
def asin_rules(x, y, *, x_minus_1):
    yield y.zero.iff(x.zero)
    yield y.real >> x.real
    yield y.real >> y.positive.iff(x.positive)
    yield y.real >> y.negative.iff(x.negative)
    # asin is real on [0, 1] (and [-1, 0] by symmetry).
    yield (x.nonnegative & x_minus_1.nonpositive) >> y.real
    yield x.finite >> y.finite
    yield x.complex >> y.complex
    yield x.imaginary >> y.imaginary
    yield (x.algebraic & ~x.zero) >> y.transcendental


@template(acos, shape=minus_one, extra=_unit_interval_units('acos'))
def acos_rules(x, y, *, x_minus_1):
    yield y.real >> y.nonnegative
    yield y.real >> x.real
    yield y.zero.iff(x_minus_1.zero)                        # acos(1) == 0
    yield x.zero >> y.positive                              # pi/2
    yield x.finite >> y.finite
    yield x.complex >> y.complex
    yield (x.algebraic & ~y.zero) >> y.transcendental


@template(atan)
def atan_rules(x, y):
    yield x.extended_real >> y.real
    yield y.zero.iff(x.zero)
    yield x.extended_real >> y.positive.iff(x.extended_positive)
    yield x.extended_real >> y.negative.iff(x.extended_negative)
    # atan(I) == oo*I, so restrict to real arguments.
    yield (x.real & x.algebraic & ~x.zero) >> y.transcendental
    # atan(x) is real iff x is real (atan(I*t) is imaginary, infinite or
    # non-real complex).
    yield x.imaginary >> ~y.extended_real


@template(acot)
def acot_rules(x, y):
    yield x.extended_real >> y.real
    yield x.nonnegative >> y.positive                       # acot(0) == pi/2
    yield x.negative >> y.negative
    yield x.extended_nonnegative >> y.nonnegative
    yield x.extended_negative >> y.nonpositive              # acot(-oo) == 0
    yield x.real >> ~y.zero
    yield (x.infinite & x.extended_real) >> y.zero
    yield (x.real & x.algebraic) >> y.transcendental
    yield x.imaginary >> ~y.extended_real
    # acot(0) == pi/2, acot(+-I) is infinite, acot(x) == atan(1/x) otherwise.
    yield x.algebraic >> ~y.algebraic


# ---------------------------------------------------------------------------
# hyperbolic
# ---------------------------------------------------------------------------

@template(sinh)
def sinh_rules(x, y):
    yield x.real >> y.real
    yield x.extended_real >> y.extended_real
    yield x.finite >> y.finite
    yield x.complex >> y.complex
    yield (x.infinite & x.extended_real) >> y.infinite
    yield (x.algebraic & ~x.zero) >> y.transcendental
    for pred in ('extended_positive', 'extended_negative', 'zero'):
        yield x.extended_real >> y[pred].iff(x[pred])
    yield x.imaginary >> (y.imaginary | y.zero)             # I*sin(t)


@template(cosh)
def cosh_rules(x, y):
    yield x.real >> y.positive
    yield x.extended_real >> y.extended_positive
    yield x.finite >> y.finite
    yield x.complex >> y.complex
    yield x.zero >> y.odd                                   # cosh(0) == 1
    yield x.imaginary >> y.real                             # cos(t)
    yield (x.algebraic & ~x.zero) >> y.transcendental


@template(tanh)
def tanh_rules(x, y):
    yield x.extended_real >> y.real
    yield (x.algebraic & ~x.zero) >> y.transcendental
    yield x.extended_real >> y.positive.iff(x.extended_positive)
    yield x.extended_real >> y.negative.iff(x.extended_negative)
    yield x.extended_real >> y.zero.iff(x.zero)
