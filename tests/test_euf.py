"""Unit tests for the EUF theory solver (satassume/euf.py).

Written against the announced interface, independently of the
implementation:

    th = EUFTheory()
    t = th.term(head, args=())      # interned term id; args are term ids
    k = th.value(key)               # interpreted constant, pairwise distinct
    th.register_atom(v, EqAtom(lhs, rhs, positive=True))  # or (lhs, rhs)
    th.assert_lit / check / push_level / pop_level / propagate
    th.find(t), th.equal(a, b), th.explain(a, b) -> asserted literals

``v`` means ``lhs == rhs`` for a positive atom and ``lhs != rhs`` for an
``EqAtom(..., positive=False)``; ``-v`` means the opposite.

This module also holds the *independent oracle* used by
``test_euf_fuzz.py``: a deliberately naive congruence closure (union-find
over every term, merge any two applications with the same head, the same
arity and pairwise equal arguments, repeat until nothing changes), which
shares no code or idea beyond the definition with the implementation.

Improvements over the SymPy references (PR 30010 test_euf_theory.py, PR
30327 test_euf_solver.py) are marked "REF-FLAW" with the flaw they target;
the full list is in ``REFERENCE_FLAWS`` at the end of test_euf_fuzz.py.
"""
from __future__ import annotations

import itertools

import pytest

euf = pytest.importorskip("satassume.euf")
EUFTheory = euf.EUFTheory
EqAtom = euf.EqAtom

from theory_harness import (TheoryCase, Recorder, check_protocol,  # noqa: E402
                            check_solve, check_entails, check_implied)


# ======================================================================
# The independent oracle
# ======================================================================
#
# A problem is a list of term specs over term *indices* (not theory ids):
#   ("c", name)             an uninterpreted constant
#   ("v", key)              an interpreted value; distinct keys are distinct
#   ("a", head, (i, j, ..)) head applied to earlier terms i, j, ...
# and a list of atoms (i, j, positive); atom k has solver variable k + 1.
# Heads are compared together with the arity, so ("a", "f", (i,)) and
# ("a", "f", (i, j)) are unrelated function symbols.

def naive_roots(terms, eqs):
    """Congruence closure the simplest possible way.  Returns root per
    term index."""
    n = len(terms)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for i, j in eqs:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
    apps = [i for i, t in enumerate(terms) if t[0] == "a"]
    changed = True
    while changed:
        changed = False
        for p in apps:
            for q in apps:
                tp, tq = terms[p], terms[q]
                if (tp[1] == tq[1] and len(tp[2]) == len(tq[2])
                        and find(p) != find(q)
                        and all(find(x) == find(y) for x, y in zip(tp[2], tq[2]))):
                    parent[find(p)] = find(q)
                    changed = True
    return [find(i) for i in range(n)]


def naive_consistent(terms, eqs, neqs):
    """Is the conjunction of equalities ``eqs`` and disequalities ``neqs``
    (index pairs) satisfiable?  Ground EUF with distinct values: it is iff
    no disequality and no pair of distinct values is merged by the
    closure of the equalities."""
    roots = naive_roots(terms, eqs)
    if any(roots[i] == roots[j] for i, j in neqs):
        return False
    vals = [roots[i] for i, t in enumerate(terms) if t[0] == "v"]
    return len(vals) == len(set(vals))


def lit_meaning(atoms, lit):
    """``(is_equality, i, j)`` for a solver literal over ``atoms``."""
    i, j, positive = atoms[abs(lit) - 1]
    return ((lit > 0) == positive, i, j)


def split_lits(atoms, lits):
    eqs, neqs = [], []
    for l in lits:
        e, i, j = lit_meaning(atoms, l)
        (eqs if e else neqs).append((i, j))
    return eqs, neqs


def oracle_consistent(terms, atoms, lits):
    eqs, neqs = split_lits(atoms, lits)
    return naive_consistent(terms, eqs, neqs)


def oracle_for_harness(terms, atoms):
    """``consistent(assign)`` for theory_harness.check_*."""
    def consistent(assign):
        return oracle_consistent(terms, atoms,
                                 [v if b else -v for v, b in assign.items()])
    return consistent


def build(terms, atoms, theory=None):
    """Intern the terms and register the atoms on a fresh theory.  Returns
    ``(theory, ids)`` with ``ids[i]`` the theory id of term index i."""
    th = theory if theory is not None else EUFTheory()
    ids = []
    for t in terms:
        if t[0] == "c":
            ids.append(th.term(t[1]))
        elif t[0] == "v":
            ids.append(th.value(t[1]))
        else:
            ids.append(th.term(t[1], tuple(ids[k] for k in t[2])))
    for k, (i, j, positive) in enumerate(atoms):
        th.register_atom(k + 1, EqAtom(ids[i], ids[j], positive))
    return th, ids


