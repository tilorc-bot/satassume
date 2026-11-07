"""Component 3's `P` on Rust. `satassume/__init__` imports everything, and many modules hold `P` by name, so patching after
import would miss them. This swaps it as `satassume.sat.formula` finishes executing, before any other module can read it,
with no source change. It has to run before anything imports satassume, so each driver calls `install()` first. Nothing in
formula.py builds a `P` at module level, so no Python `P` outlives the swap. SLICE_P=py keeps Python's."""
import importlib.abc
import importlib.machinery
import os
import sys

NAME = "satassume.sat.formula"
state = {"installed": False, "swapped": False}


class _Loader(importlib.abc.Loader):
    def __init__(self, inner):
        self.inner = inner

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module):
        import sa_solver
        self.inner.exec_module(module)
        module.P = sa_solver.P
        state["swapped"] = True


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name != NAME:
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if spec is not None:
            spec.loader = _Loader(spec.loader)
        return spec


def install():
    """Refuses if satassume got there first: half the modules would hold Python's `P`."""
    if os.environ.get("SLICE_P") == "py" or state["installed"]:
        return
    if NAME in sys.modules:
        raise RuntimeError("p_install.install() after satassume.sat.formula was imported")
    state["installed"] = True
    sys.meta_path.insert(0, _Finder())
