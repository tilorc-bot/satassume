"""The environment switches of satrefine's refine, in one place.

``SATREFINE_HANDLERS``     the handler package :mod:`satrefine` loads (read once, at import);
``SATREFINE_IDENTITIES``   ``generated`` (default) or ``live``: whether the driver uses the
                           generated rule tables (read on every lookup, so tests can switch it);
``SATREFINE_STRICT_LOOPS`` ``1``: a tripped termination guard raises instead of returning the
                           input unchanged (read when a guard trips).

The ``ask`` backend (``SATREFINE_BACKEND``) is chosen in :mod:`.compat.backend`.
The context managers that override the last two inside a block are
:func:`.core.driver.live`, :func:`.core.driver.tables` and :func:`.core.guard.strict_loops`.
"""
from __future__ import annotations

import os

HANDLERS_ENV_VAR = "SATREFINE_HANDLERS"
"""Name of the handler package to load, relative to ``satrefine``.

Defaults to :data:`DEFAULT_HANDLERS`.  The other implementations of the same
registry keys (``handlers``, the original layer; ``handlers_v2``;
``handlers_v3``) can be selected instead, so they can be measured with the
same dispatcher, backends and tools.
"""

DEFAULT_HANDLERS = "handlers_identities"
"""Handler package loaded when :data:`HANDLERS_ENV_VAR` is not set."""

MODE_ENV_VAR = "SATREFINE_IDENTITIES"

STRICT_ENV_VAR = "SATREFINE_STRICT_LOOPS"


def handlers_package() -> str:
    """The handler package the environment selects."""
    return os.environ.get(HANDLERS_ENV_VAR, DEFAULT_HANDLERS)


def env_mode() -> str:
    """``"generated"`` (default) or ``"live"``, from ``SATREFINE_IDENTITIES``."""
    value = os.environ.get(MODE_ENV_VAR, "generated")
    if value not in ("generated", "live"):
        raise ValueError(f"{MODE_ENV_VAR} must be 'generated' or 'live', not {value!r}")
    return value


def env_strict() -> bool:
    """Whether ``SATREFINE_STRICT_LOOPS`` asks a tripped guard to raise."""
    return os.environ.get(STRICT_ENV_VAR, "") not in ("", "0")
