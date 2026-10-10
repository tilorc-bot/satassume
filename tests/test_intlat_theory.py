"""The INTLAT theory (issue #149, T2): every clause it emits is valid
(brute force over term values), backtracking restores its state, the
lattice operations, and the answers it adds end to end."""
from __future__ import annotations

import random
from fractions import Fraction as F

import pytest

sympy = pytest.importorskip("sympy")

from sympy import Q, Rational, S, symbols

from satassume.sympy_api import ask
from satassume.theories.intlat import intlat_adapter as IA
from satassume.theories.intlat.intlat import CONST, IntLatTheory, Lattice, insert, reduce


# ---------------------------------------------------------------------------
# clause validity, brute force
# ---------------------------------------------------------------------------

#: coefficient and constant pools: the denominators of the adapter's forms
#: (``x/2``, ``x/3``, ``even`` halves them)
_COEFFS = [F(1), F(-1), F(2), F(1, 2), F(-1, 2), F(3, 2), F(1, 3), F(2, 3), F(1, 4), F(1, 6)]
_CONSTS = [F(0), F(0), F(1), F(1, 2), F(-1, 2), F(1, 3), F(1, 4)]
#: term values: multiples of 1/12 (1/6 for three terms) in [0, 6) and None, a non-finite or inexact value (``oo``,
#: ``nan``, a Float): every atom over that term is false
_GRID = {2: [F(k, 12) for k in range(72)] + [None],
         3: [F(k, 6) for k in range(36)] + [None]}


def _atom(rng, nterms):
    """A random form over the terms ``0..nterms-1``, and the term set of
    its node (an inexact node keeps a cancelled term)."""
    cols = rng.sample(range(nterms), rng.randint(1, nterms))
    f = {c: rng.choice(_COEFFS) for c in cols}
    k = rng.choice(_CONSTS)
    if k:
        f[CONST] = k
    exact = rng.random() < 0.85
    terms = set(cols)
    if not exact:
        rest = [c for c in range(nterms) if c not in cols]
        if not rest:
            exact = True
        else:
            terms.add(rng.choice(rest))
    return f, exact, frozenset(terms)


def _masks(atoms, nterms):
    """Bit ``i`` of mask ``v``: atom ``v`` true under assignment ``i``."""
    grid = _GRID[nterms]
    assigns = [()]
    for _ in range(nterms):
        assigns = [a + (u,) for a in assigns for u in grid]
    out = {}
    for v, (f, _exact, terms) in atoms.items():
        m = 0
        for i, a in enumerate(assigns):
            if any(a[t] is None for t in terms):
                continue
            val = f.get(CONST, 0) + sum(x * a[k] for k, x in f.items() if k != CONST)
            if val.denominator == 1:
                m |= 1 << i
        out[v] = m
    return out, (1 << len(assigns)) - 1


def _valid(clause, masks, full):
    m = 0
    for l in clause:
        m |= masks[l] if l > 0 else full & ~masks[-l]
    return m == full


def _theory(atoms):
    th = IntLatTheory()
    for v, (f, exact, _terms) in atoms.items():
        th.register_atom(v, (f, exact))
    return th


def _fixpoint(th, val, masks, full, checked):
    """Propagate to a fixpoint, asserting what the theory derives; check
    every clause.  False on a conflict."""
    while True:
        r = th.check()
        if r is not None:
            ok, clause = r
            assert not ok
            assert _valid(clause, masks, full), clause
            assert all(val.get(abs(l)) == (l < 0) for l in clause), clause
            checked[0] += 1
            return False
        out = list(th.propagate())
        if not out:
            return True
        for lit, clause in out:
            assert clause[0] == lit
            assert _valid(clause, masks, full), clause
            assert all(val.get(abs(l)) == (l < 0) for l in clause[1:]), clause
            checked[0] += 1
            v = abs(lit)
            if v in val:
                if val[v] != (lit > 0):
                    return False    # the clause is falsified: a conflict
                continue
            val[v] = lit > 0
            th.assert_lit(lit)


def _derived(atoms, trail):
    """What a fresh theory derives from ``trail`` at one level."""
    th = _theory(atoms)
    th.push_level()
    for l in trail:
        th.assert_lit(l)
    if th.check() is not None:
        return None
    return sorted(l for l, _ in th.propagate())


@pytest.mark.parametrize("nterms,seeds", [(2, range(150)), (3, range(12))])
def test_every_clause_is_valid_and_pop_restores(nterms, seeds):
    checked = [0]
    for seed in seeds:
        rng = random.Random(seed * 7 + nterms)
        atoms = {v: _atom(rng, nterms) for v in range(1, rng.randint(3, 6))}
        masks, full = _masks(atoms, nterms)
        for _run in range(4):
            th = _theory(atoms)
            val, trail, levels = {}, [], []
            for _step in range(8):
                free = [v for v in atoms if v not in val]
                if not free:
                    break
                v = rng.choice(free)
                lit = v if rng.random() < 0.5 else -v
                th.push_level()
                levels.append((dict(val), list(trail)))
                val[v] = lit > 0
                trail.append(lit)
                th.assert_lit(lit)
                ok = _fixpoint(th, val, masks, full, checked)
                trail = [l for l in (v if b else -v for v, b in val.items())]
                if not ok or rng.random() < 0.3:
                    # backtrack: the popped theory derives what a fresh one
                    # does from the remaining trail
                    th.pop_level()
                    val, trail = levels.pop()
                    got = _derived(atoms, trail)
                    assert (th.check() is None) == (got is not None)
                    if got is not None:
                        assert sorted(l for l, _ in th.propagate()) == got
    assert checked[0] > 0


