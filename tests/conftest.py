"""Shared pytest configuration, and the randomized runs of issue #96.

One seed decides every random choice of a run: ``SATASSUME_SEED`` from the
environment, otherwise one draw per run (handed to the pytest-xdist
workers), printed in the header and in the summary.

* Test order: the modules are shuffled, then the classes of a module and
  the tests of a class (the order pytest-randomly uses);
  ``--satassume-no-shuffle`` keeps the file order.  Every ``ask`` of the
  suite goes through one shared default engine, so an answer that changes
  with the order depends on what was asked before.
* ``--satassume-pad=RATE`` (opt-in): with probability RATE, a call of
  ``satassume.sympy_api.ask`` gets one to three conjuncts added to its
  assumptions (:data:`PAD_TEMPLATES`, :data:`PAD_RELATIONS`).  Each conjunct has symbols of its
  own, shared with neither the query nor the other conjuncts, and is
  satisfiable by itself, so the padded set is consistent exactly when the
  original is.  The answer, or the exception, must not change (I2 of
  ``harness/INVARIANTS.md``).  Not padded: the asks of a test marked
  ``no_pad`` (it asserts on what the engine did, such as counters, memo
  sizes or search conflicts, which unrelated conjuncts change), and asks
  on an engine with a stand-in theory of ``tests/theory_harness.py``
  (its conflict clause negates everything asserted, so the search grows
  exponentially with unrelated atoms), and asks on an engine with
  ``relevance=False`` or a discovery budget below the default: there the
  budget weighs the whole set, unrelated conjuncts included, by design
  (``tests/test_budget_cone.py``, H2's residual, issue #72).  A test marked
  ``no_pad_relations(reason)`` gets only :data:`PAD_TEMPLATES`: one
  unrelated relation makes a wide shape search (issue #260; same answer,
  but a sum of 160 terms takes minutes).  A test marked ``pad_xfail(issue)``
  fails under padding for that open issue and is expected to
  (``xfail``, not strict) when this option is on.
* ``--satassume-evict=RATE`` (opt-in): with probability RATE, the default
  engine drops every memo (``Engine.memos.clear()``) before a call of
  ``ask``.  The answer must not change.

The draws of a test come from generators seeded by the seed and the test's
node id, so a failing test reruns with the same padding and evictions on
its own (``SATASSUME_SEED=N pytest --satassume-pad=R tests/f.py::test``).
A failure that also depends on the tests run before it reproduces with
the same seed and options over the whole suite, without ``-n`` (xdist
hands tests to workers by timing, not by the seed).
"""
import functools
import os
import random

import pytest

#: one conjunct each, over two fresh symbols; the comment is a witness
#: that satisfies it
PAD_TEMPLATES = (
    lambda Q, a, b: Q.positive(a),                       # a = 1
    lambda Q, a, b: Q.negative(a),                       # a = -1
    lambda Q, a, b: Q.even(a),                           # a = 2
    lambda Q, a, b: Q.prime(a),                          # a = 2
    lambda Q, a, b: Q.irrational(a),                     # a = sqrt(2)
    lambda Q, a, b: Q.imaginary(a),                      # a = I
    lambda Q, a, b: ~Q.zero(a),                          # a = 1
    lambda Q, a, b: Q.integer(a) & ~Q.positive(a),       # a = 0
    lambda Q, a, b: Q.positive(a + b),                   # a = b = 1
    lambda Q, a, b: Q.integer(a * b) & Q.real(b),        # a = b = 1
    lambda Q, a, b: Q.nonnegative(a**2 - b),             # a = b = 0
    lambda Q, a, b: Q.finite(1 / a),                     # a = 1
    lambda Q, a, b: Q.even(a) >> Q.negative(b),          # a = 1
    lambda Q, a, b: Q.real(a) | Q.zero(b),               # a = 0
    lambda Q, a, b: Q.positive(a) & Q.rational(b),       # a = b = 1
)

#: the same for relations, used only on an engine with the LRA adapter: a
#: relation no adapter reads makes the answer None by design
#: (``sympy_api.ask``, "Opaque conjuncts")
PAD_RELATIONS = (
    lambda Q, a, b: a > b,                               # a = 1, b = 0
    lambda Q, a, b: (a <= 3) & Q.integer(a),             # a = 0
)

#: the fresh symbols are ``Symbol(PAD_PREFIX + str(i))``; a query naming
#: one is never padded
PAD_PREFIX = "_satassume_pad"


class _Random:
    seed = 0
    pad = 0.0
    evict = 0.0
    #: the running test is marked ``no_pad``
    unpadded = False
    #: the running test is marked ``no_pad_relations``
    no_relations = False
    pad_rng = random.Random(0)
    evict_rng = random.Random(0)

    @classmethod
    def start(cls, nodeid: str) -> None:
        cls.pad_rng = random.Random(f"{cls.seed}:pad:{nodeid}")
        cls.evict_rng = random.Random(f"{cls.seed}:evict:{nodeid}")


def _rate(s: str) -> float:
    r = float(s)
    if not 0 <= r <= 1:
        raise pytest.UsageError(f"a rate is between 0 and 1, not {s}")
    return r