def test_oracle_self_check():
    """The oracle on the textbook cases (so a broken oracle cannot make
    every differential test vacuous)."""
    a, b, c = ("c", "a"), ("c", "b"), ("c", "c")
    terms = [a, b, c, ("a", "f", (0,)), ("a", "f", (1,)), ("a", "g", (0, 1)),
             ("a", "g", (1, 0)), ("a", "f", (0, 1)), ("v", 1), ("v", 2)]
    r = naive_roots(terms, [(0, 1)])
    assert r[3] == r[4] and r[5] == r[6] and r[0] != r[2]
    assert r[7] not in (r[3], r[4])                      # arity separates
    r = naive_roots(terms, [(3, 4)])
    assert r[0] != r[1]                                   # not injective
    r = naive_roots(terms, [])
    assert r[5] != r[6]                                   # not commutative
    assert not naive_consistent(terms, [(0, 1), (1, 2)], [(0, 2)])
    assert naive_consistent(terms, [(0, 1)], [(0, 2)])
    assert not naive_consistent(terms, [(0, 8), (0, 9)], [])
    assert not naive_consistent(terms, [(3, 8), (4, 9), (0, 1)], [])
    assert naive_consistent(terms, [(3, 8), (4, 9)], [])
    assert not naive_consistent(terms, [], [(0, 0)])
    # f^3(a) = a and f^5(a) = a give f(a) = a
    tower = [a]
    for k in range(5):
        tower.append(("a", "f", (k,)))
    r = naive_roots(tower, [(3, 0), (5, 0)])
    assert r[1] == r[0]
    r = naive_roots(tower, [(4, 0)])
    assert r[1] != r[0]


# ======================================================================
# Helpers for direct (solver-free) use
# ======================================================================

class B:
    """Small builder: named constants, applications, atoms numbered 1, 2..."""

    def __init__(self):
        self.th = EUFTheory()
        self.n = 0
        self.atoms = {}

    def c(self, *names):
        r = [self.th.term(n) for n in names]
        return r if len(r) > 1 else r[0]

    def app(self, head, *args):
        return self.th.term(head, tuple(args))

    def val(self, key):
        return self.th.value(key)

    def atom(self, a, b, positive=True):
        self.n += 1
        self.th.register_atom(self.n, EqAtom(a, b, positive))
        self.atoms[self.n] = (a, b, positive)
        return self.n


def is_conflict(r):
    return r is not None and r[0] is False


def assert_all(th, lits):
    """Assert ``lits`` in order; return the first conflict, else the
    result of check()."""
    for l in lits:
        r = th.assert_lit(l)
        if is_conflict(r):
            return r
    return th.check()


def conflict_of(th, lits):
    r = assert_all(th, lits)
    assert is_conflict(r), f"expected a conflict, got {r!r}"
    clause = list(r[1])
    assert clause, "empty conflict clause"
    asserted = set(lits)
    assert all(-l in asserted for l in clause), \
        f"conflict clause {clause} is not made of negated asserted literals {lits}"
    return set(clause)


def consistent_after(th, lits):
    r = assert_all(th, lits)
    assert not is_conflict(r), f"unexpected conflict {r!r}"
    return r


# ======================================================================
# Interning
# ======================================================================

def test_interning_is_stable():
    b = B()
    a, c = b.c("a", "c")
    assert b.c("a") == a
    assert b.app("f", a) == b.app("f", a)
    assert b.app("f", a) != b.app("g", a)
    assert b.app("f", a) != b.app("f", c)
    assert b.app("f", a) != a
    assert b.val(1) == b.val(1)
    assert b.val(1) != b.val(2)
    ids = {a, c, b.app("f", a), b.app("g", a, c), b.app("g", c, a), b.val(1), b.val(2)}
    assert len(ids) == 7


def test_term_ids_survive_push_pop():
    # REF-FLAW 30010-rebuild: constants must keep their identity across
    # backtracking (30010 rebuilt everything on backtrack).
    b = B()
    a, c = b.c("a", "c")
    fa = b.app("f", a)
    v = b.atom(a, c)
    b.th.push_level()
    b.th.assert_lit(v)
    b.th.pop_level()
    assert b.c("a") == a and b.app("f", a) == fa


# ======================================================================
# Closure: equality, congruence, what does NOT follow
# ======================================================================

