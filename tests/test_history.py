"""History independence of ``ask``: the pytest entry point of ``harness/``.

Every answer of ``satassume.sympy_api.ask`` must be a function of the
query, the assumptions, the engine configuration and the registered
extensions only: never of earlier queries, caches, eviction or
``PYTHONHASHSEED``.  These tests run query streams through one long-lived
engine and compare every answer with a fresh engine (``harness.checker``).

Two parts:

* **fast** (every push, about 10 s): the pinned repros, one strict xfail
  per file in ``harness/repros`` (none left since #53 stage 5), and the
  fixed ones in ``harness/repros/fixed``, which must keep agreeing; the
  CI-sized ``links``, ``transfer`` and ``registry`` profile runs, which
  must find nothing (since stage 5 and #63); the planted-defect tests
  showing the checker, ddmin and the stream orders work; the inventory of
  module-level state.
* **slow** (marked ``slow``, run with ``HISTORY_SLOW=1``, nightly in
  ``.github/workflows/history-fuzz.yml``): random streams over several
  configurations and orders, the other profiles, the cache audit, a
  module-level reference sample, Hypothesis streams (derandomized) and
  the recorded corpus (if ``queries.jsonl`` exists).

``HISTORY_EXAMPLES`` sets the Hypothesis example count (default 15),
``HISTORY_SEEDS`` the number of random seeds (default 2).
``HISTORY_IGNORE`` is a comma-separated list of discrepancy kinds
(``contradiction``, ``none-vs-definite``, ``raise-vs-definite``,
``raise-vs-none``, ``error``) that do not fail the tests.  Every
discrepancy found is written to ``harness-results/pytest/`` as a repro.

Known families.  The engine has documented history-dependent answers
(``harness/repros/README.md``).  Every discrepancy is attributed to the
engine state that carries it and tagged with a family
(``harness.checker.family_of``, a heuristic); the stream tests fail only
on a tag that ``harness.checker.is_known_family`` does not accept
(``HISTORY_STRICT=1`` fails on every discrepancy).  The known families
themselves are pinned by the strict xfails below: a fix turns an item into
an XPASS failure, which says to drop the repro file or the marker.
"""
import glob
import json
import os

import pytest

sympy = pytest.importorskip("sympy")
hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings  # noqa: E402
from sympy import Q, Symbol  # noqa: E402

from harness import registry as reg  # noqa: E402
from harness.checker import (Ask, Checker, Discrepancy, ReferenceLevel, execute,  # noqa: E402
                             is_known_family, order_stream, shrink)
from harness.generators import random_stream, stream_strategy  # noqa: E402
from harness.state import (MODULE_CONFIG, MODULE_CONSTANTS, MODULE_STATE, PRESETS,  # noqa: E402
                           inventory, preset, reset_module_state)

