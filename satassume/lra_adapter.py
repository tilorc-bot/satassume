"""Turn SymPy relation atoms into :mod:`satassume.lra` payloads.

This is the only LRA module that imports SymPy.  Interpreted atoms:

* ``Q.lt/le/gt/ge/eq/ne(a, b)`` (applied predicates with two arguments),
* the Relationals ``a < b``, ``a <= b``, ``a > b``, ``a >= b``,
  ``Eq(a, b)``, ``Ne(a, b)``,
* ``Q.is_true(r)`` for such a Relational ``r``.

Rules
-----

``a - b`` is linearised structurally (no ``expand``, no simplification):
sums are split, a product with a rational numeric factor is scaled
(``2*(x + y)`` is ``2*x + 2*y``), and every other subexpression with free
symbols (``x``, ``x*y``, ``sin(x)``, ``x**2``, ``f(x)``) is an *opaque
term*, an independent real variable for the theory.  Treating a nonlinear
term as a variable is a relaxation, so it is sound (only incomplete).

The atom is not interpreted (``None``) if

* an argument is not a scalar ``Expr`` (booleans, tuples, matrices,
  matrix expressions), or the arity is not 2;
* anything in it is ``nan``, ``oo``, ``-oo`` or ``zoo`` (even inside an
  opaque term, e.g. ``x + oo`` or ``sin(x + oo)``);
* a factor of a product with free symbols is a number that is not a
  SymPy ``Rational`` (``pi*x``, ``sqrt(2)*x``, ``0.5*x``, ``I*x``): a
  constant times a symbol is nonlinear here;
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
follows (:func:`_closed`): a ``Rational`` is a constant; a sum is split and a rational factor pulled out (``3*pi/2 + 1`` is ``3/2 * pi + 1``); what is left
(``pi``, ``sqrt(2)``, ``pi**2``, ``log(2)``, ``sin(1)``, ``2**pi``) is a
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

Equalities and disequalities alone would even be sound over the complex
numbers (a rational linear system with disequalities that has a complex
solution has a real one), but order atoms need real terms, so the one rule
above covers both.
"""
from __future__ import annotations

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

from .lra import LRATheory, Negated

__all__ = ["LRAAdapter", "to_constraint", "terms", "interpret", "relation"]

_PRED = {Q.lt: "lt", Q.le: "le", Q.gt: "gt", Q.ge: "ge", Q.eq: "eq",
         Q.ne: "ne"}
_REL = {StrictLessThan: "lt", LessThan: "le", StrictGreaterThan: "gt",
        GreaterThan: "ge", Equality: "eq", Unequality: "ne"}
_BAD = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


class _Unhandled(Exception):
    pass


def relation(atom) -> tuple[str, Any, Any] | None:
    """``(name, lhs, rhs)`` for a supported relation atom, name one of
    ``lt le gt ge eq ne``; None otherwise."""
    if isinstance(atom, AppliedPredicate):
        f = atom.function
        if f == Q.is_true:
            return relation(atom.arguments[0]) if len(atom.arguments) == 1 else None
        name = _PRED.get(f)
        if name is None or len(atom.arguments) != 2:
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
        for f in e.args:
            if f.free_symbols:
                rest.append(f)
            elif f.is_Rational:
                coeff *= f
            else:
                raise _Unhandled(f)          # I*x, pi*x, 0.5*x, sqrt(2)*x
        if coeff != 1:
            _lin(Mul(*rest), scale * Fraction(int(coeff.p), int(coeff.q)),
                 out, const)
            return
        if len(rest) == 1:
            _lin(rest[0], scale, out, const)
            return
    out[e] = out.get(e, Fraction(0)) + scale


def _closed(e, scale: Fraction, out: dict, const: list) -> None:
    """``_lin`` for a subexpression without free symbols: rationals go to
    the constant, sums are split, a rational factor is pulled out, and what
    is left must be a real constant without Floats and with rigorous bounds
    (:func:`constant_bounds`); it becomes a term."""
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
    if e.has(Float):
        raise _Unhandled(e)                  # Floats: see the module docstring
    if constant_bounds(e) is None:
        raise _Unhandled(e)
    out[e] = out.get(e, Fraction(0)) + scale


#: working precision (bits) of the interval evaluation behind a constant's bounds
_IV_PREC = 128
#: constants of magnitude beyond ``2**±_MAX_BITS`` get no bounds: the
#: exact rationals would be integers of that many bits
#: (``exp(exp(exp(5)))`` is about ``2**(4e64)``)
_MAX_BITS = 4096
#: constant -> (lo, hi) or None (see constant_bounds); shared, pure
_BOUNDS: dict = {}


