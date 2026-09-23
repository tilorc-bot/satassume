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
are instantiated.  No ``is_*`` property is ever read on a symbolic object.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from ..formula import And, Implies, Not, Or, P
from ..rules import NPRED, PRED_INDEX, PREDICATES, RULE_FREE, RULE_INSTANTIATED, unit_propagate

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
        for ps, cs in rules:
            lits = [(k, PRED_INDEX[p], pos) for k, p, pos in ps]
            lits += [(k, PRED_INDEX[p], not pos) for k, p, pos in cs]
            lits = list(dict.fromkeys(lits))
            if any((k, i, not neg) in lits for k, i, neg in lits):
                continue    # tautology
            npreds = frozenset(i for k, i, _ in lits if k == node)
            # internal literal = 2*base_of_slot + (2*pidx + neg)
            clauses.append((tuple(lits), npreds, tuple((k, 2 * i + (1 if neg else 0)) for k, i, neg in lits)))
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
        facts = list(gen())
        lits = [PRED_INDEX[pred] + 1 if value else -(PRED_INDEX[pred] + 1) for pred, value in facts]
        closed = unit_propagate(RULE_INSTANTIATED, lits)
        if closed is not None:
            facts = [(PREDICATES[abs(l) - 1], l > 0) for l in sorted(closed, key=abs)]
        pat = Pattern([((), ((0, pred, value),)) for pred, value in facts], 0)
        if closed is not None:
            decided = {abs(l) - 1 for l in closed}
            pat.complete = len(decided | RULE_FREE) == NPRED
        _CACHE[key] = pat
    return Compiled((obj,), pat)


def consts_of(args) -> Dict[int, Any]:
    return {k: a for k, a in enumerate(args) if a.is_Atom and a.is_number}


def pattern_key(tag, n: int, consts: Dict[int, Any]):
    return (tag, n, tuple((k, type(c), c) for k, c in sorted(consts.items())))
