"""LRATheory on the Rust core (issue 323, components 1a and 1b). `lra_adapter` stays Python and calls this. Pure Python
stays the default and the reference: nothing here runs unless `backend.install()` or `rust_plugin.py` patches it in.

It is a subclass, for two reasons: `live.py` wraps hooks on the class, and the call streams carry `cls.__name__`.

Every number runs in the core, constants included: there's no Python theory behind a session. `num` stays here, because
it reads input objects: an Element it makes crosses as `constfield.rs`'s `Num`. Every bad input raises Python's exception
with the same state left behind, and `Undecided` gives up at the same hook.

Test shim, not port: `__getattr__` serves private reads read-only from the core's state dump, with no theory behind them.
The engine reads none of them. `_certificate`, `certified`, `certified_with` and `rational_values` are the core's.
"""
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.environ.get("SLICE_SO") or os.path.dirname(os.path.abspath(__file__)))
import sa_solver  # noqa: E402

from satassume.theories.lra import lra as _lra  # noqa: E402
from satassume.theories.lra.constfield import Undecided  # noqa: E402
from satassume.theories.lra.lra import Integral as _PyIntegral, LRATheory as PyLRA, Negated as _PyNegated, _ONE, _ZERO  # noqa: E402
# Adapters step, part C: the Rust adapter's payloads (payloads.rs) and Python's, which tests and the pure-Python paths build.
Integral = (sa_solver.Integral, _PyIntegral)
Negated = (sa_solver.Negated, _PyNegated)

#: What the state dump supplies to a private read; anything else missing is a plain AttributeError.
_STATE = frozenset(("_key", "_var_of", "_slack_of", "_forms", "_lo", "_up", "_lo_r", "_up_r", "_vq", "_vd", "_rows",
                    "_cols", "_atoms", "_ground", "_atoms_on", "_assigned", "_diseqs", "_ints", "_ints_on", "_int_lits",
                    "_trail", "_lims", "_dirty", "_pending_ground", "_fields", "_int_memo"))

num = sa_solver.cf_num

counts = {"sessions": 0, "views": 0}


class _View:
    """The state dump as attributes: what `state.lra_text` and the test shim read. No theory behind it."""

    def __init__(self, fields):
        self.__dict__.update(fields)
        self.exhausted = fields["_py_exhausted"]
        self.branched_rational = fields["_py_branched"]
        self.stats = fields["_py_stats"]


class LRATheory(PyLRA):
    __doc__ = PyLRA.__doc__
    #: Adapters step, part C: `_register` reads the Rust adapter's payloads (payloads.rs), so it is given them.
    _rust_payloads = True

    def __init__(self, eager: bool = True) -> None:
        d = self.__dict__
        d["eager"] = eager
        d["_tid"] = {}
        d["_terms"] = []
        d["_core"] = sa_solver.LraCore(eager)
        counts["sessions"] += 1

    def __setattr__(self, name, value):
        if name == "eager":
            self._core.eager = value
        elif name == "gave_up" or name == "branched_rational" or name in _STATE or name in ("_cert", "_cagg"):
            raise AttributeError(f"{name} can't be written on a session in the Rust core")
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in _STATE:
            return self._view().__dict__[name]
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # ------------------------------------------------------------------
    # what the engine and the tests read
    # ------------------------------------------------------------------

    @property
    def exhausted(self):
        return self._core.exhausted

    @exhausted.setter
    def exhausted(self, v):
        self._core.exhausted = v

    @property
    def gave_up(self):
        return self._core.gave_up

    @property
    def branched_rational(self):
        return self._core.branched_rational

    @property
    def stats(self):
        return self._core.stats

    def _certificate(self, values=None):
        return self._core.certificate(values)

    def rational_values(self):
        return self._core.rational_values()

    # ------------------------------------------------------------------
    # hooks
    # ------------------------------------------------------------------

    def register_atom(self, literal, payload):
        core = self._core
        if core.gave_up:
            return None
        n0 = len(self._terms)
        try:
            if literal <= 0:
                raise ValueError("register_atom takes a positive literal")
            if core.registered(literal):
                raise ValueError(f"literal {literal} registered twice")
            self._register(core, literal, payload)
        except Undecided:
            core.give_up()
        except BaseException:
            # `_lin` raised before `_term_var`: no variable, so no first-seen object either
            if len(self._terms) > n0 and not core.has_term(n0):
                self._forget(n0)
            raise
        return None

    def assert_lit(self, literal):
        return self._core.assert_lit(literal)

    def check(self):
        return self._core.check(_lra.BRANCH_BUDGET, self._terms)

    def propagate(self):
        return self._core.propagate()

    def push_level(self):
        return self._core.push_level()

    def pop_level(self):
        return self._core.pop_level()

    # ------------------------------------------------------------------
    # payloads: `_register_atom`, in the same order, so that an exception comes from the same place
    # ------------------------------------------------------------------

    def _register(self, core, literal, payload):
        if isinstance(payload, Integral):
            terms, offset = payload
            ids = self._pairs(core, terms)
            try:
                k = num(offset)
            except Exception:
                if not core.touch(ids):
                    return
                raise
            core.register_integral(literal, k, ids)
            return
        negated = False
        while isinstance(payload, Negated):
            negated = not negated
            payload = payload.payload
        terms, constant, strict, equality = payload
        ids = self._pairs(core, terms)
        try:
            k = num(constant)
        except Exception:
            if not core.touch(ids):
                return
            raise
        try:
            eq = True if equality else False
            lt = False if eq else (True if strict else False)
        except Exception:
            if not core.touch(ids):
                return
            if type(k) is not Fraction:
                core.set_fields()
            raise
        core.register_plain(literal, negated, lt, eq, k, ids)

    def _pairs(self, core, terms):
        """`_lin`'s loop over the payload: `[(id, number)]`, in payload order. New terms get an id here and are taken
        back if the loop raises, so that a term's first-seen object is the one Python keeps."""
        items = terms.items() if isinstance(terms, dict) else terms
        tid, objs, out = self._tid, self._terms, []
        n0 = len(objs)
        try:
            for t, c in items:
                if type(c) is not Fraction:
                    c = num(c)
                    if type(c) is not Fraction:
                        core.set_fields()
                i = tid.get(t)
                if i is None:
                    i = tid[t] = len(objs)
                    objs.append(t)
                out.append((i, c))
        except BaseException:
            self._forget(n0)
            raise
        return out

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
            if type(m) is Fraction and type(k) is Fraction and m == 1 and not k:
                return _ONE, _ZERO
            return m, k
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
            "_fields": s["fields"],
            "_int_memo": {(v, *fast(m, k), lr, ur): (r if r is None else (r[0], r[1])) for (v, m, k, lr, ur), r in s["int_memo"]},
            "gave_up": s["gave_up"],
            "eager": self.eager,
            "_py_exhausted": s["exhausted"],
            "_py_branched": s["branched_rational"],
            "_py_stats": s["stats"],
        }

    def _view(self):
        """The state as attributes, read-only: a test shim, for reads the engine doesn't make."""
        counts["views"] += 1
        return _View(self._state())


def install():
    """`lra.LRATheory` and the adapter's name become this class. Returns the undo."""
    from satassume.theories.lra import lra_adapter
    saved = _lra.LRATheory, lra_adapter.LRATheory
    _lra.LRATheory = lra_adapter.LRATheory = LRATheory

    def undo():
        _lra.LRATheory, lra_adapter.LRATheory = saved
    return undo
