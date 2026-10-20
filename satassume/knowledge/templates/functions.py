"""Structural templates for elementary functions.

Only statements that are theorems about the function's *value* under
SymPy's conventions are emitted (``log(0) = zoo``, ``acot(0) = pi/2``,
``atan(oo) = pi/2``, ``factorial(-1) = zoo``, principal branches, ...).
Transcendence facts follow from the Lindemann-Weierstrass theorem.
Predicates the rule base derives from the emitted ones (``positive`` from
``extended_positive & finite``, ``irrational`` from ``real & !rational``,
...) are not repeated.

Rules are index-based specs (see :mod:`._common`): the argument is index
0 and the node index 1.  A row ``(x_premises, conclusion)`` uses ``pred`` or
``(pred, False)`` for a premise on the argument and likewise for a
conclusion on the node.
"""
from __future__ import annotations

from collections import Counter

from sympy import S
from sympy.core.add import Add
from sympy.core.mod import Mod
from sympy.functions.combinatorial.factorials import factorial
from sympy.functions.elementary.complexes import (
    Abs,
    conjugate,
    im,
    polar_lift,
    principal_branch,
    re,
    sign,
)
from sympy.functions.elementary.exponential import exp, exp_polar, log
from sympy.functions.elementary.hyperbolic import (
    acosh,
    acoth,
    acsch,
    asech,
    asinh,
    atanh,
    cosh,
    coth,
    csch,
    sech,
    sinh,
    tanh,
)
from sympy.functions.elementary.integers import RoundFunction, ceiling, floor
from sympy.functions.elementary.trigonometric import (
    acos,
    acot,
    acsc,
    asec,
    asin,
    atan,
    cos,
    cot,
    csc,
    sec,
    sin,
    tan,
)

from ...sat.formula import Not, P
from ._common import (
    Rules,
    const_key,
    facts,
    ge2_alternatives,
    pattern_key,
)
from .core import ipi_rules, ipi_split
from .registry import registry

X, N = 0, 1
#: Slot of ``arg - 1`` in the templates that use it (log, acos, asin).
M = 2


def _x(spec):
    return (X, spec, True) if isinstance(spec, str) else (X, spec[0], spec[1])


def _n(spec):
    return (N, spec, True) if isinstance(spec, str) else (N, spec[0], spec[1])


def _table(R, rows):
    for prem, concl in rows:
        R.rule([_x(p) for p in prem], _n(concl))


def _equiv(R, cond, preds):
    """``cond -> (pred(node) <-> pred(arg))`` for each pred."""
    for pred in preds:
        R.equiv(cond, (N, pred, True), (X, pred, True))


def _unary(tag, gen, slots=None, units=None):
    """Template for a unary function: ``gen(R, c)`` fills ``R`` (``c`` is the
    constant argument or ``None``).  ``slots(x)`` may supply extra objects
    the rules refer to by index 2, 3, ... (``arg - 1`` for log); ``units(c,
    expr)`` may supply unit facts for a constant argument ``c``.  A node
    with another number of arguments gets no facts: ``log(x, b,
    evaluate=False)`` is ``log(x)/log(b)``, not ``log(x)`` (#191)."""
    def template(expr):
        if len(expr.args) != 1:
            return None
        x = expr.args[0]
        consts = {}
        key = [tag, None]
        if x.is_Atom and x.is_number:
            consts[X] = x
            key[1] = const_key(x)
        objs = [x, expr]
        if slots is not None:
            for obj in slots(x):
                i = len(objs)
                objs.append(obj)
                if obj.is_Atom and obj.is_number:
                    consts[i] = obj
                    key.append(const_key(obj))
                else:
                    key.append(None)

        def build():
            R = Rules()
            gen(R, consts.get(X))
            return R.rules

        out = facts(tuple(key), build, consts, tuple(objs), N)
        if units is not None and X in consts:
            return [out, *units(x, expr)]
        return out
    template.__name__ = tag + '_templates'
    # the module of the rules registers it (TemplateRegistry.register
    # tells a declared module's templates by their module)
    template.__module__ = gen.__module__
    return template


def shifted(x, c):
    """``x + c`` for a number ``c``, as a slot object."""
    # ``x + c`` rebuilds a sum from its terms: Add(y, -y, 1, evaluate=False)
    # - 1 is 0, but the argument is nan at y = oo (#184); a sum whose terms
    # rebuild to the same terms (in any order) is safe
    if x.is_Add:
        t = Add(*x.args)
        if not (t.is_Add and Counter(t.args) == Counter(x.args)):
            return Add(x, c, evaluate=False)
    return x + c


def _minus_one(x):
    return (shifted(x, S.NegativeOne),)


