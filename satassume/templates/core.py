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

from itertools import product
from types import MappingProxyType

from sympy import S
from sympy.core.add import Add
from sympy.core.mul import Mul
from sympy.core.intfunc import integer_nthroot
from sympy.core.power import Pow
from sympy.functions.elementary.exponential import exp

from ..formula import Not, P
from ..rules import BASIS, expand_clause

from ._common import (
    VOCAB,
    Rules,
    const_key,
    consts_of,
    facts,
    lits,
    pattern_key,
    resolve,
)
from .registry import registry
from .table import Row, Section, Sub, expand, rules_of

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
# finite sign predicates are derived by the rule base from these, and the
# other extended signs from extended_nonnegative and the other Add rules.
# ``extended_real`` is not: ``oo - oo`` is nan (see _add_rules).
_ADD_CLOSED = (
    'complex', 'integer', 'rational', 'algebraic', 'finite',
    'hermitian', 'antihermitian', 'commutative',
    'extended_nonnegative',
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
    # Extended reals without both +oo and -oo among the terms (not implied
    # by the other rules for 7 or more terms: rd/semdrop review)
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

    for k in A:
        rest = [j for j in A if j != k]
        # One strictly signed term among same-signed terms.
        for strict, nonstrict in _STRICT:
            rule([(k, strict, True), *lits(rest, nonstrict)], (N, strict, True))
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
# rule base (``extended_* & finite``).  ``extended_real`` is not: ``0*oo``
# is nan (see _mul_rules).
_MUL_CLOSED = (
    'complex', 'integer', 'rational', 'algebraic', 'finite',
    'commutative', 'extended_positive',
)

# Backward transfer for a nonzero real numeric coefficient c: pred(c*x) -> pred(x)
# (sign predicates flipped for negative c).  The forward directions follow
# from the closure and per-argument rules.
_COEFF_BACK = (
    'positive', 'negative', 'nonnegative', 'nonpositive',
    'extended_positive', 'extended_negative', 'real', 'extended_real',
    'finite', 'complex', 'imaginary',
)


def _coeff(ctx):
    """``c*x`` with ``c`` a finite nonzero real number (slot 0) and n == 2."""
    consts = ctx['consts']
    if not (ctx['n'] == 2 and 0 in consts and consts[0].is_Number):
        return False
    c = consts[0]
    return bool(c.is_finite and c.is_extended_real and not c.is_zero)


#: Conditions on the pattern of a Mul (``n`` arguments, ``consts``; ``m``
#: the size of the negative set in a ``negsets`` section).
MUL_GUARDS = MappingProxyType({
    'n<=MAX_ONEOUT': lambda c: c['n'] <= MAX_ONEOUT,
    'n>MAX_ONEOUT': lambda c: c['n'] > MAX_ONEOUT,
    'n>=2': lambda c: c['n'] >= 2,
    'n==2': lambda c: c['n'] == 2,
    'n even': lambda c: c['n'] % 2 == 0,
    'n odd': lambda c: c['n'] % 2 != 0,
    '3<=n<=MAX_PAIRS': lambda c: 3 <= c['n'] <= MAX_PAIRS,
    'm even': lambda c: c['m'] % 2 == 0,
    'm odd': lambda c: c['m'] % 2 != 0,
    'coeff': _coeff,
    'c negative': lambda c: bool(c['consts'][0].is_negative),
    'c not negative': lambda c: not c['consts'][0].is_negative,
    'c rational': lambda c: bool(c['consts'][0].is_Rational),
    'c.q==2': lambda c: c['consts'][0].q == 2,
    'c==-1': lambda c: c['consts'][0] is S.NegativeOne,
})

# Slots: 'N' the node, '*' all arguments; in a section 'k' the argument of
# the iteration, 'rest' the others ('l' the other one when there is one),
# 'neg' the negative set; 0 and 1 the coefficient and the other factor.
def _mul_table_rows():
    """The rows of ``MUL_TABLE`` (built on first use, :func:`_table`)."""
    return (
        Row('closed', [('*', '$p')], ('N', '$p'), preds=_MUL_CLOSED),
        # Extended reals, all finite or all nonzero (no 0*oo).
        Row('ext_real.finite', [('*', 'extended_real'), ('*', 'finite')], ('N', 'extended_real')),
        Row('ext_real.nonzero', [('*', 'extended_real'), ('*', 'zero', False)],
            ('N', 'extended_real')),
        # A commutative product has a commutative factor k when every other
        # factor is a nonzero number: k is the product divided by them.  Not
        # in general: ``0*A == 0`` (#47), and ``A*B`` is 1 for ``B = A**-1``.
        Section('each', when='n<=MAX_ONEOUT', rows=[
            Row('commutative.back',
                [('N', 'commutative'), ('rest', 'complex'), ('rest', 'zero', False)],
                ('k', 'commutative')),
        ]),
        # Zero: some zero factor with the rest finite; nonzero: all nonzero and
        # at most one of them non-commutative (non-commutative values have zero
        # divisors: ``A*B == 0`` and ``A**2 == 0`` for nilpotent ``A = B``).
        Section('each', rows=[
            Row('zero', [('k', 'zero'), ('rest', 'finite')], ('N', 'zero')),
        ]),
        Section('each', when='n<=MAX_ONEOUT', rows=[
            Row('nonzero', [('rest', 'commutative')], [('*', 'zero'), ('N', 'zero', False)]),
        ]),
        Row('nonzero.commutative', [('*', 'commutative')], [('*', 'zero'), ('N', 'zero', False)],
            when='n>MAX_ONEOUT'),
        # Hermitian product of commuting hermitian factors.
        Row('hermitian', [('*', 'commutative'), ('*', 'hermitian')], ('N', 'hermitian')),
        # Polar: all polar, or one polar factor and the rest positive.
        Row('polar', [('*', 'polar')], ('N', 'polar')),
        Section('each', rows=[
            Row('polar.one', [('k', 'polar'), ('rest', 'positive')], ('N', 'polar')),
        ]),
        Row('primes', [('*', 'prime')], ('N', 'composite'), when='n>=2'),
        # All factors negative / nonpositive / imaginary: parity of n.
        Row('all_neg.even', [('*', 'extended_negative')], ('N', 'extended_positive'),
            when='n even'),
        Row('all_neg.odd', [('*', 'extended_negative')], ('N', 'extended_negative'), when='n odd'),
        Row('all_nonpos.even', [('*', 'nonpositive')], ('N', 'nonnegative'), when='n even'),
        Row('all_nonpos.odd', [('*', 'nonpositive')], ('N', 'nonpositive'), when='n odd'),
        Row('all_imag.even', [('*', 'imaginary')], ('N', 'nonzero'), when='n even'),
        Row('all_imag.odd', [('*', 'imaginary')], ('N', 'imaginary'), when='n odd'),
        Row('all_odd', [('*', 'odd')], ('N', 'odd')),
        Section('each', when='n<=MAX_ONEOUT', rows=[
            # One infinite factor and the rest nonzero -> infinite.
            Row('one_infinite', [('k', 'infinite'), ('rest', 'zero', False)], ('N', 'infinite')),
            # Exactly one negative factor (rest positive) -> negative.
            Row('one_neg', [('k', 'extended_negative'), ('rest', 'extended_positive')],
                ('N', 'extended_negative')),
            Row('one_nonpos', [('k', 'nonpositive'), ('rest', 'nonnegative')],
                ('N', 'nonpositive')),
            # One even factor and the rest integers -> even.
            Row('one_even', [('k', 'even'), ('rest', 'integer')], ('N', 'even')),
            # One composite factor and the rest integers -> not prime (the
            # product is 0, negative, or a multiple of a composite).
            Row('one_composite', [('k', 'composite'), ('rest', 'integer')], ('N', 'prime', False)),
            # One irrational factor and the rest nonzero rationals -> irrational.
            Row('one_irrational',
                [('k', 'irrational'), ('rest', 'rational'), ('rest', 'zero', False)],
                ('N', 'irrational')),
            # One transcendental factor and the rest nonzero algebraics ->
            # transcendental (the algebraic numbers are a field).
            Row('one_transcendental',
                [('k', 'transcendental'), ('rest', 'algebraic'), ('rest', 'zero', False)],
                ('N', 'transcendental')),
            # One non-real factor and the rest nonzero extended reals -> not real.
            Row('one_non_real', [('k', 'extended_real', False), ('rest', 'extended_nonzero')],
                ('N', 'extended_real', False)),
            # One imaginary factor and the rest nonzero finite reals -> imaginary;
            # with the rest merely real the product may also be zero.
            Row('one_imag', [('k', 'imaginary'), ('rest', 'real'), ('rest', 'zero', False)],
                ('N', 'imaginary')),
            # i*a*(c + i*d) has real part -a*d and imaginary part a*c:
            # the product is real iff the other factor is imaginary or
            # zero, and imaginary iff the other factor is a nonzero real.
            Row('imag_times.real', [('k', 'imaginary'), ('l', 'complex'), ('N', 'extended_real')],
                [('l', 'imaginary'), ('l', 'zero')], when='n==2'),
            Row('imag_times.imag', [('k', 'imaginary'), ('l', 'complex'), ('N', 'imaginary')],
                ('l', 'real'), when='n==2'),
        ]),
        # Sign of a product with m negative factors, 2 <= m < n (one negative
        # factor is above, all negative is above).
        Section('negsets', when='3<=n<=MAX_PAIRS', rows=[
            Row('m_neg.even', [('neg', 'extended_negative'), ('rest', 'extended_positive')],
                ('N', 'extended_positive'), when='m even'),
            Row('m_neg.odd', [('neg', 'extended_negative'), ('rest', 'extended_positive')],
                ('N', 'extended_negative'), when='m odd'),
            Row('m_nonpos.even', [('neg', 'nonpositive'), ('rest', 'nonnegative')],
                ('N', 'nonnegative'), when='m even'),
            Row('m_nonpos.odd', [('neg', 'nonpositive'), ('rest', 'nonnegative')],
                ('N', 'nonpositive'), when='m odd'),
        ]),
        Section('pairs', when='3<=n<=MAX_PAIRS', rows=[
            Row('two_imag', [('k', 'imaginary'), ('l', 'imaginary'), ('rest', 'real'),
                             ('rest', 'zero', False)], ('N', 'nonzero')),
        ]),
        # Numeric coefficient c*x: transfer facts back from the product to x.
        Row('coeff.back', [('N', '$p')], (1, '$p'), when=('coeff', 'c not negative'),
            preds=_COEFF_BACK),
        Row('coeff.back.flip', [('N', '$p')], (1, 'flip:$p'), when=('coeff', 'c negative'),
            preds=_COEFF_BACK),
        Row('coeff.algebraic', [('N', 'algebraic')], (1, 'algebraic'),
            when=('coeff', 'c rational')),
        # (p/2)*x for integer x is an integer iff x is even.
        Row('coeff.half', [(1, 'integer')], [('N', 'integer'), (1, 'even')], kind='equiv',
            when=('coeff', 'c rational', 'c.q==2')),
        Row('coeff.minus_one', [('N', '$p')], (1, '$p'), when=('coeff', 'c rational', 'c==-1'),
            preds=('integer', 'odd')),
    )


def _mul_rules(n, consts):
    """The specs of ``MUL_TABLE`` for a Mul of ``n`` arguments."""
    return rules_of(_table('MUL_TABLE'), MUL_GUARDS, {'n': n, 'consts': consts},
                    {'N': n, '*': range(n)})


@registry.register(Mul)
def mul_templates(expr):
    if not expr.args:
        return ()
    out = [_product_block(f, expr) for f in _mul_factor_sets(expr)]
    return out if len(out) > 1 else out[0]


def _mul_factor_sets(expr):
    """The factor tuples whose Mul blocks ``mul_templates`` emits for
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
    if n >= 3 and c.is_Rational and not c.is_zero:
        # c*t: the coefficient-free t of the half-integer split of an Add
        # (x + I*pi*(4*n + 1)/2 derives I*pi*(4*n + 1))
        rest = Mul(*args[1:])
        if rest.is_Mul and len(rest.args) == n - 1:
            out.append((c, rest))
    split = ipi_split(expr)
    if split is not None and split[1] is not None and split[1].is_Mul:
        # I*pi*c*s: the s of exp(I*pi*c*s) and E**(I*pi*c*s)
        c, s_ = split
        out.append(((c,) if c is not S.One else ()) + (S.ImaginaryUnit, S.Pi, s_))
    return out


def _product_block(factors, expr):
    """The Mul block of ``expr == Mul(*factors)`` over these objects."""
    n = len(factors)
    consts = consts_of(factors)
    return facts(pattern_key('mul', n, consts), lambda: _mul_rules(n, consts),
                 consts, tuple(factors) + (expr,), n)


# ---------------------------------------------------------------------------
# Pow
# ---------------------------------------------------------------------------

# Indices: base 0, exponent 1, node 2.  Rules are ((premises), conclusion)
# with literals (index, pred) or (index, pred, False).
_B, _E, _N = 0, 1, 2
_POW_RULES = (
    # --- sign ---
    (((_B, 'positive'), (_E, 'real')), (_N, 'positive')),
    # A finite exponent: 1**oo and 1**-oo are nan.
    (((_B, 'extended_positive'), (_E, 'real')), (_N, 'extended_nonnegative')),
    (((_B, 'extended_nonnegative'), (_E, 'nonnegative')), (_N, 'extended_nonnegative')),
    (((_B, 'extended_nonnegative'), (_E, 'extended_real')), (_N, 'extended_negative', False)),
    (((_B, 'extended_real'), (_E, 'even')), (_N, 'extended_negative', False)),
    (((_B, 'nonzero'), (_E, 'even')), (_N, 'positive')),
    # (-oo)**(-2) == 0, so the extended version needs a nonnegative exponent.
    (((_B, 'negative'), (_E, 'odd')), (_N, 'negative')),
    (((_B, 'extended_nonpositive'), (_E, 'odd')), (_N, 'extended_positive', False)),
    (((_N, 'positive'), (_B, 'real'), (_E, 'odd')), (_B, 'positive')),
    # --- zero base, zero exponent (b**0 == 1, also for zoo and nan) ---
    (((_B, 'zero'), (_E, 'extended_positive')), (_N, 'zero')),
    (((_B, 'zero'), (_E, 'extended_negative')), (_N, 'infinite')),
    (((_E, 'zero'),), (_N, 'positive')),
    # SymPy leaves ``oo**0.0`` unevaluated and calls it non-integer.
    (((_E, 'zero'), (_B, 'finite')), (_N, 'odd')),
    # --- zero / nonzero / finite / infinite ---
    # (A commutative base: ``A**2 == 0`` for a nilpotent ``A``.)
    (((_B, 'zero', False), (_B, 'commutative'), (_B, 'finite'), (_E, 'finite')),
     (_N, 'zero', False)),
    (((_B, 'infinite'), (_E, 'negative')), (_N, 'zero')),
    (((_B, 'zero', False), (_B, 'commutative'), (_E, 'nonnegative')), (_N, 'zero', False)),
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
    (((_B, 'rational'), (_E, 'integer'), (_B, 'zero', False)), (_N, 'rational')),
    # --- extended real / imaginary ---
    (((_B, 'extended_nonzero'), (_E, 'integer')), (_N, 'extended_real')),
    (((_B, 'extended_real'), (_E, 'integer'), (_E, 'nonnegative')), (_N, 'extended_real')),
    (((_B, 'negative'), (_E, 'real'), (_E, 'integer', False)), (_N, 'extended_real', False)),
    (((_B, 'extended_real'), (_E, 'extended_real'), (_E, 'rational', False)),
     (_N, 'imaginary', False)),
    (((_B, 'imaginary'), (_E, 'even')), (_N, 'nonzero')),
    (((_B, 'imaginary'), (_E, 'odd')), (_N, 'imaginary')),
    # --- complex ---
    (((_B, 'complex'), (_E, 'complex'), (_B, 'zero', False)), (_N, 'complex')),
    # --- prime ---
    (((_B, 'integer'), (_E, 'prime')), (_N, 'prime', False)),
    (((_B, 'integer'), (_E, 'even'), (_E, 'positive')), (_N, 'prime', False)),
    # --- algebraic ---
    (((_B, 'algebraic'), (_E, 'rational'), (_B, 'zero', False)), (_N, 'algebraic')),
    (((_B, 'transcendental'), (_E, 'rational'), (_E, 'zero', False)), (_N, 'algebraic', False)),
    # --- polar / commutative ---
    (((_B, 'polar'),), (_N, 'polar')),
    # Not ``commutative(b**e) -> commutative(b)`` (``A**2`` is 1 for a
    # reflection ``A``, ``A**0 == 1``) or ``-> commutative(e)``
    # (``1**A == 1``); see #47 and the rule for ``1/b`` in ``_pow_rules``.
    (((_B, 'commutative'), (_E, 'commutative')), (_N, 'commutative')),
)

_POW_E_RULES = (
    (((_E, 'extended_real'),), (_N, 'extended_real')),
    (((_E, 'extended_real'),), (_N, 'extended_nonnegative')),
    (((_E, 'real'),), (_N, 'positive')),
    (((_E, 'complex'),), (_N, 'complex')),
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


#: Conditions on ``exp(I*pi*c*s)`` (``c`` rational; ``has_s``: an ``s`` slot).
IPI_GUARDS = MappingProxyType({
    'no s': lambda x: not x['has_s'],
    's': lambda x: x['has_s'],
    'c integer': lambda x: bool(x['c'].is_integer),
    'c even integer': lambda x: bool(x['c'].is_integer) and x['c'].p % 2 == 0,
    'c odd integer': lambda x: bool(x['c'].is_integer) and x['c'].p % 2 != 0,
    'c half-odd': lambda x: not x['c'].is_integer and x['c'].q == 2,
    'c other': lambda x: not x['c'].is_integer and x['c'].q != 2,
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

def _num(x):
    return x['b'] is not None and x['b'].is_Number and x['b'].is_finite


def _e_ratio(x):
    e = x['e']
    return e is not None and e.is_Rational and not e.is_Integer


def _b_not_qth_power(x):
    """b**(p/q) with gcd(p, q) == 1 is rational iff b is a perfect q-th
    power (exact integer arithmetic): here b is a positive rational that
    is not one."""
    b, e = x['b'], x['e']
    if not (b is not None and b.is_Rational and b.is_positive):
        return False
    return not (integer_nthroot(b.p, e.q)[1] and integer_nthroot(b.q, e.q)[1])


#: Conditions on the pattern of a Pow (``b``/``e`` the constant base or
#: exponent or None, and the flags of ``pow_templates``).
POW_GUARDS = MappingProxyType({
    'b is E': lambda x: x['b'] is S.Exp1,
    'ipi': lambda x: x['ipi'] is not None,
    'b is e': lambda x: x['same'],
    'e is 1': lambda x: x['e'] is S.One,
    'b unit angle': lambda x: x['angle'] is not None,
    'u slot': lambda x: x['has_u'],
    'b-1, b+1 slots': lambda x: x['has_b1'],
    '2*e slot': lambda x: x['has_t'],
    'e rational non-integer': _e_ratio,
    'e.q==2': lambda x: x['e'].q == 2,
    'e.q!=2': lambda x: x['e'].q != 2,
    'e.p==1': lambda x: x['e'].p == 1,
    'e.p==-1': lambda x: x['e'].p == -1,
    'b positive rational, not a q-th power': _b_not_qth_power,
    'e is -1': lambda x: x['e'] is S.NegativeOne,
    'b is -1': lambda x: x['b'] is S.NegativeOne,
    'b integer, |b|>=2': lambda x: (x['b'] is not None and x['b'] is not S.NegativeOne
                                    and x['b'].is_Integer and (x['b'].p >= 2 or x['b'].p <= -2)),
    'b algebraic, not 0 or 1': lambda x: (x['b'] is not None and x['b'].is_algebraic
                                          and x['b'].is_zero is False and x['b'] is not S.One),
    'b finite number, |b|>1': lambda x: _num(x) and abs(x['b']) > 1,
    'b finite number, 0<|b|<1': lambda x: (_num(x) and not abs(x['b']) > 1
                                           and x['b'].is_zero is False and abs(x['b']) < 1),
    'e integer >= 2': lambda x: x['e'] is not None and x['e'].is_Integer and x['e'].p >= 2,
    'e algebraic irrational': lambda x: (x['e'] is not None and x['e'].is_algebraic
                                         and x['e'].is_rational is False),
})

_POW_SLOT_NAMES = MappingProxyType({_B: 'B', _E: 'E', _N: 'N'})


def _pairs_rows(prefix, pairs, when=()):
    """Rows from the ``((premises), conclusion)`` tuples of ``_POW_RULES``."""
    def name(l):
        return (_POW_SLOT_NAMES[l[0]], *l[1:])
    return tuple(Row(f'{prefix}.{i}', [name(p) for p in prem], name(concl), when=when)
                 for i, (prem, concl) in enumerate(pairs))


#: Slot names of a Pow block (see ``pow_templates``).
POW_SLOTS = MappingProxyType({'B': _B, 'E': _E, 'N': _N, 'U': _U, 'S': _S, 'T': _T,
                              'BM': _BM, 'BP': _BP})

# Slots: 'B' base, 'E' exponent, 'N' node, 'U' the u of an exp(u) base,
# 'S' the s of an I*pi*c*s exponent of E, 'T' 2*e, 'BM'/'BP' b - 1, b + 1.
def _pow_table_rows():
    """The rows of ``POW_TABLE`` (built on first use, :func:`_table`)."""
    return (
        *_pairs_rows('pow', _POW_RULES),
        *_pairs_rows('pow.E', _POW_E_RULES, when='b is E'),
        Sub('ipi', _table('IPI_TABLE'), IPI_GUARDS,
            lambda x: {'c': x['ipi'][0], 'has_s': x['ipi'][1]},
            lambda x, s: {'S': _S if x['ipi'][1] else None, 'N': _N}, when=('b is E', 'ipi')),
        Row('same', [('B', 'extended_nonnegative')], ('N', 'extended_positive'), when='b is e'),
        Row('one', [], [('N', '$p'), ('B', '$p')], kind='equiv', preds=_POW_ONE_EQUIV,
            when='e is 1'),
        # A power of a composite is 1, a fraction or composite.
        Row('composite_base', [('B', 'composite'), ('E', 'integer')], ('N', 'prime', False)),
        # For algebraic b = r*exp(I*phi) != 0 and algebraic e = I*t, b**e is
        # exp(-t*phi)*exp(I*t*log(r)) with r algebraic; t*log(r) in pi*Q with
        # t algebraic nonzero forces log(r)/(I*pi) algebraic, hence rational
        # (Gelfond-Schneider), hence r == 1.  So b**e is never imaginary, and
        # it is real iff |b| == 1 (then it is positive).
        Row('gs.imaginary_exp', [('B', 'algebraic'), ('B', 'zero', False), ('E', 'imaginary'),
                                 ('E', 'algebraic')], ('N', 'imaginary', False)),
        Row('gs.imaginary_exp.not_unit', [('B', '$p'), ('B', 'algebraic'), ('E', 'imaginary'),
                                          ('E', 'algebraic')], ('N', 'extended_real', False),
            preds=_NOTUNIT),
        Row('unit_base.imaginary_exp', [('E', 'imaginary')], ('N', 'positive'),
            when='b unit angle'),
        # (exp(u))**e == exp(e*(u - 2*pi*I*k)) is positive for imaginary u, e.
        Row('exp_base.imaginary', [('U', 'imaginary'), ('E', 'imaginary')], ('N', 'positive'),
            when='u slot'),
        # An integer other than 0 and +-1 to a negative integer power is a
        # fraction (0 gives zoo).
        Row('int_base.negative_int_exp', [('B', 'integer'), ('E', 'integer'), ('E', 'negative'),
                                          ('BM', 'zero', False), ('BP', 'zero', False)],
            ('N', 'integer', False), when='b-1, b+1 slots'),
        # Real base, rational exponent: imaginary iff the base is negative
        # and the exponent is half an odd integer.
        Row('rational_exp.not_half',
            [('B', 'extended_real'), ('E', 'rational'), ('T', 'integer', False)],
            ('N', 'imaginary', False), when='2*e slot'),
        Row('rational_exp.half_odd', [('B', 'negative'), ('E', 'rational'), ('T', 'integer'),
                                      ('E', 'integer',
                                       False)], ('N', 'imaginary'), when='2*e slot'),
        # b**(k/2) for a negative real b is imaginary (the converse follows
        # from the other rows and the rule base).
        Row('e=k/2.imaginary', [('B', 'extended_real'), ('B', 'negative')], ('N', 'imaginary'),
            when=('e rational non-integer', 'e.q==2')),
        Row('e=k/2.not_negative', [('B', 'extended_real')], ('N', 'extended_negative', False),
            when=('e rational non-integer', 'e.q==2')),
        Row('e=p/q.not_imaginary', [('B', 'extended_real')], ('N', 'imaginary', False),
            when=('e rational non-integer', 'e.q!=2')),
        # (b**(1/q))**q == b: a non-real base gives a non-real root.
        Row('e=1/q.non_real', [('B', 'extended_real', False)], ('N', 'extended_real', False),
            when=('e rational non-integer', 'e.p==1')),
        # Likewise for 1/b**(1/q), but zoo**(-1/2) == 0 is real.
        Row('e=-1/q.non_real', [('B', 'extended_real', False), ('B', 'finite')],
            ('N', 'extended_real', False), when=('e rational non-integer', 'e.p==-1')),
        Row('e=p/q.irrational', [], ('N', 'irrational'),
            when=('e rational non-integer', 'b positive rational, not a q-th power')),
        # 1/b is rational iff b is (nonzero) rational.
        Row('e=-1.irrational', [('B', 'irrational')], ('N', 'irrational'), when='e is -1'),
        # b is the inverse of a nonzero number 1/b.
        Row('e=-1.commutative', [('N', 'complex'), ('N', 'zero', False)], ('B', 'commutative'),
            when='e is -1'),
        Row('b=-1.odd', [('E', 'integer')], ('N', 'odd'), when='b is -1'),
        # |b|**e < 1 for negative e.
        Row('b=int.negative_exp', [('E', 'negative')], ('N', 'integer', False),
            when='b integer, |b|>=2'),
        Row('b=algebraic.gs', [('E', 'algebraic')], [('N', 'algebraic'), ('E', 'rational')],
            kind='equiv', when='b algebraic, not 0 or 1'),
        # Exact comparisons of a number with 1 (no assumptions involved).
        Row('|b|>1.zero', [('E', 'negative_infinite')], ('N', 'zero'),
            when='b finite number, |b|>1'),
        Row('|b|>1.infinite', [('E', 'positive_infinite')], ('N', 'infinite'),
            when='b finite number, |b|>1'),
        Row('|b|<1.zero', [('E', 'positive_infinite')], ('N', 'zero'),
            when='b finite number, 0<|b|<1'),
        # Disagrees with SymPy for negative b ((-1/2)**(-oo) == nan); kept as is pending
        # an owner decision, see tests/test_p6_review.py (issue #97 P6 review).
        Row('|b|<1.infinite', [('E', 'negative_infinite')], ('N', 'infinite'),
            when='b finite number, 0<|b|<1'),
        # b**e for integer b >= 2 is composite.
        Row('e>=2.composite', [('B', 'int>=2')], ('N', 'composite'), when='e integer >= 2'),
        # Gelfond-Schneider: b not in {0, 1} algebraic, e algebraic irrational.
        Row('e=algebraic_irrational.gs', [('B', '$p'), ('B', 'algebraic')],
            ('N', 'algebraic', False),
            preds=_NOT01, when='e algebraic irrational'),
    )


def _pow_rules(b, e, same, angle, has_u, ipi, has_t, has_b1):
    """The specs of ``POW_TABLE``.  ``b``/``e`` are the constant
    base/exponent or ``None`` if symbolic; ``angle`` is
    ``_unit_angle(base)``; ``has_u``: slot ``_U`` holds the argument of an
    ``exp`` base; ``ipi``: ``(c, has_s)`` for base ``E`` and exponent
    ``I*pi*c*s``; ``has_t``: slot ``_T`` holds ``2*e``; ``has_b1``: slots
    ``_BM``/``_BP`` hold ``b - 1`` and ``b + 1``."""
    return rules_of(_table('POW_TABLE'), POW_GUARDS,
                    _pow_ctx(b, e, same, angle, has_u, ipi, has_t, has_b1),
                    POW_SLOTS)

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
    consts, objs, key, pargs = _pow_pattern(expr)
    out = facts(key, lambda: _pow_rules(*pargs), consts, tuple(objs), _N)
    angle, e = pargs[3], expr.args[1]
    if angle is not None and e.is_number:
        return [out, *_unit_power_units(angle, e, expr)]
    return out


def _pow_pattern(expr):
    """``(consts, objs, key, pargs)`` of the Pow block of ``expr``:
    ``pargs`` are the arguments of ``_pow_rules``."""
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
    pargs = (consts.get(_B), consts.get(_E), same, angle, u is not None, ipi, has_t, has_b1)
    return consts, objs, key, pargs


def _pow_ctx(b, e, same, angle, has_u, ipi, has_t, has_b1):
    return {'b': b, 'e': e, 'same': same, 'angle': angle, 'has_u': has_u, 'ipi': ipi,
            'has_t': has_t, 'has_b1': has_b1}


def table_provenance(expr):
    """For a Mul or Pow node: ``(row name, clause)`` for every rule of the
    node's table blocks, resolved against the constants like the compiled
    block, with ``clause`` a frozenset of ``(object, pred, positive)``
    literals (``tools/totality.py`` names the rows of a fired clause with
    it).  Empty for other nodes."""
    if isinstance(expr, Mul) and expr.args:
        blocks = []
        for f in _mul_factor_sets(expr):
            n = len(f)
            blocks.append((consts_of(f), tuple(f) + (expr,),
                           expand(_table('MUL_TABLE'), MUL_GUARDS, {'n': n, 'consts': consts_of(f)},
                                  {'N': n, '*': range(n)})))
    elif isinstance(expr, Pow):
        consts, objs, _, pargs = _pow_pattern(expr)
        blocks = [(consts, tuple(objs),
                   expand(_table('POW_TABLE'), POW_GUARDS, _pow_ctx(*pargs), POW_SLOTS))]
    else:
        return []
    out = []
    for consts, objs, specs in blocks:
        for row, prem, concl in specs:
            try:
                resolved = resolve([(prem, concl)], consts)
            except ValueError:
                continue
            for ps, cs in resolved:
                # over the basis, as the compiled block (rules.expand_clause)
                lits = [(k, p, not pos) for k, p, pos in ps] + [(k, p, pos) for k, p, pos in cs]
                for c in expand_clause(lits):
                    out.append((row.name, frozenset((objs[k], BASIS[i], pos) for k, i, pos in c)))
    return out


# ---------------------------------------------------------------------------
# The tables, built on first use
# ---------------------------------------------------------------------------

#: builders of the rule tables, by module attribute name.  A table is a
#: constant (a tuple of rows), built the first time it is read: through
#: :func:`_table` here, as ``core.MUL_TABLE`` (the module ``__getattr__``)
#: elsewhere.  A query without a product or a power then never builds the
#: Mul or Pow table (most of this module's import time and allocations).
_TABLE_BUILDERS = MappingProxyType({
    'MUL_TABLE': _mul_table_rows,
    'POW_TABLE': _pow_table_rows,
    'IPI_TABLE': _ipi_table_rows,
})


def _table(name: str) -> tuple:
    """The rule table ``name`` (``MUL_TABLE``, ``POW_TABLE``, ``IPI_TABLE``),
    built once and then a module attribute."""
    t = globals().get(name)
    if t is None:
        t = globals()[name] = _TABLE_BUILDERS[name]()
    return t


def __getattr__(name: str):
    if name in _TABLE_BUILDERS:
        return _table(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
