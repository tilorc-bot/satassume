"""Refine handlers written as tables of identities and rules: the online part.

Everything under this package runs (or may run) on every ``refine`` call; the
offline side (:mod:`satrefine.build`: generation of the tables in
``generated/``; :mod:`satrefine.tools`; :mod:`satrefine.testing`) imports it,
never the reverse (``tests/refine_identities/test_import_direction.py``).

``core/``       general algorithms: the driver (:mod:`.core.driver`, which
                replaces ``satrefine.refine`` when this package is selected),
                the termination guard (:mod:`.core.guard`), proving
                (:mod:`.core.prove`, :mod:`.core.bounds`), pattern matching
                (:mod:`.core.match`), rewriting with identity and rule tables
                (:mod:`.core.rewrite`) and case splits (:mod:`.core.split`);
``rules/``      the families (one module per family of heads, registering its
                handlers into ``satrefine._upstream.handlers_dict`` when
                imported), the helpers the tables share (``_tables``: chain,
                measures, ``derive``, ``compile_table``), the wraps
                (``_wraps``) and the procedural ``floor``/``Piecewise``
                handlers (``_simple``);
``generated/``  the generated rule tables, one module per family, written by
                ``python -m satrefine.tools.refine_specialize --write`` and used by
                the driver when ``SATREFINE_IDENTITIES=generated`` (the
                default); ``live`` runs the identity rows instead;
``compat/``     what is expected to change: SymPy workarounds
                (:mod:`.compat.sympy_fixes`), the matrix special cases (the
                matcher hook :mod:`.compat.matrix_match` and the matrix family
                :mod:`.compat.matrices`) and the ``ask`` backend routing
                (:mod:`.compat.backend`);
``config.py``   the environment switches.

The package is selected with ``SATREFINE_HANDLERS=handlers_identities`` (the
default); :mod:`satrefine.handlers_identities` calls :func:`load`.

A family module declares its tables under the names the scoreboard counts:
``FACTS`` (identity rows about the family's own functions), ``EXP_FORMS``
(exponential forms of other heads, reusable), ``RULES`` (plain conditional
rows) and ``SIMPLE_RULES`` (rows, or an int for procedural simple rules),
and registers with literal ``handlers_dict['key'] = handler`` statements.
It may also declare ``EDGE_POINTS`` (values every generated rule is checked
at, in addition to 0, 1, -1, I, -I: the family's branch-cut points), or
``SPECIALIZE = False`` to have no generated table; the assumption profiles
the generator tries per variable are in :data:`satrefine.build.specs.CATALOGS`.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import types


COMPAT_FAMILIES = ("matrices",)
"""Families that live in :mod:`.compat` (expected to change) rather than in :mod:`.rules`."""


def family_module_name(family: str) -> str:
    """The module of a family, by its short name (``"power_exp_log"``)."""
    return f"{__name__}.{'compat' if family in COMPAT_FAMILIES else 'rules'}.{family}"


def families() -> list[str]:
    """The short names of every family module, sorted (the order they are loaded in)."""
    from . import rules
    names = [info.name for info in pkgutil.iter_modules(rules.__path__)
             if not info.name.startswith("_") and not info.ispkg]
    return sorted(names + list(COMPAT_FAMILIES))


def family_modules() -> list[types.ModuleType]:
    """Every family module, imported, in :func:`families` order."""
    return [importlib.import_module(family_module_name(name)) for name in families()]


def load() -> None:
    """Select this package: the driver replaces ``satrefine.refine`` (the attribute
    on the partially initialized ``satrefine`` module is replaced while it loads
    its handler package, so ``from satrefine import refine`` and every tool get
    it), the simple rules are registered before the families so a family that
    registers one of their keys overrides them and the driver falls back to them,
    then the generated tables and the families are imported."""
    from .. import _upstream
    from .core import driver
    from .rules import _simple
    satrefine = sys.modules.get("satrefine")
    if satrefine is not None:
        satrefine.refine = driver.refine
    _simple.install(_upstream.handlers_dict)
    from . import generated  # noqa: F401  (registers the generated tables)
    family_modules()
