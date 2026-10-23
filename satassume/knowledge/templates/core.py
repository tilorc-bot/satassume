"""The rules of ``Add``, ``Mul`` and ``Pow`` that are not rows (their rows
are ``templates/add.py``, ``templates/mul.py`` and ``templates/power.py``;
``wiring.addition``, ``wiring.product`` and ``wiring.power`` call the
functions of the Add, Mul and Pow sections here): the sums of a special
shape, the factor sets and ``a/v**k``, and ``exp(I*pi*c*s)``.  The legacy
rules of ``Add`` (``_add_rules``) are no longer registered and go with the
next step of #299 (U1).

Every formula relates predicates of the node to predicates of its direct
arguments and is a theorem about the *value* of the node under SymPy's
conventions (``1/0 = zoo``, ``0**0 = 1``, ``oo - oo = nan`` is "unknown").
The rules mirror SymPy's ``_eval_is_*`` methods in
``sympy/core/{add,mul,power}.py`` except where those are unsound under
value semantics (noted inline).

Rules are index-based specs (see :mod:`._common`): argument ``k`` is index
``k`` and the node is index ``n``.  The rule base is relied on for
everything it can derive (``positive == extended_positive & finite``,
``zero == extended_nonnegative & extended_nonpositive``, ...), and
"transfer" facts from the node back to an argument are emitted only for
numeric coefficients, which is what the old assumption system relies on
(``-x``, ``2*x``, ``x/2``).
"""
from __future__ import annotations

from itertools import product
from types import MappingProxyType

from sympy import S
from sympy.core.add import Add
from sympy.core.intfunc import integer_nthroot
from sympy.functions.elementary.exponential import exp

from ...sat.formula import And, Implies, Not, Or, P
from ..domain import kept_product

from ._common import (
    Rules,
    const_key,
    consts_of,
    facts,
    lits,
)
from .table import Row, expand

#: Largest arity for per-term rules of Add (O(n^2) literals).
MAX_ONEOUT = 6
#: Largest arity for the per-term rules of Add that every arity gets (one
#: rule of n literals per term: O(n^2) literals).  Past it the strict-sign
#: rule of Add is one formula (linear with Tseitin variables,
#: :func:`_wide_one`); the others are not emitted (#180 C-WIDEADD).  The
#: rows of Mul past 32 factors: ``wiring.SOME_PER_ARGUMENT``.
MAX_ONEOUT_WIDE = 32
#: Largest arity for subtraction rules and parity case enumeration of Add.
MAX_ADD_SMALL = 3


# ---------------------------------------------------------------------------
# Add: the rules below up to the sums of a special shape are no longer
# registered (Add's rows are templates/add.py, #299) and go with the next
# step of #299 (U1); wiring.addition calls the sums of a special shape
# ---------------------------------------------------------------------------

# Closed under addition (all args -> node).  ``real``, ``zero`` and the
# finite sign predicates are derived by the rule base from these.
# ``extended_real`` is not: ``oo - oo`` is nan (see _add_rules).
_ADD_CLOSED = (
    'complex', 'integer', 'rational', 'algebraic', 'finite',
    'hermitian', 'antihermitian', 'commutative',
    'extended_positive', 'extended_negative',
    'extended_nonnegative', 'extended_nonpositive',
)

# Closed under subtraction of finite values: pred(node) & pred(rest) -> pred(a).
# (The contrapositives give "one non-integer term -> non-integer sum" etc.,
# and with the closure rules also irrational/transcendental/noninteger sums.)
_ADD_SUBTRACT = ('real', 'complex', 'integer', 'rational', 'algebraic', 'finite')

_STRICT = (('extended_positive', 'extended_nonnegative'),
           ('extended_negative', 'extended_nonpositive'))