N_EXAMPLES = int(os.environ.get("HISTORY_EXAMPLES", "15"))
N_SEEDS = int(os.environ.get("HISTORY_SEEDS", "2"))
IGNORE = [k for k in os.environ.get("HISTORY_IGNORE", "").split(",") if k]
STRICT = bool(os.environ.get("HISTORY_STRICT"))
SLOW = bool(os.environ.get("HISTORY_SLOW"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "harness-results", "pytest")
CORPUS = os.path.join(ROOT, "queries.jsonl")
#: the pinned repros (``HISTORY_REPROS``: another directory, for
#: test_pinned_repro_fails_on_another_outcome)
REPROS = os.environ.get("HISTORY_REPROS") or os.path.join(ROOT, "harness", "repros")

slow = pytest.mark.slow
needs_slow = pytest.mark.skipif(not SLOW, reason="slow history streams: set HISTORY_SLOW=1")


def _known(fam: str, audit: bool = False) -> bool:
    return is_known_family(fam, audit=audit) and not STRICT


def _check(cfg, items, orders, seed=0, **kw):
    """Run the checker; fail with the shrunk repros of every discrepancy
    of an unknown family (all of them under ``HISTORY_STRICT``)."""
    from harness.checker import write_repro
    rep = Checker(cfg, ReferenceLevel.ENGINE, orders, seed=seed, ignore_kinds=IGNORE, **kw).run(items)
    lines = []
    for i, d in enumerate(rep.discrepancies):
        fam = d.confirmations.get("family", "?")
        seq = d.shrunk if d.shrunk is not None else d.prefix
        _, path = write_repro(d, OUT, f"{cfg.name}-s{seed}-{i}")
        if _known(fam):
            print(f"known family {fam}: {d.summary()} (repro: {path})")
            continue
        lines.append(d.summary())
        lines.append("  minimal prefix: " + "; ".join(str(i) for i in seq))
        lines.append("  repro: " + path)
    if lines:
        pytest.fail(f"history-dependent answers of an unknown family (kinds {rep.kinds}):\n"
                    + "\n".join(lines))
    return rep


# ==========================================================================
# fast part: every push
# ==========================================================================

# -- the state inventory ------------------------------------------------------

def test_module_state_inventory_is_classified():
    """Every module-level container of the engine is a known memo (reset by
    ``reset_module_state``), a constant, an intern table, or configuration.
    A cache added later shows up here.  Every module is imported first, so
    the result does not depend on what earlier tests loaded."""
    from harness.state import MODULE_INTERNED, import_all
    import_all()
    known = set(MODULE_STATE) | MODULE_CONSTANTS | MODULE_CONFIG | MODULE_INTERNED
    unknown = [(m, a, t) for m, a, t in inventory() if (m, a) not in known]
    assert not unknown, f"unclassified module-level state: {unknown}"
    reset_module_state()


# -- the documented repros still reproduce (strict xfail: a fix is an XPASS) ---

#: family of a repro file whose name does not start with it; issue filed
#: for a family
FAMILY = {"C6b": "C'", "E1c": "E", "Gp1": "G'", "Gp2": "G'", "S1": "S"}
ISSUES = {"G": "#42", "G'": "#42", "C": "#47", "E": "#53", "S": "#53"}


def _repro_params():
    out = []
    for path in sorted(glob.glob(os.path.join(REPROS, "*.json"))):
        name = os.path.basename(path)[:-5]
        tag = name.split("-")[0]
        fam = FAMILY.get(tag) or tag.rstrip("0123456789b")
        issue = ISSUES.get(fam)
        reason = (f"known history dependence, family {fam}"
                  + (f" ({issue})" if issue else "") + ": harness/repros/README.md")
        out.append(pytest.param(path, id=name,
                                marks=pytest.mark.xfail(strict=True, raises=AssertionError,
                                                        reason=reason)))
    return out


def _replay(path):
    """The recorded repro at ``path`` and the last row of its replay: the
    final query in the engine after the prefix (``warm``) and in a fresh
    engine (``ref``)."""
    from harness.checker import item_from_json
    from harness.state import EngineConfig
    with open(path) as fh:
        d = json.load(fh)
    cfg = EngineConfig.from_dict(d["config"])
    items = [item_from_json(i) for i in d["prefix"]] + [item_from_json(d["item"])]
    rows, _ = execute(items, cfg, ReferenceLevel.NONE, ref_for_last=True)
    return d, rows[-1]


def _fail_on_error(warm, ref):
    """An engine error (``Error:<Type>``) is a defect of its own, never the
    expected failure: ``pytest.fail`` is not an AssertionError, so a strict
    xfail with ``raises=AssertionError`` reports it as a failure."""
    if warm.startswith("Error:") or ref.startswith("Error:"):
        pytest.fail(f"engine error: engine {warm}, fresh {ref}")


@pytest.mark.parametrize("path", _repro_params())
def test_repro_still_reproduces(path):
    """The minimal prefix still makes the long-lived engine answer the
    final query differently from a fresh one, with exactly the recorded
    pair of answers.  Strict xfail: once the engine answers the same, the
    item XPASSes and fails; drop the file (or move it to ``fixed/``).  Any
    other outcome (an engine error, another disagreement) is a failure,
    not the expected one."""
    d, last = _replay(path)
    _fail_on_error(last.warm, last.ref)
    if last.warm != last.ref and (last.warm, last.ref) != (d["warm"], d["ref"]):
        pytest.fail(f"another disagreement than the recorded one: engine {last.warm}, "
                    f"fresh {last.ref} (recorded {d['warm']} / {d['ref']})")
    assert last.warm == last.ref, (f"engine {last.warm}, fresh {last.ref} "
                                   f"(recorded {d['warm']} / {d['ref']})")


_PLANT = """
import os

import pytest


@pytest.fixture(autouse=True)
def _plant(monkeypatch):
    # the first engine to answer is the long-lived one; its second answer
    # (the final query of the one-query-prefix repro used here) crashes or
    # has True and False swapped
    import harness.outcomes as o
    orig, how, warm = o._ask, os.environ["HISTORY_PLANT"], {}

    def _ask():
        f = orig()

        def ask(prop, assum, engine):
            warm.setdefault("engine", engine)
            if engine is warm["engine"]:
                warm["n"] = warm.get("n", 0) + 1
                if warm["n"] > 1:
                    if how == "crash":
                        raise RuntimeError("planted crash")
                    r = f(prop, assum, engine)
                    return (not r) if (r is True or r is False) else r
            return f(prop, assum, engine)
        return ask

    monkeypatch.setattr(o, "_ask", _ask)
"""


@pytest.mark.parametrize("how", ["crash", "flip"])
def test_pinned_repro_fails_on_another_outcome(how, tmp_path):
    """The strict xfail of a pinned repro accepts only its recorded pair:
    with the long-lived engine made to crash (``Error:RuntimeError``) or to
    flip its True into False on the final query, the pinned test fails
    instead of xfailing.  The repro is G1 from ``fixed/`` pinned again in a
    temporary directory (every pinned repro is fixed since #53 R2 and stage 5):
    its recorded pair is True/None, both engines now answer True."""
    import shutil
    import subprocess
    import sys
    name = "G1-links-lra-linear-relative"
    src = os.path.join(ROOT, "harness", "repros", "fixed", name + ".json")
    with open(src) as fh:
        d = json.load(fh)
    assert (d["warm"], d["ref"]) == ("True", "None") and len(d["prefix"]) == 1
    pinned = tmp_path / "repros"
    pinned.mkdir()
    shutil.copy(src, pinned / (name + ".json"))
    (tmp_path / "history_plant.py").write_text(_PLANT)
    env = dict(os.environ, HISTORY_PLANT=how, HISTORY_REPROS=str(pinned),
               PYTHONPATH=os.pathsep.join([str(tmp_path), ROOT, os.environ.get("PYTHONPATH", "")]))
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "-p", "history_plant", "-rf",
                          f"tests/test_history.py::test_repro_still_reproduces[{name}]"],
                         capture_output=True, text=True, cwd=ROOT, env=env, timeout=600)
    tail = out.stdout[-3000:] + out.stderr[-3000:]
    assert out.returncode == 1, tail
    assert "1 failed" in out.stdout and "xfailed" not in out.stdout, tail
    want = "engine error" if how == "crash" else "another disagreement than the recorded one: engine False"
    assert want in out.stdout, tail


