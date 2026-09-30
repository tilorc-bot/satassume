"""Query generators over the engine's whole feature surface.

One builder (``QueryGen``) is driven either by a seeded ``random.Random``
(``RandomDraw``: fast fuzzing over many seeds) or by Hypothesis
(``HypothesisDraw`` inside ``stream_strategy``: shrinking).  It reaches:

* every predicate of the vocabulary (``satassume.rules.PREDICATES``, 33),
  ``Q.is_true`` over an applied predicate, custom predicates registered
  through ``harness.registry`` (unary, polyadic, and vocabulary
  predicates on a class) and unregistered custom predicates (out of
  scope);
* every class the templates cover: symbols with declared assumptions
  (real, integer, positive, nonnegative, negative, complex, extended_real,
  imaginary, nonzero, odd, rational, non-commutative, ``Dummy``), numbers
  (integers, rationals, Floats), ``pi``, ``E``, ``EulerGamma``,
  ``GoldenRatio``, ``I``, ``oo``, ``-oo``, ``zoo``, ``nan``; ``Add``,
  ``Mul``, ``Pow`` (squares, inverses, roots, symbolic exponents, ``2**x``),
  ``exp``, ``log``, ``Abs``, ``re``, ``im``, ``sign``, ``conjugate``,
  ``floor``, ``ceiling``, ``factorial``, the trigonometric, inverse
  trigonometric and hyperbolic functions, undefined functions ``f``/``g``
  (EUF congruence), and out-of-scope arguments (a ``MatrixSymbol``);
* relations in all three spellings (``Q.lt(a, b)``, ``a < b``,
  ``Q.is_true(a < b)``), with constants (``pi``, ``sqrt(2)``, Floats,
  ``oo``) and undefined functions on their sides;
* Boolean structure: ``And``, ``Or``, ``Not``, ``Implies``, ``Equivalent``
  in assumptions and propositions; ``True`` assumptions (the context-free
  path); constant propositions (answered without the assumptions);
* stream structure: a pool of assumption sets asked in runs (session
  reuse) and interleaved (LRU eviction), propositions over a pool of
  shared subterms (fact-cache sharing), exact repeats (answer memo),
  disjoint-symbol conjuncts (relevance splits), and register/unregister
  events (memo invalidation).
"""
from __future__ import annotations

import random
from typing import Any, Callable, List, Optional, Sequence

from sympy import (Abs, Dummy, E, Eq, EulerGamma, Float, Function, Ge, GoldenRatio, Gt,
                   I, Integer, Le, Lt, MatrixSymbol, Ne, Predicate, Q, Rational, S, Symbol,
                   acos, acot, asin, atan, ceiling, conjugate, cos, cosh, cot, exp, factorial,
                   floor, im, log, nan, oo, pi, re, sign, sin, sinh, sqrt, tan, tanh, zoo)
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

from satassume.rules import PREDICATES

from . import registry as reg
from .checker import Ask, Event, Item
from .sympy_io import custom_predicate

# --------------------------------------------------------------------------
# the alphabet
# --------------------------------------------------------------------------

SYMBOLS: List[Symbol] = [
    Symbol("x"), Symbol("y", real=True), Symbol("z"), Symbol("n", integer=True),
    Symbol("p", positive=True), Symbol("q", nonnegative=True),
    Symbol("k", integer=True, positive=True), Symbol("m", negative=True),
    Symbol("c", complex=True), Symbol("e", extended_real=True),
    Symbol("i", imaginary=True), Symbol("w", nonzero=True), Symbol("o", odd=True),
    Symbol("r", rational=True), Symbol("A", commutative=False), Dummy("d"),
    Symbol("t", real=True, nonzero=True), Symbol("j", integer=True, even=True),
]

CONSTANTS: List[Any] = [
    S.Zero, S.One, S.NegativeOne, S(2), S(3), S(-2), S.Half, Rational(-1, 3), Rational(3, 2),
    pi, E, sqrt(2), I, oo, -oo, zoo, nan, Float("0.5"), Float("2.0"), Integer(31), Integer(7),
    pi / 2, 2 * pi, EulerGamma, GoldenRatio, 1 + I, sqrt(3) / 2, log(2), exp(2),
]

#: constants that are safe on the sides of a relation (nan and non-reals
#: make ``Lt`` raise; they are still used through ``Q.lt``)
RELATION_CONSTANTS: List[Any] = [S.Zero, S.One, S.NegativeOne, S(2), S.Half, Rational(-1, 3),
                                 pi, pi / 2, sqrt(2), oo, -oo, Float("0.5"), E, Integer(7)]

UNARY_FUNCS: List[Callable] = [exp, log, Abs, re, im, sign, conjugate, floor, ceiling, factorial,
                               sin, cos, tan, cot, asin, acos, atan, acot, sinh, cosh, tanh, sqrt]
