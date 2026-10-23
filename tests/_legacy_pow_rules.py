"""Verbatim copy of the Pow generator of ``satassume/knowledge/templates/core.py``
at 8ddd549 (``POW_TABLE``, ``POW_GUARDS``, ``_pow_pattern``,
``pow_templates`` and what they need), before Pow became rows
(``templates/power.py``, #294).  Test-only: ``tests/test_power_rows.py``
checks with the SAT solver that the rows entail exactly what this
generator emits.  Do not edit it to follow a later rule change
(``git show 8ddd549:satassume/knowledge/templates/core.py``).

What production still uses is imported from ``core`` (``_unit_angle``, the
``IPI_TABLE`` and ``ipi_split``, ``_unit_power_units``, ``_exp_arg``,
``_pow_bound_templates``); the rest is copied unchanged, except that
``pow_templates`` is not registered and ``_table`` builds ``POW_TABLE``
here and reads ``IPI_TABLE`` from ``core``.
"""
from types import MappingProxyType

from sympy import S
from sympy.core.intfunc import integer_nthroot
from sympy.core.mul import Mul

from satassume.knowledge.templates import core
from satassume.knowledge.templates._common import VOCAB, const_key, facts
from satassume.knowledge.templates.core import (
    IPI_GUARDS,
    _exp_arg,
    _pow_bound_templates,
    _unit_angle,
    _unit_power_units,
    ipi_split,
)
from satassume.knowledge.templates.table import Row, Sub, rules_of

_TABLES = {}


def _table(name):
    """``POW_TABLE`` (built once, here), or ``core``'s ``IPI_TABLE``."""
    if name != 'POW_TABLE':
        return core._table(name)
    t = _TABLES.get(name)
    if t is None:
        t = _TABLES[name] = _pow_table_rows()
    return t