def _add_rules(n, consts):
    R = Rules()
    rule = R.rule
    N = n
    A = range(n)

    for pred in _ADD_CLOSED:
        rule(lits(A, pred), (N, pred, True))
    # Extended reals without both +oo and -oo among the terms.
    for inf in ('positive_infinite', 'negative_infinite'):
        rule([*lits(A, 'extended_real'), *lits(A, inf, False)], (N, 'extended_real', True))
    if n > MAX_ADD_SMALL:
        rule(lits(A, 'even'), (N, 'even', True))

    # Sum of imaginaries is imaginary or zero (I + (-I) == 0).
    rule(lits(A, 'imaginary'), [(N, 'imaginary', True), (N, 'zero', True)])

    # A commutative sum has a commutative term k when every other term is a
    # finite number: k is the sum minus them.  Not in general: ``A - B`` is
    # 0 for ``B = A``, and ``A + B`` is 1 for ``B = 1 - A``.
    if n <= MAX_ONEOUT:
        for k in A:
            rest = [j for j in A if j != k]
            rule([(N, 'commutative', True), *lits(rest, 'commutative'), *lits(rest, 'finite')],
                 (k, 'commutative', True))

    for k in A if n <= MAX_ONEOUT_WIDE else ():
        rest = [j for j in A if j != k]
        # One strictly signed term among same-signed terms (wider sums:
        # _wide_one).
        for strict, nonstrict in _STRICT:
            rule([(k, strict, True), *lits(rest, nonstrict)], (N, strict, True))
        # Imaginary term plus finite reals is not real.
        rule([(k, 'imaginary', True), *lits(rest, 'real')], (N, 'extended_real', False))
        # An extended-real sum whose other terms are finite reals has an
        # extended-real term k: with r = rest real, k = oo or -oo gives
        # N = k, a finite real k gives N real, and a k that is not extended
        # real (finite non-real, zoo, or an infinity off the real axis such
        # as oo*I) gives N = k + r not extended real (nan + r = nan, the
        # same value as k).  Contrapositive: a
        # non-extended-real term plus finite reals is not extended real.
        # This is what lets ``x - z > 0`` (which says ``extended_real(x -
        # z)``) give ``extended_real(x)``, as ``x > z`` does (#53, W2B1).
        rule([(N, 'extended_real', True), *lits(rest, 'real')], (k, 'extended_real', True))
        if n <= MAX_ADD_SMALL:
            for pred in _ADD_SUBTRACT:
                rule([(N, pred, True), *lits(rest, pred)], (k, pred, True))
        elif n <= MAX_ONEOUT:
            rule([(k, 'odd', True), *lits(rest, 'even')], (N, 'odd', True))
        if n <= MAX_ONEOUT:
            # A nonzero real part (finite or infinite) cannot be cancelled by
            # imaginary terms.
            rule([(k, 'extended_nonzero', True), *lits(rest, 'imaginary')],
                 (N, 'imaginary', False))
            # Infinite sums.  ``oo - oo``, ``oo + zoo``, ``oo*I - oo*I`` and
            # ``oo + nan`` are nan ("unknown"), so two infinite terms decide
            # nothing without their directions, and a term that is not -oo
            # may still be zoo, nan or an opposite infinity off the real
            # axis (#187).  An infinite term plus finite terms is infinite
            # (``oo + I``, ``zoo + 1``, ``oo*I + x`` with x finite); signed
            # infinite sums follow from the rule below.
            rule([(k, 'infinite', True), *lits(rest, 'finite')], (N, 'infinite', True))
            # A sum with an infinite term is infinite or nan, so it is
            # infinite when it is an extended real (nan is not): an infinite
            # term plus finite ones is infinite, and two or more infinite
            # terms add to an infinity or nan.  For the same reason it is
            # no (finite) complex number (``x*y + oo*I``, ``-oo + zoo``).
            rule([(k, 'infinite', True), (N, 'extended_real', True)], (N, 'infinite', True))
            rule([(k, 'infinite', True)], (N, 'complex', False))
            for strict, nonstrict in _STRICT:
                signed = strict.replace('extended_', '') + '_infinite'
                other = _STRICT[1 if strict == _STRICT[0][0] else 0][0]
                other_signed = other.replace('extended_', '') + '_infinite'
                # A -oo term (any term, not only a constant: a symbol
                # declared negative_infinite IS -oo) plus terms that are
                # extended real and not +oo is -oo, and symmetrically for
                # +oo.  Pointwise: each other term is a finite real r or
                # -oo, and -oo + r = -oo, -oo + (-oo) = -oo.  The rest
                # cannot be weakened: -oo + oo and -oo + zoo are nan, and
                # -oo + I (finite non-real) is an infinity off the real
                # axis, not -oo.  Contrapositive (keeps node blocks
                # total): N not -oo with such a rest means k is not -oo.
                rule([(k, signed, True), *lits(rest, 'extended_real'),
                      *lits(rest, other_signed, False)], (N, signed, True))
                # A constant +oo plus terms that are >= 0 or finite real is +oo.
                if k in consts:
                    for cond in (nonstrict, 'real'):
                        rule([(k, signed, True), *lits(rest, cond)], (N, strict, True))

    # Parity of a sum of integers.
    if n <= MAX_ADD_SMALL:
        for parities in product(('even', 'odd'), repeat=n):
            result = 'odd' if parities.count('odd') % 2 else 'even'
            rule([(k, p, True) for k, p in enumerate(parities)], (N, result, True))
    # A sum of two or more positive even integers is at least 4, hence composite.
    if n >= 2:
        rule([*lits(A, 'even'), *lits(A, 'positive')], (N, 'composite', True))
        # A sum of two or more positive integers is at least 2.
        rule([*lits(A, 'integer'), *lits(A, 'positive')],
             [(N, 'prime', True), (N, 'composite', True)])
    return R.rules


