"""A workload for the registry's `opaque` test (step 6g(a)), as `live.py opaque`: templates/__init__.py `_applied_to_nan`
and `_may_be_nan`, which term/dispatch.rs ports and the engine calls per node. dev, fuzz and the other hidden-gap
workloads have no function applied to a nan-valued argument (registry:opaque 0 on all six), so a MATCH there says
nothing about it. The queries are built from the code's own cases (its docstrings): a function applied to `nan`, to an
argument holding an explicit `oo`, `-oo`, `zoo` or `nan` in a value-carrying part (`x + oo`, `oo - x`, `0*oo` left
unevaluated), nested a level down, inside `Subs`, `UnevaluatedExpr`, a `Piecewise` value and a `Piecewise` condition;
and the near misses that are not opaque (`Abs(x + 1)`, an `Idx` whose range holds `oo`, a function of a plain symbol).
"""
from sympy import (Abs, Add, Idx, Mul, Piecewise, Q, S, Subs, Symbol, UnevaluatedExpr, exp, gamma, im, log, re, sign,
                   sin, sqrt)

PREDS = (Q.positive, Q.negative, Q.real, Q.zero, Q.finite, Q.nonnegative, Q.integer, Q.extended_positive)


def queries():
    x = Symbol('x', real=True)
    y = Symbol('y', positive=True)
    z = Symbol('z')
    oo, zoo, nan = S.Infinity, S.ComplexInfinity, S.NaN
    special = (oo, -oo, zoo, nan)
    args = []
    for s in special:
        args.append(s)                                         # the special value itself
        args.append(Add(x, s, evaluate=False))                 # x + oo: nan at x = -oo
        args.append(Add(y, s, evaluate=False))
        args.append(Mul(S.Zero, s, evaluate=False))            # 0*oo
        args.append(Add(Mul(2, z, evaluate=False), s, evaluate=False))
        args.append(sin(Add(x, s, evaluate=False), evaluate=False))   # nested a level down
        args.append(Subs(Add(x, s, evaluate=False), x, 1))
        args.append(UnevaluatedExpr(s))
        args.append(Piecewise((s, x > 0), (S.One, True)))     # a branch value
    args.append(Subs(x, x, nan))
    args.append(Piecewise((S.One, Add(x, oo, evaluate=False) > 0)))   # a condition holding x + oo, no True branch
    args.append(Piecewise((S.One, Add(oo, -oo, evaluate=False) > 0), (S(2), True)))
    near = [Add(x, 1), y, Mul(2, z), Idx(Symbol('i', integer=True), (0, oo)), sin(x)]   # not opaque
    out = []
    for a in args + near:
        for f in (Abs, sign, exp, gamma, re, im):
            node = f(a, evaluate=False)
            out.extend((p(node), True) for p in PREDS)
            out.append((Q.positive(node), Q.positive(y)))
    for a in args[:12] + near:
        for node in (log(a, evaluate=False), sqrt(Abs(a, evaluate=False), evaluate=False)):
            out.extend((p(node), True) for p in PREDS[:5])
    return out
