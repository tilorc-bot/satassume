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


class EUFTheory(sa_solver.EUFTheory):
    """The crate's EUF. A Python subclass only so a class-level wrapper (`live.py`) can be set on it."""


def install_euf():
    """Make `EUFAdapter` build the Rust EUF. SLICE_EUF=py keeps Python's, to compare. Returns a function that undoes it."""
    import satassume.theories.euf.euf as euf
    import satassume.theories.euf.euf_adapter as adapter
    saved = euf.EUFTheory, adapter.EUFTheory
    if os.environ.get("SLICE_EUF") != "py":
        euf.EUFTheory = adapter.EUFTheory = EUFTheory

    def undo():
        euf.EUFTheory, adapter.EUFTheory = saved
    return undo


def install():
    """Make the engine's sessions and `ref.py` use the Rust solver and `EUFAdapter` the Rust EUF, with the other theories
    as live callbacks into the unchanged Python. Returns a function that undoes it. `live.py --check plain` runs exactly
    this. Tests that build `satassume.sat.solver.Solver` themselves are left on Python."""
    import satassume.engine as engine
    import satassume.ref as ref
    saved = engine.Solver, ref.Solver
    engine.Solver = ref.Solver = make
    undo_euf = install_euf()
    # SLICE_LRA=python keeps LRA on Python with the solver on Rust: step 4's arrangement, for comparison.
    undo_lra = None
    if os.environ.get("SLICE_LRA", "rust") == "rust":
        import lra_backend
        undo_lra = lra_backend.install()

    def undo():
        engine.Solver, ref.Solver = saved
        undo_euf()
        if undo_lra is not None:
            undo_lra()
    return undo
