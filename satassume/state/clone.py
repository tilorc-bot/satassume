"""A structural copy of a post-build context session (``Engine._build_context``).

Generic, not per class: every mutable object the session reaches is copied
(lists, dicts, sets, deques, bytearrays, bound methods, weak proxies and
instances of satassume's own classes, through ``__dict__`` and
``__slots__``), aliasing preserved by a memo as in :func:`copy.deepcopy`;
what is immutable or global is shared: numbers, strings, SymPy objects,
``P`` atoms and formulas, constant-field elements, the engine, classes and
functions, and tuples and frozensets of shared objects.  A new mutable
attribute is copied without any change here.  An object of a type this
module does not know raises ``TypeError``.
"""
import types
import weakref
from collections import deque
from fractions import Fraction

from sympy import Basic

from satassume.sat.formula import Formula, P
from satassume.sat.solver import _BlockClosure
from satassume.theories.lra.constfield import Element

#: shared by reference: immutable values, and the engine and the rule
#: blocks' closures (pure memos shared by every session, ``_rule_tables``)
_SHARED_BASES = (int, float, complex, str, bytes, type(None), Fraction, range,
                 type, types.FunctionType, types.BuiltinFunctionType,
                 types.ModuleType, Basic, P, Formula, Element, _BlockClosure)
_SHARED = set()     # exact types known to be shared
_KIND = {}          # exact type -> its copier


def _kind(t):
    k = _KIND.get(t)
    if k is None:
        if issubclass(t, _SHARED_BASES):
            _SHARED.add(t)
            k = _share
        elif t in _COPIERS:
            k = _COPIERS[t]
        elif issubclass(t, tuple):    # named tuples
            k = _tuple
        elif t.__module__.split(".")[0] == "satassume":
            k = _instance
        else:
            raise TypeError(f"clone: no copier for {t!r}")
        _KIND[t] = k
    return k


def clone(x, memo):
    """The copy of ``x``; ``memo`` maps ``id`` of each copied object to its
    copy (seed it with ``{id(o): o}`` to share an object ``o``, such as the
    engine)."""
    t = type(x)
    if t in _SHARED:
        return x
    y = memo.get(id(x))
    if y is None:
        y = _kind(t)(x, memo)
    return y


def _all_shared(xs):
    ts = set(map(type, xs))
    if ts <= _SHARED:
        return True
    for t in ts:
        _kind(t)
    return ts <= _SHARED


def _share(x, memo):
    return x


def _list(x, memo):
    y = memo[id(x)] = x.copy()
    if not _all_shared(x):
        y[:] = [clone(v, memo) for v in x]
    return y


def _dict(x, memo):
    y = memo[id(x)] = x.copy()
    if not _all_shared(x.values()) or not _all_shared(x):
        y.clear()
        for k, v in x.items():
            y[clone(k, memo)] = clone(v, memo)
    return y


def _set(x, memo):
    y = memo[id(x)] = x.copy()
    if not _all_shared(x):
        y.clear()
        y.update([clone(v, memo) for v in x])
    return y


def _tuple(x, memo):
    if _all_shared(x):
        return x                      # not memoized: cheap to test again
    y = memo[id(x)] = type(x)(clone(v, memo) for v in x) if type(x) in (tuple, frozenset) \
        else type(x)._make(clone(v, memo) for v in x)
    return y


def _deque(x, memo):
    y = memo[id(x)] = deque(maxlen=x.maxlen)
    y.extend([clone(v, memo) for v in x])
    return y


def _instance(x, memo):
    t = type(x)
    y = memo[id(x)] = t.__new__(t)
    if isinstance(x, list):           # list subclasses (solver.Clause)
        y.extend([clone(v, memo) for v in x])
    d = getattr(x, "__dict__", None)
    if d is not None:
        y.__dict__.update(_dict(d, memo) if d else ())
    for c in t.__mro__:
        for k in c.__dict__.get("__slots__", ()):
            if k != "__weakref__" and hasattr(x, k):
                object.__setattr__(y, k, clone(getattr(x, k), memo))
    return y


_COPIERS = {
    list: _list, dict: _dict, set: _set, tuple: _tuple, frozenset: _tuple,
    deque: _deque, bytearray: lambda x, memo: memo.setdefault(id(x), bytearray(x)),
    types.MethodType: lambda x, memo: memo.setdefault(
        id(x), types.MethodType(x.__func__, clone(x.__self__, memo))),
    # a proxy forwards attribute access: ``__repr__.__self__`` is its referent
    weakref.ProxyType: lambda x, memo: memo.setdefault(
        id(x), weakref.proxy(clone(x.__repr__.__self__, memo))),
}
