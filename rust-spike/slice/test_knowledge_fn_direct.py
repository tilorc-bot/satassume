"""6i(b): direct checks of fn_tpl.rs's guards that no workload reaches, against Python's `TemplateRegistry.clauses_for`.

The Rust template is called through `knowledge_live.DISPATCH[0]` (Rust's `Dispatch.clauses_for`), with no query on the stack
or with one pushed on term_live's stack, and its (compiled, formulas) compared by content with Python's for the same node:
- a Float argument of asin/acos: with no query the slot `x - 1` sends the node to Python (`fn:python:unary:no-query`), and
  under a query it can't be met: conversion refuses the query (`algebra: Float`), so fn_tpl.rs's Float unit facts aren't
  reached from the engine (`fn:rust:unit_interval` stays 0);
- a unary node with another number of arguments (`log(x, 2)`): no facts (`fn:rust:unary:none`), before any slot;
- a nary node of an arity its rows don't hold (beta, besselj with three arguments): no facts (`fn:rust:nary:none`);
- a slotted node whose argument isn't a term of the query (`fn:python:unary:derived-arg`, `fn:python:nary:derived-arg`),
  and the same nodes when it is (`fn:rust:unary`, `fn:rust:nary`);
- a slot-free unary node (asinh) with no query: Rust's template, no fallback."""
import pytest
from sympy import Basic, Float, Integer, Q, Symbol, acos, asin, asinh, besselj, beta, log, polylog

import knowledge_live as K
import knowledge_common_live
import term_live
from harness.state import reset_module_state
from satassume import engine as E, sympy_api
from satassume.knowledge.templates import TemplateRegistry, _common, registry

x, y = Symbol('x'), Symbol('y')


@pytest.fixture
def D(monkeypatch):
    for v in ('SLICE_KNOWLEDGE', 'SLICE_SESSION_PLANT', 'SESSION_REPORT', 'SLICE_TERM', 'SA_F6_PLANT'):
        monkeypatch.delenv(v, raising=False)
    undo_term = term_live.from_env()
    undo = K.from_env()
    reset_module_state()
    sympy_api.set_default_engine(E.Engine())
    K.COUNTS.clear()
    yield K.DISPATCH[0]
    undo()
    undo_term()
    K.COUNTS.clear()


def counts():
    c = knowledge_common_live.COMMON[0]
    out = dict(K.COUNTS)
    for k, v in (c.counts() if c is not None else {}).items():
        out[k] = out.get(k, 0) + v
    return out


def _pat(p):
    return (repr(p.rules), repr(p.clauses), p.used, p.complete, p.node, p.nobjs, repr(p.child_preds))


def key(r):
    if r is None:
        return None
    compiled, formulas = r
    return ([(_pat(c.pattern), tuple(c.objs)) for c in compiled], list(formulas))


def same(D, e):
    # Rust's and Python's templates share `_common._CACHE` by pattern key, so each side builds its pattern from an empty
    # cache: otherwise the second reads the first's pattern and a planted rule shows on both
    py = TemplateRegistry.clauses_for.__get__(registry)
    _common._CACHE.clear()
    before = counts()
    ours = key(D.clauses_for(e))
    after = counts()
    _common._CACHE.clear()
    assert ours == key(py(e)), e
    return {k: v - before.get(k, 0) for k, v in after.items() if v != before.get(k, 0) and k.startswith('fn:')}


@pytest.mark.parametrize('e', [asin(Float('0.5'), evaluate=False), asin(Float('2.0'), evaluate=False),
                               acos(Float('-3.0'), evaluate=False), acos(Float('1.0'), evaluate=False)],
                         ids=['asin-0.5', 'asin-2.0', 'acos--3.0', 'acos-1.0'])
def test_float_no_query_goes_to_python(D, e):
    assert same(D, e) == {'fn:python:unary:no-query': 1}


@pytest.mark.parametrize('q', [Q.real(acos(Float('0.5'), evaluate=False)), Q.positive(asin(Float('2.0'), evaluate=False))],
                         ids=['acos-0.5', 'asin-2.0'])
def test_float_query_refused_before_templates(D, q):
    sympy_api.ask(q)
    c = counts()
    assert c.get('refused:algebra: Float', 0) == 1
    assert not any(k.startswith('fn:rust:unit_interval') for k in c), c


def test_unary_other_arity(D):
    assert same(D, log(x, 2, evaluate=False)) == {'fn:rust:unary:none': 1}


@pytest.mark.parametrize('e', [Basic.__new__(beta, x, y, Integer(3)), Basic.__new__(besselj, x, y, Integer(3))],
                         ids=['beta-3', 'besselj-3'])
def test_nary_other_arity(D, e):
    assert same(D, e) == {'fn:rust:nary:none': 1}


def test_unary_without_slots_no_query(D):
    assert same(D, asinh(x)) == {'fn:rust:unary': 1}


def _under_query(D, prop, e):
    q = term_live._convert(prop, True, sympy_api.default_engine())
    assert q.kept is None, q.kept
    s = term_live.stack()
    s.append(q)
    try:
        return same(D, e)
    finally:
        s.pop()


@pytest.mark.parametrize('e,want', [(log(x), 'fn:rust:unary'), (log(y), 'fn:python:unary:derived-arg'),
                                    (polylog(2, x), 'fn:rust:nary'), (polylog(2, y), 'fn:python:nary:derived-arg')],
                         ids=['log-x', 'log-y', 'polylog-x', 'polylog-y'])
def test_derived_arg(D, e, want):
    # the query's terms are x, log(x) and polylog(2, x) (and their slots), not y
    got = _under_query(D, Q.positive(log(x) + polylog(2, x)), e)
    assert got == {want: 1}, got
