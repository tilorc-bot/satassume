"""Concrete models of assumption sets: a conservative evaluator of a SymPy
Boolean at a numeric assignment, and a small grid search for a model.

Used by the I2 block producer (every block carries a witness assignment,
verified here, before it is used) and by the consistency guard as the
second path beside the engine (``invariants.consistent_by``): a set the
engine cannot decide (a matrix, a Float the theories do not read, a
relation no theory reads) is consistent when a concrete assignment
satisfies every conjunct.

The evaluator is conservative: an order relation is False whenever a
side is not an extended real, ``eq``/``ne`` are structural on the
evaluated sides, a vocabulary predicate is SymPy's own ``is_<name>`` of
the evaluated term (None when SymPy does not know), anything else (a
custom predicate, a matrix atom, an undefined function left in a term)
is None, and None propagates through the connectives three-valued.  A
model found this way is a model under SymPy's own semantics; "none
found" is inconclusive, never "inconsistent".
"""
from __future__ import annotations

import itertools
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sympy import Basic, Float, I, Rational, S, Symbol, pi, sqrt
from sympy.assumptions.assume import AppliedPredicate
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, BooleanAtom, Equivalent, Implies, Not, Or

from satassume.rules import PREDICATES

_ORDER = {"lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
          "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b}
_RELNAMES = {"Lt": "lt", "Le": "le", "Gt": "gt", "Ge": "ge", "Equality": "eq", "Unequality": "ne",
             "StrictLessThan": "lt", "LessThan": "le", "StrictGreaterThan": "gt", "GreaterThan": "ge"}

#: the classified constant pool shared by the generators and the guard:
#: exact rationals, algebraic irrationals, transcendentals, Floats,
#: constants whose sign or zero-ness exact evaluation cannot settle (they
#: simplify to a simple value by an identity only: ``unsettled``, each
#: equal to 0), non-real constants and infinities.  ``const_class`` names
#: the class of a constant; the I2 case records the classes present.
CONSTANTS: Dict[str, List[Any]] = {}


def _build_constants():
    from sympy import E, GoldenRatio, cos, cosh, exp, log, sin, sinh, zoo
    CONSTANTS.update({
        "rational": [S.Zero, S.One, S(2), S(-3), S(7), S.Half, Rational(-2, 3), S(10) ** 12],
        "algebraic": [sqrt(2), -sqrt(3) / 2, GoldenRatio, S(2) ** Rational(1, 3)],
        "transcendental": [pi, E, -pi / 2, exp(2)],
        "float": [Float(2.5), Float(-0.1), Float("1e-9")],
        "unsettled": [cos(1) ** 2 + sin(1) ** 2 - 1, log(2) + log(3) - log(6),
                      cosh(1) ** 2 - sinh(1) ** 2 - 1, sin(pi / 7) ** 2 + cos(pi / 7) ** 2 - 1],
        "nonreal": [I, 1 + I, exp(I * pi / 3)],
        "infinite": [S.Infinity, S.NegativeInfinity, zoo],
    })


_build_constants()
#: classes usable as a side of a relation (finite reals; ``unsettled``
#: too: the set is judged by the guard)
REAL_CLASSES = ("rational", "algebraic", "transcendental", "float", "unsettled")


def const_class(c) -> Optional[str]:
    """The class of a constant of the pool, or of any closed term by its
    properties (None for a term with free symbols)."""
    for name, cs in CONSTANTS.items():
        if any(c == k for k in cs):
            return name
    if getattr(c, "free_symbols", None):
        return None
    if not c.is_finite:
        return "infinite"
    if c.is_extended_real is False:
        return "nonreal"
    if c.has(Float):
        return "float"
    if c.is_rational:
        return "rational"
    if c.is_algebraic:
        return "algebraic"
    if c.is_transcendental:
        return "transcendental"
    return "unsettled"


#: the value pool of the model search (classes: exact rationals, algebraic
#: and transcendental irrationals, a Float, a non-real, the infinities)
POOL = [S.Zero, S.One, S.NegativeOne, S(2), S(-3), S(5), S(7), Rational(1, 2), Rational(-3, 2),
        Float(2.5), sqrt(2), -pi, I, 1 + I, S.Infinity, S.NegativeInfinity]
#: a smaller pool for witnesses of blocks (finite reals: order chains stay meaningful)
WITNESS_POOL = [S.Zero, S.One, S.NegativeOne, S(2), S(-3), S(5), Rational(1, 2), Rational(-3, 2), Float(2.5), sqrt(2)]


def _bool(x) -> Optional[bool]:
    if x is S.true or x is True:
        return True
    if x is S.false or x is False:
        return False
    return None


def _term(t, subs: dict):
    try:
        v = t.xreplace(subs) if subs else t
    except Exception:  # noqa: BLE001
        return None
    if getattr(v, "has", None) and v.has(S.NaN):
        return None
    return v


def _relation(name: str, a, b, subs: dict) -> Optional[bool]:
    a, b = _term(a, subs), _term(b, subs)
    if a is None or b is None:
        return None
    if name == "eq":
        return bool(a == b) if (a.free_symbols or b.free_symbols) == set() else None
    if name == "ne":
        return bool(a != b) if (a.free_symbols or b.free_symbols) == set() else None
    ra, rb = a.is_extended_real, b.is_extended_real
    if ra is False or rb is False:
        return False            # order relations hold only between extended reals
    if ra is None or rb is None:
        return None
    try:
        return _bool(_ORDER[name](a, b))
    except Exception:  # noqa: BLE001
        return None


def evaluate_at(b, subs: dict) -> Optional[bool]:
    """Truth of the Boolean ``b`` at the assignment ``subs`` (symbol ->
    number), three-valued and conservative (module docstring)."""
    if isinstance(b, (BooleanAtom, bool)):
        return _bool(b)
    if isinstance(b, Relational):
        name = _RELNAMES.get(type(b).__name__)
        return None if name is None else _relation(name, b.lhs, b.rhs, subs)
    if isinstance(b, AppliedPredicate):
        name = str(b.function.name)
        args = b.arguments
        if name == "is_true":
            return evaluate_at(args[0], subs) if len(args) == 1 else None
        if name in ("lt", "le", "gt", "ge", "eq", "ne"):
            return _relation(name, args[0], args[1], subs) if len(args) == 2 else None
        if name in PREDICATES and len(args) == 1:
            v = _term(args[0], subs)
            if v is None or not isinstance(v, Basic):
                return None
            if v.free_symbols - set(subs):
                pass                  # a symbol the assignment leaves free: SymPy may still know
            try:
                r = getattr(v, "is_" + name, None)
            except Exception:  # noqa: BLE001
                return None
            return None if r is None else bool(r)
        return None
    if isinstance(b, Not):
        r = evaluate_at(b.args[0], subs)
        return None if r is None else (not r)
    if isinstance(b, And):
        rs = [evaluate_at(x, subs) for x in b.args]
        if any(r is False for r in rs):
            return False
        return True if all(r is True for r in rs) else None
    if isinstance(b, Or):
        rs = [evaluate_at(x, subs) for x in b.args]
        if any(r is True for r in rs):
            return True
        return False if all(r is False for r in rs) else None
    if isinstance(b, Implies):
        a, c = (evaluate_at(x, subs) for x in b.args)
        if a is False or c is True:
            return True
        if a is True and c is False:
            return False
        return None
    if isinstance(b, Equivalent):
        rs = [evaluate_at(x, subs) for x in b.args]
        if any(r is None for r in rs):
            return None
        return all(r == rs[0] for r in rs)
    return None


def admissible(sym, value) -> bool:
    """``value`` satisfies every declared assumption of ``sym``."""
    for k, want in sym.assumptions0.items():
        if want is None:
            continue
        have = getattr(value, "is_" + k, None)
        if have is None or bool(have) != bool(want):
            return False
    return True


def values_for(sym, pool: Sequence[Any] = POOL) -> List[Any]:
    return [v for v in pool if admissible(sym, v)]


def find_model(assum, limit: int = 300, seed: int = 0, pool: Sequence[Any] = POOL) -> Optional[dict]:
    """A concrete assignment of the symbols of ``assum`` (each from the
    pool, respecting its declared assumptions) at which every conjunct
    evaluates True; None when none of at most ``limit`` assignments does
    (inconclusive).  Non-commutative symbols are left free."""
    if assum is True or assum is S.true:
        return {}
    syms = sorted((s for s in assum.free_symbols if isinstance(s, Symbol) and s.is_commutative is not False),
                  key=lambda s: (s.name, str(s.assumptions0)))
    choices = [values_for(s, pool) for s in syms]
    if any(not c for c in choices):
        return None
    total = 1
    for c in choices:
        total *= len(c)
    if total <= limit:
        assignments: Iterable = itertools.product(*choices)
    else:
        rng = random.Random(seed)
        assignments = (tuple(rng.choice(c) for c in choices) for _ in range(limit))
    for vals in assignments:
        subs = dict(zip(syms, vals))
        if evaluate_at(assum, subs) is True:
            return subs
    return None
