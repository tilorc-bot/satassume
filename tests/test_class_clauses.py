"""The class theories' clauses, checked directly (issue #149: SIGN, T1, and
CLOSURE, T3; both are :class:`.lattice.ClassTheory` over a lattice).

Soundness of each theory rests on every clause it returns (each
propagation's reason, each conflict clause, the clause of ``check``)
being valid: true at every point of the terms' values.  This test builds
one small node (2 to 4 arguments, ``ADD`` or ``MUL``, sometimes with a
term in two slots, sometimes with constants: a ``fixed`` atom set), gives
each term random atom-set literals (the six basis predicates and
derived-style unions and intersections of them), asserts random literals
over a few decision levels (and the literals the theory implies, as the
solver would) and checks every returned clause against every tuple of
atoms of the terms: one atom per term inside its ``fixed`` set, the
arguments' atoms folding (:func:`mop`, in every bracketing) to a set
without ``NAN`` (a node that may be ``nan`` is "no claim") that holds the
node's atom.  Each such
tuple must satisfy the clause.  The test also checks that ``pop_level``
restores each term's set to its ``fixed`` set narrowed by the literals
still asserted.  No SymPy: the theory's own tables define the semantics
(``tests/test_sign_theory.py`` and ``tests/test_closure_theory.py``
check those against SymPy).  Between levels it also pops and re-pushes
(interleaved), as the solver's backjumps do, and checks the restore and
the clauses of the levels pushed again.

TRANS (T6) is checked the same way over its *map* operations (one unary
table per function, the binary ``Pow`` table; argument order matters, and
``x**x`` puts a term in both slots): the node's set is the table entry of
the argument atoms.  Its *one-sided* atoms (``prime``, ``composite``,
``even``, ``extended_negative``: true puts the term in a set, false says
nothing) are registered and asserted too; a clause must hold for every
value of them their meaning allows (false always, true only inside the
set), so a one-sided literal in a clause counts as false, and its negation
as true only outside the set.  The theory must never propagate one.
"""
from __future__ import annotations

import os
import random
from itertools import product

import pytest

from satassume.theories.sign import closure as C
from satassume.theories.sign import trans as T
from satassume.theories.sign.sign import (ADD, FIN, INF, MUL, PRED_MASK, F, SIGN,
                                          SignTheory)

SEEDS = int(os.environ.get("SIGN_CLAUSE_SEEDS", "1500"))


class _Lat:
    """One lattice under test: its theory, predicates and constants; the
    ops of its nodes (``(op, arity)``, arity None for a fold of 2 to 4
    arguments) and its one-sided atom sets."""

    def __init__(self, name, theory, L, preds, consts, ops=None, onesided=()):
        self.name, self.theory, self.L = name, theory, L
        self.preds = list(preds)
        self.consts = consts
        self.n = L.natoms
        self.ALL, self.NANB = L.ALL, L.NANB
        self.value_sets = {}
        self.ops = ops or [(ADD, None), (MUL, None)]
        self.onesided = tuple(onesided)

    def __repr__(self):
        return self.name


def _bs(*atoms):
    return sum(1 << a for a in atoms)


SIGN_L = _Lat("sign", SignTheory, SIGN, PRED_MASK,
              (1 << F(1, 0), 1 << F(-1, 0), 1 << F(0, 0), 1 << F(0, 1), 1 << F(1, 1),
               1 << 9, 1 << 10, 1 << 11, (1 << F(1, 0)) | (1 << F(-1, 0)), FIN, INF))
CLOSURE_L = _Lat("closure", C.ClosureTheory, C.CLOSURE, C.PRED_MASK,
                 tuple(1 << a for a in (C.Z0, C.Z1, C.Q1, C.AR, C.AC, C.TR, C.TC, C.IR, C.IC))
                 + (_bs(C.Z0, C.Z1), _bs(C.AR, C.TR), _bs(*C.CPX), C.INF))
TRANS_L = _Lat("trans", T.TransTheory, T.TRANS, T.PRED_MASK,
               tuple(1 << a for a in (T.Z0, T.ONE, T.ZI, T.Q1, T.AR, T.AC, T.TR, T.TC, T.IR,
                                      T.IC))
               + (_bs(T.Z0, T.ONE, T.ZI), _bs(T.AR, T.TR), _bs(*T.CPX)),
               ops=[(op, 1) for op in T.OPS.values()] + [(T.POW, 2)] * 6,
               onesided=T.ONESIDED_MASK)
LATTICES = (SIGN_L, CLOSURE_L, TRANS_L)


def _rand_mask(lat, rng: random.Random) -> int:
    """A basis predicate, or a derived-style set over two or three of
    them (``sign_adapter.def_mask``: '&' or '|' of signed literals)."""
    ALL = lat.ALL
    if rng.random() < 0.5:
        return rng.choice(lat.preds)
    k = rng.randint(2, 3)
    parts = [m if rng.random() < 0.6 else ALL & ~m for m in rng.sample(lat.preds, k)]
    r = ALL if rng.random() < 0.5 else 0
    for m in parts:
        r = r & m if r == ALL or rng.random() < 0.5 and r != 0 else r | m
    return r & ALL


