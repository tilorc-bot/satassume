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
from sympy.core.power import Pow

from ._common import (
    SIGN_FLIP,
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


@registry.register(Add)
def add_templates(expr):
    args = expr.args
    n = len(args)
    if n == 0:
        return ()
    consts = consts_of(args)
    return facts(pattern_key('add', n, consts), lambda: _add_rules(n, consts),
                 consts, args + (expr,))


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
                 consts, args + (expr,))


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


def _lit(spec):
    return (spec[0], spec[1], spec[2] if len(spec) > 2 else True)


def _pow_rules(b, e, same):
    """``b``/``e`` are the constant base/exponent or ``None`` if symbolic."""
    R = Rules()
    rule = R.rule
    for prem, concl in _POW_RULES:
        rule([_lit(p) for p in prem], _lit(concl))
    if b is S.Exp1:
        for prem, concl in _POW_E_RULES:
            rule([_lit(p) for p in prem], _lit(concl))
    if same:
        rule([(_B, 'extended_nonnegative', True)], (_N, 'extended_positive', True))

    if e is not None and e.is_Rational and not e.is_Integer:
        if e.q == 2:
            # b**(k/2) for real b is imaginary iff b is a negative real.
            R.equiv([(_B, 'extended_real', True)], (_N, 'imaginary', True), (_B, 'negative', True))
            rule([(_B, 'extended_real', True)], (_N, 'extended_negative', False))
        if e.p == 1:
            # (b**(1/q))**q == b: a non-real base gives a non-real root.
            rule([(_B, 'extended_real', False)], (_N, 'extended_real', False))
        elif e.p == -1:
            # Likewise for 1/b**(1/q), but zoo**(-1/2) == 0 is real.
            rule([(_B, 'extended_real', False), (_B, 'finite', True)],
                 (_N, 'extended_real', False))
    if b is not None:
        if b is S.NegativeOne:
            rule([(_E, 'integer', True)], (_N, 'odd', True))
        elif b.is_Integer and (b.p >= 2 or b.p <= -2):
            # |b|**e < 1 for negative e.
            rule([(_E, 'negative', True)], (_N, 'integer', False))
        if b.is_algebraic and b.is_zero is False and b is not S.One:
            R.equiv([(_E, 'algebraic', True)], (_N, 'algebraic', True), (_E, 'rational', True))
    if e is not None:
        if e.is_Integer and e.p >= 2:
            # b**e for integer b >= 2 is composite.
            for prem in ge2_alternatives(_B):
                rule(prem, (_N, 'composite', True))
        if e.is_algebraic and e.is_rational is False:
            for pred in _NOT01:
                rule([(_B, pred, True), (_B, 'algebraic', True)], (_N, 'algebraic', False))
    return R.rules


@registry.register(Pow)
def pow_templates(expr):
    b, e = expr.args
    consts = {}
    if b.is_Atom and b.is_number:
        consts[_B] = b
    if e.is_Atom and e.is_number:
        consts[_E] = e
    same = b is e
    key = ('pow', const_key(b) if _B in consts else None,
           const_key(e) if _E in consts else None, same)
    return facts(key, lambda: _pow_rules(consts.get(_B), consts.get(_E), same),
                 consts, (b, e, expr))
