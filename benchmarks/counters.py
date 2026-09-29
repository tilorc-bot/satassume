"""How much the engine builds and does per query, as asv ``track_*`` counters.

Timings need a quiet machine and several rounds to show a 3% change; these
counts are exact (under a fixed ``PYTHONHASHSEED``, set in
``asv.conf.json``), so a commit that makes the engine instantiate more or
search more shows up at once.  They are not costs: moving the unary rules
from clauses into the rule block (``b9f2151``) cut ``clauses`` without
cutting the work, which is why ``clauses_with_rule_block`` counts the block
as the clauses it stands for.  A count going up is a question, not a
failure: a change that answers more queries may need more clauses.

Two workloads, each on a fresh ``Engine``:

* ``stream``: the refine stream (``~/.cache/satassume/stream.pkl`` or
  ``$SATASSUME_STREAM``, 13,877 recorded ``ask`` calls, the workload of
  ``tools/ab.py``), plus how many answers differ from the recording;
* ``families``: small groups of queries by the shape they exercise.

The counters are summed over every ``Solver`` and ``Session`` the workload
creates, read at the end:

* created: ``sessions``, ``nodes`` (visited expression nodes), ``vars``,
  ``clauses`` (problem clauses), ``rule_blocks`` (unary rule-block
  instances), ``clauses_with_rule_block``, ``learnts``;
* used: ``propagations`` (literals assigned), ``decisions``, ``conflicts``,
  ``escalations`` and ``searches`` (engine side).

SymPy is ``$SATASSUME_SYMPY`` or ``/home/tilo/sympy`` (the pin), as in
``tools/ab.py``.
"""
import os
import pickle
import sys
import time

sys.path.insert(0, os.environ.get("SATASSUME_SYMPY", "/home/tilo/sympy"))

STREAM = os.environ.get("SATASSUME_STREAM",
                        os.path.expanduser("~/.cache/satassume/stream.pkl"))

SOLVER_KEYS = ("vars", "clauses", "learnts", "rule_blocks",
               "propagations", "decisions", "conflicts")
ENGINE_KEYS = ("escalations", "searches")
METRICS = ("sessions", "nodes", "clauses_with_rule_block") + SOLVER_KEYS + ENGINE_KEYS


def families():
    from sympy import Abs, Q, Symbol, exp, log, sin, sqrt
    x, y, z, w = (Symbol(s) for s in "xyzw")
    r = Symbol("r", real=True)
    p = Symbol("p", positive=True)
    return {
        "add": [
            (Q.positive(y + 1), Q.positive(y)),
            (Q.positive(y + w**2 + z), Q.positive(y) & Q.real(w) & Q.nonnegative(z)),
            (Q.even(y + 1), Q.odd(y)),
            (Q.integer(x + y + z), Q.integer(x) & Q.even(y) & Q.odd(z)),
        ],
        "mul": [
            (Q.zero(y * w), Q.zero(y) & Q.finite(w)),
            (Q.real(y * w), Q.real(y) & Q.real(w)),
            (Q.negative(x * y * z), Q.positive(x) & Q.negative(y) & Q.positive(z)),
            (Q.nonzero(2 * x * y), Q.nonzero(x) & Q.nonzero(y)),
        ],
        "pow": [
            (Q.positive(((y**2 + 1)**w)**2), Q.real(y) & Q.real(w)),
            (Q.positive(exp(y)), Q.real(y)),
            (Q.real(sqrt(x)), Q.nonnegative(x)),
            (Q.rational(x**2), Q.rational(x)),
        ],
        "functions": [
            (Q.real(sin(x)), Q.real(x)),
            (Q.positive(Abs(x) + 1), True),
            (Q.real(log(x)), Q.positive(x)),
            (Q.nonnegative(exp(x) + Abs(y)), Q.real(x)),
        ],
        "compound": [
            (Q.positive(y) | Q.negative(y), Q.real(y) & Q.nonzero(y)),
            (Q.positive(x * y) & Q.real(x + y), Q.positive(x) & Q.positive(y)),
        ],
        "relations": [
            (Q.positive(x - y), Q.gt(x, y)),
            (Q.negative(x), Q.lt(x, y) & Q.negative(y)),
            (Q.positive(y), Q.eq(x, y) & Q.positive(x)),
            (Q.positive(x + y), Q.gt(x, 1) & Q.gt(y, -1)),
        ],
        "context_free": [
            (Q.positive(r**2 + 1), True),
            (Q.real(exp(r) + r**3), True),
            (Q.positive(p * exp(r) + p**2), True),
            (Q.finite(sin(r) + p), True),
        ],
        # many questions under one assumption set: the reused session
        "reuse": [(q(e), Q.positive(x) & Q.negative(y) & Q.integer(z))
                  for e in (x, y, z, x + y, x * y, x * y * z, x**2 + z**2, x - y, z + 1)
                  for q in (Q.positive, Q.negative, Q.real, Q.integer, Q.nonzero)],
    }