def test_repros_are_pinned():
    # 15 before B, B2 and E1c (the complete set check, #73), E1, E1b,
    # L1, C6b and D (the writeback rule, #53 stage 3), T1, T3-T5 and Gp1
    # (component-scoped answering, #53 R2), then G7, Gp2 and S1 (switched
    # glue, #53 stage 5) moved to fixed/; a new pinned repro comes with its
    # standalone script
    for path in glob.glob(os.path.join(REPROS, "*.json")):
        assert os.path.exists(path[:-5] + ".py"), f"no standalone script for {path}"


@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(REPROS, "fixed", "*.json"))),
                         ids=lambda p: os.path.basename(p)[:-5])
def test_fixed_repro_stays_fixed(path):
    """A repro whose history dependence was fixed (``harness/repros/fixed``):
    the long-lived engine and a fresh one must keep agreeing, on an answer
    (an engine error on either side fails too)."""
    _, last = _replay(path)
    _fail_on_error(last.warm, last.ref)
    assert last.warm == last.ref, (last.warm, last.ref)


def test_generated_streams_do_not_depend_on_the_hash_seed():
    """The CI-sized streams are the same under every ``PYTHONHASHSEED``
    (CI does not set it): the generators iterate no sets.  Dummy indices
    are random per process and left out."""
    import subprocess
    import sys
    code = """
import hashlib, re
from harness.generators import random_stream
from harness.sympy_io import to_srepr
h = hashlib.md5()
for kw in (dict(seed=13, profile="links"), dict(seed=2, profile="transfer"),
           dict(seed=0, n=120, nsets=3, profile="registry", custom=True, events=True),
           dict(seed=1, n=40, nsets=3)):
    kw = dict(dict(n=100, nsets=4), **kw)
    for it in random_stream(**kw):
        s = f"{to_srepr(it.prop)}|{to_srepr(it.assum)}" if hasattr(it, "prop") else str(tuple(it))
        h.update(re.sub(r"dummy_index=[0-9]+", "", s).encode())
print(h.hexdigest())
"""
    digests = set()
    for hs in ("0", "1", "42"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                             cwd=ROOT, env=env, timeout=300)
        assert out.returncode == 0, out.stderr[-3000:]
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


# -- CI-sized profile runs that find a known family (strict xfails) -----------

