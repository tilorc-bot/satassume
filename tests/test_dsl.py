"""Tests for the template notation (:mod:`satassume.templates.dsl`)."""
from __future__ import annotations

import re

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Symbol

from satassume.templates.dsl import Group, Term, any_of, given, lower, none_of, show_rules

x, y = Term(0, 'x'), Term(1, 'y')


def test_statements_lower_to_specs():
    assert lower(y.positive) == [([], [(1, 'positive', True)])]
    assert lower(~y.zero) == [([], [(1, 'zero', False)])]
    assert lower((x.real & ~x.zero) >> y.positive) == [
        ([(0, 'real', True), (0, 'zero', False)], [(1, 'positive', True)])]
    assert lower(x.real >> (y.imaginary | y.zero)) == [
        ([(0, 'real', True)], [(1, 'imaginary', True), (1, 'zero', True)])]
    # A conjunction as conclusion is one rule per conjunct.
    assert lower(x.zero >> (y.odd & y.positive)) == [
        ([(0, 'zero', True)], [(1, 'odd', True)]),
        ([(0, 'zero', True)], [(1, 'positive', True)])]
    assert lower(x.real >> y.zero.iff(x.zero)) == [
        ([(0, 'real', True), (1, 'zero', True)], [(0, 'zero', True)]),
        ([(0, 'real', True), (0, 'zero', True)], [(1, 'zero', True)])]
    assert lower(given(x.real, x.finite) >> y.real) == lower((x.real & x.finite) >> y.real)
    assert lower(x['real'] >> y['real']) == lower(x.real >> y.real)


def test_groups():
    a, b, c = (Term(k, f'a{k}') for k in range(3))
    g = Group([a, b, c])
    assert lower(g.integer >> y.integer)[0][0] == [(0, 'integer', True), (1, 'integer', True),
                                                   (2, 'integer', True)]
    assert lower(y.zero >> any_of(g).zero) == [
        ([(1, 'zero', True)], [(0, 'zero', True), (1, 'zero', True), (2, 'zero', True)])]
    assert lower(none_of(g.without(b)).zero >> y.finite)[0][0] == [(0, 'zero', False),
                                                                    (2, 'zero', False)]
    pairs = [(t.name, [r.name for r in rest]) for t, rest in g.each_with_rest()]
    assert pairs == [('a0', ['a1', 'a2']), ('a1', ['a0', 'a2']), ('a2', ['a0', 'a1'])]
    assert len(g.subsets(2)) == 3
    # An empty group is a true premise.
    assert lower(Group([]).real >> y.real) == [([], [(1, 'real', True)])]


def test_mistakes_are_errors():
    with pytest.raises(AttributeError, match='unknown predicate'):
        x.postive
    with pytest.raises(AttributeError, match='unknown predicate'):
        Group([x]).postive
    # `a & b >> c` parses as `a & (b >> c)`.
    with pytest.raises(TypeError, match='parenthesise'):
        x.real & x.finite >> y.real
    # `a >> b | c` parses as `(a >> b) | c`.
    with pytest.raises(TypeError):
        x.real >> y.imaginary | y.zero
    with pytest.raises(TypeError):
        bool(x.real)
    with pytest.raises(TypeError):
        (y.imaginary | y.zero) >> x.real


def test_show_rules():
    z = Symbol('z')
    text = show_rules(z**2)
    assert '# pow_rules: b = z, e = 2, y = z**2' in text
    # Constants are resolved: "e.even" is true for 2 and has gone.
    assert 'b.nonzero >> y.positive' in text
    assert not re.search(r'\be\.', text)
    text = show_rules(z + 1)
    assert '# add_rules:' in text and 'terms[0] = 1' in text
