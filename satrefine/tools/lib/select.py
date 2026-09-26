"""The handler package and ``ask`` backend a tool runs under.

A tool run as a script sets ``SATREFINE_HANDLERS`` (``SATREFINE_BACKEND``)
before it imports :mod:`satrefine`.  Run as ``python -m satrefine.tools.<name>``
(or through anything that imports ``satrefine.tools``), :mod:`satrefine` and its
handler package are loaded before the tool reads its arguments; :func:`select`
then runs the tool again in a fresh process with the variables set, once, and
only when what is loaded differs.
"""
from __future__ import annotations

import os
import sys


def rerun_with(handlers: str | None = None, backend: str | None = None) -> None:
    """Re-execute this process (same arguments, same pid) with the selection in the environment.

    Returns without doing anything when ``satrefine`` already runs the
    selected package and backend."""
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


def select(handlers: str | None = None, backend: str | None = None) -> None:
    """Run this tool under ``handlers`` and ``backend`` (None: leave as is).

    If ``satrefine`` is loaded with something else, re-execute (see
    :func:`rerun_with`); then set the variables, so that subprocesses and a
    later import see them too."""
    if "satrefine" in sys.modules:
        rerun_with(handlers=handlers, backend=backend)
    if handlers is not None:
        os.environ["SATREFINE_HANDLERS"] = handlers
    if backend is not None:
        os.environ["SATREFINE_BACKEND"] = backend


def backend_from_env(default: str = "combined") -> None:
    """Set the ``ask`` backend from ``SATREFINE_BACKEND`` (default ``combined``), as the fuzzers always did."""
    from satrefine.identities.compat import backend
    backend.set_backend(os.environ.get(backend.ENV_VAR, default))
