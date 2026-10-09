"""satassume: one incremental SAT-based assumptions engine for SymPy."""
from . import _compat
_compat.install()   # first: transitional aliases of the old flat module names

from .engine import Engine, InconsistentAssumptions, DictCache, ObjectCache
from .knowledge.extensions import Extensions, register, unregister
from .sat.formula import P, And, Or, Not, Implies, Equivalent, Exclusive, allargs, anyarg, exactlyonearg

__all__ = ["Engine", "InconsistentAssumptions", "DictCache", "ObjectCache", "P", "And", "Or",
           "Not", "Implies", "Equivalent", "Exclusive", "allargs", "anyarg", "exactlyonearg",
           "Extensions", "register", "unregister"]
__version__ = "0.0.1"


def __getattr__(name):
    """``satassume.rules`` and the other old flat module names
    (:data:`satassume._compat.ALIASES`), with a DeprecationWarning."""
    return _compat.package_getattr(name)
