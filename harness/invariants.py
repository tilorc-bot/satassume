"""Invariant checkers I1-I7 (see ``harness/INVARIANTS.md``).

Every checker takes one query ``ask(p, A)`` from a generated stream, builds
one or more *variants* of it (the solver with a seeded subset of its
clauses dropped, an unrelated conjunct added, a stronger set, the negated
proposition, a restated set, renamed symbols, a setting changed after
history) and compares the answers of fresh engines under the exact
statement of the invariant.  Nothing here is heuristic: a pair of answers
is reported only if the invariant as stated forbids it, the assumption set
is known consistent (a model found by the engine's own solver with full
escalation and search, ``sympy_api._consistent``), and neither answer is
an inconsistency report (``ValueError``: allowed whatever the history).

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

from sympy import Dummy, Eq, Function, Ge, Gt, Le, Lt, Ne, Q, Symbol, exp, sqrt, pi, S
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

import satassume.sympy_api as _api
from satassume.rules import PREDICATES
from satassume.solver import Solver

from .checker import Ask, Event, Item, ddmin
from .outcomes import outcome
from .state import EngineConfig
from .sympy_io import from_srepr, to_srepr

INVARIANTS = ("I1", "I2", "I3", "I4", "I5", "I6", "I7")
SEVERITY = ("wrong", "depends", "lost", "crash")

DEFINITE = ("True", "False")


def _definite(o: str) -> bool:
    return o in DEFINITE


def _error(o: str) -> bool:
    return o.startswith("Error:") or o.startswith("Value:")


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
def dropping_clauses(seed: int, rate: float, stats: Optional[dict] = None):
    """While active, every ``Solver.add_clause`` / ``add_clauses`` /
    ``add_internal`` drops the clauses ``_drop`` selects (an engine change
    is not needed: the engine only ever sees a subset of the clauses it
    meant to add).  Not covered: ``add_pattern`` and the lazily loaded rule
    blocks (``mention_blocks``), which insert whole compiled blocks."""
    orig_add, orig_bulk, orig_int = Solver.add_clause, Solver.add_clauses, Solver.add_internal
    n = {"dropped": 0, "kept": 0}

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

    Solver.add_clause, Solver.add_clauses, Solver.add_internal = add_clause, add_clauses, add_internal
    try:
        yield n
    finally:
        Solver.add_clause, Solver.add_clauses, Solver.add_internal = orig_add, orig_bulk, orig_int
        if stats is not None:
            stats.update(n)


# --------------------------------------------------------------------------
# consistency guard
# --------------------------------------------------------------------------

def consistent(assum, config: EngineConfig) -> bool:
    """The engine's own solver finds a model of ``assum`` (full escalation
    and search).  False also when that cannot be decided: a candidate
    violation under such a set is not reported."""
    if assum is True or assum is S.true:
        return True
    eng = config.make()
    try:
        return bool(_api._consistent(assum, eng, count=False, search=True))
    except Exception:  # noqa: BLE001
        return False


def fresh_outcome(prop, assum, config: EngineConfig) -> str:
    return outcome(prop, assum, config.make())


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
_FINITE_CONSTS = [S.Zero, S.One, S(2), S(-3), S.Half, pi, sqrt(2), S(7)]


class Unrelated:
    """Conjuncts over fresh symbols and fresh undefined functions, each
    piece satisfiable on its own and sharing nothing with the others or
    with the query: their conjunction is satisfiable, and ``A & B`` is
    consistent exactly when ``A`` is.  Each piece is a predicate on a term
    ``u + T(v, ...)`` (``u`` appears nowhere else: the term takes every
    value), on a product or power of fresh symbols, on ``h(u)`` with a
    fresh ``h``, a relation between two such terms with different bases,
    or a fact on a declared fresh symbol consistent with its declaration."""

    def __init__(self, rng: random.Random, tag: str):
        self.rng, self.tag, self.k = rng, tag, 0

    def sym(self, **kw):
        self.k += 1
        return Symbol(f"{self.tag}u{self.k}", **kw)

    def func(self):
        self.k += 1
        return Function(f"{self.tag}h{self.k}")

    def _inner(self, depth: int):
        r = self.rng
        if depth <= 0 or r.random() < 0.4:
            return self.sym() if r.random() < 0.7 else r.choice(_FINITE_CONSTS)
        c = r.random()
        if c < 0.3:
            return self._inner(depth - 1) + self._inner(depth - 1)
        if c < 0.55:
            return self._inner(depth - 1) * self._inner(depth - 1)
        if c < 0.7:
            return self._inner(depth - 1) ** r.choice([2, 3, -1, S.Half])
        if c < 0.85:
            return self.func()(self._inner(depth - 1))
        return r.choice([exp, sqrt])(self._inner(depth - 1))

    def free_term(self, depth: int):
        """A term whose value is unconstrained: a fresh symbol plus anything."""
        r = self.rng
        c = r.random()
        if c < 0.35:
            return self.sym()
        if c < 0.55:
            return self.func()(self._inner(depth))
        if c < 0.7:
            return self.sym() * self.sym()
        if c < 0.8:
            return self.sym() ** r.choice([2, 3, S.Half])
        return self.sym() + self._inner(depth)

    def piece(self, depth: int = 2):
        r = self.rng
        c = r.random()
        if c < 0.55:
            atom = getattr(Q, r.choice(VALUE_PREDS))(self.free_term(depth))
            return Not(atom) if r.random() < 0.25 else atom
        if c < 0.8:
            a, b = self.free_term(depth), self.free_term(depth) if r.random() < 0.7 else r.choice(_FINITE_CONSTS)
            rel = r.choice([Q.lt, Q.le, Q.gt, Q.ge, Q.eq, Q.ne, Lt, Le, Gt, Ge, Eq, Ne])
            if a == b:
                return Q.eq(a, b)
            return rel(a, b)
        kind = r.choice(list(_DECLARED))
        s = self.sym(**{kind: True})
        return getattr(Q, r.choice(_DECLARED[kind]))(s)

    def conjunction(self, n: int, depth: int = 2):
        return And(*[self.piece(depth) for _ in range(n)])


# --------------------------------------------------------------------------
# I5: equivalent restatements; I6: renaming
# --------------------------------------------------------------------------

_SWAP = {Q.lt: Q.gt, Q.gt: Q.lt, Q.le: Q.ge, Q.ge: Q.le, Q.eq: Q.eq, Q.ne: Q.ne}
_RSWAP = {Lt: Gt, Gt: Lt, Le: Ge, Ge: Le, Eq: Eq, Ne: Ne}
_QREL = {Lt: Q.lt, Gt: Q.gt, Le: Q.le, Ge: Q.ge, Eq: Q.eq, Ne: Q.ne}


def restate(b, rng: random.Random, p: float = 0.5):
    """An equivalent restatement of the Boolean ``b``: swapped relation
    sides (``lt(a, b)`` -> ``gt(b, a)``), the three spellings of a
    relation, ``Implies`` as ``Or``, ``Equivalent`` as two ``Implies``,
    ``Q.is_true`` around an atom, reordered ``And``/``Or`` arguments (SymPy
    re-sorts them, so this checks the engine's own ordering)."""
    if isinstance(b, AppliedPredicate):
        f = b.function
        if f in _SWAP and rng.random() < p:
            a, c = b.arguments
            return _SWAP[f](c, a)
        if f in _SWAP and rng.random() < p:
            try:
                return {v: k for k, v in _QREL.items()}[f](*b.arguments)
            except Exception:  # noqa: BLE001
                return b
        if rng.random() < p * 0.3:
            return Q.is_true(b)
        return b
    if isinstance(b, Relational):
        cls = type(b)
        if cls in _QREL and rng.random() < p:
            return _QREL[cls](*b.args)
        if cls in _RSWAP and rng.random() < p:
            try:
                return _RSWAP[cls](b.rhs, b.lhs)
            except Exception:  # noqa: BLE001
                return b
        return b
    if isinstance(b, Not):
        return Not(restate(b.args[0], rng, p))
    if isinstance(b, Implies):
        a, c = b.args
        a, c = restate(a, rng, p), restate(c, rng, p)
        return Or(Not(a), c) if rng.random() < p else Implies(a, c)
    if isinstance(b, Equivalent) and len(b.args) == 2:
        a, c = (restate(x, rng, p) for x in b.args)
        return And(Implies(a, c), Implies(c, a)) if rng.random() < p else Equivalent(a, c)
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
    out = []
    for e in exprs:
        if not hasattr(e, "xreplace"):
            out.append(e)
            continue
        e = e.xreplace(smap)
        if fmap:
            e = e.replace(lambda x: isinstance(x, AppliedUndef) and x.func in fmap,
                          lambda x: fmap[x.func](*x.args))
        out.append(e)
    return out


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

    def summary(self) -> str:
        k = f" known:{self.known}" if self.known else ""
        return (f"{self.inv} {self.severity}{k} [{self.config.name}] ask({self.prop}, {self.assum}) "
                f"= {self.base}; variant {self.variant.get('kind')} = {self.other}")

    def to_json(self) -> Dict[str, Any]:
        return {"inv": self.inv, "severity": self.severity, "known": self.known,
                "config": self.config.to_dict(), "prop": to_srepr(self.prop),
                "assum": to_srepr(self.assum), "variant": self.variant, "base": self.base,
                "other": self.other, "source": self.source, "shrunk": self.shrunk,
                "prefix": [{"prop": to_srepr(a.prop), "assum": to_srepr(a.assum)} for a in self.prefix]}


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
    stats: dict = {}
    with dropping_clauses(variant["seed"], variant["rate"], stats):
        other = fresh_outcome(prop, assum, config)
    variant = dict(variant, dropped=stats.get("dropped", 0), kept=stats.get("kept", 0))
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
        u = Unrelated(random.Random(rng.randrange(1 << 30)), "iu")
        n = rng.choice([1, 1, 2, 3, 5, 8, 12])
        extra = u.conjunction(n, depth=rng.choice([1, 2, 3]))
        variant = {"kind": "unrelated", "extra": to_srepr(extra)}
    extra = from_srepr(variant["extra"])
    new = extra if assum is True or assum is S.true else And(assum, extra)
    other = fresh_outcome(prop, new, config)
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
        b = prop if base == "True" else Not(prop)
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
    """ask(p, A) is True exactly when ask(~p, A) is False."""
    variant = variant or {"kind": "negation"}
    other = fresh_outcome(Not(prop), assum, config)
    sev = None
    if "ValueError" not in (base, other):
        if _error(base) or _error(other):
            sev = "crash" if base != other else None
        elif base == "True" and other != "False" or other == "False" and base != "True":
            sev = "wrong" if _definite(base) and _definite(other) else "lost"
        elif base == "False" and other != "True" or other == "True" and base != "False":
            sev = "wrong" if _definite(base) and _definite(other) else "lost"
    return sev, other, variant


def check_I5(prop, assum, config, base, rng, variant=None):
    """An equivalent restatement of the assumptions gives the same answer."""
    if assum is True or assum is S.true:
        return None, base, variant or {"kind": "skip"}
    if variant is None:
        r = restate(assum, random.Random(rng.randrange(1 << 30)))
        variant = {"kind": "restate", "assum": to_srepr(r)}
    new = from_srepr(variant["assum"])
    other = fresh_outcome(prop, new, config)
    return _severity_same("I5", base, other), other, variant


def check_I6(prop, assum, config, base, rng, variant=None):
    """Renaming symbols and functions to fresh names gives the same answer."""
    if variant is None:
        p2, a2 = rename([prop, assum], random.Random(rng.randrange(1 << 30)))
        variant = {"kind": "rename", "prop": to_srepr(p2), "assum": to_srepr(a2)}
    p2, a2 = from_srepr(variant["prop"]), from_srepr(variant["assum"])
    other = fresh_outcome(p2, a2, config)
    return _severity_same("I6", base, other), other, variant


I7_SETTINGS = {
    "discovery_budget": [5, 40, 400, 5000],
    "cone_threshold": [0, 3, 1000],
    "transfer": [True, False],
    "cone_search": [True, False],
    "relevance": [True, False],
    "session_limit": [2, 2000],
    "keep_sessions": [1, 16],
}


def check_I7(prop, assum, config, base, rng, variant=None, prefix: Sequence[Ask] = ()):
    """After a history, changing a setting gives the answer of a fresh
    engine with that setting (``base`` is ignored: the reference is fresh
    under the new setting)."""
    if variant is None:
        name = rng.choice(list(I7_SETTINGS))
        vals = [v for v in I7_SETTINGS[name] if v != getattr(config, name)]
        variant = {"kind": "setting", "name": name, "value": rng.choice(vals)}
    cfg2 = config.replace(**{variant["name"]: variant["value"]}, name=f"{config.name}+{variant['name']}")
    ref = fresh_outcome(prop, assum, cfg2)
    eng = config.make()
    for a in prefix:
        outcome(a.prop, a.assum, eng)
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
    sev, other, var = CHECKERS[v.inv](prop, assum, v.config, base, rng, variant)
    return sev, base, other, var


def _guarded(v: Violation, prop, assum, variant) -> bool:
    """The candidate still violates and its sets are consistent."""
    sev, base, other, var = evaluate(v, prop, assum, variant)
    if sev is None:
        return False
    if not consistent(assum, v.config):
        return False
    if v.inv in ("I2", "I3"):
        # A & B is consistent iff A is, by construction: B is over fresh
        # symbols and functions and satisfiable (I2), or p / ~p as answered
        # or a declared fact (I3); the engine's own check would refuse
        # sets with relations no theory reads and lose real findings
        return True
    if v.inv == "I5":
        return consistent(from_srepr(var["assum"]), v.config)
    return True


def shrink(v: Violation, max_tests: int = 400) -> Violation:
    """ddmin over the conjuncts of the assumption set, then over the
    unrelated conjuncts (I2) and the history (I7)."""
    cs = _conjuncts(v.assum)

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
    violations: List[Violation] = dataclasses.field(default_factory=list)
    seconds: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        return {"source": self.source, "config": self.config, "checked": self.checked,
                "inconclusive": self.inconclusive, "candidates": self.candidates,
                "seconds": round(self.seconds, 1),
                "violations": [v.summary() for v in self.violations]}


def _known(v: Violation) -> Optional[str]:
    if v.inv == "I7":
        return "I7-settings"       # plain attributes, not keyed on the registry epoch
    return None


def run_stream(items: Sequence[Item], config: EngineConfig, invs: Sequence[str], seed: int,
               source: str = "", max_violations: int = 5, shrink_them: bool = True,
               deadline: Optional[float] = None, progress: Optional[Callable[[str], None]] = None,
               i1_rounds: int = 2, slow_limit: float = 3.0) -> InvReport:
    """Every ``Ask`` of ``items`` (events are skipped: the registry is
    configuration, checked by ``python -m harness fuzz --custom``) through
    each checker in ``invs``."""
    rng = random.Random(seed)
    rep = InvReport(source, config.name)
    t0 = time.time()
    asks = [it for it in items if isinstance(it, Ask)]
    seen = set()
    for idx, it in enumerate(asks):
        if deadline is not None and time.time() > deadline:
            break
        key = (it.prop, it.assum)
        if key in seen:
            continue
        seen.add(key)
        t1 = time.time()
        base = fresh_outcome(it.prop, it.assum, config)
        if time.time() - t1 > slow_limit:
            rep.inconclusive["slow"] = rep.inconclusive.get("slow", 0) + 1
            continue              # a query that alone takes seconds would eat the budget
        for inv in invs:
            if len(rep.violations) >= max_violations:
                break
            rounds = i1_rounds if inv == "I1" else 1
            for _ in range(rounds):
                try:
                    if inv == "I7":
                        prefix = asks[max(0, idx - rng.choice([1, 2, 4, 8])):idx]
                        sev, other, var = check_I7(it.prop, it.assum, config, base, rng, None, prefix)
                        b = var["fresh"]
                    else:
                        prefix = []
                        b = base
                        sev, other, var = CHECKERS[inv](it.prop, it.assum, config, base, rng)
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
                rep.candidates[inv] = rep.candidates.get(inv, 0) + 1
                v = Violation(inv, sev, config, it.prop, it.assum, var, b, other, source,
                              prefix=list(prefix))
                if not _guarded(v, v.prop, v.assum, v.variant):
                    rep.inconclusive[inv] = rep.inconclusive.get(inv, 0) + 1
                    continue
                v.known = _known(v)
                if v.known and any(w.known == v.known for w in rep.violations):
                    continue          # one finding covers a known family
                if shrink_them:
                    try:
                        shrink(v)
                    except Exception as e:  # noqa: BLE001
                        if progress:
                            progress(f"shrink failed: {type(e).__name__}: {e}")
                    if not _guarded(v, v.prop, v.assum, v.variant):
                        continue      # gone after shrinking: not reproducible
                rep.violations.append(v)
                if progress:
                    progress("violation: " + v.summary())
    rep.seconds = time.time() - t0
    return rep
