"""Turn SymPy relation atoms into :mod:`satassume.lra` payloads.

This is the only LRA module that imports SymPy.  Interpreted atoms:

* ``Q.lt/le/gt/ge/eq/ne(a, b)`` (applied predicates with two arguments),
* the Relationals ``a < b``, ``a <= b``, ``a > b``, ``a >= b``,
  ``Eq(a, b)``, ``Ne(a, b)``,
* ``Q.is_true(r)`` for such a Relational ``r``.

Rules
-----

``a - b`` is linearised structurally (no ``expand``, no simplification):
sums are split, a product with a numeric factor is scaled (``2*(x + y)``
is ``2*x + 2*y``; the factor may involve constants: ``pi*x``, ``x/pi``,
``x*(pi + 1)``, ``sqrt(2)*x`` have the exact coefficients ``pi``,
``1/pi``, ``pi + 1``, ``sqrt(2)`` of :mod:`satassume.constfield`), and
every other subexpression with free
symbols (``x``, ``x*y``, ``sin(x)``, ``x**2``, ``f(x)``) is an *opaque
term*, an independent real variable for the theory.  Treating a nonlinear
term as a variable is a relaxation, so it is sound (only incomplete).

The atom is not interpreted (``None``) if

* an argument is not a scalar ``Expr`` (booleans, tuples, matrices,
  matrix expressions), or the arity is not 2;
* anything in it is ``nan``, ``oo``, ``-oo`` or ``zoo`` (even inside an
  opaque term, e.g. ``x + oo`` or ``sin(x + oo)``); an order atom with an
  ``oo`` or ``-oo`` summand is read by :func:`order_sides` instead;
* a factor of a product with free symbols is a number that is no number
  of the exact field (``0.5*x``, ``I*x``; ``log(2)*x`` without
  :data:`GENERIC_CONSTANTS`);
* a coefficient's sign cannot be decided, or the arithmetic exceeds the
  field's size budget (:class:`satassume.constfield.Undecided`: a formal
  expression whose value is 0, ``((1 + sqrt(2))**2 - 3 - 2*sqrt(2))*x``);
* a subexpression without free symbols is none of the readable constants
  below (``I``, ``I*pi``, ``f(1)``, ``AccumBounds(0, 1)``, anything SymPy
  does not know to be a finite real, or that interval arithmetic over
  rationals, pi, E, +, *, **, exp, log, sin, cos, tan and atan cannot bound);
* it holds a ``Float`` anywhere in a closed subexpression (``x < 0.5``,
  ``x < 0.5*pi``).  SymPy has no single meaning for a Float in a relation:
  ``Float(0.1) > Rational(1, 10)`` is True (exact binary value) while
  ``Eq(Float(0.1), Rational(1, 10))`` is True as well (equality at the
  Float's precision), and ``sympy.ask(Q.gt(0.1, 1/10))`` is False.  Reading
  a Float either way would contradict SymPy somewhere, so it stays
  unreadable.

Constants
---------
A subexpression without free symbols in a linear position is read as
follows (:func:`_closed`): a ``Rational`` is a constant; a sum is split
and a rational factor pulled out; a number of the exact field
(:func:`satassume.constfield.from_sympy`: ``pi``, ``E``, ``exp(n)``,
rational powers of rationals such as ``sqrt(2)``, with ``+ - * /`` and
integer powers: ``3*pi/2 + 1``, ``pi**2``, ``1/(pi + E)``) is part of the
constant, exact (``x/pi + 1/2`` at ``x = -pi/2`` is exactly 0).  With
:data:`GENERIC_CONSTANTS` (the default) so is every other closed real
constant with rigorous bounds (``log(2)``, ``sin(1)``, ``2**pi``): an
indeterminate of the field, enclosed at any precision by
:func:`constant_enclosure`.  Without it, what is
left (``log(2)``, ``sin(1)``, ``2**pi``) is a
*constant term* if SymPy says it is a finite real (``is_extended_real``
and ``is_finite`` True) and :func:`constant_bounds` finds rational bounds
``lo < c < hi``.  A constant term is a theory variable like an opaque term
(the same expression, the same variable, so ``pi/2`` and ``3*pi`` share
``pi``); the engine asserts its bounds once per session
(:meth:`LRAAdapter.register_bounds`, ``Relations._bound``).  Sound: the
constant's value satisfies every asserted bound.  Comparisons closer than
the bounds' width (about 2**-70 relative) stay undecided; distinct
spellings of one value (``log(8)/log(2)`` and ``3``) are unrelated
variables, which is a relaxation.

No SymPy assumptions are consulted about terms with free symbols.
**The caller vouches that every opaque
term (see :func:`terms`) is a finite real**: the theory reads
``not (a < b)`` as ``a >= b`` and ``Q.lt(x, x + 1)`` as true, which is only
right for finite reals.  The engine guarantees this with bridge clauses
``real(u1) & ... & real(uk) -> (atom <-> theory atom)``.  That is why
:func:`terms` includes terms that cancel (``x`` in ``Q.lt(x, x + 1)``).

Extended reals
--------------
Order relations are over the extended reals (see
:mod:`satassume.relations`, "Meaning"): the theory atom above is exact
only when every term is a finite real, which is what the guard ensures.
For the other cases :func:`order_sides` gives the engine each side of
``Q.lt(a, b)`` separately, as a linear form over the same opaque terms
plus the sign of an ``oo`` or ``-oo`` summand (``x + oo``, ``oo``,
``2*y - oo``); the engine reads the atom's value off the terms' infinity
facts and the coefficients' signs.  Anything else infinite (``oo*x``,
``sin(x + oo)``, ``zoo``, ``nan``) stays unread.

Integrality
-----------
:func:`integer_form` reads ``Q.integer(e)`` for a scalar ``e`` like one
side of a relation: ``e`` as ``sum(c*u) + k`` over the same opaque terms and
constant terms, as an :class:`satassume.lra.Integral` payload.  The engine
registers it under the same kind of guard (every opaque term a finite
real, then ``e`` is exactly that form, and ``Q.integer(e)`` holds iff the
form's value is an integer; see :meth:`satassume.relations.Relations._link_integer`).

Equalities and disequalities alone would even be sound over the complex
numbers (a rational linear system with disequalities that has a complex
solution has a real one), but order atoms need real terms, so the one rule
above covers both.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from typing import Any

from sympy import Float, Rational, S
from sympy.assumptions.assume import AppliedPredicate
from sympy.assumptions.ask import Q
from sympy.core.add import Add
from sympy.core.expr import Expr
from sympy.core.mul import Mul
from sympy.core.relational import (Equality, GreaterThan, LessThan,
                                   StrictGreaterThan, StrictLessThan,
                                   Unequality)
from sympy.core.sorting import default_sort_key

from .constfield import Undecided, from_sympy
from .lra import Integral, LRATheory, Negated
from .memos import adopt as _adopt_memo

__all__ = ["LRAAdapter", "to_constraint", "terms", "interpret", "relation",
           "integer_form"]

_PRED = {Q.lt: "lt", Q.le: "le", Q.gt: "gt", Q.ge: "ge", Q.eq: "eq",
         Q.ne: "ne"}
_REL = {StrictLessThan: "lt", LessThan: "le", StrictGreaterThan: "gt",
        GreaterThan: "ge", Equality: "eq", Unequality: "ne"}
_BAD = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


class _Unhandled(Exception):
    pass


#: read every closed real constant that has rigorous bounds as a number of
#: the exact field (``log(2)*x`` readable, ``x < log(2)`` exact); False:
#: only pi, E and rational powers of rationals (with ``+ - * /``), other
#: constants stay bounded terms (see "Constants").  A bool; it may change
#: at run time: the process-wide memo (:data:`_INTERPRETED`) is keyed on it
GENERIC_CONSTANTS = True

#: what reading can raise besides _Unhandled: undecidable signs of
#: coefficients with constants, and the size budget (satassume.constfield)
_UNREAD = (_Unhandled, TypeError, ValueError, Undecided, ZeroDivisionError)


def relation(atom) -> tuple[str, Any, Any] | None:
    """``(name, lhs, rhs)`` for a supported relation atom, name one of
    ``lt le gt ge eq ne``; None otherwise."""
    if isinstance(atom, AppliedPredicate):
        f = atom.function
        name = _PRED.get(f)
        if name is None:
            # by name: reading ``Q.is_true`` imports SymPy's handler modules
            # (about 1 ms, once per process) for every relation atom.  Only
            # ``Q.is_true`` matches: ``Predicate("is_true")`` is a different
            # object (an UndefinedPredicate whose ``.name`` is a ``Str``, not
            # equal to the string), so this behaves like ``f == Q.is_true``
            if getattr(f, "name", None) == "is_true":
                return relation(atom.arguments[0]) if len(atom.arguments) == 1 else None
            return None
        if len(atom.arguments) != 2:
            return None
        return (name,) + tuple(atom.arguments)
    name = _REL.get(type(atom))
    if name is None:
        return None
    return name, atom.lhs, atom.rhs


def _lin(e, scale: Fraction, out: dict, const: list) -> None:
    """Add ``scale * e`` to the linear form ``out`` (term -> coefficient)
    and ``const[0]``."""
    if not isinstance(e, Expr) or getattr(e, "is_Matrix", False) \
            or getattr(e, "is_MatrixExpr", False):
        raise _Unhandled(e)
    if not e.free_symbols:
        _closed(e, scale, out, const)
        return
    if e.is_Add:
        for a in e.args:
            _lin(a, scale, out, const)
        return
    if e.is_Mul:
        coeff = S.One
        rest = []
        closed = []
        for f in e.args:
            if f.free_symbols:
                rest.append(f)
            elif f.is_Rational:
                coeff *= f
            else:
                closed.append(f)             # pi, 1/pi, pi + 1, sqrt(2); I, 0.5
        if closed:
            c = from_sympy(Mul(*closed), generic=GENERIC_CONSTANTS)
            if c is None:
                raise _Unhandled(e)          # I*x, 0.5*x, log(2)*x (see GENERIC_CONSTANTS)
            c = c * Fraction(int(coeff.p), int(coeff.q))
            _lin(Mul(*rest), scale * c, out, const)
            return
        if coeff != 1:
            _lin(Mul(*rest), scale * Fraction(int(coeff.p), int(coeff.q)),
                 out, const)
            return
        if len(rest) == 1:
            _lin(rest[0], scale, out, const)
            return
    out[e] = out.get(e, Fraction(0)) + scale


def _closed(e, scale, out: dict, const: list) -> None:
    """``_lin`` for a subexpression without free symbols: rationals go to
    the constant, sums are split, a rational factor is pulled out; a
    number of the exact field (:func:`satassume.constfield.from_sympy`:
    ``pi``, ``3*pi/2``, ``1/pi``, ``E**2``, ``sqrt(2)``) goes to the
    constant too; what is left must be a real constant without Floats and
    with rigorous bounds (:func:`constant_bounds`); it becomes a term."""
    if e.is_Rational:
        const[0] += scale * Fraction(int(e.p), int(e.q))
        return
    if e.is_Add:
        for a in e.args:
            _closed(a, scale, out, const)
        return
    c, rest = e.as_coeff_Mul()
    if rest is not e and c != 1 and c.is_Rational:
        _closed(rest, scale * Fraction(int(c.p), int(c.q)), out, const)
        return
    v = from_sympy(e, generic=GENERIC_CONSTANTS)
    if v is not None:
        const[0] += scale * v
        return
    if e.has(Float):
        raise _Unhandled(e)                  # Floats: see the module docstring
    if constant_bounds(e) is None:
        raise _Unhandled(e)
    out[e] = out.get(e, Fraction(0)) + scale


def constant_bounds(c):
    """Rational bounds ``(lo, hi)`` with ``lo < c < hi`` for a closed
    constant, or None (:func:`satassume.lra_bounds.constant_bounds`; that
    module is loaded by the first query with such a constant)."""
    from .lra_bounds import constant_bounds
    return constant_bounds(c)


def constant_enclosure(c, prec: int):
    """:func:`satassume.lra_bounds.constant_enclosure`."""
    from .lra_bounds import constant_enclosure
    return constant_enclosure(c, prec)


def _linear(name, lhs, rhs):
    """``(form, constant)`` with form ``{term: coeff}`` (zeros kept) for
    ``lhs - rhs``; raises _Unhandled."""
    for side in (lhs, rhs):
        if not isinstance(side, Expr) or side.has(*_BAD):
            raise _Unhandled(side)
    form: dict = {}
    const = [Fraction(0)]
    _lin(lhs, Fraction(1), form, const)
    _lin(rhs, Fraction(-1), form, const)
    return form, const[0]


def to_constraint(atom):
    """Interpret ``atom``.

    Returns ``(payload, positive)`` where ``payload`` is an
    :mod:`satassume.lra` record ``(terms, constant, strict, equality)`` and
    ``positive`` is False when the atom is the negation of the payload
    (``Q.ne``/``Ne``); ``True``/``False`` when the relation has no terms
    left (its value for all finite reals); None when not interpreted.

    ``Q.lt(x, y)`` and ``Q.gt(y, x)`` give equal payloads, as do
    ``Q.eq(x, y)`` and ``Q.eq(y, x)``.
    """
    r = interpret(atom)
    return None if r is None else r[0]


def _constraint(name, form, k):
    if name in ("gt", "ge"):                 # a > b  <=>  b - a < 0
        form = {t: -c for t, c in form.items()}
        k = -k
        name = "lt" if name == "gt" else "le"
    items = sorted(((t, c) for t, c in form.items() if c),
                   key=lambda tc: default_sort_key(tc[0]))
    if name in ("eq", "ne") and items and items[0][1] < 0:
        items = [(t, -c) for t, c in items]
        k = -k
    positive = name != "ne"
    # sum(items) + k OP 0  <=>  sum(items) OP -k
    if not items:
        value = {"lt": k < 0, "le": k <= 0, "eq": k == 0, "ne": k != 0}[name]
        return value
    payload = (tuple(items), -k, name == "lt", name in ("eq", "ne"))
    return payload, positive


def interpret(atom):
    """``(to_constraint(atom), terms(atom))`` from a single linearisation,
    or None when the atom is not interpreted."""
    rel = relation(atom)
    if rel is None:
        return None
    try:
        form, k = _linear(*rel)
        c = _constraint(rel[0], form, k)
    except _UNREAD:
        return None
    return c, sorted(form, key=default_sort_key)


def terms(atom) -> list | None:
    """The opaque terms of ``atom`` (including ones that cancel, e.g.
    ``[x]`` for ``Q.lt(x, x + 1)``), in a canonical order; ``[]`` for a
    purely numeric relation; None if the atom is not interpreted."""
    r = interpret(atom)
    return None if r is None else r[1]


def _side(e):
    """``(form, inf)`` for one side of an order atom: the linear form of
    ``e`` without its ``oo``/``-oo`` summand, and that summand's sign (+1,
    -1, or 0 for none); raises _Unhandled."""
    if not isinstance(e, Expr) or getattr(e, "is_Matrix", False) \
            or getattr(e, "is_MatrixExpr", False):
        raise _Unhandled(e)
    inf = 0
    form: dict = {}
    const = [Fraction(0)]
    for t in Add.make_args(e):
        if t is S.Infinity or t is S.NegativeInfinity:
            sign = 1 if t is S.Infinity else -1
            if inf and inf != sign:
                raise _Unhandled(e)              # oo - oo does not stay unevaluated
            inf = sign
            continue
        if t.has(*_BAD):
            raise _Unhandled(t)
        _lin(t, Fraction(1), form, const)
    return form, inf


def order_sides(atom):
    """``((form_a, inf_a), (form_b, inf_b))`` for an order atom
    ``Q.lt(a, b)`` (or ``a < b``): per side the linear form (term ->
    rational coefficient, zeros kept, the rational constant dropped) and
    the sign of its ``oo`` summand (+1 for ``oo``, -1 for ``-oo``, 0 for
    none).  None when a side is not read (as :func:`interpret`, except
    that an ``oo`` or ``-oo`` summand is allowed) or the atom is no
    ``lt``.  The terms are those of :func:`terms` for an atom without
    infinities."""
    rel = relation(atom)
    if rel is None or rel[0] != "lt":
        return None
    try:
        return _side(rel[1]), _side(rel[2])
    except _UNREAD:
        return None


def integer_form(e):
    """``(payload, terms)`` for ``Q.integer(e)``: an
    :class:`~satassume.lra.Integral` payload for the linear form of ``e``
    and its opaque terms (as :func:`terms`); None when ``e`` is not read
    (as a side of :func:`interpret`: no ``oo``, ``nan``, ``Float``,
    non-rational factor of a symbol, ...)."""
    if not isinstance(e, Expr) or e.has(*_BAD):
        return None
    form: dict = {}
    const = [Fraction(0)]
    try:
        _lin(e, Fraction(1), form, const)
        keys = sorted(form, key=default_sort_key)
        items = tuple((t, form[t]) for t in keys if form[t])
        # decide here what callers read (offset nonzero, unit coefficient):
        # an undecidable constant reads as "not read" (no integrality
        # link, a relaxation) instead of raising Undecided later
        bool(const[0])
        for _t, c in items:
            bool(c == 1)
    except _UNREAD:
        return None
    return Integral(items, const[0]), keys


#: ``GENERIC_CONSTANTS -> {atom -> interpret(atom)}`` (and the
#: ``order_sides`` and ``integer_form`` results), shared by every adapter:
#: keyed by the SymPy atom itself (equal atoms linearise identically) and,
#: through the outer dict, by the flag the results were computed under, so
#: flipping the flag never serves the other value's linearisations.  One
#: memo per flag value keeps a lookup at one more index.  A
#: ``defaultdict``, so emptying the outer dict (the harness's
#: ``reset_module_state`` does ``_INTERPRETED.clear()``) leaves it usable.
_INTERPRETED: dict = defaultdict(dict)
_adopt_memo(__name__, "_INTERPRETED")
#: size bound of each memo; a module constant, not a setting: changing it at run time is unsupported (answers memoized under the old value are kept)
_INTERPRETED_MAX = 100_000


class LRAAdapter:
    """Registers SymPy relation atoms with one :class:`LRATheory`.

    ``register(solver, var, atom)`` interprets ``atom``; on success it
    attaches the theory to ``solver`` (first time only; an adapter serves
    one solver, a second one raises ValueError), registers solver
    variable ``var`` for it and returns True.  A relation without terms is
    registered as a ground atom (the theory fixes its value).  ``Q.ne`` is
    accepted too (``var`` then means the disequality).  Returns False, and
    registers nothing, when the atom is not interpreted.
    """

    def __init__(self, theory: LRATheory | None = None) -> None:
        self.theory = theory if theory is not None else LRATheory()
        self._solver = None
        self._shared: set = set()

    def register(self, solver, var: int, atom, interpreted=None) -> bool:
        """``interpreted``: optionally the result of :func:`interpret`
        for ``atom`` already at hand (saves a second linearisation).

        An adapter owns one theory and so serves a single solver: a
        second solver raises ValueError (the theory's bounds would leak
        between them)."""
        it = self.interpret(atom) if interpreted is None else interpreted
        if it is None:
            return False
        r, atom_terms = it
        if r is True or r is False:
            payload: Any = ((), Fraction(0) if r else Fraction(-1), False, False)
        else:
            payload, positive = r
            if not positive:
                payload = Negated(payload)
        self._attach(solver)
        solver.register_atom(self.theory, var, payload)
        self._shared.update(atom_terms)
        return True

    def _attach(self, solver) -> None:
        if self._solver is not solver:
            if self._solver is not None:
                raise ValueError("an LRAAdapter serves a single solver")
            if not any(t is self.theory for t in solver.theories()):
                solver.attach_theory(self.theory)
            self._solver = solver

    def interpret(self, atom):
        """``(constraint, terms)`` in one call (see :func:`interpret`),
        memoized across adapters: it is a pure function of the atom (the
        result is shared, never mutate it)."""
        memo = _INTERPRETED[GENERIC_CONSTANTS]
        try:
            return memo[atom]
        except KeyError:
            if len(memo) >= _INTERPRETED_MAX:
                memo.clear()
            r = memo[atom] = interpret(atom)
            return r
        except TypeError:                   # unhashable: do not cache
            return interpret(atom)

    def order_sides(self, atom):
        """:func:`order_sides`, memoized like :meth:`interpret`."""
        key = ("sides", atom)
        memo = _INTERPRETED[GENERIC_CONSTANTS]
        try:
            return memo[key]
        except KeyError:
            if len(memo) >= _INTERPRETED_MAX:
                memo.clear()
            r = memo[key] = order_sides(atom)
            return r
        except TypeError:
            return order_sides(atom)

    def integer_form(self, e):
        """:func:`integer_form`, memoized like :meth:`interpret`."""
        key = ("integer", e)
        memo = _INTERPRETED[GENERIC_CONSTANTS]
        try:
            return memo[key]
        except KeyError:
            if len(memo) >= _INTERPRETED_MAX:
                memo.clear()
            r = memo[key] = integer_form(e)
            return r
        except TypeError:
            return integer_form(e)

    def register_integer(self, solver, var, form) -> None:
        """Register ``var`` for the ``Integral`` payload of ``form`` (a
        result of :meth:`integer_form`), attaching the theory to ``solver``
        as :meth:`register` does.  Its terms are not shared terms: an
        integrality atom alone connects nothing."""
        self._attach(solver)
        solver.register_atom(self.theory, var, form[0])

    def terms(self, atom) -> list | None:
        """:func:`terms` through the cache; None: not interpreted."""
        r = self.interpret(atom)
        return None if r is None else r[1]

    def to_constraint(self, atom):
        """:func:`to_constraint` through the cache."""
        r = self.interpret(atom)
        return None if r is None else r[0]

    def register_bounds(self, solver, term, new_var) -> list:
        """Register the bounds ``lo < term < hi`` of a constant term
        (:func:`constant_bounds`) on fresh variables ``new_var()``; returns
        those variables, to be asserted true (``[]`` for any other term).
        The caller does this once per solver and term."""
        b = constant_bounds(term) if not term.free_symbols else None
        if b is None:
            return []
        lo, hi = b
        out = []
        for payload in ((((term, Fraction(-1)),), -lo, True, False),   # -c < -lo
                        (((term, Fraction(1)),), hi, True, False)):     # c < hi
            v = new_var()
            solver.register_atom(self.theory, v, payload)
            out.append(v)
        return out

    def shared_terms(self) -> set:
        """Every opaque term of every atom registered through this adapter."""
        return set(self._shared)
