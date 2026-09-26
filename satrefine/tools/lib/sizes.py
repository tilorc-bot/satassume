"""Sizes the scoreboard prints: rows per family and code lines of the engine and the families.

Code lines are physical lines that are not blank, not comments and not
module, class or function docstrings.  The engine is the former underscore
modules of ``handlers_identities``: online, ``satrefine/identities`` without
the families, the generated tables, the ``ask`` backend and the vendored
SymPy dispatcher (``compat/upstream.py``, ``satrefine/_upstream.py`` before
phase 3, never counted); offline,
``satrefine/build`` (specialisation, fixpoint).  Rows are counted from each
family's ``SPEC`` (:class:`satrefine.identities.core.spec.Family`): its table
kinds ``facts``, ``exp_forms``, ``rules``, ``ranges``, counting only rows the
module states in its own public tables (not the shared ``ZERO`` row, not another
family's exponential forms); ``stage0`` is every stated row.
"""
from __future__ import annotations

import ast
import importlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

COLUMNS = ("FACTS", "EXP_FORMS", "RULES", "SIMPLE_RULES", "RANGES")
KINDS = {"FACTS": "facts", "EXP_FORMS": "exp_forms", "RULES": "rules", "RANGES": "ranges"}
"""Column -> ``Family`` table kind (``SIMPLE_RULES`` is 0: no family has procedural rules)."""


def _size(module, name: str) -> int:
    v = getattr(module, name, None)
    return v if isinstance(v, int) else len(v) if v is not None else 0


def family_rows() -> list[tuple[str, Counter]]:
    """(family, counts) for every family: ``COLUMNS``, ``STAGE0`` and ``GENERATED``
    (the size of ``generated/<family>.py``, 0 if there is none)."""
    from satrefine.identities import families, family_module_name
    out = []
    for name in families():
        mod = importlib.import_module(family_module_name(name))
        own = [v for k, v in vars(mod).items() if isinstance(v, list) and not k.startswith("_")]
        counts = Counter({col: sum(any(row in rows for rows in own) for row in getattr(mod.SPEC, kind))
                          for col, kind in KINDS.items()})
        counts["SIMPLE_RULES"] = 0
        counts["STAGE0"] = sum(counts.values())
        try:
            gen = importlib.import_module(f"satrefine.identities.generated.{name}")
            counts["GENERATED"] = _size(gen, "RULES")
        except ModuleNotFoundError:
            counts["GENERATED"] = 0
        out.append((name, counts))
    return out


def code_lines(path: Path) -> int:
    """Lines of ``path`` that are not blank, comments, or module/class/function docstrings."""
    source = path.read_text()
    docstrings: set = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                docstrings.update(range(first.lineno, first.end_lineno + 1))
    return sum(1 for k, line in enumerate(source.splitlines(), 1)
               if line.strip() and not line.strip().startswith("#") and k not in docstrings)


def family_paths() -> dict[str, Path]:
    from satrefine.identities import families, family_module_name
    return {f: ROOT / (family_module_name(f).replace(".", "/") + ".py") for f in families()}


def engine_paths() -> tuple[list[Path], list[Path]]:
    """The engine's modules, ``(online, offline)`` (see the module docstring)."""
    package = ROOT / "satrefine/identities"
    skip = set(family_paths().values()) | {package / "compat/backend.py", package / "compat/upstream.py"}
    online = sorted(p for p in package.rglob("*.py") if p not in skip and "generated" not in p.parts
                    and not (p.name == "__init__.py" and code_lines(p) == 0))
    offline = sorted(p for p in (ROOT / "satrefine/build").glob("*.py") if p.name != "__init__.py" or code_lines(p))
    return online, offline