f, g = Function("f"), Function("g")
UNDEF_FUNCS = [f, g]
EXPONENTS: List[Any] = [S(2), S(3), S.NegativeOne, S.Half, Rational(1, 3), S(-2), Rational(3, 2),
                        Rational(-1, 2), S(4)]
MATRIX = MatrixSymbol("M", 2, 2)

RELATION_NAMES = ("lt", "le", "gt", "ge", "eq", "ne")
RELATION_CLASSES = {"lt": Lt, "le": Le, "gt": Gt, "ge": Ge, "eq": Eq, "ne": Ne}
Q_RELATIONS = {"lt": Q.lt, "le": Q.le, "gt": Q.gt, "ge": Q.ge, "eq": Q.eq, "ne": Q.ne}

CUSTOM_UNARY = list(reg.CUSTOM_PREDICATES) + ["hunknown"]   # hunknown: never registered
CUSTOM_POLYADIC = list(reg.POLYADIC_PREDICATES)


def predicate(name: str, arity: int = 1) -> Predicate:
    if name in CUSTOM_UNARY or name in CUSTOM_POLYADIC:
        return custom_predicate(name, 2 if name in CUSTOM_POLYADIC else arity)
    # 'polar' is in the vocabulary but has no key on SymPy's Q
    return getattr(Q, name) if hasattr(Q, name) else custom_predicate(name)


# --------------------------------------------------------------------------
# draw interfaces
# --------------------------------------------------------------------------

class RandomDraw:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def choice(self, seq: Sequence):
        return self.rng.choice(seq)

    def integer(self, lo: int, hi: int) -> int:
        return self.rng.randint(lo, hi)

    def chance(self, p: float) -> bool:
        """True with probability ``p`` (under Hypothesis, True is the
        simpler value, so ask questions where True is the simpler case)."""
        return self.rng.random() < p

    def sample(self, seq: Sequence, k: int) -> list:
        return self.rng.sample(list(seq), k)


class HypothesisDraw:
    def __init__(self, draw: Callable):
        from hypothesis import strategies as st
        self.draw, self.st = draw, st

    def choice(self, seq: Sequence):
        return self.draw(self.st.sampled_from(list(seq)))

    def integer(self, lo: int, hi: int) -> int:
        return self.draw(self.st.integers(lo, hi))

    def chance(self, p: float) -> bool:
        return self.draw(self.st.integers(0, 999)) < int(p * 1000)

    def sample(self, seq: Sequence, k: int) -> list:
        seq = list(seq)
        idx = self.draw(self.st.lists(self.st.integers(0, len(seq) - 1), min_size=k, max_size=k,
                                      unique=True))
        return [seq[i] for i in idx]


# --------------------------------------------------------------------------
# the builder
# --------------------------------------------------------------------------

class GenOptions:
    def __init__(self, relations: bool = True, custom: bool = False, matrices: bool = True,
                 undefined: bool = True, max_depth: int = 3, nsymbols: Optional[int] = None,
                 events: bool = False, constant_props: bool = True, profile: str = "base",
                 lazy: float = 0.0):
        self.relations = relations
        self.custom = custom
        self.matrices = matrices
        self.undefined = undefined
        self.max_depth = max_depth
        self.nsymbols = nsymbols
        self.events = events
        self.constant_props = constant_props
        #: the stream shape (``harness.profiles``); ``base`` is ``QueryGen.stream``
        self.profile = profile
        #: probability that a base-stream query is followed by a trigger /
        #: observer pair for the lazily switched-on capabilities
        #: (``harness.lazy``): a relation query under the current set, then
        #: a unary query about a linear or congruent relative of the set's
        #: terms under the same set
        self.lazy = lazy


