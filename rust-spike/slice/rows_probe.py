"""rows_probe.py: calls through templates/_rows.py's `generator` and `constant_value` (state part 3, the _rows ruling).

Planner's ruling (~06:47 10 Nov, addenda/sa-port-rows-stale-ruling.txt): count the calls on the seven workloads and the
full suite, plant a wrong-value change per name, and remove the binding install() can't replace if nothing calls it.

Counters (state part 3's range 550-579), by the name a caller reached:
  550 rows:generator        a call of `_rows.generator` (the name as `_rows` gives it; `_rows.rules` reaches it too)
  551 rows:constant_value   a call of `_rows.constant_value`
  552 rows:rules            a call of `_rows.rules`
  553 rows:py_generator     PY_START of Python's `_rows_runtime.generator`, by any path (after the install: not Rust's)
  554 rows:py_constant      PY_START of Python's `_rows_runtime.constant_value`, by any path
Plants (state part 3's range 420-449), wrong values, by SLICE_SESSION_PLANT:
  424 rows-gen-wrong        `_rows.generator` drops the first rule of every spec
  425 rows-cv-wrong         `_rows.constant_value` gives the value at c + 1
  426 rows-gen-slot-wrong   the install's slot `wiring.generator` drops the first rule of every spec
  427 rows-cv-slot-wrong    the install's slot `wiring.constant_value` gives the value at c + 1
424/425 sit on `_rows`' name; 426/427 on the slot install() fills, so a `_rows` name that resolves at call time sees them
and a binding held from before the install doesn't.

Use: `pytest -p rows_probe ...` with ROWS_PROBE_OUT=DIR (rowsprobe.PID.jsonl, one line per test with any count), or
`rows_probe.py OUT.json [live.py args...]` for one live.py pass.
"""
import json
import os
import sys
from collections import Counter

COUNTS = Counter()
PLANT = os.environ.get('SLICE_SESSION_PLANT', '')
_done = []


def _drop_first(specs):
    return tuple((n, tuple(rs)[1:]) for n, rs in specs)


def _wrong_gen(f):
    def g(name, arity, terms, specs, module, *rest):
        return f(name, arity, terms, _drop_first(specs), module, *rest)
    return g


def _wrong_cv(f):
    return lambda text, c: f(text, c + 1)


def _counted(key, f):
    def w(*a, **k):
        COUNTS[key] += 1
        return f(*a, **k)
    w.__wrapped__ = f
    return w


_SLOT = {'rows-gen-slot-wrong': ('generator', _wrong_gen), 'rows-cv-slot-wrong': ('constant_value', _wrong_cv)}


def _plant_slot():
    """Plant 426/427 on `wiring`'s slot, now and at every later assignment (the installs fill it, undo empties it)."""
    if PLANT not in _SLOT:
        return
    import types
    from satassume.knowledge.templates import wiring
    name, wrong = _SLOT[PLANT]

    class Planted(types.ModuleType):
        def __setattr__(self, k, v):
            super().__setattr__(k, wrong(v) if k == name else v)
    wiring.__class__ = Planted
    setattr(wiring, name, vars(wiring)[name])


def wrap():
    """Count (and plant) on `_rows`' names; the slot plants go on after the install (`installed`)."""
    if _done:
        return
    _done.append(1)
    from satassume.knowledge.templates import _rows, _rows_runtime
    held = vars(_rows)
    for name, key, wrong in (('generator', 'rows:generator', _wrong_gen), ('constant_value', 'rows:constant_value', _wrong_cv)):
        if name in held:          # a binding in _rows' namespace
            f = held[name]
            if PLANT == {'generator': 'rows-gen-wrong', 'constant_value': 'rows-cv-wrong'}[name]:
                f = wrong(f)
            setattr(_rows, name, _counted(key, f))
        # else: resolved at call time (no binding to count); 553/554 still count Python's implementation by any path
    _rows.rules = _counted('rows:rules', _rows.rules)
    mon = sys.monitoring
    tool = 5      # handler_count holds 4
    mon.use_tool_id(tool, 'rows_probe')
    codes = {_rows_runtime.generator.__code__: 'rows:py_generator', _rows_runtime.constant_value.__code__: 'rows:py_constant'}

    def start(code, offset):
        k = codes.get(code)
        if k is None:
            return mon.DISABLE
        COUNTS[k] += 1
    mon.register_callback(tool, mon.events.PY_START, start)
    mon.set_events(tool, mon.events.PY_START)


def report():
    return {k: v for k, v in sorted(COUNTS.items())}


# ---- pytest plugin
_out = []


def pytest_configure(config):
    wrap()
    _plant_slot()


try:
    import pytest

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(item, nextitem):
        COUNTS.clear()
        yield
        d = os.environ.get('ROWS_PROBE_OUT')
        if d and any(COUNTS.values()):
            with open(os.path.join(d, f'rowsprobe.{os.getpid()}.jsonl'), 'a') as fh:
                fh.write(json.dumps({'id': item.nodeid, 'counts': report()}) + '\n')
except ImportError:
    pass


# ---- one live.py pass
def main():
    out, rest = sys.argv[1], sys.argv[2:]
    if 'rust' in rest[1:2] and os.environ.get('SLICE_TRANSFER') != 'py':    # live.py's own first step, idempotent
        import p_install
        p_install.install()
    wrap()
    _plant_slot()
    sys.argv = ['live.py'] + rest
    import runpy
    try:
        runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live.py'), run_name='__main__')
    except SystemExit:
        pass
    with open(out, 'w') as fh:
        json.dump({'argv': rest, 'counts': report(), 'plant': PLANT}, fh, indent=1)


if __name__ == '__main__':
    main()
