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

__all__ = ["LRAAdapter", "to_constraint", "terms", "interpret", "relation",
           "integer_form"]

_PRED = {Q.lt: "lt", Q.le: "le", Q.gt: "gt", Q.ge: "ge", Q.eq: "eq",
         Q.ne: "ne"}
_REL = {StrictLessThan: "lt", LessThan: "le", StrictGreaterThan: "gt",
        GreaterThan: "ge", Equality: "eq", Unequality: "ne"}
_BAD = (S.NaN, S.Infinity, S.NegativeInfinity, S.ComplexInfinity)


class _Unhandled(Exception):
    pass


_ZERO = Fraction(0)
_ONE = Fraction(1)


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


def _lin(e, scale: Fraction, out: list, const: list) -> None:
    """Append the contributions of ``scale * e``: ``(term, coefficient)``
    pairs to ``out`` and constants to ``const``, in reading order (see
    :func:`_parts`)."""
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
    out.append((e, scale))


def _closed(e, scale, out: list, const: list) -> None:
    """``_lin`` for a subexpression without free symbols: rationals go to
    the constant, sums are split, a rational factor is pulled out; a
    number of the exact field (:func:`satassume.constfield.from_sympy`:
    ``pi``, ``3*pi/2``, ``1/pi``, ``E**2``, ``sqrt(2)``) goes to the
    constant too; what is left must be a real constant without Floats and
    with rigorous bounds (:func:`constant_bounds`); it becomes a term."""
    if e.is_Rational:
        const.append(scale * Fraction(int(e.p), int(e.q)))
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
        const.append(scale * v)
        return
    if e.has(Float):
        raise _Unhandled(e)                  # Floats: see the module docstring
    if constant_bounds(e) is None:
        raise _Unhandled(e)
    out.append((e, scale))


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


#: precision -> mpmath interval context at that precision
_IV: dict = {}


def _iv_context(prec: int = _IV_PREC):
    ctx = _IV.get(prec)
    if ctx is None:
        from mpmath.ctx_iv import MPIntervalContext
        ctx = _IV[prec] = MPIntervalContext()
        ctx.prec = prec
    return ctx


#: (constant, working precision) -> rational enclosure or None
_ENCLOSURES: dict = {}


def constant_enclosure(c, prec: int):
    """Rational ``(lo, hi)`` with ``lo <= c <= hi`` and ``hi - lo`` about
    ``2**-prec`` relative, for a closed constant with
    :func:`constant_bounds` (None otherwise): the interval evaluation of
    :func:`_interval` at working precision ``prec + 16`` bits, rounded
    outward.  Used to refine a constant of :mod:`satassume.constfield`
    beyond the 128 bits of its bounds."""
    key = (c, prec)
    try:
        return _ENCLOSURES[key]
    except KeyError:
        pass
    except TypeError:
        return _enclosure(c, prec)
    if len(_ENCLOSURES) >= _INTERPRETED_MAX:
        _ENCLOSURES.clear()
    r = _ENCLOSURES[key] = _enclosure(c, prec)
    return r


def _enclosure(c, prec: int):
    if constant_bounds(c) is None:           # also: SymPy says a finite real
        return None
    iv = _interval(c, max(prec + 16, _IV_PREC))
    if iv is None:
        return None
    a, b = iv._mpi_
    return _rational(a), _rational(b)


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


def _interval(e, prec: int = _IV_PREC):
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
    iv = _iv_context(prec)
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
        x = _interval(a, prec)
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
                if abs(int(n)).bit_length() > prec:
                    return None              # not exact at this precision: mpmath goes through log/exp
                r = b ** int(n)
            else:
                if _sign(ba) <= 0:
                    return None
                r = _iv_exp(x * _loose(iv.log(b), prec), prec)
        elif head is exp:
            r = _iv_exp(args[0], prec)
        elif head is log:
            if _sign(args[0]._mpi_[0]) <= 0:
                return None
            r = _loose(iv.log(args[0]), prec)
        elif head is atan:
            from mpmath.libmp import mpf_atan
            x = args[0]
            import mpmath
            mk = mpmath.mp.make_mpf       # atan is increasing: round the ends outward
            xa, xb = args[0]._mpi_
            r = _loose(iv.mpf([mk(mpf_atan(xa, prec, "f")), mk(mpf_atan(xb, prec, "c"))]), prec)
        else:
            r = _loose({sin: iv.sin, cos: iv.cos, tan: iv.tan}[head](args[0]), prec)
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
        r = iv.make_mpf((a, b))
    return r


def _loose(r, prec: int = _IV_PREC):
    """``r`` widened outward by ``2**(8 - prec)`` relative at each end
    (``2**-120`` at the 128 bits of :func:`constant_bounds`).  mpmath's
    exp, log, atan, sin, cos and tan round an approximation (a few units in
    the last place at 10 to 30 guard bits) in the requested direction,
    which is wrong when the true value is that close to a 128-bit number:
    ``exp(891)`` and ``log(156434)`` come out with an upper end below the
    value, and a cancelling parent (``pi*(log(156434) - Y)``) exposes it."""
    from mpmath.libmp import mpf_abs, mpf_add, mpf_shift, mpf_sub
    a, b = r._mpi_
    a = mpf_sub(a, mpf_shift(mpf_abs(a), 8 - prec), prec, "f")
    b = mpf_add(b, mpf_shift(mpf_abs(b), 8 - prec), prec, "c")
    return _iv_context(prec).make_mpf((a, b))