def _assert_no_discrepancy(rep):
    """The expected failure of a profile xfail is a disagreement between
    answers; an engine error (kind ``error``) fails instead."""
    for d in rep.discrepancies:
        if d.kind == "error":
            pytest.fail("engine error, not the known family: " + d.summary())
    assert not rep.discrepancies, rep.discrepancies[0].summary()


def test_registry_profile_finds_no_registration_dependence():
    """The ``registry`` profile straddles register/unregister events with
    the same queries.  Family R (``harness/repros/fixed/R*``) is fixed by
    #63: every cache is keyed on the registry epoch, so the run must find
    nothing."""
    cfg = preset("default")
    items = random_stream(0, n=120, nsets=3, profile="registry", custom=True, events=True)
    rep = Checker(cfg, ReferenceLevel.ENGINE, ("forward",), seed=0, max_discrepancies=1).run(items)
    if reg.active_ids():            # a leak is a failure, never the expected one
        pytest.fail(f"registrations left active: {reg.active_ids()}")
    _assert_no_discrepancy(rep)


def test_links_profile_finds_no_glue_dependence():
    """The ``links`` profile asks a relation query under a unary set and
    then order predicates about linear relatives of the set's terms.
    Family G (#42, fixed by #53 stage 5: the glue is switched per query)
    made a session answer a unary query differently once a relation was
    asked before."""
    cfg = preset("default")
    items = random_stream(13, n=100, nsets=4, profile="links")
    rep = Checker(cfg, ReferenceLevel.ENGINE, ("forward",), seed=13, max_discrepancies=1).run(items)
    _assert_no_discrepancy(rep)


def test_transfer_profile_finds_no_transfer_dependence():
    """The ``transfer`` profile asks an equality query under a set that puts
    a term into an EUF class (``zero(u)``) and states facts about
    applications of the class's value (``positive(f(0))``), then asks the
    same applications of the term (``positive(f(u))``)."""
    cfg = preset("default")
    items = random_stream(2, n=100, nsets=4, profile="transfer")
    rep = Checker(cfg, ReferenceLevel.ENGINE, ("forward",), seed=2, max_discrepancies=1).run(items)
    _assert_no_discrepancy(rep)


# -- both reference levels: a fresh engine (ENGINE) and the spec (SPEC) --------
#
# ``ReferenceLevel.SPEC`` compares the long-lived engine with a fresh engine
# and with ``satassume.ref.ask_ref``, the eager reference of docs/spec.md.
# The pinned and fixed repros are replayed at both levels, every row of the
# replay checked; a SPEC-level disagreement is pinned below as a strict
# xfail with its tag (``harness.checker.spec_tag``) and query.

#: repro file -> (SPEC tag, the disagreeing query of its replay)
SPEC_DIFFERENCES = {
    "D-discovery-budget-truncates-fresh-cone": (
        "budget", "ask(Q.lt(1, sqrt(2)) | Q.ne(E, w + (I*w)**(1/3)*Abs(j)**(2/3)), True): "
        "engine None, ask_ref True (and the next prefix query, None vs False); "
        "the repro's config has discovery_budget below the cone"),
    "L1-learnt-unit-written-back": (
        "relevance", "ask(Q.imaginary((ir + 2)*(inf - 1 + I)) | ~Q.nonzero(inf + acos(-1/he)), "
        "Q.gt(-1/3, 1/(2*al)) & Q.infinite(acos(-1/he))): engine None, ask_ref True; "
        "a fresh engine with relevance=False answers True"),
}


def _level_params():
    out = []
    pinned = sorted(glob.glob(os.path.join(REPROS, "*.json")))
    fixed = sorted(glob.glob(os.path.join(REPROS, "fixed", "*.json")))
    for level in (ReferenceLevel.ENGINE, ReferenceLevel.SPEC):
        for path in pinned + fixed:
            name = os.path.basename(path)[:-5]
            marks = []
            if level == ReferenceLevel.SPEC and name in SPEC_DIFFERENCES:
                tag, query = SPEC_DIFFERENCES[name]
                marks.append(pytest.mark.xfail(strict=True, raises=AssertionError,
                                                reason=f"SPEC {tag}: {query}"))
            elif level == ReferenceLevel.ENGINE and path in pinned:
                marks.append(pytest.mark.xfail(strict=True, raises=AssertionError,
                                                reason="pinned repro: harness/repros/README.md"))
            out.append(pytest.param(level, path, id=f"{level.name}-{name}", marks=marks))
    return out


