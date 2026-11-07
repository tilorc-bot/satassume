"""f6_trace.py: count calls into step 6f's six template modules (functions, special, rootof, nodes, physics, stats), split into
import time and after import (step 6f, issue 323). Generalizes core_trace.py.

sys.monitoring PY_START, global: a code object outside the six files is disabled at its first call, so the run pays once per code
object. A call counts as `import` when a `<module>` frame of any of the six files, or of wiring.py, is on the stack (lazy
modules import mid-run), else as `runtime`. Nested code (templates, `build`, lambdas) counts under its qualname. The outer
factories (`_unary`, `nary`, `_pi_trig`, `_exp_ipi`, `_cosh_shift`, `_genocchi_half`, `_in_unit_interval_units`) run at runtime
too, once per class per process when wiring first builds that class's template: their counts are numbers of classes.
Use: `python f6_trace.py WL OUT` (dev, fuzz, value, rootof, core, f6) on the default Python engine; or `pytest -p f6_trace`
with F6_TRACE_OUT=dir (one file per process).
"""
import collections, json, os, sys

M = sys.monitoring
TOOL = 4
D = os.path.join('knowledge', 'templates', '')
FILES = tuple(D + m + '.py' for m in ('functions', 'special', 'rootof', 'nodes', 'physics', 'stats'))
SETUP = (D + 'wiring.py',)
COUNTS = {'import': collections.Counter(), 'runtime': collections.Counter()}
_started = [False]


def _phase():
    f = sys._getframe(2)
    while f is not None:
        c = f.f_code
        if c.co_name == '<module>' and c.co_filename.endswith(FILES + SETUP):
            return 'import'
        f = f.f_back
    return 'runtime'


def _on_start(code, offset):
    fn = code.co_filename
    if fn.endswith(FILES):
        COUNTS[_phase()][f'{fn.rsplit(os.sep, 1)[1][:-3]}.{code.co_qualname}:{code.co_firstlineno}'] += 1
        return None
    return M.DISABLE


def start():
    if _started[0]:
        return
    _started[0] = True
    M.use_tool_id(TOOL, 'f6_trace')
    M.register_callback(TOOL, M.events.PY_START, _on_start)
    M.set_events(TOOL, M.events.PY_START)


def dump(path):
    with open(path, 'w') as fh:
        json.dump({k: dict(sorted(v.items())) for k, v in COUNTS.items()}, fh, indent=1)


def pytest_configure(config):
    start()


def pytest_unconfigure(config):
    d = os.environ.get('F6_TRACE_OUT')
    if d:
        os.makedirs(d, exist_ok=True)
        dump(os.path.join(d, f'trace-{os.environ.get("PYTEST_XDIST_WORKER", "main")}-{os.getpid()}.json'))


if __name__ == '__main__':
    wl, out = sys.argv[1:3]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    start()
    from harness.state import reset_module_state
    from satassume import sympy_api
    if wl == 'fuzz':
        from evalbench.fuzz import queries
        pairs = queries(424242)
    elif wl in ('value', 'rootof', 'core', 'f6'):
        import importlib
        pairs = importlib.import_module(f'knowledge_{wl}_wl').queries()
    else:
        from evalbench.common import workload
        pairs = workload(wl)
    for p, a in pairs:
        reset_module_state(sympy_cache=False)
        try:
            sympy_api.ask(p, a)
        except Exception:
            pass
    dump(out)