def _value_set(lat, op, atoms):
    """The atoms the node may take for arguments in the single ``atoms``:
    the intersection, over every bracketing of every order of the
    arguments, of the folded set.  The tables over-approximate each step,
    so each bracketing holds the true value and so does the intersection
    (the theory folds prefixes and suffixes in its own bracketings).  For
    a map op, the table entry of the atoms in their order."""
    L = lat.L
    if op >= L.nfold:
        return L.maps[op - L.nfold][1][tuple(atoms)]
    key = (op, tuple(sorted(atoms)))
    r = lat.value_sets.get(key)
    if r is None:
        r = lat.value_sets[key] = _bracketings(lat, op, key[1])
    return r


def _bracketings(lat, op, atoms):
    n = len(atoms)
    memo = {}

    def rec(sub):
        r = memo.get(sub)
        if r is None:
            idx = [k for k in range(n) if sub >> k & 1]
            if len(idx) == 1:
                r = 1 << atoms[idx[0]]
            else:
                r = lat.ALL | lat.NANB
                part = (sub - 1) & sub
                while part:
                    if part < sub ^ part:       # each split once
                        r &= lat.L.mop(op, rec(part), rec(sub ^ part))
                    part = (part - 1) & sub
            memo[sub] = r
        return r

    return rec((1 << n) - 1)


def _models(lat, op, slots, fixed, nterms):
    """Every atom tuple (one atom per term) at which the node is defined:
    each atom in its term's fixed set, the arguments' value set
    (:func:`_value_set`) without NAN and holding the node's atom."""
    node, args = slots[0], slots[1:]
    free = [u for u in range(nterms) if u != node]
    out = []
    for atoms in product(*[[a for a in range(lat.n) if fixed[u] >> a & 1] for u in free]):
        val = dict(zip(free, atoms))
        acc = _value_set(lat, op, [val[u] for u in args])
        if acc & lat.NANB:
            continue
        for a in range(lat.n):
            if acc >> a & 1 and fixed[node] >> a & 1:
                full = dict(val)
                full[node] = a
                out.append(tuple(full[u] for u in range(nterms)))
    return out


def _satisfied(clause, model, atom, oneside=frozenset()):
    for l in clause:
        t, m = atom[abs(l)]
        if abs(l) in oneside:
            # the worst value the atom may take: false for ``v``, true
            # (where its set allows it) for ``-v``
            if l < 0 and not m >> model[t] & 1:
                return True
            continue
        if (m >> model[t] & 1) == (l > 0):
            return True
    return False


def _restore_ok(th):
    for t in range(len(th.cur)):
        m = th.fixed[t]
        for v, pm in th.tvars[t]:
            if v in th.val:
                m &= pm if th.val[v] else ~pm
        for v, pm in getattr(th, "ovars", [()] * len(th.cur))[t]:
            if th.val.get(v):
                m &= pm
        if th.cur[t] != m:
            return False
    return True


def _one(lat, seed):
    rng = random.Random(seed)
    op, arity = rng.choice(lat.ops)
    if arity is None:
        n = rng.randint(2, 4) if rng.random() < 0.3 else rng.randint(2, 3)
    else:
        n = arity
    th = lat.theory()
    nterms = n + 1
    fixed = []
    for u in range(nterms):
        f = lat.ALL
        if u and rng.random() < 0.2:
            f = rng.choice(lat.consts)
        fixed.append(f)
        th.term(f)
    args = list(range(1, nterms))
    if (n >= 3 or arity == 2) and rng.random() < 0.2:
        # a term in two slots (``x*x``, ``x**x``): one atom for both
        args[-1] = args[0]
    th.add_node(op, 0, args)
    slots = [0] + args
    v = 0
    oneside = set()
    for u in range(nterms):
        for _ in range(rng.randint(1, 4)):
            v += 1
            if lat.onesided and rng.random() < 0.3:
                th.register_atom(v, (u, rng.choice(lat.onesided), True))
                oneside.add(v)
            else:
                th.register_atom(v, (u, _rand_mask(lat, rng)))
    used = sorted(set(slots))
    models = _models(lat, op, slots, fixed, nterms)
    kinds = {"prop": 0, "conflict": 0, "repush": 0}

    def check(clause, kind):
        kinds[kind] += 1
        assert clause, "empty clause"
        for mdl in models:
            if not _satisfied(clause, mdl, th.atom, oneside):
                raise AssertionError(f"{lat} seed {seed}: clause {clause} false at {mdl} "
                                     f"(atoms {th.atom}, fixed {fixed}, op {op}, args {args})")

    nvars = v

    def level():
        """Push a level, assert random literals and what the theory
        implies; True iff it ended in a conflict."""
        th.push_level()
        for _ in range(rng.randint(1, 4)):
            x = rng.randint(1, nvars)
            if x in th.val:
                continue
            th.assert_lit(x if rng.random() < 0.5 else -x)
        lazy = []

        def explain():
            # the lazy reasons, explained after later literals were asserted
            # (as conflict analysis does): from the literals asserted
            # before the propagation only, all of them false
            for lit, reason, k in lazy:
                clause = reason()
                assert clause[0] == lit
                before = set(th.trail[:k])
                for l in clause[1:]:
                    assert abs(l) in before and th.val[abs(l)] == (l < 0), (lit, clause)
                check(clause, "prop")

        for _ in range(4):
            got = th.propagate()
            if not got:
                break
            conflict = False
            k = len(th.trail)
            for lit, clause in got:
                if callable(clause):
                    if abs(lit) not in th.val:
                        lazy.append((lit, clause, k))
                        th.assert_lit(lit)
                        continue
                    # (the other literal came first in this round: the
                    # solver explains this one now, as a conflict)
                    clause = clause()
                assert lit in clause
                if abs(lit) not in th.val:
                    assert abs(lit) not in oneside, "a one-sided atom was propagated"
                    check(clause, "prop")
                    th.assert_lit(lit)
                else:
                    # a conflict: the clause's literals are all false
                    check(clause, "conflict")
                    conflict = True
            if conflict:
                explain()
                return True
        explain()
        r = th.check()
        if r is not None:
            check(r[1], "conflict")
            return True
        return False

    for _ in range(rng.randint(1, 6)):
        conflict = level()
        assert _restore_ok(th)
        if conflict or rng.random() < 0.3:
            # backjump: pop one or more levels, then go on pushing
            for _ in range(rng.randint(1, len(th.lim))):
                th.pop_level()
                assert _restore_ok(th), f"{lat} seed {seed}: pop_level left {th.cur}"
            kinds["repush"] += 1
    while th.lim:
        th.pop_level()
        assert _restore_ok(th), f"{lat} seed {seed}: pop_level left {th.cur}"
    assert not th.val and all(th.cur[t] == th.fixed[t] for t in used)
    return kinds


