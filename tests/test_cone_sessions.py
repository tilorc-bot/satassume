"""Cone sessions of ``Engine.is_`` (#116, ``Engine._cone_session``): the
answers must not depend on which queries ran before, in which order, in
which engine of the configuration, or on which cached child cone a cone
was copied from (docs/design.md, "Cone sessions of ``Engine.is_``")."""
import random

import pytest
from sympy import S, Symbol, sqrt, symbols

import satassume.engine as E
from satassume import Engine, Extensions, InconsistentAssumptions, Not, P
from satassume.formula import Implies, Or
from satassume.rules import PREDICATES
from satassume.solver import Solver

x, y = symbols("x y", positive=True)
z = Symbol("z")
NODES = [x, z, x + 1, z + 1, x * z, (x + 1) ** 2, (z + 1) ** 2,
         sqrt(x) + z, (x + 1) ** 2 + z * (z + 1), 1 / (x + y)]


def _ask(eng, e, p):
    try:
        return eng.is_(e, p)
    except InconsistentAssumptions:
        return "inconsistent"


def _reference(qs, **kw):
    """The per-query path (no cone session), a fresh engine per query."""
    saved = E.CONE_SESSIONS
    E.CONE_SESSIONS = False
    try:
        return {q: _ask(Engine(writeback="none", **kw), *q) for q in qs}
    finally:
        E.CONE_SESSIONS = saved


@pytest.fixture(autouse=True)
def _fresh_cones():
    E._CONE_SESSIONS.clear()
    yield
    E._CONE_SESSIONS.clear()


@pytest.mark.parametrize("reuse", [True, False])
def test_answers_do_not_depend_on_query_order(monkeypatch, reuse):
    monkeypatch.setattr(E, "CONE_REUSE", reuse)
    qs = [(e, p) for e in NODES for p in PREDICATES]
    ref = _reference(qs)
    rng = random.Random(0)
    orders = [qs, qs[::-1]] + [rng.sample(qs, len(qs)) for _ in range(3)]
    for order in orders:
        E._CONE_SESSIONS.clear()
        engines = [Engine(writeback="none") for _ in range(3)]
        got = {q: _ask(rng.choice(engines), *q) for q in order}
        assert got == ref
    # the parents were copied from cached child cones
    assert any(s for d in E._CONE_SESSIONS.values() for s in d.values())


def test_unsatisfiable_cone_takes_the_per_query_path():
    """A cone whose clause set is unsatisfiable without a root conflict:
    the search finds it, the cone is dropped, and every query answers or
    raises as the per-query path does, whatever ran before."""
    ext = Extensions()
    a, b = P("prime", z), P("composite", z)
    facts = [Or(a, b), Or(a, Not(b)), Or(Not(a), b), Or(Not(a), Not(b))]
    ext.register("integer", Symbol)(lambda n: facts if n == z else None)
    qs = [(e, p) for e in (z, z + 1) for p in PREDICATES]
    ref = _reference(qs, extensions=ext)
    assert "inconsistent" in ref.values()
    for order in (qs, qs[::-1], random.Random(1).sample(qs, len(qs))):
        E._CONE_SESSIONS.clear()
        eng = Engine(writeback="none", extensions=ext)
        assert {q: _ask(eng, *q) for q in order} == ref
        assert eng._cone_dict().get(z) is False


def test_registration_starts_new_cone_sessions():
    ext = Extensions()
    eng = Engine(extensions=ext)
    assert eng.is_(z, "integer") is None
    cfg = eng._cone_cfg()
    ext.register("integer", Symbol)(lambda n: True if n == z else None)
    assert eng._cone_cfg() != cfg
    assert eng.is_(z, "integer") is True
    assert eng.is_(z + 1, "integer") is True


def test_settings_select_their_own_cone_sessions():
    a, b = Engine(), Engine(transfer=False)
    assert a._cone_cfg() != b._cone_cfg()
    assert a._cone_cfg() == Engine()._cone_cfg()


def _stored():
    return [s for d in E._CONE_SESSIONS.values() for s in d.values() if s]


def _check_sizes():
    """Each configuration's ``size`` is the sum of its sessions' sizes."""
    for d in E._CONE_SESSIONS.values():
        assert d.size == sum(s.cone_size for s in d.values() if s)


def test_cone_sessions_are_bounded_by_count(monkeypatch):
    monkeypatch.setattr(E, "_CONE_MAX", 4)
    qs = [(e, p) for e in NODES for p in ("positive", "integer", "real")]
    ref = _reference(qs)
    eng = Engine(writeback="none")
    assert {q: _ask(eng, *q) for q in qs} == ref
    assert all(len(d) <= 4 for d in E._CONE_SESSIONS.values())
    _check_sizes()
    for k in range(10):
        Engine(templates=lambda node: ()).is_(z, "real")
    assert len(E._CONE_SESSIONS) <= E._CONE_CFGS