def test_chain_and_symmetry():
    b = B()
    x, y, z, w = b.c("x", "y", "z", "w")
    e1, e2 = b.atom(x, y), b.atom(z, y)          # second one reversed
    consistent_after(b.th, [e1, e2])
    assert b.th.equal(x, z) and b.th.equal(z, x) and b.th.equal(y, x)
    assert not b.th.equal(x, w)
    assert b.th.find(x) == b.th.find(z)


def test_long_chain_all_pairs():
    b = B()
    v = [b.c(f"a{i}") for i in range(20)]
    lits = [b.atom(v[i], v[i + 1]) for i in range(19)]
    consistent_after(b.th, lits[::-1])
    for i, j in itertools.combinations(range(20), 2):
        assert b.th.equal(v[i], v[j])


def test_unary_congruence():
    b = B()
    a, c, x = b.c("a", "c", "x")
    fa, fc = b.app("f", a), b.app("f", c)
    consistent_after(b.th, [b.atom(a, c), b.atom(fa, x)])
    assert b.th.equal(fc, x)


def test_binary_congruence_needs_every_argument():
    b = B()
    a, a2, c, c2 = b.c("a", "a2", "c", "c2")
    g1, g2 = b.app("g", a, c), b.app("g", a2, c2)
    e1 = b.atom(a, a2)
    e2 = b.atom(c, c2)
    b.th.push_level()
    consistent_after(b.th, [e1])
    assert not b.th.equal(g1, g2)
    b.th.push_level()
    consistent_after(b.th, [e2])
    assert b.th.equal(g1, g2)
    b.th.pop_level()
    assert not b.th.equal(g1, g2)
    b.th.pop_level()


def test_congruence_is_not_injectivity():
    b = B()
    a, c = b.c("a", "c")
    consistent_after(b.th, [b.atom(b.app("f", a), b.app("f", c))])
    assert not b.th.equal(a, c)
    b2 = B()
    a, c = b2.c("a", "c")
    h1, h2 = b2.app("h", a, c), b2.app("h", c, a)
    consistent_after(b2.th, [b2.atom(h1, h2)])
    assert not b2.th.equal(a, c)


def test_no_commutativity():
    b = B()
    a, c = b.c("a", "c")
    gac, gca = b.app("g", a, c), b.app("g", c, a)
    assert not b.th.equal(gac, gca)
    consistent_after(b.th, [b.atom(a, c)])
    assert b.th.equal(gac, gca)


def test_distinct_heads_never_merge():
    b = B()
    a, c = b.c("a", "c")
    fa, gc = b.app("f", a), b.app("g", c)
    consistent_after(b.th, [b.atom(a, c)])
    assert not b.th.equal(fa, gc)


def test_arity_is_part_of_the_head():
    # REF-FLAW 30010-currying: f(a, b) was EUFApp(EUFApp(f, a), b), so the
    # unary term f(a) *is* the partial application inside f(a, c).  Merging
    # the unary f(a) with f(b) then forces f(a, c) = f(b, c), which is false
    # for a function symbol used at two arities (legal in SymPy:
    # Function('f')(x) and Function('f')(x, y)).
    b = B()
    a, a2, c = b.c("a", "a2", "c")
    fa, fa2 = b.app("f", a), b.app("f", a2)
    fac, fa2c = b.app("f", a, c), b.app("f", a2, c)
    assert fa != fac
    e = b.atom(fa, fa2)
    ne = b.atom(fac, fa2c, positive=False)
    consistent_after(b.th, [e, ne])
    assert not b.th.equal(fac, fa2c)


def test_arity_unary_value_does_not_leak_into_binary():
    # f(a) = 1 (unary), f(a, c) = 2 (binary) is consistent.
    b = B()
    a, c = b.c("a", "c")
    consistent_after(b.th, [b.atom(b.app("f", a), b.val(1)),
                            b.atom(b.app("f", a, c), b.val(2))])


def test_constant_named_like_a_head_is_a_different_symbol():
    # REF-FLAW 30010-currying: with currying the head f is itself a term.
    # term("f") (a nullary constant) must not be that head, otherwise
    # asserting the constants f = g makes f(a) = g(a).
    b = B()
    a = b.c("a")
    kf, kg = b.c("f", "g")
    fa, ga = b.app("f", a), b.app("g", a)
    consistent_after(b.th, [b.atom(kf, kg), b.atom(fa, ga, positive=False)])
    assert not b.th.equal(fa, ga)


def test_nested_congruence_and_compound_terms():
    b = B()
    x, y, w, z = b.c("x", "y", "w", "z")
    l = b.app("+", b.app("*", x, w), z)
    r = b.app("+", b.app("*", y, w), z)
    fl, fr = b.app("f", l), b.app("f", r)
    consistent_after(b.th, [b.atom(x, y)])
    assert b.th.equal(l, r) and b.th.equal(fl, fr)


