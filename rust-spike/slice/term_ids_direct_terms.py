"""The term generator of the direct comparisons."""
from sympy import Function, I, Mul, Rational as Rat, S, Symbol, exp, log, oo, pi, sqrt, sin

x, y, z, w = Symbol('x'), Symbol('y'), Symbol('z'), Symbol('w', positive=True)
f, g = Function('f'), Function('g')
ATOMS = [x, y, z, w, f(x), f(y), g(x), f(S(1)), g(S(1)), pi, sqrt(2), S(2), S(-3), Rat(1, 2), I, exp(x), exp(S(1)), log(y), sin(x),
         x**2, y**-1, w**Rat(1, 2), S(2)**x, exp(y), exp(x + 1), exp(-y)]
#: Rare, so that most pairs aren't refusals: each is a shape the algebra refuses.
RARE = [S(1.5)*x, oo, -oo, S.NaN, S.ComplexInfinity, Symbol('n', commutative=False), exp(log(y), evaluate=False),
        exp(2*log(x), evaluate=False), exp(S(0), evaluate=False), exp(Symbol('z0', zero=True), evaluate=False)]


def term(r, depth=2):
    k = r.random()
    if depth == 0 or k < 0.3:
        return r.choice(RARE) if r.random() < 0.03 else r.choice(ATOMS)
    n = r.choice((2, 2, 3))
    args = [term(r, depth - 1) for _ in range(n)]
    if k < 0.65:
        return sum(args[1:], args[0])
    return Mul(*args)
