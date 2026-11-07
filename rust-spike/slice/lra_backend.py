"""LRATheory on the rational Rust core, for rational sessions (issue 323, component 1a). `lra_adapter` stays Python and
calls this. Pure Python stays the default and the reference: nothing here runs unless `backend.install()` or
`rust_plugin.py` patches it in.

It is a subclass, for three reasons: `live.py` wraps hooks on the class, the call streams carry `cls.__name__`, and a
session that has to leave the core becomes the real Python theory by filling in `__dict__`.

A payload with constants moves its session to Python by state transfer (`_move`). That is temporary scaffolding, ruled
on by the planner with conditions: it's triggered by the payload's shape alone, a transfer that fails raises, and it's
deleted no later than component 1b (see ~/dev/architect/briefs/addenda/sa-port-1a-transfer-ruling.txt). Every other bad
input raises Python's exception here, with the same state left behind.

Test shims, not port: `__getattr__` and `_certificate` answer private reads and `certified` from a Python copy of the
state (`_view`). The engine reads neither.
"""
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
import sa_solver  # noqa: E402

from satassume.theories.lra import lra as _lra  # noqa: E402
from satassume.theories.lra.constfield import num  # noqa: E402
from satassume.theories.lra.lra import Integral, LRATheory as PyLRA, Negated, _ONE, _ZERO  # noqa: E402

#: The fields a Python copy of the state supplies; anything else missing is a plain AttributeError.
_STATE = frozenset(("_key", "_var_of", "_slack_of", "_forms", "_lo", "_up", "_lo_r", "_up_r", "_vq", "_vd", "_rows",
                    "_cols", "_atoms", "_ground", "_atoms_on", "_assigned", "_diseqs", "_ints", "_ints_on", "_int_lits",
                    "_trail", "_lims", "_dirty", "_pending_ground"))

counts = {"sessions": 0, "views": 0, "moved": 0}
#: One entry per moved session: (reason, call index, decision level).
moves = []


class _Move(Exception):
    """The payload has constants: this session leaves the core before the payload is handled."""


def _once(items):
    """A one-shot iterable, replayable: the payload may still have to go to Python. An exception from it comes back at
    the same place, after the same items."""
    seen = []
    try:
        for x in items:
            seen.append(x)
    except Exception as e:
        return _Replay(seen, e)
    return seen


class _Replay:
    def __init__(self, seen, exc):
        self.seen, self.exc = seen, exc

    def __iter__(self):
        yield from self.seen
        raise self.exc