def test_self_applied_function():
    b = B()
    a, c = b.c("a", "b")
    g1 = b.app("g", a, c)
    g2 = b.app("g", g1, c)
    g3 = b.app("g", g2, c)
    consistent_after(b.th, [b.atom(g1, a)])
    assert b.th.equal(g2, a) and b.th.equal(g3, a)


def test_iterated_function_cycles():
    b = B()
    p = [b.c("a")]
    for _ in range(5):
        p.append(b.app("f", p[-1]))
    consistent_after(b.th, [b.atom(p[3], p[0]), b.atom(p[5], p[0])])
    assert b.th.equal(p[1], p[0])
    b2 = B()
    q = [b2.c("a")]
    for _ in range(5):
        q.append(b2.app("f", q[-1]))
    consistent_after(b2.th, [b2.atom(q[4], q[0])])
    assert not b2.th.equal(q[1], q[0])
    assert b2.th.equal(q[5], q[1])


def test_terms_interned_after_root_merges_see_them():
    # A term created after its arguments were merged at root must join the
    # right class (the adapter interns lazily as atoms arrive).
    b = B()
    a, c = b.c("a", "c")
    consistent_after(b.th, [b.atom(a, c)])
    fa, fc = b.app("f", a), b.app("f", c)
    assert b.th.equal(fa, fc)
    gfa, gfc = b.app("g", fa, a), b.app("g", fc, c)
    assert b.th.equal(gfa, gfc)
    # and a disequality over them registered afterwards conflicts
    ne = b.atom(gfa, gfc, positive=False)
    assert is_conflict(assert_all(b.th, [ne]))


def test_term_made_at_a_popped_level_keeps_congruence():
    # The adapter may intern terms while levels are open.  A term made at a
    # level that is popped again must still take part in congruence.
    b = B()
    a, c = b.c("a", "c")
    fc = b.app("f", c)
    ac = b.atom(a, c)
    b.th.push_level()
    fa = b.app("f", a)
    gfa = b.app("g", fa, a)
    b.th.pop_level()
    gfc = b.app("g", fc, c)
    b.th.push_level()
    consistent_after(b.th, [ac])
    assert b.th.equal(fa, fc) and b.th.equal(gfa, gfc)
    b.th.pop_level()
    assert not b.th.equal(fa, fc)


def test_term_made_above_root_joins_existing_classes():
    b = B()
    a, c = b.c("a", "c")
    ac = b.atom(a, c)
    b.th.push_level()
    consistent_after(b.th, [ac])
    b.th.push_level()
    fa, fc = b.app("f", a), b.app("f", c)          # made while a = c holds
    assert b.th.equal(fa, fc)
    ne = b.atom(fa, fc, positive=False)            # atom registered above root
    r = assert_all(b.th, [ne])
    assert is_conflict(r) and set(r[1]) == {-ac, -ne}
    b.th.pop_level()
    assert b.th.equal(fa, fc)
    b.th.pop_level()
    assert not b.th.equal(fa, fc)
    b.th.push_level()
    consistent_after(b.th, [ne])                   # f(a) != f(c) alone is fine
    b.th.pop_level()


def test_new_atom_over_new_terms_after_root_merges():
    b = B()
    a, c, d = b.c("a", "c", "d")
    consistent_after(b.th, [b.atom(a, c), b.atom(c, d)])
    fa, fd = b.app("f", a), b.app("f", d)
    e = b.atom(fa, fd)
    assert b.th.explain(fa, fd) is not None
    assert set(b.th.explain(fa, fd)) <= {1, 2}
    assert e


# ======================================================================
# Conflicts and their clauses
# ======================================================================

def test_transitivity_conflict_clause():
    b = B()
    a, c, d = b.c("a", "c", "d")
    ab, bc, ne = b.atom(a, c), b.atom(c, d), b.atom(a, d)
    assert conflict_of(b.th, [ab, -ne, bc]) == {-ab, -bc, ne}


def test_conflict_detected_whatever_the_order():
    for perm in itertools.permutations(range(3)):
        b = B()
        a, c, d = b.c("a", "c", "d")
        lits = [b.atom(a, c), b.atom(c, d), -b.atom(a, d)]
        order = [lits[k] for k in perm]
        assert conflict_of(b.th, order) == {-l for l in lits}


def test_conflict_ignores_disjoint_equalities():
    # REF-FLAW 30327 checked this for one order only.
    for first in (True, False):
        b = B()
        a, c, x, y = b.c("a", "c", "x", "y")
        ab, xy, ne = b.atom(a, c), b.atom(x, y), b.atom(a, c, positive=False)
        lits = [xy, ab, ne] if first else [ab, xy, ne]
        assert conflict_of(b.th, lits) == {-ab, -ne}