#: Largest number of odd-coefficient terms whose parity cases are enumerated
#: for a sum with half-integer coefficients (2**k rules).
MAX_HALF_ODD = 4


def _half_split(args):
    """A sum ``c0 + sum(c_k*t_k)`` whose rational coefficients have least
    common denominator 2, as ``(a0 % 2, [(a_k % 2, t_k)])`` with ``a = 2*c``
    (integers), or None.

    ``c0`` is the Rational term (0 if none), a term ``c*t`` is a ``Mul``
    with a Rational first factor, any other term has coefficient 1.  None
    unless some coefficient has denominator 2 and none a larger one.
    """
    half = False
    for a in args:
        c = a if a.is_Rational else (a.args[0] if a.is_Mul and a.args[0].is_Rational else None)
        if c is not None and c.q != 1:
            if c.q != 2:
                return None
            half = True
    if not half:
        return None
    a0, terms = 0, []
    for a in args:
        if a.is_Rational:
            a0 = (a0 + (2*a).p) % 2          # an unevaluated sum has several
        else:
            ct = _coeff_term(a)
            if ct is None:
                return None
            terms.append(((2*ct[0]).p % 2, ct[1]))
    return a0, terms


def _coeff_term(a):
    """A term ``a`` of a sum as ``(c, t)`` with ``a = c*t``: ``c`` the
    Rational first factor of a ``Mul`` (1 if none), ``t`` the rest; None if
    the rest is no product of its factors (``Mul(1/2, x, 1/x)`` is not
    ``x*(1/x) = 1``, #184)."""
    if not (a.is_Mul and a.args[0].is_Rational):
        return S.One, a
    rest = a.args[1:]
    t = rest[0] if len(rest) == 1 else kept_product(rest)
    return None if t is None else (a.args[0], t)


def _half_rules(a0, odd, m):
    """Rules for ``N = (a0 + sum a_k*t_k)/2`` over integer ``t_k``: slots
    ``0..m-1`` are the terms (``odd[k]`` tells whether ``a_k`` is odd), slot
    ``m`` the node.  With every term an integer the numerator is an integer
    whose parity is ``a0`` plus the number of odd ``t_k`` with odd ``a_k``,
    and ``N`` is an integer iff that is even (``N`` is rational either way)."""
    R = Rules()
    rule = R.rule
    T = range(m)
    ints = lits(T, 'integer')
    rule(ints, (m, 'rational', True))
    O = [k for k in T if odd[k]]
    if len(O) > MAX_HALF_ODD:
        return R.rules
    for parities in product(('even', 'odd'), repeat=len(O)):
        num_odd = (a0 + parities.count('odd')) % 2
        rule([*ints, *[(k, p, True) for k, p in zip(O, parities)]], (m, 'integer', not num_odd))
    return R.rules


def _half_templates(expr, split):
    a0, terms = split
    m = len(terms)
    odd = tuple(a for a, _ in terms)
    objs = tuple(t for _, t in terms) + (expr,)
    consts = consts_of(objs[:m])
    key = ('add_half', a0, odd, tuple((k, type(c), c) for k, c in sorted(consts.items())))
    return facts(key, lambda: _half_rules(a0, odd, m), consts, objs, m)


