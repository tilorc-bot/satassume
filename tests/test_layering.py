"""The module layering of :mod:`satassume`, where SymPy is imported, and
the transitional old-name aliases.

Layers, bottom to top: ``state`` < ``sat`` < ``knowledge`` < ``theories`` <
``relations`` < ``scope`` < ``engine`` < ``sympy_api`` < ``ref`` (< the
package ``__init__``, the public API, and ``_compat``, which only it
imports).  A module may depend on its own layer and the layers below.
Inside ``theories`` each theory (``lra/``, ``euf/``, ``transfer``) imports
only itself, so a new theory package needs no entry here.

A dependency is every import, at module level or inside a function (lazy
imports count) or under ``TYPE_CHECKING``, every string that names a
``satassume`` module (passed to ``importlib`` or kept for later lookup in
``sys.modules``), and ``__name__ + ".x"`` names.

SymPy (and mpmath) may be imported at module level only by the modules
that read SymPy objects as their job (:data:`SYMPY_AT_IMPORT`), and
inside functions additionally by :data:`SYMPY_IN_FUNCTIONS`; no other
module imports it at all.  ``import satassume`` and every module outside
:data:`SYMPY_AT_IMPORT` load neither SymPy nor mpmath (checked in a fresh
interpreter, so a run-time path through another module counts too).

Neither the package nor ``tests/``, ``harness/``, ``tools/`` and
``benchmarks/`` use an old flat name (``satassume.rules``, ...); those are
transitional aliases (:mod:`satassume._compat`) for code outside the
repository.
"""
from __future__ import annotations

import ast
import importlib
import importlib.abc
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import satassume
from satassume import _compat

ROOT = Path(satassume.__file__).resolve().parent
REPO = ROOT.parent
PKG = "satassume"

#: top-level layer of each module name (prefix match on the first part
#: after ``satassume``)
LAYERS = {"state": 0, "sat": 1, "knowledge": 2, "theories": 3,
          "relations": 4, "scope": 5, "engine": 6, "sympy_api": 7, "ref": 8,
          "_compat": 9}
TOP = 9          # the package __init__ (public API)

#: modules (or packages, by prefix) that import SymPy at module level: the
#: knowledge per SymPy class and the domain test, the theories' adapters
#: from SymPy terms, and the SymPy front end
SYMPY_AT_IMPORT = ("satassume.knowledge.templates", "satassume.knowledge.domain",
                   "satassume.theories.lra.lra_adapter", "satassume.theories.lra.lra_bounds",
                   "satassume.theories.euf.euf_adapter", "satassume.sympy_api")
#: modules that import SymPy only inside the functions that receive or
#: return SymPy objects
SYMPY_IN_FUNCTIONS = ("satassume.theories.lra.constfield", "satassume.relations")

_MODNAME = re.compile(r"^satassume(\.[A-Za-z_]\w*)+$")
_SYMPY = ("sympy", "mpmath")


def _modules():
    """``(module name, path, is package)`` of every module of the package."""
    out = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT.parent).with_suffix("")
        parts = list(rel.parts)
        is_pkg = parts[-1] == "__init__"
        if is_pkg:
            parts = parts[:-1]
        out.append((".".join(parts), path, is_pkg))
    return out


def _exists(name: str) -> bool:
    parts = name.split(".")
    if parts[0] != PKG:
        return False
    p = ROOT.parent.joinpath(*parts)
    return p.with_suffix(".py").is_file() or (p / "__init__.py").is_file()


def layer(name: str) -> int:
    parts = name.split(".")
    if len(parts) == 1:
        return TOP
    return LAYERS[parts[1]]


def theory_group(name: str) -> str:
    """The theory a ``theories`` module belongs to (``""`` for the
    package ``__init__``)."""
    parts = name.split(".")
    return parts[2] if len(parts) > 2 else ""


def allowed(src: str, tgt: str) -> bool:
    ls, lt = layer(src), layer(tgt)
    if lt != ls:
        return lt < ls
    if ls == LAYERS["theories"]:
        return theory_group(src) != "" and theory_group(tgt) == theory_group(src)
    return True


def _resolve(module: str, is_pkg: bool, level: int, name: str | None) -> str:
    base = module.split(".") if is_pkg else module.split(".")[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + ([name] if name else []))


