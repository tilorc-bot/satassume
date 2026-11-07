"""harness_rust.py rust|python OUT ARGS...: `python -m harness ARGS` with the solver patched as in rust_plugin.py.
OUT gets the harness's output; the last line is the count of solvers made, so a run that never used Rust shows it.
Only modes that stay in one process mean anything here: --confirm and `hashseed` start subprocesses without the patch."""
import contextlib
import json
import os
import runpy
import sys

backend, out = sys.argv[1:3]
os.environ["SLICE_SUITE_BACKEND"] = backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rust_plugin  # noqa: E402
sys.argv = ["harness"] + sys.argv[3:]
rc = 0
with open(out, "w") as f, contextlib.redirect_stdout(f):
    try:
        runpy.run_module("harness", run_name="__main__")
    except SystemExit as e:
        rc = e.code
    print(json.dumps(dict(backend=backend, rc=rc, **rust_plugin.counts)))