#: Bounds of an integer ``u`` (slot 0): premises (literals of ``u``), and
#: ``(lower, b)`` for the bound they give, ``u >= b`` (``u <= b`` if not
#: ``lower``).  Each premise makes ``u`` an integer (``prime``,
#: ``composite`` and ``even`` imply it), so a strict sign bound rounds:
#: ``u > 0`` is ``u >= 1``, a prime is at least 2, a composite at least 4,
#: an odd composite at least 9, a positive even integer at least 2.  Also
#: read by :func:`_not_unit_premises` (``(c0 + c1*u)**-k`` no integer).
_INT_BOUNDS = (
    (('integer', 'extended_positive'), True, 1),
    (('prime',), True, 2),
    (('composite',), True, 4),
    (('composite', 'odd'), True, 9),
    (('even', 'extended_positive'), True, 2),
    (('integer', 'extended_nonnegative'), True, 0),
    (('integer', 'extended_negative'), False, -1),
    (('even', 'extended_negative'), False, -2),
    (('integer', 'extended_nonpositive'), False, 0),
)


def _bound_split(args):
    """A sum ``c0 + c1*u`` of a Rational ``c0`` and one other term (``c1``
    its Rational coefficient, 1 if none), as ``(c0, c1, u)``, or None."""
    if len(args) != 2:
        return None
    c0, t = args
    if not c0.is_Rational:
        c0, t = t, c0
    if not c0.is_Rational or t.is_Rational:
        return None
    ct = _coeff_term(t)
    if ct is None or ct[0] == 0 or ct[1].is_number:
        return None
    return (c0,) + ct


def _bound_rules(c0, c1):
    """Rules for ``N = c0 + c1*u`` (slot 0 ``u``, slot 1 ``N``): a bound of
    ``u`` (:data:`_INT_BOUNDS`) bounds ``N``, which signs ``N`` when the
    bound is on the right side of 0.  ``u`` is finite under every premise,
    so ``N`` is a finite real and the extended signs are the signs."""
    R = Rules()
    for prem, lower, b in _INT_BOUNDS:
        v = c0 + c1*b
        if lower == (c1.p > 0):             # N >= v
            concl = 'extended_positive' if v > 0 else 'extended_nonnegative' if v == 0 else None
        else:                               # N <= v
            concl = 'extended_negative' if v < 0 else 'extended_nonpositive' if v == 0 else None
        if concl is not None:
            R.rule([(0, p, True) for p in prem], (1, concl, True))
    return R.rules


def _bound_templates(expr, split):
    """The sign of ``c0 + c1*u`` from integer bounds of ``u``
    (:func:`_bound_rules`)."""
    c0, c1, u = split
    return facts(('add_bound', c0, c1), lambda: _bound_rules(c0, c1), {}, (u, expr), 1)


#: Bounds of ``1/v`` from those of an integer ``v`` (slot 0): premises,
#: then ``(lo, lo_open, hi, hi_open)``.  ``v`` is nonzero under each
#: premise, so ``1/v`` is a finite real.
_RECIP_BOUNDS = (
    (('integer', 'extended_positive'), (S.Zero, True, S.One, False)),
    (('prime',), (S.Zero, True, S.Half, False)),
    (('composite',), (S.Zero, True, S.One/4, False)),
    (('even', 'extended_positive'), (S.Zero, True, S.Half, False)),
    (('integer', 'extended_negative'), (-S.One, False, S.Zero, True)),
    (('even', 'extended_negative'), (-S.Half, False, S.Zero, True)),
)


def _recip_rules(c0, c1):
    """Rules for ``N = c0 + c1/v`` (slot 0 ``v``, slot 1 ``N``): the
    bounds of ``1/v`` (:data:`_RECIP_BOUNDS`) bound ``N``."""
    R = Rules()
    for prem, (lo, lo_open, hi, hi_open) in _RECIP_BOUNDS:
        a, a_open, b, b_open = c0 + c1*lo, lo_open, c0 + c1*hi, hi_open
        if c1.p < 0:
            a, a_open, b, b_open = b, b_open, a, a_open
        if a > 0 or a == 0 and a_open:
            concl = 'extended_positive'
        elif a == 0:
            concl = 'extended_nonnegative'
        elif b < 0 or b == 0 and b_open:
            concl = 'extended_negative'
        elif b == 0:
            concl = 'extended_nonpositive'
        else:
            continue
        R.rule([(0, p, True) for p in prem], (1, concl, True))
    return R.rules


def _recip_templates(expr, split):
    """The sign of ``c0 + c1/v`` from integer bounds of ``v``
    (:func:`_recip_rules`), or None if the term is no ``1/v``."""
    c0, c1, u = split
    if not (u.is_Pow and u.args[1] is S.NegativeOne) or u.args[0].is_number:
        return None
    return facts(('add_recip', c0, c1), lambda: _recip_rules(c0, c1), {},
                 (u.args[0], expr), 1)


