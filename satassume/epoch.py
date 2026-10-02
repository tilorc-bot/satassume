"""The registry epoch: one process-wide counter of everything an answer
depends on besides its inputs.

An ``ask`` answer is a function of the proposition, the assumptions, the
engine's configuration and the registrations in force: the clause-generating
functions of every :class:`satassume.extensions.Extensions` registry (the
default one also decides the scope of ``sympy_api.ask``, whichever registry
an engine uses), the structural templates
(``satassume.templates.registry``) and the theory adapters of the engine.
Every change of one of these bumps :data:`EPOCH`:

* ``Extensions.register`` and ``Extensions.unregister`` (through the
  ``version`` counter of the registry);
* ``TemplateRegistry.register``;
* assigning ``Engine.extensions`` or ``Engine.relation_specs``.

The engine settings (``templates``, ``discovery_budget``, ``transfer``,
``uninterpreted``, ``relevance``) are not part of the epoch:
they belong to one engine, and assigning a different value drops that
engine's caches only (``Engine._settings_changed``).

``lra_adapter.GENERIC_CONSTANTS`` does not bump: its process-wide memo is
keyed on the flag.  ``lra.BRANCH_BUDGET``, ``sympy_api.RELATIONAL``,
``sympy_api.CHECK_SEARCH``, ``sympy_api.CHECK_SEARCH_RELATIONS`` and
``lra_adapter._INTERPRETED_MAX`` are module constants, not settings.

Everything an engine keeps between queries records the epoch it was filled
under and is dropped by ``Engine._check_version`` when it differs; the
fact caches (``DictCache``) carry their own, so a cache shared between
engines, or handed to an engine created after a registration, is dropped
too.  The guard on the hot paths is one list index and one integer
comparison.  The epoch is global, not per registry, so a change on one
registry also drops the caches of engines using another; that is a
needless clear, never a stale answer.
"""
from __future__ import annotations

#: the current epoch, as a one-element list so the hot paths read it with
#: one index (``EPOCH[0]``)
EPOCH = [0]


def bump() -> int:
    """Start a new epoch; returns it."""
    EPOCH[0] += 1
    return EPOCH[0]