def dependencies(module: str, source: str, is_pkg: bool):
    """``(line, target module, how)`` of every dependency of ``module``."""
    tree = ast.parse(source)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == PKG or a.name.startswith(PKG + "."):
                    out.append((node.lineno, a.name, "import"))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if not node.module or not (node.module == PKG or node.module.startswith(PKG + ".")):
                    continue
                base = node.module
            else:
                base = _resolve(module, is_pkg, node.level, node.module)
            for a in node.names:
                sub = f"{base}.{a.name}"
                if _exists(sub) or _compat.new_name(sub) is not None:
                    out.append((node.lineno, sub, "from-import"))
                else:
                    out.append((node.lineno, base, "from-import"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _MODNAME.match(node.value):
                out.append((node.lineno, node.value, "string"))
        elif (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
              and isinstance(node.left, ast.Name) and node.left.id == "__name__"
              and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)):
            out.append((node.lineno, module + node.right.value, "__name__ string"))
    return out


def violations(module: str, source: str, is_pkg: bool = False):
    bad = []
    for line, tgt, how in dependencies(module, source, is_pkg):
        if _compat.new_name(tgt) is not None:
            bad.append(f"{module}:{line}: {how} of old alias name {tgt}")
        elif not _exists(tgt):
            bad.append(f"{module}:{line}: {how} of {tgt}, which is not a module of the package")
        elif not allowed(module, tgt):
            bad.append(f"{module}:{line}: {how} of {tgt} goes up or across the layers")
    return bad


def test_every_module_has_a_layer():
    for name, _, _ in _modules():
        layer(name)


def test_layering():
    bad = []
    for name, path, is_pkg in _modules():
        bad += violations(name, path.read_text(), is_pkg)
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("module, source", [
    # a lazy upward import (the engine -> sympy_api cycle that was fixed)
    ("satassume.engine", "def f():\n    from .sympy_api import ask\n"),
    ("satassume.sat.solver", "def f():\n    from ..engine import Engine\n"),
    # a module named by string (the old memos / default_specs lookups)
    ("satassume.state.memos", "X = ('satassume.engine', '_SPLIT')\n"),
    ("satassume.relations", "import importlib\nm = importlib.import_module('satassume.lra_adapter')\n"),
    # the theories reaching up to their glue, or into each other
    ("satassume.theories.transfer", "from ..relations import RELATION_ATOMS\n"),
    ("satassume.theories.lra.lra_adapter", "def f():\n    from ...scope import Scope\n"),
    ("satassume.theories.lra.constfield", "def f():\n    from ..euf.euf import EUFTheory\n"),
    ("satassume.theories.transfer", "from .lra.lra import LRATheory\n"),
    ("satassume.theories.lra.lra_cert", "if TYPE_CHECKING:\n    from ..euf.euf import EUFTheory\n"),
    ("satassume.relations", "from .scope import Scope\n"),
    # an old alias name, and a path that does not exist
    ("satassume.engine", "from .rules import PRED_INDEX\n"),
    ("satassume.engine", "from . import lra_adapter\n"),
    ("satassume.engine", "import satassume.templates\n"),
    ("satassume.knowledge.rules", "from ..nowhere import x\n"),
])
def test_checker_catches(module, source):
    assert violations(module, source)


@pytest.mark.parametrize("module, source", [
    ("satassume.relations", "def f():\n    from .theories.lra.lra_adapter import LRAAdapter\n"),
    ("satassume.scope", "from .relations import RELATION_ATOMS\nfrom .theories.transfer import transfer_wanted\n"),
    ("satassume.theories.lra.lra", "def f():\n    from .lra_cert import certify\n"),
    ("satassume.knowledge.templates", "registry.lazy(__name__ + '.core', Add)\n"),
    ("satassume.ref", "from .knowledge import templates\n"),
])
def test_checker_allows(module, source):
    assert not violations(module, source, module == "satassume.knowledge.templates")


# -- SymPy -------------------------------------------------------------------

def _in(name: str, prefixes) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


def sympy_violations(module: str, source: str):
    """Imports of SymPy or mpmath that :data:`SYMPY_AT_IMPORT` and
    :data:`SYMPY_IN_FUNCTIONS` do not allow ``module``."""
    at_import = _in(module, SYMPY_AT_IMPORT)
    in_functions = at_import or _in(module, SYMPY_IN_FUNCTIONS)
    bad = []

    def visit(node, in_function):
        for ch in ast.iter_child_nodes(node):
            inf = in_function or isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            names = []
            if isinstance(ch, ast.Import):
                names = [a.name for a in ch.names]
            elif isinstance(ch, ast.ImportFrom) and ch.level == 0 and ch.module:
                names = [ch.module]
            for n in names:
                if n.split(".")[0] in _SYMPY and not (in_functions if inf else at_import):
                    where = "inside a function" if inf else "at module level"
                    bad.append(f"{module}:{ch.lineno}: imports {n} {where}")
            visit(ch, inf)

    visit(ast.parse(source), False)
    return bad


def test_sympy_imports():
    bad = []
    for name, path, _ in _modules():
        bad += sympy_violations(name, path.read_text())
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("module, source, ok", [
    ("satassume.knowledge.rules", "from sympy import Q\n", False),
    ("satassume.knowledge.rules", "def f():\n    import sympy\n", False),
    ("satassume.engine", "def f():\n    from mpmath import iv\n", False),
    ("satassume.relations", "from sympy import Eq\n", False),
    ("satassume.relations", "def f():\n    from sympy import Eq\n", True),
    ("satassume.theories.lra.constfield", "def f():\n    import sympy\n", True),
    ("satassume.theories.lra.lra_adapter", "from sympy import Add\n", True),
    ("satassume.knowledge.templates.core", "from sympy import Mul\n", True),
])
def test_sympy_checker(module, source, ok):
    assert (not sympy_violations(module, source)) == ok


def test_sympy_free_modules_load_no_sympy():
    """In a fresh interpreter, importing the package and every module
    outside :data:`SYMPY_AT_IMPORT` loads neither SymPy nor mpmath."""
    free = [n for n, _, _ in _modules() if not _in(n, SYMPY_AT_IMPORT)]
    code = ("import sys\n"
            + "".join(f"import {n}\n" for n in free)
            + "print(sorted(m for m in ('sympy', 'mpmath') if m in sys.modules))\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(REPO), env={**os.environ, "PYTHONPATH": str(REPO)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]", r.stdout


# -- old names ---------------------------------------------------------------

#: deliberate uses of an old name outside the package: (file, name)
OLD_NAME_USES = {
    # asv replays the benchmarks over commits before the move
    ("benchmarks/counters.py", "satassume.solver"),
}


def test_consumers_use_the_new_names():
    bad = []
    for d in ("tests", "harness", "tools", "benchmarks"):
        for path in sorted((REPO / d).rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            if rel == "tests/test_layering.py":
                continue
            module = rel[:-3].replace("/", ".")
            is_pkg = module.endswith(".__init__")
            for line, tgt, how in dependencies(module, path.read_text(), is_pkg):
                if _compat.new_name(tgt) is not None and (rel, tgt) not in OLD_NAME_USES:
                    bad.append(f"{rel}:{line}: {how} of old name {tgt} (now {_compat.new_name(tgt)})")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("old", sorted(_compat.ALIASES))
def test_alias_is_the_same_module(old):
    new = _compat.ALIASES[old]
    sys.modules.pop(f"{PKG}.{old}", None)
    with pytest.warns(DeprecationWarning, match=f"{PKG}.{new}"):
        a = importlib.import_module(f"{PKG}.{old}")
    b = importlib.import_module(f"{PKG}.{new}")
    assert a is b and a.__name__ == f"{PKG}.{new}"
    # the alias's import must not leave its own spec on the module
    assert a.__spec__.name == a.__name__ and a.__package__ == a.__spec__.parent
    assert getattr(satassume, old) is b


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_alias_under_an_old_package():
    import satassume.templates.core as old
    import satassume.knowledge.templates.core as new
    assert old is new


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_alias_keeps_package_attributes():
    """``satassume.templates.registry`` is the registry object (the
    package binds it over its submodule's name); importing the submodule
    by its old name must not replace it with the module."""
    import satassume.templates.registry  # noqa: F401
    from satassume.knowledge.templates.registry import TemplateRegistry
    import satassume.templates as t
    assert isinstance(t.registry, TemplateRegistry)


def test_old_name_first_loads_no_second_module():
    """In a fresh interpreter, importing a template module by its old name
    first leaves one module object, under both names."""
    code = (
        "import sys\n"
        "import satassume.templates.core as c\n"
        "import satassume.rules as r\n"
        "assert sys.modules['satassume.templates.core'] is sys.modules['satassume.knowledge.templates.core'] is c\n"
        "assert sys.modules['satassume.rules'] is sys.modules['satassume.knowledge.rules'] is r\n"
        "core = {id(m) for m in list(sys.modules.values())\n"
        "        if getattr(m, '__file__', None) and m.__file__.endswith(('templates/core.py', 'templates\\\\core.py'))}\n"
        "assert len(core) == 1, core\n"
        "print('ok')\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(ROOT.parent), env={**os.environ, "PYTHONPATH": str(ROOT.parent)})
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr


@pytest.mark.parametrize("missing, left", [
    ("satassume.theories.lra.lra_adapter", ["euf"]),
    ("satassume.theories.euf.euf_adapter", ["lra"]),
])
def test_default_specs_skips_a_missing_adapter(monkeypatch, missing, left):
    """``default_specs`` names its adapters relative to the package: a
    missing adapter module is left out (a move that leaves the name stale
    would make it raise instead)."""
    from satassume.relations import default_specs
    monkeypatch.delitem(sys.modules, missing, raising=False)
    monkeypatch.setitem(sys.modules, missing, None)
    assert [s.name for s in default_specs()] == left


def test_default_specs_raises_for_a_broken_adapter(monkeypatch):
    """An adapter module that exists but fails to import raises."""
    from satassume.relations import default_specs
    name = "satassume.theories.lra.lra_adapter"

    class Broken(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == name:
                raise ModuleNotFoundError("No module named 'some_dependency'", name="some_dependency")
            return None

    monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [Broken()] + sys.meta_path)
    with pytest.raises(ModuleNotFoundError):
        default_specs()