@pytest.mark.parametrize("level,path", _level_params())
def test_repro_at_both_levels(level, path):
    """Every query of a repro's replay (prefix and final query) agrees with
    the reference of ``level``: a fresh engine (ENGINE) or a fresh engine
    and ``ask_ref`` (SPEC).  An error on any side fails, not xfails."""
    from harness.checker import item_from_json, spec_tag
    from harness.state import EngineConfig
    with open(path) as fh:
        d = json.load(fh)
    cfg = EngineConfig.from_dict(d["config"])
    items = [item_from_json(i) for i in d["prefix"]] + [item_from_json(d["item"])]
    rows, _ = execute(items, cfg, level)
    for r in rows:
        _fail_on_error(r.warm, r.ref)
        if level == ReferenceLevel.SPEC:
            _fail_on_error(r.warm, r.spec)
            assert r.spec is not None
    bad = [(str(r.item), r.warm, r.ref, r.spec, spec_tag(r.warm, r.spec, r.budget_limited)
            if r.spec is not None else None) for r in rows if r.mismatches()]
    assert not bad, bad


@pytest.mark.parametrize("level", [ReferenceLevel.ENGINE, ReferenceLevel.SPEC], ids=lambda l: l.name)
@pytest.mark.parametrize("profile,seed", [("links", 13), ("transfer", 2)])
def test_ci_profiles_at_both_levels(profile, seed, level):
    """The CI-sized ``links`` and ``transfer`` runs find nothing at either
    level: at SPEC every warm answer is also ``ask_ref``'s (no finding, no
    budget or relevance difference, no defect)."""
    cfg = preset("default")
    items = random_stream(seed, n=100, nsets=4, profile=profile)
    rep = Checker(cfg, level, ("forward",), seed=seed, max_discrepancies=1).run(items)
    _assert_no_discrepancy(rep)
    assert rep.mismatches == 0 and rep.spec_mismatches == 0, rep.to_json()
    if level == ReferenceLevel.SPEC:
        assert rep.queries == len(items) and rep.spec_seconds > 0, rep.to_json()


def test_spec_level_tags():
    """``spec_tag`` and the SPEC-level discrepancy of a checker run: an
    engine answer the spec does not entail is a ``finding``; None against
    a definite spec answer is ``budget`` or ``relevance``; a contradiction
    or a one-sided ValueError is a ``defect``."""
    from harness.checker import spec_tag
    assert spec_tag("True", "True") is None
    assert spec_tag("True", "None") == "finding"
    assert spec_tag("None", "False") == "relevance"
    assert spec_tag("None", "False", budget_limited=True) == "budget"
    assert spec_tag("True", "False") == "defect"
    assert spec_tag("ValueError", "None") == "defect"
    assert spec_tag("None", "ValueError") == "defect"
    assert spec_tag("None", "ValueError", budget_limited=True) == "budget"   # spec 10, rule 1
    assert spec_tag("ValueError", "None", budget_limited=True) == "defect"
    assert spec_tag("Error:TypeError", "True") == "defect"
    assert is_known_family("S:budget") and is_known_family("S:relevance")
    assert not is_known_family("S:finding") and not is_known_family("S:defect")


def test_spec_level_catches_a_planted_engine_answer(monkeypatch):
    """An engine answer the spec does not entail, the same warm and fresh
    (so the ENGINE level cannot see it), is found at SPEC level only, as a
    ``finding`` with level SPEC and family ``S:finding``."""
    import satassume.ref as ref
    x = Symbol("x")
    orig = ref.ask_ref

    def weak(p, A=True, extensions=None, **kw):
        r = orig(p, A, extensions, **kw)
        return None if p == Q.positive(x + 1) else r

    monkeypatch.setattr(ref, "ask_ref", weak)
    items = [Ask(Q.real(x), Q.positive(x)), Ask(Q.positive(x + 1), Q.positive(x))]
    rep = Checker(preset("default"), ReferenceLevel.ENGINE, ("forward",)).run(items)
    assert not rep.discrepancies, rep.to_json()
    rep = Checker(preset("default"), ReferenceLevel.SPEC, ("forward",)).run(items)
    assert rep.mismatches == 0 and rep.spec_mismatches == 1, rep.to_json()
    (d,) = rep.discrepancies
    assert (d.level, d.tag, d.warm, d.ref) == (ReferenceLevel.SPEC, "finding", "True", "None")
    assert d.confirmations["family"] == "S:finding" and d.confirmations["fresh_engine"] == "True"
    assert d.shrunk is not None and len(d.shrunk) <= 1, d.summary()