class LRATheory(PyLRA):
    __doc__ = PyLRA.__doc__

    def __init__(self, eager: bool = True) -> None:
        d = self.__dict__
        d["eager"] = eager
        d["gave_up"] = False                    # the core never gives up: it has no constants
        d["_fields"] = False
        d["_cert"] = {}
        d["_cagg"] = None
        d["_int_memo"] = {}
        d["_tid"] = {}
        d["_terms"] = []
        d["_core"] = sa_solver.LraCore(eager)
        counts["sessions"] += 1

    def __setattr__(self, name, value):
        core = self.__dict__.get("_core")
        if core is not None:
            if name == "eager":
                core.eager = value
            elif name == "gave_up" or name in _STATE or name in ("_fields", "_cert", "_cagg", "_int_memo"):
                raise AttributeError(f"{name} can't be written on a session in the Rust core")
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in _STATE and self.__dict__.get("_core") is not None:
            return getattr(self._view(), name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # ------------------------------------------------------------------
    # what the engine and the tests read
    # ------------------------------------------------------------------

    @property
    def exhausted(self):
        core = self._core
        return self._py_exhausted if core is None else core.exhausted

    @exhausted.setter
    def exhausted(self, v):
        core = self._core
        if core is None:
            self.__dict__["_py_exhausted"] = v
        else:
            core.exhausted = v

    @property
    def branched_rational(self):
        core = self._core
        return self._py_branched if core is None else core.branched_rational

    @branched_rational.setter
    def branched_rational(self, v):
        if self._core is not None:
            raise AttributeError("branched_rational can't be written on a session in the Rust core")
        self.__dict__["_py_branched"] = v

    @property
    def stats(self):
        core = self._core
        return self._py_stats if core is None else core.stats

    def _certificate(self, values=None):
        if self._core is None:
            return PyLRA._certificate(self, values)
        return self._view()._certificate(values)

    # ------------------------------------------------------------------
    # hooks
    # ------------------------------------------------------------------

    def register_atom(self, literal, payload):
        core = self._core
        if core is None:
            return PyLRA.register_atom(self, literal, payload)
        if literal <= 0:
            raise ValueError("register_atom takes a positive literal")
        if core.registered(literal):
            raise ValueError(f"literal {literal} registered twice")
        n0 = len(self._terms)
        try:
            self._register(core, literal, payload)
        except _Move as m:
            self._forget(n0)
            self._move(m.args[0])
            return PyLRA.register_atom(self, literal, m.args[1])
        return None

    def assert_lit(self, literal):
        core = self._core
        return PyLRA.assert_lit(self, literal) if core is None else core.assert_lit(literal)

    def check(self):
        core = self._core
        return PyLRA.check(self) if core is None else core.check(_lra.BRANCH_BUDGET, self._terms)

    def propagate(self):
        core = self._core
        return PyLRA.propagate(self) if core is None else core.propagate()

    def push_level(self):
        core = self._core
        return PyLRA.push_level(self) if core is None else core.push_level()

    def pop_level(self):
        core = self._core
        return PyLRA.pop_level(self) if core is None else core.pop_level()

    # ------------------------------------------------------------------
    # payloads: `_register_atom`, in the same order, so that an exception comes from the same place
    # ------------------------------------------------------------------

    def _register(self, core, literal, payload):
        if isinstance(payload, Integral):
            terms, offset = payload
            ids, terms = self._pairs(terms, lambda t: Integral(t, offset))
            try:
                k = num(offset)
            except Exception:
                self._touch(core, ids)
                raise
            if type(k) is not Fraction:
                raise _Move("constant offset", Integral(terms, offset))
            core.register_integral(literal, k, ids)
            return
        negated = False
        while isinstance(payload, Negated):
            negated = not negated
            payload = payload.payload
        terms, constant, strict, equality = payload

        def rebuilt(t):
            p = (t, constant, strict, equality)
            return Negated(p) if negated else p
        ids, terms = self._pairs(terms, rebuilt)
        try:
            k = num(constant)
            if type(k) is not Fraction:
                raise _Move("constant", rebuilt(terms))
            eq = True if equality else False
            lt = False if eq else (True if strict else False)
        except _Move:
            raise
        except Exception:
            self._touch(core, ids)
            raise
        core.register_plain(literal, negated, lt, eq, k, ids)

    @staticmethod
    def _touch(core, ids):
        """`_lin` has run in Python when its number raises: its variables stay."""
        seen = {}
        for i, _ in ids:
            seen[i] = None
        core.touch(list(seen))

    def _pairs(self, terms, rebuilt):
        """`_lin`'s loop over the payload: `[(id, Fraction)]`, in payload order. New terms get an id here and are taken
        back if the payload doesn't reach the core, so that a term's first-seen object is the one Python keeps."""
        if not isinstance(terms, dict) and iter(terms) is terms:
            terms = _once(terms)
        items = terms.items() if isinstance(terms, dict) else terms
        tid, objs, out = self._tid, self._terms, []
        n0 = len(objs)
        try:
            for t, c in items:
                if type(c) is not Fraction:
                    c = num(c)
                    if type(c) is not Fraction:
                        raise _Move("constant coefficient", rebuilt(terms))
                i = tid.get(t)
                if i is None:
                    i = tid[t] = len(objs)
                    objs.append(t)
                out.append((i, c))
        except BaseException:
            self._forget(n0)
            raise
        return out, terms

    def _forget(self, n0):
        tid, objs = self._tid, self._terms
        for t in objs[n0:]:
            del tid[t]
        del objs[n0:]

    # ------------------------------------------------------------------
    # state: the same fields, orders and identities `LRATheory` has
    # ------------------------------------------------------------------

    def _state(self):
        s = self._core.dump()
        objs = self._terms

        def term(i):
            return objs[i]

        def fast(m, k):                         # `m is _ONE and k is _ZERO`: `_register_integral`'s fast path
            return (_ONE, _ZERO) if m == 1 and not k else (m, k)
        key = [None if i < 0 else term(i) for i in s["key"]]
        ints = {}
        for lit, v, m, k in s["ints"]:
            ints[lit] = (v, *fast(m, k))
        int_lits = [(v, *fast(m, k), lit) for v, m, k, lit in s["int_lits"]]
        return {
            "_key": key,
            "_var_of": {t: v for v, t in enumerate(key) if t is not None},
            "_slack_of": {tuple(form): v for form, v in s["slack_of"]},
            "_forms": {frozenset((term(i), c) for i, c in f): (v, c0) for f, v, c0 in s["forms"]},
            "_lo": s["lo"], "_up": s["up"], "_lo_r": s["lo_r"], "_up_r": s["up_r"],
            "_vq": s["vq"], "_vd": s["vd"],
            "_rows": {b: dict(r) for b, r in s["rows"]},
            "_cols": [set(c) for c in s["cols"]],
            "_atoms": {lit: (v, kind, c) for lit, v, kind, c in s["atoms"]},
            "_ground": dict(s["ground"]),
            "_atoms_on": s["atoms_on"],
            "_assigned": dict(s["assigned"]),
            "_diseqs": [tuple(x) for x in s["diseqs"]],
            "_ints": ints,
            "_ints_on": dict(s["ints_on"]),
            "_int_lits": int_lits,
            "_trail": s["trail"],
            "_lims": s["lims"],
            "_dirty": set(s["dirty"]),
            "_pending_ground": s["pending_ground"],
            "_py_exhausted": s["exhausted"],
            "_py_branched": s["branched_rational"],
            "_py_stats": s["stats"],
        }

    def _view(self):
        """A Python copy of the state: a test shim, for reads the engine doesn't make."""
        counts["views"] += 1
        v = object.__new__(type(self))
        v.__dict__.update(self._state(), _core=None, eager=self.eager, gave_up=False, _fields=False, _cert={},
                          _cagg=None, _int_memo={})
        return v

    def _move(self, reason):
        """This session becomes the real Python theory. If building the state fails nothing has changed and the
        exception goes up: there is no other state to carry on in."""
        core = self._core
        st = self._state()
        self.__dict__.update(st)
        self.__dict__["_core"] = None
        self.__dict__["_moved"] = (reason, core.calls, core.level)
        moves.append((reason, core.calls, core.level))
        counts["moved"] += 1


def install():
    """`lra.LRATheory` and the adapter's name become this class. Returns the undo."""
    from satassume.theories.lra import lra_adapter
    saved = _lra.LRATheory, lra_adapter.LRATheory
    _lra.LRATheory = lra_adapter.LRATheory = LRATheory

    def undo():
        _lra.LRATheory, lra_adapter.LRATheory = saved
    return undo