def _minus_plus_one(x):
    """Slots 2 and 3: ``x - 1`` and ``x + 1``."""
    return (shifted(x, S.NegativeOne), shifted(x, S.One))


# ---------------------------------------------------------------------------
# exp / log
# ---------------------------------------------------------------------------

_EXP = (
    (('extended_real',), 'extended_real'),
    (('extended_real',), 'extended_nonnegative'),
    (('real',), 'positive'),
    (('finite',), 'finite'),
    (('finite',), ('zero', False)),
    (('complex',), 'complex'),
    (('extended_negative',), 'complex'),
    (('algebraic', ('zero', False)), 'transcendental'),
    (('infinite', 'extended_negative'), 'zero'),
    (('infinite', 'extended_positive'), 'infinite'),
    (('infinite', 'extended_positive'), 'extended_positive'),
)

_LOG = (
    (('extended_positive',), 'extended_real'),
    (('positive',), 'real'),
    (('zero',), 'infinite'),
    (('zero',), ('extended_real', False)),
    (('complex', ('zero', False)), 'complex'),
    (('finite', ('zero', False)), 'finite'),
    (('infinite',), 'infinite'),
    (('infinite', 'extended_real'), 'extended_positive'),
    (('negative',), ('extended_real', False)),
    (('complex', ('extended_real', False)), ('extended_real', False)),
)


def _exp(R, c, ipi=None):
    _table(R, _EXP)
    # exp(0) == 1
    R.rule([(X, 'zero', True)], (N, 'odd', True))
    R.rule([(X, 'zero', True)], (N, 'positive', True))
    if ipi is not None:
        c, has_s = ipi
        ipi_rules(R.rule, c, M if has_s else None, N)


@registry.register(exp)
def exp_templates(expr):
    """``exp(x)``; for ``x == I*pi*c*s`` (``c`` rational) the value is a
    root of unity or on the unit circle, described in terms of ``s``."""
    x = expr.args[0]
    consts = {}
    objs = [x, expr]
    ipi = None
    if x.is_Atom and x.is_number:
        consts[X] = x
        key = ('exp', const_key(x))
    else:
        split = ipi_split(x)
        if split is not None:
            c, s_ = split
            ipi = (c, s_ is not None)
            if s_ is not None:
                objs.append(s_)
                if s_.is_Atom and s_.is_number:
                    consts[M] = s_
        key = ('exp', None, ipi, const_key(objs[M]) if M in consts else None)

    def build():
        R = Rules()
        _exp(R, consts.get(X), ipi)
        return R.rules

    return facts(key, build, consts, tuple(objs), N)


def _log(R, c):
    _table(R, _LOG)
    # log(x) == 0 iff x == 1; log(x) > 0 iff x > 1 for positive x.
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(M, 'extended_positive', True)], (N, 'extended_positive', True))
    R.rule([(M, 'negative', True), (X, 'positive', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (N, 'positive', True)], (M, 'positive', True))
    R.rule([(X, 'positive', True), (N, 'negative', True)], (M, 'negative', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


registry.register(log)(_unary('log', _log, slots=_minus_one))


# ---------------------------------------------------------------------------
# Abs / re / im / sign / conjugate
# ---------------------------------------------------------------------------

def _abs(R, c):
    R.rule([], (N, 'extended_real', True))
    R.rule([], (N, 'extended_nonnegative', True))
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(N, 'finite', True)], (X, 'finite', True))
    R.rule([(X, 'infinite', True)], (N, 'extended_positive', True))
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))
    _equiv(R, [(X, 'extended_real', True)], ('integer', 'rational', 'even', 'odd', 'algebraic'))
    # Abs(x) == x for x >= 0.
    _equiv(R, [(X, 'extended_nonnegative', True)], ('prime', 'composite'))


# ``re`` and ``im`` are not extended real for every argument:
# ``re(zoo) = im(zoo) = nan``.  The vocabulary cannot tell ``zoo`` from
# ``oo*I`` (``re(oo*I) = 0``) or ``oo + oo*I``, so an infinite non-real
# argument gets no claim; a finite argument gives a real part, an extended
# real one gives itself (``re``) or zero (``im``).
def _re(R, c):
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'extended_real', True)], (N, 'extended_real', True))
    R.rule([(X, 'imaginary', True)], (N, 'zero', True))
    R.rule([(X, 'zero', True)], (N, 'zero', True))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))
    _equiv(R, [(X, 'extended_real', True)], (
        'zero', 'extended_positive', 'extended_negative', 'integer', 'rational',
        'even', 'odd', 'algebraic', 'finite', 'prime', 'composite'))


def _im(R, c):
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'extended_real', True)], (N, 'zero', True))
    R.rule([(X, 'imaginary', True)], (N, 'nonzero', True))
    # a finite argument is read as a complex number x + I*y (above: im is real)
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'zero', False))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))


