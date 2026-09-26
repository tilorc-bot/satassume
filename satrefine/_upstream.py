"""Alias of :mod:`satrefine.identities.compat.upstream` (the vendored refine dispatcher),
kept for phase 3 because tests still import it under this name.

This name is bound to the same module object in ``sys.modules``, so
``satrefine._upstream.ask = ...`` patches what the dispatcher and the handlers use.
"""
import sys

from .identities.compat import upstream as _upstream

sys.modules[__name__] = _upstream