class QueryGen:
    def __init__(self, draw, opts: Optional[GenOptions] = None):
        self.d = draw
        self.o = opts or GenOptions()
        n = self.o.nsymbols or self.d.integer(2, 5)
        self.syms: List[Symbol] = self.d.sample(SYMBOLS, min(n, len(SYMBOLS)))
        self.pool: List[Any] = []            # shared subterms of this stream

    # -- expressions -------------------------------------------------------
    def symbol(self):
        return self.d.choice(self.syms)

    def constant(self):
        return self.d.choice(CONSTANTS)

    def leaf(self):
        if self.d.chance(0.7):
            return self.symbol()
        return self.constant()

    def term(self, depth: Optional[int] = None):
        depth = self.o.max_depth if depth is None else depth
        if self.pool and self.d.chance(0.35):
            return self.d.choice(self.pool)
        if depth <= 0 or self.d.chance(0.4):
            return self.leaf()
        kind = self.d.choice(("add", "mul", "pow", "func", "coeff", "neg", "undef", "add3", "mul3",
                              "shift", "inv"))
        sub = lambda: self.term(depth - 1)   # noqa: E731
        try:
            if kind == "add":
                e = sub() + sub()
            elif kind == "add3":
                e = sub() + sub() + sub()
            elif kind == "mul":
                e = sub() * sub()
            elif kind == "mul3":
                e = sub() * sub() * sub()
            elif kind == "pow":
                e = sub() ** (self.d.choice(EXPONENTS) if self.d.chance(0.7) else sub())
            elif kind == "func":
                e = self.d.choice(UNARY_FUNCS)(sub())
            elif kind == "coeff":
                e = self.d.choice((S(2), S(-3), S.Half, pi, I, sqrt(2), Float("0.5"))) * sub()
            elif kind == "neg":
                e = -sub()
            elif kind == "shift":
                e = sub() + self.d.choice((S.One, S.NegativeOne, S(2), pi, I))
            elif kind == "inv":
                e = 1 / sub()
            elif kind == "undef" and self.o.undefined:
                e = self.d.choice(UNDEF_FUNCS)(sub())
            else:
                e = sub() + sub()
        except (TypeError, ValueError, ZeroDivisionError, RecursionError):
            e = self.leaf()
        if len(self.pool) < 16 and self.d.chance(0.5):
            self.pool.append(e)
        return e

    # -- atoms -----------------------------------------------------------------
    def pred_name(self) -> str:
        return self.d.choice(PREDICATES)

    def unary_atom(self):
        name = self.pred_name()
        arg = self.term()
        if self.o.matrices and self.d.chance(0.02):
            arg = MATRIX
        a = predicate(name)(arg)
        if self.d.chance(0.05):
            a = Q.is_true(a)
        return a

    def custom_atom(self):
        if CUSTOM_POLYADIC and self.d.chance(0.25):
            name = self.d.choice(CUSTOM_POLYADIC)
            a, b = self.term(), self.term()
            if self.d.chance(0.3):
                b = a
            return predicate(name)(a, b)
        name = self.d.choice(CUSTOM_UNARY)
        arg = self.term()
        if name == "hmersenne" and self.d.chance(0.5):
            arg = self.d.choice((Integer(31), Integer(7), Integer(10), Integer(3)))
        return predicate(name)(arg)

    def relation_side(self):
        if self.d.chance(0.35):
            return self.d.choice(RELATION_CONSTANTS)
        return self.term(2)

    def relation_atom(self):
        name = self.d.choice(RELATION_NAMES)
        a, b = self.relation_side(), self.relation_side()
        style = self.d.choice(("Q", "rel", "is_true"))
        if style == "Q":
            return Q_RELATIONS[name](a, b)
        try:
            r = RELATION_CLASSES[name](a, b)
        except (TypeError, ValueError):
            return Q_RELATIONS[name](a, b)
        return Q.is_true(r) if style == "is_true" else r

    def atom(self):
        roll = self.d.integer(0, 99)
        if self.o.relations and roll < 25:
            return self.relation_atom()
        if self.o.custom and roll < 37:
            return self.custom_atom()
        return self.unary_atom()

    def literal(self):
        a = self.atom()
        return a if self.d.chance(0.75) else Not(a)

    def predicate_on(self, node):
        """A random vocabulary predicate applied to ``node`` (a given
        expression, for the profiles that aim at particular nodes)."""
        a = predicate(self.pred_name())(node)
        if self.d.chance(0.03):
            a = Q.is_true(a)
        return a

    def literal_on(self, node):
        a = self.predicate_on(node)
        return a if self.d.chance(0.75) else Not(a)

    # -- formulas --------------------------------------------------------------
    def conjunct(self):
        roll = self.d.integer(0, 99)
        if roll < 75:
            return self.literal()
        if roll < 88:
            return Or(self.literal(), self.literal())
        if roll < 94:
            return Implies(self.literal(), self.literal())
        if roll < 98:
            return Equivalent(self.literal(), self.literal())
        return Not(And(self.literal(), self.literal()))

    def assumptions(self):
        if self.d.chance(0.08):
            return True
        n = self.d.integer(1, 4)
        cs = [self.conjunct() for _ in range(n)]
        a = And(*cs) if len(cs) > 1 else cs[0]
        return a

    def constant_proposition(self):
        name = self.pred_name()
        c = self.d.choice(CONSTANTS)
        e = c if self.d.chance(0.6) else self.d.choice(UNARY_FUNCS)(c)
        try:
            return predicate(name)(e)
        except (TypeError, ValueError):
            return predicate(name)(c)

    def proposition(self):
        roll = self.d.integer(0, 99)
        if self.o.constant_props and roll < 4:
            return self.constant_proposition()
        if roll < 72:
            return self.literal()
        if roll < 85:
            return Or(self.literal(), self.literal())
        if roll < 93:
            return And(self.literal(), self.literal())
        if roll < 97:
            return Implies(self.literal(), self.literal())
        return Equivalent(self.literal(), self.literal())

    # -- streams ---------------------------------------------------------------
    def stream(self, n: int, nsets: int = 6) -> List[Item]:
        sets = [self.assumptions() for _ in range(nsets)]
        items: List[Item] = []
        props: List[Any] = []                # propositions asked so far (reused across sets)
        cur = 0
        events_left = 6 if (self.o.events and self.o.custom) else 0
        active: List[str] = []       # registrations switched on by this stream
        recent = 0                   # queries since the last event: repeat more
        for k in range(n):
            if events_left and self.d.chance(0.04):
                rid = self.d.choice(sorted(reg.REGISTRATIONS))
                kind = "unregister" if rid in active else "register"
                (active.remove if kind == "unregister" else active.append)(rid)
                items.append(Event(kind, rid))
                events_left -= 1
                recent = 12
                continue
            if items and self.d.chance(0.06 if not recent else 0.45):
                recent = max(recent - 1, 0)
                # an exact repeat of an earlier query (answer memo)
                prev = self.d.choice([it for it in items if isinstance(it, Ask)] or [None])
                if prev is not None:
                    items.append(prev)
                    continue
            if not self.d.chance(0.65):
                cur = self.d.integer(0, nsets - 1)
            a = sets[cur]
            if self.d.chance(0.05):
                a = True
            if props and self.d.chance(0.3):
                # the same proposition under another set (memo keys, shared
                # nodes between sessions, context-free facts)
                prop = self.d.choice(props)
            else:
                prop = self.proposition()
                props.append(prop)
            items.append(Ask(prop, a))
            if self.o.lazy and a is not True and self.d.chance(self.o.lazy):
                items.extend(self.lazy_pair(a))
        for rid in active:           # leave the registry as it was found
            items.append(Event("unregister", rid))
        return items


    def lazy_pair(self, a) -> List[Ask]:
        """A trigger (a relation query) and one or two observers (unary
        queries about linear and congruent relatives of the set's terms)
        under the set ``a`` (see ``harness.lazy``)."""
        from . import lazy as lz
        d = self.d
        terms = lz.atom_args(a)
        if not terms:
            return []
        rel = lz.linear_relatives(terms, d, 4)
        cong = [lz.wrap(d.choice(terms), d)]
        sides = terms + rel + list(self.syms)
        unary = lambda: self.literal_on(d.choice(sides))    # noqa: E731
        out = [Ask(lz.trigger(d, sides, unary, consts=lz.ORDER_CONSTS + lz.EQ_CONSTS), a)]
        for _ in range(d.integer(1, 2)):
            if d.chance(0.6):
                out.append(Ask(lz.observer(d, d.choice(rel or terms), lz.ORDER_PREDS, unary), a))
            else:
                out.append(Ask(lz.observer(d, d.choice(cong), lz.TRANSFER_PREDS, unary), a))
        return out