_SIGN = (
    (('extended_real',), 'integer'),
    (('imaginary',), 'imaginary'),
    (('extended_positive',), 'positive'),
    (('extended_positive',), 'odd'),
    (('extended_negative',), 'negative'),
    (('extended_negative',), 'odd'),
    (('extended_nonnegative',), 'nonnegative'),
    (('extended_nonpositive',), 'nonpositive'),
    (('algebraic',), 'algebraic'),
)


def _sign(R, c):
    R.rule([], (N, 'complex', True))
    _table(R, _SIGN)
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(X, 'extended_real', True), (N, 'positive', True)], (X, 'extended_positive', True))
    R.rule([(X, 'extended_real', True), (N, 'negative', True)], (X, 'extended_negative', True))


# Invariant under conjugation; the rule base derives the rest (real, the
# finite sign predicates, nonzero, infinite, irrational, transcendental...).
_CONJUGATE_INVARIANT = (
    'extended_real', 'finite', 'zero', 'extended_positive', 'extended_negative',
    'integer', 'rational', 'even', 'odd', 'algebraic', 'complex', 'imaginary',
    'prime', 'composite', 'commutative', 'hermitian', 'antihermitian',
)


def _conjugate(R, c):
    _equiv(R, [], _CONJUGATE_INVARIANT)


registry.register(Abs)(_unary('Abs', _abs))
registry.register(re)(_unary('re', _re))
registry.register(im)(_unary('im', _im))
registry.register(sign)(_unary('sign', _sign))
registry.register(conjugate)(_unary('conjugate', _conjugate))


# ---------------------------------------------------------------------------
# floor / ceiling
# ---------------------------------------------------------------------------

def _round(R, c):
    R.equiv([], (N, 'finite', True), (X, 'finite', True))
    # NOTE: floor(1 + I/2) == 1, so "non-real -> non-integer" is unsound.
    R.rule([(X, 'real', True)], (N, 'integer', True))
    R.rule([(X, 'extended_real', True)], (N, 'extended_real', True))
    R.rule([(X, 'complex', True)], (N, 'complex', True))
    # a real value of floor/ceiling is an integer (floor(1 + I/2) == 1 is
    # real; floor(oo) == oo is not)
    R.rule([(N, 'real', True)], (N, 'integer', True))
    _equiv(R, [(X, 'integer', True)], ('even', 'odd', 'zero', 'positive', 'negative'))


def _floor(R, c):
    for pred in ('negative', 'extended_negative', 'nonnegative', 'extended_nonnegative'):
        R.rule([(X, pred, True)], (N, pred, True))


def _ceiling(R, c):
    for pred in ('positive', 'extended_positive', 'nonpositive', 'extended_nonpositive'):
        R.rule([(X, pred, True)], (N, pred, True))


registry.register(RoundFunction)(_unary('round', _round))
registry.register(floor)(_unary('floor', _floor))
registry.register(ceiling)(_unary('ceiling', _ceiling))


def _parts_of_round_rules():
    # slots: 0 the argument y of floor/ceiling, 1 floor(y), 2 re(...) or im(...)
    R = Rules()
    R.rule([(0, 'finite', True)], (2, 'integer', True))
    return R.rules


@registry.register(re, im)
def parts_of_round_templates(expr):
    """``re`` and ``im`` of ``floor(y)`` or ``ceiling(y)`` for finite ``y``
    are integers: SymPy rounds each part (``floor(y) = floor(re(y)) +
    I*floor(im(y))``), so the value is a Gaussian integer.  The vocabulary
    has no Gaussian-integer predicate, hence the rule looks through one
    level of structure."""
    r = expr.args[0]
    if not isinstance(r, (floor, ceiling)):
        return None
    y = r.args[0]
    consts = {0: y} if y.is_Atom and y.is_number else {}
    key = ('parts_of_round', const_key(y) if consts else None)
    return facts(key, _parts_of_round_rules, consts, (y, r, expr), 2)


# ---------------------------------------------------------------------------
# factorial
# ---------------------------------------------------------------------------

_FACTORIAL = (
    (('integer', 'nonnegative'), 'positive'),
    (('integer', 'nonnegative'), 'integer'),
    (('composite',), 'composite'),
    (('zero',), 'odd'),
    (('nonnegative',), 'positive'),
    (('noninteger', 'finite'), 'real'),
    (('noninteger', 'finite'), ('zero', False)),
    (('integer', 'negative'), 'infinite'),
    (('integer', 'negative'), ('extended_real', False)),
)


def _factorial(R, c):
    _table(R, _FACTORIAL)
    for prem in ge2_alternatives(X):
        R.rule(prem, (N, 'even', True))


