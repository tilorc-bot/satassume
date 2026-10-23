"""Every compiled rule of the families of rows is true at concrete points
(#249).

The rows (``satassume/knowledge/templates/<family>.py``) are compiled into
``templates/_compiled_rows.py``: per function, rules ``(premises,
conclusion)`` over literals ``(slot, predicate, sign)``, the slots being
the arguments, then the node, then the terms ``args[i] + c``
(``_rows.compile_rows``).  This test evaluates every rule at every choice
of arguments from a fixed pool of numbers:

* the node is the value SymPy gives ``head(*args)`` (the rows follow its
  conventions: ``zoo`` at a pole, its values at the infinities); the terms
  ``x + c`` are built by ``functions.shifted``, as the templates do;
  ``RoundFunction``, a base class without a value, is checked through its
  subclasses ``floor`` and ``ceiling``;
* a literal is decided by satassume's meaning of its predicate: the basis
  predicates of ``knowledge/rules.py`` (``BASIS``) are decided for the value
  (:func:`basis`), the others through ``DEFINITIONS``, in Kleene's
  three-valued logic.  Exactly for a rational, a Gaussian rational and the
  infinities; ``nan`` is no number (every predicate implying a number is
  False, ``finite`` is unknown), and for any other finite number
  numerically, from ``evalf(30)``: a part ``evalf`` cannot tell from 0 is
  0, integrality is decided only away from an integer, and ``algebraic`` is
  decided only for an expression of radicals (True) or a polynomial in
  ``pi`` or ``E`` with rational coefficients (False).  ``polar`` is SymPy's
  ``is_polar`` of the value (a point of the Riemann surface of ``log``
  is an ``exp_polar`` object).  A value SymPy leaves unevaluated at an
  infinity, an ``AccumBounds`` and anything ``evalf`` does not reduce to
  two numbers decide nothing;
* a rule is *checked* at a point where its premises all hold and its
  conclusion is decided; there the conclusion must hold.  A rule whose
  premises or conclusion are undecided at a point (and not settled by
  another literal) is *skipped* there, and counted.  A head whose
  evaluation raises or exceeds :data:`TIMEOUT` decides nothing about its
  node at that point; those are counted too.

The rows of ``Pow`` (``templates/power.py``, #294) have shapes and terms
other than ``x + c`` (:data:`SHAPED`); :func:`check_power` takes every point
``(b, e)`` of :data:`POW_BASES` x :data:`POW_EXPONENTS`, the node being
SymPy's ``Pow(b, e)``.  A rule with a shape (``f(base, -1)``, ``f(E,
exponent)``, ``f(exp(log_base), exponent)``, ``f(base, base)``, a constant
``number``) is checked only at the points of its shape, matched by
:func:`.wiring.matches` as the template matches a node; ``b**b`` is a
point whose base and exponent are the same object.  The terms are built as
the template builds them (:func:`power_objects`), and a rule about a term
that does not exist at a point (the ``u`` of a base that is no ``exp(u)``,
a term of a constant that is no SymPy ``Number``) is not checked there.
The rules ``wiring.power`` adds that are not rows (``core.ipi_rules``,
``core.irrational_root``, ``core._unit_power_units``,
``core._pow_bound_templates``) are not checked here.

The rows of ``Max``, ``Min`` and ``Piecewise`` (``templates/selection.py``,
#299) have a star (``f(*values)``, ``f(value, *values)``); :func:`check_selection`
expands each row for nodes of 1 to 4 values (``wiring.expand``, the rules
over too many clauses left out as the template leaves them out) and takes
every choice of the values from :data:`SELECTION_POOLS`, the node being
SymPy's ``Max(*values)`` or ``Min(*values)``, or, for a ``Piecewise``, the
value its conditions select, each value in turn (``Piecewise((v0, False),
..., (vk, True), ...)``).  Which arguments a ``Piecewise`` has for its rows
(``wiring.piecewise_values``) is not checked here.

The rows of ``Mul`` (``templates/mul.py``, #299) have a star too, and rows
of two factors with a shape (``f(coefficient, factor)``, ``f(-1,
factor)``) and the term ``2*coefficient``; :func:`check_mul` expands each
row with a star for products of 2 to 4 factors and takes every choice of
the factors from :data:`MUL_POOLS`, the node being SymPy's
``Mul(*factors)``; a row of two factors is checked at the points of its
shape, its term computed from the coefficient, as ``wiring.product`` does.
The factor sets (``core._mul_factor_sets``), ``a/v**k``
(``core._quotient_templates``) and the formula of the zero row past 32
factors (``wiring.wide_formulas``) are not checked here.

The rows of ``Add`` (``templates/add.py``, #299) have a star, and a
constant term (``f(number, *terms)``); :func:`check_add` expands each row
for sums of 2 to 4 terms, the constants of the point at their positions,
and takes every choice of the terms from :data:`ADD_POOLS`, the node being
SymPy's ``Add(*terms)``.  The sums of a special shape
(``core._imag_templates``; before #315 also ``_half_templates``,
``_bound_templates``, ``_recip_templates``) and the formulas of
the strict-sign rows past 32 terms are not checked here.

Every rule must be checked at least once, except those in
:data:`NEVER_CHECKED`, each with the reason; an entry that becomes
checkable fails, so the list cannot go stale.  A rule found false at a
point is a soundness bug; the known ones are in :data:`KNOWN_FALSE`, each
with the issue, and an entry that is no longer false fails.  Run the module
as a script to print the counts of every function.
"""
from __future__ import annotations

import functools
import itertools
from fractions import Fraction
import signal
import sys
import threading
import time

import pytest

pytest.importorskip("sympy")

import mpmath  # noqa: E402
from sympy import (  # noqa: E402
    AccumBounds, Add, E, Float, I, Integer, Max, Min, Mul, Piecewise, Poly, Pow, Rational, S,
    erfcinv, erfinv, oo, pi, exp, exp_polar, sqrt, unpolarify, zoo,
)
from sympy.ntheory import isprime  # noqa: E402

from satassume.knowledge.rules import BASIS, DEFINITIONS  # noqa: E402
from satassume.knowledge.templates import ROW_FAMILIES  # noqa: E402
from satassume.knowledge.templates._compiled_rows import FAMILIES  # noqa: E402
from satassume.knowledge.templates._rows import constant_value, from_text, generator  # noqa: E402
from satassume.knowledge.templates.core import _exp_arg  # noqa: E402
from satassume.knowledge.templates.functions import shifted  # noqa: E402
from satassume.knowledge.templates.wiring import _declared, expand, matches  # noqa: E402

#: seconds for one evaluation of a node (construction and evalf)
TIMEOUT = 10

