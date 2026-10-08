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
from ..rules import BASIS, BASIS_OF, NPRED, RULE_FREE, SHARED, SHARED_INDEX, RULE_INSTANTIATED, cnf_of, expand_clause, unit_propagate

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
    without the clauses a shorter one subsumes, shortest first.

    Each kept clause is indexed under one literal only, its rarest, and is
    a bit mask over the literals, so a candidate checks every kept clause
    at most once, with one mask operation (wide Add/Mul patterns have
    hundreds of clauses of 100+ literals)."""
    by_len = sorted(dict.fromkeys(frozenset(c) for c in clauses), key=len)
    bit: Dict[Any, int] = {}
    count: Dict[Any, int] = {}
    for c in by_len:
        for l in c:
            if l not in bit:
                bit[l] = 1 << len(bit)
            count[l] = count.get(l, 0) + 1
    index: Dict[Any, list] = {}           # literal -> masks of kept clauses
    out = []
    for c in by_len:
        m = 0
        for l in c:
            m |= bit[l]
        rest = ~m
        for l in c:
            if any(not d & rest for d in index.get(l, ())):
                break
        else:
            if c:
                index.setdefault(min(c, key=count.__getitem__), []).append(m)
            else:
                index = {l: [0] for l in bit}
            out.append(tuple(sorted(c)))
    return out


def _rup_candidates(cls):
    """Bit ``j`` of the result is set if unit propagation over all clauses
    of ``cls`` but ``j`` (lists of literals ``2*v + neg``), from the negation
    of clause ``j``, reaches a conflict.  All tests run at once, bit-sliced:
    ``F[l]``/``T[l]`` are the tests in which literal ``l`` is false/true, and
    after the first pass only the clauses of literals that changed are
    looked at again."""
    nl = 2 + max(max(c) for c in cls) // 2 * 2
    F = [0] * nl
    T = [0] * nl
    occ = [[] for _ in range(nl)]
    for j, c in enumerate(cls):
        b = 1 << j
        for l in c:
            F[l] |= b
            T[l ^ 1] |= b
            occ[l].append(j)
            occ[l ^ 1].append(j)
    full = (1 << len(cls)) - 1
    done = 0
    todo = range(len(cls))
    while todo:
        dirty = set()
        for j in todo:
            c = cls[j]
            sat = one = two = 0
            for l in c:
                sat |= T[l]
                nf = ~F[l]
                two |= one & nf
                one |= nf
            act = full & ~(done | sat | (1 << j))
            if not act:
                continue
            done |= act & ~one              # all literals false: conflict
            unit = act & one & ~two         # one literal not false: unit
            if unit:
                for l in c:
                    u = unit & ~(F[l] | T[l])
                    if u:
                        T[l] |= u
                        F[l ^ 1] |= u
                        dirty.add(l)
        todo = sorted({t for l in dirty for t in occ[l]})
    return done


def _rup_redundant(clauses):
    """Indices of ``clauses`` (tuples of ``(slot, basis index, neg)``) that
    are implied by the others kept: unit propagation over the kept clauses
    from the negation of the clause reaches a conflict (RUP).  Longest
    clauses are tried first, so short clauses are kept.

    Most clauses are not implied, and a pattern is built on first use (cold
    time), so a cheap filter comes first: unit clauses (never tested, never
    dropped) are applied to the others once, and :func:`_rup_candidates`
    runs every test at once over all clauses, an over-approximation of the
    sequential test (more clauses only propagate more).  Only its
    candidates get the exact test, in which clauses dropped before are left
    out: bit masks over literals (bit ``2*v`` for literal ``v``, ``2*v + 1``
    for its negation), one mask operation per clause and pass."""
    var: Dict[Any, int] = {}
    cls = [[2 * var.setdefault((k, i), len(var)) + neg for k, i, neg in c]
           for c in clauses]
    units = {c[0] for c in cls if len(c) == 1}
    # contradicting units: every clause is implied
    cand = 0 if units.isdisjoint([u ^ 1 for u in units]) else (1 << len(cls)) - 1
    idx = []
    red = []
    for j, c in enumerate(cls):
        if len(c) < 2:
            continue
        r = [l for l in c if l ^ 1 not in units]
        if not r:
            # the units falsify a clause: every clause is implied
            cand = (1 << len(cls)) - 1
            break
        if not units.isdisjoint(r):
            # true under the units (subsumed): conflict right away
            cand |= 1 << j
            continue
        idx.append(j)
        red.append(r)
    if red and cand != (1 << len(cls)) - 1:
        got = _rup_candidates(red)
        for b, j in enumerate(idx):
            if got >> b & 1:
                cand |= 1 << j
    drop = set()
    if not cand:
        return drop
    masks = []
    comps = []
    for c in cls:
        m = n = 0
        for l in c:
            m |= 1 << l
            n |= 1 << (l ^ 1)
        masks.append(m)
        comps.append(n)
    alive = [True] * len(masks)
    for j in sorted(range(len(masks)), key=lambda j: -len(clauses[j])):
        if len(clauses[j]) < 2 or not cand >> j & 1:
            continue
        false, true = masks[j], comps[j]
        live = [masks[t] for t in range(len(masks)) if alive[t] and t != j
                and not masks[t] & true]
        conflict = False
        while live and not conflict:
            changed = False
            for d in live:
                if d & true:
                    continue
                rem = d & ~false
                if not rem:
                    conflict = True
                    break
                if not rem & (rem - 1):           # unit: one literal left
                    true |= rem
                    p = rem.bit_length() - 1
                    false |= rem << 1 if p % 2 == 0 else rem >> 1
                    changed = True
            if not changed:
                break
            live = [d for d in live if not d & true]
        if conflict:
            alive[j] = False
            drop.add(j)
    return drop


#: most clauses one rule may expand to in a pattern (see ``Pattern.wide``)
MAX_EXPAND = 16

#: fewest clauses a rule must expand to for the engine to get it with one
#: shared definitional variable per distributing literal instead
#: (``Pattern.eclauses``)
MIN_SHARED = 8



def _shared_clauses(lits) -> List[Tuple[Tuple[int, int, bool], ...]]:
    """``expand_clause`` with each distributing literal kept as the one
    literal ``(slot, NPRED + j, True)`` of its shared variable
    (``rules.SHARED[j]``)."""
    out: List[Tuple[Tuple[int, int, bool], ...]] = [()]
    for k, pred, pos in lits:
        cnf = cnf_of(pred, pos)
        if len(cnf) > 1:
            ext = ((k, NPRED + SHARED_INDEX[(pred, pos)], True),)
            out = [c + ext for c in out]
        else:
            out = [c + tuple((k, abs(l) - 1, l > 0) for l in cl) for c in out for cl in cnf]
    res = []
    for c in out:
        c = tuple(dict.fromkeys(c))
        cs = set(c)
        if not any((k, i, not p) in cs for k, i, p in c):
            res.append(c)
    return res

#: most clauses a pattern is pruned over (:func:`_rup_redundant` is
#: quadratic; wide Add/Mul patterns have hundreds and lose next to nothing)
MAX_RUP = 320


class Pattern:
    """The resolved rules of one template pattern, also as clauses in
    *slot space*: a literal is ``(k, pidx, neg)`` for predicate index
    ``pidx`` of the object in slot ``k``.  Slots below ``node`` are the
    direct arguments, slot ``node`` is the node, slots above are derived
    nodes (``2*e``, ``x - 1``, ...).

    ``complete`` is set on a unit pattern whose facts, closed under the rule
    base, decide every predicate the rule base mentions: the engine then
    asserts the closed units and skips the rule base for the node."""
    __slots__ = ('rules', 'node', 'clauses', 'used', 'child_preds', 'complete', 'wide', 'eclauses')

    def __init__(self, rules: List[Rule], node: int):
        self.rules = rules
        self.node = node
        self.complete = False
        clauses = []
        used = set()
        child_preds: Dict[int, set] = {}
        expanded = []
        #: rules whose clauses over the basis would be too many (a wide
        #: Add's ``~positive_infinite(x_i)`` premises: 2**n clauses); they
        #: are handed over as formulas (``Compiled.wide_formulas``), which
        #: ``compile_formula`` encodes with Tseitin variables past
        #: ``compile.MAX_DISTRIBUTE``
        self.wide = wide = []
        need = set()
        origin = {}
        big: Dict[int, list] = {}     # rule -> its clauses, if MIN_SHARED or more
        small = set()                 # clauses of the other rules
        for r, (ps, cs) in enumerate(rules):
            n = 1
            for k, p, pos in ps:
                n *= len(cnf_of(p, not pos))
            for k, p, pos in cs:
                n *= len(cnf_of(p, pos))
            if n > MAX_EXPAND:
                wide.append((ps, cs))
                need.add(r)
                continue
            # over the basis: a derived predicate is its definition
            # (rules.expand_clause), so one rule may give several clauses
            for lits in expand_clause([(k, p, not pos) for k, p, pos in ps]
                                      + [(k, p, pos) for k, p, pos in cs]):
                # (slot, basis index, neg)
                c = tuple((k, i, not pos) for k, i, pos in lits)
                expanded.append(c)
                origin.setdefault(frozenset(c), r)
                if n >= MIN_SHARED:
                    big.setdefault(r, []).append(frozenset(c))
                else:
                    small.add(frozenset(c))
        kept = _unsubsumed(expanded)
        # drop clauses the other kept clauses imply (RUP)
        if 1 < len(kept) <= MAX_RUP:
            drop = _rup_redundant(kept)
            kept = [c for j, c in enumerate(kept) if j not in drop]
        eclauses = None
        if big:
            # the engine's clauses: a rule that expands to MIN_SHARED or more
            # clauses, with one shared literal per distributing literal (see
            # SHARED; ``engine.Session._dvar`` gives each a definitional
            # variable per node with only the variable -> definition
            # direction, which propagates as the expanded clauses do)
            keptset = set(map(frozenset, kept))
            ek = [c for c in kept if frozenset(c) in small]
            for r, fcs in big.items():
                if any(fc in keptset and fc not in small for fc in fcs):
                    ps, cs = rules[r]
                    ek.extend(tuple((k, i, not pos) for k, i, pos in lits) for lits in _shared_clauses(
                        [(k, p, not pos) for k, p, pos in ps] + [(k, p, pos) for k, p, pos in cs]))
            eclauses = []
            for lits in _unsubsumed(ek):
                npreds = set()
                li = []
                for k, i, neg in lits:
                    if i < NPRED:
                        li.append((k, 2 * i + (1 if neg else 0)))
                        if k == node:
                            npreds.add(i)
                    else:
                        # a shared literal: offset -1 - j (never negated)
                        li.append((k, NPRED - 1 - i))
                        if k == node:
                            npreds.update(BASIS_OF[SHARED[i - NPRED][0]])
                eclauses.append((lits, frozenset(npreds), tuple(li)))
        # the rules that give a kept clause: the others are implied by them
        need.update(origin[frozenset(c)] for c in kept)
        self.rules = rules = [r for j, r in enumerate(rules) if j in need]
        for lits in kept:
            npreds = frozenset(i for k, i, _ in lits if k == node)
            # internal literal = 2*base_of_slot + (2*pidx + neg)
            clauses.append((lits, npreds, tuple((k, 2 * i + (1 if neg else 0)) for k, i, neg in lits)))
            for k, i, _ in lits:
                used.add(k)
                if k != node:
                    child_preds.setdefault(k, set()).add(i)
        self.clauses = clauses
        #: the clauses the engine emits: ``clauses``, or with shared
        #: literals (offset ``-1 - j`` for SHARED[j]; see above)
        self.eclauses = clauses if eclauses is None else eclauses
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

    def wide_formulas(self) -> List:
        """The formulas of the pattern's wide rules (``Pattern.wide``),
        which its clauses leave out."""
        return instantiate(self.pattern.wide, self.objs)


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