# Indices: base 0, exponent 1, node 2.  Rules are ((premises), conclusion)
# with literals (index, pred) or (index, pred, False).
_B, _E, _N = 0, 1, 2
_POW_RULES = (
    # --- sign ---
    (((_B, 'positive'), (_E, 'real')), (_N, 'positive')),
    (((_B, 'extended_positive'), (_E, 'positive')), (_N, 'extended_positive')),
    # A finite exponent: 1**oo and 1**-oo are nan.
    (((_B, 'extended_positive'), (_E, 'real')), (_N, 'extended_nonnegative')),
    (((_B, 'extended_nonnegative'), (_E, 'nonnegative')), (_N, 'extended_nonnegative')),
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


def _num(x):
    # sympy-boundary: b a Number
    return x['b'] is not None and x['b'].is_Number and x['b'].is_finite


def _e_ratio(x):
    e = x['e']
    return e is not None and e.is_Rational and not e.is_Integer


def _b_not_qth_power(x):
    """b**(p/q) with gcd(p, q) == 1 is rational iff b is a perfect q-th
    power (exact integer arithmetic): here b is a positive rational that
    is not one."""
    b, e = x['b'], x['e']
    if not (b is not None and b.is_Rational and b.is_positive):  # sympy-boundary: b Rational
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
    'b is 1': lambda x: x['b'] is S.One,
    'b integer, |b|>=2': lambda x: (x['b'] is not None and x['b'] is not S.NegativeOne
                                    and x['b'].is_Integer and (x['b'].p >= 2 or x['b'].p <= -2)),
    # sympy-boundary: b a numeric constant
    'b algebraic, not 0 or 1': lambda x: (x['b'] is not None and x['b'].is_algebraic
                                          and x['b'].is_zero is False and x['b'] is not S.One),
    'b finite number, |b|>1': lambda x: _num(x) and abs(x['b']) > 1,
    # sympy-boundary: b a numeric constant
    'b finite number, 0<|b|<1': lambda x: (_num(x) and not abs(x['b']) > 1
                                           and x['b'].is_zero is False and abs(x['b']) < 1),
    'e integer >= 2': lambda x: x['e'] is not None and x['e'].is_Integer and x['e'].p >= 2,
    'e integer, 2 mod 4': lambda x: x['e'] is not None and x['e'].is_Integer and x['e'].p % 4 == 2,
    'e integer, 0 mod 4': lambda x: x['e'] is not None and x['e'].is_Integer and x['e'].p % 4 == 0,
    # sympy-boundary: e a numeric constant
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
        # So an integer power of an integer to a negative integer power
        # has the base +-1, and is +-1 (0**-k is zoo).
        Row('int_base.negative_int_exp.unit', [('B', 'integer'), ('E', 'integer'),
                                               ('E', 'negative'), ('N', 'integer')],
            ('N', 'odd')),
        Row('int_base.negative_int_exp.unit_not', [('B', 'integer'), ('E', 'integer'),
                                                   ('E', 'negative'), ('N', 'integer')],
            ('N', '$p', False), preds=('prime', 'composite')),
        Row('int_base.negative_int_exp.unit_base', [('B', 'integer'), ('E', 'integer'),
                                                    ('E', 'negative'), ('N', 'integer')],
            ('B', 'odd')),
        Row('int_base.negative_int_exp.not_unit', [('B', '$p'), ('E', 'integer'),
                                                   ('E', 'negative')],
            ('N', 'integer', False), preds=('prime', 'composite')),
        # Real base, rational exponent: imaginary iff the base is negative
        # and the exponent is half an odd integer.
        Row('rational_exp.not_half',
            [('B', 'extended_real'), ('E', 'rational'), ('T', 'integer', False)],
            ('N', 'imaginary', False), when='2*e slot'),
        Row('rational_exp.half_odd', [('B', 'negative'), ('E', 'rational'), ('T', 'integer'),
                                      ('E', 'integer',
                                       False)], ('N', 'imaginary'), when='2*e slot'),
        # b**(k/2) for real b is imaginary iff b is a negative real.
        Row('e=k/2.imaginary', [('B', 'extended_real')], [('N', 'imaginary'), ('B', 'negative')],
            kind='equiv', when=('e rational non-integer', 'e.q==2')),
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
        # 1**e == exp(e*log(1)) == 1 for complex e (1**oo is nan).
        Row('b=1', [('E', 'complex')], ('N', '$p'), preds=('positive', 'odd'), when='b is 1'),
        Row('b=1.unit', [('E', 'complex')], ('N', '$p', False), preds=('prime', 'composite'),
            when='b is 1'),
        # 1/b is imaginary iff b is (1/0 == zoo, 1/oo == 0).
        Row('e=-1.imaginary', [('N', 'imaginary')], ('B', 'imaginary'), when='e is -1'),
        # (I*t)**e == I**e * t**e for real t != 0: I**e is -1 or 1.
        Row('imaginary_base.e=2mod4', [('B', 'imaginary')], ('N', 'negative'),
            when='e integer, 2 mod 4'),
        Row('imaginary_base.e=0mod4', [('B', 'imaginary')], ('N', 'positive'),
            when='e integer, 0 mod 4'),
        # |b|**e < 1 for negative e.
        Row('b=int.negative_exp', [('E', 'negative')], ('N', 'integer', False),
            when='b integer, |b|>=2'),
        Row('b=algebraic.gs', [('E', 'algebraic')], [('N', 'algebraic'), ('E', 'rational')],
            kind='equiv', when='b algebraic, not 0 or 1'),
        # Exact comparisons of a number with 1 (no assumptions involved).
        Row('|b|>1.finite', [('E', 'extended_negative')], ('N', 'finite'),
            when='b finite number, |b|>1'),
        Row('|b|>1.zero', [('E', 'negative_infinite')], ('N', 'zero'),
            when='b finite number, |b|>1'),
        Row('|b|>1.infinite', [('E', 'positive_infinite')], ('N', 'infinite'),
            when='b finite number, |b|>1'),
        Row('|b|<1.finite', [('E', 'extended_positive')], ('N', 'finite'),
            when='b finite number, 0<|b|<1'),
        Row('|b|<1.zero', [('E', 'positive_infinite')], ('N', 'zero'),
            when='b finite number, 0<|b|<1'),
        # Disagrees with SymPy for negative b ((-1/2)**(-oo) == nan); kept as is pending
        # an owner decision, see tests/test_p6_review.py (issue #97 P6 review).
        Row('|b|<1.infinite', [('E', 'negative_infinite')], ('N', 'infinite'),
            when='b finite number, 0<|b|<1'),
        # b**e for integer b >= 2 is composite.
        Row('e>=2.composite', [('B', 'int>=2')], ('N', 'composite'), when='e integer >= 2'),
        # b**e >= 2 for an integer b >= 2 and a positive integer e (composite
        # with e>=2.not_prime: 3 formulas, not 3**2 for both premises >= 2).
        Row('ge2s.composite', [('B', 'int>=2'), ('E', 'integer'), ('E', 'positive')],
            [('N', 'prime'), ('N', 'composite')]),
        # b**e for an integer b and an integer e >= 2 is 0, +-1, a negative
        # number or composite.
        Row('e>=2.not_prime', [('B', 'integer'), ('E', 'int>=2')], ('N', 'prime', False)),
        # b <= -2 (b + 1 negative) to an even power e >= 2 is composite.
        Row('b<=-2.even_e.composite', [('B', 'integer'), ('B', 'negative'), ('BP', 'negative'),
                                       ('E', 'even'), ('E', 'positive')], ('N', 'composite'),
            when='b-1, b+1 slots'),
        # Gelfond-Schneider: b not in {0, 1} algebraic, e algebraic irrational.
        Row('e=algebraic_irrational.gs', [('B', '$p'), ('B', 'algebraic')],
            ('N', 'algebraic', False),
            preds=_NOT01, when='e algebraic irrational'),
        # Likewise for symbolic b and e: b not in {0, 1} says b != 0, b - 1 != 0.
        Row('gs.symbolic', [('B', 'algebraic'), ('B', 'zero', False), ('BM', 'zero', False),
                            ('E', 'algebraic'), ('E', 'rational', False)],
            ('N', 'algebraic', False), when='b-1, b+1 slots'),
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


def pow_templates(expr):
    consts, objs, key, pargs = _pow_pattern(expr)
    out = facts(key, lambda: _pow_rules(*pargs), consts, tuple(objs), _N)
    angle, e = pargs[3], expr.args[1]
    if angle is not None and e.is_number:
        return [out, *_unit_power_units(angle, e, expr)]
    bound = _pow_bound_templates(expr)
    if bound is not None:
        return [out, bound]
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