#: the arguments of a function of one argument
POOL1 = (
    S(0), S(1), S(-1), S(2), S(-2), S.Half, -S.Half, S(3), S(-3), Rational(3, 2),
    Rational(-3, 2), Rational(1, 3), Rational(-1, 3), Rational(-7, 3), S(4), S(5), S(9),
    -1/E, sqrt(2), pi, -pi, E,
    I, -I, 2*I, I/2, 1 + I, -1 - I, 2 - 3*I,
    oo, -oo, zoo, oo*I, -oo*I,
)
#: the arguments of a function of two arguments
POOL2 = (
    S(0), S(1), S(-1), S(2), S(-2), S.Half, -S.Half, S(3), Rational(-3, 2), Rational(-1, 3),
    sqrt(2), pi, I, 1 + I, oo, -oo, zoo, oo*I,
)
#: the arguments of a function of three or four arguments
POOL4 = (S(0), S(1), S(-1), S.Half, S(2), I, oo)

POOLS = {1: POOL1, 2: POOL2}

_LINDEMANN = ("the value at an algebraic a != 0 stays unevaluated (sin(1), I*sinh(1), "
              "LambertW(1)), and its transcendence, the rule's theorem (Lindemann-Weierstrass), "
              "is not decided numerically")

_IRRATIONAL = ("irrational is never decided numerically: rational is decided only for an exact "
               "(Gaussian) rational, so no value of the pool is irrational (sqrt(2) is not)")
_GELFOND_SCHNEIDER = ("the conclusion, that an algebraic irrational power of an algebraic number "
                      "other than 0 and 1 is transcendental, is the Gelfond-Schneider theorem: "
                      "not decided numerically (2**GoldenRatio, sqrt(2)**sqrt(2))")

_INCOMPARABLE = ("SymPy's Max and Min raise for an argument that is not extended real (Max(I, 1), "
                 "Max(zoo)): no point has values that are all imaginary or not extended real")

#: rules no point of the pools checks: ``(function, the rule as :func:`show`
#: prints it)`` and the reason
NEVER_CHECKED = {
    **{(fn, f"{fn}: algebraic(x0) & ~zero(x0) -> transcendental(f)"): _LINDEMANN
       for fn in ('sin', 'cos', 'tan', 'cot', 'sec', 'csc',
                  'sinh', 'cosh', 'tanh', 'coth', 'sech', 'csch', 'LambertW')},
    ('LambertW', "LambertW: algebraic(x0) & integer(x1) & ~zero(x0) -> transcendental(f)"):
        _LINDEMANN,
    **{('Pow', rule): _IRRATIONAL for rule in (
        "Pow(b, 1): irrational(f) -> irrational(b)",
        "Pow(b, 1): irrational(b) -> irrational(f)",
        "Pow(b, -1): irrational(b) -> irrational(f)",
        "Pow(b, e): algebraic(b) & algebraic(e) & imaginary(e) & irrational(b) "
        "-> ~extended_real(f)",
    )},
    **{('Pow', rule): _GELFOND_SCHNEIDER for rule in (
        "Pow(b, c): algebraic(c) & algebraic(b) & irrational(b) & ~rational(c) -> ~algebraic(f)",
        "Pow(b, c): algebraic(c) & algebraic(b) & noninteger(b) & ~rational(c) -> ~algebraic(f)",
        "Pow(b, c): algebraic(c) & algebraic(b) & negative(b) & ~rational(c) -> ~algebraic(f)",
        "Pow(b, c): algebraic(c) & algebraic(b) & prime(b) & ~rational(c) -> ~algebraic(f)",
        "Pow(b, c): algebraic(c) & algebraic(b) & composite(b) & ~rational(c) -> ~algebraic(f)",
        "Pow(b, e): algebraic(b) & algebraic(e) & ~zero((b - 1)) & ~rational(e) & ~zero(b) "
        "-> ~algebraic(f)",
    )},
    **{(fn, f"{fn}: every({p}) -> {p}(f)"): _INCOMPARABLE
       for fn in ('Max', 'Min') for p in ('imaginary', '~extended_real')},
    ('Mul', "Mul: irrational(v0) & every(rational) & every(~zero) -> irrational(f) (at most 6)"):
        _IRRATIONAL,
}

#: rules of the rows found false at a point of the pools, each a known
#: soundness bug of the rules the rows were written from (#294 kept the
#: answers): ``(the point, the rule as :func:`show_power` prints it)`` and
#: the reason.  The test fails when an entry is no longer false there.
#: ``(-1/2)**(-oo)`` (``tests/test_p6_review.py``, #97 P6) is not here:
#: SymPy's value is ``nan``, whose finiteness this oracle leaves undecided,
#: so the row "infinite" is skipped at that point, not false.
KNOWN_FALSE = {
    **{(f"Pow({b}, -oo)", "Pow(c, e): finite(c) & negative_infinite(e) "
        "& extended_positive((Abs(c) - 1)) -> zero(f)"):
       "#240: SymPy gives nan for a negative non-integer base of absolute value above 1 to "
       "the power -oo ((-2)**(-oo) == 0, (-3/2)**(-oo) == nan); the row says zero"
       for b in ('-3/2', '-7/3')},
}


# ---------------------------------------------------------------------------
# the truth of a predicate for a concrete value
# ---------------------------------------------------------------------------

def _kand(vs):
    vs = list(vs)
    return False if False in vs else (True if all(v is True for v in vs) else None)


def _kor(vs):
    vs = list(vs)
    return True if True in vs else (False if all(v is False for v in vs) else None)


def _knot(v):
    return None if v is None else not v


def _definition(text):
    """``(op, ((pred, sign), ...))`` of a definition of ``DEFINITIONS``."""
    op = '|' if '|' in text else '&'
    lits = tuple((t.strip().lstrip('!').strip(), not t.strip().startswith('!'))
                 for t in text.split(op) if t.strip())
    return op, lits


_DEFS = {p: _definition(d) for p, d in DEFINITIONS.items()}
_UNKNOWN = dict.fromkeys(BASIS)


def truth(b, pred):
    """Kleene truth of ``pred`` given the basis values ``b`` (:func:`basis`)."""
    if pred in b:
        return b[pred]
    op, lits = _DEFS[pred]
    vs = (b[p] if s else _knot(b[p]) for p, s in lits)
    return _kand(vs) if op == '&' else _kor(vs)


def _no_number(**known):
    """The basis of a value that is no finite number: every predicate implying
    one is False."""
    b = dict.fromkeys(BASIS, False)
    b.update(polar=None)
    b.update(known)
    return b


_INFINITIES = {S.Infinity: 1, S.NegativeInfinity: -1}


def _infinite(v):
    """The basis of ``v`` when it is ``oo``, ``-oo``, ``zoo`` or a nonzero
    finite number times one of them (``oo*I``), else None."""
    if v in _INFINITIES:
        s = _INFINITIES[v]
    elif v is zoo:
        s = None
    elif isinstance(v, Mul) and sum(a in _INFINITIES or a is zoo for a in v.args) == 1:
        inf = next(a for a in v.args if a in _INFINITIES or a is zoo)
        rest = basis(Mul(*[a for a in v.args if a is not inf]))
        if rest is None or rest['complex'] is not True or rest['zero'] is not False:
            return _UNKNOWN
        if inf is zoo or rest['extended_real'] is False:
            s = None
        elif rest['extended_real'] is None:
            return dict(_no_number(finite=False), extended_real=None, extended_positive=None,
                        extended_negative=None)
        else:
            s = _INFINITIES[inf] * (1 if rest['extended_positive'] else -1)
    else:
        return None
    return _no_number(finite=False, extended_real=s is not None, extended_positive=s == 1,
                      extended_negative=s == -1)


