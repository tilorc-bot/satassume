"""A workload for step 6f's template modules (functions, special, rootof, nodes, physics, stats), as `knowledge_fresh.py f6`.

Built from the code it reaches, never from held-out data (planner's hidden-gap ruling). dev and fuzz reach `_unary`, `nary`,
`parts_of_round_templates`, `_pi_trig` and `_exp_ipi` only (f6_trace.py); `value`, `rootof` and `core` add `_value_units`,
`_genocchi_half`, `multigamma`, `crootof_units` and `_pi_trig_rules`. This adds the rest: `AccumBounds` (`_accum`), `Idx`,
`Quantity`, `RandomSymbol`, `asin`/`acos` of a constant (`_in_unit_interval_units`, both sides of -1 and 1, Rational and Float),
`cosh(r + I*pi*c*s)` (`_cosh_shift_split`, `_cosh_shift_rules`, even and odd `c`, with and without `s`, a cancelling Add),
`sin`/`cos(pi*c*s)` with a constant `c` and no `s` (`_pi_trig_rules`' number branch), `re`/`im` of `floor`/`ceiling`, and
unary rows with shifted slots on a cancelling Add (`shifted`'s #184 guard), and n-ary rows (`nary`).
"""
from sympy import (Add, Mod, RisingFactorial, besselj, beta, binomial, lowergamma, polylog, zeta, Float, I, Idx, Mul, Q, Rational, S, Symbol, acos, asin, ceiling, cos, cosh, floor, im, log, pi, re,
                   sin, tan)
from sympy.calculus.accumulationbounds import AccumulationBounds

PREDS = (Q.real, Q.positive, Q.negative, Q.zero, Q.integer, Q.finite, Q.extended_real, Q.imaginary)
CS = (Rational(0), Rational(1), Rational(-1), Rational(1, 2), Rational(-1, 2), Rational(3, 2), Rational(1, 3), Rational(5, 6),
      Rational(2), Rational(7, 4))
UNIT = (Rational(-3), Rational(-1), Rational(-1, 2), Rational(0), Rational(1, 3), Rational(1), Rational(5, 4), Rational(2),
        Float(0.5), Float(-1.0), Float(1.0), Float(1.5), Float(-2.5), S(7))


def queries():
    n = Symbol('n', integer=True)
    m = Symbol('m', odd=True)
    k = Symbol('k', even=True)
    y = Symbol('y', real=True)
    t = Symbol('t', imaginary=True)
    z = Symbol('z')
    x = Symbol('x', positive=True)
    out = []
    ask = lambda node, ante=True: out.extend((p(node), ante) for p in PREDS)
    for c in CS:
        for f in (sin, cos):
            ask(f(Mul(c, pi, evaluate=False), evaluate=False))
            for s in (n, m, k, y):
                ask(f(Mul(c, pi, s, evaluate=False), evaluate=False))
    for c in (Rational(0), Rational(1), Rational(2), Rational(-3), Rational(1, 2)):
        for r in (y, t, z, x, y + x):
            for s in (None, n, m, k, y):
                ipi = Mul(c, I, pi, evaluate=False) if s is None else Mul(c, I, pi, s, evaluate=False)
                ask(cosh(Add(r, ipi, evaluate=False), evaluate=False))
        ask(cosh(Add(y, -y, Mul(c, I, pi, n, evaluate=False), evaluate=False), evaluate=False))
    for f in (asin, acos):
        for c in UNIT:
            ask(f(c, evaluate=False))
            out.append((Q.positive(f(c, evaluate=False) + x), True))
    for r in (re, im):
        for g in (floor, ceiling):
            for a in (y, z, x + I * y, S(5) / 2, Rational(-7, 3), z + 1):
                ask(r(g(a, evaluate=False), evaluate=False))
    for a in (y, z, Add(y, -y, 1, evaluate=False), Add(z, 2, evaluate=False), x):
        for f in (log, tan):
            ask(f(a, evaluate=False))
    for lo, hi in ((S(1), S(2)), (S(-1), S(3)), (y, y + 1), (x, 2 * x), (S(-5), -x), (Rational(1, 2), pi)):
        try:
            node = AccumulationBounds(lo, hi)
        except Exception:
            continue
        if isinstance(node, AccumulationBounds):
            ask(node)
            out.append((Q.positive(node), Q.positive(lo)))
    for a, b in ((n, S(3)), (x, y), (S(2), x), (k, m), (Add(y, -y, 1, evaluate=False), n), (Rational(1, 2), S(-2))):
        for f in (Mod, polylog, besselj, binomial, lowergamma, zeta, beta, RisingFactorial):
            try:
                ask(f(a, b, evaluate=False))
            except Exception:
                pass
    i, j = Idx('i'), Idx('j', 10)
    for node in (i, j, i + j, 2 * i + 1):
        ask(node)
    try:
        from sympy.physics.units import meter, second, speed_of_light
        for node in (meter, speed_of_light, meter / second, meter + y):
            ask(node)
    except Exception:
        pass
    try:
        from sympy.stats import Die, Exponential, Normal, Poisson
        for node in (Normal('N', 0, 1), Exponential('E1', 1), Poisson('Po', 2), Die('D', 6)):
            ask(node)
            out.append((Q.positive(node + x), True))
    except Exception:
        pass
    return out