def constant_bounds(c):
    """Rational bounds ``(lo, hi)`` with ``lo < c < hi`` for a closed
    expression ``c`` that SymPy says is a finite (extended) real number, or
    None: not such a constant, or no rigorous bound.

    The value comes from interval arithmetic (:func:`_interval`: mpmath's
    interval context at 128 bits, outward rounded at every step, over
    rationals, pi, E, ``+``, ``*``, ``**``, exp, log, sin, cos, tan, atan);
    the interval is widened outward to rationals on a grid 72 bits below
    its magnitude.  A constant that SymPy cannot show to be zero still gets
    a narrow interval around 0.  Memoized per constant."""
    try:
        return _BOUNDS[c]
    except KeyError:
        pass
    except TypeError:
        return _bounds(c)
    if len(_BOUNDS) >= _INTERPRETED_MAX:
        _BOUNDS.clear()
    r = _BOUNDS[c] = _bounds(c)
    return r


def _bounds(c):
    iv = _interval(c)
    if iv is None:
        return None
    a, b = iv._mpi_
    lo, hi = _rational(a), _rational(b)
    top = max(_mag(a), _mag(b), -_MAX_BITS)
    q = Fraction(2) ** (top - 72)            # a coarse grid, strictly outside
    return ((lo / q).__floor__() - 1) * q, ((hi / q).__ceil__() + 1) * q


_IV = None


def _iv_context():
    global _IV
    if _IV is None:
        from mpmath.ctx_iv import MPIntervalContext
        _IV = MPIntervalContext()
        _IV.prec = _IV_PREC
    return _IV


def _rational(x) -> Fraction:
    """The exact value of a finite raw mpf (bounded by the caller)."""
    from mpmath.libmp import to_rational
    p, q = to_rational(x)
    return Fraction(p, q)


def _mag(x) -> float:
    """``k`` with ``|x| < 2**k`` for a raw mpf; -inf for zero, inf for an
    infinity or nan."""
    sign, man, exp, bc = x
    if man:
        return exp + bc
    return float("-inf") if not exp else float("inf")


def _sign(x) -> int:
    from mpmath.libmp import mpf_sign
    return mpf_sign(x)


def _interval(e):
    """An interval (mpmath, outward rounded at every step) that holds the
    real value of the closed expression ``e``, or None.

    Only rationals, pi, E, ``+``, ``*``, ``**``, exp, log, sin, cos, tan and
    atan are evaluated; a step outside its real domain (log of an interval
    that reaches 0, a fractional power of one that reaches below 0, tan
    across a pole, 1/x across 0) gives None, so a result is also a proof
    that the value is real.  Every intermediate value must stay within
    ``2**±_MAX_BITS`` (exp is checked before it is applied), so nothing huge
    is built: ``exp(exp(exp(5)))`` and ``sin(exp(exp(exp(5))))`` are None
    at once.  No error estimate of SymPy's evalf is trusted (it claims full
    accuracy for ``sign``, ``tanh``, ``tan`` next to a pole, ``log`` next to
    1)."""
    iv = _iv_context()
    from sympy import Pow, exp, log, sin, cos, tan, atan
    if e.is_Rational:
        if e.p and abs(e.p.bit_length() - e.q.bit_length()) > _MAX_BITS:
            return None
        return iv.mpf(e.p) / iv.mpf(e.q)
    if e is S.Pi:
        return iv.pi + 0
    if e is S.Exp1:
        return iv.e + 0
    head = type(e)
    if head not in (Add, Mul, Pow, exp, log, sin, cos, tan, atan):
        return None
    args = []
    for a in e.args:
        x = _interval(a)
        if x is None:
            return None
        args.append(x)
    try:
        if head is Add:
            r = args[0]
            for x in args[1:]:
                r = r + x
        elif head is Mul:
            r = args[0]
            for x in args[1:]:
                r = r * x
        elif head is Pow:
            b, x = args
            n = e.args[1]
            ba, bb = b._mpi_
            if n.is_Integer:
                if n < 0 and _sign(ba) <= 0 <= _sign(bb):
                    return None
                if abs(int(n)).bit_length() > _IV_PREC:
                    return None              # not exact at 128 bits: mpmath goes through log/exp
                r = b ** int(n)
            else:
                if _sign(ba) <= 0:
                    return None
                r = _iv_exp(x * _loose(iv.log(b)))
        elif head is exp:
            r = _iv_exp(args[0])
        elif head is log:
            if _sign(args[0]._mpi_[0]) <= 0:
                return None
            r = _loose(iv.log(args[0]))
        elif head is atan:
            from mpmath.libmp import mpf_atan
            x = args[0]
            import mpmath
            mk = mpmath.mp.make_mpf       # atan is increasing: round the ends outward
            xa, xb = args[0]._mpi_
            r = _loose(iv.mpf([mk(mpf_atan(xa, _IV_PREC, "f")), mk(mpf_atan(xb, _IV_PREC, "c"))]))
        else:
            r = _loose({sin: iv.sin, cos: iv.cos, tan: iv.tan}[head](args[0]))
    except Exception:                        # noqa: BLE001 - a step mpmath refuses decides nothing
        return None
    if r is None or type(r) is not type(args[0]):
        return None                          # complex
    a, b = r._mpi_
    if max(_mag(a), _mag(b)) > _MAX_BITS:
        return None                          # huge, infinite or nan
    if (a[1] and _mag(a) < -_MAX_BITS) or (b[1] and _mag(b) < -_MAX_BITS):
        # a tiny end moves outward to 0 or 2**-_MAX_BITS: its exact rational
        # would be huge (``pi**-(10**9)``, ``tan(22)**(10**100)``)
        from mpmath.libmp import fzero
        if a[1] and _mag(a) < -_MAX_BITS:
            a = (1, 1, -_MAX_BITS, 1) if a[0] else fzero
        if b[1] and _mag(b) < -_MAX_BITS:
            b = fzero if b[0] else (0, 1, -_MAX_BITS, 1)
        r = _IV.make_mpf((a, b))
    return r


