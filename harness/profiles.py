"""Stream profiles: query sequences shaped after the engine's state.

The base generator (``QueryGen.stream``) draws every assumption set and
every proposition independently.  That is good coverage of the *input*
space and poor coverage of the *state* space: a history-dependent answer
needs two or three coordinated queries (the same node under two related
sets, a conjunct asked back as a proposition, a probe of a subterm after a
big parent was visited), and independent draws reach such shapes with
vanishing probability.  Each profile here builds one of these shapes on
purpose; ``random_stream(..., profile=NAME)`` selects it.

``related``
    A pool of conjuncts; assumption sets are random subsets of it, so sets
    share components, nest, and some are single conjuncts of others.
    Propositions are the conjuncts themselves (and their negations),
    sibling predicates on the nodes the conjuncts mention, probes of their
    subterms, and context-free probes of the same.  Aims at the relevance
    layer (per-component consistency memo, part sessions shared between
    sets, answer memo keyed by the part) and at fact-cache flows between
    a set's nodes and its subterms.

``focus``
    One or two symbols, a small pool of terms, most queries under one set:
    long sessions (hundreds of queries), so the solver's model reuse, held
    levels, learnt clauses and the accumulated demand sets are exercised;
    compound propositions force searches between propagation-decided ones.

``deep``
    Large expressions (sums and products of 6-30 terms, nested), whose
    cones exceed the default discovery and escalation budgets (400);
    propositions about the big terms and about their subterms, most under
    one set (``session_limit`` is a no-op since issue #97).

``relational``
    Relation-heavy sets sharing conjuncts (equalities between symbols,
    terms and numbers, order chains), unary propositions about the sides
    and about applications of them (EUF congruence, predicate transfer),
    ``Implies(eq, unary)`` propositions, relation propositions under unary
    sets (links added after the session exists).

``declared``
    The alphabet is symbols declared with every kind of fact the vocabulary
    has (zero, infinite, prime, composite, irrational, transcendental,
    noninteger, polar, negated facts such as ``integer=False``, ...) plus
    same-name variants (``x``, ``x`` real, ``x`` positive); the base stream
    over it.

``mixed``
    One of the above per seed.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from sympy import Function, Q, Rational, S, Symbol, pi, sqrt, Float, oo
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

from .checker import Ask, Item
from .lazy import sorted_atoms as _sorted_atoms

DECLARED: List[Symbol] = [
    Symbol("z0", zero=True), Symbol("inf", infinite=True), Symbol("pr", prime=True),
    Symbol("cm", composite=True), Symbol("ir", irrational=True), Symbol("al", algebraic=True),
    Symbol("tr", transcendental=True), Symbol("ni", noninteger=True), Symbol("fi", finite=True),
    Symbol("he", hermitian=True), Symbol("ah", antihermitian=True), Symbol("np", nonpositive=True),
    Symbol("ep", extended_positive=True), Symbol("en", extended_negative=True),
    Symbol("ez", extended_nonzero=True), Symbol("nI", integer=False), Symbol("nR", real=False),
    Symbol("nF", finite=False), Symbol("nZ", zero=False), Symbol("nP", positive=False),
    Symbol("nC", complex=False), Symbol("nA", algebraic=False),
    Symbol("ev", even=True, negative=True), Symbol("op", odd=True, positive=True),
    Symbol("rn", rational=True, negative=True), Symbol("po", polar=True),
    Symbol("pinf", positive_infinite=True), Symbol("ninf", negative_infinite=True),
    Symbol("er", extended_real=True, finite=False), Symbol("Af", commutative=False, finite=True),
    Symbol("A", commutative=False),
    # same-name variants: distinct objects with one name
    Symbol("x"), Symbol("x", real=True), Symbol("x", positive=True), Symbol("x", integer=True),
    Symbol("y"), Symbol("y", real=True), Symbol("y", zero=True),
]

f, g = Function("f"), Function("g")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def subterms(booleans, max_n: int = 40) -> List[Any]:
    """Every scalar subexpression of the predicate arguments and relation
    sides of the Booleans, deepest last, numbers left out."""
    from sympy import Expr, preorder_traversal
    out: Dict[Any, None] = {}
    for b in booleans:
        if b is True or b is False:
            continue
        exprs: List[Any] = []
        for a in _sorted_atoms(b, AppliedPredicate):
            exprs.extend(x for x in a.arguments if isinstance(x, Expr))
        for r in _sorted_atoms(b, Relational):
            exprs.extend((r.lhs, r.rhs))
        for e in exprs:
            for s in preorder_traversal(e):
                if isinstance(s, Expr) and not s.is_number:
                    out[s] = None
    return list(out)[:max_n]


def conjuncts_of(a) -> List[Any]:
    if a is True or a is False:
        return []
    return list(a.args) if isinstance(a, And) else [a]


class Runs:
    """Pick the current assumption set with runs (session reuse) and
    switches (LRU order), as the base stream does."""

    def __init__(self, gen, sets, stay: float = 0.7, p_true: float = 0.05):
        self.gen, self.sets, self.stay, self.p_true = gen, sets, stay, p_true
        self.cur = 0

    def next(self):
        d = self.gen.d
        if not d.chance(self.stay):
            self.cur = d.integer(0, len(self.sets) - 1)
        if d.chance(self.p_true):
            return True
        return self.sets[self.cur]

    def current(self):
        return self.sets[self.cur]


def _maybe_repeat(gen, items: List[Item], p: float = 0.06) -> Optional[Ask]:
    if items and gen.d.chance(p):
        asks = [it for it in items if isinstance(it, Ask)]
        if asks:
            return gen.d.choice(asks)
    return None


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------

def stream_related(gen, n: int, nsets: int) -> List[Item]:
    d = gen.d
    k = max(nsets + 2, 4)
    conj = [gen.conjunct() for _ in range(k)]
    sets: List[Any] = []
    for _ in range(nsets):
        cs = d.sample(conj, d.integer(1, min(3, k)))
        sets.append(And(*cs) if len(cs) > 1 else cs[0])
    sets.append(d.choice(conj))                          # a single conjunct
    sets.append(And(*conj[:min(k, 3)]))                  # a union
    nodes = subterms(conj) or [gen.symbol()]
    runs = Runs(gen, sets)
    items: List[Item] = []
    for _ in range(n):
        rep = _maybe_repeat(gen, items)
        if rep is not None:
            items.append(rep)
            continue
        a = runs.next()
        roll = d.integer(0, 99)
        if roll < 30:
            prop = gen.proposition()
        elif roll < 48:
            src = runs.current() if d.chance(0.6) else d.choice(sets)
            cs = conjuncts_of(src) or [gen.literal()]
            prop = d.choice(cs)
            if d.chance(0.3):
                prop = Not(prop)
        elif roll < 78:
            prop = gen.predicate_on(d.choice(nodes))
            if d.chance(0.2):
                prop = Not(prop)
        elif roll < 90:
            p1, p2 = gen.predicate_on(d.choice(nodes)), gen.predicate_on(d.choice(nodes))
            prop = d.choice((Or, Implies, Equivalent))(p1, p2)
        else:
            prop = gen.predicate_on(d.choice(nodes))
            a = True                                     # a context-free probe
        items.append(Ask(prop, a))
    return items


def stream_focus(gen, n: int, nsets: int) -> List[Item]:
    d = gen.d
    gen.syms = gen.syms[: d.integer(1, 2)]
    pool = []
    for _ in range(8):
        t = gen.term(2)
        pool.append(t)
    pool = list(dict.fromkeys(pool))
    nodes = subterms([Q.real(t) for t in pool]) or list(pool)
    sets: List[Any] = []
    for _ in range(max(1, nsets)):
        cs = [gen.literal_on(d.choice(nodes)) for _ in range(d.integer(1, 3))]
        sets.append(And(*cs) if len(cs) > 1 else cs[0])
    items: List[Item] = []
    for _ in range(n):
        rep = _maybe_repeat(gen, items, 0.08)
        if rep is not None:
            items.append(rep)
            continue
        a = sets[0] if d.chance(0.75) else d.choice(sets)
        if d.chance(0.06):
            a = True
        roll = d.integer(0, 99)
        if roll < 55:
            prop = gen.literal_on(d.choice(nodes))
        elif roll < 80:
            p1, p2 = gen.literal_on(d.choice(nodes)), gen.literal_on(d.choice(nodes))
            prop = d.choice((Or, Implies, Equivalent, And))(p1, p2)
        elif roll < 92 and gen.o.relations:
            prop = gen.relation_atom()
        else:
            prop = gen.proposition()
        items.append(Ask(prop, a))
    return items


def stream_deep(gen, n: int, nsets: int) -> List[Item]:
    d = gen.d
    from sympy import Add, Mul

    def big(depth: int = 1):
        m = d.integer(6, 30)
        parts = [gen.term(2) for _ in range(m)]
        if depth > 0 and d.chance(0.5):
            parts.append(big(depth - 1))
        try:
            e = (Add if d.chance(0.6) else Mul)(*parts)
            roll = d.integer(0, 9)
            if roll < 2:
                e = 1 / e
            elif roll < 4:
                e = e ** d.choice((S(2), S.Half, S(-2), Rational(1, 3)))
            elif roll < 5:
                e = d.choice(gen_unary_funcs())(e)
        except (TypeError, ValueError, ZeroDivisionError, RecursionError):
            e = gen.term(2)
        return e

    bigs = [big() for _ in range(d.integer(2, 4))]
    subs = subterms([Q.real(b) for b in bigs], max_n=80) or list(bigs)
    sets: List[Any] = []
    for _ in range(max(1, nsets)):
        cs = [gen.literal_on(d.choice(subs)) for _ in range(d.integer(1, 3))]
        sets.append(And(*cs) if len(cs) > 1 else cs[0])
    items: List[Item] = []
    for _ in range(n):
        rep = _maybe_repeat(gen, items)
        if rep is not None:
            items.append(rep)
            continue
        a = sets[0] if d.chance(0.7) else d.choice(sets)
        if d.chance(0.08):
            a = True
        roll = d.integer(0, 99)
        if roll < 45:
            prop = gen.literal_on(d.choice(bigs))
        elif roll < 80:
            prop = gen.literal_on(d.choice(subs))
        else:
            prop = d.choice((Or, Implies))(gen.literal_on(d.choice(bigs)), gen.literal_on(d.choice(subs)))
        items.append(Ask(prop, a))
    return items


def gen_unary_funcs():
    from .generators import UNARY_FUNCS
    return UNARY_FUNCS


def stream_relational(gen, n: int, nsets: int) -> List[Item]:
    d = gen.d
    syms = gen.syms
    consts = [S.Zero, S.One, S(2), S.Half, S(-1), pi, sqrt(2), Float("0.5"), oo, Rational(-1, 3)]

    def side():
        r = d.integer(0, 9)
        s = d.choice(syms)
        if r < 4:
            return s
        if r < 5:
            return s + 1
        if r < 6:
            return 2 * s
        if r < 7:
            return d.choice((f, g))(s)
        if r < 8:
            return s * d.choice(syms)
        return gen.term(2)

    def rel_conjunct():
        r = d.integer(0, 9)
        if r < 4:
            a, b = side(), (d.choice(consts) if d.chance(0.45) else side())
            atom = Q.eq(a, b) if d.chance(0.6) else Q.ne(a, b)
        else:
            a, b = side(), (d.choice(consts) if d.chance(0.4) else side())
            atom = d.choice((Q.lt, Q.le, Q.gt, Q.ge))(a, b)
        return Not(atom) if d.chance(0.15) else atom

    k = max(nsets + 2, 4)
    conj = [rel_conjunct() if d.chance(0.6) else gen.literal_on(side()) for _ in range(k)]
    sets: List[Any] = []
    for _ in range(nsets):
        cs = d.sample(conj, d.integer(1, min(3, k)))
        sets.append(And(*cs) if len(cs) > 1 else cs[0])
    sets.append(d.choice(conj))
    # a unary-only set, for relation propositions that arrive after the session
    unary = [c for c in conj if not c.atoms(Relational) and not any(
        str(p.function.name) in ("eq", "ne", "lt", "le", "gt", "ge") for p in c.atoms(AppliedPredicate))]
    if unary:
        sets.append(And(*unary) if len(unary) > 1 else unary[0])
    nodes = subterms(conj) or list(syms)
    runs = Runs(gen, sets)
    items: List[Item] = []
    for _ in range(n):
        rep = _maybe_repeat(gen, items)
        if rep is not None:
            items.append(rep)
            continue
        a = runs.next()
        roll = d.integer(0, 99)
        if roll < 35:
            prop = gen.predicate_on(d.choice(nodes))
        elif roll < 50:
            prop = gen.predicate_on(d.choice((f, g))(d.choice(nodes)))
        elif roll < 65:
            prop = rel_conjunct()
        elif roll < 80:
            prop = Implies(rel_conjunct(), gen.predicate_on(d.choice(nodes)))
        elif roll < 90:
            src = runs.current() if d.chance(0.6) else d.choice(sets)
            cs = conjuncts_of(src) or [gen.literal()]
            prop = d.choice(cs)
            if d.chance(0.3):
                prop = Not(prop)
        else:
            prop = gen.proposition()
        items.append(Ask(prop, a))
    return items


def stream_declared(gen, n: int, nsets: int) -> List[Item]:
    from .generators import SYMBOLS
    d = gen.d
    k = d.integer(3, 5)
    gen.syms = d.sample(DECLARED + SYMBOLS[:6], k)
    return gen.stream(n, nsets)


def stream_registry(gen, n: int, nsets: int) -> List[Item]:
    """Registration events straddled by the *same* queries.  For each block
    a registration ``r`` is chosen; a batch of queries about the objects
    ``r`` affects (applications ``f(s)``, symbols, small integers, custom
    atoms, context-free and under sets that mention them) is asked, then
    ``register(r)``, the batch again, then ``unregister(r)`` and the batch
    once more, with a few other registrations switched meanwhile and fresh
    queries mixed in.  Sessions, caches and memos persist across the
    events; the reference is computed under the registrations in force."""
    from . import registry as reg
    from .checker import Event
    d = gen.d
    syms = gen.syms
    ids = sorted(reg.REGISTRATIONS)
    apps = [d.choice((f, g))(s) for s in syms] + [f(d.choice(syms)) + 1, exp_(f(d.choice(syms)))]
    ints = [S(31), S(7), S(10), S(3)]
    custom_names = list(reg.CUSTOM_PREDICATES)

    def custom_atom():
        from .sympy_io import custom_predicate
        name = d.choice(custom_names)
        if name == "hmersenne":
            return custom_predicate(name)(d.choice(ints))
        return custom_predicate(name)(d.choice(syms))

    def poly_atom():
        from .sympy_io import custom_predicate
        a, b = d.choice(syms + apps), d.choice(syms + apps)
        return custom_predicate("hsame", 2)(a, a if d.chance(0.4) else b)

    sets: List[Any] = []
    for _ in range(max(2, nsets)):
        cs = []
        for _ in range(d.integer(1, 3)):
            r = d.integer(0, 9)
            if r < 4:
                cs.append(gen.literal_on(d.choice(syms)))
            elif r < 6:
                cs.append(custom_atom())
            elif r < 8:
                cs.append(gen.literal_on(d.choice(apps)))
            else:
                cs.append(poly_atom())
        sets.append(And(*cs) if len(cs) > 1 else cs[0])

    def batch(k: int) -> List[Ask]:
        out = []
        for _ in range(k):
            r = d.integer(0, 9)
            if r < 4:
                prop = gen.predicate_on(d.choice(apps))
            elif r < 6:
                prop = custom_atom()
            elif r < 7:
                prop = poly_atom()
            elif r < 9:
                prop = gen.predicate_on(d.choice(syms))
            else:
                prop = gen.proposition()
            a = True if d.chance(0.4) else d.choice(sets)
            out.append(Ask(prop, a))
        return out

    items: List[Item] = []
    active: List[str] = []
    while len(items) < n:
        rid = d.choice(ids)
        b = batch(d.integer(4, 10))
        items.extend(b)
        if rid in active:
            items.append(Event("unregister", rid))
            active.remove(rid)
        else:
            items.append(Event("register", rid))
            active.append(rid)
        items.extend(b)
        items.extend(batch(d.integer(0, 4)))
        if d.chance(0.5) and active:
            other = d.choice(active)
            items.append(Event("unregister", other))
            active.remove(other)
            items.extend(b)
    for rid in active:                                   # leave the registry as found
        items.append(Event("unregister", rid))
    return items[: n + 8]


def exp_(e):
    from sympy import exp
    return exp(e)


PROFILES: Dict[str, Callable] = {
    "related": stream_related,
    "focus": stream_focus,
    "deep": stream_deep,
    "relational": stream_relational,
    "declared": stream_declared,
    "registry": stream_registry,
}


def stream_mixed(gen, n: int, nsets: int) -> List[Item]:
    name = gen.d.choice(sorted(k for k in PROFILES if k != "mixed"))
    return PROFILES[name](gen, n, nsets)




# --------------------------------------------------------------------------
# lazily switched-on capabilities (harness/lazy.py): trigger + observer
# --------------------------------------------------------------------------

REAL_SYMBOLS: List[Symbol] = [
    Symbol("y", real=True), Symbol("n", integer=True), Symbol("p", positive=True),
    Symbol("q", nonnegative=True), Symbol("k", integer=True, positive=True),
    Symbol("m", negative=True), Symbol("e", extended_real=True), Symbol("o", odd=True),
    Symbol("r", rational=True), Symbol("t", real=True, nonzero=True),
    Symbol("j", integer=True, even=True), Symbol("x"), Symbol("z"),
]


def _add_literal(cs: List[Any], lit) -> None:
    """Append ``lit`` unless it or its negation is already there (a set
    that is inconsistent by syntax alone only raises)."""
    neg = lit.args[0] if isinstance(lit, Not) else Not(lit)
    if lit not in cs and neg not in cs:
        cs.append(lit)


def _lazy_syms(gen, d):
    """Mostly real-declared symbols (LRA's guard needs ``real``), one or
    two plain ones sometimes."""
    k = d.integer(1, 3)
    syms = d.sample(REAL_SYMBOLS[:-2], k)
    if d.chance(0.3):
        syms.append(d.choice(REAL_SYMBOLS[-2:]))
    gen.syms = syms
    return syms


def stream_links(gen, n: int, nsets: int) -> List[Item]:
    """Relation glue.  Unary-only sets of order predicates on linear forms
    over real symbols (and opaque nonlinear terms, and constants with
    bounds); triggers are relation queries under a set; observers are
    order predicates on linear relatives of the set's terms (shifts,
    scalings, sums, differences) under the same set.  Sets share symbols,
    so the relevance layer does not split them (a relation query is
    answered under the whole set, a unary one under its component: the
    session that holds the glue must be the one the observer uses)."""
    from . import lazy as lz
    d = gen.d
    syms = _lazy_syms(gen, d)
    opaque = lz.opaque_terms(syms, d, d.integer(0, 2))
    forms = list(dict.fromkeys(lz.linear_form(syms, d, opaque) for _ in range(d.integer(3, 6))))
    sets: List[Any] = []
    for _ in range(max(1, nsets)):
        cs = []
        for _ in range(d.integer(1, 3)):
            t = d.choice(forms)
            a = getattr(Q, d.choice(lz.ORDER_PREDS))(t)
            _add_literal(cs, Not(a) if d.chance(0.2) else a)
        if d.chance(0.15):
            _add_literal(cs, gen.literal_on(d.choice(forms)))
        sets.append(And(*cs) if len(cs) > 1 else cs[0])
    runs = Runs(gen, sets, stay=0.8, p_true=0.0)
    items: List[Item] = []
    while len(items) < n:
        a = runs.next()
        terms = lz.atom_args(a) or forms
        rel = lz.linear_relatives(terms + forms, d, 6)
        sides = terms + rel + list(syms)
        unary = lambda: gen.literal_on(d.choice(sides))    # noqa: E731
        roll = d.integer(0, 99)
        if roll < 25:
            items.append(Ask(lz.trigger(d, sides, unary, equality=False if d.chance(0.6) else None), a))
        elif roll < 70:
            node = d.choice(rel or terms)
            items.append(Ask(lz.observer(d, node, lz.ORDER_PREDS, unary), a))
        elif roll < 78:
            items.append(Ask(lz.observer(d, d.choice(terms), lz.ORDER_PREDS, unary), a))
        elif roll < 85:
            items.append(Ask(lz.observer(d, d.choice(rel or terms)), True))
        elif roll < 92:
            items.append(Ask(gen.literal_on(d.choice(sides)), a))
        else:
            items.append(Ask(gen.proposition(), a))
    return items[:n]


def stream_transfer(gen, n: int, nsets: int) -> List[Item]:
    """Predicate transfer.  Sets that put a term into an EUF class through
    the links (``zero(u)``, ``positive_infinite(u)``) and state facts about
    applications of the class's value (``positive(f(0))``); triggers are
    equality queries under a set; observers are the same applications of
    the term (``positive(f(u))``), which only congruence plus transfer
    connect."""
    from . import lazy as lz
    d = gen.d
    from .generators import SYMBOLS
    syms = d.sample([s for s in SYMBOLS if s.name in ("x", "z", "y", "n")], d.integer(1, 3))
    gen.syms = syms
    sets: List[Any] = []
    obs_of: Dict[Any, List[Any]] = {}
    for _ in range(max(1, nsets)):
        # an extra conjunct about the class's term keeps the set connected
        a, observers = lz.transfer_set(d, syms)
        if d.chance(0.3):
            # an extra conjunct about the class's term keeps the set connected
            a = And(a, gen.literal_on(lz.atom_args(a)[0]))
        sets.append(a)
        obs_of[a] = observers or [lz.wrap(d.choice(syms), d)]
    runs = Runs(gen, sets, stay=0.8, p_true=0.0)
    items: List[Item] = []
    while len(items) < n:
        a = runs.next()
        terms = lz.atom_args(a) or list(syms)
        observers = obs_of[a]
        sides = list(syms) + terms
        unary = lambda: gen.literal_on(d.choice(sides))    # noqa: E731
        roll = d.integer(0, 99)
        if roll < 25:
            items.append(Ask(lz.trigger(d, sides, unary, equality=True if d.chance(0.7) else None,
                                        consts=lz.EQ_CONSTS), a))
        elif roll < 65:
            node = d.choice(observers)
            items.append(Ask(lz.observer(d, node, lz.TRANSFER_PREDS, unary), a))
        elif roll < 75:
            # a congruent wrapping the set does not mention (numbers' facts)
            node = lz.wrap(d.choice(terms), d)
            items.append(Ask(lz.observer(d, node, lz.TRANSFER_PREDS, unary), a))
        elif roll < 82:
            items.append(Ask(lz.observer(d, d.choice(observers), lz.TRANSFER_PREDS), True))
        elif roll < 92:
            items.append(Ask(gen.literal_on(d.choice(sides)), a))
        else:
            items.append(Ask(gen.proposition(), a))
    return items[:n]


def stream_lazy(gen, n: int, nsets: int) -> List[Item]:
    """Both of the above in one stream, over sets of both shapes and mixed
    ones, with generic queries between: the shape a base stream would need
    to hit the lazily switched-on capabilities."""
    from . import lazy as lz
    d = gen.d
    syms = _lazy_syms(gen, d)
    plain = [s for s in syms if s.is_finite is None] or [syms[0]]
    opaque = lz.opaque_terms(syms, d, 1)
    forms = list(dict.fromkeys(lz.linear_form(syms, d, opaque) for _ in range(d.integer(2, 5))))
    sets: List[Any] = []
    obs_of: Dict[Any, List[Any]] = {}
    for _ in range(max(1, nsets)):
        cs: List[Any] = []
        observers: List[Any] = []
        if d.chance(0.6):
            for _ in range(d.integer(1, 2)):
                t = d.choice(forms)
                a = getattr(Q, d.choice(lz.ORDER_PREDS))(t)
                _add_literal(cs, Not(a) if d.chance(0.2) else a)
        if d.chance(0.6):
            a, obs = lz.transfer_set(d, syms)
            for c in conjuncts_of(a):
                _add_literal(cs, c)
            observers.extend(obs)
        if not cs:
            cs.append(gen.literal_on(d.choice(forms)))
        a = And(*cs) if len(cs) > 1 else cs[0]
        sets.append(a)
        obs_of[a] = observers
    runs = Runs(gen, sets, stay=0.75, p_true=0.03)
    items: List[Item] = []
    while len(items) < n:
        rep = _maybe_repeat(gen, items, 0.04)
        if rep is not None:
            items.append(rep)
            continue
        a = runs.next()
        if a is True:
            items.append(Ask(gen.proposition(), True))
            continue
        terms = lz.atom_args(a) or forms
        rel = lz.linear_relatives(terms, d, 5)
        cong = obs_of[a] + [lz.wrap(d.choice(terms), d)]
        sides = terms + rel + list(syms) + plain
        unary = lambda: gen.literal_on(d.choice(sides))    # noqa: E731
        roll = d.integer(0, 99)
        if roll < 22:
            items.append(Ask(lz.trigger(d, sides, unary, consts=lz.ORDER_CONSTS + lz.EQ_CONSTS), a))
        elif roll < 50:
            items.append(Ask(lz.observer(d, d.choice(rel or terms), lz.ORDER_PREDS, unary), a))
        elif roll < 72:
            items.append(Ask(lz.observer(d, d.choice(cong), lz.TRANSFER_PREDS, unary), a))
        elif roll < 80:
            items.append(Ask(lz.observer(d, d.choice(rel + cong)), True))
        elif roll < 90:
            items.append(Ask(gen.literal_on(d.choice(sides)), a))
        else:
            items.append(Ask(gen.proposition(), a))
    return items[:n]


PROFILES["links"] = stream_links
PROFILES["transfer"] = stream_transfer
PROFILES["lazy"] = stream_lazy


PROFILES["mixed"] = stream_mixed