def test_conflict_from_congruence():
    b = B()
    a, c = b.c("a", "c")
    ab = b.atom(a, c)
    ne = b.atom(b.app("f", a), b.app("f", c), positive=False)
    assert conflict_of(b.th, [ne, ab]) == {-ab, -ne}


def test_conflict_from_nested_congruence_with_side_equalities():
    b = B()
    a, c, x, y, u = b.c("a", "c", "x", "y", "u")
    ab = b.atom(a, c)
    fx = b.atom(b.app("g", b.app("f", a)), x)
    fy = b.atom(b.app("g", b.app("f", c)), y)
    irrelevant = b.atom(u, a)
    ne = b.atom(x, y)
    clause = conflict_of(b.th, [irrelevant, fx, fy, -ne, ab])
    assert clause == {-ab, -fx, -fy, ne}


def test_negative_polarity_atoms():
    # EqAtom(a, b, positive=False): v means a != b, -v means a == b.
    b = B()
    a, c, d = b.c("a", "c", "d")
    ne = b.atom(a, c, positive=False)
    eq = b.atom(c, a)
    assert conflict_of(b.th, [ne, eq]) == {-ne, -eq}
    b = B()
    a, c, d = b.c("a", "c", "d")
    ne_ac = b.atom(a, c, positive=False)
    ne_cd = b.atom(c, d, positive=False)
    eq_ad = b.atom(a, d)
    consistent_after(b.th, [-ne_ac, -ne_cd])      # a == c, c == d
    assert b.th.equal(a, d)
    assert set(b.th.explain(a, d)) == {-ne_ac, -ne_cd}
    assert is_conflict(assert_all(b.th, [-eq_ad]))


def test_tuple_payload():
    th = EUFTheory()
    a, c = th.term("a"), th.term("c")
    th.register_atom(1, (a, c))
    th.register_atom(2, (c, a))
    assert th.assert_lit(1) is None
    assert th.equal(a, c)
    r = assert_all(th, [-2])
    assert is_conflict(r) and set(r[1]) == {-1, 2}


def test_reflexive_disequality():
    b = B()
    a = b.c("a")
    fa = b.app("f", a)
    v1, v2 = b.atom(a, a), b.atom(fa, fa)
    assert conflict_of(b.th, [-v1]) == {v1}
    b2 = B()
    a = b2.c("a")
    fa = b2.app("f", a)
    v = b2.atom(fa, fa, positive=False)
    assert conflict_of(b2.th, [v]) == {-v}
    assert v2


def test_values_are_distinct():
    b = B()
    x = b.c("x")
    one, two = b.val(1), b.val(2)
    e1, e2 = b.atom(x, one), b.atom(x, two)
    assert conflict_of(b.th, [e1, e2]) == {-e1, -e2}


def test_value_atom_between_values():
    b = B()
    v = b.atom(b.val(1), b.val(2))
    assert conflict_of(b.th, [v]) == {-v}
    b = B()
    v = b.atom(b.val(1), b.val(1))
    assert conflict_of(b.th, [-v]) == {v}


def test_value_clash_through_congruence():
    b = B()
    a, c = b.c("a", "c")
    e1 = b.atom(b.app("f", a), b.val(1))
    e2 = b.atom(b.app("f", c), b.val(2))
    e3 = b.atom(a, c)
    assert conflict_of(b.th, [e1, e2, e3]) == {-e1, -e2, -e3}


def test_value_clash_after_unrelated_values():
    b = B()
    x, y = b.c("x", "y")
    e1, e2, e3 = b.atom(x, b.val("p")), b.atom(y, b.val("q")), b.atom(x, y)
    assert conflict_of(b.th, [e3, e1, e2]) == {-e1, -e2, -e3}


def test_equal_values_share_a_class():
    b = B()
    x, y = b.c("x", "y")
    consistent_after(b.th, [b.atom(x, b.val(1)), b.atom(y, b.val(1))])
    assert b.th.equal(x, y)


def test_values_as_arguments():
    b = B()
    f1, f2 = b.app("f", b.val(1)), b.app("f", b.val(2))
    assert not b.th.equal(f1, f2)
    consistent_after(b.th, [b.atom(f1, f2)])       # f(1) = f(2) is satisfiable