def _radical(v):
    """Whether ``v`` is built of rationals and ``I`` by +, * and powers to
    rational exponents: an algebraic number."""
    if v.is_Rational or v is I:
        return True
    if isinstance(v, (Add, Mul)):
        return all(_radical(a) for a in v.args)
    if isinstance(v, Pow):
        return v.exp.is_Rational and _radical(v.base)
    return False


def _transcendental(v):
    """Whether ``v`` is a nonconstant polynomial in ``pi`` or ``E`` with
    Gaussian rational coefficients (a transcendental number)."""
    for t in (pi, E):
        if v.has(t) and v.free_symbols == set() and not v.has(*({pi, E} - {t})):
            try:
                p = Poly(v, t)
            except Exception:
                continue
            if p.domain.is_QQ or p.domain.is_ZZ or p.domain.is_QQ_I or p.domain.is_ZZ_I:
                return p.degree() >= 1
    return False


def _precise(p):
    """``p``, a part of an ``evalf`` result, as an mpf, 0 where ``evalf``
    cannot tell it from 0; None when it is not a number."""
    if p.is_zero:
        return mpmath.mpf(0)
    if not isinstance(p, Float):
        return None
    if p._prec < 20:
        return mpmath.mpf(0)
    with mpmath.workdps(40):
        return mpmath.mpf(p._mpf_)


#: the relative size below which a part of a numeric value is 0
_REL = mpmath.mpf(10)**-25
#: the distance (relative above 1) below which a value is near an integer
_NEAR = mpmath.mpf(10)**-20


def _evalf(v):
    """``v.evalf(30)``; SymPy has no ``evalf`` of ``erfcinv``:
    ``erfcinv(z) == erfinv(1 - z)``."""
    if v.has(erfcinv):
        v = v.rewrite(erfinv)
    return v.evalf(30)


@functools.lru_cache(maxsize=None)
def basis(v):
    """The Kleene values of the predicates of ``BASIS`` for the value
    ``v``, under satassume's meanings (``knowledge/rules.py``)."""
    if v is S.NaN:
        return _no_number(finite=None)
    if not getattr(v, 'is_number', False) or v.has(AccumBounds):
        return _UNKNOWN
    inf = _infinite(v)
    if inf is not None:
        return inf
    if v.has(S.Infinity, S.NegativeInfinity, zoo, S.NaN):
        # unevaluated at an infinity (lowergamma(1, oo) is left alone)
        return _UNKNOWN
    polar = True if v.is_polar else None
    # the complex number a polar one is (exp_polar(0) is 1)
    v = unpolarify(v)
    re_, im_ = v.as_real_imag() if v.is_Add or v.is_Mul or v is I else (v, S.Zero)
    if re_.is_Rational and im_.is_Rational:
        # a Gaussian rational: everything is exact
        b = dict.fromkeys(BASIS, False)
        b.update(finite=True, complex=True, algebraic=True, polar=polar)
        if im_:
            b['imaginary'] = bool(re_ == 0)
            return b
        q = Fraction(int(re_.p), int(re_.q))
        b.update(extended_real=True, rational=True, zero=q == 0, extended_positive=q > 0,
                 extended_negative=q < 0, integer=q.denominator == 1)
        if q.denominator == 1:
            k = q.numerator
            b.update(even=k % 2 == 0, prime=k > 1 and isprime(k),
                     composite=k > 1 and not isprime(k))
        return b
    try:
        a, c = (_precise(t) for t in _evalf(v).as_real_imag())
    except (TypeError, ValueError, AttributeError, ZeroDivisionError):
        return _UNKNOWN
    if a is None or c is None or not (mpmath.isfinite(a) and mpmath.isfinite(c)):
        return _UNKNOWN
    # a part below 1e-25 of the other is noise (polylog(1/2, -2) evaluates
    # with an imaginary part of 6e-36)
    if abs(c) <= _REL * abs(a):
        c = mpmath.mpf(0)
    elif abs(a) <= _REL * abs(c):
        a = mpmath.mpf(0)
    b = dict.fromkeys(BASIS)
    b.update(finite=True, complex=True, polar=polar)
    real = c == 0
    b.update(extended_real=real, zero=real and a == 0, imaginary=a == 0 and c != 0)
    b['algebraic'] = True if _radical(v) else (False if _transcendental(v) else None)
    if not real:
        b.update(extended_positive=False, extended_negative=False, integer=False,
                 rational=False, even=False, prime=False, composite=False)
        return b
    b.update(extended_positive=a > 0, extended_negative=a < 0)
    with mpmath.workdps(40):
        near = abs(a - mpmath.nint(a)) <= _NEAR * max(1, abs(a))
    if not near:
        b.update(integer=False, even=False, prime=False, composite=False)
    if a == 0:
        b.update(integer=True, rational=True, algebraic=True, even=True, prime=False,
                 composite=False)
    return b


# ---------------------------------------------------------------------------
# the rules and their points
# ---------------------------------------------------------------------------

#: families whose rows have shapes and terms other than x + c, checked by
#: their own section below (the rows of Pow, :func:`check_power`)
SHAPED = ('power',)

#: families whose rows have a star, checked by their own sections below (the
#: rows of Max, Min and Piecewise, :func:`check_selection`; of Mul,
#: :func:`check_mul`; of Add, :func:`check_add`)
STARRED = ('selection', 'mul', 'add')


def _heads():
    """``(family, name, heads, arity, terms, rules)`` for every function of
    the compiled rows (but those of :data:`SHAPED` and :data:`STARRED`);
    ``heads`` the SymPy classes whose nodes get the rules (empty for a
    function this SymPy lacks)."""
    declared = {}
    for family, fns in ROW_FAMILIES:
        for fn in fns:
            name = fn.rpartition(':')[2] if isinstance(fn, str) else fn.__name__
            declared[family, name] = _declared(fn)
    out = []
    for family, fns in FAMILIES:
        if family in SHAPED + STARRED:
            continue
        for name, arity, terms, specs in fns:
            fn = declared[family, name]
            if fn is None:
                heads = ()
            elif name == 'RoundFunction':
                # a base class has no value: its rules are its subclasses'
                heads = tuple(fn.__subclasses__())
            else:
                heads = (fn,)
            for n, rules in specs:
                out.append((family, name, heads, n, dict(terms)[n], rules))
    return out


HEADS = _heads()


class _Timeout(BaseException):
    # not an Exception: the handlers of an evaluation do not catch it
    pass


def _alarm(signum, frame):
    raise _Timeout