@pytest.mark.parametrize("lat", LATTICES, ids=repr)
def test_clauses_hold_at_every_atom_tuple(lat):
    total = {"prop": 0, "conflict": 0, "repush": 0}
    for s in range(SEEDS):
        for k, c in _one(lat, s).items():
            total[k] += c
    # the generator does reach both kinds of clause, and backjumps
    assert total["prop"] > SEEDS // 4 and total["conflict"] > SEEDS // 20, total
    assert total["repush"] > SEEDS // 4, total


def test_restore_after_partial_pop():
    # pop one of two levels: the set is fixed narrowed by level 1's literal
    th = SignTheory()
    for _ in range(3):
        th.term()
    th.add_node(MUL, 0, (1, 2))
    th.register_atom(1, (1, PRED_MASK[1]))      # finite(a)
    th.register_atom(2, (1, PRED_MASK[3]))      # extended_positive(a)
    th.push_level()
    th.assert_lit(1)
    th.push_level()
    th.assert_lit(-2)
    assert th.cur[1] == FIN & ~PRED_MASK[3]
    th.pop_level()
    assert th.cur[1] == FIN and _restore_ok(th)
    th.pop_level()
    assert th.cur[1] == SIGN.ALL and not th.val


def test_one_sided_atoms():
    """``prime(b)`` puts ``b`` in ``ZI`` (Gelfond-Schneider's ``b not in
    {0, 1}``); ``~prime(b)`` says nothing; neither is ever propagated, and
    a partial pop restores the set."""
    PM = dict(zip(T.PREDS, T.PRED_MASK))
    th = T.TransTheory()
    for _ in range(3):
        th.term()
    th.add_node(T.POW, 0, (1, 2))                        # N = b**e
    th.register_atom(1, (1, PM["algebraic"]))            # algebraic(b)
    th.register_atom(2, (1, T.ONESIDED_MASK[0], True))   # prime(b)
    th.register_atom(3, (2, PM["algebraic"]))            # algebraic(e)
    th.register_atom(4, (2, PM["rational"]))             # rational(e)
    th.register_atom(5, (0, PM["algebraic"]))            # algebraic(N)
    th.push_level()
    for l in (1, 3, -4):
        th.assert_lit(l)
    got = dict(th.propagate())
    assert 5 not in got and -5 not in got                # b may be 0 or 1
    th.push_level()
    th.assert_lit(-2)                                    # ~prime(b): no claim
    assert th.cur[1] == PM["algebraic"] and not th.propagate()
    th.pop_level()
    th.push_level()
    th.assert_lit(2)
    assert th.cur[1] == 1 << T.ZI
    # a propagated literal's reason may be lazy: explain it (as conflict
    # analysis does) before reading it
    got = {l: r() if callable(r) else r for l, r in th.propagate()}
    assert sorted(got[-5]) == sorted([-5, -1, -2, -3, 4]) or set(got[-5]) <= {-5, -2, -3, 4}
    assert all(abs(l) != 2 for l in got)
    th.pop_level()
    assert th.cur[1] == PM["algebraic"] and _restore_ok(th)
    th.pop_level()
    assert th.cur[1] == T.ALL and not th.val