def _imag_term(a):
    """A term ``a`` of a sum as ``(c, x)`` with ``a = c*I*x`` (``c``
    Rational, ``x`` one factor or None for ``c*I``), or None."""
    if a is S.ImaginaryUnit:
        return S.One, None
    if not a.is_Mul:
        return None
    args = a.args
    c = S.One
    if args[0].is_Rational:
        c, args = args[0], args[1:]
    rest = [f for f in args if f is not S.ImaginaryUnit]
    if len(rest) != len(args) - 1 or len(rest) > 1 or c == 0:
        return None
    return c, rest[0] if rest else None


def _imag_split(args):
    """The terms of a sum ``I*(c_1*x_1 + ... )`` as ``(c_k, x_k)``
    (:func:`_imag_term`), or None if some term is no such product."""
    terms = [_imag_term(a) for a in args]
    return None if None in terms else terms


def _imag_rules(signs, csign):
    """Rules for ``N = I*(sum c_k*x_k + c)`` (slots ``x_k``, then ``N``;
    ``signs[k]`` the sign of ``c_k``, ``csign`` the signs of the terms
    without an ``x``): the real sum is nonzero, so ``N`` imaginary, when
    every term has the same weak sign and one the strict one."""
    R = Rules()
    m = len(signs)
    for d in (1, -1):
        if -d in csign:
            continue
        weak = ['nonnegative' if s*d > 0 else 'nonpositive' for s in signs]
        strict = ['positive' if s*d > 0 else 'negative' for s in signs]
        if d in csign:
            R.rule([(k, weak[k], True) for k in range(m)], (m, 'imaginary', True))
            continue
        for j in range(m):
            R.rule([(k, strict[k] if k == j else weak[k], True) for k in range(m)],
                   (m, 'imaginary', True))
    return R.rules


def _imag_number_rules():
    """Rules for ``N == I*s`` with ``s`` a number (slot 0, slot 1 ``N``)."""
    R = Rules()
    R.rule([(0, 'real', True), (0, 'zero', False)], (1, 'imaginary', True))
    R.rule([(0, 'zero', True)], (1, 'zero', True))
    return R.rules


def _imag_templates(expr, terms):
    """``c_1*I*x_1 + ... + c*I`` is imaginary when the real sum
    ``c_1*x_1 + ... + c`` is signed: by the signs of the terms
    (:func:`_imag_rules`, at most ``MAX_ONEOUT`` with an ``x``), or, when
    every ``x`` is a number, by the sum itself, a derived node whose
    facts are closed (``-sqrt(3)*I/2 + 0.866025403784439*I``)."""
    xs = [x for _, x in terms if x is not None]
    if all(x.is_number for x in xs):
        s = Add(*[c * x if x is not None else c for c, x in terms])
        consts = {0: s} if s.is_Atom else {}
        return facts(('add_imag_number', const_key(s) if consts else None),
                     _imag_number_rules, consts, (s, expr), 1)
    if len(xs) > MAX_ONEOUT:
        return None
    signs = tuple(1 if c.p > 0 else -1 for c, x in terms if x is not None)
    csign = frozenset(1 if c.p > 0 else -1 for c, x in terms if x is None)
    consts = {k: x for k, x in enumerate(xs) if x.is_Atom and x.is_number}
    key = ('add_imag', signs, csign, tuple(sorted((k, const_key(x)) for k, x in consts.items())))
    return facts(key, lambda: _imag_rules(signs, csign), consts, tuple(xs) + (expr,), len(xs))


def _not_unit_premises(c0, c1):
    """The premises of :data:`_INT_BOUNDS` whose bound of an integer ``u``
    puts ``c0 + c1*u`` at 2 or more, or at -2 or less."""
    out = []
    for prem, lower, b in _INT_BOUNDS:
        v = c0 + c1*b
        if lower == (c1.p > 0) and v >= 2 or lower != (c1.p > 0) and v <= -2:
            out.append(prem)
    return out


