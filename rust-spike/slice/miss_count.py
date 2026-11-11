"""Counts attribute misses on modules, whoever asks (D "adapters cost", issue 323; test-only).

handler_count.py sees an exception only when a Python frame handles it, in `_build_context` or `_consistent`
(sys.monitoring EXCEPTION_HANDLED, filtered by code object). A miss that Rust takes with pyo3's `getattr_opt` on Python 3.12
is raised in C (module_getattro builds the AttributeError) and cleared in Rust (pyo3-ffi 0.30.1 src/compat/py_3_13.rs:185-203:
PyObject_GetAttr, then PyErr_Clear on AttributeError). No Python frame handles it, so no event fires, and it never reaches those
two handlers anyway: adapters.rs py_class built and dropped one on every call for that reason without being counted (C1).
A module `__getattr__` (PEP 562) is called by module_getattro on every miss, from Rust or from Python, so this sees them.
It raises the same AttributeError a miss raises without it; it doesn't change what anything finds.
Rows: {(module, name): count}. Python's own misses (`hasattr(m, x)`, `getattr(m, x, None)`) are counted too, so read by name.
  `-p miss_count` in a suite run: one misses.PID.json per worker in SLICE_SUITE_OUT, written at exit.
"""
import json
import os
import sys
from collections import Counter

rows = Counter()
_done = set()


def install(modules=None, prefixes=("satassume",)):
    """Hooks each module (default: every loaded module under `prefixes`). A module's own `__getattr__` is kept and called after."""
    if modules is None:
        modules = [m for n, m in list(sys.modules.items()) if m is not None and n.split(".")[0] in prefixes]
    for m in modules:
        if m.__name__ in _done:
            continue
        _done.add(m.__name__)
        prev = m.__dict__.get("__getattr__")

        def ga(name, _m=m.__name__, _prev=prev):
            rows[(_m, name)] += 1
            if _prev is not None:
                return _prev(name)
            raise AttributeError(f"module {_m!r} has no attribute {name!r}")
        m.__getattr__ = ga


def snapshot():
    return {f"{m}:{n}": c for (m, n), c in sorted(rows.items())}


def pytest_configure(config):
    import atexit
    import satassume.theories.euf.euf_adapter, satassume.theories.lra.lra_adapter  # noqa: F401  (the adapters' modules)
    install()
    path = os.path.join(os.environ["SLICE_SUITE_OUT"], f"misses.{os.getpid()}.json")
    atexit.register(lambda: json.dump(snapshot(), open(path, "w"), indent=0))
