"""Transitional aliases: the flat module names of :mod:`satassume` before
the package move (``satassume.rules``, ``satassume.lra_adapter``,
``satassume.templates.core``, ...) as names of the moved modules.

Every module in this repository imports the new names
(``tests/test_layering.py`` checks the package, ``tests/``, ``harness/``,
``tools/`` and ``benchmarks/``).  The aliases exist for code written
against the flat layout that runs against a checkout after the move:
branches and scripts opened before the move, and an older checkout's
tools or tests run with this checkout on ``PYTHONPATH``.  Importing an old
name emits a :class:`DeprecationWarning` that names the new one.

End: this module, its ``install()`` call in ``satassume/__init__.py`` and
its test are deleted in the first PR after the class-level follow-up of
the package move has merged (PLAN.md, "Package move: remove the flat
aliases").  ``satassume.relations`` and ``satassume.scope`` did not move
and are not aliases.

Why a finder rather than one alias file per old name: a file
``satassume/rules.py`` that replaced itself in ``sys.modules`` would put
the flat layout back next to the packages, and it cannot handle a name
under an old package: ``import satassume.templates.core`` would find
``core.py`` through the aliased package's ``__path__`` and load the
templates a second time, under a second name.  :class:`AliasFinder`
therefore comes first on ``sys.meta_path``: for every import it does one
string prefix test and declines every name that is not in
:data:`ALIASES` (or under one).  For an old name its loader imports the
new module and hands back that very object, so the old name is the
*same* module (monkeypatching through an old path reaches the code that
runs, and no module is ever loaded twice).

This module imports nothing heavier than :mod:`importlib.machinery`
(``importlib.abc`` and ``importlib.util`` pull in ``importlib.resources``,
several milliseconds at every ``import satassume``); the finder and the
loader implement the import protocols without the ABC base classes.
"""
from __future__ import annotations

import importlib
import importlib.machinery
import sys
import warnings
from typing import Optional

#: old name (relative to ``satassume``) -> new name (relative to ``satassume``)
ALIASES = {
    "epoch": "state.epoch",
    "memos": "state.memos",
    "formula": "sat.formula",
    "solver": "sat.solver",
    "theory": "sat.theory",
    "rules": "knowledge.rules",
    "compile": "knowledge.compile",
    "extensions": "knowledge.extensions",
    "templates": "knowledge.templates",
    "transfer": "theories.transfer",
    "constfield": "theories.lra.constfield",
    "lra": "theories.lra.lra",
    "lra_adapter": "theories.lra.lra_adapter",
    "lra_bounds": "theories.lra.lra_bounds",
    "lra_cert": "theories.lra.lra_cert",
    "euf": "theories.euf.euf",
    "euf_adapter": "theories.euf.euf_adapter",
}

_PACKAGE = __name__.rpartition(".")[0]
_PREFIX = _PACKAGE + "."


def new_name(fullname: str) -> Optional[str]:
    """The module an old name ``fullname`` stands for, or None when it is
    not an old name (or a name under an old package)."""
    if not fullname.startswith(_PREFIX):
        return None
    head, dot, tail = fullname[len(_PREFIX):].partition(".")
    new = ALIASES.get(head)
    if new is None:
        return None
    return _PREFIX + new + dot + tail


class _AliasLoader:
    """Loads an old name as the new module object itself."""

    def __init__(self, target: str):
        self.target = target
        self.spec = None

    def create_module(self, spec):
        warnings.warn(f"{spec.name} is a transitional alias of {self.target}; "
                      f"import {self.target}", DeprecationWarning, stacklevel=2)
        module = importlib.import_module(self.target)
        self.spec = module.__spec__
        if hasattr(module, "__path__"):
            # a package: enter the old names of its submodules loaded so
            # far, so that importing one later does not set it as an
            # attribute of the package over a name the package binds to
            # something else (``templates.registry`` is the registry)
            old, new = spec.name + ".", self.target + "."
            for name, m in list(sys.modules.items()):
                if name.startswith(new) and m is not None:
                    sys.modules.setdefault(old + name[len(new):], m)
        return module

    def exec_module(self, module) -> None:
        # the import system has set ``__spec__`` to the alias's spec; put
        # back the module's own (``__package__`` must equal its parent)
        module.__spec__ = self.spec


class AliasFinder:
    """Finds the old names (:data:`ALIASES`).  A ``sys.meta_path`` finder
    (it needs no ``importlib.abc`` base class)."""

    def find_spec(self, fullname, path=None, target=None):
        new = new_name(fullname)
        if new is None:
            return None
        return importlib.machinery.ModuleSpec(fullname, _AliasLoader(new))


    def invalidate_caches(self) -> None:
        pass


def install() -> None:
    """Put :class:`AliasFinder` first on ``sys.meta_path`` (once)."""
    if not any(isinstance(f, AliasFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, AliasFinder())