registry.register(factorial)(_unary('factorial', _factorial))


# ---------------------------------------------------------------------------
# trigonometric
# ---------------------------------------------------------------------------

_TRANSCENDENTAL = (('algebraic', ('zero', False)), 'transcendental')

# sin(oo*I) == oo*I, so finiteness of the value needs a finite argument.
_SIN = (
    (('real',), 'real'), (('complex',), 'complex'), (('finite',), 'finite'),
    (('zero',), 'zero'), (('imaginary',), 'imaginary'), _TRANSCENDENTAL,
)
_COS = (
    (('real',), 'real'), (('complex',), 'complex'), (('finite',), 'finite'),
    (('zero',), 'odd'), (('zero',), 'positive'), (('imaginary',), 'positive'),
    _TRANSCENDENTAL,
)
_TAN = (
    # tan(pi/2) == zoo, so realness needs finiteness of the value.
    (('real',), ('imaginary', False)), (('zero',), 'zero'),
    (('imaginary',), 'imaginary'), _TRANSCENDENTAL,
)


def _sin(R, c):
    _table(R, _SIN)


def _cos(R, c):
    _table(R, _COS)


def _tan(R, c):
    _table(R, _TAN)
    R.rule([(X, 'real', True), (N, 'finite', True)], (N, 'real', True))
    # tan(x + I*y) has imaginary part sinh(2*y)/(cos(2*x) + cosh(2*y)),
    # nonzero for y != 0 (no poles off the real line); a finite argument
    # is read as a complex number, as for im
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'extended_real', False))


_COT = (
    # cot(k*pi) == zoo, so realness needs finiteness of the value.
    (('real',), ('imaginary', False)),
    (('imaginary',), 'imaginary'),          # cot(I*t) == -I*coth(t)
    (('zero',), 'infinite'),
    (('zero',), ('extended_real', False)),
    # cot(x) == cos(x)/sin(x) is finite for algebraic x != 0 (sin(x) == 0
    # only at multiples of pi) and transcendental by Lindemann-Weierstrass:
    # cot(x) == a algebraic would make exp(2*I*x) algebraic.
    (('algebraic', ('zero', False)), 'transcendental'),
    (('algebraic',), ('algebraic', False)),
)


def _cot(R, c):
    _table(R, _COT)
    R.rule([(X, 'real', True), (N, 'finite', True)], (N, 'real', True))
    # cot == 1/tan, and tan(z) is non-real and nonzero off the real line
    R.rule([(X, 'finite', True), (X, 'extended_real', False)], (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (N, 'finite', True)], (N, 'complex', True))