# --------------------------------------------------------------------------
# entry points
# --------------------------------------------------------------------------

def build_stream(gen: QueryGen, n: int, nsets: int) -> List[Item]:
    """The stream of ``gen``'s profile (``base``: ``QueryGen.stream``;
    the others: ``harness.profiles``)."""
    name = gen.o.profile or "base"
    if name == "base":
        return gen.stream(n, nsets)
    from .profiles import PROFILES
    try:
        fn = PROFILES[name]
    except KeyError:
        raise SystemExit(f"unknown profile {name!r}; choose from base, {', '.join(sorted(PROFILES))}")
    return fn(gen, n, nsets)


def random_stream(seed: int, n: int = 200, nsets: int = 6, **opts) -> List[Item]:
    """A seeded stream of ``n`` items over ``nsets`` assumption sets
    (``profile=NAME`` selects a shape from ``harness.profiles``)."""
    rng = random.Random(seed)
    gen = QueryGen(RandomDraw(rng), GenOptions(**opts))
    return build_stream(gen, n, nsets)


def stream_strategy(n_max: int = 40, nsets_max: int = 4, **opts):
    """A Hypothesis strategy for streams (shrinkable)."""
    from hypothesis import strategies as st

    @st.composite
    def _streams(draw):
        gen = QueryGen(HypothesisDraw(draw), GenOptions(**opts))
        nsets = draw(st.integers(1, nsets_max))
        n = draw(st.integers(1, n_max))
        return build_stream(gen, n, nsets)

    return _streams()
