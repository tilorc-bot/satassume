"""Triggers and observers for the engine's lazily switched-on capabilities.

Some of the engine's capabilities are not there from the start of a
session (or of the engine): they switch on when a certain kind of input
first appears, and stay on.  A history-dependent answer of this kind needs
two coordinated queries in one stream:

* a **trigger**: a query that switches the capability on in the session of
  an assumption set (a relation atom creates the relation glue, an
  equality atom engages predicate transfer, ...);
* an **observer**: a later query under the same set that *only that
  capability can answer*.  The always-on parts of the engine (rule base,
  structural templates, search over the set's own atoms) answer questions
  about the syntax the set already contains either way, so an observer has
  to be about terms that are *related in meaning* to the set's terms but
  *new in form*: a linear relative (``x + y`` for a set about ``x + y -
  1``: only the linked LRA theory connects them), a congruent application
  (``f(u)`` for a set with ``zero(u)`` and ``positive(f(0))``: only EUF
  congruence plus predicate transfer connects them), and so on.

This module builds both kinds from an assumption set, without reference to
any particular defect; ``harness.profiles`` uses them for the ``links``,
``transfer`` and ``lazy`` profiles, and ``QueryGen.stream`` inserts
trigger/observer pairs into the base stream (``GenOptions.lazy``).

Capabilities and their observers (see ``harness/README.md``, "Lazily
switched-on capabilities"):

``relations`` (per session; ``Session._custom`` creates ``Relations`` at
    the first relation atom).  Links ``extended_positive(e) <-> gt(e, 0)``,
    ``extended_negative(e) <-> lt(e, 0)``, ``zero(e) <-> eq(e, 0)`` for
    every argument ``e`` of a vocabulary atom of the assumptions and of
    every later query, whose sides LRA reads as linear forms over real
    terms (with bounds for ``pi``, ``sqrt(2)``, ...), and the extended-order
    clauses for ``oo`` summands.  Observers: order predicates on *linear
    relatives* of the set's terms (shifts, scalings, sums and differences
    of them, with rational and irrational constants).
``transfer`` (per session; ``Relations._engage_transfer`` at the first
    equality atom that is not glue).  Every node of the session becomes a
    candidate for sharing all its unary facts with the terms EUF puts in
    its class: through the links (``zero(e)`` puts ``e`` in the class of
    ``0``; ``eq(e, oo)`` makes ``positive_infinite(e)`` a class with
    ``oo``), through equal sides, and through congruence (``f(u) ~ f(0)``).
    Observers: unary predicates on applications *congruent* to ones the
    set has facts about.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple

from sympy import (Abs, E, Eq, Function, I, Integer, Ne, Q, Rational, S, Symbol, cos, exp, oo, pi,
                   sin, sqrt)
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or

from .checker import Ask

f, g = Function("f"), Function("g")

#: predicates the links and LRA decide (order-related), the good observers
#: of the relation glue
ORDER_PREDS = ("positive", "negative", "nonnegative", "nonpositive", "zero", "nonzero",
               "extended_positive", "extended_negative", "extended_nonzero",
               "extended_nonnegative", "extended_nonpositive")
#: predicates whose transfer across a class is visible (any unary works;
#: these are the ones a set about ``f(0)`` is likely to decide)
TRANSFER_PREDS = ("positive", "negative", "zero", "nonzero", "integer", "rational", "prime",
                  "even", "odd", "real", "irrational", "algebraic", "imaginary", "finite",
                  "infinite", "commutative", "composite", "transcendental")

COEFFS = (S.One, S.NegativeOne, S(2), S(-2), S.Half, S(3), Rational(-1, 3), Rational(3, 2))
SHIFTS = (S.One, S.NegativeOne, S(2), S(-3), S.Half, Rational(-1, 2), pi, -pi, sqrt(2), E,
          Rational(1, 3), Integer(7))
ORDER_CONSTS = (S.Zero, S.One, S.NegativeOne, S(2), S.Half, Rational(-1, 3), pi, sqrt(2), E,
                Integer(7), oo, -oo)
EQ_CONSTS = (S.Zero, S.One, S(2), S.NegativeOne, S.Half, oo, -oo, pi)

RELATION_NAMES = ("eq", "ne", "lt", "le", "gt", "ge")


def sorted_atoms(b, *types) -> List[Any]:
    """``b.atoms(*types)`` in SymPy's canonical order: a set iterates in
    an order that depends on ``PYTHONHASHSEED``, and every choice a
    generator makes from these lists must not."""
    from sympy import default_sort_key
    return sorted(b.atoms(*types), key=default_sort_key)


def rel_names_of(b) -> set:
    """Names (``eq ne lt le gt ge``) of the relations in the Boolean ``b``."""
    out: set = set()
    if b is True or b is False or not hasattr(b, "atoms"):
        return out
    for r in sorted_atoms(b, Relational):
        out.add({"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}[r.rel_op])
    for a in sorted_atoms(b, AppliedPredicate):
        n = str(a.function.name)
        if n in RELATION_NAMES:
            out.add(n)
    return out


def has_relation(b) -> bool:
    return bool(rel_names_of(b))


def has_equality(b) -> bool:
    return bool(rel_names_of(b) & {"eq", "ne"})


def relation_sides(b) -> List[Any]:
    """Sides of the relations in the Boolean ``b`` (the terms the relation
    glue links), without repeats."""
    out: dict = {}
    if b is True or b is False or not hasattr(b, "atoms"):
        return []
    for r in sorted_atoms(b, Relational):
        out[r.lhs] = None
        out[r.rhs] = None
    for a in sorted_atoms(b, AppliedPredicate):
        if str(a.function.name) in RELATION_NAMES:
            for e in a.arguments:
                out[e] = None
    return list(out)


def relation_atoms(b) -> List[Any]:
    """The relation atoms of the Boolean ``b`` (Relationals and
    ``Q.eq``/... applications), without repeats."""
    out: dict = {}
    if b is True or b is False or not hasattr(b, "atoms"):
        return []
    for r in sorted_atoms(b, Relational):
        out[r] = None
    for a in sorted_atoms(b, AppliedPredicate):
        if str(a.function.name) in RELATION_NAMES:
            out[a] = None
    return list(out)


def atom_args(b) -> List[Any]:
    """Arguments of the vocabulary atoms of ``b`` (the terms the relation
    glue links), in order, without repeats."""
    out: dict = {}
    if b is True or b is False or not hasattr(b, "atoms"):
        return []
    for a in sorted_atoms(b, AppliedPredicate):
        n = str(a.function.name)
        if n in RELATION_NAMES or n == "is_true":
            continue
        for e in a.arguments:
            if hasattr(e, "free_symbols") and getattr(e, "is_number", False) is False:
                out[e] = None
    return list(out)


# --------------------------------------------------------------------------
# linear relatives (relation glue: links + LRA)
# --------------------------------------------------------------------------

def linear_relatives(terms: Sequence[Any], d, k: int = 6) -> List[Any]:
    """Up to ``k`` terms linearly related to ``terms`` (LRA connects them
    once the links exist; the structural templates mostly do not): shifts
    by a constant, scalings, negations, sums and differences of two of
    them, a half-sum, a term plus a fresh symbol of the same terms."""
    terms = [t for t in terms if getattr(t, "free_symbols", None)]
    if not terms:
        return []
    out: dict = {}
    tries = 0
    while len(out) < k and tries < 4 * k:
        tries += 1
        t = d.choice(terms)
        r = d.integer(0, 9)
        try:
            if r < 3:
                e = t + d.choice(SHIFTS)
            elif r < 5:
                e = d.choice(COEFFS) * t
            elif r < 6:
                e = -t
            elif r < 8:
                e = t + d.choice(terms) if d.chance(0.5) else t - d.choice(terms)
            elif r < 9:
                e = (t + d.choice(terms)) / 2 + d.choice(SHIFTS)
            else:
                e = d.choice(COEFFS) * t + d.choice(SHIFTS)
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if getattr(e, "free_symbols", None) and e not in terms:
            out[e] = None
    return list(out)


def linear_form(syms: Sequence[Any], d, opaque: Optional[Sequence[Any]] = None):
    """A linear form ``c1*t1 + c2*t2 + k`` over 1-3 terms: symbols, and
    (``opaque``) nonlinear terms LRA treats as variables."""
    pool = list(syms) + list(opaque or ())
    n = d.integer(1, 3)
    e = S.Zero
    for _ in range(n):
        t = d.choice(pool)
        c = d.choice(COEFFS) if d.chance(0.5) else S.One
        e = e + c * t
    if d.chance(0.6):
        e = e + d.choice(SHIFTS)
    return e


def opaque_terms(syms: Sequence[Any], d, k: int = 3) -> List[Any]:
    """Nonlinear terms over ``syms`` that LRA reads as opaque variables."""
    out: dict = {}
    for _ in range(k):
        s = d.choice(syms)
        r = d.integer(0, 6)
        try:
            e = (sin(s), exp(s), Abs(s), s * d.choice(syms), s ** 2, f(s), sqrt(s))[r]
        except (TypeError, ValueError):
            continue
        out[e] = None
    return list(out)


# --------------------------------------------------------------------------
# congruent relatives (predicate transfer)
# --------------------------------------------------------------------------

def wrap(e, d, depth: int = 1):
    """An application around ``e`` (``f(e)``, ``g(f(e))``, ``f(e) + 1``,
    ``2*f(e)``, ``exp(f(e))``, ``Abs(f(e))``): an EUF-structural term
    congruent to the same wrapping of an equal term."""
    r = d.integer(0, 7)
    h = d.choice((f, g))
    try:
        if r < 3:
            out = h(e)
        elif r < 4:
            out = h(e) + d.choice((S.One, S(2), S.NegativeOne))
        elif r < 5:
            out = d.choice((S(2), S(-1), S.Half)) * h(e)
        elif r < 6:
            out = exp(h(e))
        elif r < 7:
            out = Abs(h(e))
        else:
            out = h(e, d.choice((S.One, S.Zero))) if d.chance(0.3) else h(h(e))
    except (TypeError, ValueError):
        out = h(e)
    if depth > 0 and d.chance(0.25):
        return wrap(out, d, depth - 1)
    return out


def class_pairs(d, syms: Sequence[Any]) -> List[Tuple[Any, Any, Any]]:
    """``(term, value, link)`` triples: a term the links put into the EUF
    class of ``value`` when the unary fact ``link`` holds (``zero(e)`` for
    ``0``, ``positive_infinite(e)`` for ``oo``, ...); the term is a symbol
    or a linear form.  Infinite values only for plain symbols (a declared
    real symbol is finite)."""
    out = []
    used: set = set()
    plain = [s for s in syms if getattr(s, "is_Symbol", False) and s.is_finite is None]
    for _ in range(d.integer(1, 2)):
        t = d.choice(syms) if d.chance(0.7) else linear_form(syms, d)
        if t in used:
            continue
        used.add(t)
        r = d.integer(0, 5)
        if r >= 4 and plain and t in plain:
            out.append((t, oo, Q.positive_infinite(t)) if r == 4 else (t, -oo, Q.negative_infinite(t)))
        else:
            out.append((t, S.Zero, Q.zero(t)))
    return out


def transfer_set(d, syms: Sequence[Any], extra: Callable[[], Any] = None):
    """An assumption set with a class-making fact and facts about
    applications of the class's value (``zero(u) & positive(f(0))``); the
    observers ask the same applications of the term (``positive(f(u))``).
    Every conjunct is connected to the observers through the term and the
    function head (the relevance layer answers a unary query under the
    conjuncts connected to it; the trigger, a relation, is answered under
    the whole set, and both must use one session).  Returns ``(set,
    observers)``."""
    pairs = class_pairs(d, syms)
    conj: List[Any] = []
    observers: List[Any] = []
    for t, value, link in pairs:
        conj.append(link)
        for _ in range(d.integer(1, 2)):
            app_v = wrap(value, d)
            app_t = app_v.xreplace({value: t})
            if app_t == app_v:
                continue
            pred = d.choice(TRANSFER_PREDS)
            atom = getattr(Q, pred)(app_v)
            conj.append(Not(atom) if d.chance(0.2) else atom)
            observers.append(app_t)
    if len(pairs) == 2 and pairs[0][1] == pairs[1][1] and d.chance(0.5):
        # two terms in one class: facts about applications of one for the other
        t1, t2 = pairs[0][0], pairs[1][0]
        app = wrap(t2, d)
        conj.append(getattr(Q, d.choice(TRANSFER_PREDS))(app))
        observers.append(app.xreplace({t2: t1}))
    if extra is not None and d.chance(0.3):
        conj.append(extra())
    d_conj = list(dict.fromkeys(conj))
    return (And(*d_conj) if len(d_conj) > 1 else d_conj[0]), observers


# --------------------------------------------------------------------------
# triggers
# --------------------------------------------------------------------------

def relation_query(d, sides: Sequence[Any], consts: Sequence[Any] = ORDER_CONSTS,
                   equality: Optional[bool] = None):
    """A relation atom in one of the three spellings, with sides from
    ``sides`` and ``consts``; ``equality`` True: ``eq``/``ne`` only, False:
    order relations only."""
    if equality is None:
        name = d.choice(RELATION_NAMES)
    elif equality:
        name = d.choice(("eq", "ne"))
    else:
        name = d.choice(("lt", "le", "gt", "ge"))
    a = d.choice(sides)
    b = d.choice(consts) if d.chance(0.5) else d.choice(sides)
    style = d.choice(("Q", "rel", "is_true"))
    qrel = getattr(Q, name)
    if style == "Q":
        return qrel(a, b)
    cls = {"eq": Eq, "ne": Ne, "lt": lambda p, q: p < q, "le": lambda p, q: p <= q,
           "gt": lambda p, q: p > q, "ge": lambda p, q: p >= q}[name]
    try:
        r = cls(a, b)
    except (TypeError, ValueError):
        return qrel(a, b)
    if r is S.true or r is S.false or isinstance(r, bool):
        return qrel(a, b)
    return Q.is_true(r) if style == "is_true" else r


def trigger(d, sides: Sequence[Any], unary: Callable[[], Any], equality: Optional[bool] = None,
            consts: Sequence[Any] = ORDER_CONSTS):
    """A query that brings a relation atom into the session: the atom, its
    negation, or a Boolean combination with a unary literal."""
    r = relation_query(d, sides, consts, equality)
    roll = d.integer(0, 9)
    if roll < 5:
        return r
    if roll < 6:
        return Not(r)
    if roll < 8:
        return Implies(r, unary())
    if roll < 9:
        return Or(r, unary())
    return Equivalent(r, unary())


def observer(d, node, preds: Sequence[str] = ORDER_PREDS, other: Callable[[], Any] = None):
    """A unary query about ``node`` (and, sometimes, a Boolean combination
    with another unary literal, so that the answer memo of an earlier
    plain form does not hide it)."""
    atom = getattr(Q, d.choice(preds))(node)
    roll = d.integer(0, 9)
    if roll < 6 or other is None:
        return Not(atom) if d.chance(0.25) else atom
    if roll < 8:
        return Or(atom, other())
    if roll < 9:
        return Implies(other(), atom)
    return And(atom, other())
