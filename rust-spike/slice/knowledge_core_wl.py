"""A workload for core.py's Mul and Pow families (step 6e), as `knowledge_fresh.py core`. dev-400 reaches neither `ipi_rules`
nor `_unit_power_units`, so a MATCH there says nothing about them. Rows: `exp(I*pi*c*s)` and `E**(I*pi*c*s)` over each
`IPI_GUARDS` case, with and without an `s`; `cosh(I*pi*c*s)` and `cos(pi*c*s)` (the `_pi_split` callers in functions.py);
`I`, `-1`, `-I` to numeric powers (`_unit_power_units`, Rational and other exponents); `b**(p/q)` (`irrational_root`);
`a/v**k` (`_quotient_templates`); `(c0 + c1*u)**-k` (`_pow_bound_templates`); `c*x*y` and `I*pi*c*x*y` Muls
(`_mul_factor_sets`' derived sets); 6g(c), under the gaps ruling: `I*x + c*I*y` Adds of I-coefficient terms (with and without a
real term), whose `_imag_split` is non-empty, so rows_tpl.rs's direct imag split and its plant rows-imag-drop-last are reached.
"""
from sympy import Add, E, I, Mul, Pow, Q, Rational, S, Symbol, cos, cosh, exp, pi, sqrt

PREDS = (Q.positive, Q.negative, Q.real, Q.imaginary, Q.zero, Q.integer, Q.algebraic, Q.irrational, Q.odd, Q.even)
CS = (S.Zero, S.One, Rational(2), Rational(-3), Rational(1, 2), Rational(-3, 2), Rational(2, 3), Rational(5, 7))


def queries():
    n = Symbol('n', integer=True)
    m = Symbol('m', odd=True)
    k = Symbol('k', even=True)
    y = Symbol('y', real=True)
    z = Symbol('z')
    x = Symbol('x', positive=True)
    out = []
    for c in CS:
        for s in (None, n, m, k, y, z, n * y):
            arg = c * I * pi if s is None else Mul(c, I, pi, s, evaluate=False) if c != 0 else Mul(I, pi, s)
            for node in (exp(arg, evaluate=False), Pow(E, arg, evaluate=False), cosh(arg, evaluate=False)):
                out.extend((p(node), True) for p in PREDS[:6])
            if s is not None:
                out.append((Q.real(cos(Mul(c, pi, s, evaluate=False), evaluate=False)), True))
                out.append((Q.odd(s), Q.positive(exp(arg, evaluate=False))))
    for b in (I, S.NegativeOne, -I):
        for e in (Rational(1, 2), Rational(1, 3), Rational(2), Rational(-3), Rational(3, 2), Rational(5, 4), I, 1 + I, pi,
                  sqrt(2), Rational(1, 2) + 2 * I):
            node = Pow(b, e, evaluate=False)
            out.extend((p(node), True) for p in PREDS[:5])
    for b in (2, 4, 8, Rational(1, 4), Rational(8, 27), 3, Rational(-8)):
        for e in (Rational(1, 2), Rational(1, 3), Rational(2, 3), Rational(-1, 2), 2):
            out.append((Q.irrational(Pow(S(b), e, evaluate=False)), True))
            out.append((Q.rational(Pow(S(b), e, evaluate=False)), True))
    for a in (S(3), S(-5), m, k, x):
        for v in (k, n, 2 * n, z):
            for e in (-1, -2):
                out.append((Q.integer(Mul(a, Pow(v, e, evaluate=False), evaluate=False)), True))
                out.append((Q.integer(a / v**-e), Q.nonzero(v)))
    for c0 in (S(0), S(1), S(3), S(-5), Rational(1, 2)):
        for c1 in (S(1), S(2), S(-3), Rational(1, 3)):
            for u in (n, m, x):
                for e in (S(-1), S(-2), z):
                    b = c0 + c1 * u
                    if b.is_Add:
                        out.append((Q.integer(Pow(b, e, evaluate=False)), Q.positive(u)))
    for c in (S(2), Rational(-1, 2), Rational(3, 4)):
        out.append((Q.positive(Mul(c, x, y, z, evaluate=False)), Q.positive(y)))
        out.append((Q.real(Mul(c, I, pi, n, y, evaluate=False)), True))
        out.append((Q.imaginary(Mul(I, pi, n, y, evaluate=False)), Q.nonzero(n * y)))
    for c in (S(1), S(2), S(-3), Rational(1, 2)):
        for node in (Add(Mul(I, x, evaluate=False), Mul(c, I, y, evaluate=False), evaluate=False),
                     Add(Mul(I, x, evaluate=False), Mul(c, I, z, evaluate=False), evaluate=False),
                     Add(Mul(I, x, y, evaluate=False), Mul(c, I, evaluate=False), evaluate=False),
                     Add(x, Mul(I, y, evaluate=False), Mul(c, I, z, evaluate=False), evaluate=False)):
            for p in (Q.imaginary, Q.real, Q.zero, Q.nonzero):
                out.append((p(node), Q.positive(y) & Q.positive(z)))
    return out
