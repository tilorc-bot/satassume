"""The rules of ``Add``, ``Mul`` and ``Pow`` that are not rows (their rows
are ``templates/add.py``, ``templates/mul.py`` and ``templates/power.py``;
``wiring.addition``, ``wiring.product`` and ``wiring.power`` call the
functions of the Add, Mul and Pow sections here): the sums of a special
shape, the factor sets and ``a/v**k``, and ``exp(I*pi*c*s)``.

Every formula relates predicates of the node to predicates of its direct
arguments and is a theorem about the *value* of the node under SymPy's
conventions (``1/0 = zoo``, ``0**0 = 1``, ``oo - oo = nan`` is "unknown").
The rules mirror SymPy's ``_eval_is_*`` methods in
``sympy/core/{add,mul,power}.py`` except where those are unsound under
value semantics (noted inline).

Rules are index-based specs (see :mod:`._common`): the slots of a block
are its objects in order, the node's slot is passed to ``facts``.  The rule
base is relied on for everything it can derive (``positive ==
extended_positive & finite``, ``zero == extended_nonnegative &
extended_nonpositive``, ...).
"""
from __future__ import annotations

from types import MappingProxyType

from sympy import S
from sympy.core.add import Add
from sympy.core.intfunc import integer_nthroot
from sympy.functions.elementary.exponential import exp

from ...sat.formula import Not, P
from ..domain import kept_product

from ._common import (
    Rules,
    const_key,
    facts,
)
from .table import Row, expand

#: Largest number of terms with an ``x`` of a sum ``I*(c_1*x_1 + ...)``
#: whose rules are emitted (:func:`_imag_templates`; one rule of m
#: literals per term: O(m^2) literals).
MAX_ONEOUT = 6


# ---------------------------------------------------------------------------
# Add: the sums of a special shape, which are not rows of templates/add.py
# (wiring.addition calls them)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mul: the rules that are not rows of templates/mul.py (wiring.product calls
# them): the factor sets and a/v**k
# ---------------------------------------------------------------------------

def _mul_factor_sets(expr):
    """The factor tuples whose Mul blocks ``wiring.product`` emits for
    ``expr``: its arguments, then ``I*pi*c*s`` with ``s`` a product as a
    factor (the ``s`` of ``exp(I*pi*c*s)`` and ``E**(I*pi*c*s)``, which
    ``ipi_split`` derives: the Mul's own block knows its factors, not the
    product of a subset of them, so without this the deriving block
    relates a node to a term nothing constrains, a non-total block,
    ``tools/totality.py``).  The sign of ``c*m`` against ``m`` (``-x*y``
    and ``x*y``) is the relation glue's (``relations.PRODUCTS``, #315)."""
    out = [expr.args]
    split = ipi_split(expr)
    if split is not None and split[1] is not None and split[1].is_Mul:
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