def _loose(r):
    """``r`` widened outward by ``2**-120`` relative at each end.  mpmath's
    exp, log, atan, sin, cos and tan round an approximation (a few units in
    the last place at 10 to 30 guard bits) in the requested direction,
    which is wrong when the true value is that close to a 128-bit number:
    ``exp(891)`` and ``log(156434)`` come out with an upper end below the
    value, and a cancelling parent (``pi*(log(156434) - Y)``) exposes it."""
    from mpmath.libmp import mpf_abs, mpf_add, mpf_shift, mpf_sub
    a, b = r._mpi_
    a = mpf_sub(a, mpf_shift(mpf_abs(a), -120), _IV_PREC, "f")
    b = mpf_add(b, mpf_shift(mpf_abs(b), -120), _IV_PREC, "c")
    return _IV.make_mpf((a, b))


def _iv_exp(x):
    # exp of anything beyond about 2839 in size would be beyond 2**±4096;
    # the check allows |x| < 2048
    if x is None or max(_mag(x._mpi_[0]), _mag(x._mpi_[1])) > 11:
        return None                          # |x| >= 2048
    return _loose(_IV.exp(x))


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
    except (_Unhandled, TypeError, ValueError):
        return None
    return _constraint(rel[0], form, k), sorted(form, key=default_sort_key)


def terms(atom) -> list | None:
    """The opaque terms of ``atom`` (including ones that cancel, e.g.
    ``[x]`` for ``Q.lt(x, x + 1)``), in a canonical order; ``[]`` for a
    purely numeric relation; None if the atom is not interpreted."""
    r = interpret(atom)
    return None if r is None else r[1]


#: atom -> interpret(atom), shared by every adapter (keyed by the SymPy
#: atom itself: equal atoms linearise identically)
_INTERPRETED: dict = {}
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
        if self._solver is not solver:
            if self._solver is not None:
                raise ValueError("an LRAAdapter serves a single solver")
            if not any(t is self.theory for t in solver.theories()):
                solver.attach_theory(self.theory)
            self._solver = solver
        solver.register_atom(self.theory, var, payload)
        self._shared.update(atom_terms)
        return True

    def interpret(self, atom):
        """``(constraint, terms)`` in one call (see :func:`interpret`),
        memoized across adapters: it is a pure function of the atom (the
        result is shared, never mutate it)."""
        try:
            return _INTERPRETED[atom]
        except KeyError:
            if len(_INTERPRETED) >= _INTERPRETED_MAX:
                _INTERPRETED.clear()
            r = _INTERPRETED[atom] = interpret(atom)
            return r
        except TypeError:                   # unhashable: do not cache
            return interpret(atom)

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
