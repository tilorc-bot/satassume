"""Variant B: pickle with the shared objects pre-filled in the memo, so a load
runs no Python code.  dumps(root, shared_seed) -> (bytes, shared list); loads(...)"""
import io, struct, pickle, types, weakref
from satassume.state import clone as C
DEBUG = 0
class _Find(pickle.Pickler):
    def __init__(self, f, seed):
        super().__init__(f, protocol=3); self.found = {id(o): o for o in seed}
    def reducer_override(self, x):
        t = type(x)
        if t is weakref.ProxyType:
            return weakref.proxy, (x.__repr__.__self__,)
        C._kind(t); print("RO", t.__name__, flush=True) if DEBUG else None
        if t in C._SHARED or id(x) in self.found:
            self.found[id(x)] = x; return NotImplemented if isinstance(x, (type, types.FunctionType, types.BuiltinFunctionType)) else (int, ())
        return NotImplemented
class _Dump(pickle.Pickler):
    def reducer_override(self, x):
        if type(x) is weakref.ProxyType:
            return weakref.proxy, (x.__repr__.__self__,)
        return NotImplemented
def dumps(root, seed):
    f = _Find(io.BytesIO(), seed); f.dump(root)
    shared = list(f.found.values())
    b = io.BytesIO(); d = _Dump(b, protocol=3)
    d.memo = {id(o): (i, o) for i, o in enumerate(shared)}
    d.dump(root)
    prog = b"".join(b"P%d\nr" % i + struct.pack("<I", i) for i in range(len(shared))) + b"N."
    t = pickle.Unpickler(io.BytesIO(prog)); t.persistent_load = lambda pid: shared[int(pid)]; t.load()
    return b.getvalue(), t
def loads(data, t):
    u = pickle.Unpickler(io.BytesIO(data)); u.memo = t.memo; return u.load()
