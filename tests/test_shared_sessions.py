"""Shared contextual sessions (``Engine._shared``, ``Engine._ask_shared``):
a theory-free session of a contextual query is reused by the next query
about the same expression under the same set and theory scope.  Its
answers must not depend on which queries ran before, in which order, in
which engine, or in which forked process (docs/design.md, "History
independence").  Modelled on the cone-session tests of PR #119."""
import os
import pickle
import random

import pytest
from sympy import Abs, Q, Symbol, exp, sqrt, symbols

import satassume.engine as E
from satassume import Engine, Extensions, InconsistentAssumptions, Not, P
from satassume.sat.formula import Or
from satassume.sympy_api import ask

x, y = symbols("x y")
z = Symbol("z")
SETS = [Q.positive(x), Q.real(x) & Q.negative(y), Q.integer(x) & Q.odd(y),
        Q.negative(x), Q.even(x) & Q.positive(y), Q.zero(x)]
EXPRS = [x + 1, x * y, x**2 + y**2, 1 / x, exp(x), sqrt(x), Abs(x), x**3 + x]
PREDS = ["positive", "negative", "zero", "nonzero", "nonnegative", "real",
         "integer", "rational", "even", "irrational"]
#: (set, expression) groups, each with every predicate: refine's pattern
GROUPS = [[(e, p, s) for p in PREDS] for s in SETS for e in EXPRS]
QS = [q for g in GROUPS for q in g]


def _ask(eng, e, p, s):
    try:
        return ask(getattr(Q, p)(e), s, engine=eng)
    except ValueError:
        return "inconsistent"


def _reference(qs, **kw):
    """A fresh engine per query: no session is ever reused."""
    return {q: _ask(Engine(**kw), *q) for q in qs}


@pytest.fixture(scope="module")
def ref():
    return _reference(QS)


def _orders(seed):
    """The stream in order and reversed, groups shuffled with their
    predicates shuffled, groups interleaved pairwise, and fully random."""
    rng = random.Random(seed)
    shuffled = [rng.sample(g, len(g)) for g in rng.sample(GROUPS, len(GROUPS))]
    pairs = [q for a, b in zip(shuffled[::2], shuffled[1::2])
             for q in sum(zip(a, b), ())]
    return [QS, QS[::-1], [q for g in shuffled for q in g], pairs,
            rng.sample(QS, len(QS))]


@pytest.mark.parametrize("cap", [None, 10**6])
def test_answers_do_not_depend_on_query_order(monkeypatch, ref, cap):
    """Shuffled orders, one engine per order and three engines taking turns
    at random; with ``cap`` every session is kept, so every repeated key
    reuses a session whatever ran in it before."""
    if cap:
        monkeypatch.setattr(E, "SHARED_MAX", cap)
    rng = random.Random(1)
    for order in _orders(0):
        eng = Engine()
        assert {q: _ask(eng, *q) for q in order} == ref
        if cap:
            assert eng.stats["set_checks"] < len(QS) // 2
        engines = [Engine() for _ in range(3)]
        assert {q: _ask(rng.choice(engines), *q) for q in order} == ref
        assert all(len(e._shared) <= E.SHARED_MAX for e in engines)


def test_sessions_are_reused_in_order(ref):
    eng = Engine()
    assert {q: _ask(eng, *q) for q in QS} == ref
    # one set check per group, give or take a theory session or a fallback
    assert eng.stats["set_checks"] <= 2 * len(GROUPS)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs os.fork")
