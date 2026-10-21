"""Compiling the parity connectives (``Equivalent``, ``Exclusive``, ``ITE``):
the clauses have exactly the formula's truth table, and nesting them keeps
the encoding linear (#241: a binary ``Equivalent`` encoded each argument
twice, so a 20-argument ``Xor`` took about 50 s)."""
import itertools
import random
import time

import pytest
from sympy import ITE as SITE, Equivalent as SEquivalent, Q, Symbol, Xor

from satassume.knowledge.compile import VarTable, compile_formula, formula_literal
from satassume.sat.formula import (And, Equivalent, Exclusive, ITE, Implies, Not, Or, P,
                                   TRUE, FALSE)
from satassume.sat.solver import Solver
from satassume.sympy_api import ask

ATOMS = [P('c%d' % i, None) for i in range(4)]


def _value(f, env):
    if f is TRUE or f is FALSE:
        return f
    if isinstance(f, P):
        return env[f]
    v = [_value(a, env) for a in f.args]
    if isinstance(f, Not):
        return not v[0]
    if isinstance(f, And):
        return all(v)
    if isinstance(f, Or):
        return any(v)
    if isinstance(f, Implies):
        return not v[0] or v[1]
    if isinstance(f, Equivalent):
        return len(set(v)) <= 1
    if isinstance(f, Exclusive):
        return sum(v) <= 1
    if isinstance(f, ITE):
        return v[1] if v[0] else v[2]
    raise TypeError(f)


def _random(r, depth):
    if depth == 0 or r.random() < 0.2:
        a = r.choice(ATOMS + [TRUE, FALSE] if r.random() < 0.1 else ATOMS)
        return Not(a) if a in ATOMS and r.random() < 0.3 else a
    k = r.choice(['eq', 'eq', 'ex', 'ite', 'ite', 'and', 'or', 'not', 'imp'])
    sub = lambda: _random(r, depth - 1)
    if k == 'eq':
        return Equivalent(*[sub() for _ in range(r.randint(1, 3))])
    if k == 'ex':
        return Exclusive(*[sub() for _ in range(r.randint(1, 3))])
    if k == 'ite':
        return ITE(sub(), sub(), sub())
    if k == 'and':
        return And(sub(), sub())
    if k == 'or':
        return Or(sub(), sub())
    if k == 'imp':
        return Implies(sub(), sub())
    return Not(sub())


def _table(make):
    """Truth table of the clauses ``make(table, emit)`` emits, projected on
    ``ATOMS`` (``make`` returns an extra unit literal, or None)."""
    table = VarTable()
    clauses = []
    lits = [table.var(a) for a in ATOMS]
    unit = make(table, clauses.append)
    out = []
    for bits in itertools.product([False, True], repeat=len(ATOMS)):
        s = Solver()
        s.ensure_vars(len(table))
        for c in clauses:
            s.add_clause(c)
        assume = [l if b else -l for l, b in zip(lits, bits)]
        if unit is not None:
            assume.append(unit)
        out.append(s.solve(assume))
    return out


@pytest.mark.parametrize('seed', range(150))
def test_compiled_truth_table(seed):
    r = random.Random(seed)
    f = _random(r, 4)
    want = [bool(_value(f, dict(zip(ATOMS, bits))))
            for bits in itertools.product([False, True], repeat=len(ATOMS))]
    assert _table(lambda t, e: compile_formula(f, t, e)) == want
    assert _table(lambda t, e: compile_formula(Not(f), t, e)) == [not w for w in want]
    assert _table(lambda t, e: formula_literal(f, t, e)) == want
    assert _table(lambda t, e: -formula_literal(f, t, e)) == [not w for w in want]


def _size(f):
    table = VarTable()
    clauses = []
    compile_formula(f, table, clauses.append)
    return len(clauses)


def test_nested_parity_is_linear():
    atoms = [P('c%d' % i, None) for i in range(81)]
    for build in [
        lambda n: _fold(lambda a, b: Not(Equivalent(a, b)), atoms[:n]),   # Xor
        lambda n: _fold(Equivalent, atoms[:n]),
        lambda n: _fold(lambda a, b: Equivalent(b, a), atoms[:n]),
        lambda n: _fold(lambda a, b: ITE(a, b, Not(b)), atoms[:n]),
        lambda n: _fold(lambda a, b: Exclusive(a, b, Not(b)), atoms[:n]),
    ]:
        s20, s40, s80 = [_size(build(n + 1)) for n in (20, 40, 80)]
        # each level adds the same number of clauses (it doubled them)
        assert s80 - s40 == 2 * (s40 - s20), (s20, s40, s80)


def _fold(op, xs):
    f = xs[0]
    for x in xs[1:]:
        f = op(f, x)
    return f


def test_issue_241_reproducers():
    """#241: an ``ask`` with a 20-argument ``Xor``, a nested ``Equivalent``
    or ITEs nested in conditions took seconds to minutes."""
    xs = [Symbol('x%d' % i) for i in range(20)]
    ps = [Q.positive(x) for x in xs]
    t0 = time.perf_counter()
    a = Xor(*ps, evaluate=False)
    assert ask(Q.positive(xs[0]), a & ~Q.positive(xs[1])) is None
    e = ps[0]
    for p in ps[1:]:
        e = SEquivalent(e, p, evaluate=False)
    assert ask(Q.positive(xs[0]), e & ~Q.positive(xs[1])) is None
    c = ps[0]
    for i in range(1, 19):
        c = SITE(c, ps[i], ps[i + 1], evaluate=False)
    assert ask(Q.positive(xs[0]), c) is None
    # answers that need the parity: x0 xor x1 with x1 false gives x0
    assert ask(Q.positive(xs[0]), Xor(ps[0], ps[1]) & ~ps[1]) is True
    assert ask(Q.positive(xs[0]), Xor(*ps[:3]) & ~ps[1] & ~ps[2]) is True
    assert ask(Q.positive(xs[0]), Xor(*ps[:3]) & ps[1] & ~ps[2]) is False
    assert time.perf_counter() - t0 < 10     # was minutes