def _asin(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    R.equiv([(N, 'real', True)], (N, 'positive', True), (X, 'positive', True))
    R.equiv([(N, 'real', True)], (N, 'negative', True), (X, 'negative', True))
    # asin is real on [-1, 1].
    R.rule([(X, 'nonnegative', True), (M, 'nonpositive', True)], (N, 'real', True))
    _table(R, ((('finite',), 'finite'), (('complex',), 'complex'),
               (('imaginary',), 'imaginary'), _TRANSCENDENTAL))


def _acos(R, c):
    R.rule([(N, 'real', True)], (N, 'nonnegative', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    # acos(x) == 0 iff x == 1.
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    _table(R, ((('zero',), 'positive'), (('finite',), 'finite'), (('complex',), 'complex')))
    R.rule([(X, 'algebraic', True), (N, 'zero', False)], (N, 'transcendental', True))


def _in_unit_interval_units(kind):
    """Unit facts for ``asin(c)``/``acos(c)`` with a rational or float ``c``
    (exact comparisons): real on [-1, 1], else ``+-pi/2 -+ I*acosh|c|``
    or ``I*acosh(c)`` / ``pi - I*acosh|c|``."""
    def units(c, expr):
        if not (c.is_Rational or c.is_Float):
            return []
        out = [P('finite', expr), P('complex', expr)]
        if -1 <= c <= 1:
            out.append(P('real', expr))
            if kind == 'acos':
                out.append(P('positive' if c < 1 else 'zero', expr))
            else:
                out.append(P('positive' if c > 0 else 'negative' if c < 0 else 'zero', expr))
        else:
            out.append(Not(P('extended_real', expr)))
            if kind == 'acos' and c > 1:
                out.append(P('imaginary', expr))
            else:
                out.append(Not(P('imaginary', expr)))
        return out
    return units


def _atan(R, c):
    R.rule([(X, 'extended_real', True)], (N, 'real', True))
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.equiv([(X, 'extended_real', True)], (N, 'positive', True), (X, 'extended_positive', True))
    R.equiv([(X, 'extended_real', True)], (N, 'negative', True), (X, 'extended_negative', True))
    # atan(I) == oo*I, so restrict to real arguments.
    R.rule([(X, 'real', True), (X, 'algebraic', True), (X, 'zero', False)],
           (N, 'transcendental', True))
    # atan(x) is real iff x is real (atan(I*t) is imaginary, infinite or
    # non-real complex).
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))


_ACOT = (
    (('extended_real',), 'real'),
    (('nonnegative',), 'positive'),           # acot(0) == pi/2
    (('negative',), 'negative'),
    (('extended_nonnegative',), 'nonnegative'),
    (('extended_negative',), 'nonpositive'),  # acot(-oo) == 0
    (('real',), ('zero', False)),
    (('infinite', 'extended_real'), 'zero'),
    (('real', 'algebraic'), 'transcendental'),
    (('imaginary',), ('extended_real', False)),
    # acot(0) == pi/2, acot(+-I) is infinite, acot(x) == atan(1/x) otherwise.
    (('algebraic',), ('algebraic', False)),
)


def _acot(R, c):
    _table(R, _ACOT)


for _cls, _tag, _gen in ((sin, 'sin', _sin), (cos, 'cos', _cos), (tan, 'tan', _tan),
                         (cot, 'cot', _cot), (atan, 'atan', _atan), (acot, 'acot', _acot)):
    registry.register(_cls)(_unary(_tag, _gen))
registry.register(asin)(_unary('asin', _asin, slots=_minus_one,
                               units=_in_unit_interval_units('asin')))
registry.register(acos)(_unary('acos', _acos, slots=_minus_one,
                               units=_in_unit_interval_units('acos')))


# ---------------------------------------------------------------------------
# hyperbolic
# ---------------------------------------------------------------------------

_SINH = (
    (('real',), 'real'), (('extended_real',), 'extended_real'),
    (('finite',), 'finite'), (('complex',), 'complex'),
    (('infinite', 'extended_real'), 'infinite'), _TRANSCENDENTAL,
)
_COSH = (
    (('real',), 'positive'), (('extended_real',), 'extended_positive'),
    (('finite',), 'finite'), (('complex',), 'complex'), (('zero',), 'odd'),
    (('imaginary',), 'real'), _TRANSCENDENTAL,
)


def _sinh(R, c):
    _table(R, _SINH)
    _equiv(R, [(X, 'extended_real', True)], ('extended_positive', 'extended_negative', 'zero'))
    R.rule([(X, 'imaginary', True)], [(N, 'imaginary', True), (N, 'zero', True)])


def _cosh(R, c):
    _table(R, _COSH)


def _tanh(R, c):
    _table(R, ((('extended_real',), 'real'), _TRANSCENDENTAL))
    for pred in ('positive', 'negative'):
        R.equiv([(X, 'extended_real', True)], (N, pred, True), (X, 'extended_' + pred, True))
    R.equiv([(X, 'extended_real', True)], (N, 'zero', True), (X, 'zero', True))


for _cls, _tag, _gen in ((sinh, 'sinh', _sinh), (cosh, 'cosh', _cosh), (tanh, 'tanh', _tanh)):
    registry.register(_cls)(_unary(_tag, _gen))


# ---------------------------------------------------------------------------
# reciprocal and inverse trigonometric and hyperbolic functions (#180)
# ---------------------------------------------------------------------------
#
# Values at the special points follow SymPy's evaluation: ``csc(0) =
# csch(0) = coth(0) = acsch(0) = asec(0) = acsc(0) = zoo``, ``sech(+-oo) =
# csch(+-oo) = 0``, ``coth(+-oo) = +-1``, ``acosh(+-oo) = oo``,
# ``atanh(+-1) = +-oo``, ``atanh(+-oo) = -+I*pi/2``, ``acoth(+-1) = +-oo``,
# ``acoth(0) = I*pi/2``, ``asech(0) = oo``, ``asech(+-oo) = I*pi/2``, and
# ``acoth``, ``acsch``, ``acsc`` are 0 and ``asec`` is ``pi/2`` at every
# infinity.  ``sec``, ``csc`` and ``cot`` of an infinite argument are
# ``AccumBounds`` or ``nan``, and ``sech``/``csch``/``coth`` of an infinite
# non-real one too: no claim is made there.  Branch cuts follow the
# principal branches (``acosh(x) = log(x + sqrt(x + 1)*sqrt(x - 1))``,
# ``atanh(x) = (log(1 + x) - log(1 - x))/2``, ``acoth(x) = atanh(1/x)``,
# ``asech(x) = acosh(1/x)``, ``acsch(x) = asinh(1/x)``, ``asec(x) =
# acos(1/x)``, ``acsc(x) = asin(1/x)``); the claims only use on which side
# of a cut a value lies, never the sign of its imaginary part on the cut.
#
# Transcendence: for algebraic ``a != 0``, ``sin(a)``, ``cos(a)``,
# ``sinh(a)``, ``cosh(a)``, ``tanh(a)`` and ``coth(a)`` are transcendental
# and nonzero (Lindemann-Weierstrass: ``exp(a)`` and ``exp(I*a)`` are), so
# their reciprocals are; an inverse function's value ``b != 0`` at an
# algebraic point is transcendental, else the function of ``b`` would be
# algebraic.
#
# Slots: 0 the argument, 1 the node, 2 ``x - 1``, 3 ``x + 1``.
P1 = 3


def _finite_value(R, pred):
    """``pred(x) & finite(node) -> pred(node)``: the value is a number of
    the kind or ``zoo`` (at a pole)."""
    R.rule([(X, pred, True), (N, 'finite', True)], (N, pred, True))


_SEC = (
    (('real',), ('imaginary', False)),     # sec(pi/2) == zoo
    (('complex',), ('zero', False)),       # cos is finite at a finite point
    (('zero',), 'odd'), (('zero',), 'positive'),
    (('imaginary',), 'positive'),          # sec(I*t) == 1/cosh(t) in (0, 1)
    _TRANSCENDENTAL,
)
_CSC = (
    (('real',), ('imaginary', False)),     # csc(k*pi) == zoo
    (('complex',), ('zero', False)),
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    (('imaginary',), 'imaginary'),         # csc(I*t) == -I/sinh(t)
    _TRANSCENDENTAL,
)


def _sec(R, c):
    _table(R, _SEC)
    _finite_value(R, 'real')
    _finite_value(R, 'complex')


def _csc(R, c):
    _table(R, _CSC)
    _finite_value(R, 'real')
    _finite_value(R, 'complex')


_COTH = (
    (('extended_real', ('zero', False)), 'real'),   # coth(+-oo) == +-1
    (('extended_positive',), 'positive'),           # coth(x) > 1 for x > 0
    (('extended_negative',), 'negative'),
    (('extended_real',), ('imaginary', False)),     # coth(0) == zoo
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    # coth(a) == (exp(2*a) + 1)/(exp(2*a) - 1), exp(2*a) != 1
    (('algebraic', ('zero', False)), 'transcendental'),
)


def _coth(R, c):
    _table(R, _COTH)
    _finite_value(R, 'complex')
    # coth(I*t) == -I*cot(t): imaginary, 0 (t == pi/2) or zoo (t == pi)
    R.rule([(X, 'imaginary', True)], [(N, 'extended_real', False), (N, 'zero', True)])
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], [(N, 'imaginary', True), (N, 'zero', True)])