def test_cache_audit_counts_what_it_could_not_check():
    """The cache audit prints what it skipped next to what it checked
    (docs/agents.md, Gating rule 5): closed number nodes with their facts,
    and cached None facts; the checked counts are unchanged."""
    from harness.checker import audit_cache
    items = random_stream(0, n=60, nsets=3)
    _, stats = audit_cache(items, preset("default"))
    why = stats["unchecked_reasons"]
    assert stats["unchecked"] == why["number_node_facts"] + why["none_facts"], stats
    assert why["number_nodes"] > 0 and why["number_node_facts"] > 0 and stats["facts"] > 0, stats
    assert set(stats) >= {"nodes", "facts", "bad"}, stats


# -- the checker catches planted defects ---------------------------------------

def test_checker_catches_a_planted_history_dependence(monkeypatch):
    """A defect planted from outside (a wrong answer once the engine has
    seen a few queries) is found, and the prefix is shrunk to one query."""
    from satassume.engine import Engine
    orig = Engine.ask

    def bad_ask(self, proposition, assumptions=None):
        r = orig(self, proposition, assumptions)
        if self.stats["queries"] > 3 and r is None:
            return True             # history-dependent: depends on the count
        return r

    monkeypatch.setattr(Engine, "ask", bad_ask)
    items = random_stream(1, n=40, nsets=3)
    rep = Checker(preset("default"), ReferenceLevel.ENGINE, ("forward",), max_discrepancies=1).run(items)
    assert rep.discrepancies, "the planted defect was not caught"
    d = rep.discrepancies[0]
    assert d.shrunk is not None and len(d.shrunk) <= 3, d.summary()


def test_checker_catches_a_planted_cache_leak(monkeypatch):
    """A fact leaking from one query's assumptions into the fact cache is
    caught by a later context-free query."""
    from satassume.engine import DictCache
    orig_put = DictCache.put
    x = Symbol("x")

    def leaky_put(self, node, pred, value):
        orig_put(self, node, pred, value)
        if node == x + 1:
            orig_put(self, x, "positive", True)        # a fact no query derived

    monkeypatch.setattr(DictCache, "put", leaky_put)
    # the cache is a memo of is_ (#97 P2): a context-free query with a
    # definite answer memoizes it, which is when the leak is planted (a
    # None, as Q.positive(x + 1) for a plain x, is never written; a
    # contextual query writes nothing)
    items = [Ask(Q.commutative(x + 1), True), Ask(Q.positive(x), True)]
    rows, _ = execute(items, preset("default"), ReferenceLevel.ENGINE)
    assert [r.mismatch for r in rows] == [False, True], [(r.warm, r.ref) for r in rows]


def test_ddmin_shrinks_to_the_responsible_query(monkeypatch):
    from satassume.engine import Engine
    orig = Engine.ask
    x, y = Symbol("x"), Symbol("y")
    trigger = Q.real(y + 1)

    def bad_ask(self, proposition, assumptions=None):
        r = orig(self, proposition, assumptions)
        seen = self.__dict__.setdefault("_seen", set())
        from satassume.formula import P
        if isinstance(proposition, P) and proposition.expr == y + 1:
            seen.add("t")
        if "t" in seen and isinstance(proposition, P) and proposition.expr == x and r is None:
            return False
        return r

    monkeypatch.setattr(Engine, "ask", bad_ask)
    cfg = preset("default")
    prefix = [Ask(Q.real(x + 2), Q.real(x)), Ask(trigger, Q.integer(y)), Ask(Q.zero(x * y), Q.real(x))]
    d = Discrepancy(cfg, "forward", 3, Ask(Q.positive(x), Q.real(x)), "False", "None",
                    ReferenceLevel.ENGINE, prefix)
    shrink(d)
    assert d.shrunk is not None and len(d.shrunk) == 1 and d.shrunk[0].prop == trigger


def test_order_stream_keeps_events_in_place():
    from harness.checker import Event
    x = Symbol("x")
    items = [Ask(Q.real(x), True), Event("register", "big"), Ask(Q.positive(x), True),
             Ask(Q.zero(x), True)]
    for order in ("forward", "reverse", "shuffle", "grouped", "interleave", "repeat"):
        out = order_stream(items, order, 1)
        ev = [i for i, it in enumerate(out) if isinstance(it, Event)]
        assert len(ev) == 1 and out[ev[0]] == items[1]
        assert all(it == items[0] for it in out[:ev[0]]) and len(out[:ev[0]]) >= 1
        assert {it.prop for it in out[ev[0] + 1:]} == {items[2].prop, items[3].prop}
    assert not reg.active_ids()


