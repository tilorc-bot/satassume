"""The discovery budget as a test on the query's structural cone (#53 task 6).

A query is budget-limited iff the weight of ``cone(p) | cone(a)`` exceeds
``discovery_budget``, decided before any session work from the structure
alone (``Engine._within_budget``): such a query is None (unless its set
fits the budget and is inconsistent: then it raises, as every query under
that set does), every other one runs uncapped and is never truncated.  So the answer and ``last_budget_limited`` are
functions of ``(p, a, config, registry)``, never of earlier queries, the
caches or a reused session.
"""
import pickle
from pathlib import Path

import pytest
from sympy import Function, Q, exp, sin, sqrt, symbols

from satassume import P
from satassume.engine import UNKNOWN
from satassume.sympy_api import DictCache, Engine, _formula, ask

x, y, z, u = symbols('x y z u')
f = Function('f')


def _outcome(eng, p, a):
    try:
        r = ask(p, a, eng)
    except ValueError:
        r = "ValueError"
    return r, eng.last_budget_limited


#: queries around a budget of 5: some fit, some do not, under shared sets
TARGETS = [
    (Q.positive(x + 1), Q.positive(x)),
    (Q.positive(x*y + 1), Q.positive(x) & Q.positive(y)),
    (Q.real(exp(x) + sin(y)), Q.real(x) & Q.real(y)),
    (Q.nonzero(x**2 + 1), Q.real(x)),
    (Q.positive(sqrt(x) + y), Q.positive(x) & Q.positive(y) & Q.real(z)),
    (Q.lt(x, y + 1), Q.lt(x, y)),
    (Q.real(f(x)), Q.eq(f(x), x) & Q.real(x)),
]
#: earlier queries on the warm engine: related (same sets, sub-terms) and
#: unrelated ones
HISTORY = [
    (Q.real(x), Q.positive(x)),
    (Q.positive(x*y), Q.positive(x) & Q.positive(y)),
    (Q.real(exp(x)), Q.real(x) & Q.real(y)),
    (Q.real(x**2), Q.real(x)),
    (Q.positive(z*u + 1), Q.positive(z) & Q.positive(u)),
    (Q.positive(sqrt(x)), Q.positive(x) & Q.positive(y) & Q.real(z)),
    (Q.lt(x, y + 2), Q.lt(x, y)),
    (Q.real(u + 1), True),
]


@pytest.mark.parametrize("budget", [3, 5, 8])
def test_warm_equals_fresh_answer_and_flag(budget):
    warm = Engine(discovery_budget=budget, cache=DictCache())
    for p, a in HISTORY + TARGETS:
        _outcome(warm, p, a)
    for p, a in TARGETS + HISTORY:
        fresh = Engine(discovery_budget=budget, cache=DictCache())
        assert _outcome(warm, p, a) == _outcome(fresh, p, a), (p, a)
    # warm is_ against fresh is_, after the contextual queries filled the cache
    for e in (x + 1, x*y + 1, exp(x) + sin(y), x**2 + 1, sqrt(x) + y):
        fresh = Engine(discovery_budget=budget, cache=DictCache())
        assert ((warm.is_(e, 'real'), warm.last_budget_limited)
                == (fresh.is_(e, 'real'), fresh.last_budget_limited))


@pytest.mark.parametrize("budget", [2, 3, 4])
def test_warm_chain_equals_fresh(budget):
    # wave 1 finding (a): cached facts of the smaller nodes let a warm query
    # skip the escalation that truncated the fresh one (True warm, None
    # fresh, both flagged); now both are over the budget, or both fit
    xp, w = symbols('xp', positive=True), symbols('w')
    warm = Engine(discovery_budget=budget)
    e = xp
    for _ in range(5):
        e = exp(e)
        f1, f2 = Engine(discovery_budget=budget), Engine(discovery_budget=budget)
        assert _outcome(warm, Q.positive(e), Q.real(w)) == _outcome(f1, Q.positive(e), Q.real(w))
        assert ((warm.is_(e, 'positive'), warm.last_budget_limited)
                == (f2.is_(e, 'positive'), f2.last_budget_limited))


def test_no_session_is_truncated_within_the_budget():
    # every query that passes the test runs uncapped: Session.truncated is
    # never set (Engine._note_budget asserts it) in any session the engine
    # builds.  The sessions are collected as they are built: since #97 no
    # session is kept (_context_sessions stays empty), so the check used
    # to look at none of them
    eng = Engine(discovery_budget=5, cache=DictCache(), relevance=False)
    built = []
    fresh = eng._fresh_session

    def record(*args):
        s = fresh(*args)
        built.append(s)
        return s
    eng._fresh_session = record
    for p, a in HISTORY + TARGETS:
        _outcome(eng, p, a)
    assert not eng._context_sessions
    assert len(built) >= 10
    assert not any(s.truncated for s in built)


