"""satassume: one incremental SAT-based assumptions engine for SymPy."""
from .engine import Engine, InconsistentAssumptions, DictCache, ObjectCache
from .extensions import Extensions, register, unregister
from .formula import P, And, Or, Not, Implies, Equivalent, Exclusive, allargs, anyarg, exactlyonearg

__all__ = ["Engine", "InconsistentAssumptions", "DictCache", "ObjectCache", "P", "And", "Or",
           "Not", "Implies", "Equivalent", "Exclusive", "allargs", "anyarg", "exactlyonearg",
           "Extensions", "register", "unregister"]
__version__ = "0.1.0"