def _srepr_samples():
    from sympy import (AccumBounds, CRootOf, FiniteSet, Function, ImageSet, Interval, Lambda,
                       Piecewise, Range, S, hyper, meijerg, oo)
    x = Symbol("x")
    return [
        AccumBounds(-1, 1),                       # AccumulationBounds: not in sympy's namespace
        Q.extended_negative(AccumBounds(-1, 1) + x),
        Piecewise((x, x > 0), (0, True)),         # ExprCondPair
        hyper([1], [2], x),                       # TupleArg
        meijerg([[1], []], [[], []], x),
        CRootOf(x**5 + x + 1, 0),                 # ComplexRootOf
        ImageSet(Lambda(x, x**2), S.Naturals),
        Range(3), Interval(0, oo), FiniteSet(1, x),
        Q.positive(Function("f")(x)) | Q.eq(x, 1),
    ]


@pytest.mark.parametrize("expr", _srepr_samples(), ids=lambda e: type(e).__name__)
def test_srepr_round_trip(expr):
    """``from_srepr`` rebuilds what ``srepr`` prints for classes SymPy does
    not export at the top level (the nightly hash-seed step once crashed on
    ``NameError: AccumulationBounds``)."""
    from harness.sympy_io import from_srepr, to_srepr
    back = from_srepr(to_srepr(expr))
    assert back == expr and type(back) is type(expr)


def test_srepr_unknown_name_is_a_name_error():
    from harness.sympy_io import from_srepr
    with pytest.raises(NameError):
        from_srepr("NoSuchSymPyClass(Integer(1))")


def test_answer_memo_repeating_the_query_is_history_free():
    """E1 and C6b with the query repeated context-free in the prefix (the
    shape of E1c).  Before #53 stage 5, under the old history-dependent
    writeback (``Engine(writeback="all")``, removed by #97 P2), the prefix
    query wrote a fact back (E1: a root fact from an unguarded link) and
    the prefix's own copy of the query put it in the answer memo, so only
    clearing both the cache and the memo restored the fresh answer (carrier
    ``cache+answers``, the cache's family C').  With the glue switched per
    query and the cache a memo of ``is_`` neither vehicle carries the
    dependence any more, and no context-free vehicle is known (a search
    over the fixed repros and ~26k pairs of C6b's shape found none): this
    is a regression test, warm == fresh, under the default engine."""
    from harness.checker import item_from_json
    from harness.state import EngineConfig

    def pinned(name):
        with open(os.path.join(REPROS, "fixed", name)) as fh:
            rec = json.load(fh)
        rec["prefix"] = rec["prefix"] + [rec["item"]]
        seq = [item_from_json(i) for i in rec["prefix"]]
        return seq, Discrepancy(EngineConfig.from_dict(rec["config"]), "pinned", len(seq),
                                item_from_json(rec["item"]), rec["warm"], rec["ref"],
                                ReferenceLevel.ENGINE, list(seq), shrunk=list(seq),
                                shrunk_warm=rec["warm"], shrunk_ref=rec["ref"])
    from harness.checker import outcome
    for name in ("E1-order-clauses-write-back-oo-sum.json", "C6b-derived-node-of-acos-found.json"):
        seq, d = pinned(name)
        eng = d.config.make()
        for it in seq:
            outcome(it.prop, it.assum, eng)
        warm = outcome(d.item.prop, d.item.assum, eng)
        assert warm == outcome(d.item.prop, d.item.assum, d.config.make()), name


def test_known_families():
    for fam in ("A", "C", "C+answers", "R:cache-none-vs-definite"):
        assert is_known_family(fam), fam
    # G, G' and T are fixed (#53 stage 5): finding one again is a failure
    for fam in ("?", "new:sessions-contradiction", "new:cache-none-vs-definite",
                "G", "G'", "T"):
        assert not is_known_family(fam), fam
    assert is_known_family("new:cache-none-vs-definite", audit=True)
    assert not is_known_family("new:cache-contradiction", audit=True)


# ==========================================================================
# slow part: HISTORY_SLOW=1 (nightly)
# ==========================================================================

@slow
@needs_slow
@pytest.mark.parametrize("config", ["default", "tight", "reuse"])
def test_random_streams(config):
    cfg = preset(config)
    for seed in range(N_SEEDS):
        items = random_stream(seed, n=120, nsets=5, relations=True, custom=False)
        rep = _check(cfg, items, ("forward", "grouped", "interleave"), seed=seed)
        assert rep.queries > 0


@slow
@needs_slow
def test_random_streams_with_registrations():
    cfg = preset("default")
    items = random_stream(7, n=100, nsets=4, relations=True, custom=True, events=True)
    _check(cfg, items, ("forward", "shuffle"), seed=7)
    assert not reg.active_ids()


