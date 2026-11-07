"""Component 3's comparison tools: the per-call shadow, Python's state dump, and the quiet-handler count.

`ShadowTransfer` stands where `TransferTheory` does and runs Python's and Rust's side by side over the one EUF. Every
hook goes to both; the result and the full state of both are compared after each call. It always returns Python's
result, so a difference can't change the run that found it. It logs instead of raising: `engine.py:1906` and
`sympy_api.py:1107` would swallow an exception raised here, and a swallowed one looks like a lost answer. After a
theory's first difference its Rust side is stale, so that theory stops comparing and the difference is counted once.
"""
import collections
import json
import sys

from satassume.theories import transfer as _py

PyTransfer = _py.TransferTheory
stats = collections.Counter()
diffs = []
log = None    # an open file, or None
where = {"query": None}


def _j(xs):
    return " ".join(map(str, xs))


def dump_py(t):
    """The same field -> string dict as `TransferCore::dump` in `transfer.rs`."""
    return {
        "sel": str(t.sel),
        "enabled": str(int(t.enabled)),
        "ehist": _j(f"{l}:{int(b)}" for l, b in t._ehist),
        "rescan": str(int(t._rescan)),
        "atoms": _j(f"{v}:{a[0]}:{a[1]}" for v, a in sorted(t._atoms.items())),
        "by_term": _j(f"{m}{{" + ";".join(f"{p}=" + ",".join(map(str, vs)) for p, vs in d.items()) + "}"
                      for m, d in sorted(t._by_term.items())),
        "val": _j(f"{v}:{int(b)}" for v, b in sorted(t._val.items())),
        "trail": _j(t._trail),
        "lims": _j(t._lims),
        "dirty": _j(t._dirty),
        "dirty_p": _j(t._dirty_p),
        "fixed": _j(f"{m}{{" + ";".join(f"{p}={int(b)}" for p, b in f.items()) + "}"
                    for m, f in sorted(t._fixed.items())),
        "pterms": _j(f"{m}{{" + ",".join(map(str, s)) + "}" for m, s in sorted(t._pterms.items())),
        "multi": _j(t._multi),
        "sw": _j(f"{m}:{s[0]}:{s[1]}" for m, s in sorted(t._sw.items())),
        "onv": _j(f"{v}:{o[0]}:{o[1]}" for v, o in sorted(t._onv.items())),
        "on": _j(f"{v}:{int(b)}" for v, b in sorted(t._on.items())),
        "otrail": _j(t._otrail),
        "olims": _j(t._olims),
    }


def dump_of(t):
    """Either backend's state, or the Python side of a shadow."""
    if isinstance(t, ShadowTransfer):
        return dump_py(t.py)
    return dump_py(t) if isinstance(t, PyTransfer) else dict(t._dump())


def first_diff(a, b):
    return next((k for k in sorted(a) if a[k] != b.get(k)), None)


class ShadowTransfer:
    """See the module docstring. `rust_class` is set by `install`."""
    rust_class = None

    def __init__(self, euf):
        self.euf = euf
        self.py = PyTransfer(euf)
        self.rs = self.rust_class(euf)
        self.dead = False
        euf.on_merge = self._merged
        self._same("__init__", (), ("ok", None), ("ok", None))
        stats["theories"] += 1

    @property
    def sel(self):
        return self.py.sel

    @property
    def enabled(self):
        return self.py.enabled

    def _same(self, name, args, rp, rr):
        if self.dead:
            return
        stats["calls"] += 1
        stats["call " + name] += 1
        field = None
        if rp != rr:
            field = "result"
            detail = {"py": repr(rp)[:800], "rust": repr(rr)[:800]}
        else:
            dp, dr = dump_py(self.py), dict(self.rs._dump())
            field = first_diff(dp, dr)
            if field:
                detail = {"py": dp[field][:800], "rust": dr[field][:800]}
        if field is None:
            return
        self.dead = True
        stats["differences"] += 1
        d = dict(query=where["query"], hook=name, args=repr(args)[:300], field=field, **detail)
        diffs.append(d)
        if log:
            log.write(json.dumps(d) + "\n")
            log.flush()

    def _both(self, name, *args):
        try:
            rp = ("ok", getattr(self.py, name)(*args))
        except Exception as e:
            rp = ("raise", type(e).__name__, str(e))
        if self.dead:
            rr = rp
        else:
            try:
                rr = ("ok", getattr(self.rs, name)(*args))
            except KeyboardInterrupt:
                raise
            except BaseException as e:    # a Rust panic is a BaseException
                rr = ("raise", type(e).__name__, str(e))
        self._same(name, args, rp, rr)
        if rp[0] == "raise":
            raise getattr(__import__("builtins"), rp[1], RuntimeError)(rp[2])
        return rp[1]

    def _merged(self, ra, rb):
        return self._both("_merged", ra, rb)

    def guard(self, sel):
        return self._both("guard", sel)

    def switch(self, term, full, polar):
        return self._both("switch", term, full, polar)

    def set_fixed(self, term, facts):
        return self._both("set_fixed", term, list(facts))

    def register_atom(self, literal, payload):
        return self._both("register_atom", literal, payload)

    def assert_lit(self, literal):
        return self._both("assert_lit", literal)

    def check(self):
        return self._both("check")

    def propagate(self):
        return self._both("propagate")

    def decide(self):
        return self._both("decide")

    def push_level(self):
        return self._both("push_level")

    def pop_level(self):
        return self._both("pop_level")


QUIET = {"engine.py": (1890, 1920), "sympy_api.py": (1095, 1115)}
catches = collections.Counter()


def count_quiet_catches():
    """Count what the quiet handlers catch (`engine.py:1906`, `sympy_api.py:1107`), by file, line and exception type,
    with `sys.monitoring`, so neither handler is edited. Only these two windows, so unrelated handled exceptions cost
    a filter and nothing else."""
    mon = sys.monitoring
    tool = 4
    mon.use_tool_id(tool, "sa-port-17-quiet")

    def handled(code, offset, exc):
        name = code.co_filename.rsplit("/", 1)[-1]
        win = QUIET.get(name)
        if win and "satassume" in code.co_filename and win[0] <= code.co_firstlineno <= win[1] + 400:
            line = sys._getframe(1).f_lineno
            if win[0] <= line <= win[1]:
                catches[f"{name}:{line} {type(exc).__name__}"] += 1
    mon.register_callback(tool, mon.events.EXCEPTION_HANDLED, handled)
    mon.set_events(tool, mon.events.EXCEPTION_HANDLED)
