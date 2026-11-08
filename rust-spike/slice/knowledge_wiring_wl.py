"""A workload for wiring.py's rows families on Rust (step 6g(b)), as `live.py wiring`: term/rows_tpl.rs's `any_arity`
(Max, Min, Piecewise through `piecewise_values`, with `leave_out_wide`'s `_clauses`), `wide_formulas`/`_wide` (a node of
more than SOME_PER_ARGUMENT = 32 arguments: Max, Min, Add, Mul), addition's `_imag_templates` (`I*(c_1*x_1 + ...)`), and
power's `pow_templates`. dev, fuzz and the other hidden-gap workloads have no Max, Min or Piecewise node and no node of
more than 32 arguments (reach1: registry:rust:Max/Min/Piecewise_rows_templates, rows:wide, rows:wide_formulas,
rows:clauses and rows:piecewise_values 0 on dev, opaque, core and f6), so a MATCH there says nothing about them. The
queries are built from the code's own cases (wiring.py's docstrings and the rows' kinds): nodes of a few arguments with
and without constants (a Number, a negative one, zero, a half), wide nodes with a constant argument decided in `_wide`,
Piecewise with and without a final True, sums of imaginary products, and powers of symbols and constants.
"""
from sympy import Add, And, I, Max, Min, Mul, Piecewise, Pow, Q, Rational, S, Symbol, pi, E, exp, sqrt

PREDS = (Q.positive, Q.negative, Q.nonnegative, Q.nonpositive, Q.zero, Q.nonzero, Q.real, Q.integer, Q.finite,
         Q.imaginary, Q.even, Q.rational, Q.extended_real)


def queries():
    x, y, z, w = (Symbol(n) for n in 'xyzw')
    wide = [Symbol(f'a{i}') for i in range(36)]
    facts = (True, Q.positive(x) & Q.positive(y), Q.negative(x) & Q.negative(y), Q.real(x) & Q.real(y),
             Q.integer(x) & Q.integer(y) & Q.integer(z), Q.zero(x), Q.nonnegative(x) & Q.positive(y),
             Q.positive(x) & Q.negative(y) & Q.real(z))
    nodes = []
    for f in (Max, Min):
        nodes += [f(x, y, evaluate=False), f(x, y, z, evaluate=False), f(x, S(2), evaluate=False),
                  f(x, S(-1), evaluate=False), f(x, S.Zero, evaluate=False), f(x, y, Rational(1, 2), evaluate=False),
                  f(x, -y, evaluate=False), f(x, y, z, w, S(3), evaluate=False)]
    nodes += [Piecewise((x, y > 0), (S(2), True)), Piecewise((x, y > 0)), Piecewise((x, y > 0), (z, True)),
              Piecewise((x, y > 0), (y, z > 0), (S(-1), True)), Piecewise((S(3), x > 0), (S.Zero, True))]
    nodes += [Add(I*x, 2*I*y), Add(I*x, -I*y), Add(I*x, I*y, I*z), Add(I*x, I*Rational(1, 2)*y, 3*I)]
    nodes += [Pow(x, 2), Pow(x, 3), Pow(x, -1), Pow(x, Rational(1, 2)), Pow(x, y), Pow(S(2), x), Pow(E, x),
              Pow(E, I*pi*x), Pow(x, S(1)/3), sqrt(x*y), Pow(S(-1), x), Pow(x + 1, 2), Pow(2*x, -2), Pow(x, x),
              Pow(E, x, evaluate=False), Pow(E, I*pi*x, evaluate=False), Pow(E, I*pi*Rational(1, 3), evaluate=False),
              Pow(E, I*pi*Rational(2, 3)*x, evaluate=False), Pow(I, Rational(1, 3), evaluate=False),
              Pow(S.NegativeOne, Rational(1, 2), evaluate=False), Pow(-I, Rational(2, 3), evaluate=False),
              Pow(I, x, evaluate=False), Pow(S(2), Rational(1, 2), evaluate=False),
              Pow(S(3), Rational(2, 3), evaluate=False), Pow(exp(x), 2, evaluate=False), Pow(exp(x), y, evaluate=False),
              Pow(2*x + 1, y, evaluate=False), Pow(S(-2), x, evaluate=False), Pow(S.Half, x, evaluate=False)]
    out = []
    for node in nodes:
        for a in facts:
            out.extend((p(node), a) for p in PREDS)
    # wide nodes: more than 32 arguments, with the facts the wide formulas need (every argument, and some one)
    wfacts = (True, And(*[Q.positive(s) for s in wide]), And(*[Q.nonnegative(s) for s in wide]),
              And(*[Q.nonnegative(s) for s in wide[1:]], Q.positive(wide[0])),
              And(*[Q.negative(s) for s in wide]), And(*[Q.real(s) for s in wide]),
              And(*[Q.nonpositive(s) for s in wide], Q.negative(wide[-1])), Q.positive(wide[3]))
    wnodes = []
    for f in (Max, Min):
        wnodes += [f(*wide, evaluate=False), f(*wide, S(5), evaluate=False), f(*wide, S(-5), evaluate=False),
                   f(*wide[:33], evaluate=False), f(*wide[:33], S.Zero, evaluate=False)]
    wnodes += [Add(*wide), Add(*wide, S(1)), Add(*wide, S(-1)), Mul(*wide), Mul(*wide, S(2)), Mul(*wide, S(-3))]
    for node in wnodes:
        for a in wfacts:
            out.extend((p(node), a) for p in PREDS[:7])
    return out
