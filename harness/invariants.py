"""Invariant checkers I1-I7 (see ``harness/INVARIANTS.md``).

Every checker takes one query ``ask(p, A)`` from a generated stream, builds
one or more *variants* of it (the solver with a seeded subset of its
clauses dropped, an unrelated conjunct added, a stronger set, the negated
proposition, a restated set, renamed symbols, a setting changed after
history) and compares the answers of fresh engines under the exact
statement of the invariant.  Nothing here is heuristic: a pair of answers
is reported only if the invariant as stated forbids it, the assumption set
is known consistent (a model found by the engine's own solver with full
escalation and search, ``Engine.verdict``, or a concrete
assignment from a grid, ``harness.models.find_model``: ``consistent_by``),
and neither answer is an inconsistency report (``ValueError``: allowed
whatever the history).  The engine's documented scope is a tag on a case
(``scope``), never a reason to skip the oracle.

Severity classes (``SEVERITY``, most important first):

``wrong``     two definite answers differ, or (I1) None became definite
``depends``   definite against None across an invariant that says "same"
``lost``      lost definiteness where the invariant demands a definite value
``crash``     an engine error (not ``ValueError``) on one side only

Each violation is shrunk (``ddmin`` over the conjuncts of the set, and
over the added conjuncts) to a replayable case, written as ``NAME.json``
and ``NAME.py`` like ``harness/repros``.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import random
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from sympy import (Abs, Basic, Dummy, E, Eq, Float, Function, Ge, GoldenRatio, Gt, I, Le, Lt, Mod,
                   Ne, Q, Rational, Symbol, ceiling, conjugate, cos, exp, floor, im, log, pi, re,
                   sign, sin, sqrt, S)
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational
from sympy.matrices.expressions import MatrixExpr
from sympy.logic.boolalg import And, BooleanAtom, Equivalent, Implies, Not, Or

import satassume.sympy_api as _api
from satassume.engine import CONSISTENT
from satassume.rules import PREDICATES
from satassume.solver import Solver

from .checker import Ask, Event, Item, ddmin
from .outcomes import outcome
from .state import REMOVED_SETTINGS, EngineConfig
from .sympy_io import custom_predicate, from_srepr, to_srepr

INVARIANTS = ("I1", "I2", "I3", "I4", "I5", "I6", "I7")
SEVERITY = ("wrong", "depends", "lost", "crash")

DEFINITE = ("True", "False")


def _definite(o: str) -> bool:
    return o in DEFINITE


def _error(o: str) -> bool:
    return o.startswith("Error:") or o.startswith("Value:")


def negate(p):
    """The logical negation of ``p``.  SymPy's ``Not(rel)`` *rewrites* a
    ``Relational`` (``Not(x >= a)`` becomes ``x < a``), which is not the
    negation when ``x`` can be non-real: the negation is built with
    ``evaluate=False`` (``Not(Not(q))`` is ``q``; a Boolean atom flips)."""
    if isinstance(p, Not):
        return p.args[0]
    if isinstance(p, BooleanAtom):
        return Not(p)
    return Not(p, evaluate=False)


# --------------------------------------------------------------------------
# I1: a test-time solver patch dropping a seeded subset of the clauses
# --------------------------------------------------------------------------

def _drop(lits: Sequence[int], seed: int, rate: float) -> bool:
    """Deterministic per clause content and seed (ints hash the same under
    every PYTHONHASHSEED): the same clause is dropped or kept every time
    it is added within one run."""
    h = hash((seed, tuple(lits))) & 0xFFFFFF
    return h < int(rate * 0x1000000)


@contextlib.contextmanager
def dropping_clauses(seed: int, rate: float, stats: Optional[dict] = None, blocks: bool = False):
    """While active, every ``Solver.add_clause`` / ``add_clauses`` /
    ``add_internal`` drops the clauses ``_drop`` selects (an engine change
    is not needed: the engine only ever sees a subset of the clauses it
    meant to add); ``add_pattern`` (compiled blocks) is filtered the same
    way.  Not covered: the lazily loaded rule blocks (``mention_blocks``),
    which are propagated without clauses."""
    orig_add, orig_bulk, orig_int = Solver.add_clause, Solver.add_clauses, Solver.add_internal
    orig_pat, orig_reg = Solver.add_pattern, Solver.register_block
    n = {"dropped": 0, "kept": 0, "blocks": 0}

    def register_block(self, base, mentions=0):
        # ``blocks``: the lazily loaded rule block instantiated as clauses
        # (``set_rule_block``: the solver then "behaves as if
        # add_pattern(block, base, nvars) had been called"), minus the
        # dropped ones; the reference of such a check is the same patch at
        # rate 0 (eager blocks, nothing dropped), see ``check_I1``
        n["blocks"] += 1
        return add_pattern(self, self._rb_clauses, base, self._rb_n)

    def add_clause(self, lits):
        lits = list(lits)
        if _drop(lits, seed, rate):
            n["dropped"] += 1
            return self._ok
        n["kept"] += 1
        return orig_add(self, lits)

    def add_clauses(self, clauses):
        kept = []
        for c in clauses:
            c = list(c)
            if _drop(c, seed, rate):
                n["dropped"] += 1
            else:
                n["kept"] += 1
                kept.append(c)
        return orig_bulk(self, kept)

    def add_internal(self, clauses, mentions=None):
        # the template patterns' path (internal literals); ``mentions`` is
        # left as it is: mentioning a variable only loads lazy rule blocks
        kept = []
        for c in clauses:
            if _drop(c, seed, rate):
                n["dropped"] += 1
            else:
                n["kept"] += 1
                kept.append(c)
        return orig_int(self, kept, mentions)

    def add_pattern(self, pattern, base, nvars):
        # a compiled block relative to variable 0, shifted to ``base``:
        # decided on the shifted literals (a subset of a unit-free,
        # tautology-free pattern is one too)
        lo = 2 * base
        kept = []
        for c in pattern:
            if _drop([l + lo for l in c], seed, rate):
                n["dropped"] += 1
            else:
                n["kept"] += 1
                kept.append(c)
        return orig_pat(self, kept, base, nvars)

    Solver.add_clause, Solver.add_clauses, Solver.add_internal = add_clause, add_clauses, add_internal
    Solver.add_pattern = add_pattern
    if blocks:
        Solver.register_block = register_block
    try:
        yield n
    finally:
        Solver.add_clause, Solver.add_clauses, Solver.add_internal = orig_add, orig_bulk, orig_int
        Solver.add_pattern, Solver.register_block = orig_pat, orig_reg
        if stats is not None:
            stats.update(n)


# --------------------------------------------------------------------------
# consistency guard
# --------------------------------------------------------------------------

#: disagreements between the two paths of the guard (the engine finds no
#: model, a concrete assignment satisfies the set): logged, never reported
GUARD_DISAGREEMENTS: List[dict] = []


def consistent_by(assum, config: EngineConfig) -> Optional[str]:
    """Which path finds a model of ``assum``: ``"engine"`` (the engine's
    own solver, full escalation and search), else ``"model"`` (a concrete
    assignment of the symbols from a small grid, respecting their declared
    assumptions, under the conservative evaluator of ``harness.models``),
    else None (undecided: a candidate under such a set is not reported).
    The engine's "no model" is also what it says of a set it cannot read,
    so a model found after it is logged (``GUARD_DISAGREEMENTS``), never
    reported.  The engine path runs with ``uninterpreted="none"`` whatever
    the configuration: under the default ``"free"`` an unread atom is a
    free Boolean, so a satisfying assignment of the opaque abstraction is
    not a model of the set (``x > 7 & x < 2.5`` with a Float side)."""
    if assum is True or assum is S.true:
        return "engine"
    eng = config.replace(uninterpreted="none").make()
    try:
        # the set's complete check (Engine.verdict: whole cone, propagation,
        # search); only CONSISTENT is a model (UNKNOWN: a theory gave up or
        # the cone was truncated)
        g = _api._formula(assum, bool(eng.relation_specs), True)
        if g is _api.TRUE or g is not _api.FALSE and eng.verdict(g) == CONSISTENT:
            return "engine"
    except Exception:  # noqa: BLE001
        pass
    from .models import find_model
    try:
        m = find_model(assum)
    except Exception:  # noqa: BLE001
        m = None
    if m is None:
        return None
    GUARD_DISAGREEMENTS.append({"assum": to_srepr(assum), "model": {str(k): str(v) for k, v in m.items()}})
    return "model"


def consistent(assum, config: EngineConfig) -> bool:
    """The engine's own solver or a concrete model (``consistent_by``)
    finds a model of ``assum``.  False when neither can decide: a
    candidate violation under such a set is not reported."""
    return consistent_by(assum, config) is not None


#: whether the latest ``fresh_outcome`` was a budget-limited None (its
#: engine's ``last_budget_limited`` set after the ask); read by the runner
#: and ``evaluate`` right after each side's ask (``budget_exempt``)
LAST_BUDGET_LIMITED = [False]

#: invariants a pair is exempt from when a side's answer is a budget-limited
#: None: above the discovery budget the answer is None by design (issue
#: #72), and an unsplit set with unrelated material (I2), a stronger set
#: (I3) or a restatement (I5) may weigh more than the base.  Not I4 (p and
#: Not(p) have the same cone) and not soundness (I1).  INVARIANTS.md.
BUDGET_EXEMPT = ("I2", "I3", "I5")


def fresh_outcome(prop, assum, config: EngineConfig) -> str:
    eng = config.make()
    LAST_BUDGET_LIMITED[0] = False
    o = outcome(prop, assum, eng)
    LAST_BUDGET_LIMITED[0] = o == "None" and bool(getattr(eng, "last_budget_limited", False))
    return o


def budget_exempt(inv: str, base_limited: bool, other_limited: bool) -> bool:
    """The pair is exempt from ``inv`` (``BUDGET_EXEMPT``): a side's answer
    is a budget-limited None."""
    return inv in BUDGET_EXEMPT and (base_limited or other_limited)


# --------------------------------------------------------------------------
# unrelated conjuncts (I2), satisfiable by construction
# --------------------------------------------------------------------------

#: predicates any single value can satisfy (``commutative`` is declared on
#: every plain symbol, so its negation would be inconsistent)
VALUE_PREDS = [p for p in PREDICATES if p not in ("commutative", "polar")]
_DECLARED = {
    "positive": ["integer", "rational", "irrational", "prime", "composite", "even", "odd",
                 "algebraic", "transcendental", "noninteger"],
    "integer": ["positive", "negative", "zero", "even", "odd", "prime", "composite", "nonzero"],
    "real": ["positive", "negative", "zero", "integer", "irrational", "rational", "nonzero"],
}
from .models import CONSTANTS, REAL_CLASSES, const_class   # noqa: E402  (the classified pool)
#: finite constants of every class (inside terms; ``nonreal`` included,
#: ``unsettled`` and the extra Floats at a low weight: the first entries
#: are the plain ones the blocks use)
_FINITE_CONSTS = [S.Zero, S.One, S(2), S(-3), S.Half, pi, sqrt(2), S(7),
                  Float(2.5), Rational(-2, 3), E, S(10) ** 12, I, GoldenRatio] + \
                 [c for k in ("algebraic", "transcendental", "float", "unsettled", "nonreal") for c in CONSTANTS[k]]
_FINITE_CONSTS = list(dict.fromkeys(_FINITE_CONSTS))
#: real constants only: a relation to ``I`` is unsatisfiable
_REAL_CONSTS = [c for c in _FINITE_CONSTS if const_class(c) in REAL_CLASSES]
#: infinities a fresh symbol may equal or be bounded by (each satisfiable)
_INF_RELS = [lambda u: Q.eq(u, S.Infinity), lambda u: Q.eq(u, S.NegativeInfinity),
             lambda u: Q.eq(u, S.ComplexInfinity), lambda u: Q.ne(u, S.Infinity),
             lambda u: Q.ne(u, S.ComplexInfinity), lambda u: Q.lt(u, S.Infinity),
             lambda u: Q.gt(u, S.NegativeInfinity), lambda u: Q.le(u, S.Infinity),
             lambda u: Q.ge(u, S.NegativeInfinity), lambda u: Lt(u, S.Infinity),
             lambda u: Gt(u, S.NegativeInfinity), lambda u: Q.infinite(u) & Q.extended_real(u)]
_UNARY = [Abs, floor, ceiling, log, sin, cos, conjugate, re, im, sign, lambda t: Mod(t, 3)]


class Unrelated:
    """Conjuncts over fresh symbols and fresh undefined functions, each
    piece satisfiable on its own and sharing nothing with the others or
    with the query: their conjunction is satisfiable, and ``A & B`` is
    consistent exactly when ``A`` is.  Each piece is a predicate on a term
    ``u + T(v, ...)`` (``u`` appears nowhere else: the term takes every
    value), on a product or odd power of fresh symbols, on ``h(u)`` with a
    fresh ``h``, a relation between two such terms with different bases,
    or a fact on a declared fresh symbol consistent with its declaration."""

    def __init__(self, rng: random.Random, tag: str, mode: str = "any"):
        """``mode``: ``any``; ``norel``, no relation anywhere in the
        material (predicates, closed predicate facts, commutativity,
        declared facts, extensions: a definite answer lost to these is
        not the relation family); ``rel``, relations only."""
        self.rng, self.tag, self.k, self.mode = rng, tag, 0, mode

    def sym(self, **kw):
        self.k += 1
        if not kw and self.rng.random() < 0.1:
            return Dummy(f"{self.tag}d{self.k}")
        return Symbol(f"{self.tag}u{self.k}", **kw)

    def func(self):
        self.k += 1
        return Function(f"{self.tag}h{self.k}")

    def _inner(self, depth: int):
        t = self._inner_raw(depth)
        if getattr(t, "has", None) and t.has(S.ComplexInfinity, S.Infinity, S.NegativeInfinity, S.NaN):
            return self.sym()
        return t

    def _inner_raw(self, depth: int):
        r = self.rng
        if depth <= 0 or r.random() < 0.4:
            return self.sym() if r.random() < 0.7 else r.choice(_FINITE_CONSTS)
        c = r.random()
        if c < 0.3:
            return self._inner(depth - 1) + self._inner(depth - 1)
        if c < 0.55:
            return self._inner(depth - 1) * self._inner(depth - 1)
        if c < 0.7:
            b = self._inner(depth - 1)
            return b ** r.choice([2, 3, -1, S.Half]) if b != 0 else b + 1
        if c < 0.85:
            if r.random() < 0.25:
                return self.func()(self._inner(depth - 1), self._inner(depth - 1))   # a binary application
            return self.func()(self._inner(depth - 1))
        if c < 0.93:
            return r.choice([exp, sqrt])(self._inner(depth - 1))
        if c < 0.96:
            return r.choice([S(2), S(-3), Rational(1, 3), Float(0.5)]) * self._inner(depth - 1)   # a scaled term (linear glue)
        return r.choice(_UNARY)(self._inner(depth - 1))

    def free_term(self, depth: int):
        """A term whose value is unconstrained: a fresh symbol plus anything.
        SymPy may fold a sub-term into an infinity (``u + zoo`` is ``zoo``),
        which would make a predicate on it unsatisfiable: such a term is
        replaced by the fresh symbol alone."""
        r = self.rng
        c = r.random()
        if c < 0.3:
            return self.sym()
        if c < 0.36:
            # a linear combination with a fresh leading symbol: every value
            return self.sym() + r.choice([S(2), S(-3), Rational(1, 3)]) * self.sym() + r.choice([S.Zero, S.One, S(-2)])
        if c < 0.55:
            return self.func()(self._inner(depth))
        if c < 0.7:
            return self.sym() * self.sym()
        if c < 0.8:
            # odd powers only: u**3 takes every value (including -oo);
            # u**2 or sqrt(u) cannot be negative, so a predicate on them
            # could be unsatisfiable
            return self.sym() ** r.choice([3, 5])
        u = self.sym()
        t = u + self._inner(depth)
        if u not in getattr(t, "free_symbols", ()) or t.has(S.ComplexInfinity, S.Infinity, S.NegativeInfinity, S.NaN):
            return u
        return t

    def piece(self, depth: int = 2):
        """A satisfiable conjunct over fresh symbols: an atom (``atom``),
        or ``Or``/``Implies``/``Equivalent`` of two atoms over disjoint
        symbols (satisfiable: the consequent's model plus any value for the
        rest), or ``Q.is_true`` around one; at ``OOS_RATE`` (``any`` mode)
        a piece the engine documents as out of scope (``out_of_scope``: a
        matrix atom, ``Q.is_true`` over a non-relation, an unregistered
        predicate), which the invariant does not exempt."""
        r = self.rng
        c = r.random()
        if self.mode == "any" and r.random() < OOS_RATE:
            return self.out_of_scope()
        if c < 0.12 and depth > 0:
            a, b = self.piece(depth - 1), self.piece(depth - 1)
            return r.choice([Or, Implies, Equivalent])(a, b)
        if c < 0.24:
            # ``Q.is_true`` over a relational only: over anything else it is
            # documented as out of scope (``sympy_api``: category "custom")
            a = self.atom(depth)
            if isinstance(a, Relational):
                return Q.is_true(a)
            if isinstance(a, AppliedPredicate) and a.function in _SWAP:
                return Q.is_true({v: k for k, v in _QREL.items()}[a.function](*a.arguments, evaluate=False))
            return a
        return self.atom(depth)

    def closed(self):
        """A true fact about closed terms (SymPy's own assumptions decide
        it): a predicate on a constant, or a relation between constants."""
        r = self.rng
        for _ in range(8):
            c = r.random()
            if self.mode == "norel":
                c = 0.0
            elif self.mode == "rel":
                c = 1.0
            if c < 0.5:
                t = r.choice(_FINITE_CONSTS)
                if r.random() < 0.4:
                    t = r.choice([exp, sqrt, Abs, floor, sin, log])(t)
                name = r.choice(VALUE_PREDS)
                val = getattr(t, "is_" + name, None)
                if val is None or t.has(S.NaN, S.ComplexInfinity, S.Infinity, S.NegativeInfinity):
                    continue
                atom = getattr(Q, name)(t)
                return atom if val else Not(atom)
            a, b = r.choice(_REAL_CONSTS), r.choice(_REAL_CONSTS)
            cls = r.choice([Lt, Le, Gt, Ge, Eq, Ne])
            try:
                val = cls(a, b)
            except TypeError:
                continue
            if val not in (S.true, S.false):
                continue
            atom = _QREL[cls](a, b) if r.random() < 0.6 else Q.is_true(cls(a, b, evaluate=False))
            return atom if val == S.true else Not(atom)
        return Q.positive(S.One)

    def atom(self, depth: int = 2):
        r = self.rng
        c = r.random()
        if self.mode == "norel":
            c = r.choice([0.2, 0.2, 0.7, 0.86, 0.95])     # predicate, closed predicate, commutativity, declared
        elif self.mode == "rel":
            c = r.choice([0.5, 0.5, 0.7, 0.8])            # relation, closed relation, infinity relation
        if c < 0.45:
            atom = getattr(Q, r.choice(VALUE_PREDS))(self.free_term(depth))
            return Not(atom) if r.random() < 0.25 else atom
        if c < 0.68:
            a, b = self.free_term(depth), self.free_term(depth) if r.random() < 0.7 else r.choice(_REAL_CONSTS)
            rel = r.choice([Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne, Lt, Le, Gt, Ge, Eq, Ne])
            if a == b:
                return Q.eq(a, b)
            return rel(a, b)
        if c < 0.76:
            return self.closed()
        if c < 0.84:
            return r.choice(_INF_RELS[:-1] if self.mode != "norel" else _INF_RELS[-1:])(self.sym())
        if c < 0.88:
            # commutativity is declared: a plain symbol is commutative, a
            # symbol declared commutative=False is not
            if r.random() < 0.5:
                return Q.commutative(self.sym())
            return Not(Q.commutative(self.sym(commutative=False)))
        kind = r.choice(list(_DECLARED))
        s = self.sym(**{kind: True})
        return getattr(Q, r.choice(_DECLARED[kind]))(s)

    def conjunction(self, n: int, depth: int = 2):
        return And(*[self.piece(depth) for _ in range(n)])

    def out_of_scope(self):
        """Material the engine documents as out of scope (``sympy_api.
        out_of_scope``): a matrix atom, ``Q.is_true`` over a non-relation,
        an unregistered custom predicate on a fresh symbol.  Each is
        satisfiable over fresh symbols, so ``A & B`` is consistent iff ``A``
        is; the invariant does not exempt them (a scope tag is recorded in
        the case, the oracle is the same)."""
        r = self.rng
        c = r.random()
        if c < 0.34:
            from sympy import MatrixSymbol
            self.k += 1
            M = MatrixSymbol(f"{self.tag}M{self.k}", 2, 2)
            return r.choice([Q.symmetric, Q.invertible, Q.square])(M)
        if c < 0.67:
            u = self.sym()
            inner = r.choice([Or(Q.positive(u), Q.negative(u)), Q.real(u), Not(Q.zero(u), evaluate=False)])
            return Q.is_true(inner)
        self.k += 1
        return custom_predicate(f"{self.tag}oos{self.k}", 1)(self.sym())

    def block(self, shared_consts: Sequence[Any] = ()) -> Optional[List[Any]]:
        """An unrelated *subsystem*: 2-4 conjuncts over 2-3 fresh symbols
        that share symbols among themselves (sign atoms on sums sharing a
        symbol, order chains, equalities, disequalities, integrality), the
        symbols optionally declared, the constants optionally from the
        query's own (``shared_consts``: symbol-disjoint, sharing a constant,
        is still unrelated).  A witness assignment is chosen first and the
        block built around it: each atom is kept in the polarity true at
        the witness, and the whole block is verified by evaluation
        (``harness.models.evaluate_at``); None when it cannot be."""
        from .models import WITNESS_POOL, evaluate_at, values_for
        r = self.rng
        n_syms = r.choice([2, 2, 3])
        syms, subs = [], {}
        for _ in range(n_syms):
            kw = {}
            c = r.random()
            if c < 0.2:
                kw = {"integer": True}
            elif c < 0.35:
                kw = {"positive": True}
            elif c < 0.5:
                kw = {"real": True}
            s = self.sym(**kw)
            if isinstance(s, Dummy):
                s = Symbol(f"{self.tag}u{self.k}", **kw)
            vals = values_for(s, WITNESS_POOL)
            if not vals:
                return None
            syms.append(s)
            subs[s] = r.choice(vals)
        consts = list(_FINITE_CONSTS[:6]) + [c for c in shared_consts if getattr(c, "is_extended_real", None) and getattr(c, "is_finite", None)]

        def term():
            a, b = r.sample(syms, 2)
            c = r.random()
            if c < 0.3:
                return a + b
            if c < 0.45:
                return a + r.choice(consts)
            if c < 0.6:
                return a - b
            if c < 0.7:
                return a * b
            if c < 0.8:
                return r.choice([S(2), S(-3), Rational(1, 2)]) * a + b
            if c < 0.9:
                return a
            return a + b + r.choice(consts)

        out = []
        for _ in range(r.choice([2, 3, 3, 4])):
            c = r.random()
            if self.mode == "norel":
                c = r.choice([0.1, 0.1, 0.9])
            elif self.mode == "rel":
                c = r.choice([0.5, 0.5, 0.8])
            if c < 0.4:
                name = r.choice(["positive", "negative", "nonnegative", "nonpositive", "zero", "nonzero", "real"])
                atom = getattr(Q, name)(term())
                val = evaluate_at(atom, subs)
                if val is None:
                    continue
                out.append(atom if val else Not(atom, evaluate=False))
            elif c < 0.8:
                a = term()
                b = term() if r.random() < 0.6 else r.choice(consts)
                if a == b:
                    continue
                rel = r.choice([Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne])
                atom = rel(a, b)
                val = evaluate_at(atom, subs)
                if val is None:
                    continue
                if not val:
                    atom = {Q.lt: Q.ge, Q.le: Q.gt, Q.gt: Q.le, Q.ge: Q.lt, Q.eq: Q.ne, Q.ne: Q.eq}[rel](a, b)
                if r.random() < 0.3:
                    atom = {v: k for k, v in _QREL.items()}[atom.function](*atom.arguments, evaluate=False)
                out.append(atom)
            else:
                name = r.choice(["integer", "even", "odd", "rational", "irrational", "noninteger"])
                atom = getattr(Q, name)(term())
                val = evaluate_at(atom, subs)
                if val is None:
                    continue
                out.append(atom if val else Not(atom, evaluate=False))
        if len(out) < 2:
            return None
        if evaluate_at(And(*out), subs) is not True:
            return None
        self.last_witness = subs
        return out

    def extension(self):
        """A registered extension with no path to the query.  Either a
        fresh predicate on a fresh symbol (or fresh ``h(u)``, or a pair of
        fresh symbols for a polyadic one), whose handler relates it to one
        vocabulary literal on that term (satisfiable on its own), returns
        ``None``/``True``, or chains to a second fresh predicate; the
        conjunct asserts the fresh predicate so that the handler runs.  Or
        a *registration only* (nothing asserted): a fresh predicate on a
        number class, an operator class, ``Symbol`` or ``Basic`` whose
        handler may also return ``False``; or a vocabulary predicate on a
        fresh function class (no application of it occurs anywhere) or a
        vocabulary predicate on ``Symbol``/``Basic`` whose handler returns
        ``None`` (no clause: no path)."""
        r = self.rng
        self.k += 1
        name = f"{self.tag}h{self.k}p"
        c = r.random()
        if c < 0.55:
            cls = r.choice(["Symbol", "Basic", "AppliedUndef", "Symbol,Symbol"])
            polyadic = "," in cls
            if polyadic:
                name += "2"          # one predicate object per name (custom_predicate caches by name): its own arity
            if polyadic:
                args = (self.sym(), self.sym())
            else:
                args = (self.func()(self.sym()) if cls == "AppliedUndef" else self.sym(),)
            spec = {"pred": name, "cls": cls,
                    "lit": r.choice(VALUE_PREDS), "neg": r.random() < 0.3,
                    "shape": r.choice(["implies", "iff", "or", "none", "true", "chain"])}
            atom = custom_predicate(name, len(args))(*args)
            return spec, atom
        if c < 0.85:
            cls = r.choice(["Integer", "Rational", "Float", "NumberSymbol", "Add", "Mul", "Pow",
                            "Symbol", "Basic", "AppliedUndef", "Symbol,Symbol"])
            if "," in cls:
                name += "2"
            spec = {"pred": name, "cls": cls, "lit": r.choice(VALUE_PREDS), "neg": r.random() < 0.3,
                    "shape": r.choice(["implies", "iff", "or", "none", "true", "false", "chain"])}
            return spec, None
        if c < 0.95:
            self.k += 1
            spec = {"pred": r.choice(VALUE_PREDS), "cls": f"Function:{self.tag}h{self.k}",
                    "lit": r.choice(VALUE_PREDS), "neg": r.random() < 0.3,
                    "shape": r.choice(["implies", "iff", "none", "true", "false"])}
            return spec, None
        spec = {"pred": r.choice(VALUE_PREDS), "cls": r.choice(["Symbol", "Basic"]),
                "lit": "positive", "neg": False, "shape": "none"}
        return spec, None


#: exceptions raised inside the harness's own handlers (a harness defect,
#: never reported as an engine crash)
HANDLER_ERRORS: List[str] = []


def extension_handler(spec: dict):
    from satassume.formula import Implies, Not as FNot, Or as FOr, P

    def fn(*ts):
        try:
            return _handler_body(spec, ts, Implies, FNot, FOr, P)
        except Exception as e:  # noqa: BLE001
            HANDLER_ERRORS.append(f"{type(e).__name__}: {e}")
            raise
    return fn


def _handler_body(spec, ts, Implies, FNot, FOr, P):
    if True:       # (indented as the former closure body; see extension_handler)
        t = ts[0]
        if spec["shape"] == "none":
            return None                       # no knowledge
        if spec["shape"] == "true":
            return True                       # the predicate holds of t: what the conjunct asserts
        if spec["shape"] == "false":
            return False                      # never asserted: a registration only
        lit = P(spec["lit"], t)
        if spec["neg"]:
            lit = FNot(lit)
        if len(ts) > 1:
            from satassume.extensions import Args
            me = P(spec["pred"], Args(ts))            # a polyadic atom's expr is its argument tuple
        else:
            me = P(spec["pred"], t)
        if spec["shape"] == "chain":
            return Implies(me, P(spec["pred"] + "q", t))     # to a second fresh predicate (unregistered)
        if spec["shape"] == "implies":
            return Implies(me, lit)
        if spec["shape"] == "iff":
            return [Implies(me, lit), Implies(lit, me)]
        return FOr(FNot(me), lit)


def _classes(cls: str) -> tuple:
    from sympy import Add, Basic, Float, Integer, Mul, NumberSymbol, Pow, Rational
    table = {"Symbol": Symbol, "Basic": Basic, "AppliedUndef": AppliedUndef, "Integer": Integer,
             "Rational": Rational, "Float": Float, "NumberSymbol": NumberSymbol, "Add": Add,
             "Mul": Mul, "Pow": Pow}
    out = []
    for name in cls.split(","):
        if name.startswith("Function:"):
            out.append(Function(name[len("Function:"):]))
        else:
            out.append(table[name])
    return tuple(out)


@contextlib.contextmanager
def registered(specs: Sequence[dict]):
    """The extensions of ``specs`` registered while active (the registry
    is restored afterwards, as ``harness.registry`` does)."""
    from .registry import restore, snapshot
    from satassume.extensions import extensions
    snap = snapshot()
    try:
        for spec in specs:
            extensions.register(spec["pred"], *_classes(spec["cls"]))(extension_handler(spec))
        yield
    finally:
        restore(snap)


# --------------------------------------------------------------------------
# I5: equivalent restatements; I6: renaming
# --------------------------------------------------------------------------

_SWAP = {Q.lt: Q.gt, Q.gt: Q.lt, Q.le: Q.ge, Q.ge: Q.le, Q.eq: Q.eq, Q.ne: Q.ne}
_RSWAP = {Lt: Gt, Gt: Lt, Le: Ge, Ge: Le, Eq: Eq, Ne: Ne}
_QREL = {Lt: Q.lt, Gt: Q.gt, Le: Q.le, Ge: Q.ge, Eq: Q.eq, Ne: Q.ne}


def _scalar(e) -> bool:
    return getattr(e, "is_commutative", False) is True and not isinstance(e, MatrixExpr)


def syntax_form(cs: Sequence[Any], rng: random.Random):
    """The conjunction of ``cs`` spelled differently: reordered, with a
    duplicate, nested (``And`` built with ``evaluate=False`` so that SymPy
    keeps the spelling; the models are the same)."""
    parts = list(cs)
    rng.shuffle(parts)
    if not parts:
        return True
    if rng.random() < 0.4:
        parts.append(rng.choice(parts))
    for _ in range(rng.choice([0, 1, 1, 2])):
        if len(parts) < 2:
            break
        i = rng.randrange(len(parts) - 1)
        j = rng.randrange(i + 2, len(parts) + 1)
        parts[i:j] = [And(*parts[i:j], evaluate=False)]
    if len(parts) == 1 and isinstance(parts[0], And):
        return parts[0]
    return And(*parts, evaluate=False) if len(parts) > 1 else parts[0]


#: a predicate as a union or intersection of others, true of exactly the
#: same values (SymPy's assumption facts: real is negative, zero or positive;
#: nonzero is real and not zero; integer is even or odd; ...)
_SPLIT = {
    Q.real: lambda x: Or(Q.negative(x), Q.zero(x), Q.positive(x)),
    Q.nonnegative: lambda x: Or(Q.zero(x), Q.positive(x)),
    Q.nonpositive: lambda x: Or(Q.zero(x), Q.negative(x)),
    Q.nonzero: lambda x: Or(Q.positive(x), Q.negative(x)),
    Q.positive: lambda x: And(Q.nonnegative(x), Q.nonzero(x)),
    Q.negative: lambda x: And(Q.nonpositive(x), Q.nonzero(x)),
    Q.zero: lambda x: And(Q.nonnegative(x), Q.nonpositive(x)),
    Q.integer: lambda x: Or(Q.even(x), Q.odd(x)),
    Q.odd: lambda x: And(Q.integer(x), Not(Q.even(x), evaluate=False)),
    Q.even: lambda x: And(Q.integer(x), Not(Q.odd(x), evaluate=False)),
    Q.rational: lambda x: And(Q.real(x), Not(Q.irrational(x), evaluate=False)),
    Q.irrational: lambda x: And(Q.real(x), Not(Q.rational(x), evaluate=False)),
}
#: predicates a predicate implies (adding one is an equivalent restatement)
_IMPLIED = {
    Q.positive: ["real", "nonzero", "nonnegative", "extended_positive", "finite", "complex"],
    Q.negative: ["real", "nonzero", "nonpositive", "extended_negative", "finite"],
    Q.zero: ["real", "even", "integer", "finite", "nonnegative", "nonpositive"],
    Q.even: ["integer", "rational", "real"],
    Q.odd: ["integer", "real", "nonzero"],
    Q.prime: ["integer", "positive", "nonzero"],
    Q.composite: ["integer", "positive"],
    Q.irrational: ["real", "nonzero"],
    Q.rational: ["real", "algebraic"],
    Q.integer: ["rational", "real", "algebraic"],
    Q.real: ["complex", "hermitian", "finite", "extended_real"],
    Q.imaginary: ["complex", "antihermitian", "finite"],
    Q.nonzero: ["real"],
    Q.transcendental: ["complex", "finite"],
}
#: the same predicate on a transformed term with the same truth for every
#: scalar value: x is positive exactly when -x is negative or 2*x is positive
_TERM_FORMS = {
    Q.positive: [lambda x: 2 * x, lambda x: x / 3],
    Q.negative: [lambda x: 2 * x, lambda x: x / 3],
    Q.zero: [lambda x: -x, lambda x: 3 * x, lambda x: x / 2],
    Q.nonzero: [lambda x: -x, lambda x: 2 * x],
    Q.real: [lambda x: -x, lambda x: 2 * x, lambda x: x + 1],
    Q.integer: [lambda x: -x, lambda x: x + 1, lambda x: x - 3],
    Q.even: [lambda x: -x, lambda x: x + 2],
    Q.odd: [lambda x: -x, lambda x: x + 2],
    Q.rational: [lambda x: -x, lambda x: 2 * x, lambda x: x + 1],
    Q.irrational: [lambda x: -x, lambda x: x + 1],
    Q.finite: [lambda x: -x, lambda x: 2 * x],
    Q.infinite: [lambda x: -x, lambda x: 2 * x],
    Q.complex: [lambda x: -x, lambda x: x + 1],
    Q.imaginary: [lambda x: -x, lambda x: 2 * x],
}
_SIGN_FLIP = {Q.positive: Q.negative, Q.negative: Q.positive}


def _shift_relation(b, rng: random.Random):
    """``rel(a, b)`` as ``rel(a + c, b + c)`` or ``rel(-b, -a)`` (the same
    relation on the negated, swapped sides: ``a < b`` is ``-b < -a``), the
    same truth for every value of scalar sides (in the extended reals
    ``oo + c`` is ``oo``; non-real sides make every order relation false
    and equality is unchanged)."""
    a, c = b.arguments
    if not (_scalar(a) and _scalar(c)):
        return None
    if a.has(S.NaN) or c.has(S.NaN):
        return None
    f = b.function
    r = rng.random()
    if r < 0.3:
        k = rng.choice([S.One, S(-2), Rational(1, 2)])
        return f(a + k, c + k)
    if r < 0.5:
        # shifted by a term of the relation itself: ``a < c`` is ``0 < c - a``
        # (finite terms; an infinite side would give ``oo - oo``)
        if a.is_finite and c.is_finite:
            return f(S.Zero, c - a) if rng.random() < 0.5 else f(a - c, S.Zero)
        return f(-c, -a)
    if r < 0.75:
        # scaled by a positive constant (the order is unchanged; non-real
        # sides stay non-real, equality is unchanged)
        k = rng.choice([S(2), S(3), Rational(1, 2)])
        return f(k * a, k * c)
    return f(-c, -a)


#: equivalences that hold only given a declared fact of the argument
#: (``assumptions0`` of a ``Symbol``; never an ``ask``), each proved by hand
#: for the declared class: ``real`` in SymPy is finite real, ``integer``
#: is a finite real integer.  ``pred -> (fact, rewrite)``; the rewrite is
#: the equivalent statement under ``fact``.  Covered by the value-level
#: self-check in ``tests/test_invariants.py`` at declared sample values.
_GIVEN = {
    # x real (finite): the order relation to 0 is the sign predicate
    Q.positive: [("real", lambda x: Q.gt(x, S.Zero)), ("real", lambda x: Not(Q.nonpositive(x), evaluate=False)),
                 ("integer", lambda x: Q.ge(x, S.One))],
    Q.negative: [("real", lambda x: Q.lt(x, S.Zero)), ("real", lambda x: Not(Q.nonnegative(x), evaluate=False)),
                 ("integer", lambda x: Q.le(x, S.NegativeOne))],
    Q.nonnegative: [("real", lambda x: Q.ge(x, S.Zero)), ("real", lambda x: Not(Q.negative(x), evaluate=False)),
                    ("integer", lambda x: Q.gt(x, S.NegativeOne))],
    Q.nonpositive: [("real", lambda x: Q.le(x, S.Zero)), ("real", lambda x: Not(Q.positive(x), evaluate=False))],
    Q.nonzero: [("real", lambda x: Q.ne(x, S.Zero)), ("real", lambda x: Not(Q.zero(x), evaluate=False))],
    Q.zero: [("real", lambda x: Not(Q.nonzero(x), evaluate=False)), ("integer", lambda x: Q.even(x) & Q.lt(x, S.One) & Q.gt(x, S.NegativeOne))],
    Q.irrational: [("real", lambda x: Not(Q.rational(x), evaluate=False))],
    Q.rational: [("real", lambda x: Not(Q.irrational(x), evaluate=False))],
    Q.even: [("integer", lambda x: Not(Q.odd(x), evaluate=False))],
    Q.odd: [("integer", lambda x: Not(Q.even(x), evaluate=False))],
    Q.integer: [("real", lambda x: Not(Q.noninteger(x), evaluate=False))],
    Q.noninteger: [("real", lambda x: Not(Q.integer(x), evaluate=False))],
    Q.extended_real: [("finite", lambda x: Q.real(x))],
    Q.extended_positive: [("finite", lambda x: Q.positive(x))],
    Q.extended_negative: [("finite", lambda x: Q.negative(x))],
    Q.extended_nonzero: [("finite", lambda x: Q.nonzero(x))],
    Q.extended_nonnegative: [("finite", lambda x: Q.nonnegative(x))],
    Q.extended_nonpositive: [("finite", lambda x: Q.nonpositive(x))],
    Q.real: [("finite", lambda x: Q.extended_real(x)), ("extended_real", lambda x: Q.finite(x))],
    Q.finite: [("extended_real", lambda x: Q.real(x))],
}


def restate_given(b, rng: random.Random):
    """``b`` restated by an equivalence of ``_GIVEN`` whose fact the
    argument's *declaration* guarantees (``Symbol.assumptions0``); None
    when none applies.  Relations: ``~lt(x, y)`` is ``ge(x, y)`` when
    both sides are declared real (finite reals are totally ordered)."""
    if isinstance(b, Not) and isinstance(b.args[0], AppliedPredicate) and b.args[0].function in (Q.lt, Q.le, Q.gt, Q.ge):
        inner = b.args[0]
        x, y = inner.arguments
        if all(isinstance(t, Symbol) and t.assumptions0.get("real") for t in (x, y)):
            comp = {Q.lt: Q.ge, Q.le: Q.gt, Q.gt: Q.le, Q.ge: Q.lt}
            return comp[inner.function](x, y)
        return None
    if not isinstance(b, AppliedPredicate) or len(b.arguments) != 1:
        return None
    x = b.arguments[0]
    if not isinstance(x, Symbol):
        return None
    opts = [(fact, rw) for fact, rw in _GIVEN.get(b.function, ()) if x.assumptions0.get(fact)]
    if not opts:
        return None
    fact, rw = rng.choice(opts)
    return rw(x)


#: when a list, ``restate`` appends the name of each atom rule it applies
#: (``rewrite_of``'s names; the test compares the two)
_RESTATE_TRACE: Optional[list] = None


def _traced(rule, value):
    if _RESTATE_TRACE is not None:
        _RESTATE_TRACE.append(rule() if callable(rule) else rule)
    return value


def restate(b, rng: random.Random, p: float = 0.5):
    """An equivalent restatement of the Boolean ``b``: swapped relation
    sides (``lt(a, b)`` -> ``gt(b, a)``), the three spellings of a
    relation, ``Implies`` as ``Or``, ``Equivalent`` as two ``Implies``,
    ``Q.is_true`` around an atom, reordered ``And``/``Or`` arguments (SymPy
    re-sorts them, so this checks the engine's own ordering)."""
    if rng.random() < p * 0.5:
        g = restate_given(b, rng)                 # an equivalence under a declared fact
        if g is not None:
            return _traced("given", g)
    if isinstance(b, AppliedPredicate):
        f = b.function
        if f in _SWAP and rng.random() < p * 0.8:
            r = _shift_relation(b, rng)         # first: shifted, scaled, one-sided (the rewrites)
            if r is not None:
                return _traced("shift-relation", r)
        if f in _SWAP and rng.random() < p * 0.6:
            a, c = b.arguments
            return _traced("swap", _SWAP[f](c, a))
        if f in _SWAP and rng.random() < p:
            try:
                return _traced("relational", {v: k for k, v in _QREL.items()}[f](*b.arguments))
            except Exception:  # noqa: BLE001
                return b
        if f == Q.zero and _scalar(b.arguments[0]) and rng.random() < p:
            return _traced("zero-eq", Q.eq(b.arguments[0], S.Zero))             # zero(x) is x = 0 for every scalar value
        if f == Q.eq and b.arguments[1] == S.Zero and _scalar(b.arguments[0]) and rng.random() < p:
            return _traced("eq-zero", Q.zero(b.arguments[0]))
        if f in _SWAP and rng.random() < p * 1.6:
            r = _shift_relation(b, rng)
            if r is not None:
                return _traced("shift-relation", r)
        if f in _SPLIT and _scalar(b.arguments[0]) and rng.random() < p * 0.6:
            return _traced("split", _SPLIT[f](*b.arguments))              # the predicate as a union / intersection of others
        if f in _IMPLIED and _scalar(b.arguments[0]) and rng.random() < p * 0.5:
            return _traced("implied", And(b, getattr(Q, rng.choice(_IMPLIED[f]))(*b.arguments)))   # a conjunct it implies
        if f in _TERM_FORMS and _scalar(b.arguments[0]) and rng.random() < p * 0.5:
            if f in _SIGN_FLIP and rng.random() < 0.4:
                return _traced("sign-flip", _SIGN_FLIP[f](-b.arguments[0]))
            g = rng.choice(_TERM_FORMS[f])
            return _traced(lambda: "term-form:" + _form_tag(g), f(g(b.arguments[0])))
        if rng.random() < p * 0.6:
            return _traced("is_true", Q.is_true(b))
        return b
    if rng.random() < p * 0.15:
        return _traced("double-not", Not(Not(b, evaluate=False), evaluate=False))   # a double negation, unevaluated
    if isinstance(b, Relational):
        cls = type(b)
        if cls in _QREL and rng.random() < p:
            return _traced("q-relation", _QREL[cls](*b.args))
        if rng.random() < p * 0.3:
            return _traced("is_true", Q.is_true(b))
        if cls in _RSWAP and rng.random() < p:
            try:
                return _traced("swap", _RSWAP[cls](b.rhs, b.lhs))
            except Exception:  # noqa: BLE001
                return b
        return b
    if isinstance(b, Not):
        inner = b.args[0]
        if isinstance(inner, AppliedPredicate) and inner.function in (Q.eq, Q.ne) and rng.random() < p:
            # ne is the complement of eq for every value (unlike lt/ge)
            f = Q.ne if inner.function == Q.eq else Q.eq
            return _traced("ne-eq", f(*inner.arguments))
        if isinstance(inner, (And, Or)) and rng.random() < p:
            # De Morgan
            other = Or if isinstance(inner, And) else And
            return other(*[negate(restate(x, rng, p)) for x in inner.args])
        return negate(restate(inner, rng, p))
    if isinstance(b, Implies):
        a, c = b.args
        a, c = restate(a, rng, p), restate(c, rng, p)
        r = rng.random()
        if r < p / 2:
            return Or(negate(a), c)
        if r < p:
            return Implies(negate(c), negate(a))          # contrapositive
        return Implies(a, c)
    if isinstance(b, Equivalent) and len(b.args) == 2:
        a, c = (restate(x, rng, p) for x in b.args)
        r = rng.random()
        if r < p / 2:
            return And(Implies(a, c), Implies(c, a))
        if r < p:
            return Or(And(a, c), And(negate(a), negate(c)))
        return Equivalent(a, c)
    if isinstance(b, (And, Or)):
        args = [restate(x, rng, p) for x in b.args]
        rng.shuffle(args)
        if isinstance(b, And) and rng.random() < p:
            args = args + [rng.choice(args)]          # a duplicate (SymPy merges it)
        return type(b)(*args)
    return b


def rename(exprs: Sequence[Any], rng: random.Random, tag: str = "r"):
    """The same expressions over fresh symbols and functions with the same
    declared assumptions (``assumptions0``); names drawn so that their sort
    order differs from the originals'."""
    syms, funcs = set(), set()
    for e in exprs:
        if hasattr(e, "free_symbols"):
            # plain symbols and Dummies only: a MatrixSymbol is out of scope
            # and must stay one
            syms |= {s for s in e.free_symbols if type(s) in (Symbol, Dummy)}
            funcs |= {a.func for a in e.atoms(AppliedUndef)}
    names = list(range(len(syms) + len(funcs)))
    rng.shuffle(names)
    smap = {}
    for s in sorted(syms, key=str):
        nm = f"{rng.choice('aqz')}{tag}{names.pop()}"
        cls = Dummy if isinstance(s, Dummy) else Symbol
        smap[s] = cls(nm, **s.assumptions0)
    fmap = {f: Function(f"{rng.choice('aqz')}{tag}f{names.pop()}") for f in sorted(funcs, key=str)}
    return apply_rename(exprs, smap, fmap), smap, fmap


def _rebuild(e, smap: dict, fmap: dict):
    """``xreplace`` that keeps the spelling of ``Not``/``And``/``Or`` nodes
    (SymPy would rewrite a rebuilt ``Not(rel)`` and flatten a nested
    ``And``): the renamed expression means what the original means."""
    if e in smap:
        return smap[e]
    if not isinstance(e, Basic) or not e.args:
        return e
    args = [_rebuild(a, smap, fmap) for a in e.args]
    if isinstance(e, AppliedUndef) and e.func in fmap:
        return fmap[e.func](*args)
    if isinstance(e, Not):
        return Not(*args, evaluate=False)
    if isinstance(e, (And, Or)):
        # a canonical node (SymPy's own order) stays canonical under the new
        # names, so that an I6 report is about the names, not the order (I5);
        # a respelled one keeps its spelling
        canonical = e == type(e)(*e.args)
        return type(e)(*args) if canonical else type(e)(*args, evaluate=False)
    return e.func(*args)


def apply_rename(exprs: Sequence[Any], smap: dict, fmap: dict) -> list:
    return [_rebuild(e, smap, fmap) if isinstance(e, Basic) else e for e in exprs]


# --------------------------------------------------------------------------
# violations
# --------------------------------------------------------------------------

@dataclasses.dataclass
class Violation:
    inv: str
    severity: str
    config: EngineConfig
    prop: Any
    assum: Any
    variant: Dict[str, Any]            # what was varied (srepr / plain values)
    base: str
    other: str
    source: str = ""
    known: Optional[str] = None
    shrunk: bool = False
    prefix: List[Any] = dataclasses.field(default_factory=list)   # I7: the history
    consistent_by: Optional[str] = None     # which guard path decided ("engine" / "model")
    fingerprint: Optional[str] = None       # the probes that make the difference vanish

    def summary(self) -> str:
        k = f" known:{self.known}" if self.known else ""
        return (f"{self.inv} {self.severity}{k} [{self.config.name}] ask({self.prop}, {self.assum}) "
                f"= {self.base}; variant {self.variant.get('kind')} = {self.other}")

    def to_json(self) -> Dict[str, Any]:
        return {"inv": self.inv, "severity": self.severity, "known": self.known,
                "config": self.config.to_dict(), "prop": to_srepr(self.prop),
                "assum": to_srepr(self.assum), "variant": self.variant, "base": self.base,
                "other": self.other, "source": self.source, "shrunk": self.shrunk,
                "consistent_by": self.consistent_by, "fingerprint": self.fingerprint,
                "prefix": [{"prop": to_srepr(a.prop), "assum": to_srepr(a.assum)} for a in self.prefix]}


def scope_of(prop, assum) -> str:
    """The engine's documented scope category of the query
    (``sympy_api.out_of_scope``: ``matrix``, ``custom`` (an unregistered
    predicate or ``Q.is_true`` over a non-relational), ``other``), or
    ``"in"``.  A *tag* recorded in the case: the invariants do not exempt
    out-of-scope material (an answer changed by an unrelated conjunct the
    engine calls out of scope is an I2 violation all the same)."""
    try:
        c = _api.out_of_scope(prop, assum)
    except Exception as e:  # noqa: BLE001
        return f"error:{type(e).__name__}"
    return "in" if c in (None, "relation") else c


def in_scope(prop, assum) -> bool:
    return scope_of(prop, assum) == "in"


def _severity_same(inv: str, base: str, other: str) -> Optional[str]:
    """Class of ``base`` vs ``other`` under an invariant that says "same
    answer" (I2, I5, I6, I7); None when nothing is violated or the pair is
    inconclusive (an inconsistency report on either side)."""
    if base == other or "ValueError" in (base, other):
        return None
    if _error(base) or _error(other):
        return "crash"
    if _definite(base) and _definite(other):
        return "wrong"
    return "depends"


# --------------------------------------------------------------------------
# the checkers: each returns (severity or None, other outcome, variant dict)
# --------------------------------------------------------------------------

def check_I1(prop, assum, config, base, rng, variant=None):
    """Dropping any subset of the clauses never flips a definite answer
    and never turns None into a definite answer."""
    if variant is None:
        variant = {"kind": "drop", "seed": rng.randrange(1 << 30),
                   "rate": rng.choice([0.03, 0.1, 0.25, 0.5])}
        if rng.random() < I1_BLOCKS_RATE:
            variant["blocks"] = True
    stats: dict = {}
    blocks = bool(variant.get("blocks"))
    if blocks:
        # the rule blocks as clauses: the reference is the eager solver
        # with nothing dropped (the engine says it answers as the lazy
        # block does, or more definitely, which is not I1's statement),
        # and the check is inconclusive when that reference differs
        with dropping_clauses(variant["seed"], 0.0, blocks=True):
            ref = fresh_outcome(prop, assum, config)
        if ref != base:
            return None, ref, dict(variant, eager=ref, inconclusive="eager blocks answer differently")
    with dropping_clauses(variant["seed"], variant["rate"], stats, blocks=blocks):
        other = fresh_outcome(prop, assum, config)
    variant = dict(variant, dropped=stats.get("dropped", 0), kept=stats.get("kept", 0))
    if blocks:
        variant["blocks_as_clauses"] = stats.get("blocks", 0)
    sev = None
    if "ValueError" not in (base, other):
        if _definite(base) and _definite(other) and base != other:
            sev = "wrong"
        elif base == "None" and _definite(other):
            sev = "wrong"
        elif base == "None" and _error(other):
            sev = "crash"
    return sev, other, variant


def check_I2(prop, assum, config, base, rng, variant=None):
    """Unrelated conjuncts (fresh symbols, fresh functions) do not change
    the answer, whatever they do to the budget or the polluted switch."""
    if variant is None:
        mode = rng.choice(["any", "any", "norel", "norel", "rel"])
        u = Unrelated(random.Random(rng.randrange(1 << 30)), "iu", mode)
        n = rng.choice([1, 1, 2, 3, 5, 8, 12, 12, 20, 30])
        parts = [u.piece(depth=rng.choice([1, 2, 3])) for _ in range(n)]
        nblocks = 0
        if rng.random() < I2_BLOCK_RATE:
            # unrelated subsystems (blocks of conjuncts sharing symbols among
            # themselves), each with a verified witness; constants of the
            # query's set may recur in them (no shared variable: unrelated)
            consts = [c for c in _consts_of(assum) + _consts_of(prop)][:6]
            for _ in range(rng.choice([1, 1, 2])):
                blk = u.block(consts if rng.random() < 0.5 else ())
                if blk is not None:
                    parts.extend(blk)
                    nblocks += 1
            if nblocks and rng.random() < 0.5:
                parts = parts[n:]            # the blocks alone
        specs = []
        if rng.random() < I2_EXTENSION_RATE:
            for _ in range(rng.choice([1, 1, 2, 3])):
                spec, atom = u.extension()
                specs.append(spec)
                if atom is not None:
                    parts.append(atom)
        rng.shuffle(parts)
        variant = {"kind": "unrelated", "extra": to_srepr(And(*parts)), "mode": mode}
        if nblocks:
            variant["blocks"] = nblocks
        if specs:
            variant["extensions"] = specs
    extra = from_srepr(variant["extra"])
    new = extra if assum is True or assum is S.true else And(assum, extra)
    n_err = len(HANDLER_ERRORS)
    with registered(variant.get("extensions", [])):
        other = fresh_outcome(prop, new, config)
    if len(HANDLER_ERRORS) > n_err and _error(other):
        return None, other, variant          # the harness's handler raised: not the engine's error
    with registered(variant.get("extensions", [])):
        variant = dict(variant, scope=scope_of(prop, new))   # a tag, never a veto (INVARIANTS.md)
    return _severity_same("I2", base, other), other, variant


def check_I3(prop, assum, config, base, rng, variant=None):
    """A definite answer under A stays under A & B (B: the proposition or
    its negation as answered, or a fact declared on one of the symbols)."""
    if not _definite(base):
        return None, base, variant or {"kind": "skip"}
    if variant is None:
        opts = [{"kind": "self"}]
        syms = sorted(getattr(prop, "free_symbols", set()) | getattr(assum, "free_symbols", set()), key=str)
        for s in syms:
            for k, v in s.assumptions0.items():
                if k in PREDICATES and k != "commutative":
                    opts.append({"kind": "declared", "sym": to_srepr(s), "pred": k, "value": bool(v)})
        variant = rng.choice(opts)
    if variant["kind"] == "self":
        b = prop if base == "True" else negate(prop)
    else:
        atom = getattr(Q, variant["pred"])(from_srepr(variant["sym"]))
        b = atom if variant["value"] else Not(atom)
    new = b if assum is True or assum is S.true else And(assum, b)
    other = fresh_outcome(prop, new, config)
    sev = None
    if "ValueError" not in (base, other) and base != other:
        sev = "crash" if _error(other) else ("wrong" if _definite(other) else "lost")
    return sev, other, variant


def check_I4(prop, assum, config, base, rng, variant=None):
    """ask(p, A) is True exactly when ask(~p, A) is False; ``~p`` is the
    logical negation (``negate``: ``Not(p, evaluate=False)``), never
    SymPy's rewrite of a negated relation."""
    variant = variant or {"kind": "negation"}
    other = fresh_outcome(negate(prop), assum, config)
    sev = None
    if "ValueError" not in (base, other):
        if _error(base) or _error(other):
            sev = "crash" if base != other else None
        elif base == "True" and other != "False" or other == "False" and base != "True":
            sev = "wrong" if _definite(base) and _definite(other) else "lost"
        elif base == "False" and other != "True" or other == "True" and base != "False":
            sev = "wrong" if _definite(base) and _definite(other) else "lost"
    return sev, other, variant


def check_I5(prop, assum, config, base, rng, variant=None, prop_only: bool = False):
    """An equivalent restatement of the assumptions (or, ``prop_only`` /
    the ``prop`` kind, of the proposition) gives the same answer."""
    if (assum is True or assum is S.true) and not prop_only:
        return None, base, variant or {"kind": "skip"}
    if variant is None and not prop_only and rng.random() < I5_SYNTAX_RATE:
        variant = {"kind": "syntax", "seed": rng.randrange(1 << 30)}
    if variant is None and (prop_only or rng.random() < I5_PROP_RATE):
        # the proposition restated (the set unchanged): ``restate`` on it,
        # or padded with a tautology / contradiction over a fresh symbol
        r = random.Random(rng.randrange(1 << 30))
        q = restate_prop(prop, r)
        if q != prop:
            variant = {"kind": "prop", "prop": to_srepr(q)}
        elif prop_only:
            return None, base, {"kind": "skip"}
    if variant is None:
        cs = _conjuncts(assum)
        parts = list(cs)
        for _ in range(4):        # SymPy canonicalises most of it: retry until it differs
            r = random.Random(rng.randrange(1 << 30))
            parts = [restate(c, r) for c in cs]
            if _join(parts) != assum:
                break
        variant = {"kind": "restate", "parts": [to_srepr(x) for x in parts],
                   "assum": to_srepr(_join(parts))}
    if variant["kind"] == "syntax":
        # rebuilt from the (possibly shrunk) conjuncts: the seed fixes the spelling
        new = syntax_form(_conjuncts(assum), random.Random(variant["seed"]))
        variant = dict(variant, assum=to_srepr(new))
    elif variant["kind"] == "prop":
        new = assum
    else:
        new = from_srepr(variant["assum"])
    new_prop = from_srepr(variant["prop"]) if "prop" in variant else prop
    other = fresh_outcome(new_prop, new, config)
    variant = dict(variant, scope=scope_of(new_prop, new))    # a tag, never a veto
    return _severity_same("I5", base, other), other, variant


def check_I6(prop, assum, config, base, rng, variant=None):
    """Renaming symbols and functions to fresh names gives the same answer.
    Terms above ``RENAME_LIMIT`` characters of srepr are skipped: SymPy's
    rebuild of a renamed deep term takes tens of seconds (a budget matter,
    not an engine one)."""
    if variant is None:
        if len(to_srepr(prop)) + len(to_srepr(assum)) > RENAME_LIMIT:
            return None, base, {"kind": "skip"}
        (p2, a2), smap, fmap = rename([prop, assum], random.Random(rng.randrange(1 << 30)))
        variant = {"kind": "rename", "prop": to_srepr(p2), "assum": to_srepr(a2),
                   "symbols": [(to_srepr(k), to_srepr(x)) for k, x in smap.items()],
                   "functions": [(k.__name__, x.__name__) for k, x in fmap.items()]}
    else:
        # the maps applied to (possibly shrunk) prop and assum
        smap = {from_srepr(k): from_srepr(x) for k, x in variant.get("symbols", [])}
        fmap = {Function(k): Function(x) for k, x in variant.get("functions", [])}
        p2, a2 = apply_rename([prop, assum], smap, fmap)
        variant = dict(variant, prop=to_srepr(p2), assum=to_srepr(a2))
    if variant.get("hashseed") is None and rng.random() < I6_PROCESS_RATE:
        variant = dict(variant, hashseed=rng.choice([1, 2, 3]))
    if variant.get("hashseed") is not None:
        # the renamed query in a fresh interpreter under another PYTHONHASHSEED
        from .checker import process_outcome
        other = process_outcome(Ask(p2, a2), config, variant["hashseed"])
    else:
        other = fresh_outcome(p2, a2, config)
    return _severity_same("I6", base, other), other, variant


RENAME_LIMIT = 1500
#: share of I1 checks that instantiate the lazily loaded rule blocks as
#: clauses (``dropping_clauses(blocks=True)``) and drop among them too
I1_BLOCKS_RATE = 1.0 if os.environ.get('I1_BLOCKS_ALL') else 0.3
#: share of I2 checks that also register fresh extensions
I2_EXTENSION_RATE = 0.3
#: share of the I2 checks whose material holds an unrelated *block*
I2_BLOCK_RATE = 0.4
#: rate of out-of-scope pieces (matrix atom, ``Q.is_true`` over a
#: non-relation, unregistered predicate) in the ``any`` mode
OOS_RATE = 0.03
#: share of the I5 checks that restate the proposition instead of the set
I5_PROP_RATE = 0.3
#: share of I5 checks that respell the conjunction (order, duplicate, nesting)
#: instead of restating conjuncts
I5_SYNTAX_RATE = 0.35
#: share of I6 checks whose renamed query also runs in a fresh interpreter
#: under another PYTHONHASHSEED (a subprocess: about a second each)
I6_PROCESS_RATE = 0.04
#: share of stream queries that also get a derived query (``derived_asks``)
WIDEN_RATE = 0.35


def _terms(exprs) -> list:
    """Scalar terms the atoms of ``exprs`` are about."""
    out = []
    for e in exprs:
        if not isinstance(e, Basic):
            continue
        for a in e.atoms(AppliedPredicate):
            out.extend(x for x in a.arguments if isinstance(x, Basic) and _scalar(x))
        for r in e.atoms(Relational):
            out.extend(x for x in r.args if isinstance(x, Basic) and _scalar(x))
    return sorted(set(out), key=str)


def derived_asks(asks: Sequence[Ask], rng: random.Random, rate: float = WIDEN_RATE) -> List[Ask]:
    """Queries derived from the stream's: the proposition combined with a
    conjunct of its set (``And``, ``Or`` with the negation, ``Implies``,
    ``Equivalent``), wrapped in ``Q.is_true``, negated, a conjunct asked
    back or negated, or a relation between two terms of the query.  The
    same checkers run on them; they reach shapes the profiles do not."""
    out: List[Ask] = []
    for it in asks:
        if rng.random() >= rate:
            continue
        p, a = it.prop, it.assum
        cs = _conjuncts(a)
        opts = ["neg", "rel"]
        if cs:
            opts += ["and", "or", "implies", "equiv", "conj", "negconj"]
        if isinstance(p, (AppliedPredicate, Relational)):
            opts.append("is_true")
        kind = rng.choice(opts)
        c = rng.choice(cs) if cs else None
        try:
            if kind == "neg":
                q = negate(p)
            elif kind == "and":
                q = And(p, c)
            elif kind == "or":
                q = Or(p, negate(c))
            elif kind == "implies":
                q = Implies(c, p)
            elif kind == "equiv":
                q = Equivalent(p, c)
            elif kind == "conj":
                q = c
            elif kind == "negconj":
                q = negate(c)
            elif kind == "is_true":
                q = Q.is_true(p)
            else:
                ts = _terms([p, a])
                if len(ts) < 1:
                    continue
                t1 = rng.choice(ts)
                t2 = rng.choice(ts + [S.Zero, S.One, S(-1), S.Infinity])
                if t1 == t2:
                    continue
                q = rng.choice([Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne, Lt, Le, Ge, Eq, Ne])(t1, t2)
            if isinstance(q, BooleanAtom) or q in (True, False):
                continue
        except Exception:  # noqa: BLE001 - SymPy refused the construction
            continue
        out.append(Ask(q, a))
    return out

#: every assignable setting of ``EngineConfig`` (#97 P7 removed the no-op
#: ``cone_threshold``, ``cone_search``, ``session_limit``, ``keep_sessions``
#: and added ``uninterpreted``, a live setting the sweep had missed)
I7_SETTINGS = {
    "discovery_budget": [5, 40, 400, 5000],
    "transfer": [True, False],
    "relevance": [True, False],
    "uninterpreted": ["free", "none"],
}


def check_I7(prop, assum, config, base, rng, variant=None, prefix: Sequence[Ask] = ()):
    """After a history, changing a setting gives the answer of a fresh
    engine with that setting (``base`` is ignored: the reference is fresh
    under the new setting)."""
    if variant is None:
        name = rng.choice(list(I7_SETTINGS))
        vals = [v for v in I7_SETTINGS[name] if v != getattr(config, name)]
        variant = {"kind": "setting", "name": name, "value": rng.choice(vals)}
    # A recorded variant over a setting removed in #97 P7 (``REMOVED_SETTINGS``)
    # was a no-op when it was recorded and stays one: the variant config is the
    # config itself and the assignment is skipped, so the case still replays
    # and counts as checked (``harness/repros/invariants/fixed/I7-...``).
    removed = variant["name"] in REMOVED_SETTINGS
    changes = {} if removed else {variant["name"]: variant["value"]}
    cfg2 = config.replace(**changes, name=f"{config.name}+{variant['name']}")
    ref = fresh_outcome(prop, assum, cfg2)
    eng = config.make()
    for a in prefix:
        outcome(a.prop, a.assum, eng)
    if not removed:
        setattr(eng, variant["name"], variant["value"])
    other = outcome(prop, assum, eng)
    return _severity_same("I7", ref, other), other, dict(variant, fresh=ref)


CHECKERS: Dict[str, Callable] = {
    "I1": check_I1, "I2": check_I2, "I3": check_I3, "I4": check_I4,
    "I5": check_I5, "I6": check_I6, "I7": check_I7,
}


# --------------------------------------------------------------------------
# shrinking and replay
# --------------------------------------------------------------------------

def _consts_of(e) -> List[Any]:
    """The finite real numeric constants occurring in ``e`` (shared with
    the unrelated blocks: a constant is not a variable)."""
    if not isinstance(e, Basic):
        return []
    from sympy import Number, NumberSymbol
    out = []
    for a in e.atoms(Number, NumberSymbol):
        if a.is_finite and a.is_extended_real and a not in out and a not in (S.Zero, S.One, S.NegativeOne):
            out.append(a)
    return sorted(out, key=str)


def restate_prop(p, rng: random.Random):
    """An equivalent restatement of the proposition: ``restate`` on it, or
    the proposition padded with a tautology (``And``) or a contradiction
    (``Or``) over a fresh symbol (``w``, declared at random): the padding
    has no model-theoretic effect on ``p``."""
    if not isinstance(p, Basic) or isinstance(p, BooleanAtom):
        return p
    r = rng.random()
    if r < 0.6:
        q = restate(p, rng, p=0.7)
        if q != p:
            return q
    w = Symbol("iw", **rng.choice([{}, {"real": True}, {"integer": True}, {"positive": True}]))
    atom = getattr(Q, rng.choice(VALUE_PREDS))(w)
    if rng.random() < 0.5:
        return And(p, Or(atom, negate(atom)), evaluate=False)
    return Or(p, And(atom, negate(atom)), evaluate=False)


def _conjuncts(a) -> List[Any]:
    if a is True or a is S.true:
        return []
    return list(a.args) if isinstance(a, And) else [a]


def _join(cs: List[Any]):
    return True if not cs else (cs[0] if len(cs) == 1 else And(*cs))


def evaluate(v: Violation, prop=None, assum=None, variant=None) -> Tuple[Optional[str], str, str, dict]:
    """Replay a violation (or a candidate variant of it): severity, base
    outcome, other outcome, variant."""
    prop = v.prop if prop is None else prop
    assum = v.assum if assum is None else assum
    variant = v.variant if variant is None else variant
    rng = random.Random(0)
    if v.inv == "I7":
        sev, other, var = check_I7(prop, assum, v.config, None, rng, variant, v.prefix)
        return sev, var["fresh"], other, var
    base = fresh_outcome(prop, assum, v.config)
    base_limited = LAST_BUDGET_LIMITED[0]
    sev, other, var = CHECKERS[v.inv](prop, assum, v.config, base, rng, variant)
    if sev is not None and budget_exempt(v.inv, base_limited, LAST_BUDGET_LIMITED[0]):
        sev = None                       # a budget-limited None: by design
    return sev, base, other, var


def _equivalent_set(v: Violation, assum, var) -> Optional[Any]:
    """A set with exactly the models of ``assum`` (I5: the restatement;
    I6: the renamed set) or one whose consistency implies ``assum``'s
    (I2, I3: ``A & B``); None for the other invariants."""
    if v.inv == "I5":
        return from_srepr(var["assum"]) if "assum" in var else None   # ``prop`` kind: the set itself
    if v.inv == "I6":
        return from_srepr(var["assum"])
    if v.inv == "I2":
        return _join(_conjuncts(assum) + _conjuncts(from_srepr(var["extra"])))
    if v.inv == "I3":
        if var.get("kind") == "self":
            b = v.prop if v.base == "True" else negate(v.prop)
        elif var.get("kind") == "declared":
            atom = getattr(Q, var["pred"])(from_srepr(var["sym"]))
            b = atom if var["value"] else Not(atom)
        else:
            return None
        return _join(_conjuncts(assum) + [b])
    return None


def _guarded(v: Violation, prop, assum, variant) -> bool:
    """The candidate still violates and its set is consistent: the
    engine finds a model of ``A`` or of a set equivalent to it (the
    restated or renamed set) or one that implies it is consistent
    (``A & B``: B is over fresh symbols and satisfiable, or p / ~p as
    answered, or a declared fact).  The engine's check refuses sets it
    cannot decide (a relation no theory reads), so both are tried."""
    sev, base, other, var = evaluate(v, prop, assum, variant)
    if sev is None:
        return False
    alt = _equivalent_set(v, assum, var)
    if v.inv == "I3":
        # anything goes if A & B is inconsistent: A & B itself must have a model
        by = alt is not None and consistent_by(alt, v.config)
    else:
        by = consistent_by(assum, v.config) or (alt is not None and consistent_by(alt, v.config))
    v.consistent_by = by or None
    return bool(by)


def shrink(v: Violation, max_tests: int = 400) -> Violation:
    """ddmin over the conjuncts of the assumption set, then over the
    unrelated conjuncts (I2) and the history (I7)."""
    cs = _conjuncts(v.assum)
    if v.inv == "I5" and len(v.variant.get("parts", [])) == len(cs):
        pairs = list(zip(cs, v.variant["parts"]))

        def variant_of(sub):
            return dict(v.variant, parts=[q for _, q in sub],
                        assum=to_srepr(_join([from_srepr(q) for _, q in sub])))

        def test_p5(sub):
            return _guarded(v, v.prop, _join([c for c, _ in sub]), variant_of(sub))

        if len(pairs) >= 2 and test_p5(pairs):
            pairs = ddmin(pairs, test_p5, max_tests)
            v.assum, v.variant = _join([c for c, _ in pairs]), variant_of(pairs)
        # a conjunct the violation needs whose restatement it does not:
        # spelled as it was, so that the case's rewrite (the family key)
        # is the one that matters.  Kept only when the severity and both
        # answers are unchanged (a revert must not change the finding)
        assum5 = _join([c for c, _ in pairs])
        before = evaluate(v, v.prop, assum5, variant_of(pairs))[:3]
        for i in range(len(pairs)):
            c, q = pairs[i]
            if q == to_srepr(c):
                continue
            trial = pairs[:i] + [(c, to_srepr(c))] + pairs[i + 1:]
            if evaluate(v, v.prop, assum5, variant_of(trial))[:3] == before and test_p5(trial):
                pairs = trial
                v.variant = variant_of(pairs)
        cs = []                                  # done

    def test_a(sub):
        return _guarded(v, v.prop, _join(sub), v.variant)

    if len(cs) >= 2 and test_a(cs):
        cs = ddmin(cs, test_a, max_tests)
        v.assum = _join(cs)
    if v.inv == "I2":
        es = _conjuncts(from_srepr(v.variant["extra"]))

        def test_e(sub):
            return _guarded(v, v.prop, v.assum, dict(v.variant, extra=to_srepr(_join(sub))))
        if len(es) >= 2 and test_e(es):
            es = ddmin(es, test_e, max_tests)
            v.variant = dict(v.variant, extra=to_srepr(_join(es)))
        specs = list(v.variant.get("extensions", []))
        if specs:
            # registrations whose atom was dropped (or which were registration
            # only) may not matter: drop each that the violation survives without
            def test_s(sub):
                return _guarded(v, v.prop, v.assum, dict(v.variant, extensions=list(sub)))
            if test_s([]):
                specs = []
            elif len(specs) >= 2:
                specs = ddmin(specs, test_s, max_tests)
            v.variant = dict(v.variant, extensions=specs)
            if not specs:
                del v.variant["extensions"]
    if v.inv == "I7" and len(v.prefix) >= 1:
        def test_p(sub):
            old, v.prefix = v.prefix, list(sub)
            try:
                return _guarded(v, v.prop, v.assum, v.variant)
            finally:
                v.prefix = old
        if test_p([]):
            v.prefix = []
        elif len(v.prefix) >= 2:
            v.prefix = ddmin(list(v.prefix), test_p, max_tests)
    sev, base, other, var = evaluate(v)
    v.severity, v.base, v.other, v.variant, v.shrunk = sev or v.severity, base, other, var, True
    return v


def violation_from_json(d: Dict[str, Any]) -> Violation:
    v = Violation(d["inv"], d["severity"], EngineConfig.from_dict(d["config"]),
                  from_srepr(d["prop"]), from_srepr(d["assum"]), d["variant"], d["base"], d["other"],
                  d.get("source", ""), d.get("known"), d.get("shrunk", False),
                  [Ask(from_srepr(a["prop"]), from_srepr(a["assum"])) for a in d.get("prefix", [])])
    return v


def replay(path: str) -> Tuple[Optional[str], str, str]:
    """Replay a ``.json`` case: (severity or None, base, other)."""
    with open(path) as fh:
        v = violation_from_json(json.load(fh))
    sev, base, other, _ = evaluate(v)
    return sev, base, other


_SCRIPT = '''# Replays an invariant violation of satassume.sympy_api.ask (harness/INVARIANTS.md).
# Run from anywhere inside a satassume checkout:  PYTHONHASHSEED=0 python this_file.py
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.exists(os.path.join(_d, 'harness', '__init__.py')):
    if os.path.dirname(_d) == _d:
        _d = os.getcwd()
        break
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from harness.invariants import replay
sev, base, other = replay(os.path.join(os.path.dirname(os.path.abspath(__file__)), {json!r}))
print('invariant {inv}: base', base, '  variant', other, '  severity', sev)
assert sev is not None, (base, other)
'''


def write_case(v: Violation, directory: str, stem: str) -> Tuple[str, str]:
    os.makedirs(directory, exist_ok=True)
    jp, pp = os.path.join(directory, stem + ".json"), os.path.join(directory, stem + ".py")
    with open(jp, "w") as fh:
        json.dump(v.to_json(), fh, indent=1)
    with open(pp, "w") as fh:
        fh.write(_SCRIPT.format(json=stem + ".json", inv=v.inv))
    return jp, pp


# --------------------------------------------------------------------------
# the runner
# --------------------------------------------------------------------------

@dataclasses.dataclass
class InvReport:
    source: str
    config: str
    checked: Dict[str, int] = dataclasses.field(default_factory=dict)
    inconclusive: Dict[str, int] = dataclasses.field(default_factory=dict)
    candidates: Dict[str, int] = dataclasses.field(default_factory=dict)
    #: pairs exempt because a side is a budget-limited None (``budget_exempt``)
    exempt: Dict[str, int] = dataclasses.field(default_factory=dict)
    violations: List[Violation] = dataclasses.field(default_factory=list)
    seconds: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        return {"source": self.source, "config": self.config, "checked": self.checked,
                "inconclusive": self.inconclusive, "candidates": self.candidates,
                "budget_exempt": self.exempt,
                "seconds": round(self.seconds, 1),
                "violations": [v.summary() for v in self.violations]}


def extra_kinds(extra, specs: Sequence[dict] = ()) -> List[str]:
    """The kinds of unrelated material in an I2 variant (after shrinking:
    what suffices): ``closed`` (no fresh symbol), ``inf``, ``commutative``,
    ``relation``, ``declared``, ``pred``, ``compound``, ``ext:<cls>:<shape>``.
    Reported with the case and used to tell families apart."""
    kinds = set()
    cs = _conjuncts(extra)
    seen_syms: set = set()
    for c in cs:
        fs = {s for s in getattr(c, "free_symbols", ()) if isinstance(s, Symbol)}
        if fs & seen_syms:
            kinds.add("block")          # conjuncts sharing a symbol among themselves
        seen_syms |= fs
    for c in cs:
        if isinstance(c, (And, Or, Implies, Equivalent)):
            kinds.add("compound")
            continue
        inner = c.args[0] if isinstance(c, Not) else c
        if isinstance(inner, Basic) and inner.has(MatrixExpr):
            kinds.add("oos:matrix")
            continue
        if isinstance(inner, AppliedPredicate) and inner.function == Q.is_true and inner.arguments \
                and not isinstance(inner.arguments[0], Relational):
            kinds.add("oos:is_true")
            continue
        if isinstance(inner, AppliedPredicate) and inner.function == Q.is_true and inner.arguments:
            inner = inner.arguments[0]
        if isinstance(inner, Basic) and inner.has(S.Infinity, S.NegativeInfinity, S.ComplexInfinity):
            kinds.add("inf")
        elif isinstance(inner, AppliedPredicate) and inner.function == Q.commutative:
            kinds.add("commutative")
        elif isinstance(inner, Basic) and not inner.free_symbols:
            kinds.add("closed")
        elif isinstance(inner, Relational) or (isinstance(inner, AppliedPredicate) and inner.function in _SWAP):
            kinds.add("relation")
        elif isinstance(inner, AppliedPredicate) and inner.function not in _SWAP and str(inner.function.name) not in PREDICATES:
            kinds.add("custom")
        elif isinstance(inner, AppliedPredicate) and any(s.assumptions0.get(k) for s in inner.free_symbols for k in _DECLARED):
            kinds.add("declared")
        else:
            kinds.add("pred")
    for spec in specs:
        kinds.add(f"ext:{spec['cls']}:{spec['shape']}")
    # the classes of the constants in the material (the pool's classes)
    from sympy import Number, NumberSymbol
    classes = set()
    for c in cs:
        if not isinstance(c, Basic):
            continue
        for a in c.atoms(Number, NumberSymbol):
            if a in (S.Zero, S.One, S.NegativeOne, S(2)):
                continue
            k = const_class(a)
            if k:
                classes.add(k)
        for k in ("unsettled", "nonreal"):
            if any(c.has(u) for u in CONSTANTS[k]):
                classes.add(k)
    kinds |= {f"const:{k}" for k in classes}
    return sorted(kinds)


# --------------------------------------------------------------------------
# the rewrite of a variant (part of the family key, INVARIANTS.md)
# --------------------------------------------------------------------------

def term_class(t) -> str:
    """The class of a term for the family key: ``nan``, ``inf`` (``oo``,
    ``-oo``, ``zoo``), ``number`` (any other SymPy ``Number``), ``symbol``,
    ``closed`` (no free symbol: ``pi``, ``sqrt(2)``, ``f(1)``), ``expr``."""
    if t is S.NaN:
        return "nan"
    if t in (S.Infinity, S.NegativeInfinity, S.ComplexInfinity):
        return "inf"
    if getattr(t, "is_Number", False):
        return "number"
    if isinstance(t, Symbol):
        return "symbol"
    if isinstance(t, Basic) and not t.free_symbols:
        return "closed"
    return "expr"


def _atom_head(b) -> str:
    """The predicate or relation name of an atom (``Not`` looked through)."""
    if isinstance(b, Not):
        b = b.args[0]
    if isinstance(b, AppliedPredicate):
        return str(b.function.name)
    if isinstance(b, Relational) and type(b) in _QREL:
        return str(_QREL[type(b)].name)
    return type(b).__name__


def _atom_terms(b) -> str:
    if isinstance(b, Not):
        b = b.args[0]
    args = b.arguments if isinstance(b, AppliedPredicate) else (b.args if isinstance(b, Relational) else ())
    return ",".join(sorted({term_class(t) for t in args})) or "-"


_FORM_SYMBOL = Symbol("_form_tag_x")


def _form_tag(g) -> str:
    """``neg``, ``scale`` or ``shift``: which ``_TERM_FORMS`` transform ``g`` is."""
    d = _FORM_SYMBOL               # a Symbol: no Dummy (SymPy's global Dummy counter stays as on main)
    r = g(d)
    if r == -d:
        return "neg"
    return "scale" if getattr(r / d, "is_Number", False) else "shift"


def _atom_rewrites(b) -> List[Tuple[str, Any]]:
    """Every output ``restate`` (and ``restate_given``) can give for the
    atom ``b``, with the name of its rule, constants enumerated: the
    rewrite of a variant is recomputed by matching against these, so it
    needs no record of the random choices (and hand-written pins have one)."""
    out: List[Tuple[str, Any]] = []

    def add(rule, make):
        try:
            out.append((rule, make()))
        except Exception:  # noqa: BLE001 - a rule that cannot build this atom
            pass

    if isinstance(b, Not):
        inner = b.args[0]
        if isinstance(inner, AppliedPredicate) and inner.function in (Q.lt, Q.le, Q.gt, Q.ge):
            comp = {Q.lt: Q.ge, Q.le: Q.gt, Q.gt: Q.le, Q.ge: Q.lt}
            add("given", lambda: comp[inner.function](*inner.arguments))
        if isinstance(inner, AppliedPredicate) and inner.function in (Q.eq, Q.ne):
            add("ne-eq", lambda: (Q.ne if inner.function == Q.eq else Q.eq)(*inner.arguments))
        return out
    if isinstance(b, AppliedPredicate):
        f, args = b.function, b.arguments
        if len(args) == 1 and isinstance(args[0], Symbol):
            for fact, rw in _GIVEN.get(f, ()):
                if args[0].assumptions0.get(fact):
                    add("given", lambda rw=rw: rw(args[0]))
        if f in _SWAP:
            a, c = args
            add("swap", lambda: _SWAP[f](c, a))
            add("relational", lambda: {v: k for k, v in _QREL.items()}[f](a, c))
            for k in (S.One, S(-2), Rational(1, 2)):
                add("shift-relation", lambda k=k: f(a + k, c + k))
            add("shift-relation", lambda: f(S.Zero, c - a))
            add("shift-relation", lambda: f(a - c, S.Zero))
            add("shift-relation", lambda: f(-c, -a))
            for k in (S(2), S(3), Rational(1, 2)):
                add("shift-relation", lambda k=k: f(k * a, k * c))
        if len(args) == 1:
            x = args[0]
            if f == Q.zero:
                add("zero-eq", lambda: Q.eq(x, S.Zero))
            if f in _SPLIT:
                add("split", lambda: _SPLIT[f](x))
            for name in _IMPLIED.get(f, ()):
                add("implied", lambda name=name: And(b, getattr(Q, name)(x)))
            for g in _TERM_FORMS.get(f, ()):
                add("term-form:" + _form_tag(g), lambda g=g: f(g(x)))
            if f in _SIGN_FLIP:
                add("sign-flip", lambda: _SIGN_FLIP[f](-x))
        if f == Q.eq and len(args) == 2 and args[1] == S.Zero:
            add("eq-zero", lambda: Q.zero(args[0]))
        add("is_true", lambda: Q.is_true(b))
    elif isinstance(b, Relational):
        cls = type(b)
        if cls in _QREL:
            add("q-relation", lambda: _QREL[cls](*b.args))
        add("is_true", lambda: Q.is_true(b))
        if cls in _RSWAP:
            add("swap", lambda: _RSWAP[cls](b.rhs, b.lhs))
    return out


def _rewrite(b, n, out: List[str]) -> bool:
    """Append to ``out`` the rewrites that turn ``b`` into ``n`` (the
    structure of ``restate``); False when ``n`` is not recognised."""
    if n == b:
        return True
    if isinstance(n, Not) and isinstance(n.args[0], Not) and n.args[0].args[0] == b:
        out.append("double-not")
        return True
    for rule, c in _atom_rewrites(b):
        if c == n:
            out.append(f"{rule}({_atom_head(b)})[{_atom_terms(b)}]")
            return True
    if isinstance(b, Not):
        inner = b.args[0]
        if isinstance(inner, (And, Or)) and isinstance(n, Or if isinstance(inner, And) else And):
            tmp: List[str] = []
            if _rewrite_args(inner.args, [negate(x) for x in n.args], tmp):
                out.extend(tmp + ["de-morgan"])
                return True
        return _rewrite(inner, negate(n), out)
    if isinstance(b, Implies):
        a, c = b.args
        if isinstance(n, Implies):
            n1, n2 = n.args
            for tag, pairs in (("", ((a, n1), (c, n2))), ("contrapositive", ((a, negate(n2)), (c, negate(n1))))):
                tmp = []
                if all(_rewrite(x, y, tmp) for x, y in pairs):
                    out.extend(tmp + ([tag] if tag else []))
                    return True
        if isinstance(n, Or) and len(n.args) == 2:
            for n1, n2 in (n.args, n.args[::-1]):
                tmp = []
                if _rewrite(a, negate(n1), tmp) and _rewrite(c, n2, tmp):
                    out.extend(tmp + ["implies-or"])
                    return True
        return False
    if isinstance(b, Equivalent) and len(b.args) == 2:
        a, c = b.args
        if isinstance(n, Equivalent) and len(n.args) == 2:
            for n1, n2 in (n.args, n.args[::-1]):
                tmp = []
                if _rewrite(a, n1, tmp) and _rewrite(c, n2, tmp):
                    out.extend(tmp)
                    return True
        if isinstance(n, (And, Or)):
            tag = "equiv-implies" if isinstance(n, And) else "equiv-or"
            want = Implies if isinstance(n, And) else And
            for arg in n.args:
                if isinstance(arg, want) and len(arg.args) == 2:
                    for n1, n2 in (arg.args, arg.args[::-1]):
                        tmp = []
                        if _rewrite(a, n1, tmp) and _rewrite(c, n2, tmp):
                            out.extend(tmp + [tag])
                            return True
        return False
    if isinstance(b, (And, Or)) and type(n) is type(b):
        tmp = []
        if _rewrite_args(b.args, n.args, tmp, type(b)):
            out.extend(tmp)
            return True
    return False


def _rewrite_args(orig: Sequence[Any], new: Sequence[Any], out: List[str], op=None) -> bool:
    """Each argument of ``new`` is an argument of ``orig`` or a rewrite of
    one.  SymPy reorders, merges duplicates and flattens: a rewrite of an
    argument that is itself an ``op`` (``split`` as an ``Or`` inside an
    ``Or``, ``implied`` as an ``And`` inside an ``And``) appears as several
    arguments of ``new``."""
    rest = [x for x in new if x not in orig]
    if op is not None:
        for o in orig:
            for rule, c in _atom_rewrites(o):
                if isinstance(c, op) and len(c.args) > 1 and all(y in rest or y in orig for y in c.args) \
                        and any(y in rest for y in c.args):
                    rest = [y for y in rest if y not in c.args]
                    out.append(f"{rule}({_atom_head(o)})[{_atom_terms(o)}]")
                    break
    for x in rest:
        for o in orig:
            tmp: List[str] = []
            if _rewrite(o, x, tmp):
                out.extend(tmp)
                break
        else:
            return False
    return True


def rewrite_of(b, n) -> List[str]:
    """The rewrites that restated ``b`` as ``n`` (``prop-pad``: the
    proposition padded by ``restate_prop``), each ``rule(head)[term
    classes]`` for an atom rule (``zero-eq(zero)[nan]``,
    ``shift-relation(eq)[expr,number]``, ``term-form:neg(zero)[expr]``);
    ``?(<head>)`` when the restatement is not recognised."""
    if isinstance(n, (And, Or)):
        # the padding (``restate_prop``: ``atom | ~atom`` or ``atom & ~atom``
        # over the fresh ``iw``).  Matched as a set: released SymPy orders
        # the arguments of an unevaluated ``And``/``Or`` and the pin's dev
        # SymPy does not, and an ``Or`` proposition padded with ``Or`` is
        # flattened by neither or both
        pads = [a for a in n.args if isinstance(a, (And, Or)) and len(a.args) == 2
                and any(isinstance(s, Symbol) and s.name == "iw" for s in a.free_symbols)]
        rest = [a for a in n.args if a not in pads]
        if pads and (rest == [b] or (type(b) is type(n) and set(rest) == set(b.args))):
            return ["prop-pad"]
    out: List[str] = []
    if _rewrite(b, n, out):
        return out
    return [f"?({_atom_head(b)})"]


def i5_rewrite(prop, assum, variant: dict) -> List[str]:
    """The rewrite of an I5 variant (recomputed from the case: the
    original and the restated conjuncts or proposition), sorted, without
    repeats: ``["syntax"]`` for the syntax kind."""
    kind = variant.get("kind")
    if kind == "syntax":
        return ["syntax"]
    out: List[str] = []
    if kind == "prop" and "prop" in variant:
        out = rewrite_of(prop, from_srepr(variant["prop"]))
    elif kind == "restate" and "parts" in variant:
        cs = _conjuncts(assum)
        parts = [from_srepr(q) for q in variant["parts"]]
        for i, q in enumerate(parts):
            if q in cs:
                continue
            # paired by position (``check_I5``, ``shrink`` keep the order),
            # then any conjunct
            order = ([cs[i]] if i < len(cs) and len(cs) == len(parts) else []) + cs
            got = None
            for c in order:
                r = rewrite_of(c, q)
                if not r[0].startswith("?"):
                    got = r
                    break
            out.extend(got or (rewrite_of(order[0], q) if order else [f"?({_atom_head(q)})"]))
    return sorted(set(out))


def prop_heads(prop) -> str:
    """``prop:<heads>``: the predicate and relation names of the
    proposition's atoms, sorted (the I2 key: what was asked, whose answer
    the unrelated material changed)."""
    heads = set()

    def walk(e):                  # the Boolean structure (``atoms`` misses some applied predicates)
        if isinstance(e, (AppliedPredicate, Relational)):
            heads.add(_atom_head(e))
        elif isinstance(e, (Not, And, Or, Implies, Equivalent)):
            for a in e.args:
                walk(a)
    walk(prop)
    return "prop:" + (",".join(sorted(heads)) or "-")


def family_detail(v: "Violation") -> tuple:
    """The component of the family key that names the variant's rewrite:
    I5 the rewrites (``variant["rewrite"]``, computed without storing when
    missing), I2 the proposition's heads, I3 the declared fact, I7 the
    setting, I1 the blocks mode, I6 the mechanism (in-process rename or a
    ``hashseed`` subprocess); empty for I4 (one rewrite)."""
    var = v.variant
    if v.inv == "I5":
        return tuple(var["rewrite"] if "rewrite" in var else i5_rewrite(v.prop, v.assum, var))
    if v.inv == "I2":
        return (prop_heads(v.prop),)
    if v.inv == "I6":
        return ("process" if var.get("hashseed") is not None else "in-process",)
    if v.inv == "I3" and var.get("kind") == "declared":
        return (f"declared:{var.get('pred')}={var.get('value')}",)
    if v.inv == "I7":
        return (f"setting:{var.get('name')}",)
    if v.inv == "I1" and var.get("blocks"):
        return ("blocks",)
    return ()


#: the probes of the fingerprint: each switches one mechanism off (or, for
#: the discovery budget, lifts it); the fingerprint of a candidate is the
#: set of probes under which the difference vanishes
PROBES: Dict[str, dict] = {
    "relevance": {"relevance": False},
    "transfer": {"transfer": False},
    "none": {"uninterpreted": "none"},
    # #97 P7: the probe set only the removed no-op settings (cone_search,
    # cone_threshold); it is the configuration itself now, so ``fingerprint``
    # skips it.  Kept so that recorded fingerprint names stay meaningful.
    "cone": {},
    "budget": {"discovery_budget": 400},
    "norel": {"relations": "none"},
}


def fingerprint(v: Violation) -> str:
    """The probes (``PROBES``) under which the candidate's difference
    vanishes while the base answer persists (a probe that changes the base
    answer itself says nothing about the mechanism), as ``"a,b"`` (``"-"``:
    none); ``?`` after a probe that errored.  With the kinds it keys the family: two cases with the same
    answer shape but different fingerprints are different families."""
    gone = []
    for name, over in PROBES.items():
        if all(getattr(v.config, k) == val for k, val in over.items()):
            continue                      # the probe is the configuration itself
        cfg = dataclasses.replace(v.config, name=f"{v.config.name}+{name}", **over)
        w = dataclasses.replace(v, config=cfg)
        try:
            sev, base, other, _ = evaluate(w)
        except Exception:  # noqa: BLE001
            gone.append(name + "?")
            continue
        if sev is None and base == v.base:
            gone.append(name)         # the base answer persists and the difference is gone
    return ",".join(gone) or "-"


def family_key(v: Violation) -> tuple:
    """(invariant, severity, base, other, kinds, fingerprint, detail).  The
    constant classes (``const:<class>``) are recorded in the case but are
    not part of the I2 kinds: the same mechanism reached with another
    constant is the same family.  ``detail`` (``family_detail``) names the
    variant's rewrite (I5: rule, predicate, term classes); it was added
    after the first six, which are the key before it, so a match of the
    whole key is a match of the old one (INVARIANTS.md)."""
    kinds = tuple(k for k in v.variant.get("kinds", ()) if not k.startswith("const:")) if v.inv == "I2" \
        else (str(v.variant.get("kind", "")),)
    return (v.inv, v.severity, v.base, v.other, kinds, v.fingerprint or "-", family_detail(v))


def _settings(cfg: EngineConfig) -> EngineConfig:
    """A configuration without its name (what the engine is built with)."""
    return dataclasses.replace(cfg, name="")


PINNED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness", "repros", "invariants")
#: pinned cases by shape (inv, severity, base, other) -> [(stem, Violation)], loaded once
_PINNED: Dict[tuple, list] = {}
_PINNED_LOADED = False
#: pinned families (family keys) reported in this run (``KNOWN_SEEN``)
KNOWN_SEEN: set = set()
#: families (``family_key``) reported in this run, with counts: at most
#: ``FAMILY_RUN_CAP`` reports (and shrinks) of one family per run, whatever
#: the profile or configuration (the CPU goes to new mechanisms)
FAMILY_SEEN: Dict[tuple, int] = {}
FAMILY_RUN_CAP = 2


#: the recorded family fields of each pinned case, by stem (``_pinned_with_shape``)
_PIN_META: Dict[str, dict] = {}


def _pin_recorded(stem: str, w: Violation) -> bool:
    """The pinned case carries the fields of the current family key
    (``config_specific``; I5: ``variant["rewrite"]``).  A pin recorded
    before them matches nothing until ``python -m harness pins --write``
    re-records it: old files are not matched more loosely."""
    meta = _PIN_META.get(stem, {})
    return isinstance(meta.get("config_specific"), bool) and (w.inv != "I5" or "rewrite" in w.variant)


def _pinned_with_shape(shape: tuple) -> list:
    """The pinned cases of ``shape``, each with its fingerprint computed
    (once per process, lazily: only shapes a candidate reaches)."""
    global _PINNED_LOADED
    if not _PINNED_LOADED:
        _PINNED_LOADED = True
        import glob
        for path in sorted(glob.glob(os.path.join(PINNED_DIR, "*.json"))):
            try:
                with open(path) as f:
                    d = json.load(f)
                w = violation_from_json(d)
            except Exception:  # noqa: BLE001
                continue
            stem = os.path.basename(path)[:-5]
            _PIN_META[stem] = {"config_specific": d.get("config_specific")}
            _PINNED.setdefault((w.inv, w.severity, w.base, w.other), []).append([stem, w])
    out = []
    for entry in _PINNED.get(shape, []):
        stem, w = entry
        if w.fingerprint is None:
            try:
                sev, base, other, var = evaluate(w)
                if sev is None:
                    w.fingerprint = "gone"   # the pinned case no longer violates here
                else:
                    if w.inv == "I2" and "kinds" not in w.variant:
                        w.variant = dict(w.variant, kinds=extra_kinds(from_srepr(w.variant["extra"]),
                                                                      w.variant.get("extensions", ())))
                    w.fingerprint = fingerprint(w)
            except Exception:  # noqa: BLE001
                w.fingerprint = "gone"
        out.append((stem, w))
    return out


def _match_pinned(v: Violation, key: tuple, subset: bool = False) -> Optional[str]:
    """``pinned:<stem>`` of the first pinned case whose family key is
    ``key`` (the candidate's): all seven components equal, and the same
    configuration when the pin is ``config_specific``.  Before shrinking
    (``subset``) the pinned case's I2 kinds need only be *among* the
    candidate's (shrinking removes material, never adds); the rewrite is
    compared exactly then too (a candidate with two rewritten conjuncts
    is shrunk before it can match a one-rewrite pin)."""
    for stem, w in _pinned_with_shape((v.inv, v.severity, v.base, v.other)):
        if w.fingerprint in (None, "gone") or not _pin_recorded(stem, w):
            continue
        if _PIN_META[stem]["config_specific"] and _settings(w.config) != _settings(v.config):
            continue
        wk = family_key(w)
        if wk == key or (subset and wk[:4] == key[:4] and wk[5:] == key[5:] and set(wk[4]) <= set(key[4])):
            return f"pinned:{stem}"
    return None


def _known(v: Violation, subset: bool = False) -> Optional[str]:
    """``pinned:<stem>`` when the candidate's family key is a pinned
    case's (``_match_pinned``).  The kinds, the fingerprint and the
    rewrite are (re)computed here."""
    if v.inv == "I2":
        v.variant = dict(v.variant, kinds=extra_kinds(from_srepr(v.variant["extra"]),
                                                      v.variant.get("extensions", ())))
    if v.inv == "I5":
        v.variant = dict(v.variant, rewrite=i5_rewrite(v.prop, v.assum, v.variant))
    v.fingerprint = fingerprint(v)
    return _match_pinned(v, family_key(v), subset)


def pin_record(path: str) -> Dict[str, Any]:
    """The family fields of the pinned case at ``path`` recomputed by
    replaying it: ``rewrite`` (I5), ``fingerprint``, ``config_specific``
    (the case does not reproduce with the same answers under the
    ``default`` preset, so its pin covers only its own configuration), the
    key before (``old_key``, six components) and with them (``key``);
    ``gone`` when the case no longer violates."""
    from .state import preset
    with open(path) as fh:
        d = json.load(fh)
    w = violation_from_json(d)
    sev, base, other, _ = evaluate(w)
    rec: Dict[str, Any] = {"stem": os.path.basename(path)[:-5], "gone": sev is None,
                           "recorded": {"rewrite": d["variant"].get("rewrite"),
                                        "config_specific": d.get("config_specific")}}
    if sev is None:
        return rec
    if w.inv == "I2" and "kinds" not in w.variant:
        w.variant = dict(w.variant, kinds=extra_kinds(from_srepr(w.variant["extra"]),
                                                      w.variant.get("extensions", ())))
    if w.inv == "I5":
        w.variant = dict(w.variant, rewrite=i5_rewrite(w.prop, w.assum, w.variant))
    w.fingerprint = fingerprint(w)
    specific = False
    if _settings(w.config) != _settings(preset("default")):
        u = dataclasses.replace(w, config=preset("default"))
        s2, b2, o2, _ = evaluate(u)
        specific = s2 is None or (b2, o2) != (base, other)
    key = family_key(w)
    rec.update(rewrite=w.variant.get("rewrite"), fingerprint=w.fingerprint, config_specific=specific,
               old_key=key[:6], key=key)
    return rec


def rerecord_pins(directory: str = PINNED_DIR, write: bool = False) -> List[Dict[str, Any]]:
    """Every pinned case of ``directory`` (``*.json``, not ``fixed/``)
    through ``pin_record``; with ``write`` the recomputed fields are
    written back into the case (``variant.rewrite``, ``config_specific``;
    the fingerprint is recomputed at match time, never read from the
    file), nothing else changes; a rewrite with ``?(...)`` (a restatement
    ``rewrite_of`` does not name) is refused.  ``python -m harness pins
    --write`` is the one-liner after a change of the family key or a
    rebase that brings new pins; without ``--write`` it checks that every
    pin is recorded and current."""
    global _PINNED_LOADED
    import glob
    out = []
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        rec = pin_record(path)
        rec["current"] = not rec["gone"] and rec["recorded"] == {"rewrite": rec.get("rewrite"),
                                                                 "config_specific": rec.get("config_specific")}
        if write and not rec["gone"]:
            with open(path) as fh:
                d = json.load(fh)
            if any(r.startswith("?") for r in rec.get("rewrite") or ()):
                rec["unclassified"] = True     # not written: classify the rule first
                out.append(rec)
                continue
            if rec.get("rewrite") is not None:
                d["variant"]["rewrite"] = rec["rewrite"]
            d["config_specific"] = rec["config_specific"]
            with open(path, "w") as fh:
                json.dump(d, fh, indent=1)
        out.append(rec)
    _PINNED.clear()                       # reloaded with the new records on the next match
    _PIN_META.clear()
    _PINNED_LOADED = False
    return out


def run_stream(items: Sequence[Item], config: EngineConfig, invs: Sequence[str], seed: int,
               source: str = "", max_violations: int = 5, shrink_them: bool = True,
               deadline: Optional[float] = None, progress: Optional[Callable[[str], None]] = None,
               i1_rounds: int = 3, slow_limit: float = 3.0, i2_rounds: int = 3, i5_rounds: int = 2,
               clock: Callable[[], float] = time.time, family_cap: int = 1,
               widen: bool = True) -> InvReport:
    """Every ``Ask`` of ``items`` (events are skipped: the registry is
    configuration, checked by ``python -m harness fuzz --custom``) through
    each checker in ``invs``; at most ``max_violations`` reports per
    invariant per stream, and ``family_cap`` of the same shape (invariant,
    severity, base answer, variant answer), so that one large family does
    not spend the budget on shrinking."""
    rng = random.Random(seed)
    rep = InvReport(source, config.name)
    t0 = time.time()
    asks = [it for it in items if isinstance(it, Ask)]
    if widen:
        asks = asks + derived_asks(asks, rng)
    seen = set()
    for idx, it in enumerate(asks):
        if deadline is not None and clock() > deadline:
            break
        key = (it.prop, it.assum)
        if key in seen:
            continue
        seen.add(key)
        t1 = time.time()
        base = fresh_outcome(it.prop, it.assum, config)
        base_limited = LAST_BUDGET_LIMITED[0]
        if time.time() - t1 > slow_limit:
            rep.inconclusive["slow"] = rep.inconclusive.get("slow", 0) + 1
            continue              # a query that alone takes seconds would eat the budget
        for inv in invs:
            # the cap is per invariant: a flood of one family (the I2
            # lost-definiteness one) must not stop the other checkers
            if sum(v.inv == inv for v in rep.violations) >= max_violations:
                continue
            rounds = {"I1": i1_rounds, "I2": i2_rounds, "I5": i5_rounds}.get(inv, 1)
            for k in range(rounds):
                try:
                    if inv == "I7":
                        prefix = asks[max(0, idx - rng.choice([1, 2, 4, 8])):idx]
                        sev, other, var = check_I7(it.prop, it.assum, config, base, rng, None, prefix)
                        b = var["fresh"]
                    elif inv == "I5" and k == 1:
                        prefix = []
                        b = base
                        sev, other, var = check_I5(it.prop, it.assum, config, base, rng, prop_only=True)
                    else:
                        prefix = []
                        b = base
                        sev, other, var = CHECKERS[inv](it.prop, it.assum, config, base, rng)
                    other_limited = LAST_BUDGET_LIMITED[0]
                except Exception as e:  # noqa: BLE001 - a checker crash is not a violation
                    rep.inconclusive[inv] = rep.inconclusive.get(inv, 0) + 1
                    if progress:
                        progress(f"{inv} checker error on {it}: {type(e).__name__}: {e}")
                    continue
                rep.checked[inv] = rep.checked.get(inv, 0) + 1
                if "ValueError" in (b, other):
                    rep.inconclusive[inv] = rep.inconclusive.get(inv, 0) + 1
                if sev is None:
                    continue
                if inv != "I7" and budget_exempt(inv, base_limited, other_limited):
                    rep.exempt[inv] = rep.exempt.get(inv, 0) + 1
                    continue
                rep.candidates[inv] = rep.candidates.get(inv, 0) + 1
                v = Violation(inv, sev, config, it.prop, it.assum, var, b, other, source,
                              prefix=list(prefix))
                if not _guarded(v, v.prop, v.assum, v.variant):
                    rep.inconclusive[inv] = rep.inconclusive.get(inv, 0) + 1
                    continue
                v.known = _known(v, subset=True)     # kinds, fingerprint, pinned match (before shrinking)
                if v.known and (any(w.known == v.known for w in rep.violations) or v.known in KNOWN_SEEN):
                    rep.inconclusive["family_repeat"] = rep.inconclusive.get("family_repeat", 0) + 1
                    continue          # one finding covers a known family (per run for a pinned one)
                fam = (inv, sev, b, other)
                if sum((w.inv, w.severity, w.base, w.other) == fam for w in rep.violations) >= family_cap \
                        and not (v.fingerprint and all(family_key(w) != family_key(v) for w in rep.violations)):
                    continue          # the same shape again (the I2 definite -> None flood): shrinking costs
                if v.known:
                    KNOWN_SEEN.add(v.known)
                    FAMILY_SEEN[family_key(v)] = FAMILY_SEEN.get(family_key(v), 0) + 1
                    rep.violations.append(v)     # tagged with the pinned case, never shrunk again
                    if progress:
                        progress("violation: " + v.summary())
                    continue
                if FAMILY_SEEN.get(family_key(v), 0) >= FAMILY_RUN_CAP:
                    rep.inconclusive["family_repeat"] = rep.inconclusive.get("family_repeat", 0) + 1
                    continue          # a family already reported in this run (kinds and fingerprint)
                if shrink_them:
                    try:
                        shrink(v)
                    except Exception as e:  # noqa: BLE001
                        if progress:
                            progress(f"shrink failed: {type(e).__name__}: {e}")
                    if not _guarded(v, v.prop, v.assum, v.variant):
                        continue      # gone after shrinking: not reproducible
                # the family of the *shrunk* case (what suffices): kinds,
                # fingerprint and the pinned match again
                v.known = _known(v)
                key = family_key(v)
                if FAMILY_SEEN.get(key, 0) >= FAMILY_RUN_CAP or (v.known and v.known in KNOWN_SEEN):
                    rep.inconclusive["family_repeat"] = rep.inconclusive.get("family_repeat", 0) + 1
                    continue          # the same family once shrunk
                FAMILY_SEEN[key] = FAMILY_SEEN.get(key, 0) + 1
                if v.known:
                    KNOWN_SEEN.add(v.known)
                if any(family_key(w) == key for w in rep.violations):
                    continue          # the same family in this slice
                rep.violations.append(v)
                if progress:
                    progress("violation: " + v.summary())
    rep.seconds = time.time() - t0
    return rep
