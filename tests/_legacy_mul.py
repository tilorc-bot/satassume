"""Verbatim copy of the ``Mul`` templates of
``satassume/knowledge/templates/core.py`` at e068e49, before ``Mul``
became rows (``templates/mul.py``, #299, U2): ``MUL_TABLE`` (with
``MUL_GUARDS``, ``_coeff``, ``_MUL_CLOSED``, ``_COEFF_BACK`` and the arity
limits), ``_mul_rules``, ``mul_templates``, ``_mul_factor_sets``, the
quotient ``a/v**k``, ``_product_block`` and ``_wide_one``.  Test-only:
``tests/test_mul_rows.py`` checks with the SAT solver that the rows entail
exactly what these templates emit.  Do not edit it to follow a later rule
change (``git show e068e49:satassume/knowledge/templates/core.py``).

Copied unchanged, except that the imports are absolute, ``mul_templates``
is not registered (no ``@registry.register``), and ``_table`` builds only
``MUL_TABLE``.  ``ipi_split`` (the ``I*pi*c*s`` factor set) is imported
from ``core``, where it stays for ``Pow`` and ``exp``.
"""
from __future__ import annotations

from types import MappingProxyType

from sympy import S

from satassume.knowledge.domain import kept_product
from satassume.knowledge.templates._common import (
    Rules,
    const_key,
    consts_of,
    facts,
    pattern_key,
)
from satassume.knowledge.templates.core import ipi_split
from satassume.knowledge.templates.table import Row, Section, rules_of
from satassume.sat.formula import And, Implies, Or, P

#: Largest arity for per-argument rules of Mul (O(n^2) literals).
MAX_ONEOUT = 6
#: Largest arity for the per-term rules of Add and Mul that every arity
#: gets (one rule of n literals per term: O(n^2) literals).  Past it the
#: strict-sign rule of Add is one formula (linear
#: with Tseitin variables, :func:`_wide_one`), and so is the zero rule of
#: Mul; the others are not emitted (#180 C-WIDEADD).
MAX_ONEOUT_WIDE = 32
#: Largest arity for rules enumerating pairs of arguments.
MAX_PAIRS = 4


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