def test_answers_do_not_depend_on_the_forked_parent(monkeypatch, ref):
    """Fork per case, as satsimp's refine battery does: a warm parent holds
    shared sessions; each child asks one group in a shuffled order."""
    monkeypatch.setattr(E, "SHARED_MAX", 10**6)
    rng = random.Random(2)
    eng = Engine()
    for q in rng.sample(QS, len(QS) // 2):
        _ask(eng, *q)
    assert eng._shared
    for g in GROUPS[::5]:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:                                # the child
            os.close(r)
            code = 1
            try:
                got = {q: _ask(eng, *q) for q in rng.sample(g, len(g))}
                os.write(w, pickle.dumps(got))
                code = 0
            finally:
                os._exit(code)
        os.close(w)
        with os.fdopen(r, "rb") as f:
            data = f.read()
        assert os.waitpid(pid, 0)[1] == 0
        assert pickle.loads(data) == {q: ref[q] for q in g}


def test_a_session_that_raises_falls_back_to_a_fresh_one(monkeypatch, ref):
    """A shared session that raises (the set is inconsistent with the
    expression's cone) is dropped, and the query is answered, or raises,
    as in a fresh session."""
    calls = []
    def raising(self, s, proposition):
        calls.append(proposition)
        raise InconsistentAssumptions("planted")
    monkeypatch.setattr(E.Engine, "_ask_shared", raising)
    eng = Engine()
    assert {q: _ask(eng, *q) for q in QS} == ref
    assert calls


def test_a_cone_inconsistent_with_the_set():
    """``z`` has an unsatisfiable cone (no root conflict, PR #119's test):
    queries about ``z + x`` under a set that does not mention ``z`` answer
    or raise as a fresh engine does, in any order."""
    ext = Extensions()
    a, b = P("prime", z), P("composite", z)
    facts = [Or(a, b), Or(a, Not(b)), Or(Not(a), b), Or(Not(a), Not(b))]
    ext.register("integer", Symbol)(lambda n: facts if n == z else None)
    qs = [(e, p, s) for s in SETS[:3] for e in (z + x, x + 1) for p in PREDS]
    want = _reference(qs, extensions=ext)
    for order in (qs, qs[::-1], random.Random(3).sample(qs, len(qs))):
        eng = Engine(extensions=ext)
        assert {q: _ask(eng, *q) for q in order} == want


def test_theory_sessions_are_not_kept():
    """An LRA session's branch and bound has a path-dependent budget
    (satassume.sat.lra): such a session answers its query only."""
    eng = Engine()
    _ask(eng, x - y, "positive", Q.gt(x, y) & Q.integer(x))
    assert not eng._shared
    _ask(eng, x + 1, "positive", Q.positive(x))
    assert len(eng._shared) == 1


def test_shared_sessions_are_bounded():
    eng = Engine()
    for e in EXPRS:
        _ask(eng, e, "positive", Q.positive(x))
        assert len(eng._shared) <= E.SHARED_MAX
    assert len(eng._shared) == E.SHARED_MAX
    assert [k[1] for k in eng._shared] == EXPRS[-E.SHARED_MAX:]


def test_a_new_epoch_drops_the_shared_sessions():
    ext = Extensions()
    eng = Engine(extensions=ext)
    assert _ask(eng, z + 1, "integer", Q.positive(z)) is None
    assert eng._shared
    ext.register("integer", Symbol)(lambda n: True if n == z else None)
    assert _ask(eng, z + 1, "integer", Q.positive(z)) is True


def test_a_setting_change_drops_the_shared_sessions():
    eng = Engine()
    _ask(eng, x + 1, "positive", Q.positive(x))
    assert eng._shared
    eng.transfer = not eng.transfer
    assert not eng._shared


def test_a_query_of_another_scope_builds_its_own_session():
    """``positive(x + y)`` links ``x + y`` with ``x - 1`` (two sign atoms
    on sums sharing ``x``: LRA glue), ``real(x + y)`` does not: the
    theory-free session of the second is not the first's."""
    a = Q.positive(x - 1) & Q.positive(y)
    eng = Engine()
    assert _ask(eng, x + y, "real", a) is True
    assert eng._shared
    assert _ask(eng, x + y, "positive", a) is True
    assert eng.stats["set_checks"] == 2
