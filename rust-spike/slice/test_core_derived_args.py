"""6i(c): rows_tpl.rs's direct core splits on args that used to send it to the kcl shells (knowledge_core_live.py), on the
loop workload (live.py's), under the shadow: every direct split is compared with Python's (`shadow:direct:NAME`), and
the answers with the pure-Python default's. Reached here: a Rational with no input id (`rows:ids:number`), a term Python
already learned (`rows:ids:derived`) and a Pow Python built (`rows:pow_bound:args`, loop's three `x**2`-shaped Pows, each
no split on both sides, so plant rows-pow-bound-args-swap is void on the workloads and this test is that guard's check)."""
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
