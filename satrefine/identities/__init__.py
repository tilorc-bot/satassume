"""Refine handlers written as tables of identities and rules: the online part.

Everything under this package runs (or may run) on every ``refine`` call; the
offline side (:mod:`satrefine.build`: generation of the tables in
``generated/``; :mod:`satrefine.tools`; :mod:`satrefine.testing`) imports it,
never the reverse (``tests/refine_identities/test_import_direction.py``).

``core/``       general algorithms: the driver (:mod:`.core.driver`, which
                replaces ``satrefine.refine`` when this package is selected),
                the termination guard (:mod:`.core.guard`), proving
                (:mod:`.core.prove`), pattern matching
                (:mod:`.core.match`), rewriting with identity and rule tables
                (:mod:`.core.rewrite`) and case splits (:mod:`.core.split`);
``rules/``      the families (one module per family of heads, each ending with
                a ``SPEC`` (:class:`.core.spec.Family`) that :func:`load`
                registers), the helpers the tables share (``_tables``:
                measures, ``derive``, ``ZERO``), the wraps (``_wraps``) and
                the procedural ``floor``/``Piecewise`` handlers (``_simple``);
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

A family module states its rows in module-level tables under the names the
scoreboard counts: ``FACTS`` (identity rows about the family's own
functions), ``EXP_FORMS`` (exponential forms of other heads, reusable),
``RULES`` (plain conditional rows), ``RANGES`` (ranges of bounded heads) and
further named tables (the names label the rows of the generated modules),
and ends with ``SPEC = Family(handlers, facts=..., exp_forms=..., rules=...,
ranges=...)``: which parts (:class:`.core.spec.Rules`,
:class:`.core.spec.Identities`) serve which ``handlers_dict`` key, and the
tables classified into those kinds.  Importing a family registers nothing.
The generation settings (the edge points every generated rule is checked at,
the families without a generated table, the assumption profiles per
variable) are in :mod:`satrefine.build.specs`.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import types

from .compat import matrix_match as _matrix_match  # noqa: F401  (installs the matcher's matrix hook)
from .compat import sympy_fixes as _sympy_fixes  # noqa: F401  (installs the driver's SymPy workarounds)


COMPAT_FAMILIES = ("matrices",)
"""Families that live in :mod:`.compat` (expected to change) rather than in :mod:`.rules`."""


def family_module_name(family: str) -> str:
    """The module of a family, by its short name (``"power_exp_log"``)."""
    return f"{__name__}.{'compat' if family in COMPAT_FAMILIES else 'rules'}.{family}"


def families() -> list[str]:
    """The short names of every family module, sorted."""
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
    then the generated tables are imported and every family's ``SPEC`` and range
    rows are registered."""
    from .. import _upstream
    from .core import driver, spec
    from .rules import _simple
    satrefine = sys.modules.get("satrefine")
    if satrefine is not None:
        satrefine.refine = driver.refine
    _simple.install(_upstream.handlers_dict)
    from . import generated  # noqa: F401  (registers the generated tables)
    modules = family_modules()
    names = [m.__name__.rsplit(".", 1)[-1] for m in modules]
    # complex_parts imports power_exp_log's exponential forms, so power_exp_log used to register
    # first: keep that order (the order of handlers_dict's keys, which generation follows)
    modules.insert(names.index("complex_parts"), modules.pop(names.index("power_exp_log")))
    spec.register([m.SPEC for m in modules], _upstream.handlers_dict)
    for m in modules:
        _simple.register_ranges(m.SPEC.ranges)
