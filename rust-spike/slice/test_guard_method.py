"""The part 3 follow-up, item (4): session_live.py's guarded wrappers as `GuardMethod` (session_glue.rs), with no Python frame.

Each wrapper ran Python's method for a session with no core and the Rust entry otherwise. `GuardMethod` makes the same test
in Rust. The asks below run on Rust's sessions (no guarded wrapper's frame may run: sys.setprofile), and through
`satassume/ref.py`'s `ask_ref`, whose `_RefSession` has no core but builds real `Relations`, so each guarded `Relations`
method must take Python's path. Both sets of answers must equal the run with every def installed (SLICE_ENTRY_FRAME=py),
which is also the control that the profile sees the defs' frames.

Plant 619 `gm-guard-skip` gives a session with no core the Rust entry: `ask_ref`'s answers change (the check compares
answers with the defs' run, not the plant's flag).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _asks(ref=False):
    from sympy import Function, Q, symbols
    from satassume.engine import DictCache, Engine
    from satassume.ref import ask_ref
    from satassume.sympy_api import ask
    x, y, z = symbols('x y z')
    f = Function('f')
    qs = [(Q.positive(x + y), Q.positive(x) & Q.positive(y)), (Q.integer(x * y), Q.integer(x) & Q.integer(y)),
          (Q.positive(x), Q.gt(x, 1)), (Q.lt(x, y), Q.lt(x, z) & Q.lt(z, y)), (Q.eq(f(x), f(y)), Q.eq(x, y)),
          (Q.negative(x), Q.gt(x, 0)), (Q.nonzero(x), Q.ne(x, 0) | Q.gt(x, 2)), (Q.real(x + 1), Q.real(x)),
          (Q.gt(x + 1, y), Q.gt(x, y)), (Q.ne(f(x), f(y)), Q.ne(x, y))]
    eng = Engine(cache=DictCache())
    out = []
    for p, a in qs:
        try:
            out.append(repr(ask_ref(p, a) if ref else ask(p, a, engine=eng)))
        except KeyboardInterrupt:
            raise
        except BaseException as e:      # a wrong path may raise (TermFault is a BaseException); that is an answer too
            out.append(type(e).__name__)
    return out


def _lookups(v, bound, py):
    """OWED [128]: what reads `__module__` and `__qualname__` finds the method as it finds the Python method. inspect finds
    the module; pickle stores a function by reference (module, then qualname) and loads the class's attribute, so a
    method pickles to itself, where the Python method does: not a local function (`<locals>` in its qualname)."""
    import inspect
    import pickle
    bad = [[w, 'getmodule', getattr(inspect.getmodule(o), '__name__', None), py.__module__]
           for w, o in (('bound', bound), ('class', v)) if py is not None and inspect.getmodule(o) is not sys.modules[py.__module__]]
    if py is not None and '<locals>' not in py.__qualname__:
        try:
            back = pickle.loads(pickle.dumps(v))
        except Exception as e:      # noqa: BLE001  (the row says what failed)
            back = type(e).__name__
        if back is not v:
            bad.append(['class', 'pickle', repr(back)[:80], py.__qualname__])
    return bad


def _child():
    from test_relations_core import _rust
    _rust()
    import session_live as SL
    from satassume import engine, relations
    kinds = sorted({type(v).__name__ for cls in (engine.Session, relations.Relations) for v in vars(cls).values()
                    if type(v).__name__ in ('GuardMethod', 'function')})
    names = {k for k, v in vars(SL).items() if k.startswith(('_rel_', '_ses_')) and callable(v)} | {'f'}
    seen = []

    def prof(frame, event, arg):
        if event == 'call' and frame.f_code.co_filename == SL.__file__ and frame.f_code.co_name in names:
            seen.append(frame.f_code.co_name)
    sys.setprofile(prof)
    try:
        rust = _asks()
    finally:
        sys.setprofile(None)
    nocore = _asks(ref=True)
    # the planner's ruling (3) on 293's deviations: a bound GuardMethod is named as the Python method it stands for
    # (the class's method before the install, kept in PY_X),
    # as the bound method forwards to it
    looks, n = {}, 0
    for cls in (engine.Session, relations.Relations):
        for k, v in vars(cls).items():
            if type(v).__name__ != 'GuardMethod':
                continue
            n += 1
            saved = (SL.PY_REL,) if cls is relations.Relations else (SL.PY_DISC, SL.PY_LOOP, SL.PY_QUERY, SL.PY_GLUE)
            py = next((D[k] for D in saved if k in D), None)
            bound = v.__get__(object(), cls)
            bad = [[w, a, getattr(o, a), getattr(py, a, '?')] for w, o in (('bound', bound), ('class', v))
                   for a in ('__name__', '__qualname__', '__doc__', '__module__')
                   if py is None or getattr(o, a) != getattr(py, a)]
            bad += _lookups(v, bound, py)
            if bad:
                looks[cls.__name__ + '.' + k] = bad
    print(json.dumps(dict(kinds=kinds, rust=rust, nocore=nocore, frames=sorted(set(seen)), nframes=len(seen), looks=looks,
                          n_guard=n)))


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


def test_guarded_methods_have_no_frame_and_keep_pythons_path():
    got, defs = _run(), _run(frame='py')
    assert 'GuardMethod' in got['kinds'] and 'GuardMethod' not in defs['kinds'], (got['kinds'], defs['kinds'])
    assert got['rust'] == defs['rust'] and got['nocore'] == defs['nocore'], (got, defs)
    assert 'Error' not in ''.join(defs['nocore'] + defs['rust']) and len(set(defs['nocore'])) > 1, defs
    # the control: with the defs the profile sees their frames, so their absence here is a measurement
    assert {'_ses_ensure', '_rel_fresh', 'f'} <= set(defs['frames']), defs['frames']
    assert 'f' not in got['frames'] and not {'_rel_fresh', '_ses_ensure', '_ses_discover', '_ses_custom'} & set(got['frames']), got
    print('still frames:', got['frames'], got['nframes'], 'of', defs['nframes'])


def test_a_bound_guard_method_looks_like_the_python_method():
    got = _run()
    assert got['n_guard'] > 50 and got['looks'] == {}, (got['n_guard'], got['looks'])


def test_gm_guard_skip_plant_is_caught():
    got, defs = _run('gm-guard-skip'), _run(frame='py')
    assert got['nocore'] != defs['nocore'], (got['nocore'], defs['nocore'])


if __name__ == '__main__' and sys.argv[1:2] == ['child']:
    _child()
