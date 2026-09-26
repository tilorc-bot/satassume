"""The identity-based handlers, selected with ``SATREFINE_HANDLERS=handlers_identities``
(the default): a thin package that loads :mod:`satrefine.identities`, where the
code lives (kept under this name because tools, tests and reports use it)."""
from __future__ import annotations

from ..identities import load as _load

_load()
