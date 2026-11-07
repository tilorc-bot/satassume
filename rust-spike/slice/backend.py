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


class TransferTheory(sa_solver.TransferTheory):
    """The crate's transfer theory. A Python subclass so a class-level wrapper (`live.py`) can be set on it, and so
    `on_merge` is set to a bound method, as in Python's `__init__`."""

    def __init__(self, euf):
        self._attach()


def install_transfer():
    """Component 3 on Rust: `TransferTheory`, `EqualitySharing`, `transfer_wanted`. SLICE_TRANSFER=py keeps Python's, and
    =shadow runs both, comparing per hook (`transfer_shadow.py`). `relations.py` imports the theory at its call, so
    patching the module is enough; the other two are held by name in the modules below. Returns a function that undoes it."""
    import satassume.relations as relations
    import satassume.scope as scope
    import satassume.sat.theory as theory
    import satassume.theories.transfer as transfer
    saved = transfer.TransferTheory, transfer.transfer_wanted, relations.transfer_wanted, scope.transfer_wanted, \
        relations.EqualitySharing, theory.EqualitySharing
    mode = os.environ.get("SLICE_TRANSFER", "rust")
    if mode == "shadow":
        import transfer_shadow
        transfer_shadow.ShadowTransfer.rust_class = TransferTheory
        transfer.TransferTheory = transfer_shadow.ShadowTransfer
        transfer_shadow.ShadowSharing.rust_class = sa_solver.EqualitySharing
        transfer_shadow.rust_wanted[0] = sa_solver.transfer_wanted
        transfer.transfer_wanted = relations.transfer_wanted = scope.transfer_wanted = transfer_shadow.shadow_wanted
        relations.EqualitySharing = theory.EqualitySharing = transfer_shadow.ShadowSharing
    elif mode == "rust":
        transfer.TransferTheory = TransferTheory
    if mode == "rust":
        transfer.transfer_wanted = relations.transfer_wanted = scope.transfer_wanted = sa_solver.transfer_wanted
    if mode == "rust":
        relations.EqualitySharing = theory.EqualitySharing = sa_solver.EqualitySharing

    def undo():
        transfer.TransferTheory, transfer.transfer_wanted, relations.transfer_wanted, scope.transfer_wanted, \
            relations.EqualitySharing, theory.EqualitySharing = saved
    return undo


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
    """Make the engine's sessions and `ref.py` use the Rust solver, `EUFAdapter` the Rust EUF, and component 3, with the
    other theories as live callbacks into the unchanged Python. Returns a function that undoes it. `live.py --check plain`
    runs exactly this. Tests that build `satassume.sat.solver.Solver` themselves are left on Python."""
    import satassume.engine as engine
    import satassume.ref as ref
    saved = engine.Solver, ref.Solver
    engine.Solver = ref.Solver = make
    undo_euf = install_euf()
    undo_transfer = install_transfer()
    # SLICE_LRA=python keeps LRA on Python with the solver on Rust: step 4's arrangement, for comparison.
    undo_lra = None
    if os.environ.get("SLICE_LRA", "rust") == "rust":
        import lra_backend
        undo_lra = lra_backend.install()

    def undo():
        engine.Solver, ref.Solver = saved
        undo_transfer()
        undo_euf()
        if undo_lra is not None:
            undo_lra()
    return undo