def test_at_most_one_disequality_per_conflict():
    # Two disequalities are violated at once; each conflict clause must
    # still be about one of them (a proof forest never needs two).
    b = B()
    a, c, d = b.c("a", "c", "d")
    # a = c, c = d, a != d, and d != c (a second atom over c, d)
    lits = [-b.atom(a, d), -b.atom(d, c), b.atom(a, c), b.atom(c, d)]
    r = assert_all(b.th, lits)
    assert is_conflict(r)
    negs = [l for l in r[1] if lit_is_diseq(b, -l)]
    assert len(negs) == 1


def lit_is_diseq(b, lit):
    a, c, positive = b.atoms[abs(lit)]
    return (lit > 0) != positive


# ======================================================================
# Backtracking
# ======================================================================

def test_pop_undoes_merges_and_congruences():
    b = B()
    a, c, d = b.c("a", "c", "d")
    gfa, gfc = b.app("g", b.app("f", a)), b.app("g", b.app("f", c))
    ac, cd = b.atom(a, c), b.atom(c, d)
    b.th.push_level()
    consistent_after(b.th, [ac])
    assert b.th.equal(gfa, gfc)
    b.th.push_level()
    consistent_after(b.th, [cd])
    assert b.th.equal(a, d)
    b.th.pop_level()
    assert b.th.equal(gfa, gfc) and not b.th.equal(a, d)
    b.th.pop_level()
    assert not b.th.equal(a, c) and not b.th.equal(gfa, gfc)
    assert not b.th.equal(b.app("f", a), b.app("f", c))


def test_pop_undoes_disequalities():
    b = B()
    a, c = b.c("a", "c")
    v = b.atom(a, c)
    b.th.push_level()
    consistent_after(b.th, [-v])
    b.th.pop_level()
    b.th.push_level()
    consistent_after(b.th, [v])
    assert b.th.equal(a, c)
    b.th.pop_level()


def test_pop_after_conflict_restores_consistency():
    b = B()
    a, c, d = b.c("a", "c", "d")
    ac, cd, ad = b.atom(a, c), b.atom(c, d), b.atom(a, d)
    b.th.push_level()
    consistent_after(b.th, [ac, -ad])
    b.th.push_level()
    assert is_conflict(assert_all(b.th, [cd]))
    b.th.pop_level()
    r = b.th.check()
    assert not is_conflict(r)
    assert b.th.equal(a, c) and not b.th.equal(c, d)
    b.th.push_level()
    consistent_after(b.th, [-cd])
    b.th.pop_level()
    b.th.pop_level()
    assert not b.th.equal(a, c)


def test_pop_after_value_conflict():
    b = B()
    x = b.c("x")
    e1, e2 = b.atom(x, b.val(1)), b.atom(x, b.val(2))
    b.th.push_level()
    consistent_after(b.th, [e1])
    b.th.push_level()
    assert is_conflict(assert_all(b.th, [e2]))
    b.th.pop_level()
    b.th.pop_level()
    b.th.push_level()
    consistent_after(b.th, [e2])
    b.th.pop_level()


def test_empty_levels_and_root_facts():
    b = B()
    a, c, d = b.c("a", "c", "d")
    ac, cd, ad = b.atom(a, c), b.atom(c, d), b.atom(a, d)
    consistent_after(b.th, [ac])                    # root: permanent
    for _ in range(3):
        b.th.push_level()
    b.th.push_level()
    consistent_after(b.th, [cd])
    b.th.pop_level()
    for _ in range(3):
        b.th.pop_level()
    assert b.th.equal(a, c) and not b.th.equal(a, d)
    b.th.push_level()
    r = assert_all(b.th, [cd, -ad])
    assert is_conflict(r) and set(r[1]) == {-ac, -cd, ad}
    b.th.pop_level()


def test_repeated_merge_undo_cycles():
    b = B()
    a, c, d = b.c("a", "c", "d")
    fs = [b.app("f", t) for t in (a, c, d)]
    ac, cd = b.atom(a, c), b.atom(c, d)
    for _ in range(5):
        b.th.push_level()
        consistent_after(b.th, [ac, cd])
        assert b.th.equal(fs[0], fs[2])
        b.th.pop_level()
        assert not b.th.equal(a, c) and not b.th.equal(fs[0], fs[1])


def test_check_does_not_change_state():
    b = B()
    a, c = b.c("a", "c")
    v = b.atom(a, c)
    b.th.push_level()
    b.th.assert_lit(v)
    r1 = b.th.check()
    r2 = b.th.check()
    assert r1[0] is True and r2[0] is True
    b.th.pop_level()
    assert not b.th.equal(a, c)
    r = b.th.check()
    assert r is None or r[0] is True


