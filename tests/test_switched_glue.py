"""History independence of the switched relation glue (#53 stage 5): a
query in a long-lived engine answers as a fresh engine does, whatever the
engine's earlier queries under the set made.  Each case is (assumptions,
prefix queries, final query); the long-lived engine answers the prefix
first.

Some of these differed on ``main`` only until T3's re-answer
(``engine._path_dependent``, deleted in #97 P1 with the session reuse it
patched) happened to catch them (a branch-and-bound conflict, uncertified
constants); the ``unmasked`` variant pins that no such re-answer exists
and compares the final query at the engine level (``Engine.ask`` on the
translated formulas: no answer memo, no relevance split), so the glue in
the session built for the query is what is tested."""
import pytest
from sympy import Function, Q, Rational, Symbol, sin, symbols

import satassume.engine as engine_mod
from satassume.engine import DictCache, Engine
from satassume.formula import P
from satassume.sympy_api import _formula, ask

a, b, c, u = symbols("a b c u")
f = Function("f")
n = Symbol("n", integer=True)
xi, yi = symbols("x y", integer=True)

CASES = {
    # the own-term integrality atom integer(n) of a link of n (prefix)
    # rounded the bounds on 2*n in the final query
    "own-term-integrality": (Q.lt(0, 2 * n), [Q.zero(n)], Q.lt(2 * n, 2)),
    # the same with a slack term: Integral(x - y) from the prefix's link
    "slack-integrality": (Q.gt(xi, yi + Rational(1, 3)), [Q.positive(xi - yi)],
                          Q.ge(xi, yi + 1)),
    # an equality an earlier query asked kept its LRA twin and its sides'
    # transfer candidacy: LRA's a - b = 0 reached EUF, prime moved to b
    "eq-twin-and-sides": (Q.eq(a - b, 0) & Q.prime(a) & Q.real(b), [Q.eq(a, b)],
                          Q.prime(b)),
    "ne-twin-and-sides": (Q.eq(a - b, 0) & Q.prime(a) & Q.real(b), [Q.ne(a, b)],
                          Q.prime(b)),
    # the bridge alone: LRA derives a = 2, the earlier atom eq(a, 2) hands
    # it to EUF, and 2's facts reach a
    "eq-twin-bridge": (Q.eq(a, 2 * b) & Q.eq(b, 1), [Q.ne(a, 2)], Q.prime(a)),
    "eq-twin-bridge-false": (Q.eq(a + b, 2) & Q.eq(a - b, 0) & Q.real(a) & Q.real(b),
                             [Q.eq(a, 1)], Q.prime(a)),
    "eq-twin-bridge-integer": (Q.gt(a, 1) & Q.lt(a, 3) & Q.integer(a), [Q.eq(a, 2)],
                               Q.prime(a)),
    # an interface equality eq(a, b) exists fresh too, but only the
    # earlier eq(a, c) made a a side: candidacy, not the bridge
    "side-candidacy": (Q.eq(b, 2) & Q.eq(a - b, 0) & Q.real(a), [Q.eq(a, c)],
                       Q.prime(a)),
    # a congruent partner f(c) / f(u) an earlier query brought made f(a) a
    # candidate, which then took 2's facts through an interface equality
    "congruent-partner": (Q.eq(f(a) - b, 0) & Q.eq(b, 2),
                          [Q.eq(a, c) | Q.positive(f(c))], Q.prime(f(a))),
    "congruent-partner-unary": (Q.eq(f(a) - b, 0) & Q.eq(b, 2) & Q.eq(a, u),
                                [Q.positive(f(u))], Q.prime(f(a))),
    # a number node an earlier query mentioned is no congruent partner
    "number-partner": (Q.eq(a, 2), [Q.positive(sin(2))], Q.positive(sin(a))),
    # the set's glue is at the root (Session._set_glue), but a _trichotomy
    # pair of a set atom (a <= b) and a query's (a >= b) keeps the query
    # atom's selector: a = b only in the query that says a >= b
    "tri-pair-set-and-query": (Q.le(a, b) & Q.prime(a) & Q.real(b), [Q.ge(a, b)],
                               Q.prime(b)),
    "tri-pair-set-and-query-eq": (Q.le(a, b) & Q.ge(a, 2) & Q.le(a, 2), [Q.ge(a, b)],
                                  Q.prime(b)),
}

CONFIGS = {"default": {}, "notransfer": {"transfer": False}, "whole": {"relevance": False}}


def _ask(p, s, e):
    try:
        return ask(p, s, e)
    except Exception as ex:          # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


def _pair(name, cfg):
    s, prefix, p = CASES[name]
    e = Engine(cache=DictCache(), **CONFIGS[cfg])
    for q in prefix:
        _ask(q, s, e)
    return _ask(p, s, e), _ask(p, s, Engine(cache=DictCache(), **CONFIGS[cfg]))


@pytest.mark.parametrize("cfg", list(CONFIGS))
@pytest.mark.parametrize("name", list(CASES))
def test_warm_answers_as_fresh(name, cfg):
    warm, fresh = _pair(name, cfg)
    assert warm == fresh


def _engine_ask(p, s, e):
    try:
        return e.ask(_formula(p, True), _formula(s, True, True))
    except Exception as ex:          # noqa: BLE001 (compared as an outcome)
        return type(ex).__name__


@pytest.mark.parametrize("name", list(CASES))
def test_warm_answers_as_fresh_unmasked(name):
    # the re-answer the old variant switched off is gone with the reuse
    assert not hasattr(engine_mod, "_path_dependent")
    s, prefix, p = CASES[name]
    e = Engine(cache=DictCache())
    for q in prefix:
        _ask(q, s, e)
    warm = _engine_ask(p, s, e)
    assert warm == _engine_ask(p, s, Engine(cache=DictCache()))
    assert warm == _pair(name, "default")[1]
    assert not e._context_sessions


def test_capability_kept():
    """What the switched glue gives a query from its own atoms."""
    e = Engine(cache=DictCache())
    assert ask(Q.prime(a), Q.gt(a, 1) & Q.lt(a, 3) & Q.integer(a) & Q.eq(a, 2), e) is True
    assert ask(Q.lt(2 * n, 2), Q.lt(0, 2 * n) & Q.integer(n) & Q.positive(n), e) is False
    # (a common value does not connect sin(2) to a: Engine(relevance=False))
    assert ask(Q.positive(sin(a)), Q.eq(a, 2) & Q.positive(sin(2)),
               Engine(cache=DictCache(), relevance=False)) is True
    assert ask(Q.prime(f(a)), Q.eq(f(a), b) & Q.eq(b, 2), e) is True


def test_set_glue_at_the_root():
    """The glue of a set with a relation atom is on in every query of its
    session, so its selectors are root units (Session._set_glue); a
    query's own glue stays switched (assumed per query)."""
    e = Engine(cache=DictCache(), relevance=False)
    s = Q.gt(a, 1) & Q.lt(a, 3) & Q.eq(c, 2)
    assert ask(Q.positive(b), s, e) is None
    assert not e._context_sessions                  # built per query, discarded
    sess, lits = e._build_context(_formula(s, True, True))
    assert e._ask(sess, lits, P("positive", b), True) is None
    rel, root = sess.relations, set(sess.solver.root_trail())
    for x in (rel.link_sel[a], rel.link_sel[c], rel.xfer_sel):
        assert x in root
    sb = rel.link_sel[b]
    assert sb not in root and -sb not in root
    assert sess.assumption_lits(P("positive", b)) == [sess.sel, sb]
    assert sess.assumption_lits(P("positive", a)) == [sess.sel]