def test_answer_memo_hit_restores_last_budget_limited():
    eng = Engine(discovery_budget=3, cache=DictCache())
    small, big = Q.positive(x + 1), Q.positive(exp(x) + sin(x) + x**2)
    assert ask(small, Q.positive(x), eng) is True and not eng.last_budget_limited
    assert ask(big, Q.positive(x), eng) is None and eng.last_budget_limited
    hits = eng.stats["cache_hits"]
    assert ask(small, Q.positive(x), eng) is True            # a memo hit
    assert eng.stats["cache_hits"] == hits + 1
    assert not eng.last_budget_limited
    # an answer over the budget is not memoized: asked again, flagged again
    assert ask(big, Q.positive(x), eng) is None and eng.last_budget_limited
    # the part memo of the relevance layer (the set splits by component)
    a = Q.positive(x) & Q.positive(u)
    assert ask(small, a, eng) is True and not eng.last_budget_limited
    assert ask(big, Q.positive(x) & Q.real(u), eng) is None and eng.last_budget_limited
    assert ask(small, Q.positive(x) & Q.real(u), eng) is True   # part memo hit
    assert not eng.last_budget_limited
    # an out-of-scope query clears the flag too
    assert ask(big, Q.positive(x), eng) is None and eng.last_budget_limited
    assert ask(Q.invertible(x), True, eng) is None             # matrix predicate
    assert not eng.last_budget_limited


def test_set_over_the_budget_unknown_none_no_raise():
    # an inconsistent set whose cone outweighs the budget: never checked,
    # verdict unknown, every query under it None (it is over the budget
    # too), no raise: sound for None answers
    a = Q.positive(exp(x) + y) & Q.negative(exp(x) + y)
    g = _formula(a, True, True)
    eng = Engine(discovery_budget=2, cache=DictCache())
    assert eng.verdict(g) is UNKNOWN
    assert ask(Q.real(x), a, eng) is None and eng.last_budget_limited
    assert eng.ask(P('real', y), g) is None and eng.last_budget_limited
    assert eng.stats["sessions"] == 0
    with pytest.raises(ValueError):
        ask(Q.real(x), a, Engine(cache=DictCache()))


def test_h2_residual_unsplit_or_reweighted_sets():
    """H2's residual, by design ("above the discovery budget the answer is
    None", issue #72): the budget weighs the set the engine is asked
    under.  Whenever that set is not split down to the query's component
    (``relevance=False`` as here, a vocabulary registration in force,
    opaque or keyless sets) an unrelated conjunct is in ``cone(a)``, and
    any restatement of a set (implied conjuncts, ``Implies`` vs ``Or``)
    may weigh differently; so for a budget between the two weights (here
    ``|cone(p, a)|`` = 2 and ``|cone(p, a & B)|`` = 4) the two spellings
    differ.  The heavier one is None, flagged ``last_budget_limited``,
    never a wrong value, and each answer is a function of (p, a, config,
    registry).  With relevance (the default) this ``B`` is dropped and
    both agree."""
    p, a, b = Q.positive(x), Q.positive(x - 1), Q.real(1/u)
    for budget in (2, 3):
        e1 = Engine(discovery_budget=budget, relevance=False)
        e2 = Engine(discovery_budget=budget, relevance=False)
        assert ask(p, a, e1) is True and not e1.last_budget_limited
        assert ask(p, a & b, e2) is None and e2.last_budget_limited
        assert ask(p, a & b, Engine(discovery_budget=budget)) is True
    e = Engine(discovery_budget=4, relevance=False)
    assert ask(p, a & b, e) is True and not e.last_budget_limited


_STREAM = Path.home() / ".cache" / "satassume" / "stream.pkl"


@pytest.mark.skipif(not _STREAM.exists(), reason="no refine stream")
def test_stream_sample_is_never_budget_limited_at_the_default():
    with open(_STREAM, "rb") as fh:
        st = pickle.load(fh)
    eng = Engine()
    for p, a, _r in st[::25]:
        try:
            ask(p, a, eng)
        except ValueError:
            pass
        assert not eng.last_budget_limited, (p, a)
    assert eng.stats["budget_limited"] == 0


def test_inconsistent_set_within_budget_raises_for_every_query():
    """I6: whether a set raises is a function of the set alone.  A set that
    fits the budget and is inconsistent raises for a query over the budget
    as for one within it; ``last_budget_limited`` is reset even when the
    query raises."""
    a = P('positive', 'x') & P('negative', 'x')
    heavy = ('add', ('add', ('add', 'x', 'y'), ('add', 'z', 'w')), ('add', 'u', 'v'))
    from satassume import Implies, allargs
    from satassume.engine import InconsistentAssumptions

    def templates(node):
        if isinstance(node, tuple):
            return [Implies(allargs('positive', node[1:]), P('positive', node))]
        return []
    eng = Engine(templates=templates, cache=DictCache(), discovery_budget=3)
    assert eng._within_budget(a) and not eng._within_budget(P('positive', heavy), a)
    assert eng.ask(P('positive', heavy), True) is None and eng.last_budget_limited
    for p in (P('positive', heavy), P('real', 'x')):
        with pytest.raises(InconsistentAssumptions):
            eng.ask(p, a)
        assert not eng.last_budget_limited
    # the SymPy layer: the same set raises ValueError whatever the query
    big = Q.positive(x + y + z + u + sin(x) + exp(y))
    e = Engine(discovery_budget=3)
    assert ask(big, Q.real(x), e) is None and e.last_budget_limited
    for p in (big, Q.real(x)):
        e = Engine(discovery_budget=3)
        with pytest.raises(ValueError):
            ask(p, Q.positive(x) & Q.negative(x), e)
