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


# ---------------------------------------------------------------------------
# unevaluated products (review of #160): c*t is read through t only when the
# product of the other factors, built, is those factors
# ---------------------------------------------------------------------------

def _uneval_cases():
    from sympy import Mul
    x, y = symbols('x y')
    R = Rational
    e1 = Mul(R(1, 3), x, 3 / x, evaluate=False)      # nan at x = 0
    e2 = Mul(R(1, 3), x, 0, evaluate=False)           # nan at x = oo
    e3 = Mul(3, x, 1 / x, evaluate=False) + y / 3     # nan at x = 0
    e4 = Mul(R(1, 3), x, 0, evaluate=False) + y       # nan at x = oo
    return [
        (Q.integer(e1), True), (Q.odd(e1), True),
        (Q.integer(e2), True), (Q.even(e2), True),
        (Q.integer(e3), Q.integer(y / 3)), (Q.integer(e4), Q.integer(y)),
    ]


@pytest.mark.parametrize("prop,assum", _uneval_cases())
def test_unevaluated_product_is_not_read_as_its_value(prop, assum):
    assert ask(prop, assum) is not True


def test_linear_needs_the_rest_to_keep_its_factors():
    from sympy import Mul
    x, y = symbols('x y')
    third = Rational(1, 3)
    assert not IA.linear(Mul(third, x, 3 / x, evaluate=False))
    assert not IA.linear(Mul(third, x, 0, evaluate=False))
    assert not IA.owns(Mul(third, x, 0, evaluate=False))
    assert IA.linear(Mul(third, x, y, evaluate=False))
    assert IA.linear(Mul(third, x * y / 3, evaluate=False))   # two factors: c*t
    assert IA.linear(third * x * y) and IA.owns(third * x * y)


# ---------------------------------------------------------------------------
# clause validity through the adapter: random, partly unevaluated SymPy
# nodes on a real session, every clause checked on substituted values
# ---------------------------------------------------------------------------

def _rebuild(e):
    """The value of ``e`` with every node evaluated (an unevaluated
    ``Mul(x, 1/x)`` at x = 0 is ``nan``)."""
    if not e.args:
        return e
    return e.func(*[_rebuild(a) for a in e.args])


def _random_node(rng, syms, depth):
    from sympy import Add, Float, I, Mul, oo, pi
    x, y = syms
    leaves = [x, y, x, y, x * y, 1 / x, S.Zero, oo, I, Float(2.0), pi, Rational(1, 2), S(3)]
    coeffs = [Rational(1, 2), Rational(-1, 2), Rational(1, 3), Rational(2, 3), Rational(3, 2),
              S(2), S(-1), S(3), Rational(1, 6)]

    def sub():
        if depth > 0 and rng.random() < 0.35:
            return _random_node(rng, syms, depth - 1)
        return rng.choice(leaves)

    ev = rng.random() < 0.3
    if rng.random() < 0.5:
        args = [sub() for _ in range(rng.randint(2, 5))]
        args = [Mul(rng.choice(coeffs), a, evaluate=ev) if rng.random() < 0.5 else a for a in args]
        return Add(*args, evaluate=ev)
    factors = [sub() for _ in range(rng.randint(1, 3))]
    return Mul(rng.choice(coeffs), *factors, evaluate=ev)


#: values of x and y: integers, fractions, infinities, a non-real and a Float
def _values():
    from sympy import Float, I, oo, zoo
    R = Rational
    return [S.Zero, S.One, S(-1), S(2), S(3), R(1, 2), R(1, 3), R(-2, 3), R(5, 6),
            oo, -oo, zoo, I, 1 + I, Float(2.0)]


def _truth(v, pred):
    """Whether the value ``v`` is an (even) integer.  A Float is the
    number it denotes (the session knows nothing of ``integer(2.0)``, and
    SymPy evaluates ``2.0 - 2`` to the Integer 0)."""
    if getattr(v, "is_Float", False) and v.is_finite:
        if not float(v).is_integer():
            return False
        n = int(v)
    elif getattr(v, "is_Integer", False):
        n = int(v)
    else:
        return False
    return pred == "integer" or n % 2 == 0