def _iv_exp(x, prec: int = _IV_PREC):
    # exp of anything beyond about 2839 in size would be beyond 2**±4096;
    # the check allows |x| < 2048
    if x is None or max(_mag(x._mpi_[0]), _mag(x._mpi_[1])) > 11:
        return None                          # |x| >= 2048
    return _loose(_iv_context(prec).exp(x), prec)


def _form(terms, form=None) -> dict:
    """The linear form ``{term: coefficient}`` of the contributions
    ``terms`` (:func:`_lin`), summed in order onto ``form``."""
    if form is None:
        form = {}
    get = form.get
    for t, c in terms:
        form[t] = get(t, _ZERO) + c
    return form


def _parts(e):
    """``(form, const, terms, consts)`` for an expression ``e`` (an
    ``Expr``): the contributions :func:`_lin` reads off ``e`` at scale 1,
    ``terms`` (``(term, coefficient)`` pairs) and ``consts``, in reading
    order, and their sums ``form`` (:func:`_form`) and ``const``; None when
    reading raises one of ``_UNREAD``.  Memoized per expression in
    :data:`_INTERPRETED` under the flag (never mutate the result): every
    relation atom about ``e`` (the links ``0 < e``, ``e < 0``, ``e = 0``,
    their order sides, ``Q.integer(e)``, the budget's cone) reads it once.

    Composing the memoized parts gives exactly what one :func:`_lin` pass
    over both sides of a relation gives: the same coefficients (the
    arithmetic is exact, and :mod:`satassume.constfield` numbers have a
    normal form) in the same dict order (the left side's terms first, then
    the right side's new ones, each in reading order)."""
    memo = _INTERPRETED[GENERIC_CONSTANTS]
    key = ("lin", e)
    try:
        return memo[key]
    except KeyError:
        pass
    terms: list = []
    consts: list = []
    try:
        _lin(e, _ONE, terms, consts)
    except _UNREAD:
        r = None
    else:
        const = _ZERO
        for v in consts:
            const += v
        r = (_form(terms), const, terms, consts)
    if len(memo) >= _INTERPRETED_MAX:
        memo.clear()
    memo[key] = r
    return r


def _bad(e) -> bool:
    """``e.has(*_BAD)`` for an ``Expr``, memoized like :func:`_parts`."""
    memo = _INTERPRETED[GENERIC_CONSTANTS]
    key = ("bad", e)
    r = memo.get(key)
    if r is None:
        r = e.has(*_BAD)
        if len(memo) >= _INTERPRETED_MAX:
            memo.clear()
        memo[key] = r
    return r


def _sort_key(t):
    """``default_sort_key(t)``, memoized like :func:`_parts`."""
    memo = _INTERPRETED[GENERIC_CONSTANTS]
    key = ("sort", t)
    r = memo.get(key)
    if r is None:
        r = default_sort_key(t)
        if len(memo) >= _INTERPRETED_MAX:
            memo.clear()
        memo[key] = r
    return r


def _linear(name, lhs, rhs):
    """``(form, constant)`` with form ``{term: coeff}`` (zeros kept) for
    ``lhs - rhs``; raises _Unhandled."""
    for side in (lhs, rhs):
        if not isinstance(side, Expr) or _bad(side):
            raise _Unhandled(side)
    a = _parts(lhs)
    if a is None:
        raise _Unhandled(lhs)
    b = _parts(rhs)
    if b is None:
        raise _Unhandled(rhs)
    form = dict(a[0])
    get = form.get
    for t, c in b[2]:
        form[t] = get(t, _ZERO) + -c
    const = a[1]
    for v in b[3]:
        const += -v
    return form, const


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
                   key=lambda tc: _sort_key(tc[0]))
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
    return c, sorted(form, key=_sort_key)


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
    args = Add.make_args(e)
    if not any(t is S.Infinity or t is S.NegativeInfinity for t in args):
        # no oo summand: the form of e itself (the same reading, term by
        # term, and the same checks)
        if _bad(e):
            raise _Unhandled(e)
        p = _parts(e)
        if p is None:
            raise _Unhandled(e)
        return p[0], 0
    inf = 0
    out: list = []
    const: list = []
    for t in args:
        if t is S.Infinity or t is S.NegativeInfinity:
            sign = 1 if t is S.Infinity else -1
            if inf and inf != sign:
                raise _Unhandled(e)              # oo - oo does not stay unevaluated
            inf = sign
            continue
        if t.has(*_BAD):
            raise _Unhandled(t)
        _lin(t, _ONE, out, const)
    return _form(out), inf


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
    if not isinstance(e, Expr) or _bad(e):
        return None
    p = _parts(e)
    if p is None:
        return None
    form, const = p[0], p[1]
    try:
        keys = sorted(form, key=_sort_key)
        items = tuple((t, form[t]) for t in keys if form[t])
        # decide here what callers read (offset nonzero, unit coefficient):
        # an undecidable constant reads as "not read" (no integrality
        # link, a relaxation) instead of raising Undecided later
        bool(const)
        for _t, c in items:
            bool(c == 1)
    except _UNREAD:
        return None
    return Integral(items, const), keys


#: ``GENERIC_CONSTANTS -> {atom -> interpret(atom)}`` (and the
#: ``order_sides`` and ``integer_form`` results), shared by every adapter:
#: keyed by the SymPy atom itself (equal atoms linearise identically) and,
#: through the outer dict, by the flag the results were computed under, so
#: flipping the flag never serves the other value's linearisations.  One
#: memo per flag value keeps a lookup at one more index.  A
#: ``defaultdict``, so emptying the outer dict (the harness's
#: ``reset_module_state`` does ``_INTERPRETED.clear()``) leaves it usable.
_INTERPRETED: dict = defaultdict(dict)
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
