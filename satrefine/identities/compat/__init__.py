"""Code expected to change: SymPy workarounds, matrix special cases, ``ask`` backend routing,
and the vendored refine dispatcher (:mod:`.upstream`), which core reaches as ``core.hooks.dispatcher``."""
from ..core import hooks as _hooks
from . import backend as _backend
from . import upstream as _upstream

_hooks.dispatcher = _upstream
_hooks.whole = _backend.decides_whole