@pytest.mark.parametrize("seeds", [range(0, 100), range(100, 200), range(200, 300)])
def test_adapter_clauses_are_valid_on_values(seeds):
    from satassume.engine import Engine, Session
    syms = symbols('x y')
    vals = _values()
    assigns = [{syms[0]: a, syms[1]: b} for a in vals for b in vals]
    full = (1 << len(assigns)) - 1
    checked = told = 0
    for seed in seeds:
        rng = random.Random(seed)
        session = Session(Engine())
        ad = IA.IntLatAdapter(session)
        nodes = [_random_node(rng, syms, 2) for _ in range(rng.randint(1, 3))]
        for n in nodes:
            if IA.linear(n):
                ad.tell(n)
                told += 1
        if not ad.attached:
            continue
        th = ad.theory
        atoms = {}
        for n in ad.done:
            b = session.base[n]
            atoms[b + IA._INT] = (n, "integer")
            atoms[b + IA._EVEN] = (n, "even")
        masks = {}
        values = {}
        for v, (n, pred) in atoms.items():
            if n not in values:
                row = []
                for a in assigns:
                    try:
                        row.append(_rebuild(n.xreplace(a)))
                    except Exception:   # noqa: BLE001 - an undefined value: no atom holds
                        row.append(S.NaN)
                values[n] = row
            m = 0
            for i, val in enumerate(values[n]):
                if _truth(val, pred):
                    m |= 1 << i
            masks[v] = m
        assert set(th.frac) <= set(masks)

        def valid(clause):
            m = 0
            for l in clause:
                m |= masks[l] if l > 0 else full & ~masks[-l]
            return m == full

        for _run in range(3):
            val = dict(th.val)
            th.push_level()
            for _step in range(6):
                free = [v for v in th.frac if v not in val]
                if not free:
                    break
                v = rng.choice(free)
                lit = v if rng.random() < 0.5 else -v
                val[v] = lit > 0
                th.assert_lit(lit)
                conflict = False
                while not conflict:
                    r = th.check()
                    if r is not None:
                        assert valid(r[1]), r[1]
                        checked += 1
                        conflict = True
                        break
                    out = list(th.propagate())
                    if not out:
                        break
                    for l, clause in out:
                        assert valid(clause), clause
                        checked += 1
                        u = abs(l)
                        if u in val:
                            if val[u] != (l > 0):
                                conflict = True
                            continue
                        val[u] = l > 0
                        th.assert_lit(l)
                if conflict:
                    break
            th.pop_level()
    assert told and checked


# ---------------------------------------------------------------------------
# stage B: products of integral forms (Poly), brute force over base values
# ---------------------------------------------------------------------------

_PCOEFFS = [F(1), F(-1), F(1, 2), F(1, 3), F(1, 4), F(3, 4), F(1, 6), F(1, 8), F(3, 8),
            F(5, 12), F(1, 9)]
_PCONSTS = [F(0), F(0), F(1, 2), F(-1, 4), F(1, 8), F(1, 3), F(-1, 6)]


