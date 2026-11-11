"""The part 3 follow-up, C7 (group-d-cause.md, "per-ask entry frame"): an Engine entry method is one Rust call.

session_live installs each 5c10d entry (`_ENTRY_METHODS`: `ask`, `is_`, the record methods, ...) as an `EntMethod`
(session_glue.rs), which binds the pyfunction as Python binds a `def`, so a call runs no Python frame. Before, each was a
`def f(self, *a, **k)`, one Python frame per entry call; `SLICE_ENTRY_FRAME=py` puts it back, and is the control that the
profile below sees a frame when there is one.

Plant 618 `ent-method-first-self` binds every entry method to the first engine it was read from: a second engine's record
calls then count on the first. The check reads each engine's own `stats`, so it doesn't read the plant's flag.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _frames(fn):
    """Python 'call' events (a Python frame starting) while `fn()` runs."""
    calls = []

    def prof(frame, event, arg):
        if event == 'call' and frame.f_code is not fn.__code__:
            calls.append(frame.f_code.co_name)
    sys.setprofile(prof)
    try:
        fn()
    finally:
        sys.setprofile(None)
    return calls


def _child():
    from test_relations_core import _rust
    _rust()
    from sympy import Q, Symbol
    from satassume.engine import DictCache, Engine
    from satassume.sympy_api import ask
    out = {'kind': type(Engine.__dict__['ask']).__name__}
    e1 = Engine(cache=DictCache(), uninterpreted='none')
    e2 = Engine(cache=DictCache(), uninterpreted='none')
    e1._record_cache_hit()                        # the first engine any entry method is read from
    h1, h2 = e1.stats['cache_hits'], e2.stats['cache_hits']
    for _ in range(3):
        e2._record_cache_hit()
    Engine._record_cache_hit(e2)                  # called on the class, the instance first, as a `def` is
    out['hits'] = [e1.stats['cache_hits'] - h1, e2.stats['cache_hits'] - h2]
    out['frames'] = _frames(lambda: (e2._clear_budget_flag(), e2._record_cache_hit(), e2._check_version()))
    x = Symbol('x')
    out['ask'] = [ask(Q.positive(x), Q.positive(x), engine=e2), ask(Q.negative(x), Q.positive(x), engine=e1),
                  ask(Q.positive(x + 1), Q.positive(x), engine=e2)]
    out['name'] = [Engine.ask.__name__, e2.ask.__name__, e2.ask.__self__ is e2]
    # the planner's ruling (3): every bound entry method is named as the Python method it replaced
    import session_live
    attrs = ('__name__', '__qualname__', '__doc__', '__module__')
    out['looks'] = {n: [[a, getattr(getattr(e2, n), a), getattr(py, a)] for a in attrs
                        if getattr(getattr(e2, n), a) != getattr(py, a)]
                    for n, py in session_live.PY_ENTRY.items() if n in session_live._ENTRY_METHODS}
    out['n_methods'] = len(out['looks'])
    # the control: an EntMethod made without the class and module binds the pyfunction, which names the bound method
    import sa_solver
    bare = sa_solver.EntMethod(sa_solver.ent_ask, 'ask', 'Engine.ask', Engine.ask.__doc__)
    out['bare_name'] = bare.__get__(e2, Engine).__name__
    print(json.dumps(out))


def _run(plant=None, frame=None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([HERE, os.environ.get('PYTHONPATH', '')]))
    env.pop('SLICE_SESSION_PLANT', None)
    env.pop('SLICE_ENTRY_FRAME', None)
    if plant:
        env['SLICE_SESSION_PLANT'] = plant
    if frame:
        env['SLICE_ENTRY_FRAME'] = frame
    r = subprocess.run([sys.executable, os.path.abspath(__file__), 'child'], env=env, capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_an_entry_method_is_one_rust_call():
    got = _run()
    assert got['kind'] == 'EntMethod', got
    assert got['frames'] == [], got
    assert got['hits'] == [0, 4], got
    assert got['ask'] == [True, False, True], got
    # the class's attribute and the bound method are named as the method
    assert got['name'] == ['ask', 'ask', True], got


def test_a_bound_entry_method_looks_like_the_python_method():
    """The planner's ruling (3) on 293's deviations: `__name__`, `__qualname__`, `__doc__` (and `__module__`) of each bound
    entry method are the Python method's. The control: bound to the bare pyfunction, the name is the Rust entry's."""
    got = _run()
    assert got['n_methods'] > 10, got
    assert {n: d for n, d in got['looks'].items() if d} == {}, got['looks']
    assert got['bare_name'] == 'ent_ask', got


def test_the_python_def_is_a_frame_per_call():
    """The control: the profile sees the `def`'s frames when it is installed, so the empty list above is a measurement."""
    got = _run(frame='py')
    assert got['kind'] == 'function', got
    assert got['frames'].count('f') == 3, got
    assert got['hits'] == [0, 4] and got['ask'] == [True, False, True], got


def test_ent_method_first_self_plant_is_caught():
    got = _run('ent-method-first-self')
    assert got['hits'] != [0, 4], got


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child()