def _wide_one(expr, args, consts, every, some, concl):
    """``every(t)`` for every term ``t`` and ``some(t)`` for one of them
    give ``concl(expr)``, as one formula (None if it says nothing): the
    per-term rule ``some(t_k) & every(rest) -> concl`` of a node wider
    than :data:`MAX_ONEOUT_WIDE` when ``some`` implies ``every``.  Its
    compilation is linear in the width (Tseitin variables), the per-term
    rules' quadratic.  Constant terms are decided here: one that is not
    ``every`` drops the formula."""
    weak, strong, met = [], [], False
    for k, a in enumerate(args):
        c = consts.get(k)
        if c is None:
            weak.append(P(every, a))
            strong.append(P(some, a))
        elif not getattr(c, f'is_{every}'):  # sympy-boundary: c a constant
            return None
        elif getattr(c, f'is_{some}'):  # sympy-boundary: c a constant
            met = True
    if not (met or strong):
        return None
    prem = weak if met else weak + [Or(*strong)]
    return Implies(And(*prem), P(concl, expr)) if prem else P(concl, expr)


# ---------------------------------------------------------------------------
# Mul: the rules that are not rows of templates/mul.py (wiring.product calls
# them): the factor sets and a/v**k
# ---------------------------------------------------------------------------

def _mul_factor_sets(expr):
    """The factor tuples whose Mul blocks ``wiring.product`` emits for
    ``expr``: its arguments, then the derived products."""
    args = expr.args
    n = len(args)
    # A product that another template derives from this Mul's factors is
    # a derived node here too, related to the Mul by the Mul rules over
    # (constants, product): the Mul's own block knows its factors, not the
    # product of a subset of them, so without this the deriving block
    # relates a node to a term nothing constrains (a non-total block,
    # tools/totality.py; the relation must sit in the block whose node
    # is the Mul, not in the deriving block, which is local to its node).
    out = [args]
    c = args[0]
    if n >= 3 and c.is_Rational and not c.is_zero:  # sympy-boundary: c Rational
        # c*t: the coefficient-free t of the half-integer split of an Add
        # (x + I*pi*(4*n + 1)/2 derives I*pi*(4*n + 1))
        rest = kept_product(args[1:])
        if rest is not None:
            out.append((c, rest))
    split = ipi_split(expr)
    if split is not None and split[1] is not None and split[1].is_Mul:
        # I*pi*c*s: the s of exp(I*pi*c*s) and E**(I*pi*c*s)
        c, s_ = split
        out.append(((c,) if c is not S.One else ()) + (S.ImaginaryUnit, S.Pi, s_))
    return out


def _quotient_rules():
    R = Rules()
    # odd/even**k: an odd integer over a nonzero even one, or zoo
    R.rule([(0, 'odd', True), (1, 'even', True)], (3, 'integer', False))
    return R.rules


def _quotient_templates(expr):
    """``a/v**k`` (``k`` a positive integer) is no integer for odd ``a``
    and even ``v`` (slots ``a``, ``v``, ``v**-k``, node), or None."""
    if len(expr.args) != 2:
        return None
    a, t = expr.args
    if not t.is_Pow:
        a, t = t, a
    if not t.is_Pow or t.args[0].is_number or not (t.args[1].is_Integer and t.args[1].p < 0):
        return None
    consts = {0: a} if a.is_Atom and a.is_number else {}
    return facts(('mul_quot', const_key(a) if consts else None), _quotient_rules, consts,
                 (a, t.args[0], t, expr), 3)


# ---------------------------------------------------------------------------
# Pow: the rules that are not rows of templates/power.py (wiring.power calls
# them), and exp(I*pi*c*s) (IPI_TABLE, for exp and E**(I*pi*c*s))
# ---------------------------------------------------------------------------

def _unit_angle(b):
    """``theta/pi`` as a Rational for the constants ``I``, ``-I``, ``-1``
    (``b == exp(I*pi*theta/pi)``), else None."""
    if b is S.ImaginaryUnit:
        return S.Half
    if b is S.NegativeOne:
        return S.One
    if b.is_Mul and b.args == (S.NegativeOne, S.ImaginaryUnit):
        return -S.Half
    return None


def ipi_split(arg):
    """``arg == I*pi*c*s`` structurally (a ``Mul`` with one ``I`` factor, one
    ``pi`` factor, rational coefficients ``c`` and other factors ``s``):
    returns ``(c, s)`` with ``s`` None when there are no other factors, else
    None."""
    return _pi_split(arg, True)


def pi_split(arg):
    """``arg == pi*c*s`` structurally (:func:`ipi_split` without the ``I``
    factor; an ``I`` factor is one of the factors of ``s``)."""
    return _pi_split(arg, False)


