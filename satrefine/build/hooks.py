"""The generation hooks of the driver: what a table generation switches on.

The driver (:mod:`satrefine.identities.core.driver`) keeps the state these
read and write (``_trace`` via :func:`~satrefine.identities.core.driver.note`,
``live_keys``); step 3 of issue #13 replaces both with one observer hook
("call this on each firing" plus "use these tables").
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .. import _upstream
from ..identities.core.driver import _trace, live_keys


@contextmanager
def tracing() -> Iterator[list]:
    """Collect the rows that fire and the ``ask`` queries answered ``True`` inside the
    block: a list of ``("rule" | "identity", row)`` and ``("ask", proposition)`` entries
    (the derivation record of a generated rule)."""
    log: list = []
    _trace.append(log)
    inner = _upstream.ask

    def recording_ask(proposition: Any, assumptions: Any = True) -> Any:
        answer = inner(proposition, assumptions)
        if answer is True and _trace:
            _trace[-1].append(("ask", proposition))
        return answer
    _upstream.ask = recording_ask
    try:
        yield log
    finally:
        _upstream.ask = inner
        _trace.pop()


@contextmanager
def live_for(keys: Any) -> Iterator[None]:
    """Run ``keys`` on their identity rows inside the block, every other key as :func:`mode` says."""
    saved = set(live_keys)
    live_keys.update(keys)
    try:
        yield
    finally:
        live_keys.clear()
        live_keys.update(saved)