# Closed under multiplication.  ``real`` and ``positive`` are derived by the
# rule base (``extended_* & finite``).  ``extended_real`` is not: ``0*oo``
# is nan (see _mul_rules).
_MUL_CLOSED = (
    'complex', 'integer', 'rational', 'algebraic', 'finite',
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


def _coeff(ctx):
    """``c*x`` with ``c`` a finite nonzero real number (slot 0) and n == 2."""
    consts = ctx['consts']
    if not (ctx['n'] == 2 and 0 in consts and consts[0].is_Number):
        return False
    c = consts[0]
    return bool(c.is_finite and c.is_extended_real and not c.is_zero)  # sympy-boundary: c a Number


#: Conditions on the pattern of a Mul (``n`` arguments, ``consts``; ``m``
#: the size of the negative set in a ``negsets`` section).
MUL_GUARDS = MappingProxyType({
    'n<=MAX_ONEOUT': lambda c: c['n'] <= MAX_ONEOUT,
    'n>MAX_ONEOUT': lambda c: c['n'] > MAX_ONEOUT,
    'n<=MAX_ONEOUT_WIDE': lambda c: c['n'] <= MAX_ONEOUT_WIDE,
    'n>=2': lambda c: c['n'] >= 2,
    'n==2': lambda c: c['n'] == 2,
    'n even': lambda c: c['n'] % 2 == 0,
    'n odd': lambda c: c['n'] % 2 != 0,
    '3<=n<=MAX_PAIRS': lambda c: 3 <= c['n'] <= MAX_PAIRS,
    'm even': lambda c: c['m'] % 2 == 0,
    'm odd': lambda c: c['m'] % 2 != 0,
    'coeff': _coeff,
    'c negative': lambda c: bool(c['consts'][0].is_negative),  # sympy-boundary: c a constant
    'c not negative': lambda c: not c['consts'][0].is_negative,  # sympy-boundary: c a constant
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
        Section('each', when='n<=MAX_ONEOUT_WIDE', rows=[
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
        Section('each', when='n<=MAX_ONEOUT_WIDE', rows=[
            Row('polar.one', [('k', 'polar'), ('rest', 'positive')], ('N', 'polar')),
        ]),
        Row('primes', [('*', 'prime')], ('N', 'composite'), when='n>=2'),
        # A product of two integers >= 2 is composite.
        Row('ge2s', [('*', 'int>=2')], ('N', 'composite'), when='n==2'),
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
            # Likewise one non-algebraic factor (possibly infinite or not a
            # complex number): else k = N/(product of the rest) would be
            # algebraic (#180 S7).
            Row('one_non_algebraic',
                [('k', 'algebraic', False), ('rest', 'algebraic'), ('rest', 'zero', False)],
                ('N', 'algebraic', False)),
            # One non-real factor and the rest nonzero extended reals -> not real.
            Row('one_non_real', [('k', 'extended_real', False), ('rest', 'extended_nonzero')],
                ('N', 'extended_real', False)),
            # One imaginary factor and the rest nonzero finite reals -> imaginary;
            # with the rest merely real the product may also be zero.
            Row('one_imag', [('k', 'imaginary'), ('rest', 'real'), ('rest', 'zero', False)],
                ('N', 'imaginary')),
            Row('one_imag.or_zero', [('k', 'imaginary'), ('rest', 'real')],
                [('N', 'imaginary'), ('N', 'zero')]),
            # and back: k is the product over the nonzero reals
            Row('one_imag.back', [('rest', 'real'), ('rest', 'zero', False), ('N', 'imaginary')],
                ('k', 'imaginary')),
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
            # imag_times with the rest nonzero reals (r*i is imaginary)
            Row('imag_times_rest.real', [('k', 'imaginary'), ('l', 'complex'), ('rest', 'real'),
                                         ('rest', 'zero', False), ('N', 'extended_real')],
                [('l', 'imaginary'), ('l', 'zero')]),
            Row('imag_times_rest.real.flip', [('l', 'imaginary'), ('k', 'complex'),
                                              ('rest', 'real'), ('rest', 'zero', False),
                                              ('N', 'extended_real')],
                [('k', 'imaginary'), ('k', 'zero')]),
            Row('imag_times_rest.imag', [('k', 'imaginary'), ('l', 'complex'), ('rest', 'real'),
                                         ('rest', 'zero', False), ('N', 'imaginary')],
                ('l', 'real')),
            Row('imag_times_rest.imag.flip', [('l', 'imaginary'), ('k', 'complex'),
                                              ('rest', 'real'), ('rest', 'zero', False),
                                              ('N', 'imaginary')],
                ('k', 'real')),
        ]),
        # Numeric coefficient c*x: transfer facts back from the product to x.
        Row('coeff.back', [('N', '$p')], (1, '$p'), when=('coeff', 'c not negative'),
            preds=_COEFF_BACK),
        Row('coeff.back.flip', [('N', '$p')], (1, 'flip:$p'), when=('coeff', 'c negative'),
            preds=_COEFF_BACK),
        Row('coeff.rational', [('N', 'rational')], (1, 'rational'), when=('coeff', 'c rational')),
        Row('coeff.algebraic', [('N', 'algebraic')], (1, 'algebraic'),
            when=('coeff', 'c rational')),
        # (p/2)*x for integer x is an integer iff x is even.
        Row('coeff.half', [(1, 'integer')], [('N', 'integer'), (1, 'even')], kind='equiv',
            when=('coeff', 'c rational', 'c.q==2')),
        Row('coeff.minus_one', [('N', '$p')], (1, '$p'), when=('coeff', 'c rational', 'c==-1'),
            preds=('integer', 'even', 'odd')),
    )


def _mul_rules(n, consts):
    """The specs of ``MUL_TABLE`` for a Mul of ``n`` arguments."""
    return rules_of(_table('MUL_TABLE'), MUL_GUARDS, {'n': n, 'consts': consts},
                    {'N': n, '*': range(n)})


def mul_templates(expr):
    if not expr.args:
        return ()
    out = [_product_block(f, expr) for f in _mul_factor_sets(expr)]
    args = expr.args
    quot = _quotient_templates(expr)
    if quot is not None:
        out.append(quot)
    if len(args) > MAX_ONEOUT_WIDE:
        # the zero rule of MUL_TABLE
        f = _wide_one(expr, args, consts_of(args), 'finite', 'zero', 'zero')
        if f is not None:
            out.append(f)
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


def _product_block(factors, expr):
    """The Mul block of ``expr == Mul(*factors)`` over these objects."""
    n = len(factors)
    consts = consts_of(factors)
    return facts(pattern_key('mul', n, consts), lambda: _mul_rules(n, consts),
                 consts, tuple(factors) + (expr,), n)


def _table(name: str) -> tuple:
    """The rule table ``name`` (``MUL_TABLE``), built once."""
    t = globals().get(name)
    if t is None:
        t = globals()[name] = _mul_table_rows()
    return t
