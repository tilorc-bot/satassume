"""Offline: satrefine's tools (scoreboards, differential, fuzz, oracle, ablation, generation, gates).

Run as ``python -m satrefine.tools.<name>``; refine never imports this package.
"""
from __future__ import annotations

import os
import sys


def rerun_with(handlers: str | None = None, backend: str | None = None) -> None:
    """Make the selection a tool read from its own arguments take effect under ``python -m``.

    A tool run as a script sets ``SATREFINE_HANDLERS`` (``SATREFINE_BACKEND``)
    before it imports :mod:`satrefine`; run as ``python -m satrefine.tools.<name>``,
    :mod:`satrefine` and its handler package are imported before the tool's code
    runs.  When they differ from the tool's selection, run the tool again in a
    fresh process with the variables set (``os.execv``: same arguments, same
    process id); otherwise return.  Tools call it only when ``satrefine`` was
    imported before them."""
    import satrefine
    from satrefine.identities.compat import backend as _backend
    env = {}
    if handlers is not None and satrefine.HANDLERS_PACKAGE != handlers:
        env["SATREFINE_HANDLERS"] = handlers
    if backend is not None and _backend.current() != backend:
        env["SATREFINE_BACKEND"] = backend
    if not env:
        return
    os.environ.update(env)
    main = sys.modules["__main__"]
    spec = getattr(main, "__spec__", None)
    command = ["-m", spec.name] if spec is not None else [main.__file__]
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable, *command, *sys.argv[1:]])