def _pi_split(arg, imag):
    if not arg.is_Mul:
        return None
    c = S.One
    rest = []
    seen_i = not imag
    seen_pi = False
    for f in arg.args:
        if f is S.ImaginaryUnit and not seen_i:
            seen_i = True
        elif f is S.Pi and not seen_pi:
            seen_pi = True
        elif f.is_Rational:
            c *= f
        else:
            rest.append(f)
    if not (seen_i and seen_pi):
        return None
    if not rest:
        return c, None
    if c.is_zero:  # sympy-boundary: c Rational
        return None                     # Mul(I, pi, 0, x): nan at x = oo
    if len(rest) == 1:
        return c, rest[0]
    s = kept_product(rest)              # Mul(I, pi, x, 1/x) is not I*pi
    return None if s is None else (c, s)


#: Conditions on ``exp(I*pi*c*s)`` (``c`` rational; ``has_s``: an ``s`` slot).
IPI_GUARDS = MappingProxyType({
    'no s': lambda x: not x['has_s'],
    's': lambda x: x['has_s'],
    'c integer': lambda x: bool(x['c'].is_integer),  # sympy-boundary: c Rational
    # sympy-boundary: c Rational
    'c even integer': lambda x: bool(x['c'].is_integer) and x['c'].p % 2 == 0,
    # sympy-boundary: c Rational
    'c odd integer': lambda x: bool(x['c'].is_integer) and x['c'].p % 2 != 0,
    'c half-odd': lambda x: not x['c'].is_integer and x['c'].q == 2,  # sympy-boundary: c Rational
    'c other': lambda x: not x['c'].is_integer and x['c'].q != 2,  # sympy-boundary: c Rational
})

# Slots: 'N' the node exp(I*pi*c*s), 'S' the s (only with an s).
def _ipi_table_rows():
    """The rows of ``IPI_TABLE`` (built on first use, :func:`_table`)."""
    return (
        Row('ipi.int', [], ('N', 'odd'), when=('no s', 'c integer')),
        Row('ipi.int.even', [], ('N', 'positive'), when=('no s', 'c even integer')),
        Row('ipi.int.odd', [], ('N', 'negative'), when=('no s', 'c odd integer')),
        Row('ipi.half.imaginary', [], ('N', 'imaginary'), when=('no s', 'c half-odd')),
        Row('ipi.half.algebraic', [], ('N', 'algebraic'), when=('no s', 'c half-odd')),
        Row('ipi.other.algebraic', [], ('N', 'algebraic'), when=('no s', 'c other')),
        Row('ipi.other.not_real', [], ('N', 'extended_real', False), when=('no s', 'c other')),
        Row('ipi.other.not_imaginary', [], ('N', 'imaginary', False), when=('no s', 'c other')),
        Row('ipi.other.nonzero', [], ('N', 'zero', False), when=('no s', 'c other')),
        Row('ipi.s.algebraic', [('S', 'integer')], ('N', 'algebraic'), when='s'),
        Row('ipi.s.complex', [('S', 'real')], ('N', 'complex'), when='s'),
        Row('ipi.s.nonzero', [('S', 'real')], ('N', 'zero', False), when='s'),
        Row('ipi.s.int', [('S', 'integer')], ('N', 'odd'), when=('s', 'c integer')),
        Row('ipi.s.int.even', [('S', 'integer')], ('N', 'positive'), when=('s', 'c even integer')),
        Row('ipi.s.int.odd.even', [('S', 'even')], ('N', 'positive'), when=('s', 'c odd integer')),
        Row('ipi.s.int.odd.odd', [('S', 'odd')], ('N', 'negative'), when=('s', 'c odd integer')),
        Row('ipi.s.int.odd.back_even', [('S', 'integer'), ('N', 'positive')], ('S', 'even'),
            when=('s', 'c odd integer')),
        Row('ipi.s.int.odd.back_odd', [('S', 'integer'), ('N', 'negative')], ('S', 'odd'),
            when=('s', 'c odd integer')),
        Row('ipi.s.half.even', [('S', 'even')], ('N', 'odd'), when=('s', 'c half-odd')),
        Row('ipi.s.half.odd', [('S', 'odd')], ('N', 'imaginary'), when=('s', 'c half-odd')),
    )


def ipi_rules(rule, c, iS, N):
    """Rules for ``node == exp(I*pi*c*s)``: a root of unity when ``s`` is an
    integer, on the unit circle when ``s`` is real.  ``iS`` is the slot of
    ``s`` (None: ``s == 1``).  The rows are ``IPI_TABLE``."""
    for _, prem, concl in expand(_table('IPI_TABLE'), IPI_GUARDS, {'c': c, 'has_s': iS is not None},
                                 {'S': iS, 'N': N}):
        rule(prem, concl)