def test_same_merge_twice_on_different_levels():
    # a = c asserted via two different atoms at two levels; popping the
    # inner one keeps the outer equality.
    b = B()
    a, c = b.c("a", "c")
    v1, v2 = b.atom(a, c), b.atom(c, a)
    b.th.push_level()
    b.th.assert_lit(v1)
    b.th.push_level()
    b.th.assert_lit(v2)
    b.th.pop_level()
    assert b.th.equal(a, c)
    assert set(b.th.explain(a, c)) == {v1}
    b.th.pop_level()
    assert not b.th.equal(a, c)


# ======================================================================
# check() model
# ======================================================================

def test_check_model_is_a_congruence_model():
    b = B()
    a, c, d, x = b.c("a", "c", "d", "x")
    fa, fc, gad = b.app("f", a), b.app("f", c), b.app("g", a, d)
    lits = [b.atom(a, c), -b.atom(c, d), b.atom(fa, x)]
    r = consistent_after(b.th, lits)
    assert r[0] is True
    model = r[1]
    for t in (a, c, d, x, fa, fc, gad):
        assert t in model
    assert model[a] == model[c] and model[fa] == model[fc] == model[x]
    assert model[c] != model[d]


# ======================================================================
# explain()
# ======================================================================

def test_explain_basic():
    b = B()
    a, c, d, x, y = b.c("a", "c", "d", "x", "y")
    ac, cd, xy = b.atom(a, c), b.atom(c, d), b.atom(x, y)
    consistent_after(b.th, [ac, xy, cd])
    assert set(b.th.explain(a, d)) == {ac, cd}
    assert set(b.th.explain(d, a)) == {ac, cd}
    assert list(b.th.explain(a, a)) == []
    assert set(b.th.explain(x, y)) == {xy}


def test_explain_congruence_edge():
    b = B()
    a, c, x, y = b.c("a", "c", "x", "y")
    e = [b.atom(a, c), b.atom(b.app("f", a), x), b.atom(b.app("f", c), y)]
    consistent_after(b.th, e)
    assert set(b.th.explain(x, y)) == set(e)


def test_explain_shortcut_is_used():
    # Chain of 10 plus a shortcut.  Asserted shortcut first, a proof forest
    # explains with the shortcut alone; either way the explanation must be
    # one of the two irredundant proofs, never a mix.
    b = B()
    v = [b.c(f"n{i}") for i in range(11)]
    shortcut = b.atom(v[0], v[10])
    chain = [b.atom(v[i], v[i + 1]) for i in range(10)]
    consistent_after(b.th, [shortcut] + chain)
    ex = set(b.th.explain(v[0], v[10]))
    assert ex in ({shortcut}, set(chain))


def test_explain_diamonds_stay_linear():
    n = 8
    b = B()
    v = [b.c(f"dm{i}") for i in range(3 * n + 1)]
    lits = []
    for i in range(n):
        lo, hi = v[3 * i], v[3 * i + 3]
        lits += [b.atom(lo, v[3 * i + 1]), b.atom(v[3 * i + 1], hi),
                 b.atom(lo, v[3 * i + 2]), b.atom(v[3 * i + 2], hi)]
    consistent_after(b.th, lits)
    assert len(set(b.th.explain(v[0], v[3 * n]))) == 2 * n


def test_explain_after_pop_uses_live_literals_only():
    b = B()
    v = [b.c(f"p{i}") for i in range(7)]
    base = [b.atom(v[i], v[i + 1]) for i in range(4)]
    extra = [b.atom(v[4], v[5]), b.atom(v[0], v[5])]
    late = b.atom(v[4], v[6])
    consistent_after(b.th, base)
    b.th.push_level()
    consistent_after(b.th, extra)
    assert b.th.explain(v[0], v[5])
    b.th.pop_level()
    b.th.push_level()
    consistent_after(b.th, [late])
    ex = set(b.th.explain(v[0], v[6]))
    assert ex <= set(base) | {late} and late in ex
    b.th.pop_level()


def test_explain_function_side_head_equal_not_needed():
    # Heads are never terms here, so an explanation contains only literals
    # about argument/term equalities.
    b = B()
    a, x, y = b.c("a", "x", "y")
    e = [b.atom(b.app("f", a), x), b.atom(b.app("f", a), y)]
    consistent_after(b.th, e)
    assert set(b.th.explain(x, y)) == set(e)


# ======================================================================
# propagate() (optional; skipped when absent)
# ======================================================================

needs_propagate = pytest.mark.skipif(not hasattr(EUFTheory, "propagate"),
                                     reason="EUFTheory has no propagate()")


def _check_reason(b, lit, reason, true_lits):
    assert lit in reason
    for l in reason:
        if l != lit:
            assert -l in true_lits, (lit, reason, true_lits)