_SECH = (
    (('extended_real',), 'real'),                   # sech(+-oo) == 0
    (('extended_real',), 'nonnegative'),
    (('real',), 'positive'),
    (('infinite', 'extended_real'), 'zero'),
    (('zero',), 'odd'),
    (('imaginary',), ('imaginary', False)),         # sech(I*t) == sec(t)
    (('complex',), ('zero', False)),
    _TRANSCENDENTAL,
)
_CSCH = (
    (('extended_real', ('zero', False)), 'real'),   # csch(+-oo) == 0
    (('positive',), 'positive'), (('negative',), 'negative'),
    (('extended_positive',), 'nonnegative'), (('extended_negative',), 'nonpositive'),
    (('infinite', 'extended_real'), 'zero'),
    (('extended_real',), ('imaginary', False)),     # csch(0) == zoo
    (('zero',), 'infinite'), (('zero',), ('extended_real', False)),
    (('imaginary',), ('extended_real', False)),     # csch(I*t) == -I/sin(t)
    (('complex',), ('zero', False)),
    _TRANSCENDENTAL,
)


def _sech(R, c):
    _table(R, _SECH)
    _finite_value(R, 'complex')
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], (N, 'real', True))


def _csch(R, c):
    _table(R, _CSCH)
    _finite_value(R, 'complex')
    R.rule([(X, 'imaginary', True), (N, 'finite', True)], (N, 'imaginary', True))


_ASINH = (
    (('real',), 'real'), (('extended_real',), 'extended_real'),
    (('finite',), 'finite'), (('complex',), 'complex'),
    (('infinite',), 'infinite'),                    # asinh(oo*I) == oo, asinh(zoo) == zoo
    # asinh(I*t) == I*asin(t): imaginary for |t| <= 1, else a real part
    (('imaginary',), ('extended_real', False)),
    _TRANSCENDENTAL,
)