_SEEN = {"solvers": [], "sessions": []}


def _instrument():
    """Patch ``Solver`` and ``Session`` (where they exist) so every instance
    lands in ``_SEEN``."""
    import importlib
    for mod, name, key in (("satassume.solver", "Solver", "solvers"),
                           ("satassume.engine", "Session", "sessions")):
        try:
            cls = getattr(importlib.import_module(mod), name)
        except (ImportError, AttributeError):
            continue
        if getattr(cls, "_asv_patched", False):
            continue
        orig = cls.__init__

        def init(self, *a, _orig=orig, _key=key, **k):
            _orig(self, *a, **k)
            _SEEN[_key].append(self)
        cls.__init__ = init
        cls._asv_patched = True


def answer(queries):
    """Answer ``queries`` (``(prop, assumptions)`` pairs) on a fresh engine;
    return ``(answers, engine)``.  Any exception a query raises is recorded
    as the answer ``"error"``, so one failing query does not lose the run."""
    from satassume.engine import Engine
    from satassume import sympy_api
    eng = Engine()
    if hasattr(sympy_api, "set_default_engine"):
        sympy_api.set_default_engine(eng)
        ask = sympy_api.ask
    else:
        def ask(p, a):
            return sympy_api.ask(p, a, engine=eng)
    answers = []
    for p, a in queries:
        try:
            answers.append(ask(p, a))
        except Exception:
            answers.append("error")
    return answers, eng


def _stats(obj):
    """``obj.stats`` as a dict, called if it is a method; {} if absent."""
    st = getattr(obj, "stats", None)
    if callable(st):
        try:
            st = st()
        except Exception:
            return {}
    return st if isinstance(st, dict) else {}


def run(queries):
    """``(answers, counters)`` for ``queries`` on a fresh engine.

    A counter the engine no longer exposes (a renamed stats key, a removed
    attribute) is NaN, which asv records as a missing value, so the other
    counters of that commit are kept; the counters rely on internals
    (``Solver.stats()``, ``Session.base``, ``Engine.stats``) by design."""
    nan = float("nan")
    _instrument()
    _SEEN["solvers"].clear()
    _SEEN["sessions"].clear()
    answers, eng = answer(queries)
    solvers, sessions = _SEEN["solvers"], _SEEN["sessions"]
    stats = [_stats(s) for s in solvers]
    c = {}
    for k in SOLVER_KEYS:
        have = [st[k] for st in stats if k in st]
        c[k] = sum(have) if have or not solvers else nan
    c["clauses_with_rule_block"] = nan if c["clauses"] != c["clauses"] else (
        c["clauses"] + sum(getattr(s, "_rb_nclauses", 0) for s in solvers))
    c["sessions"] = len(sessions) if sessions or not solvers else nan
    c["nodes"] = (sum(len(s.base) for s in sessions)
                  if all(hasattr(s, "base") for s in sessions) else nan)
    est = _stats(eng)
    for k in ENGINE_KEYS:
        c[k] = est.get(k, nan)
    return answers, c


def load_stream():
    with open(STREAM, "rb") as f:
        return pickle.load(f)


def _track_stream(name):
    def f(self, counters):
        return counters["stream"][name]
    f.__name__ = "track_" + name
    f.unit = name
    return f


def _track_family(name):
    def f(self, counters, family):
        return counters[family][name]
    f.__name__ = "track_" + name
    f.unit = name
    return f


class Stream:
    """The refine stream, one cold pass."""

    timeout = 600

    def setup_cache(self):
        stream = load_stream()
        answers, c = run([(p, a) for p, a, _ in stream])
        c["mismatches"] = sum(1 for got, (_, _, r) in zip(answers, stream) if got is not r)
        c["more_definite"] = sum(1 for got, (_, _, r) in zip(answers, stream)
                                 if r is None and (got is True or got is False))
        return {"stream": c}

    def track_mismatches(self, counters):
        """Answers that differ from the recording (more definite ones included)."""
        return counters["stream"]["mismatches"]
    track_mismatches.unit = "answers"

    def track_more_definite(self, counters):
        """None in the recording, True/False now."""
        return counters["stream"]["more_definite"]
    track_more_definite.unit = "answers"


class Families:
    """Small query groups by shape, each on a fresh engine."""

    timeout = 600

    params = list(families())
    param_names = ["family"]

    def setup_cache(self):
        return {name: run(qs)[1] for name, qs in families().items()}


for _m in METRICS:
    setattr(Stream, "track_" + _m, _track_stream(_m))
    setattr(Families, "track_" + _m, _track_family(_m))


class StreamTime:
    """Wall time of one cold pass of the refine stream (fresh process each)."""

    processes = 3
    repeat = 1
    number = 1
    warmup_time = 0
    timeout = 600

    def setup(self):
        self.stream = [(p, a) for p, a, _ in load_stream()]
        from satassume.sympy_api import ask  # noqa: F401  (import outside the timing)

    def time_stream(self):
        answer(self.stream)