def _poly_case(rng):
    """Bases ``0..nb-1``, the product term ``nb`` (a random
    :class:`Poly`), random atoms over the three; the assignments: base
    values (integers covering every residue mod 72, fractions, None for
    a non-finite one), the product's value the polynomial's (None when a
    base is None)."""
    from satassume.theories.intlat.intlat import Poly
    nb = rng.choice((1, 1, 2))
    u = nb
    factors = []
    for _ in range(rng.randint(1, 3)):
        a = tuple(rng.randint(-2, 2) for _ in range(nb))
        if not any(a):
            a = (1,) + a[1:]
        factors.append((a, rng.randint(-2, 2), rng.randint(1, 3)))
    poly = Poly(u, tuple(range(nb)), factors)
    if nb == 1:
        vals = [F(i) for i in range(-36, 36)] + [F(1, 2), F(-3, 2), F(1, 3), F(5, 4), None]
    else:
        vals = [F(i) for i in range(-12, 12)] + [F(1, 2), F(2, 3), None]
    assigns = [()]
    for _ in range(nb):
        assigns = [a + (v,) for a in assigns for v in vals]
    rows = []
    for a in assigns:
        if any(v is None for v in a):
            rows.append(a + (None,))
            continue
        p = F(1)
        for co, c, k in factors:
            p *= (sum(x * v for x, v in zip(co, a)) + c) ** k
        rows.append(a + (p,))
    atoms = {}
    for v in range(1, rng.randint(4, 8)):
        if rng.random() < 0.6:
            cols = [u] + [b for b in range(nb) if rng.random() < 0.4]
        else:
            cols = rng.sample(range(nb), rng.randint(1, nb))
        f = {c: rng.choice(_PCOEFFS) for c in cols}
        k = rng.choice(_PCONSTS)
        if k:
            f[CONST] = k
        atoms[v] = f
    for b in range(nb):         # integer(x) for each base
        atoms[len(atoms) + 1] = {b: F(1)}
    masks = {}
    for v, f in atoms.items():
        m = 0
        for i, row in enumerate(rows):
            if any(row[c] is None for c in f if c != CONST):
                continue
            val = f.get(CONST, 0) + sum(x * row[c] for c, x in f.items() if c != CONST)
            if val.denominator == 1:
                m |= 1 << i
        masks[v] = m
    return poly, atoms, masks, (1 << len(rows)) - 1


def _poly_theory(poly, atoms):
    th = IntLatTheory()
    for v, f in atoms.items():
        th.register_atom(v, (f, True))
    th.define_poly(poly)
    return th


@pytest.mark.parametrize("seeds", [range(0, 120), range(120, 240)])
def test_poly_clauses_are_valid_and_pop_restores(seeds):
    checked = [0]
    for seed in seeds:
        rng = random.Random(seed)
        poly, atoms, masks, full = _poly_case(rng)

        def derived(trail):
            th = _poly_theory(poly, atoms)
            th.push_level()
            for l in trail:
                th.assert_lit(l)
            if th.check() is not None:
                return None
            return sorted(l for l, _ in th.propagate())

        for _run in range(4):
            th = _poly_theory(poly, atoms)
            val, levels = {}, []
            for _step in range(8):
                free = [v for v in atoms if v not in val]
                if not free:
                    break
                v = rng.choice(free)
                # the bases' integrality first, mostly: the products' rows need it
                ints = [w for w in free if len(atoms[w]) == 1 and poly.u not in atoms[w]
                        and atoms[w].get(next(iter(atoms[w]))) == 1]
                if ints and rng.random() < 0.7:
                    v, lit = ints[0], ints[0]
                else:
                    lit = v if rng.random() < 0.5 else -v
                th.push_level()
                levels.append(dict(val))
                val[v] = lit > 0
                th.assert_lit(lit)
                ok = _fixpoint(th, val, masks, full, checked)
                if not ok or rng.random() < 0.3:
                    th.pop_level()
                    val = levels.pop()
                    got = derived([v if b else -v for v, b in val.items()])
                    assert (th.check() is None) == (got is not None)
                    if got is not None:
                        assert sorted(l for l, _ in th.propagate()) == got
    assert checked[0] > 100


