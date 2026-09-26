"""What a table generation switches on in the driver, through its one observer hook
(:func:`satrefine.identities.core.driver.observing`)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .. import _upstream
from ..identities.core.driver import observing


@contextmanager
def tracing() -> Iterator[list]:
    """Collect the rows that fire and the ``ask`` queries answered ``True`` inside the
    block: a list of ``("rule" | "identity", row)`` and ``("ask", proposition)`` entries
    (the derivation record of a generated rule)."""
    log: list = []
    inner = _upstream.ask

    def recording_ask(proposition: Any, assumptions: Any = True) -> Any:
        answer = inner(proposition, assumptions)
        if answer is True:
            log.append(("ask", proposition))
        return answer
    _upstream.ask = recording_ask
    try:
        with observing(on_fire=lambda kind, row: log.append((kind, row))):
            yield log
    finally:
        _upstream.ask = inner
