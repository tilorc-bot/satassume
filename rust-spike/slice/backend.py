"""The Rust solver as a backend, switched by monkeypatch. Pure Python stays the default and the reference: nothing
here runs unless a script calls `install()`, and no satassume source changes.

Build the module first: `sh rust-spike/slice/build_solver.sh` (it lands next to this file as `sa_solver.so`).

`created` and `dropped` count solvers made through `make()`. They live here, not in the crate, which has no static.
"""
import os
import sys
import weakref

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sa_solver  # noqa: E402

RustSolver = sa_solver.Solver
created = 0
dropped = 0


def _gone():
    global dropped
    dropped += 1


def make():
    """A Rust solver that counts towards `created` and, once Python drops it, `dropped`."""
    global created
    s = RustSolver()
    created += 1
    weakref.finalize(s, _gone).atexit = False
    return s


def install():
    """Make the engine's sessions and `ref.py` use the Rust solver. Returns a function that undoes it. Step 3 turns
    this on; tests that build `satassume.sat.solver.Solver` themselves are left on Python."""
    import satassume.engine as engine
    import satassume.ref as ref
    saved = engine.Solver, ref.Solver
    engine.Solver = ref.Solver = make

    def undo():
        engine.Solver, ref.Solver = saved
    return undo
