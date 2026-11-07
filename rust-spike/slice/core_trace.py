"""core_trace.py: count calls into knowledge/templates/core.py, split into import time and after import (step 6e, issue 323).

sys.monitoring PY_START: global events while core imports (so any call its module body makes is seen), then local events on
core's own code objects only, so the rest of the run pays nothing. Nested code (lambdas, `gen`) counts under its qualname.
Use: `import core_trace; core_trace.start()` before satassume imports, `core_trace.dump(path)` at the end; or
`python core_trace.py WL OUT` for one workload (dev, fuzz) on the default Python engine; or `pytest -p core_trace`
with CORE_TRACE_OUT=dir (one file per process).
"""
import collections, json, os, sys
M = sys.monitoring
TOOL = 4
CORE = os.path.join('knowledge', 'templates', 'core.py')
COUNTS = {'import': collections.Counter(), 'runtime': collections.Counter()}
_phase = ['import']
_started = [False]


def _name(code):
    return f'{code.co_qualname}:{code.co_firstlineno}'


def _on_start(code, offset):
    if code.co_filename.endswith(CORE):
        COUNTS[_phase[0]][_name(code)] += 1
        return None
    return M.DISABLE if _phase[0] == 'runtime' else None


def _codes(c):
    yield c
    for k in c.co_consts:
        if hasattr(k, 'co_code'):
            yield from _codes(k)


def start():
    if _started[0]:
        return
    _started[0] = True
    M.use_tool_id(TOOL, 'core_trace')
    M.register_callback(TOOL, M.events.PY_START, _on_start)
    M.set_events(TOOL, M.events.PY_START)
    import satassume.knowledge.templates.core as core
    M.set_events(TOOL, 0)
    _phase[0] = 'runtime'
    seen = set()
    for v in list(vars(core).values()):
        c = getattr(v, '__code__', None)
        if c is not None and c.co_filename.endswith(CORE):
            for k in _codes(c):
                if id(k) not in seen:
                    seen.add(id(k))
                    M.set_local_events(TOOL, k, M.events.PY_START)
    return core




def dump(path):
    out = {k: dict(sorted(v.items())) for k, v in COUNTS.items() if isinstance(v, collections.Counter)}
    with open(path, 'w') as fh:
        json.dump(out, fh, indent=1)


# pytest plugin
def pytest_configure(config):
    start()


def pytest_unconfigure(config):
    d = os.environ.get('CORE_TRACE_OUT')
    if d:
        os.makedirs(d, exist_ok=True)
        dump(os.path.join(d, f'trace-{os.environ.get("PYTEST_XDIST_WORKER", "main")}-{os.getpid()}.json'))


if __name__ == '__main__':
    wl, out = sys.argv[1:3]
    start()
    from harness.state import reset_module_state
    from satassume import sympy_api
    from evalbench.common import workload
    if wl == 'fuzz':
        from evalbench.fuzz import queries
        pairs = queries(424242)
    else:
        pairs = workload(wl)
    for p, a in pairs:
        reset_module_state(sympy_cache=False)
        try:
            sympy_api.ask(p, a)
        except Exception:
            pass
    dump(out)