@slow
@needs_slow
def test_module_memos_do_not_change_answers():
    """Engine-level and module-level references agree on a sample."""
    cfg = preset("default")
    items = random_stream(3, n=80, nsets=4)
    rep = _check(cfg, items, ("forward",), seed=3, ref_check_every=3)
    assert not rep.ref_instability, rep.ref_instability


@slow
@needs_slow
@pytest.mark.parametrize("profile", ["related", "focus", "relational", "declared", "deep"])
def test_profile_streams(profile):
    """Streams shaped after the engine's state: shared conjuncts between
    sets, long sessions, relation-heavy sets, declared facts, big cones."""
    cfg = preset("default")
    n = 60 if profile == "deep" else 100
    items = random_stream(1, n=n, nsets=4, profile=profile)
    _check(cfg, items, ("forward", "grouped"), seed=1)


@slow
@needs_slow
def test_lazy_profile_finds_only_known_families():
    """Both shapes with generic queries between (``lazy``), and the base
    stream with trigger/observer pairs inserted (``lazy=0.2``)."""
    cfg = preset("default")
    for items, seed in ((random_stream(1, n=100, nsets=4, profile="lazy"), 1),
                        (random_stream(1, n=80, nsets=4, lazy=0.2), 101)):
        _check(cfg, items, ("forward", "grouped"), seed=seed)


@slow
@needs_slow
def test_cache_audit_finds_only_known_flows():
    """Every cached fact after a short stream is one a fresh engine derives
    for the node, or a documented flow (family C, E)."""
    from harness.checker import attribute, audit_cache
    cfg = preset("default")
    items = random_stream(11, n=100, nsets=4, profile="base")
    found, stats = audit_cache(items, cfg, source="pytest audit", max_findings=3)
    assert stats["facts"] > 0
    unknown = []
    for d in found:
        shrink(d)
        attribute(d)
        if not _known(d.confirmations.get("family", "?"), audit=True):
            unknown.append(d.summary())
    assert not unknown, "\n".join(unknown)


@slow
@needs_slow
@settings(max_examples=N_EXAMPLES, deadline=None, derandomize=True, database=None,
          suppress_health_check=list(HealthCheck))
@given(stream_strategy(n_max=25, nsets_max=3, relations=True, custom=False))
def test_hypothesis_streams(items):
    """Hypothesis-generated streams (derandomized: the same examples every
    run); a discrepancy is shrunk and must be of a known family."""
    from harness.checker import attribute
    for cfg in (PRESETS["default"], PRESETS["tight"]):
        for order in ("forward", "grouped"):
            rep = Checker(cfg, ReferenceLevel.ENGINE, (order,), shrink_them=False,
                          max_discrepancies=1, ignore_kinds=IGNORE).run(items)
            for d in rep.discrepancies:
                shrink(d)
                attribute(d)
                assert _known(d.confirmations.get("family", "?")), d.summary()


@slow
@needs_slow
@pytest.mark.skipif(not os.path.exists(CORPUS),
                    reason="queries.jsonl not recorded (tools/record_queries.py)")
def test_corpus_sample():
    from harness.corpus import load_corpus
    items = load_corpus(CORPUS, limit=400)
    assert len(items) >= 300, len(items)
    _check(preset("default"), items, ("forward", "grouped"))


# ==========================================================================
# the runtime self-check (harness/selfcheck.py)
# ==========================================================================

def test_selfcheck_passes_clean_queries_and_flags_a_planted_one():
    """``selfcheck.install()`` (in a subprocess: it wraps ``ask`` for the
    whole process) lets clean answers through and raises on an answer
    planted in the default engine's answer memo."""
    import subprocess
    import sys
    code = """
from sympy import Q, Symbol
import satassume.sympy_api as api
from harness import selfcheck
selfcheck.install()
assert api._selfcheck_original is not None
x = Symbol('x')
for p, a in [(Q.positive(x + 1), Q.positive(x)), (Q.real(x), Q.integer(x)), (Q.positive(x), Q.real(x))]:
    api.ask(p, a)
assert not selfcheck.mismatches
eng = api.default_engine()
key = (Q.negative(x), Q.positive(x))
eng.answers.put(key, True)
try:
    api.ask(*key)
except selfcheck.HistoryDependence as e:
    print("caught:", e)
else:
    raise SystemExit("planted mismatch not caught")
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=ROOT, env=dict(os.environ, PYTHONHASHSEED="0"), timeout=300)
    assert out.returncode == 0, out.stderr[-3000:]
    assert "caught:" in out.stdout