def test_lattice_insert_reduce():
    # d = 6: x/2 integral and x/3 integral give x/6 integral
    rows = {CONST: ({CONST: 6}, frozenset())}
    insert(rows, {0: 3}, frozenset((1,)))      # x/2
    insert(rows, {0: 2}, frozenset((2,)))      # x/3
    assert reduce(rows, {0: 1}) == frozenset((1, 2))
    assert reduce(rows, {0: 1, CONST: 3}) is None      # x/6 + 1/2
    assert reduce(rows, {0: 1, CONST: 6}) == frozenset((1, 2))


def test_lattice_conflict_and_refutes():
    lat = Lattice(6)
    lat.add_pos({0: 6}, 1, frozenset((0,)))            # x
    assert lat.conflict is None
    # x/2 + 1/3 is not integral when x is
    assert lat.refutes({0: 3, CONST: 2}, frozenset((0,))) == frozenset((1,))
    assert lat.refutes({0: 3}, frozenset((0,))) is None
    lat.add_pos({0: 6, CONST: 3}, 2, frozenset((0,)))  # x + 1/2
    assert lat.conflict == frozenset((1, 2))


def test_parity_step():
    # odd(x) & odd(y) -> even(x + y): x, ~x/2, y, ~y/2 give (x + y)/2
    lat = Lattice(2)
    for lit, f in ((1, {0: 2}), (2, {1: 2})):
        lat.add_pos(f, lit, frozenset(f))
    lat.add_neg({0: 1}, -3, frozenset((0,)))
    lat.add_neg({1: 1}, -4, frozenset((1,)))
    why = lat.implies({0: 1, 1: 1})
    assert why is not None and why <= {1, 2, -3, -4}
    assert lat.implies({0: 1}) is None


def test_inexact_negation_is_not_read():
    # a node whose terms cancel: its negative literal says nothing
    th = IntLatTheory()
    th.register_atom(1, ({0: F(1)}, False))
    th.register_atom(2, ({0: F(1)}, True))
    th.push_level()
    th.assert_lit(-1)
    assert th.check() is None
    assert list(th.propagate()) == []


# ---------------------------------------------------------------------------
# ownership
# ---------------------------------------------------------------------------

x, y, z, w, a, b, c, d, e, k, n = symbols("x y z w a b c d e k n")


@pytest.mark.parametrize("node,owned", [
    (a + b + c + d, True),          # over MAX_ADD_SMALL
    (x/2 + y, True),                # a non-integer coefficient
    (k/2 - S.Half, True),
    (x/3, True),                    # c.q > 2
    (x/2, False),                   # coeff.half row
    (x + S.Half, False),            # the subtraction rows
    (x/y + S.Half, False),
    (x + y + Rational(1, 3), False),
    (2*x + y, False),
    (x*y, False),
])
def test_owns(node, owned):
    assert IA.owns(node) is owned


def test_cap_agrees_with_the_templates():
    from satassume.knowledge.templates import core
    assert IA.MAX_ADD_SMALL == core.MAX_ADD_SMALL


# ---------------------------------------------------------------------------
# answers
# ---------------------------------------------------------------------------

ANSWERS = [
    (Q.even(a + b + c + d), Q.odd(a) & Q.odd(b) & Q.even(c) & Q.even(d), True),
    (Q.odd(a + b + c + d + e), Q.odd(a) & Q.odd(b) & Q.odd(c) & Q.even(d) & Q.even(e), True),
    (Q.integer((a + b + c + d + e)/2), Q.odd(a) & Q.odd(b) & Q.odd(c) & Q.odd(d) & Q.even(e), True),
    (Q.integer(x/2), Q.integer(x/4), True),
    (Q.integer(x/2 + Rational(1, 3)), Q.integer(x), False),
    (Q.integer(x/6), Q.integer(x/2) & Q.integer(x/3), True),
    (Q.odd(x/3), Q.even(x), False),
    (Q.odd(k/2 + S.Half), Q.odd(k) & Q.odd(k/2 - S.Half), False),
    (Q.odd(k/2 + S.Half), Q.odd(k) & Q.even(k/2 - S.Half), True),
    (Q.even(k/2 + S.Half), Q.odd(k) & Q.odd(k/2 - S.Half), True),
    (Q.integer(x), Q.integer(x + S.Half), False),
    (Q.integer((x + 1)/2), Q.odd(x), True),
    (Q.integer(x/2), Q.odd(x), False),
    (Q.integer(x*y/2 + S.Half), Q.odd(x*y), True),
    (Q.integer(n/2 + S.Half), Q.odd(n), True),
    (Q.integer(a/2 + b/2 + c/2 + S.Half), Q.odd(a) & Q.odd(b) & Q.even(c), False),
    (Q.even(x - y), Q.even(x) & Q.even(y), True),
    (Q.integer(x), Q.even(x + y) & Q.odd(y), True),
]


@pytest.mark.parametrize("prop,assum,expected", ANSWERS)
def test_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


@pytest.mark.parametrize("prop,assum,expected", ANSWERS)
def test_answers_against_values(prop, assum, expected):
    # every definite answer holds on random integer values of the symbols
    rng = random.Random(0)
    syms = sorted(prop.free_symbols | assum.free_symbols, key=str)
    seen = 0
    for _ in range(400):
        sub = {s: Rational(rng.randint(-24, 24), rng.choice((1, 1, 2, 3, 4))) for s in syms}
        if not _holds(assum, sub):
            continue
        seen += 1
        assert _holds(prop, sub) is expected, sub
    assert seen


def _holds(p, sub):
    if p.func is sympy.And:
        return all(_holds(q, sub) for q in p.args)
    v = p.arguments[0].subs(sub)
    return {Q.integer: v.is_integer, Q.even: v.is_even, Q.odd: v.is_odd}[p.function]