def _asinh(R, c):
    _table(R, _ASINH)
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    _equiv(R, [(X, 'extended_real', True)], ('extended_positive', 'extended_negative'))


def _acosh(R, c):
    # acosh(x) == 0 iff x == 1; real (and >= 0) iff x >= 1
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'real', True), (M, 'nonnegative', True)], (N, 'nonnegative', True))
    R.rule([(X, 'real', True), (M, 'positive', True)], (N, 'positive', True))
    # x < 1: I*acos(x) for x in [-1, 1), log(-x + sqrt(x**2 - 1)) + I*pi below
    R.rule([(X, 'real', True), (M, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'extended_positive', True))
    _table(R, (
        (('finite',), 'finite'), (('complex',), 'complex'), (('infinite',), 'infinite'),
        # acosh(I*t) == asinh(|t|) +- I*pi/2
        (('imaginary',), ('extended_real', False)), (('imaginary',), ('imaginary', False)),
    ))
    R.rule([(X, 'algebraic', True), (N, 'zero', False)], (N, 'transcendental', True))


def _atanh(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    # real on (-1, 1) with the sign of x; +-oo at +-1; not real beyond
    R.rule([(M, 'negative', True), (P1, 'positive', True)], (N, 'real', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'positive', True)], (N, 'negative', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'extended_real', False))
    R.rule([(X, 'negative', True), (P1, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'extended_positive', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'extended_negative', True))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'imaginary', True))
    R.rule([(X, 'complex', True), (M, 'zero', False), (P1, 'zero', False)], (N, 'complex', True))
    # atanh(I*t) == I*atan(t), atan(t) in (-pi/2, pi/2) \ {0}
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (M, 'zero', False), (P1, 'zero', False)],
           (N, 'transcendental', True))


def _acoth(R, c):
    # acoth(x) == atanh(1/x): 0 only at the infinities, acoth(0) == I*pi/2;
    # SymPy evaluates acoth(+-oo), acoth(zoo) and acoth(+-oo*I) to 0 but
    # leaves acoth(1 + oo*I) alone (its evalf is nan): no claim there
    R.rule([(N, 'zero', True)], (X, 'infinite', True))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'positive', True), (M, 'zero', True)], (N, 'extended_positive', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'negative', True), (P1, 'zero', True)], (N, 'extended_negative', True))
    R.rule([(X, 'complex', True), (M, 'zero', False), (P1, 'zero', False)], (N, 'complex', True))
    # acoth(I*t) == -I*atan(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (M, 'zero', False), (P1, 'zero', False)],
           (N, 'transcendental', True))


def _asech(R, c):
    # asech(x) == acosh(1/x): real (and >= 0) on (0, 1], 0 iff x == 1
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'positive', True), (M, 'nonpositive', True)], (N, 'nonnegative', True))
    R.rule([(X, 'positive', True), (M, 'negative', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_positive', True))
    # x > 1: I*acos(1/x); x < 0: acosh of a number below 0
    R.rule([(X, 'positive', True), (M, 'positive', True)], (N, 'imaginary', True))
    R.rule([(X, 'negative', True)], (N, 'extended_real', False))
    R.rule([(X, 'infinite', True), (X, 'extended_real', True)], (N, 'imaginary', True))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


def _acsch(R, c):
    # acsch(x) == asinh(1/x): 0 exactly at the infinities, acsch(0) == zoo
    R.equiv([], (N, 'zero', True), (X, 'infinite', True))
    R.rule([(X, 'extended_real', True), (X, 'zero', False)], (N, 'real', True))
    R.rule([(X, 'positive', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True)], (N, 'negative', True))
    R.rule([(X, 'extended_real', True)], (N, 'imaginary', False))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False)], (N, 'transcendental', True))


