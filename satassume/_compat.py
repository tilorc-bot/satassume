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
string prefix test and declines every name outside the package, and
every name of the package that is neither an old name (:data:`ALIASES`,
or under one) nor a moved module or one in :data:`RENAMED`.  For an old
name its loader imports the new module and hands back that very object,
so the old name is the *same* module (monkeypatching through an old path
reaches the code that runs, and no module is ever loaded twice).

Old names are also entered in ``sys.modules`` when their module is
imported by its new name (``import satassume.sympy_api`` enters
``satassume.rules``, as it did before the move), and ``satassume.rules``
resolves as an attribute of the package (``satassume.__getattr__``).
Both make scripts that look a module up by its old name keep working
(``sys.modules.get("satassume.rules")``).  The DeprecationWarning comes
from an import of an old name that is not loaded yet and from an
attribute access ``satassume.<old>``; a plain ``sys.modules`` lookup
cannot warn.  For the same scripts, :data:`RENAMED` serves the names the
old modules had and the new ones do not (``memos.engine_memos``,
``euf_adapter._structural``, ``relations._optional``).

This module imports nothing heavier than :mod:`importlib.machinery`
(``importlib.abc`` and ``importlib.util`` pull in ``importlib.resources``,
several milliseconds at every ``import satassume``); the finder and the
loaders implement the import protocols without the ABC base classes.
"""
from __future__ import annotations

import importlib
import importlib.machinery
import sys
import warnings
from typing import Dict, Optional, Tuple

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

#: names a module had before the move that it no longer has: module
#: (relative to ``satassume``) -> {old attribute: (module, attribute) it
#: is now}; served, with a DeprecationWarning, by a module ``__getattr__``
#: that :class:`AliasFinder` adds when the module is imported
RENAMED: Dict[str, Dict[str, Tuple[str, str]]] = {
    "state.memos": {"ENGINE_MEMOS": ("engine", "ENGINE_MEMOS"),
                    "engine_memos": ("engine", "engine_memos")},
    "theories.euf.euf_adapter": {"_structural": ("theories.euf.euf_adapter", "structural")},
    # no public replacement (``relations.default_specs`` inlines it)
    "relations": {"_optional": ("_compat", "_optional")},
}

_PACKAGE = __name__.rpartition(".")[0]
_PREFIX = _PACKAGE + "."
#: new name (relative) -> old name (relative), for :func:`old_name`
_OLD = {new: old for old, new in ALIASES.items()}


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


def old_name(fullname: str) -> Optional[str]:
    """The old name of the moved module ``fullname`` (or of a module under
    a moved package), or None."""
    if not fullname.startswith(_PREFIX):
        return None
    rel = fullname[len(_PREFIX):]
    head, tail = rel, ""
    while True:
        old = _OLD.get(head)
        if old is not None:
            return _PREFIX + old + tail
        head, dot, last = head.rpartition(".")
        if not dot:
            return None
        tail = "." + last + tail


def _deprecated(what: str, new: str, stacklevel: int) -> None:
    warnings.warn(f"{what} is a transitional alias of {new}; use {new}",
                  DeprecationWarning, stacklevel=stacklevel + 1)


def package_getattr(name: str):
    """``satassume.<name>`` for an old module name (the package's
    ``__getattr__``): the moved module, imported if needed."""
    new = ALIASES.get(name)
    if new is None:
        raise AttributeError(f"module {_PACKAGE!r} has no attribute {name!r}")
    _deprecated(_PREFIX + name, _PREFIX + new, stacklevel=3)
    module = importlib.import_module(_PREFIX + new)
    setattr(sys.modules[_PACKAGE], name, module)
    return module


def _optional(module: str, attr: str):
    """``module.attr`` if ``module`` exists, else None; a broken module
    raises (``relations._optional`` before the move)."""
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        if e.name == module:
            return None
        raise
    return getattr(mod, attr)


def _add_renamed(module, names: Dict[str, Tuple[str, str]]) -> None:
    """Give ``module`` a ``__getattr__`` that serves ``names`` (keeping a
    ``__getattr__`` the module defines itself)."""
    own = module.__dict__.get("__getattr__")

    def __getattr__(name):
        target = names.get(name)
        if target is not None:
            where = _PREFIX + target[0]
            if target[0] == "_compat":
                warnings.warn(f"{module.__name__}.{name} is deprecated and will be removed",
                              DeprecationWarning, stacklevel=2)
            else:
                _deprecated(f"{module.__name__}.{name}", f"{where}.{target[1]}", stacklevel=2)
            return getattr(importlib.import_module(where), target[1])
        if own is not None:
            return own(name)
        raise AttributeError(f"module {module.__name__!r} has no attribute {name!r}")

    module.__getattr__ = __getattr__


class _AliasLoader:
    """Loads an old name as the new module object itself."""

    def __init__(self, target: str):
        self.target = target
        self.spec = None

    def create_module(self, spec):
        _deprecated(spec.name, self.target, stacklevel=2)
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


class _MovedLoader:
    """Wraps the loader of a moved module (or of one in :data:`RENAMED`)
    for its first load: after the module has run, it enters the old name
    in ``sys.modules`` and adds the renamed names.  The module keeps its
    own loader (``__loader__`` and ``__spec__.loader``)."""

    def __init__(self, loader, old: Optional[str], renamed):
        self.loader, self.old, self.renamed = loader, old, renamed

    def __getattr__(self, name):          # get_source, get_resource_reader, ...
        return getattr(self.loader, name)

    def create_module(self, spec):
        return self.loader.create_module(spec)

    def exec_module(self, module) -> None:
        spec = module.__spec__
        if spec is not None and spec.loader is self:
            spec.loader = self.loader
        if module.__dict__.get("__loader__") is self:
            module.__loader__ = self.loader
        self.loader.exec_module(module)
        if self.old is not None:
            sys.modules.setdefault(self.old, module)
        if self.renamed:
            _add_renamed(module, self.renamed)


class AliasFinder:
    """Finds the old names (:data:`ALIASES`), and wraps the loader of the
    moved modules (:class:`_MovedLoader`).  A ``sys.meta_path`` finder
    (it needs no ``importlib.abc`` base class)."""

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_PREFIX):
            return None
        new = new_name(fullname)
        if new is not None:
            return importlib.machinery.ModuleSpec(fullname, _AliasLoader(new))
        old = old_name(fullname)
        renamed = RENAMED.get(fullname[len(_PREFIX):])
        if old is None and renamed is None:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(fullname, path, target)
            if spec is not None:
                break
        else:
            return None
        if spec.loader is not None and hasattr(spec.loader, "exec_module"):
            spec.loader = _MovedLoader(spec.loader, old, renamed)
        return spec

    def invalidate_caches(self) -> None:
        pass


def install() -> None:
    """Put :class:`AliasFinder` first on ``sys.meta_path`` (once)."""
    if not any(isinstance(f, AliasFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, AliasFinder())
