"""Helpers shared by the template modules (no SymPy imports here).

Templates describe their rules as *index-based specs*: a literal is
``(k, pred, pos)`` where ``k`` indexes a tuple of objects (the arguments
followed by the node), and a rule is ``(premises, conclusion)`` meaning
``And(premises) -> Or(conclusion)``.  Only these clausal shapes are emitted,
so compilation needs no Tseitin variables.

A spec list depends only on the *pattern* of a node (its class, arity and
which argument positions hold which constants), so it is generated once
per pattern, resolved against the constants (a premise a constant satisfies
is dropped, one it violates kills the rule, a violated conclusion negates the
premises), pruned of subsumed rules, and cached.  Per node only the atoms
are instantiated.  No ``is_*`` property is ever read on a symbolic object,
except the structural ``is_commutative`` (``atoms.structural_commutative``).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from ..formula import And, Implies, Not, Or, P
from ..rules import BASIS, NPRED, RULE_FREE, RULE_INSTANTIATED, expand_clause, unit_propagate

import os as _os
#: template clause pruning (session 2 experiment): "rup" or "rules"
PRUNE_MODE = _os.environ.get("SATASSUME_PRUNE", "rup")

#: The predicate vocabulary templates may emit.
VOCAB = frozenset({
    'algebraic', 'antihermitian', 'commutative', 'complex', 'composite',
    'even', 'extended_negative', 'extended_nonnegative',
    'extended_nonpositive', 'extended_nonzero', 'extended_positive',
    'extended_real', 'finite', 'hermitian', 'imaginary', 'infinite',
    'integer', 'irrational', 'negative', 'negative_infinite', 'noninteger',
    'nonnegative', 'nonpositive', 'nonzero', 'odd', 'polar', 'positive',
    'positive_infinite', 'prime', 'rational', 'real', 'transcendental',
    'zero',
})

#: Sign predicate swapped when multiplying by a negative number.
SIGN_FLIP = {
    'positive': 'negative', 'negative': 'positive',
    'nonnegative': 'nonpositive', 'nonpositive': 'nonnegative',
    'extended_positive': 'extended_negative',
    'extended_negative': 'extended_positive',
    'extended_nonnegative': 'extended_nonpositive',
    'extended_nonpositive': 'extended_nonnegative',
}

Lit = Tuple[int, str, bool]
Rule = Tuple[Tuple[Lit, ...], Tuple[Lit, ...]]


def is_constant(obj) -> bool:
    """True for SymPy atoms whose ``is_*`` properties are static facts.

    Both flags are class attributes on atoms: no assumption query is made.
    """
    return bool(obj.is_Atom and obj.is_number)


def const_key(obj):
    """Cache-key component for a constant (``Float(2.0) == Integer(2)``!)."""
    return (type(obj), obj)


def lits(ks, pred: str, pos: bool = True) -> List[Lit]:
    return [(k, pred, pos) for k in ks]


class Rules:
    """Collects rule specs."""
    __slots__ = ('rules',)

    def __init__(self):
        self.rules: List[Tuple[list, list]] = []

    def rule(self, premises, conclusion) -> None:
        """``And(premises) -> conclusion`` (a literal or a list = ``Or``)."""
        self.rules.append((list(premises),
                           conclusion if isinstance(conclusion, list) else [conclusion]))

    def equiv(self, cond, a: Lit, b: Lit) -> None:
        """``cond -> (a <-> b)`` as two rules."""
        self.rule([*cond, a], b)
        self.rule([*cond, b], a)


def ge2_alternatives(k: int):
    """Premise alternatives meaning ``objs[k]`` is an integer >= 2."""
    return ([(k, 'prime', True)], [(k, 'composite', True)],
            [(k, 'even', True), (k, 'positive', True)])


def const_value(c, pred: str):
    """Static truth value of ``pred`` for the constant ``c`` (None if the
    constant does not decide it).  Beyond the old-system property this
    derives the new-system predicates the old system does not store."""
    v = getattr(c, 'is_' + pred, None)
    if v is None:
        if pred in _SIGNED_INFINITE:
            inf, sign = c.is_infinite, getattr(c, 'is_extended_' + _SIGNED_INFINITE[pred])
            if inf is False or sign is False:
                v = False
            elif inf and sign:
                v = True
        elif pred == 'hermitian':
            v = c.is_real
        elif pred == 'antihermitian':
            z, im = c.is_zero, c.is_imaginary
            v = True if (z or im) else (False if z is False and im is False else None)
    return v


def _resolve_lit(lit: Lit, consts):
    c = consts.get(lit[0])
    if c is not None:
        v = const_value(c, lit[1])
        if v is not None:
            return v is lit[2]
        # A constant decides all it ever will right here (its node would
        # only repeat these static facts), so a rule with an undecidable
        # literal about a constant (``polar(2)``) can never fire: drop it
        # rather than make the constant a node of the engine.
        return None
    return lit


_SIGNED_INFINITE = {'positive_infinite': 'positive', 'negative_infinite': 'negative'}


def resolve(rules, consts: Dict[int, Any]) -> List[Rule]:
    """Resolve constants, then drop duplicate and subsumed rules."""
    keyed = []
    for prem, concl in rules:
        ps = []
        for lit in prem:
            r = _resolve_lit(lit, consts)
            if r is True:
                continue
            if r is False or r is None:
                break
            ps.append(r)
        else:
            cs = []
            for lit in concl:
                r = _resolve_lit(lit, consts)
                if r is True or r is None:
                    break
                if r is not False:
                    cs.append(r)
            else:
                if not cs:
                    # A constant violates the conclusion: the premises
                    # cannot all hold.
                    if not ps:
                        raise ValueError("template asserts a contradiction")
                    cs = [(k, pred, not pos) for k, pred, pos in ps]
                    ps = []
                keyed.append((len(ps), frozenset(ps), tuple(cs), tuple(ps)))
    keyed.sort(key=lambda t: t[0])
    seen: Dict[tuple, list] = {}
    out: List[Rule] = []
    for _, key, cs, ps in keyed:
        lst = seen.setdefault(cs, [])
        if any(k <= key for k in lst):
            continue
        lst.append(key)
        out.append((ps, cs))
    return out


def instantiate(resolved: List[Rule], objs) -> List:
    """Build the formulas of ``resolved`` over the concrete ``objs``."""
    atoms: Dict[Tuple[int, str], P] = {}
    out = []

    def mk(lit):
        key = (lit[0], lit[1])
        a = atoms.get(key)
        if a is None:
            a = atoms[key] = P(lit[1], objs[lit[0]])
        return a if lit[2] else Not(a)

    for ps, cs in resolved:
        c = mk(cs[0]) if len(cs) == 1 else Or(*[mk(l) for l in cs])
        if not ps:
            out.append(c)
        elif len(ps) == 1:
            out.append(Implies(mk(ps[0]), c))
        else:
            out.append(Implies(And(*[mk(l) for l in ps]), c))
    return out


def _unsubsumed(clauses):
    """``clauses`` (tuples of hashable literals) without duplicates and
    without the clauses a shorter one subsumes, shortest first."""
    by_len = sorted(dict.fromkeys(frozenset(c) for c in clauses), key=len)
    kept: List[frozenset] = []
    holding: Dict[Any, list] = {}         # literal -> kept clauses holding it
    out = []
    for c in by_len:
        for l in c:
            for d in holding.get(l, ()):
                if d <= c:
                    break
            else:
                continue
            break
        else:
            kept.append(c)
            for l in c:
                holding.setdefault(l, []).append(c)
            out.append(tuple(sorted(c)))
    return out


def _up(clauses, assign):
    """Unit propagation over ``clauses`` from ``assign`` (var -> bool),
    in place; False on a conflict."""
    changed = True
    while changed:
        changed = False
        for c in clauses:
            free = None
            nfree = 0
            for l in c:
                v = assign.get(abs(l))
                if v is None:
                    nfree += 1
                    free = l
                    if nfree > 1:
                        break
                elif v == (l > 0):
                    break
            else:
                if nfree == 0:
                    return False
                assign[abs(free)] = free > 0
                changed = True
    return True


def _rup_redundant(clauses, slots):
    """Indices of ``clauses`` (tuples of ``(slot, basis index, neg)``) to
    drop: every implication of each (one literal from the negation of the
    others) follows by unit propagation from the clauses kept so far (and,
    with PRUNE_MODE "rupb", the rule block of each slot), so unit
    propagation over the block derives what it derived before.  Longest
    clauses are tried first."""
    def var(k, i):
        return k * NPRED + i + 1
    base = [tuple((abs(l) + k * NPRED) * (1 if l > 0 else -1) for l in c)
            for k in slots for c in RULE_INSTANTIATED
            if PRUNE_MODE != "rupn" or k == slots[-1]] if PRUNE_MODE in ("rupb", "rupc", "rupn") else []
    own = [tuple(-var(k, i) if neg else var(k, i) for k, i, neg in c) for c in clauses]
    alive = [True] * len(own)
    drop = set()
    for j in sorted(range(len(own)), key=lambda j: -len(own[j])):
        c = own[j]
        if len(c) < 2:
            continue
        others = base + [d for t, d in enumerate(own) if alive[t] and t != j]
        ok = True
        if PRUNE_MODE in ("rupc", "rupo", "rupn"):
            ok = not _up(others, {abs(m): m < 0 for m in c})
            c = ()
        for l in c:
            assign = {abs(m): m < 0 for m in c if m != l}
            if _up(others, assign) and assign.get(abs(l)) != (l > 0):
                ok = False
                break
        if ok:
            alive[j] = False
            drop.add(j)
    return drop


class Pattern:
    """The resolved rules of one template pattern, also as clauses in
    *slot space*: a literal is ``(k, pidx, neg)`` for predicate index
    ``pidx`` of the object in slot ``k``.  Slots below ``node`` are the
    direct arguments, slot ``node`` is the node, slots above are derived
    nodes (``2*e``, ``x - 1``, ...).

    ``complete`` is set on a unit pattern whose facts, closed under the rule
    base, decide every predicate the rule base mentions: the engine then
    asserts the closed units and skips the rule base for the node."""
    __slots__ = ('rules', 'node', 'clauses', 'used', 'child_preds', 'complete')

    def __init__(self, rules: List[Rule], node: int):
        self.rules = rules
        self.node = node
        self.complete = False
        clauses = []
        used = set()
        child_preds: Dict[int, set] = {}
        expanded = []
        origin = {}
        for r, (ps, cs) in enumerate(rules):
            # over the basis: a derived predicate is its definition
            # (rules.expand_clause), so one rule may give several clauses
            for lits in expand_clause([(k, p, not pos) for k, p, pos in ps]
                                      + [(k, p, pos) for k, p, pos in cs]):
                # (slot, basis index, neg)
                c = tuple((k, i, not pos) for k, i, pos in lits)
                expanded.append(c)
                origin.setdefault(frozenset(c), r)
        kept = _unsubsumed(expanded)
        if PRUNE_MODE in ("rup", "rupb", "rupc", "rupo", "rupn") and len(kept) > 1:
            slots = sorted({k for c in kept for k, _, _ in c})
            if PRUNE_MODE == "rupn":
                slots = [k for k in slots if k != node] + [node]
            drop = _rup_redundant(kept, slots)
            kept = [c for j, c in enumerate(kept) if j not in drop]
        # the rules that give a kept clause: the others are implied by them
        need = {origin[frozenset(c)] for c in kept}
        self.rules = rules = [r for j, r in enumerate(rules) if j in need]
        for lits in kept:
            if True:
                npreds = frozenset(i for k, i, _ in lits if k == node)
                # internal literal = 2*base_of_slot + (2*pidx + neg)
                clauses.append((lits, npreds, tuple((k, 2 * i + (1 if neg else 0)) for k, i, neg in lits)))
                for k, i, _ in lits:
                    used.add(k)
                    if k != node:
                        child_preds.setdefault(k, set()).add(i)
        self.clauses = clauses
        self.used = tuple(sorted(used))
        self.child_preds = {k: frozenset(v) for k, v in child_preds.items()}


class Compiled:
    """A pattern applied to concrete objects: what a template hands the
    engine.  ``instantiate(c.pattern.rules, c.objs)`` gives the formulas."""
    __slots__ = ('objs', 'pattern')

    def __init__(self, objs, pattern: Pattern):
        self.objs = objs
        self.pattern = pattern

    def formulas(self) -> List:
        return instantiate(self.pattern.rules, self.objs)


#: compiled patterns by the key the template passes to :func:`facts` or
#: :func:`units`.  Keyed on that key and the registry epoch: a key names
#: one generator only among the templates registered at a time, and
#: ``TemplateRegistry.register`` (the only way the set of templates
#: changes) empties this table before bumping the epoch, so a later
#: template that reuses a key never gets an earlier template's pattern.
#: Registered with ``satassume.memos.PROCESS`` as ``"epoch"``.
_CACHE: Dict[Any, Pattern] = {}
MAX_CACHE = 4096


def facts(key, gen: Callable[[], list], consts: Dict[int, Any], objs, node: int) -> Compiled:
    """The (cached) resolved rules of ``key`` applied to ``objs``; slot
    ``node`` holds the node itself."""
    pat = _CACHE.get(key)
    if pat is None:
        if len(_CACHE) >= MAX_CACHE:
            _CACHE.clear()
        pat = _CACHE[key] = Pattern(resolve(gen(), consts), node)
    return Compiled(objs, pat)


def units(key, gen: Callable[[], list], obj) -> Compiled:
    """Unit facts about one object: ``gen()`` returns ``(pred, value)``
    pairs; the pattern is cached under ``key``.  The facts are closed under
    the rule base (unit propagation); when the closure decides every
    predicate the rule base mentions the pattern is ``complete``."""
    pat = _CACHE.get(key)
    if pat is None:
        if len(_CACHE) >= MAX_CACHE:
            _CACHE.clear()
        # the facts over the basis: a derived predicate's value is a
        # conjunction of basis units, or (``antihermitian``) one clause
        lits, rest = [], []
        for pred, value in gen():
            for c in expand_clause([(0, pred, value)]):
                if len(c) == 1:
                    lits.append(c[0][1] + 1 if c[0][2] else -(c[0][1] + 1))
                else:
                    rest.append(((), tuple((0, BASIS[i], pos) for _, i, pos in c)))
        closed = unit_propagate(RULE_INSTANTIATED, lits)
        if closed is not None:
            lits = sorted(closed, key=abs)
        if rest:
            # a clause the units satisfy is dropped; a false literal leaves
            # a clause (``antihermitian(c)`` of a non-zero ``c`` is
            # ``imaginary(c)``), a new unit is closed again
            units = set(lits)
            while True:
                keep, new = [], []
                for ps, cs in rest:
                    cl = [(k, p, pos) for k, p, pos in cs
                          if (BASIS.index(p) + 1 if not pos else -(BASIS.index(p) + 1)) not in units]
                    if any((BASIS.index(p) + 1 if pos else -(BASIS.index(p) + 1)) in units for k, p, pos in cl):
                        continue
                    if len(cl) == 1 and closed is not None:
                        new.append(BASIS.index(cl[0][1]) + 1 if cl[0][2] else -(BASIS.index(cl[0][1]) + 1))
                    else:
                        keep.append((ps, tuple(cl)))
                rest = keep
                if not new:
                    break
                closed = unit_propagate(RULE_INSTANTIATED, sorted(units) + new)
                if closed is None:
                    break
                lits = sorted(closed, key=abs)
                units = set(lits)
        facts = [(BASIS[abs(l) - 1], l > 0) for l in lits]
        pat = Pattern([((), ((0, pred, value),)) for pred, value in facts] + rest, 0)
        if closed is not None:
            decided = {abs(l) - 1 for l in closed}
            pat.complete = len(decided | RULE_FREE) == NPRED
        _CACHE[key] = pat
    return Compiled((obj,), pat)


def consts_of(args) -> Dict[int, Any]:
    return {k: a for k, a in enumerate(args) if a.is_Atom and a.is_number}


def pattern_key(tag, n: int, consts: Dict[int, Any]):
    return (tag, n, tuple((k, type(c), c) for k, c in sorted(consts.items())))
