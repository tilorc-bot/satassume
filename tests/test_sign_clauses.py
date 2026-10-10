"""The sign theory's clauses, checked directly (issue #149, T1 stage 1).

Soundness of :class:`SignTheory` rests on every clause it returns (each
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
(``tests/test_sign_theory.py`` checks those against SymPy).
"""
from __future__ import annotations

import os
import random
from itertools import product

import pytest

from satassume.theories.sign.sign import (ADD, ALL, FIN, INF, MUL, NANB, PRED_MASK, F,
                                          SignTheory, mop)

SEEDS = int(os.environ.get("SIGN_CLAUSE_SEEDS", "1500"))

_PREDS = list(PRED_MASK)


def _rand_mask(rng: random.Random) -> int:
    """A basis predicate, or a derived-style set over two or three of
    them (``sign_adapter.def_mask``: '&' or '|' of signed literals)."""
    if rng.random() < 0.5:
        return rng.choice(_PREDS)
    k = rng.randint(2, 3)
    parts = [m if rng.random() < 0.6 else ALL & ~m for m in rng.sample(_PREDS, k)]
    r = ALL if rng.random() < 0.5 else 0
    for m in parts:
        r = r & m if r == ALL or rng.random() < 0.5 and r != 0 else r | m
    return r & ALL


_CONSTS = (1 << F(1, 0), 1 << F(-1, 0), 1 << F(0, 0), 1 << F(0, 1), 1 << F(1, 1),
           1 << 9, 1 << 10, 1 << 11, (1 << F(1, 0)) | (1 << F(-1, 0)), FIN, INF)


def _value_set(op, atoms):
    """The atoms the node may take for arguments in the single ``atoms``:
    the intersection, over every bracketing of every order of the
    arguments, of the folded set.  The tables over-approximate each step,
    so each bracketing holds the true value and so does the intersection
    (the theory folds prefixes and suffixes in its own bracketings)."""
    key = (op, tuple(sorted(atoms)))
    r = _VALUE_SETS.get(key)
    if r is None:
        r = _VALUE_SETS[key] = _bracketings(op, key[1])
    return r


_VALUE_SETS: dict = {}


def _bracketings(op, atoms):
    n = len(atoms)
    memo = {}

    def rec(sub):
        r = memo.get(sub)
        if r is None:
            idx = [k for k in range(n) if sub >> k & 1]
            if len(idx) == 1:
                r = 1 << atoms[idx[0]]
            else:
                r = ALL | NANB
                part = (sub - 1) & sub
                while part:
                    if part < sub ^ part:       # each split once
                        r &= mop(op, rec(part), rec(sub ^ part))
                    part = (part - 1) & sub
            memo[sub] = r
        return r

    return rec((1 << n) - 1)


def _models(op, slots, fixed, nterms):
    """Every atom tuple (one atom per term) at which the node is defined:
    each atom in its term's fixed set, the arguments' value set
    (:func:`_value_set`) without NAN and holding the node's atom."""
    node, args = slots[0], slots[1:]
    free = [u for u in range(nterms) if u != node]
    out = []
    for atoms in product(*[[a for a in range(12) if fixed[u] >> a & 1] for u in free]):
        val = dict(zip(free, atoms))
        acc = _value_set(op, [val[u] for u in args])
        if acc & NANB:
            continue
        for a in range(12):
            if acc >> a & 1 and fixed[node] >> a & 1:
                full = dict(val)
                full[node] = a
                out.append(tuple(full[u] for u in range(nterms)))
    return out


def _satisfied(clause, model, atom):
    for l in clause:
        t, m = atom[abs(l)]
        if (model[t] in _bits(m)) == (l > 0):
            return True
    return False


def _bits(m):
    return {a for a in range(12) if m >> a & 1}


def _restore_ok(th):
    for t in range(len(th.cur)):
        m = th.fixed[t]
        for v, pm in th.tvars[t]:
            if v in th.val:
                m &= pm if th.val[v] else ~pm
        if th.cur[t] != m:
            return False
    return True


def _one(seed):
    rng = random.Random(seed)
    op = rng.choice((ADD, MUL))
    n = rng.randint(2, 4) if rng.random() < 0.3 else rng.randint(2, 3)
    th = SignTheory()
    nterms = n + 1
    fixed = []
    for u in range(nterms):
        f = ALL
        if u and rng.random() < 0.2:
            f = rng.choice(_CONSTS)
        fixed.append(f)
        th.term(f)
    args = list(range(1, nterms))
    if n >= 3 and rng.random() < 0.2:
        # a term in two slots (``x*x``): one atom for both
        args[-1] = args[0]
    th.add_node(op, 0, args)
    slots = [0] + args
    v = 0
    for u in range(nterms):
        for _ in range(rng.randint(1, 4)):
            v += 1
            th.register_atom(v, (u, _rand_mask(rng)))
    used = sorted(set(slots))
    models = _models(op, slots, fixed, nterms)
    kinds = {"prop": 0, "conflict": 0}

    def check(clause, kind):
        kinds[kind] += 1
        assert clause, "empty clause"
        for mdl in models:
            if not _satisfied(clause, mdl, th.atom):
                raise AssertionError(f"seed {seed}: clause {clause} false at {mdl} "
                                     f"(atoms {th.atom}, fixed {fixed}, op {op}, args {args})")

    nvars = v
    for level in range(rng.randint(1, 4)):
        th.push_level()
        for _ in range(rng.randint(1, 4)):
            x = rng.randint(1, nvars)
            if x in th.val:
                continue
            th.assert_lit(x if rng.random() < 0.5 else -x)
        conflict = False
        for _ in range(4):
            got = th.propagate()
            if not got:
                break
            for lit, clause in got:
                assert lit in clause
                if abs(lit) not in th.val:
                    check(clause, "prop")
                    th.assert_lit(lit)
                else:
                    # a conflict: the clause's literals are all false
                    check(clause, "conflict")
                    conflict = True
            if conflict:
                break
        if not conflict:
            r = th.check()
            if r is not None:
                check(r[1], "conflict")
                conflict = True
        assert _restore_ok(th)
        if conflict:
            break
    while th.lim:
        th.pop_level()
        assert _restore_ok(th), f"seed {seed}: pop_level left {th.cur}"
    assert not th.val and all(th.cur[t] == th.fixed[t] for t in used)
    return kinds


def test_clauses_hold_at_every_atom_tuple():
    total = {"prop": 0, "conflict": 0}
    for s in range(SEEDS):
        for k, c in _one(s).items():
            total[k] += c
    # the generator does reach both kinds of clause
    assert total["prop"] > SEEDS // 4 and total["conflict"] > SEEDS // 20, total


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
    assert th.cur[1] == ALL and not th.val