def irrational_root(b, e):
    """``b**e`` is irrational: ``e == p/q`` is a rational non-integer
    (``gcd(p, q) == 1``) and ``b`` a positive rational that is not a perfect
    ``q``-th power, as ``b**(p/q)`` is rational iff ``b`` is one (exact
    integer arithmetic).  ``b``, ``e``: the constant base and exponent, or
    None."""
    if not (e is not None and e.is_Rational and not e.is_Integer):
        return False
    if not (b is not None and b.is_Rational and b.is_positive):  # sympy-boundary: b Rational
        return False
    return not (integer_nthroot(b.p, e.q)[1] and integer_nthroot(b.q, e.q)[1])


def _unit_power_units(angle, e, expr):
    """Unit facts for ``b**e`` with ``b == exp(I*pi*angle)`` (``I``, ``-I``,
    ``-1``) and a numeric exponent ``e == a + I*t``: the value is
    ``exp(-t*pi*angle) * exp(I*pi*a*angle)``, so it is real iff
    ``a*angle`` is an integer (positive for even, negative for odd) and
    imaginary iff ``a*angle`` is half an odd integer.  Only exact real
    parts (atomic numbers) are used."""
    a, t = e.as_real_imag()  # sympy-boundary: real/imaginary part of a closed exponent
    if not (a.is_Atom and a.is_number and t.is_Atom and t.is_number):
        return []
    out = [Not(P('zero', expr)), P('finite', expr), P('complex', expr)]
    if a.is_Rational:
        phi = a * angle
        if phi.is_Integer:
            out.append(P('positive' if phi.p % 2 == 0 else 'negative', expr))
        elif phi.q == 2:
            out.append(P('imaginary', expr))
        else:
            out.append(Not(P('extended_real', expr)))
            out.append(Not(P('imaginary', expr)))
    elif a.is_irrational:  # sympy-boundary: a an atomic number
        out.append(Not(P('extended_real', expr)))
        out.append(Not(P('imaginary', expr)))
    return out


def _exp_arg(b):
    """``u`` if ``b`` is ``exp(u)`` or ``E**u``, else None."""
    if b.is_Pow:
        return b.args[1] if b.args[0] is S.Exp1 else None
    if isinstance(b, exp):
        return b.args[0]
    return None


def _pow_bound_templates(expr):
    """``(c0 + c1*u)**e`` for a negative integer ``e`` is no integer when
    integer bounds of ``u`` put the base at 2 or more, or at -2 or less
    (slots ``u``, ``e``, base, node), or None.  The rules ask for a finite
    base, which it is under each bound, so that they read the base's own
    facts and not only those two levels down."""
    b, e = expr.args
    if not b.is_Add or (e.is_number and not (e.is_Integer and e.p < 0)):
        return None
    split = _bound_split(b.args)
    if split is None:
        return None
    c0, c1, u = split
    prems = _not_unit_premises(c0, c1)
    if not prems:
        return None

    def gen():
        R = Rules()
        for prem in prems:
            R.rule([(0, p, True) for p in prem] + [(1, 'integer', True), (1, 'negative', True),
                                                   (2, 'finite', True)],
                   (3, 'integer', False))
        return R.rules
    consts = {1: e} if e.is_number else {}
    return facts(('pow_bound', c0, c1, const_key(e) if consts else None), gen, consts,
                 (u, e, b, expr), 3)


# ---------------------------------------------------------------------------
# The tables, built on first use
# ---------------------------------------------------------------------------

#: builders of the rule tables, by module attribute name.  A table is a
#: constant (a tuple of rows), built the first time it is read: through
#: :func:`_table` here, as ``core.IPI_TABLE`` (the module ``__getattr__``)
#: elsewhere.  A query without ``exp(I*pi*c*s)`` then never builds it.
_TABLE_BUILDERS = MappingProxyType({
    'IPI_TABLE': _ipi_table_rows,
})


def _table(name: str) -> tuple:
    """The rule table ``name`` (``IPI_TABLE``), built once and then a
    module attribute."""
    t = globals().get(name)
    if t is None:
        t = globals()[name] = _TABLE_BUILDERS[name]()
    return t


def __getattr__(name: str):
    if name in _TABLE_BUILDERS:
        return _table(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
