"""The layout rules of issue #13, checked.

* **Imports go one way**: ``satrefine.build``, ``satrefine.tools`` and
  ``satrefine.testing`` (offline) may import ``satrefine.identities``, never
  the reverse; nor does ``satrefine.identities`` import the reference
  implementation ``satrefine.reference`` (v3, measuring material).  A subprocess makes the offline packages unimportable (a
  meta-path finder that raises) before it imports ``satrefine``, then refines
  a few inputs in each ``SATREFINE_IDENTITIES`` mode; the results must be what
  this process gets.
* **``identities/core`` names no specific SymPy function and no matrix type**
  (the heads the engine needs to know about are roles in
  ``identities/core/hooks.py``, set by the rules layer), and **imports neither
  ``identities.rules`` nor ``identities.compat``** (they plug in through
  ``core/hooks.py``).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from satrefine.identities.core import driver as _dispatch

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "satrefine" / "identities" / "core"

OFFLINE = ("satrefine.build", "satrefine.tools", "satrefine.testing")

CASES = [   # (expression, assumptions), as source evaluated with ``from sympy import *``
    ("log(x)", "Q.negative(x)"),
    ("sqrt(x**2)", "Q.real(x)"),
    ("atan(tan(x))", "Q.gt(x, -pi/2) & Q.lt(x, pi/2)"),
    ("floor(x)", "Q.ge(x, 1) & Q.lt(x, 2)"),
    ("Piecewise((1, x > 0), (2, True))", "Q.positive(x)"),
    ("exp(log(x)*y)", "Q.positive(x)"),
    ("Abs(x*y)", "Q.negative(x) & Q.positive(y)"),
    ("im(log(x))", "Q.negative(x)"),
    ("Determinant(Transpose(X))", "True"),
    ("MatMul(X, Inverse(X))", "Q.invertible(X)"),
]

_CHILD = r'''
import importlib.abc, json, sys

OFFLINE = %(offline)r


class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name in OFFLINE or name.startswith(tuple(p + "." for p in OFFLINE)):
            raise ImportError(f"offline package imported by refine: {name}")
        return None


sys.meta_path.insert(0, Blocked())
from sympy import *
import satrefine
x, y = symbols("x y")
X = MatrixSymbol("X", 3, 3)
out = [srepr(satrefine.refine(eval(e), eval(a))) for e, a in %(cases)r]
loaded = sorted(m for m in sys.modules if m.startswith(OFFLINE))
print(json.dumps({"results": out, "loaded": loaded, "refine": satrefine.refine.__module__}))
'''


def _expected() -> list[str]:
    from sympy import srepr, symbols, MatrixSymbol  # noqa: F401
    import sympy
    from satrefine import refine
    names = dict(vars(sympy))
    names.update(x=symbols("x"), y=symbols("y"), X=MatrixSymbol("X", 3, 3))
    return [srepr(refine(eval(e, names), eval(a, names))) for e, a in CASES]


@pytest.mark.parametrize("mode", ["generated", "live"])
def test_refine_runs_without_the_offline_packages(mode):
    code = _CHILD % {"offline": OFFLINE, "cases": CASES}
    env = dict(os.environ, SATREFINE_HANDLERS="handlers_identities", SATREFINE_IDENTITIES=mode,
               PYTHONPATH=os.pathsep.join(sys.path))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    child = json.loads(proc.stdout.strip().splitlines()[-1])
    assert child["loaded"] == []
    assert child["refine"] == "satrefine.identities.core.driver"
    with (_dispatch.live() if mode == "live" else _dispatch.tables()):
        expected = _expected()
    assert child["results"] == expected


def _imports(directory: Path, forbidden: tuple[str, ...]) -> list[str]:
    """``path:line name`` for every import (even a lazy one) under ``directory`` of a
    module in, or equal to, one of the packages ``forbidden``."""
    found = []
    for path in sorted(directory.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:          # relative: resolve against the module's package
                    package = path.relative_to(ROOT).with_suffix("").parts[:-1]
                    parts = list(package[:len(package) - node.level + 1])
                    base = ".".join(parts + ([base] if base else []))
                names = [base] + [f"{base}.{a.name}" for a in node.names]
            for name in names:
                if name in forbidden or name.startswith(tuple(p + "." for p in forbidden)):
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    return found


def test_the_offline_packages_are_not_imported_by_identities():
    """No module under ``satrefine/identities`` imports an offline package, even lazily."""
    found = _imports(ROOT / "satrefine" / "identities", OFFLINE)
    assert not found, found


def test_the_reference_is_not_imported_by_identities():
    """No module under ``satrefine/identities`` imports ``satrefine.reference`` (v3), even lazily."""
    found = _imports(ROOT / "satrefine" / "identities", ("satrefine.reference",))
    assert not found, found


def test_core_imports_no_rules_or_compat():
    """No module under ``identities/core`` imports ``identities.rules`` or ``identities.compat``,
    even lazily: they plug into core through ``core/hooks.py``."""
    found = _imports(CORE, ("satrefine.identities.rules", "satrefine.identities.compat"))
    assert not found, found


# ---------------------------------------------------------------------------
# core names no specific SymPy function and no matrix type
# ---------------------------------------------------------------------------

GENERIC = {"Function", "AppliedUndef", "UndefinedFunction"}
"""Function classes core may name: the generic ones (head wildcards)."""

REMAINING: dict[str, set[str]] = {}
"""Specific names ``core`` may still import, by module (none since step 3 of issue #13)."""


def _specific_names(path: Path) -> set[str]:
    """Names ``path`` imports from SymPy that are specific function classes
    (subclasses of ``Function``, or ``Max``/``Min``) or matrix types."""
    import importlib
    from sympy import Function
    from sympy.functions.elementary.miscellaneous import MinMaxBase
    from sympy.matrices import MatrixBase
    from sympy.matrices.expressions import MatrixExpr
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "sympy":
            module = importlib.import_module(node.module)
            for alias in node.names:
                obj = getattr(module, alias.name, None)
                if not isinstance(obj, type) or alias.name in GENERIC:
                    continue
                if issubclass(obj, (Function, MinMaxBase, MatrixBase, MatrixExpr)):
                    out.add(alias.name)
            if "matrices" in node.module:
                out.add(node.module)
        elif isinstance(node, ast.Import) and any("matrices" in a.name for a in node.names if a.name.startswith("sympy")):
            out.update(a.name for a in node.names)
    return out


def _core_names() -> dict[str, set[str]]:
    return {p.name: names for p in sorted(CORE.glob("*.py")) if (names := _specific_names(p))}


def test_core_names_nothing_new():
    """No core module names a specific function or matrix type beyond :data:`REMAINING`."""
    found = _core_names()
    extra = {m: names - REMAINING.get(m, set()) for m, names in found.items() if names - REMAINING.get(m, set())}
    assert not extra, extra


def test_core_names_no_specific_function_or_matrix():
    assert _core_names() == {}