def _timed(fn, *args):
    """``fn(*args)`` under :data:`TIMEOUT` (in the main thread)."""
    if threading.current_thread() is not threading.main_thread():
        return fn(*args)
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    try:
        return fn(*args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _node_basis(head, args):
    """``(basis, failure)`` of the node ``head(*args)``: failure is None,
    ``'raised'`` (SymPy builds no node), ``'unevaluated'`` (deciding the
    value raised) or ``'timeout'``."""
    def run():
        try:
            v = head(*args)
        except Exception:
            return _UNKNOWN, 'raised'
        try:
            return basis(v), None
        except Exception:
            return _UNKNOWN, 'unevaluated'
    try:
        return _timed(run)
    except _Timeout:
        return _UNKNOWN, 'timeout'


def _pool(n):
    return POOLS.get(n, POOL4)


def show(name, n, rule, terms):
    """``prem & ... -> concl | ...`` with the slots named: ``x0``, ...,
    the node ``f``, the terms ``x0 + c``."""
    names = [f"x{i}" for i in range(n)] + ['f'] + [f"(x{i} + {c})" for i, c in terms]

    def lit(t):
        s, p, pos = t
        return f"{'' if pos else '~'}{p}({names[s]})"
    prem, concl = rule
    return f"{name}: {' & '.join(map(lit, prem)) or 'True'} -> {' | '.join(map(lit, concl))}"


class Counts:
    def __init__(self):
        self.points = self.checked = self.vacuous = self.skipped = 0
        self.raised = self.unevaluated = self.timeout = 0
        self.per_rule = {}
        self.false = []


def check_function(family, name, heads, n, terms, rules):
    """The :class:`Counts` of the rules of one function and number of
    arguments over its pool."""
    out = Counts()
    out.per_rule = dict.fromkeys(range(len(rules)), 0)
    shifts = [(i, S(c)) for i, c in terms]
    for head in heads:
        for args in itertools.product(_pool(n), repeat=n):
            out.points += 1
            node, failure = _node_basis(head, args)
            if failure:
                setattr(out, failure, getattr(out, failure) + 1)
            slots = [basis(a) for a in args] + [node]
            slots += [basis(shifted(args[i], c)) for i, c in shifts]
            for k, (prem, concl) in enumerate(rules):
                p = _kand(_lit(slots, t) for t in prem)
                if p is False:
                    out.vacuous += 1
                    continue
                c = _kor(_lit(slots, t) for t in concl)
                if p is True and c is False:
                    out.false.append((head.__name__, args, show(name, n, (prem, concl), terms)))
                elif p is True and c is True:
                    out.checked += 1
                    out.per_rule[k] += 1
                elif c is True:
                    out.vacuous += 1
                else:
                    out.skipped += 1
    return out


def _lit(slots, t):
    s, p, pos = t
    v = truth(slots[s], p)
    return v if pos else _knot(v)


# ---------------------------------------------------------------------------
# Pow: rules with shapes, and terms other than x + c (#294)
# ---------------------------------------------------------------------------

def _shared(values, others):
    """``values``, each value equal to one of ``others`` replaced by that
    object: the point ``(v, v)`` is then ``v**v`` (a ``('same', 0)`` shape
    matches by identity, as for the symbols of ``b**b``)."""
    return tuple(next((o for o in others if type(o) is type(v) and o == v), v) for v in values)


#: the bases of the points of Pow: the numbers of the shapes (``E``, ``-1``,
#: ``1``, ``I``, ``-I``), constants (atomic numbers: integers, ``|b|`` above
#: and below 1, ``GoldenRatio``, ``pi``, the infinities), values that are no
#: constant (``sqrt(2)``, ``2*I``, ``1 + I``, ``oo*I``), ``exp(u)`` for real,
#: imaginary and complex ``u`` and a polar number
POW_BASES = (
    S(0), S(1), S(-1), S(2), S(-2), S(3), S(4), S(6), S.Half, -S.Half, Rational(3, 2),
    Rational(-3, 2), Rational(1, 3), Rational(2, 3), Rational(-7, 3),
    sqrt(2), S.GoldenRatio, pi, E, I, -I, 2*I, I/2, 1 + I,
    oo, -oo, zoo, oo*I,
    exp(2), exp(-1), exp(S.Half), exp(I), exp(-I*pi/3), exp(1 + I), exp_polar(I),
)
#: the exponents: those of the shapes (``-1``, ``1``), ``k/2``, ``1/q`` and
#: ``-1/q``, ``2 mod 4`` and ``0 mod 4``, ``|e| >= 2``, algebraic irrational
#: (``GoldenRatio``, ``sqrt(2)``), transcendental, imaginary, the infinities
POW_EXPONENTS = _shared((
    S(0), S(1), S(-1), S(2), S(-2), S(3), S(4), S(-4), S(6), S.Half, -S.Half, Rational(3, 2),
    Rational(-3, 2), Rational(1, 3), Rational(-1, 3), Rational(2, 3), Rational(-7, 3),
    sqrt(2), S.GoldenRatio, pi, E, I, -I, 2*I, 1 + I, I*pi,
    oo, -oo, zoo,
), POW_BASES)


def _power():
    """``(name, terms, rules)`` of the compiled rows of Pow: ``terms`` as
    compiled (texts), ``rules`` as :func:`.wiring.power` reads them
    (``gen.specs``, the numbers of the shapes as SymPy numbers)."""
    [(name, arity, terms, specs)] = dict(FAMILIES)['power']
    gen = generator(name, arity, terms, specs, 'power')
    return name, dict(terms)[2], gen.specs[2]


POWER = _power()


def power_objects(b, e, terms):
    """``(args, consts, objects)`` of the point ``(b, e)``: the objects of the
    slots but the node's (None there), each term as :func:`.wiring.power`
    builds it, ``Mul(k, e)``, ``b + c``, the ``u`` of ``exp(u)``
    (:func:`.core._exp_arg`), a term of a constant from the SymPy ``Number``
    (:func:`._rows.constant_value`); None for a term that does not exist at
    the point: ``u`` for a base that is no ``exp(u)``, the term of a
    constant that is no ``Number``.  ``k*e`` and ``b + c`` exist at every
    point: the template has them only for arguments that are no numbers, but
    the rules about them hold for every value, so they are checked at numbers
    too."""
    args = (b, e)
    consts = {i: a for i, a in enumerate(args) if a.is_Atom and a.is_number}
    objs = [b, e, None]
    for t in terms:
        if t[0] == 'inner':
            v = _exp_arg(args[t[1]])
        elif t[0] == 'times':
            v = Mul(from_text(t[2]), args[t[1]])
        elif t[0] == 'of_constant':
            c = consts.get(t[1])
            v = constant_value(t[2], c) if c is not None and c.is_Number else None
        else:
            v = args[t[0]] + S(t[1])
        objs.append(v)
    return args, consts, objs


def show_power(rule, terms):
    """``Pow(b, e): prem & ... -> concl | ...`` with the arguments named by
    the rule's shape (``c`` a constant, ``exp(u)``, a number) and the node
    ``f``."""
    shape = rule[2] if len(rule) > 2 else (None, None)
    args = []
    for i, s in enumerate(shape):
        if s is None:
            args.append('be'[i])
        elif s[0] == 'value':
            args.append(str(s[1]))
        elif s[0] == 'same':
            args.append(args[s[1]])
        elif s[0] == 'head':
            args.append(f'{s[1]}(u)')
        else:
            args.append('c')
    names = [*args, 'f']
    for t in terms:
        if t[0] == 'inner':
            names.append('u')
        elif t[0] == 'times':
            names.append(f"{t[2]}*{args[t[1]]}")
        elif t[0] == 'of_constant':
            names.append(f"({t[2].replace('number', args[t[1]])})")
        else:
            names.append(f"({args[t[0]]} {'+' if t[1] > 0 else '-'} {abs(t[1])})")

    def lit(t):
        s, p, pos = t
        return f"{'' if pos else '~'}{p}({names[s]})"
    prem, concl = rule[:2]
    return (f"Pow({', '.join(args)}): {' & '.join(map(lit, prem)) or 'True'} -> "
            f"{' | '.join(map(lit, concl))}")


def check_power(rules, terms):
    """The :class:`Counts` of the rules of Pow over the points ``POW_BASES x
    POW_EXPONENTS``: the node is SymPy's ``Pow(b, e)``; a rule with a shape
    only at the points of its shape (:func:`.wiring.matches`), a rule about
    a term only where it exists (:func:`power_objects`), else ``absent``."""
    out = Counts()
    out.per_rule = dict.fromkeys(range(len(rules)), 0)
    out.absent = 0
    for b, e in itertools.product(POW_BASES, POW_EXPONENTS):
        out.points += 1
        node, failure = _node_basis(Pow, (b, e))
        if failure:
            setattr(out, failure, getattr(out, failure) + 1)
        args, consts, objs = power_objects(b, e, terms)
        slots = [None if o is None else basis(o) for o in objs]
        slots[2] = node
        for k, rule in enumerate(rules):
            prem, concl = rule[:2]
            if len(rule) > 2 and not matches(rule[2], args, consts):
                continue
            if any(slots[t[0]] is None for t in (*prem, *concl)):
                out.absent += 1
                continue
            p = _kand(_lit(slots, t) for t in prem)
            if p is False:
                out.vacuous += 1
                continue
            c = _kor(_lit(slots, t) for t in concl)
            if p is True and c is False:
                out.false.append((f"Pow({b}, {e})", show_power(rule, terms)))
            elif p is True and c is True:
                out.checked += 1
                out.per_rule[k] += 1
            elif c is True:
                out.vacuous += 1
            else:
                out.skipped += 1
    return out


# ---------------------------------------------------------------------------
# Max, Min, Piecewise: rows with a star (#299)
# ---------------------------------------------------------------------------

#: the values of the points of Max, Min and Piecewise, by their number:
#: integers (0, 1, prime, composite, even, negative), halves, algebraic and
#: transcendental irrationals, imaginary and complex numbers (Max and Min
#: raise there: no node), the infinities, nan and a float; fewer for 3 and
#: 4 values
SELECTION_POOLS = {
    1: (S(0), S(1), S(-1), S(2), S(3), S(4), S(-2), S.Half, -S.Half, sqrt(2), pi, -pi, E,
        I, -I, 1 + I, oo, -oo, zoo, S.NaN, Float(2.5)),
    3: (S(0), S(1), S(-1), S(2), S(4), S.Half, sqrt(2), pi, I, oo, -oo),
    4: (S(0), S(1), S(-1), S(2), pi, I),
}
SELECTION_POOLS[2] = SELECTION_POOLS[1]

#: the heads of the rows with a star
SELECTION_HEADS = {'Max': Max, 'Min': Min, 'Piecewise': Piecewise}


def _selection():
    """``((name, schemas), ...)`` of the compiled rows of Max, Min and
    Piecewise, as :func:`.wiring.any_arity` reads them (``gen.schemas``)."""
    return tuple((name, generator(name, arity, terms, specs, 'selection', schemas).schemas)
                 for name, arity, terms, specs, schemas in dict(FAMILIES)['selection'])


SELECTION = _selection()


def show_schema(name, schema):
    """``Max: every(integer) -> integer(f)``: a row with a star, its picked
    arguments ``v0``, ``v1``, ...; ``every``, ``some`` and ``count`` of
    the others; ``at most n`` for a row with ``at_most``."""
    at_most, picks, rules = schema

    def lit(t):
        w, p, pos = t
        p = f"{'' if pos else '~'}{p}"
        if w in ('every', 'some', 'others'):
            return f"{w}({p})"
        return f"{p}({f'v{w}' if type(w) is int else 'f' if w == 'node' else w})"
    return "; ".join(
        f"{name}: {' & '.join(map(lit, prem)) or 'True'} -> {' | '.join(map(lit, concl))}"
        + (f" (at most {at_most})" if at_most is not None else '') for prem, concl in rules)


def _select(k):
    """The ``Piecewise`` whose conditions select value ``k``."""
    def head(*values):
        return Piecewise(*((v, S.true if i == k else S.false) for i, v in enumerate(values)))
    head.__name__ = 'Piecewise'
    return head


def check_selection(name, schemas):
    """The :class:`Counts` of the rows of ``name`` (``Max``, ``Min``,
    ``Piecewise``), by row (``per_rule``), over the points of
    :data:`SELECTION_POOLS`: each row is expanded for a node of ``n``
    values (``wiring.expand``, the rules of too many clauses left out)."""
    out = Counts()
    out.per_rule = dict.fromkeys(range(len(schemas)), 0)
    for n in sorted(SELECTION_POOLS):
        rules = [(i, r) for i, s in enumerate(schemas)
                 for r in expand((s,), n, {}, leave_out_wide=True)]
        heads = ([_select(k) for k in range(n)] if name == 'Piecewise'
                 else [SELECTION_HEADS[name]])
        for args in itertools.product(SELECTION_POOLS[n], repeat=n):
            for head in heads:
                out.points += 1
                node, failure = _node_basis(head, args)
                if failure:
                    setattr(out, failure, getattr(out, failure) + 1)
                    continue
                slots = [basis(a) for a in args] + [node]
                for i, (prem, concl) in rules:
                    p = _kand(_lit(slots, t) for t in prem)
                    if p is False:
                        out.vacuous += 1
                        continue
                    c = _kor(_lit(slots, t) for t in concl)
                    if p is True and c is False:
                        out.false.append((f"{name}{args}", show_schema(name, schemas[i])))
                    elif p is True and c is True:
                        out.checked += 1
                        out.per_rule[i] += 1
                    elif c is True:
                        out.vacuous += 1
                    else:
                        out.skipped += 1
    return out


# ---------------------------------------------------------------------------
# Mul: rows with a star, and rows of a coefficient (#299, U2)
# ---------------------------------------------------------------------------

#: the factors of a product of 2, 3 and 4 factors
MUL_POOLS = {
    2: (S(0), S(1), S(-1), S(2), S(3), S(4), S(-2), S(-3), S.Half, -S.Half, Rational(3, 2),
        Rational(-3, 2), sqrt(2), pi, -pi, E, I, -I, 2*I, 1 + I, oo, -oo, zoo, S.NaN,
        Float(2.5), Float(-2.0), exp_polar(I*pi), exp_polar(0)),
    3: (S(0), S(1), S(-1), S(2), S(3), S(-2), S.Half, sqrt(2), pi, I, -I, oo, -oo,
        exp_polar(I*pi)),
    4: (S(0), S(1), S(-1), S(2), S(-2), pi, I, oo),
}


def _mul():
    """The compiled rows of Mul as :func:`.wiring.product` reads them:
    ``(schemas, terms, fixed)``, the schemas of the rows with a star, the
    terms of the rows of two factors (``2*coefficient``) and their rules."""
    [(name, arity, terms, specs, schemas)] = dict(FAMILIES)['mul']
    gen = generator(name, arity, terms, specs, 'mul', schemas)
    return gen.schemas, gen.terms[2], gen.specs[2]


MUL = _mul()


def show_mul(rule, terms):
    """``Mul(c, x1): prem & ... -> concl | ...``: a row of two factors, the
    coefficient ``c`` or a number by the rule's shape, the node ``f``, the
    terms of the coefficient (``2*c``)."""
    args = ['c' if s is not None and s[0] == 'coefficient' else str(s[1]) if s is not None
            else f'x{i}' for i, s in enumerate(rule[2])]
    names = [*args, 'f', *(t[2].replace('coefficient', 'c') for t in terms)]

    def lit(t):
        k, p, pos = t
        return f"{'' if pos else '~'}{p}({names[k]})"
    prem, concl = rule[:2]
    return (f"Mul({', '.join(args)}): {' & '.join(map(lit, prem)) or 'True'} -> "
            f"{' | '.join(map(lit, concl))}")


def check_mul(schemas, terms, fixed):
    """The :class:`Counts` of the rows of Mul, by rule (``per_rule``: the
    schemas, then the rules of two factors), over the points of
    :data:`MUL_POOLS`: the node is SymPy's ``Mul(*factors)``.  A row with a
    star is expanded for ``n`` factors (``wiring.expand``); a row of two
    factors is checked at the points of its shape (:func:`.wiring.matches`:
    a coefficient is a SymPy ``Number`` first), and its terms are computed
    from the coefficient (:func:`._rows.constant_value`), as the template
    does; a rule about a term that does not exist there is ``absent``."""
    out = Counts()
    out.per_rule = dict.fromkeys(range(len(schemas) + len(fixed)), 0)
    out.absent = 0
    for n in sorted(MUL_POOLS):
        starred = [(i, r) for i, s in enumerate(schemas) for r in expand((s,), n, {})]
        for args in itertools.product(MUL_POOLS[n], repeat=n):
            out.points += 1
            node, failure = _node_basis(Mul, args)
            if failure:
                setattr(out, failure, getattr(out, failure) + 1)
                continue
            slots = [basis(a) for a in args] + [node]
            rules = list(starred)
            if n == 2:
                consts = {i: a for i, a in enumerate(args) if a.is_Atom and a.is_number}
                for _, i, t in terms:
                    c = consts.get(i)
                    slots.append(basis(constant_value(t, c)) if c is not None and c.is_Number
                                 else None)
                for j, r in enumerate(fixed):
                    if not matches(r[2], args, consts):
                        continue
                    if any(slots[t[0]] is None for t in (*r[0], *r[1])):
                        out.absent += 1
                        continue
                    rules.append((len(schemas) + j, r[:2]))
            for i, (prem, concl) in rules:
                p = _kand(_lit(slots, t) for t in prem)
                if p is False:
                    out.vacuous += 1
                    continue
                c = _kor(_lit(slots, t) for t in concl)
                if p is True and c is False:
                    out.false.append((f"Mul{args}", show_mul_rule(i)))
                elif p is True and c is True:
                    out.checked += 1
                    out.per_rule[i] += 1
                elif c is True:
                    out.vacuous += 1
                else:
                    out.skipped += 1
    return out


def show_mul_rule(i):
    """Rule ``i`` of :func:`check_mul` as :func:`show_schema` or
    :func:`show_mul` prints it."""
    schemas, terms, fixed = MUL
    if i < len(schemas):
        return show_schema('Mul', schemas[i])
    return show_mul(fixed[i - len(schemas)], terms)


# ---------------------------------------------------------------------------
# Add: rows with a star, and a constant term (#299, U1)
# ---------------------------------------------------------------------------

#: the terms of a sum of 2, 3 and 4 terms
ADD_POOLS = {
    2: (S(0), S(1), S(-1), S(2), S(3), S(4), S(-2), S(-3), S.Half, -S.Half, Rational(3, 2),
        sqrt(2), -sqrt(2), pi, -pi, E, I, -I, 2*I, 1 + I, I*pi, oo, -oo, oo*I, zoo, S.NaN,
        Float(2.5), Float(-2.0)),
    3: (S(0), S(1), S(-1), S(2), S(3), S(-2), S.Half, sqrt(2), pi, I, -I, oo, -oo, zoo),
    4: (S(0), S(1), S(-1), S(2), S(-2), I, oo, -oo),
}


def _add():
    """The schemas of the compiled rows of Add, as :func:`.wiring.addition`
    reads them (``gen.schemas``)."""
    [(name, arity, terms, specs, schemas)] = dict(FAMILIES)['add']
    return generator(name, arity, terms, specs, 'add', schemas).schemas


ADD = _add()


def check_add(schemas):
    """The :class:`Counts` of the rows of Add, by row (``per_rule``), over
    the points of :data:`ADD_POOLS`: the node is SymPy's ``Add(*terms)``.
    Each row is expanded for ``n`` terms with the constants of the point
    (``wiring.expand``: a constant term, ``number``, is at the position of
    a constant, an atomic number)."""
    out = Counts()
    out.per_rule = dict.fromkeys(range(len(schemas)), 0)
    for n in sorted(ADD_POOLS):
        by_positions = {}
        for args in itertools.product(ADD_POOLS[n], repeat=n):
            out.points += 1
            node, failure = _node_basis(Add, args)
            if failure:
                setattr(out, failure, getattr(out, failure) + 1)
                continue
            consts = {i: a for i, a in enumerate(args) if a.is_Atom and a.is_number}
            # a constant term is placed by the positions of the constants only
            rules = by_positions.get(tuple(consts))
            if rules is None:
                rules = by_positions[tuple(consts)] = [
                    (i, r) for i, s in enumerate(schemas) for r in expand((s,), n, consts)]
            slots = [basis(a) for a in args] + [node]
            for i, (prem, concl) in rules:
                p = _kand(_lit(slots, t) for t in prem)
                if p is False:
                    out.vacuous += 1
                    continue
                c = _kor(_lit(slots, t) for t in concl)
                if p is True and c is False:
                    out.false.append((f"Add{args}", show_schema('Add', schemas[i])))
                elif p is True and c is True:
                    out.checked += 1
                    out.per_rule[i] += 1
                elif c is True:
                    out.vacuous += 1
                else:
                    out.skipped += 1
    return out


def _id(h):
    family, name, heads, n, terms, rules = h
    return f"{family}-{name}-{n}"


_COUNTED = ('points', 'checked', 'vacuous', 'skipped', 'raised', 'unevaluated', 'timeout')


def _line(what, rules, c, never):
    return (f"{what}: {rules} rules ({rules - never} checked, {never} never), "
            f"{c.points} points, {c.checked} checks, {c.skipped} skipped, "
            f"{c.raised} raised, {c.unevaluated} unevaluated, {c.timeout} timeouts, "
            f"{len(c.false)} false")


@pytest.mark.parametrize("h", HEADS, ids=[_id(h) for h in HEADS])
def test_every_rule_holds_at_the_points_of_the_pool(h):
    family, name, heads, n, terms, rules = h
    if not heads:
        pytest.skip(f"{name} is not in this SymPy")
    c = check_function(*h)
    never = {show(name, n, r, terms) for k, r in enumerate(rules) if not c.per_rule[k]}
    print(_line(_id(h), len(rules), c, len(never)))
    assert not c.false, "false rules (head, arguments, rule):\n" + "\n".join(map(str, c.false))
    shown = {show(name, n, r, terms) for r in rules}
    allowed = {r for (fn, r) in NEVER_CHECKED if fn == name and r in shown}
    assert never == allowed, (f"never checked, not in NEVER_CHECKED: {sorted(never - allowed)}; "
                              f"in NEVER_CHECKED but checked: {sorted(allowed - never)}")


def test_every_rule_of_pow_holds_at_the_points_of_the_pools():
    name, terms, rules = POWER
    c = check_power(rules, terms)
    never = {show_power(r, terms) for k, r in enumerate(rules) if not c.per_rule[k]}
    print(_line(f"power-{name}-2", len(rules), c, len(never)), f"{c.absent} absent")
    false, known = set(c.false), set(KNOWN_FALSE)
    assert false == known, (f"false (point, rule), not in KNOWN_FALSE: {sorted(false - known)}; "
                            f"in KNOWN_FALSE but not false: {sorted(known - false)}")
    allowed = {r for (fn, r) in NEVER_CHECKED if fn == name}
    assert never == allowed, (f"never checked, not in NEVER_CHECKED: {sorted(never - allowed)}; "
                              f"in NEVER_CHECKED but checked: {sorted(allowed - never)}")


def test_the_points_of_pow_have_its_shapes():
    # b**b: the same object as base and exponent; exp(u), E, I, -I, -1, 1
    # and constants (atomic numbers) among the bases
    name, terms, rules = POWER
    shapes = {r[2] for r in rules if len(r) > 2}
    for shape in shapes:
        assert any(matches(shape, *power_objects(b, e, terms)[:2])
                   for b in POW_BASES for e in POW_EXPONENTS), shape
    assert sum(b is e for b in POW_BASES for e in POW_EXPONENTS) >= 20


@pytest.mark.parametrize("name", [name for name, _ in SELECTION])
def test_every_rule_of_max_min_and_piecewise_holds_at_the_points_of_the_pools(name):
    schemas = dict(SELECTION)[name]
    c = check_selection(name, schemas)
    never = {show_schema(name, s) for k, s in enumerate(schemas) if not c.per_rule[k]}
    print(_line(f"selection-{name}", len(schemas), c, len(never)))
    false, known = set(c.false), set(KNOWN_FALSE)
    assert false <= known and not {r for r in known if r[0].startswith(name + '(')} - false, (
        f"false (point, rule), not in KNOWN_FALSE: {sorted(false - known)}")
    allowed = {r for (fn, r) in NEVER_CHECKED if fn == name}
    assert never == allowed, (f"never checked, not in NEVER_CHECKED: {sorted(never - allowed)}; "
                              f"in NEVER_CHECKED but checked: {sorted(allowed - never)}")


def test_every_rule_of_mul_holds_at_the_points_of_the_pools():
    c = check_mul(*MUL)
    rules = len(MUL[0]) + len(MUL[2])
    never = {show_mul_rule(k) for k in range(rules) if not c.per_rule[k]}
    print(_line("mul-Mul", rules, c, len(never)), f"{c.absent} absent")
    false, known = set(c.false), set(KNOWN_FALSE)
    assert false <= known and not {r for r in known if r[0].startswith('Mul(')} - false, (
        f"false (point, rule), not in KNOWN_FALSE: {sorted(false - known)}")
    allowed = {r for (fn, r) in NEVER_CHECKED if fn == 'Mul'}
    assert never == allowed, (f"never checked, not in NEVER_CHECKED: {sorted(never - allowed)}; "
                              f"in NEVER_CHECKED but checked: {sorted(allowed - never)}")


def test_every_rule_of_add_holds_at_the_points_of_the_pools():
    c = check_add(ADD)
    never = {show_schema('Add', s) for k, s in enumerate(ADD) if not c.per_rule[k]}
    print(_line("add-Add", len(ADD), c, len(never)))
    false, known = set(c.false), set(KNOWN_FALSE)
    assert false <= known and not {r for r in known if r[0].startswith('Add(')} - false, (
        f"false (point, rule), not in KNOWN_FALSE: {sorted(false - known)}")
    allowed = {r for (fn, r) in NEVER_CHECKED if fn == 'Add'}
    assert never == allowed, (f"never checked, not in NEVER_CHECKED: {sorted(never - allowed)}; "
                              f"in NEVER_CHECKED but checked: {sorted(allowed - never)}")


def test_the_points_of_mul_have_its_shapes():
    # a coefficient (a Number first: 2, -3/2, 2.5, -2.0, oo) and -1 first,
    # and a 2*coefficient that is an integer and one that is not
    _, terms, fixed = MUL
    for shape in {r[2] for r in fixed}:
        assert any(matches(shape, (a, b), {0: a} if a.is_Atom and a.is_number else {})
                   for a in MUL_POOLS[2] for b in MUL_POOLS[2]), shape
    assert [t[2] for t in terms] == ['2*coefficient']


def test_the_points_of_piecewise_select_each_value():
    assert _select(1)(S(1), S(2), S(3)) == 2 and _select(0)(S(1)) == 1
    assert _node_basis(Max, (I, S(1)))[1] == 'raised'


def test_the_oracle_follows_satassumes_meanings():
    def t(v, p):
        return truth(basis(v), p)
    # imaginary excludes 0; complex and real imply finite; oo is extended real
    assert t(S(0), 'imaginary') is False and t(I, 'imaginary') is True
    assert t(oo, 'complex') is False and t(oo, 'extended_real') is True
    assert t(oo, 'real') is False and t(oo, 'extended_positive') is True
    assert t(zoo, 'extended_real') is False and t(zoo, 'infinite') is True
    assert t(oo*I, 'imaginary') is False and t(oo*I, 'extended_real') is False
    assert t(-oo*I, 'infinite') is True
    # nan is no number; finite is unknown
    assert t(S.NaN, 'complex') is False and t(S.NaN, 'finite') is None
    assert t(S.NaN, 'noninteger') is False and t(S.NaN, 'transcendental') is False
    # exact numbers
    assert t(S(7), 'prime') is True and t(S(9), 'composite') is True
    assert t(S(1), 'prime') is False and t(S(1), 'composite') is False
    assert t(S.Half, 'noninteger') is True and t(1 + I, 'algebraic') is True
    # numeric: decided away from an integer only; algebraicity of radicals
    # and of polynomials in pi
    assert t(sqrt(2), 'algebraic') is True and t(sqrt(2), 'irrational') is None
    assert t(pi/2, 'transcendental') is True and t(pi, 'positive') is True
    assert t(I*pi/2, 'transcendental') is True and t(I*pi/2, 'imaginary') is True
    # polar: SymPy's is_polar; the number of a polar value
    from sympy import exp_polar
    assert t(exp_polar(0), 'rational') is True and t(exp_polar(0), 'polar') is True
    assert t(S(2), 'polar') is None
    assert t(erfcinv(S.Half), 'positive') is True
    from sympy import cos, gamma, sin
    assert t(sin(1), 'integer') is False and t(sin(1), 'rational') is None
    assert t(sin(1), 'transcendental') is None
    assert t(sin(1)**2 + cos(1)**2 - 1, 'zero') is True
    assert t(gamma(1 + I), 'extended_real') is False
    from sympy import polylog
    assert t(polylog(S.Half, -2), 'negative') is True
    assert t(Integer(2)*I*sin(1), 'imaginary') is True
    # unevaluated at an infinity, and accumulation bounds, decide nothing
    assert t(sin(oo), 'real') is None


def test_every_entry_of_never_checked_is_a_rule():
    name, terms, rules = POWER
    shown = {(h[1], show(h[1], h[3], r, h[4])) for h in HEADS for r in h[5]}
    shown |= {(name, show_power(r, terms)) for r in rules}
    shown |= {(n, show_schema(n, s)) for n, schemas in SELECTION for s in schemas}
    shown |= {('Mul', show_mul_rule(k)) for k in range(len(MUL[0]) + len(MUL[2]))}
    shown |= {('Add', show_schema('Add', s)) for s in ADD}
    assert set(NEVER_CHECKED) <= shown
    assert {r for _, r in KNOWN_FALSE} <= ({show_power(r, terms) for r in rules}
                                           | {r for _, r in shown})


def test_every_function_of_the_families_is_checked():
    names = {(family, fn.rpartition(':')[2] if isinstance(fn, str) else fn.__name__)
             for family, fns in ROW_FAMILIES if family not in SHAPED + STARRED for fn in fns}
    assert {(h[0], h[1]) for h in HEADS} == names
    assert sum(len(h[5]) for h in HEADS) == sum(
        len(r) for family, fns in FAMILIES if family not in SHAPED + STARRED
        for _, _, _, specs in fns for _, r in specs)
    # the shaped families: Pow
    assert SHAPED == ('power',) and dict(ROW_FAMILIES)['power'] == (Pow,)
    [(name, _, _, specs)] = dict(FAMILIES)['power']
    assert POWER[0] == name and len(POWER[2]) == len(dict(specs)[2]) and len(specs) == 1
    # the families with a star: Max, Min, Piecewise
    assert STARRED == ('selection', 'mul', 'add')
    assert [name for name, _ in SELECTION] == [fn.__name__ for fn in dict(ROW_FAMILIES)['selection']]
    assert dict(ROW_FAMILIES)['mul'] == (Mul,)
    [(_, _, terms, specs, schemas)] = dict(FAMILIES)['mul']
    assert len(MUL[0]) == len(schemas) and len(MUL[2]) == len(dict(specs)[2])
    assert dict(ROW_FAMILIES)['add'] == (Add,)
    [(_, _, terms, specs, schemas)] = dict(FAMILIES)['add']
    assert len(ADD) == len(schemas) and not specs and not terms


def main():
    total = Counts()
    never = []
    t0 = time.perf_counter()
    for h in HEADS:
        family, name, heads, n, terms, rules = h
        if not heads:
            print(f"{_id(h)}: not in this SymPy")
            continue
        c = check_function(*h)
        for k in _COUNTED:
            setattr(total, k, getattr(total, k) + getattr(c, k))
        total.false += c.false
        nv = [show(name, n, r, terms) for k, r in enumerate(rules) if not c.per_rule[k]]
        never += nv
        print(_line(_id(h), len(rules), c, len(nv)), flush=True)
    name, terms, rules = POWER
    c = check_power(rules, terms)
    for k in _COUNTED:
        setattr(total, k, getattr(total, k) + getattr(c, k))
    total.false += c.false
    nv = [show_power(r, terms) for k, r in enumerate(rules) if not c.per_rule[k]]
    never += nv
    print(_line("power-Pow-2", len(rules), c, len(nv)), f"{c.absent} absent", flush=True)
    n_rules = sum(len(h[5]) for h in HEADS if h[2]) + len(rules)
    for name, schemas in SELECTION:
        c = check_selection(name, schemas)
        for k in _COUNTED:
            setattr(total, k, getattr(total, k) + getattr(c, k))
        total.false += c.false
        nv = [show_schema(name, s) for k, s in enumerate(schemas) if not c.per_rule[k]]
        never += nv
        n_rules += len(schemas)
        print(_line(f"selection-{name}", len(schemas), c, len(nv)), flush=True)
    c = check_mul(*MUL)
    for k in _COUNTED:
        setattr(total, k, getattr(total, k) + getattr(c, k))
    total.false += c.false
    nv = [show_mul_rule(k) for k in c.per_rule if not c.per_rule[k]]
    never += nv
    n_rules += len(c.per_rule)
    print(_line("mul-Mul", len(c.per_rule), c, len(nv)), f"{c.absent} absent", flush=True)
    c = check_add(ADD)
    for k in _COUNTED:
        setattr(total, k, getattr(total, k) + getattr(c, k))
    total.false += c.false
    nv = [show_schema('Add', ADD[k]) for k in c.per_rule if not c.per_rule[k]]
    never += nv
    n_rules += len(c.per_rule)
    print(_line("add-Add", len(c.per_rule), c, len(nv)), flush=True)
    print("\n" + _line("total", n_rules, total, len(never)),
          f"({time.perf_counter() - t0:.0f} s)")
    for r in never:
        print("never checked:", r)
    for r in total.false:
        print("FALSE (known):" if r in KNOWN_FALSE else "FALSE:", r)


if __name__ == '__main__':
    sys.setrecursionlimit(10000)
    main()
