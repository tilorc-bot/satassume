"""6i(c): rows_tpl.rs's direct core splits on args that used to send it to the kcl shells (knowledge_core_live.py), on the
loop workload (live.py's), under the shadow: every direct split is compared with Python's (`shadow:direct:NAME`), and
the answers with the pure-Python default's. Reached here: a Rational with no input id (`rows:ids:number`), a term Python
already learned (`rows:ids:derived`) and a Pow Python built (`rows:pow_bound:args`, loop's three `x**2`-shaped Pows, each
no split on both sides, so plant rows-pow-bound-args-swap is void on the workloads and doesn't move this first test). The
plant's direct check is the extension-derived `1/(3*x + 2)` below, a Pow with no input id whose base splits."""
import knowledge_common_live as KC
import knowledge_live as K
from harness.state import reset_module_state
from live import load
from satassume import engine as E_, sympy_api


def fresh():
    reset_module_state()
    sympy_api.set_default_engine(E_.Engine())


def counts():
    c = KC.COMMON[0]
    return dict(c.counts()) if c is not None else {}


def test_loop_derived_args_direct_and_shadowed():
    pairs = load('loop')
    fresh()
    plain = [sympy_api.ask(p, a) for p, a in pairs]
    undo = K.install(shadow=True)
    try:
        K.COUNTS.clear()
        c0 = counts()
        fresh()
        got = [sympy_api.ask(p, a) for p, a in pairs]
        c1 = counts()
        kc = dict(K.COUNTS)
    finally:
        undo()
        K.COUNTS.clear()
    d = {k: c1.get(k, 0) - c0.get(k, 0) for k in c1}
    assert got == plain
    for k in ('rows:ids:number', 'rows:pow_bound:args'):
        assert d.get(k, 0) > 0, (k, sorted(x for x in d if x.startswith(('rows:ids', 'rows:pow', 'scaffold'))))
    for k in ('_half_split', '_bound_split', '_imag_split', '_pow_bound_templates'):
        assert d.get('rows:python:' + k, 0) == 0, (k, d.get('rows:python:' + k))
    assert kc.get('shadow:mismatch', 0) == 0, K.MISMATCHES[-3:]
    assert kc.get('fault', 0) == 0


def _derived_pow_run(plant=None):
    """Plant 372's direct check: a vocabulary extension (as loop_wl.py's `_pow` builds `b**2`) builds `1/(3*x + 2)` from
    `(3*x + 2)**n`, a Pow with no input id whose base splits (`(c0 + c1*u)**-1`), so `_pow_bound_templates` takes it by
    its args (`rows:pow_bound:args`), and the shadow compares Rust's split with Python's."""
    from satassume import Implies, P
    from satassume.knowledge import extensions as X
    from sympy import Add, Mul, Pow, Q, S, Symbol
    x, n = Symbol('x', integer=True), Symbol('n', integer=True)
    b = Add(S(2), Mul(S(3), x))

    def _pow(node):
        return [Implies(P('integer', Pow(node.args[0], -1)), P('integer', node))]
    seq = [(Q.integer(b**n), Q.positive(x) & Q.negative(n)), (Q.integer(b**n), True), (Q.integer(b**n), Q.positive(x))]
    snap = X.extensions.snapshot()
    X.register('integer', Pow)(_pow)
    old = K.PLANT[0]
    try:
        fresh()
        plain = [sympy_api.ask(p, a) for p, a in seq]
        K.PLANT[0] = plant
        undo = K.install(shadow=True)
        try:
            K.COUNTS.clear()
            del K.MISMATCHES[:]
            c0 = counts()
            fresh()
            got = [sympy_api.ask(p, a) for p, a in seq]
            c1 = counts()
            kc = dict(K.COUNTS)
            mism = list(K.MISMATCHES)
        finally:
            undo()
            K.COUNTS.clear()
    finally:
        K.PLANT[0] = old
        X.extensions.restore(snap)
    d = {k: c1.get(k, 0) - c0.get(k, 0) for k in c1}
    return plain, got, d, kc, mism


def test_extension_derived_pow_bound_by_args():
    plain, got, d, kc, mism = _derived_pow_run()
    assert got == plain
    assert d.get('rows:pow_bound:args', 0) > 0
    assert d.get('rows:python:_pow_bound_templates', 0) == 0
    assert kc.get('shadow:mismatch', 0) == 0, mism[-3:]
    assert kc.get('fault', 0) == 0


def test_pow_bound_args_swap_plant_is_caught():
    """rows-pow-bound-args-swap (372) is void on the workloads (loop's derived Pows are `b**2`, no split either way);
    on the extension-derived `1/(3*x + 2)` it fires and the shadow catches it."""
    _, _, d, kc, mism = _derived_pow_run('rows-pow-bound-args-swap')
    assert d.get('plant:fired', 0) > 0
    assert kc.get('shadow:mismatch', 0) > 0
    assert any("'1/(3*x + 2)'" in repr(m) for m in mism), mism[-3:]
