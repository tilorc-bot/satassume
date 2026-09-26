"""Generated rule tables, one module per family, written by
``satrefine/tools/refine_specialize.py --write`` and never edited by hand.

Each module is a plain rule table (a ``RULES`` list of ``(lhs, rhs,
hypothesis)`` rows and literal ``handlers_dict['key'] = rule_handler(RULES)``
assignments), the same format a hand-written rule family uses, except that
``handlers_dict`` here is :data:`satrefine.handlers_identities._dispatch.generated_handlers`.
The dispatcher prefers a generated handler for a key when
``SATREFINE_IDENTITIES`` is ``generated`` (the default) and falls back to
the live identity handler otherwise; ``SATREFINE_IDENTITIES=live`` ignores
the generated tables.  ``tests/refine_identities/test_generated.py`` checks
that regenerating gives the committed modules.
"""
from __future__ import annotations

import importlib
import pkgutil

for _info in pkgutil.iter_modules(__path__):
    if not _info.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_info.name}")
