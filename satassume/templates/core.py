"""Structural templates for ``Add``, ``Mul`` and ``Pow``.

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

from itertools import combinations, product

from sympy import S
from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.core.intfunc import integer_nthroot
from sympy.core.power import Pow
from sympy.functions.elementary.exponential import exp

from ..formula import Not, P

from ._common import (
    SIGN_FLIP,
    VOCAB,
    Rules,
    const_key,
    consts_of,
    facts,
    ge2_alternatives,
    lits,
    pattern_key,
)
from .registry import registry

#: Largest arity for per-argument rules of Mul (O(n^2) literals).
MAX_ONEOUT = 6
#: Largest arity for rules enumerating pairs of arguments.
MAX_PAIRS = 4
#: Largest arity for subtraction rules and parity case enumeration of Add.
MAX_ADD_SMALL = 3


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

# Closed under addition (all args -> node).  ``real``, ``zero`` and the
# finite sign predicates are derived by the rule base from these.
_ADD_CLOSED = (
    'extended_real', 'complex', 'integer', 'rational', 'algebraic', 'finite',
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
    if n > MAX_ADD_SMALL:
        rule(lits(A, 'even'), (N, 'even', True))

    # Sum of imaginaries is imaginary or zero (I + (-I) == 0).
    rule(lits(A, 'imaginary'), [(N, 'imaginary', True), (N, 'zero', True)])

    # Commutativity: node commutative -> every term commutative (SymPy convention).
    for k in A:
        rule([(N, 'commutative', True)], (k, 'commutative', True))

    for k in A:
        rest = [j for j in A if j != k]
        # One strictly signed term among same-signed terms.
        for strict, nonstrict in _STRICT:
            rule([(k, strict, True), *lits(rest, nonstrict)], (N, strict, True))
        # Imaginary term plus finite reals is not real.
        rule([(k, 'imaginary', True), *lits(rest, 'real')], (N, 'extended_real', False))
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
            # the like are nan ("unknown"); every other infinite sum is
            # infinite (``oo + I``, ``oo + oo*I``, ``zoo + 1``, ``-oo + I``).
            # So an infinite term that is not ``-oo`` makes the sum infinite
            # unless some other term is ``-oo``, and symmetrically.
            for strict, nonstrict in _STRICT:
                signed = strict.replace('extended_', '') + '_infinite'
                other = _STRICT[1 if strict == _STRICT[0][0] else 0][0]
                other_signed = other.replace('extended_', '') + '_infinite'
                rule([(k, 'infinite', True), (k, other_signed, False),
                      *lits(rest, other_signed, False)], (N, 'infinite', True))
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
            a0 = (2*a).p % 2
        elif a.is_Mul and a.args[0].is_Rational:
            c = a.args[0]
            rest = a.args[1:]
            terms.append(((2*c).p % 2, rest[0] if len(rest) == 1 else Mul(*rest)))
        else:
            terms.append((0, a))
    return a0, terms


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


@registry.register(Add)
def add_templates(expr):
    args = expr.args
    n = len(args)
    if n == 0:
        return ()
    consts = consts_of(args)
    out = facts(pattern_key('add', n, consts), lambda: _add_rules(n, consts),
                consts, args + (expr,), n)
    split = _half_split(args)
    if split is not None:
        return [out, _half_templates(expr, split)]
    return out


# ---------------------------------------------------------------------------
# Mul
# ---------------------------------------------------------------------------

# Closed under multiplication.  ``real`` and ``positive`` are derived by the
# rule base (``extended_* & finite``).
_MUL_CLOSED = (
    'extended_real', 'complex', 'integer', 'rational', 'algebraic', 'finite',
    'commutative', 'extended_positive', 'nonnegative',
)

# Backward transfer for a nonzero real numeric coefficient c: pred(c*x) -> pred(x)
# (sign predicates flipped for negative c).  The forward directions follow
# from the closure and per-argument rules.
_COEFF_BACK = (
    'positive', 'negative', 'nonnegative', 'nonpositive',
    'extended_positive', 'extended_negative', 'real', 'extended_real',
    'finite', 'complex', 'imaginary',
)


def _mul_rules(n, consts):
    R = Rules()
    rule = R.rule
    N = n
    A = range(n)

    for pred in _MUL_CLOSED:
        rule(lits(A, pred), (N, pred, True))
    for k in A:
        rule([(N, 'commutative', True)], (k, 'commutative', True))

    # Zero: some zero factor with the rest finite; nonzero: all nonzero.
    for k in A:
        rule([(k, 'zero', True), *lits([j for j in A if j != k], 'finite')], (N, 'zero', True))
    rule([], [*lits(A, 'zero'), (N, 'zero', False)])

    # Hermitian product of commuting hermitian factors.
    rule([*lits(A, 'commutative'), *lits(A, 'hermitian')], (N, 'hermitian', True))

    # Polar: all polar, or one polar factor and the rest positive.
    rule(lits(A, 'polar'), (N, 'polar', True))
    for k in A:
        rule([(k, 'polar', True), *lits([j for j in A if j != k], 'positive')],
             (N, 'polar', True))

    if n >= 2:
        rule(lits(A, 'prime'), (N, 'composite', True))

    # All factors negative / nonpositive / imaginary: parity of n.
    even_n = n % 2 == 0
    rule(lits(A, 'extended_negative'),
         (N, 'extended_positive' if even_n else 'extended_negative', True))
    rule(lits(A, 'nonpositive'), (N, 'nonnegative' if even_n else 'nonpositive', True))
    rule(lits(A, 'imaginary'), (N, 'nonzero' if even_n else 'imaginary', True))
    rule(lits(A, 'odd'), (N, 'odd', True))

    if n <= MAX_ONEOUT:
        for k in A:
            rest = [j for j in A if j != k]
            # One infinite factor and the rest nonzero -> infinite.
            rule([(k, 'infinite', True), *lits(rest, 'zero', False)], (N, 'infinite', True))
            # Exactly one negative factor (rest positive) -> negative.
            rule([(k, 'extended_negative', True), *lits(rest, 'extended_positive')],
                 (N, 'extended_negative', True))
            rule([(k, 'nonpositive', True), *lits(rest, 'nonnegative')], (N, 'nonpositive', True))
            # One even factor and the rest integers -> even.
            rule([(k, 'even', True), *lits(rest, 'integer')], (N, 'even', True))
            # One composite factor and the rest integers -> not prime (the
            # product is 0, negative, or a multiple of a composite).
            rule([(k, 'composite', True), *lits(rest, 'integer')], (N, 'prime', False))
            # One irrational factor and the rest nonzero rationals -> irrational.
            rule([(k, 'irrational', True), *lits(rest, 'rational'), *lits(rest, 'zero', False)],
                 (N, 'irrational', True))
            # One non-real factor and the rest nonzero extended reals -> not real.
            rule([(k, 'extended_real', False), *lits(rest, 'extended_nonzero')],
                 (N, 'extended_real', False))
            # One imaginary factor and the rest nonzero finite reals -> imaginary;
            # with the rest merely real the product may also be zero.
            rule([(k, 'imaginary', True), *lits(rest, 'real'), *lits(rest, 'zero', False)],
                 (N, 'imaginary', True))
            rule([(k, 'imaginary', True), *lits(rest, 'real')],
                 [(N, 'imaginary', True), (N, 'zero', True)])
            if n == 2:
                # i*a*(c + i*d) has real part -a*d and imaginary part a*c:
                # the product is real iff the other factor is imaginary or
                # zero, and imaginary iff the other factor is a nonzero real.
                l = rest[0]
                rule([(k, 'imaginary', True), (l, 'complex', True), (N, 'extended_real', True)],
                     [(l, 'imaginary', True), (l, 'zero', True)])
                rule([(k, 'imaginary', True), (l, 'complex', True), (N, 'imaginary', True)],
                     (l, 'real', True))

    if 3 <= n <= MAX_PAIRS:
        # Sign of a product with m negative factors, 2 <= m < n (one negative
        # factor is above, all negative is above).
        for m in range(2, n):
            for neg in combinations(A, m):
                rest = [j for j in A if j not in neg]
                sign = 'extended_positive' if m % 2 == 0 else 'extended_negative'
                rule([*lits(neg, 'extended_negative'), *lits(rest, 'extended_positive')],
                     (N, sign, True))
                sign = 'nonnegative' if m % 2 == 0 else 'nonpositive'
                rule([*lits(neg, 'nonpositive'), *lits(rest, 'nonnegative')], (N, sign, True))
        for k, l in combinations(A, 2):
            rest = [j for j in A if j != k and j != l]
            rule([(k, 'imaginary', True), (l, 'imaginary', True),
                  *lits(rest, 'real'), *lits(rest, 'zero', False)], (N, 'nonzero', True))

    # Numeric coefficient c*x: transfer facts back from the product to x.
    if n == 2 and 0 in consts and consts[0].is_Number:
        c = consts[0]
        if c.is_finite and c.is_extended_real and not c.is_zero:
            flip = c.is_negative
            for pred in _COEFF_BACK:
                rule([(N, pred, True)], (1, SIGN_FLIP.get(pred, pred) if flip else pred, True))
            if c.is_Rational:
                rule([(N, 'rational', True)], (1, 'rational', True))
                rule([(N, 'algebraic', True)], (1, 'algebraic', True))
                if c.q == 2:
                    # (p/2)*x for integer x is an integer iff x is even.
                    R.equiv([(1, 'integer', True)], (N, 'integer', True), (1, 'even', True))
                elif c is S.NegativeOne:
                    for pred in ('integer', 'even', 'odd'):
                        rule([(N, pred, True)], (1, pred, True))
    return R.rules


@registry.register(Mul)
def mul_templates(expr):
    args = expr.args
    n = len(args)
    if n == 0:
        return ()
    consts = consts_of(args)
    return facts(pattern_key('mul', n, consts), lambda: _mul_rules(n, consts),
                 consts, args + (expr,), n)


# ---------------------------------------------------------------------------
# Pow
# ---------------------------------------------------------------------------

# Indices: base 0, exponent 1, node 2.  Rules are ((premises), conclusion)
# with literals (index, pred) or (index, pred, False).
_B, _E, _N = 0, 1, 2
_POW_RULES = (
    # --- sign ---
    (((_B, 'positive'), (_E, 'real')), (_N, 'positive')),
    (((_B, 'extended_positive'), (_E, 'positive')), (_N, 'extended_positive')),
    (((_B, 'extended_positive'), (_E, 'extended_real')), (_N, 'extended_nonnegative')),
    (((_B, 'extended_nonnegative'), (_E, 'extended_nonnegative')), (_N, 'extended_nonnegative')),
    (((_B, 'extended_nonnegative'), (_E, 'extended_real')), (_N, 'extended_negative', False)),
    (((_B, 'extended_real'), (_E, 'even')), (_N, 'extended_negative', False)),
    (((_B, 'nonzero'), (_E, 'even')), (_N, 'positive')),
    # (-oo)**(-2) == 0, so the extended version needs a nonnegative exponent.
    (((_B, 'extended_negative'), (_E, 'even'), (_E, 'nonnegative')), (_N, 'extended_positive')),
    (((_B, 'negative'), (_E, 'odd')), (_N, 'negative')),
    (((_B, 'extended_negative'), (_E, 'odd')), (_N, 'extended_nonpositive')),
    (((_B, 'extended_nonpositive'), (_E, 'odd')), (_N, 'extended_positive', False)),
    (((_N, 'positive'), (_B, 'real'), (_E, 'odd')), (_B, 'positive')),
    (((_N, 'negative'), (_B, 'real'), (_E, 'odd')), (_B, 'negative')),
    # --- zero base, zero exponent (b**0 == 1, also for zoo and nan) ---
    (((_B, 'zero'), (_E, 'extended_positive')), (_N, 'zero')),
    (((_B, 'zero'), (_E, 'extended_nonpositive')), (_N, 'zero', False)),
    (((_B, 'zero'), (_E, 'extended_negative')), (_N, 'infinite')),
    (((_E, 'zero'),), (_N, 'positive')),
    # SymPy leaves ``oo**0.0`` unevaluated and calls it non-integer.
    (((_E, 'zero'), (_B, 'finite')), (_N, 'odd')),
    # --- zero / nonzero / finite / infinite ---
    (((_B, 'zero', False), (_B, 'finite'), (_E, 'finite')), (_N, 'zero', False)),
    (((_B, 'infinite'), (_E, 'negative')), (_N, 'zero')),
    (((_B, 'zero', False), (_E, 'nonnegative')), (_N, 'zero', False)),
    (((_B, 'finite'), (_E, 'negative')), (_N, 'zero', False)),
    (((_B, 'finite'), (_E, 'finite'), (_E, 'nonnegative')), (_N, 'finite')),
    (((_B, 'finite'), (_E, 'finite'), (_B, 'zero', False)), (_N, 'finite')),
    (((_B, 'infinite'), (_E, 'positive')), (_N, 'infinite')),
    # --- integer / rational ---
    (((_B, 'integer'), (_E, 'integer'), (_E, 'nonnegative')), (_N, 'integer')),
    (((_B, 'even'), (_E, 'integer'), (_E, 'positive')), (_N, 'even')),
    (((_B, 'odd'), (_E, 'integer'), (_E, 'nonnegative')), (_N, 'odd')),
    (((_B, 'rational'), (_B, 'integer', False), (_E, 'rational'), (_E, 'positive')),
     (_N, 'integer', False)),
    (((_B, 'rational'), (_E, 'integer'), (_E, 'nonnegative')), (_N, 'rational')),
    (((_B, 'rational'), (_E, 'integer'), (_B, 'zero', False)), (_N, 'rational')),
    # --- extended real / imaginary ---
    (((_B, 'extended_nonzero'), (_E, 'integer')), (_N, 'extended_real')),
    (((_B, 'extended_real'), (_E, 'integer'), (_E, 'nonnegative')), (_N, 'extended_real')),
    (((_B, 'negative'), (_E, 'real'), (_E, 'integer', False)), (_N, 'extended_real', False)),
    (((_B, 'extended_real'), (_E, 'integer')), (_N, 'imaginary', False)),
    (((_B, 'extended_real'), (_E, 'extended_real'), (_E, 'rational', False)),
     (_N, 'imaginary', False)),
    (((_B, 'positive'), (_E, 'extended_real')), (_N, 'imaginary', False)),
    (((_B, 'imaginary'), (_E, 'even')), (_N, 'nonzero')),
    (((_B, 'imaginary'), (_E, 'odd')), (_N, 'imaginary')),
    # --- complex ---
    (((_B, 'complex'), (_E, 'complex'), (_B, 'zero', False)), (_N, 'complex')),
    (((_B, 'complex'), (_E, 'complex'), (_E, 'nonnegative')), (_N, 'complex')),
    # --- prime ---
    (((_B, 'integer'), (_E, 'prime')), (_N, 'prime', False)),
    (((_B, 'integer'), (_E, 'even'), (_E, 'positive')), (_N, 'prime', False)),
    # --- algebraic ---
    (((_B, 'algebraic'), (_E, 'rational'), (_B, 'zero', False)), (_N, 'algebraic')),
    (((_B, 'algebraic'), (_E, 'rational'), (_E, 'positive')), (_N, 'algebraic')),
    (((_B, 'transcendental'), (_E, 'rational'), (_E, 'zero', False)), (_N, 'algebraic', False)),
    # --- polar / commutative ---
    (((_B, 'polar'),), (_N, 'polar')),
    (((_B, 'commutative'), (_E, 'commutative')), (_N, 'commutative')),
    (((_N, 'commutative'),), (_B, 'commutative')),
    (((_N, 'commutative'),), (_E, 'commutative')),
)

_POW_E_RULES = (
    (((_E, 'extended_real'),), (_N, 'extended_real')),
    (((_E, 'extended_real'),), (_N, 'extended_nonnegative')),
    (((_E, 'real'),), (_N, 'positive')),
    (((_E, 'complex'),), (_N, 'complex')),
    (((_E, 'extended_negative'),), (_N, 'complex')),
    (((_E, 'finite'),), (_N, 'finite')),
    (((_E, 'finite'),), (_N, 'zero', False)),
    (((_E, 'algebraic'), (_E, 'zero', False)), (_N, 'transcendental')),
    (((_E, 'infinite'), (_E, 'extended_negative')), (_N, 'zero')),
)

# Gelfond-Schneider: for algebraic b not in {0, 1} and algebraic e,
# b**e is algebraic iff e is rational.  Ways to say "b not in {0, 1}":
_NOT01 = ('irrational', 'noninteger', 'negative', 'prime', 'composite')
# Ways to say "b is real with |b| not in {0, 1}".
_NOTUNIT = ('irrational', 'noninteger', 'prime', 'composite')

# Pow(x, 1) is x.
_POW_ONE_EQUIV = tuple(sorted(VOCAB - {'commutative'}))

# Extra object slots after base 0, exponent 1, node 2 (see ``pow_templates``).
_U, _S, _T, _BM, _BP = 3, 4, 5, 6, 7


def _lit(spec):
    return (spec[0], spec[1], spec[2] if len(spec) > 2 else True)


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
    if not arg.is_Mul:
        return None
    c = S.One
    rest = []
    seen_i = seen_pi = False
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
    return c, (None if not rest else rest[0] if len(rest) == 1 else Mul(*rest))


def ipi_rules(rule, c, iS, N):
    """Rules for ``node == exp(I*pi*c*s)``: a root of unity when ``s`` is an
    integer, on the unit circle when ``s`` is real.  ``iS`` is the slot of
    ``s`` (None: ``s == 1``)."""
    if iS is None:
        if c.is_integer:
            rule([], (N, 'odd', True))
            rule([], (N, 'positive' if c.p % 2 == 0 else 'negative', True))
        elif c.q == 2:
            rule([], (N, 'imaginary', True))
            rule([], (N, 'algebraic', True))
        else:
            for lit in ((N, 'algebraic', True), (N, 'extended_real', False),
                        (N, 'imaginary', False), (N, 'zero', False)):
                rule([], lit)
        return
    rule([(iS, 'integer', True)], (N, 'algebraic', True))
    rule([(iS, 'real', True)], (N, 'complex', True))
    rule([(iS, 'real', True)], (N, 'zero', False))
    if c.is_integer:
        rule([(iS, 'integer', True)], (N, 'odd', True))
        if c.p % 2 == 0:
            rule([(iS, 'integer', True)], (N, 'positive', True))
        else:
            rule([(iS, 'even', True)], (N, 'positive', True))
            rule([(iS, 'odd', True)], (N, 'negative', True))
            rule([(iS, 'integer', True), (N, 'positive', True)], (iS, 'even', True))
            rule([(iS, 'integer', True), (N, 'negative', True)], (iS, 'odd', True))
    elif c.q == 2:
        rule([(iS, 'even', True)], (N, 'odd', True))
        rule([(iS, 'odd', True)], (N, 'imaginary', True))


def _pow_rules(b, e, same, angle, has_u, ipi, has_t, has_b1):
    """``b``/``e`` are the constant base/exponent or ``None`` if symbolic;
    ``angle`` is ``_unit_angle(base)``; ``has_u``: slot ``_U`` holds the
    argument of an ``exp`` base; ``ipi``: ``(c, has_s)`` for base ``E`` and
    exponent ``I*pi*c*s``; ``has_t``: slot ``_T`` holds ``2*e``; ``has_b1``:
    slots ``_BM``/``_BP`` hold ``b - 1`` and ``b + 1``."""
    R = Rules()
    rule = R.rule
    for prem, concl in _POW_RULES:
        rule([_lit(p) for p in prem], _lit(concl))
    if b is S.Exp1:
        for prem, concl in _POW_E_RULES:
            rule([_lit(p) for p in prem], _lit(concl))
        if ipi is not None:
            c, has_s = ipi
            ipi_rules(rule, c, _S if has_s else None, _N)
    if same:
        rule([(_B, 'extended_nonnegative', True)], (_N, 'extended_positive', True))
    if e is S.One:
        for pred in _POW_ONE_EQUIV:
            R.equiv([], (_N, pred, True), (_B, pred, True))
    # A power of a composite is 1, a fraction or composite.
    rule([(_B, 'composite', True), (_E, 'integer', True)], (_N, 'prime', False))
    # For algebraic b = r*exp(I*phi) != 0 and algebraic e = I*t, b**e is
    # exp(-t*phi)*exp(I*t*log(r)) with r algebraic; t*log(r) in pi*Q with
    # t algebraic nonzero forces log(r)/(I*pi) algebraic, hence rational
    # (Gelfond-Schneider), hence r == 1.  So b**e is never imaginary, and
    # it is real iff |b| == 1 (then it is positive).
    rule([(_B, 'algebraic', True), (_B, 'zero', False), (_E, 'imaginary', True),
          (_E, 'algebraic', True)], (_N, 'imaginary', False))
    for pred in _NOTUNIT:
        rule([(_B, pred, True), (_B, 'algebraic', True), (_E, 'imaginary', True),
              (_E, 'algebraic', True)], (_N, 'extended_real', False))
    if angle is not None:
        rule([(_E, 'imaginary', True)], (_N, 'positive', True))
    if has_u:
        # (exp(u))**e == exp(e*(u - 2*pi*I*k)) is positive for imaginary u, e.
        rule([(_U, 'imaginary', True), (_E, 'imaginary', True)], (_N, 'positive', True))
    if has_b1:
        # An integer other than 0 and +-1 to a negative integer power is a
        # fraction (0 gives zoo).
        rule([(_B, 'integer', True), (_E, 'integer', True), (_E, 'negative', True),
              (_BM, 'zero', False), (_BP, 'zero', False)], (_N, 'integer', False))
    if has_t:
        # Real base, rational exponent: imaginary iff the base is negative
        # and the exponent is half an odd integer.
        rule([(_B, 'extended_real', True), (_E, 'rational', True), (_T, 'integer', False)],
             (_N, 'imaginary', False))
        rule([(_B, 'negative', True), (_E, 'rational', True), (_T, 'integer', True),
              (_E, 'integer', False)], (_N, 'imaginary', True))

    if e is not None and e.is_Rational and not e.is_Integer:
        if e.q == 2:
            # b**(k/2) for real b is imaginary iff b is a negative real.
            R.equiv([(_B, 'extended_real', True)], (_N, 'imaginary', True), (_B, 'negative', True))
            rule([(_B, 'extended_real', True)], (_N, 'extended_negative', False))
        else:
            rule([(_B, 'extended_real', True)], (_N, 'imaginary', False))
        if e.p == 1:
            # (b**(1/q))**q == b: a non-real base gives a non-real root.
            rule([(_B, 'extended_real', False)], (_N, 'extended_real', False))
        elif e.p == -1:
            # Likewise for 1/b**(1/q), but zoo**(-1/2) == 0 is real.
            rule([(_B, 'extended_real', False), (_B, 'finite', True)],
                 (_N, 'extended_real', False))
        if b is not None and b.is_Rational and b.is_positive:
            # b**(p/q) with gcd(p, q) == 1 is rational iff b is a perfect
            # q-th power (exact integer arithmetic).
            if not (integer_nthroot(b.p, e.q)[1] and integer_nthroot(b.q, e.q)[1]):
                rule([], (_N, 'irrational', True))
    if e is S.NegativeOne:
        # 1/b is rational iff b is (nonzero) rational.
        rule([(_B, 'irrational', True)], (_N, 'irrational', True))
    if b is not None:
        if b is S.NegativeOne:
            rule([(_E, 'integer', True)], (_N, 'odd', True))
        elif b.is_Integer and (b.p >= 2 or b.p <= -2):
            # |b|**e < 1 for negative e.
            rule([(_E, 'negative', True)], (_N, 'integer', False))
        if b.is_algebraic and b.is_zero is False and b is not S.One:
            R.equiv([(_E, 'algebraic', True)], (_N, 'algebraic', True), (_E, 'rational', True))
        if b.is_Number and b.is_finite:
            # Exact comparisons of a number with 1 (no assumptions involved).
            if abs(b) > 1:
                rule([(_E, 'extended_negative', True)], (_N, 'finite', True))
                rule([(_E, 'negative_infinite', True)], (_N, 'zero', True))
                rule([(_E, 'positive_infinite', True)], (_N, 'infinite', True))
            elif b.is_zero is False and abs(b) < 1:
                rule([(_E, 'extended_positive', True)], (_N, 'finite', True))
                rule([(_E, 'positive_infinite', True)], (_N, 'zero', True))
                rule([(_E, 'negative_infinite', True)], (_N, 'infinite', True))
    if e is not None:
        if e.is_Integer and e.p >= 2:
            # b**e for integer b >= 2 is composite.
            for prem in ge2_alternatives(_B):
                rule(prem, (_N, 'composite', True))
        if e.is_algebraic and e.is_rational is False:
            for pred in _NOT01:
                rule([(_B, pred, True), (_B, 'algebraic', True)], (_N, 'algebraic', False))
    return R.rules


def _unit_power_units(angle, e, expr):
    """Unit facts for ``b**e`` with ``b == exp(I*pi*angle)`` (``I``, ``-I``,
    ``-1``) and a numeric exponent ``e == a + I*t``: the value is
    ``exp(-t*pi*angle) * exp(I*pi*a*angle)``, so it is real iff
    ``a*angle`` is an integer (positive for even, negative for odd) and
    imaginary iff ``a*angle`` is half an odd integer.  Only exact real
    parts (atomic numbers) are used."""
    a, t = e.as_real_imag()
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
    elif a.is_irrational:
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


@registry.register(Pow)
def pow_templates(expr):
    b, e = expr.args
    consts = {}
    if b.is_Atom and b.is_number:
        consts[_B] = b
    if e.is_Atom and e.is_number:
        consts[_E] = e
    same = b is e
    angle = _unit_angle(b)
    objs = [b, e, expr, None, None, None, None, None]
    u = _exp_arg(b)
    if u is not None:
        objs[_U] = u
        if u.is_Atom and u.is_number:
            consts[_U] = u
    ipi = None
    if b is S.Exp1 and _E not in consts:
        split = ipi_split(e)
        if split is not None:
            c, s_ = split
            ipi = (c, s_ is not None)
            if s_ is not None:
                objs[_S] = s_
                if s_.is_Atom and s_.is_number:
                    consts[_S] = s_
    has_t = _E not in consts and not e.is_number
    if has_t:
        objs[_T] = Mul(S(2), e)
    has_b1 = has_t and _B not in consts and not b.is_number
    if has_b1:
        objs[_BM] = b - S.One
        objs[_BP] = b + S.One
    key = ('pow', const_key(b) if _B in consts else None,
           const_key(e) if _E in consts else None, same, angle,
           const_key(u) if _U in consts else u is not None, ipi,
           const_key(objs[_S]) if _S in consts else None, has_t, has_b1)
    out = facts(key, lambda: _pow_rules(consts.get(_B), consts.get(_E), same, angle,
                                        u is not None, ipi, has_t, has_b1),
                consts, tuple(objs), _N)
    if angle is not None and e.is_number:
        return [out, *_unit_power_units(angle, e, expr)]
    return out