def test_kernel_and_residue():
    from satassume.theories.intlat.intlat import _kernel, _residue, _moduli
    # u = x**2 at every x mod 8: u - x**2 is 0, so the relations with
    # (c_u, c_x, c_0) and c_u*x**2 + c_x*x + c_0 == 0 mod 8 for all x
    pts = {(x * x % 8, x, 1) for x in range(8)}
    basis = _kernel(pts, 3, 8)
    for v in basis:
        assert all(sum(a * b for a, b in zip(v, p)) % 8 == 0 for p in pts)
    # (u - x)/2 is a relation (x**2 == x mod 2): 4*(1, -1, 0) is in span + 8Z^3
    lat = {}
    for v in basis + [[8, 0, 0], [0, 8, 0], [0, 0, 8]]:
        insert(lat, {i: x for i, x in enumerate(v) if x}, frozenset())
    assert reduce(lat, {0: 4, 1: -4}) is not None
    assert reduce(lat, {0: 2, 1: -2}) is None
    # odd x: (x - 1)/2 and x/1 integral -> residue (1, 1) mod 2
    rows = {CONST: ({CONST: 8}, frozenset())}
    insert(rows, {0: 8}, frozenset({1}))
    insert(rows, {0: 4, CONST: -4}, frozenset({2}))
    assert _residue(rows, 0, 8, 2, 3) == (1, 1, frozenset({1, 2}))
    assert _moduli(24) == [(2, 3), (3, 1)] and _moduli(1000003) == []
    assert _moduli(128) == [(2, 6)]


n_, m_ = symbols('n m')
POLY_ANSWERS = [
    (Q.integer(n_*(n_ + 1)*(n_ + 2)/6), Q.integer(n_), True),
    (Q.integer((n_**2 - 1)/8), Q.odd(n_), True),
    (Q.integer(n_**2/4), Q.even(n_), True),
    (Q.integer(n_*m_/4), Q.even(n_) & Q.even(m_), True),
    (Q.integer((n_**3 - n_)/6), Q.integer(n_), True),
    (Q.integer(n_**2/4), Q.odd(n_), False),
    (Q.integer((n_**2 + 1)/4), Q.integer(n_), False),
    (Q.integer((n_**2 + 1)/2), Q.odd(n_), True),
    (Q.even(n_), Q.integer(n_) & Q.integer(n_**2/4), True),
    (Q.odd(n_), Q.integer(n_) & Q.integer((n_**2 - 1)/8), True),
    (Q.integer(n_**4/16 + n_/2), Q.even(n_), True),
    (Q.integer(n_*(n_ + 1)*(2*n_ + 1)/6), Q.integer(n_), True),
    (Q.integer((n_**5 - n_)/30), Q.integer(n_), True),
    (Q.integer(n_*m_*(n_ + m_)/2), Q.integer(n_) & Q.integer(m_), True),
    (Q.integer(n_**2/3 + m_/3), Q.integer(n_) & Q.integer((m_ - 1)/3), False),
]


@pytest.mark.parametrize("prop,assum,expected", POLY_ANSWERS)
def test_poly_answers(prop, assum, expected):
    assert ask(prop, assum) is expected


@pytest.mark.parametrize("prop,assum,expected", POLY_ANSWERS)
def test_poly_answers_against_values(prop, assum, expected):
    rng = random.Random(1)
    syms = sorted(prop.free_symbols | assum.free_symbols, key=str)
    seen = 0
    for _ in range(600):
        sub = {s: Rational(rng.randint(-30, 30), rng.choice((1, 1, 1, 2, 3))) for s in syms}
        if not _holds(assum, sub):
            continue
        seen += 1
        assert _holds(prop, sub) is expected, sub
    assert seen


def test_poly_is_not_read_through_other_factors():
    # pi, 1/x, a non-integer coefficient inside a factor, a symbolic
    # power, a Float factor: no product of integral forms (each is not an
    # integer at some even x, y; Mul(x, 1/x, y) is nan at x = 0)
    from sympy import Float, Mul, pi
    x, y = symbols('x y')
    for t in (pi*x*y, x*y/(x + 1), x**y*y, x*(x + Rational(1, 3))*y,
              Mul(x, 1/x, y, evaluate=False), Mul(x, y, Float(0.5), y, evaluate=False)):
        assert ask(Q.integer(t/4), Q.even(x) & Q.even(y)) is not True, t
