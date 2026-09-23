"""Which ``ask`` answers the refine handlers' questions.

Every handler in :mod:`satrefine` asks predicate questions through
:func:`satrefine._upstream.ask`, which delegates to the backend selected
here.  Three backends exist:

``sympy``
    SymPy's own :func:`sympy.assumptions.ask.ask`.  The reference: the
    handlers refine exactly like SymPy's ``refine`` would with the same
    handler logic.
``satassume``
    :func:`satassume.sympy_api.ask` alone.  Out-of-scope queries (relations,
    matrix predicates) and undecided in-scope queries return ``None``, so a
    handler that needs them never fires.  This is the strict measurement of
    the engine: a refine test that passes under ``sympy`` and fails here is
    a satassume gap.  Assumptions that contradict a symbol's declared facts
    raise :class:`satassume.InconsistentAssumptions`, as the engine does.
``combined``
    satassume first; every ``None`` (and every inconsistency error) is
    re-asked of SymPy's ``ask``.  The union of both, for developing handlers
    whose simplifications neither engine alone can justify.

The backend is chosen with :func:`set_backend`, temporarily with
:func:`using`, or at import time from the ``SATREFINE_BACKEND`` environment
variable.  The default is ``combined``.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator

Ask = Callable[..., "bool | None"]

BACKENDS = ("sympy", "satassume", "combined")
DEFAULT = "combined"
ENV_VAR = "SATREFINE_BACKEND"


def _sympy_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from sympy.assumptions.ask import ask
    return ask(proposition, assumptions)


def _satassume_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from satassume.sympy_api import ask
    return ask(proposition, assumptions)


def _combined_ask(proposition: Any, assumptions: Any = True) -> bool | None:
    from satassume import InconsistentAssumptions
    try:
        answer = _satassume_ask(proposition, assumptions)
    except ValueError as e:
        # satassume.sympy_api.ask re-raises InconsistentAssumptions as a
        # ValueError; SymPy then gets the last word on whether to raise.
        if not isinstance(e.__cause__, InconsistentAssumptions):
            raise
        answer = None
    if answer is None:
        answer = _sympy_ask(proposition, assumptions)
    return answer


_IMPLEMENTATIONS: dict[str, Ask] = {
    "sympy": _sympy_ask,
    "satassume": _satassume_ask,
    "combined": _combined_ask,
}


def _validate(name: str) -> str:
    if name not in _IMPLEMENTATIONS:
        raise ValueError(f"unknown satrefine backend {name!r}; expected one of {BACKENDS}")
    return name


_current: str = _validate(os.environ.get(ENV_VAR, DEFAULT))


def current() -> str:
    """Name of the selected backend."""
    return _current


def set_backend(name: str) -> None:
    """Select the backend for all following refine calls."""
    global _current
    _current = _validate(name)


Observer = Callable[[Any, Any, str, "bool | None"], None]
observers: list[Observer] = []
"""Callables told about every answered query: ``(proposition, assumptions,
backend name, answer)``.  The test suite uses this to count out-of-scope
queries per test."""


def ask(proposition: Any, assumptions: Any = True) -> bool | None:
    """Answer with the selected backend."""
    answer = _IMPLEMENTATIONS[_current](proposition, assumptions)
    for observe in observers:
        observe(proposition, assumptions, _current, answer)
    return answer


@contextmanager
def using(name: str) -> Iterator[None]:
    """Select ``name`` for the duration of a ``with`` block."""
    previous = _current
    set_backend(name)
    try:
        yield
    finally:
        set_backend(previous)
