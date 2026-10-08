"""Side predicates (prime, composite, imaginary): their rule clauses leave the
per-node rule block and are instantiated per node only once touched
(rules.SIDE_GROUPS, Solver.set_rule_block(side=...))."""
import itertools
import random

import pytest
from sympy import Q, symbols

from satassume import rules
from satassume.rules import (BASIS_INDEX, NPRED, RULE_CORE, RULE_CORE_INTERNAL, RULE_INSTANTIATED,
                             RULE_INTERNAL, SIDE, SIDE_GROUPS, SIDE_INTERNAL)
from satassume.solver import Solver
from satassume.sympy_api import ask

SIDE_IDX = [BASIS_INDEX[p] for p in SIDE]
P, C, I = BASIS_INDEX['prime'], BASIS_INDEX['composite'], BASIS_INDEX['imaginary']


def _sat(clauses, a):
    return all(any(a[abs(l) - 1] == (l > 0) for l in c) for c in clauses)


def _projected_models(clauses, drop):
    keep = [i for i in range(NPRED) if i not in drop]
    out = set()
    for a in itertools.product((False, True), repeat=NPRED):
        if _sat(clauses, a):
            out.add(tuple(a[i] for i in keep))
    return out


def test_groups_partition_the_rule_base():
    got = list(RULE_CORE) + [c for _, cls in SIDE_GROUPS for c in cls]
    assert sorted(got) == sorted(RULE_INSTANTIATED)
    assert not any(abs(l) - 1 in SIDE_IDX for c in RULE_CORE for l in c)


@pytest.mark.parametrize("touched", [s for k in range(4) for s in itertools.combinations(SIDE_IDX, k)])
def test_projection(touched):
    touched = set(touched)
    drop = set(SIDE_IDX) - touched
    part = list(RULE_CORE) + [c for s, cls in SIDE_GROUPS if s <= touched for c in cls]
    assert _projected_models(part, drop) == _projected_models(RULE_INSTANTIATED, drop)


def _solver(nblocks=1):
    s = Solver()
    s.set_rule_block(RULE_CORE_INTERNAL, NPRED, side=SIDE_INTERNAL)
    bases = [1 + k * NPRED for k in range(nblocks)]
    for b in bases:
        s.register_block(b)
    return s, bases


def v(b, pred):
    return b + BASIS_INDEX[pred]


def test_untouched_adds_nothing():
    s, (b,) = _solver()
    s.add_clause([v(b, 'integer'), v(b, 'zero')])
    assert s.solve()
    assert len(s._clauses) == 1 and s._side_done.get(b, 0) == 0


def test_root_unit_on_side_var():
    s, (b,) = _solver()
    s.add_clause([v(b, 'prime')])
    assert s.propagate()
    assert s.value(v(b, 'integer')) and s.value(v(b, 'extended_positive'))
    assert s.value(v(b, 'composite')) is None       # composite untouched


def test_assumption_on_side_var():
    s, (b,) = _solver()
    assert s.entails(v(b, 'extended_positive'), [v(b, 'composite')]) is True
    assert s.entails(-v(b, 'extended_real'), [v(b, 'imaginary')]) is True
    assert s.entails(v(b, 'prime'), [v(b, 'even'), v(b, 'extended_positive'), -v(b, 'composite')]) is True


def test_mentioned_query_literal():
    s, (b,) = _solver()
    s.add_clause([v(b, 'even')])
    s.add_clause([v(b, 'extended_positive')])
    assert s.entails(-v(b, 'composite'), [v(b, 'prime')]) is True
    with pytest.raises(ValueError):
        s.entails(v(b, 'integer'), [v(b, 'prime'), v(b, 'composite')])


def test_block_registered_after_mention():
    s = Solver()
    s.set_rule_block(RULE_CORE_INTERNAL, NPRED, side=SIDE_INTERNAL)
    s.ensure_vars(NPRED)
    s.add_clause([1 + P, 1 + C])                    # mentions both before the block exists
    s.register_block(1)
    assert s.entails(1 + BASIS_INDEX['extended_positive']) is True
    assert s.entails(1 + BASIS_INDEX['integer']) is True


def test_models_satisfy_full_rules():
    rng = random.Random(0)
    for _ in range(300):
        s, bases = _solver(2)
        full = [[(b + (l >> 1)) * (-1 if l & 1 else 1) for l in c] for b in bases for c in RULE_INTERNAL]
        for _ in range(rng.randint(1, 4)):
            c = [rng.choice(bases) + rng.randrange(NPRED) for _ in range(rng.randint(1, 3))]
            s.add_clause([x if rng.random() < .5 else -x for x in c])
        if not s.solve():
            continue
        m = s.model()
        assert all(any(m[abs(l)] == (l > 0) for l in c) for c in full)


def _ref_solver(nblocks=1):
    s = Solver()
    s.set_rule_block(RULE_INTERNAL, NPRED)
    for k in range(nblocks):
        s.register_block(1 + k * NPRED)
    return s


def test_random_entailment_matches_full_block():
    rng = random.Random(1)
    for _ in range(400):
        a, r = _solver(2)[0], _ref_solver(2)
        cls = []
        for _ in range(rng.randint(0, 3)):
            c = [rng.choice((1, 1 + NPRED)) + rng.randrange(NPRED) for _ in range(rng.randint(1, 3))]
            cls.append([x if rng.random() < .5 else -x for x in c])
        for c in cls:
            a.add_clause(c)
            r.add_clause(c)
        assum = [(1 + rng.randrange(2 * NPRED)) * rng.choice((1, -1)) for _ in range(rng.randint(0, 2))]
        lit = (1 + rng.randrange(2 * NPRED)) * rng.choice((1, -1))
        try:
            want = r.entails(lit, assum)
        except ValueError:
            with pytest.raises(ValueError):
                a.entails(lit, assum)
            continue
        assert a.entails(lit, assum) == want, (cls, assum, lit)


def test_queries():
    x, y = symbols('x y')
    assert ask(Q.integer(x), Q.prime(x)) is True
    assert ask(Q.composite(x), Q.prime(x)) is False
    assert ask(Q.prime(x) | Q.composite(x), Q.even(x) & Q.positive(x)) is True
    assert ask(Q.real(x), Q.imaginary(x)) is False
    assert ask(Q.imaginary(x * y), Q.imaginary(x) & Q.real(y) & Q.nonzero(y)) is True
    assert ask(Q.positive(x + y), Q.prime(x) & Q.composite(y)) is True