def _asec(R, c):
    # asec(x) == acos(1/x): real for |x| >= 1, 0 iff x == 1, pi/2 at every
    # infinity
    R.equiv([], (N, 'zero', True), (M, 'zero', True))
    R.rule([(X, 'infinite', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'nonnegative', True)], (N, 'nonnegative', True))
    R.rule([(X, 'negative', True), (P1, 'nonpositive', True)], (N, 'positive', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    # asec(I*t) == pi/2 + I*asinh(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'extended_real', False))
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', False))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


def _acsc(R, c):
    # acsc(x) == asin(1/x): real for |x| >= 1 with the sign of x, 0 exactly
    # at the infinities
    R.equiv([], (N, 'zero', True), (X, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'infinite', True))
    R.rule([(X, 'zero', True)], (N, 'extended_real', False))
    R.rule([(X, 'positive', True), (M, 'nonnegative', True)], (N, 'positive', True))
    R.rule([(X, 'negative', True), (P1, 'nonpositive', True)], (N, 'negative', True))
    R.rule([(X, 'real', True), (M, 'negative', True), (P1, 'positive', True)],
           (N, 'extended_real', False))
    R.rule([(X, 'complex', True), (X, 'zero', False)], (N, 'complex', True))
    # acsc(I*t) == -I*asinh(1/t)
    R.rule([(X, 'imaginary', True)], (N, 'imaginary', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False)], (N, 'transcendental', True))


for _cls, _tag, _gen in ((sec, 'sec', _sec), (csc, 'csc', _csc), (coth, 'coth', _coth),
                         (sech, 'sech', _sech), (csch, 'csch', _csch), (asinh, 'asinh', _asinh),
                         (acsch, 'acsch', _acsch)):
    registry.register(_cls)(_unary(_tag, _gen))
registry.register(acosh)(_unary('acosh', _acosh, slots=_minus_one))
registry.register(asech)(_unary('asech', _asech, slots=_minus_one))
for _cls, _tag, _gen in ((atanh, 'atanh', _atanh), (acoth, 'acoth', _acoth),
                         (asec, 'asec', _asec), (acsc, 'acsc', _acsc)):
    registry.register(_cls)(_unary(_tag, _gen, slots=_minus_plus_one))


def nary(tag, gen, slots=None):
    """Template for a function of fixed arity: ``gen(R, n)`` fills ``R``
    with rules over the arguments ``0 .. n-1``, the node ``n`` and the
    objects ``slots(args)`` from ``n + 1`` on."""
    def template(expr):
        args = expr.args
        objs = (*args, expr) + (tuple(slots(args)) if slots is not None else ())
        consts = {k: o for k, o in enumerate(objs)
                  if k != len(args) and o.is_Atom and o.is_number}
        n = len(args)

        def build():
            R = Rules()
            gen(R, n)
            return R.rules

        # keyed on the arity too: two arities can give as many objects
        # (LambertW(x, k) and a three-argument node built around the check)
        return facts(pattern_key((tag, n), len(objs), consts), build, consts, objs, n)
    template.__name__ = tag + '_templates'
    # the module of the rules registers it (TemplateRegistry.register
    # tells a declared module's templates by their module)
    template.__module__ = gen.__module__
    return template


# ---------------------------------------------------------------------------
# polar numbers: exp_polar, polar_lift, principal_branch (#180)
# ---------------------------------------------------------------------------
#
# The value at a finite argument is a point of the Riemann surface of the
# logarithm, so it is polar (``polar_lift(-2) == 2*exp_polar(I*pi)``); at
# an infinite one it is not (``polar_lift(oo*I) == oo*exp_polar(I*pi/2)``,
# not polar for SymPy), and ``principal_branch(x, oo) == x`` (unevaluated
# with ``evaluate=False``), so a period must be finite and positive.
# ``exp_polar(x)`` of a real ``x`` lies on the sheet of the positive reals
# (``exp_polar(0)`` is 1, SymPy: rational, issue 8008), its value there is
# ``exp(x)``.  Nothing else is claimed: ``exp_polar(2*I*pi)`` is not 1.

def _polar(R, n):
    """Arguments 0 (and 1, the period, for ``n == 2``), node ``n``."""
    R.rule([(0, 'finite', True)] + ([(1, 'positive', True)] if n == 2 else []), (n, 'polar', True))


def _exp_polar(R, c):
    _polar(R, N)
    R.rule([(X, 'real', True)], (N, 'positive', True))
    R.rule([(X, 'zero', True)], (N, 'rational', True))
    R.rule([(X, 'real', True), (X, 'algebraic', True), (X, 'zero', False)],
           (N, 'transcendental', True))


registry.register(exp_polar)(_unary('exp_polar', _exp_polar))
registry.register(polar_lift)(nary('polar_lift', _polar))
registry.register(principal_branch)(nary('principal_branch', _polar))


# ---------------------------------------------------------------------------
# Mod (#180)
# ---------------------------------------------------------------------------
#
# ``Mod(p, q) == p - q*floor(p/q)`` for real ``p`` and real ``q != 0``: in
# ``[0, q)`` for ``q > 0``, in ``(q, 0]`` for ``q < 0``.  ``Mod(p, 0)``
# raises, an infinite argument gives nan, non-real arguments get no claim.

def _mod(R, n):
    p, q = 0, 1
    for pred in ('integer', 'rational', 'real'):
        R.rule([(p, pred, True), (q, pred, True), (q, 'zero', False)], (n, pred, True))
    R.rule([(p, 'real', True), (q, 'positive', True)], (n, 'nonnegative', True))
    R.rule([(p, 'real', True), (q, 'negative', True)], (n, 'nonpositive', True))


registry.register(Mod)(nary('Mod', _mod))
