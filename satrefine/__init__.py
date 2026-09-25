"""Assumption-driven refinement backed by the independent engine.

The vendored dispatcher and initial handlers live in
:mod:`satrefine._upstream`; every additional handler is a module in
:mod:`satrefine.handlers` that registers itself into
``handlers_dict`` when imported.  Importing this package loads all of them.
"""
from __future__ import annotations

import importlib
import os
import pkgutil

from ._upstream import (
    ask,
    handlers_dict,
    refine,
    refine_Heaviside,
    refine_Pow,
    refine_abs,
    refine_arg,
    refine_atan2,
    refine_exp,
    refine_floor_ceiling,
    refine_im,
    refine_matrixelement,
    refine_re,
    refine_sign,
    refine_sin_cos,
)

__all__ = [
    "ask",
    "handlers_dict",
    "refine",
    "refine_Heaviside",
    "refine_Pow",
    "refine_abs",
    "refine_arg",
    "refine_atan2",
    "refine_exp",
    "refine_floor_ceiling",
    "refine_im",
    "refine_matrixelement",
    "refine_re",
    "refine_sign",
    "refine_sin_cos",
]


HANDLERS_ENV_VAR = "SATREFINE_HANDLERS"
"""Name of the handler package to load, relative to ``satrefine``.

Defaults to :data:`DEFAULT_HANDLERS`.  The other implementations of the same
registry keys (``handlers``, the original layer; ``handlers_v2``;
``handlers_v3``) can be selected instead, so they can be measured with the
same dispatcher, backends and tools.
"""

DEFAULT_HANDLERS = "handlers_identities"
"""Handler package loaded when :data:`HANDLERS_ENV_VAR` is not set."""

HANDLERS_PACKAGE = os.environ.get(HANDLERS_ENV_VAR, DEFAULT_HANDLERS)
"""Name of the handler package this process loaded (fixed at import)."""


def _load_handlers() -> None:
    """Import every public module in the selected handler package."""
    package = importlib.import_module(__name__ + "." + HANDLERS_PACKAGE)
    path = getattr(package, "__path__", None)
    if path is None:
        return
    for info in pkgutil.iter_modules(path):
        if not info.name.startswith("_"):
            importlib.import_module(f"{package.__name__}.{info.name}")


_load_handlers()