@pytest.mark.parametrize("reuse", [True, False])
def test_cone_sessions_are_bounded_by_size(monkeypatch, reuse):
    """``CONE_BUDGET`` bounds the variables of all cached sessions; the
    least recently used go first, and answers do not change."""
    monkeypatch.setattr(E, "CONE_REUSE", reuse)
    qs = [(e, p) for e in NODES for p in PREDICATES]
    ref = _reference(qs)
    Engine(writeback="none").is_(NODES[-2], "positive")
    full = sum(s.cone_size for s in _stored())
    assert full > 0
    budget = max(s.cone_size for s in _stored())
    monkeypatch.setattr(E, "CONE_BUDGET", budget)
    rng = random.Random(2)
    for order in (qs, rng.sample(qs, len(qs))):
        E._CONE_SESSIONS.clear()
        eng = Engine(writeback="none")
        got = {}
        for q in order:
            got[q] = _ask(eng, *q)
            _check_sizes()
            assert sum(d.size for d in E._CONE_SESSIONS.values()) <= budget
        assert got == ref
    # the most recently used session survives
    eng = Engine(writeback="none")
    eng.is_(x + 1, "positive")
    eng.is_(z + 1, "integer")
    assert eng._cone_dict().get(z + 1)


def test_heavy_cones_are_not_kept(monkeypatch):
    qs = [(e, p) for e in NODES for p in ("positive", "integer", "real")]
    ref = _reference(qs)
    monkeypatch.setattr(E, "CONE_WEIGHT_MAX", 2)
    eng = Engine(writeback="none")
    assert {q: _ask(eng, *q) for q in qs} == ref
    assert all(s.cone_weight <= 2 for s in _stored())
    assert eng._cone_dict().get((x + 1) ** 2 + z * (z + 1)) is None
    E._CONE_SESSIONS.clear()
    monkeypatch.setattr(E, "CONE_WEIGHT_MAX", 64)
    monkeypatch.setattr(E, "CONE_SIZE_MAX", 40)
    eng = Engine(writeback="none")
    assert {q: _ask(eng, *q) for q in qs} == ref
    assert _stored() and all(s.cone_size <= 40 for s in _stored())
    _check_sizes()


def test_a_large_sum_is_not_kept():
    """A cone over ``CONE_WEIGHT_MAX`` (a 100-term sum, tens of MB as a
    session) takes the per-query path and leaves nothing cached."""
    xs = symbols("a0:40", positive=True)
    e = sum(xs[j % 39] / (j + 1) + sqrt(xs[(j + 1) % 39]) for j in range(100))
    eng = Engine(writeback="none")
    assert eng._cone_info(e)[1] > E.CONE_WEIGHT_MAX
    assert eng.is_(e, "positive") is True
    assert eng._cone_dict().get(e) is None
    assert sum(d.size for d in E._CONE_SESSIONS.values()) == 0


def test_a_new_epoch_drops_the_old_cone_sessions():
    ext = Extensions()
    eng = Engine(extensions=ext)
    eng.is_(z + 1, "real")
    other = Engine(transfer=False)
    other.is_(z + 1, "real")
    assert len(E._CONE_SESSIONS) == 2
    epoch = eng._cone_cfg()[0]
    ext.register("integer", Symbol)(lambda n: True if n == z else None)
    assert eng.is_(z + 1, "integer") is True
    assert eng._cone_cfg()[0] != epoch
    assert list(E._CONE_SESSIONS) == [eng._cone_cfg()]


def test_relation_cones_are_not_built():
    ext = Extensions()
    ext.register("positive", Symbol)(
        lambda n: Implies(P("positive", n), P("lt", (S.Zero, n))) if n == z else None)
    qs = [(e, p) for e in (z, z + 1) for p in ("positive", "real", "integer")]
    ref = _reference(qs, extensions=ext)
    eng = Engine(writeback="none", extensions=ext)
    assert {q: _ask(eng, *q) for q in qs} == ref
    assert eng._cone_dict().get(z + 1) is False
    assert eng.stats["cone_builds"] == 0


def test_threads_share_cone_sessions():
    """Engines of one configuration in several threads (``_CONE_LOCK``)."""
    import sys
    import threading
    saved = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    qs = [(e, p) for e in NODES for p in PREDICATES]
    ref = _reference(qs)
    got, errors = [], []

    def run(seed):
        try:
            eng = Engine(writeback="none")
            order = random.Random(seed).sample(qs, len(qs))
            got.append({q: _ask(eng, *q) for q in order})
        except Exception as e:                  # pragma: no cover
            errors.append(e)
    try:
        threads = [threading.Thread(target=run, args=(i,)) for i in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    finally:
        sys.setswitchinterval(saved)
    assert not errors and len(got) == 4
    assert all(g == ref for g in got)


def test_solver_clone_is_independent():
    s = Solver()
    s.track_owners = False
    v = [s.new_var() for _ in range(4)]
    s.add_clause([v[0], v[1]])
    s.add_clause([-v[0], v[2]])
    s.add_clause([v[3]])
    assert s.entails(v[3]) is True and s.entails(v[2]) is None
    c = s.clone(models=True)
    c.add_clause([-v[1]])
    assert c.entails(v[2]) is True and c.entails(v[0]) is True
    assert s.entails(v[2]) is None and s.entails(v[0]) is None
    s.track_owners = True
    with pytest.raises(ValueError):
        s.clone()
