"""Two-order twins (item 4e; sa-port-250's twin and two-order harnesses, results/before-pr-reads.md on audit/before-pr-reads).

    two_order.py py|rust ORDER

The *twin* of a query is an equal query in which every node, symbol and function class is a new object per occurrence
(built after `clear_cache()`; asserted `==` with an equal hash). One process per call, a new `Engine` per ask, the backend
installed as live.py does. ORDER: `orig` (the originals only), `twin` (the twins only), `orig-first` (each original, then
its twin), `twin-first` (each twin, then its original). Prints one JSON line: answers by query id and side.

The terms are the harness's with two equal arguments (all 34 of base's 560 flips were such terms: `x**x`, `(x*y)**(x*y)`,
`Abs(x)**Abs(x)`, `(x + 1)**(x + 1)`, `exp(x)**exp(x)`, ...) under its 16 query forms. On base, wiring.py's 'same' shape
and Pow key compared arguments by identity, so `Pow(x1, x2)` with two equal symbols lost the `x**x` rule and whichever
object came first decided both orders; 17241af compares by `==` (rows_tpl.rs `same_term` the same).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def install(mode):
    if mode != 'rust':
        return
    import p_install
    p_install.install()
    import backend
    backend.install_euf()
    import term_live
    term_live.from_env()
    import lra_live
    lra_live.from_env()
    import session_live
    session_live.from_env()
    import knowledge_live
    knowledge_live.from_env()
    backend.install()


def main():
    mode, order = sys.argv[1], sys.argv[2]
    install(mode)
    from sympy import Abs, Basic, Function, Q, Symbol, exp, symbols
    from sympy.core.cache import clear_cache
    from sympy.core.function import AppliedUndef
    import satassume
    from satassume.sympy_api import ask

    x, y = symbols('x y')
    f = Function('f')
    terms = [lambda: x**x, lambda: (x*y)**(x*y), lambda: f(x)**f(x), lambda: Abs(x)**Abs(x), lambda: x**x + 1,
             lambda: x*x**x, lambda: (x + 1)**(x + 1), lambda: x**x*y**y, lambda: exp(x)**exp(x), lambda: x**x - y**y]
    forms = [lambda t: (Q.gt(t, 0), Q.positive(x) & Q.positive(y)),
             lambda t: (Q.positive(t), Q.gt(x, 0) & Q.gt(y, 0)),
             lambda t: (Q.ge(t, 0), Q.real(x) & Q.real(y)),
             lambda t: (Q.real(t), Q.gt(t, 1)),
             lambda t: (Q.lt(t, t + 1), Q.real(x) & Q.real(y)),
             lambda t: (Q.gt(t + 1, 0), Q.ge(x, 0) & Q.ge(y, 0)),
             lambda t: (Q.integer(t), Q.integer(x) & Q.gt(x, 0) & Q.integer(y) & Q.gt(y, 0)),
             lambda t: (Q.nonzero(t), Q.gt(t, 0)),
             lambda t: (Q.extended_positive(t), Q.extended_nonnegative(x) & Q.lt(x, y)),
             lambda t: (Q.positive(t), Q.gt(x, 1) & Q.gt(y, x)),
             lambda t: (Q.gt(t, 0), Q.gt(x, 0) & Q.eq(x, y)),
             lambda t: (Q.eq(t, y), Q.eq(x, 1) & Q.eq(y, 1)),
             lambda t: (Q.le(t, 0), Q.gt(x, 0) & Q.gt(y, 0) & Q.real(f(x))),
             lambda t: (Q.positive(t), (x > 0) & (y > 0)),
             lambda t: (Q.gt(2*t, t), Q.gt(x, 0) & Q.gt(y, 0)),
             lambda t: (Q.extended_positive(t), Q.extended_nonnegative(x) & Q.extended_nonnegative(y))]

    def twin(e):
        if not isinstance(e, Basic):
            return e
        if isinstance(e, Symbol):
            clear_cache()
            r = Symbol(e.name, **e._assumptions_orig)
        elif isinstance(e, AppliedUndef):
            args = [twin(a) for a in e.args]
            clear_cache()
            r = Function(e.func.__name__, **e.func._kwargs)(*args)
        elif not e.args or e.is_Atom:
            return e
        else:
            args = [twin(a) for a in e.args]
            clear_cache()
            r = e.func(*args)
        assert r == e and hash(r) == hash(e), (e, r)
        return r

    def ask1(q):
        try:
            return repr(ask(q[0], q[1], satassume.Engine()))
        except Exception as ex:
            return 'EXC ' + type(ex).__name__

    out = {}
    for ti, tb in enumerate(terms):
        for fi, fb in enumerate(forms):
            q = fb(tb())
            k = f't{ti}f{fi}'
            if order in ('orig', 'orig-first'):
                out[k + ':orig'] = ask1(q)
            if order != 'orig':
                out[k + ':twin'] = ask1((twin(q[0]), twin(q[1])))
            if order == 'twin-first':
                out[k + ':orig'] = ask1(q)
    print(json.dumps(dict(mode=mode, order=order, tree=satassume.__file__, answers=out)))


if __name__ == '__main__':
    main()