def pytest_addoption(parser):
    g = parser.getgroup("satassume", "randomized runs (issue #96; seed: SATASSUME_SEED)")
    g.addoption("--satassume-no-shuffle", action="store_true",
                help="run the tests in file order")
    g.addoption("--satassume-pad", type=_rate, default=0.0, metavar="RATE",
                help="pad the assumptions of this fraction of ask calls with unrelated conjuncts")
    g.addoption("--satassume-evict", type=_rate, default=0.0, metavar="RATE",
                help="drop the default engine's memos before this fraction of ask calls")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long-running test, skipped unless enabled by an environment variable")
    config.addinivalue_line("markers", "no_pad(reason): --satassume-pad leaves the asks of this test alone")
    config.addinivalue_line("markers", "no_pad_relations(reason): --satassume-pad adds no relations to the asks of this test")
    config.addinivalue_line("markers", "pad_xfail(issue): expected to fail under --satassume-pad, for that issue")
    worker = getattr(config, "workerinput", None)
    if worker is not None:
        seed = worker["satassume_seed"]
    elif os.environ.get("SATASSUME_SEED"):
        try:
            seed = int(os.environ["SATASSUME_SEED"])
        except ValueError:
            raise pytest.UsageError(f"SATASSUME_SEED is an integer, not {os.environ['SATASSUME_SEED']!r}")
    else:
        seed = random.SystemRandom().randrange(1, 10**6)
    _Random.seed = seed
    _Random.pad = config.getoption("satassume_pad")
    _Random.evict = config.getoption("satassume_evict")
    _Random.start("<collect>")
    try:
        from hypothesis import core
    except ImportError:
        pass
    else:
        # the examples of the @given tests, and so the asks they make, follow
        # the seed too (unless --hypothesis-seed says otherwise)
        if config.getoption("hypothesis_seed", None) is None:
            core.global_force_seed = seed
    if _Random.pad or _Random.evict:
        _install()


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    node.workerinput["satassume_seed"] = _Random.seed


def _settings(config) -> str:
    order = "file order" if config.getoption("satassume_no_shuffle") else "shuffled"
    return (f"SATASSUME_SEED={_Random.seed} (order: {order}, "
            f"pad: {_Random.pad:g}, evict: {_Random.evict:g}; "
            f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED', 'random')})")


def pytest_report_header(config):
    return f"satassume: {_settings(config)}"


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.write_line(f"satassume: {_settings(config)}")


def pytest_collection_modifyitems(session, config, items):
    if _Random.pad:
        for item in items:
            m = item.get_closest_marker("pad_xfail")
            if m is not None:
                item.add_marker(pytest.mark.xfail(
                    reason=f"padded assumptions change the answer: issue #{m.args[0]}", strict=False))
    if config.getoption("satassume_no_shuffle"):
        return
    rng = random.Random(f"{_Random.seed}:order")
    modules: dict = {}
    for item in items:
        cls = getattr(item, "cls", None)
        modules.setdefault(item.nodeid.split("::")[0], {}).setdefault(
            cls.__qualname__ if cls else None, []).append(item)
    order = list(modules.values())
    rng.shuffle(order)
    items[:] = []
    for classes in order:
        groups = list(classes.values())
        rng.shuffle(groups)
        for group in groups:
            rng.shuffle(group)
            items.extend(group)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    _Random.start(item.nodeid)
    _Random.unpadded = item.get_closest_marker("no_pad") is not None
    _Random.no_relations = item.get_closest_marker("no_pad_relations") is not None


def _install() -> None:
    """Replace ``satassume.sympy_api.ask`` by the padding and evicting
    wrapper (before the test modules import it)."""
    import inspect

    import satassume.sympy_api as api
    from sympy import And, Q, Symbol
    from sympy.logic.boolalg import Boolean

    original = api.ask
    budget = inspect.signature(api.Engine).parameters["discovery_budget"].default
    syms = [Symbol(f"{PAD_PREFIX}{i}") for i in range(6)]

    def names(e):
        return {s.name for s in getattr(e, "free_symbols", ())}

    def templates(proposition, assumptions, engine):
        """The templates to pad this call with; None: not padded."""
        if _Random.unpadded or not (assumptions is True or isinstance(assumptions, Boolean)):
            return None
        eng = engine if engine is not None else api.default_engine()
        specs = eng.relation_specs
        if (not eng.relevance or eng.discovery_budget < budget
                or any(getattr(s.factory, "__module__", None) == "theory_harness" for s in specs)
                or any(s.startswith(PAD_PREFIX) for s in names(proposition) | names(assumptions))):
            return None
        if _Random.no_relations or not any(s.name == "lra" for s in specs):
            return PAD_TEMPLATES
        return PAD_TEMPLATES + PAD_RELATIONS

    @functools.wraps(original)
    def ask(proposition, assumptions=True, engine=None, **kwargs):
        if _Random.evict and _Random.evict_rng.random() < _Random.evict:
            api.default_engine().memos.clear()
        if _Random.pad and _Random.pad_rng.random() < _Random.pad:
            rng = _Random.pad_rng
            # the same draws whether or not the call is padded
            picks = [rng.random() for _ in range(rng.randint(1, 3))]
            pool = templates(proposition, assumptions, engine)
            if pool is not None:
                pad = [pool[int(r * len(pool))](Q, syms[2 * k], syms[2 * k + 1])
                       for k, r in enumerate(picks)]
                assumptions = And(*pad) if assumptions is True else And(assumptions, *pad)
        return original(proposition, assumptions, engine, **kwargs)

    api.ask = ask