@needs_propagate
def test_propagate_congruence_equality():
    b = B()
    a, c = b.c("a", "c")
    ac = b.atom(a, c)
    ff = b.atom(b.app("f", a), b.app("f", c))
    b.th.push_level()
    b.th.assert_lit(ac)
    out = list(b.th.propagate())
    for lit, reason in out:
        _check_reason(b, lit, reason, {ac})
    implied = {l for l, _ in out}
    assert -ff not in implied
    b.th.pop_level()
    assert all(l != ff for l, _ in b.th.propagate())


@needs_propagate
def test_propagate_never_implies_the_wrong_polarity():
    b = B()
    a, c, d = b.c("a", "c", "d")
    ac = b.atom(a, c)
    cd = b.atom(c, d)
    ad = b.atom(a, d, positive=False)
    b.th.push_level()
    b.th.assert_lit(ac)
    b.th.assert_lit(cd)
    for lit, reason in b.th.propagate():
        _check_reason(b, lit, reason, {ac, cd})
        assert lit != ad
    b.th.pop_level()


# ======================================================================
# Through the solver (theory_harness)
# ======================================================================

def solver_case(terms, atoms, clauses):
    """A TheoryCase over a fresh theory; the solver registers the atoms."""
    th = EUFTheory()
    ids = build(terms, [], th)[1]
    rec = Recorder(th)
    payloads = {k + 1: EqAtom(ids[i], ids[j], p) for k, (i, j, p) in enumerate(atoms)}
    case = TheoryCase(rec, payloads, clauses)
    return case, rec, oracle_for_harness(terms, atoms)


ABC = [("c", "a"), ("c", "b"), ("c", "c"), ("c", "d"),
       ("a", "f", (0,)), ("a", "f", (1,)), ("a", "g", (0, 1))]


def test_solver_transitivity_unsat():
    atoms = [(0, 1, True), (1, 2, True), (0, 2, True)]
    case, rec, cons = solver_case(ABC, atoms, [[1], [2], [-3]])
    assert check_solve(case, cons) is False
    check_protocol(rec)


def test_solver_congruence_unsat_and_sat():
    atoms = [(0, 1, True), (4, 5, True), (4, 6, True)]
    case, rec, cons = solver_case(ABC, atoms, [[1], [-2]])
    assert check_solve(case, cons) is False
    case, rec, cons = solver_case(ABC, atoms, [[1], [-3]])
    assert check_solve(case, cons) is True
    check_protocol(rec)


def test_solver_picks_consistent_disjunct():
    atoms = [(0, 1, True), (0, 2, True), (2, 3, True)]
    case, rec, cons = solver_case(ABC, atoms, [[1, 2], [-1], [3]])
    assert check_solve(case, cons) is True
    assert case.solver.model()[2] is True
    check_protocol(rec)


def test_solver_entails_equality_and_disequality():
    atoms = [(0, 1, True), (1, 2, True), (0, 2, True), (4, 5, True), (0, 3, True)]
    case, rec, cons = solver_case(ABC, atoms, [])
    assert check_entails(case, cons, 3, [1, 2]) is True
    assert check_entails(case, cons, 2, [1, -3]) is False
    assert check_entails(case, cons, 4, [1]) is True
    assert check_entails(case, cons, 1, [4]) is None      # not injective
    assert check_entails(case, cons, 5, [1]) is None
    assert check_entails(case, cons, -3, [-2, 1]) is True
    check_implied(case, cons, [1, 2])
    check_protocol(rec)


def test_solver_reflexive_atom_is_valid():
    atoms = [(0, 0, True), (4, 4, False)]
    case, rec, cons = solver_case(ABC, atoms, [])
    assert check_entails(case, cons, 1) is True
    assert check_entails(case, cons, -2) is True
    check_protocol(rec)


def test_solver_values():
    terms = [("c", "x"), ("v", 1), ("v", 2), ("c", "y")]
    atoms = [(0, 1, True), (0, 2, True), (0, 3, True), (3, 1, True)]
    case, rec, cons = solver_case(terms, atoms, [])
    assert check_entails(case, cons, -2, [1]) is True
    assert check_entails(case, cons, 4, [1, 3]) is True
    assert check_entails(case, cons, -3, [1, 2]) == "inconsistent"
    check_protocol(rec)


def test_solver_repeated_queries_reuse_learnt_theory_clauses():
    atoms = [(0, 1, True), (1, 2, True), (0, 2, True), (4, 5, True)]
    case, rec, cons = solver_case(ABC, atoms, [[1, 2], [3, 4]])
    for _ in range(3):
        for lit in (1, -1, 2, -2, 3, -3, 4, -4):
            check_entails(case, cons, lit)
        check_solve(case, cons)
    check_protocol(rec)
