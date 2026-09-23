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

from sympy.core.function import Function
from sympy.functions.combinatorial.factorials import factorial
from sympy.functions.elementary.complexes import Abs, conjugate, im, re, sign
from sympy.functions.elementary.exponential import exp, log
from sympy.functions.elementary.hyperbolic import cosh, sinh, tanh
from sympy.functions.elementary.integers import RoundFunction, ceiling, floor
from sympy.functions.elementary.trigonometric import (
    acos,
    acot,
    asin,
    atan,
    cos,
    sin,
    tan,
)

from ._common import (
    Rules,
    const_key,
    consts_of,
    facts,
    ge2_alternatives,
    lits,
    pattern_key,
)
from .registry import registry

X, N = 0, 1


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


def _unary(tag, gen):
    """Template for a unary function: ``gen(R, c)`` fills ``R`` (``c`` is the
    constant argument or ``None``)."""
    def template(expr):
        x = expr.args[0]
        if x.is_Atom and x.is_number:
            consts = {X: x}
            key = (tag, const_key(x))
        else:
            consts = {}
            key = (tag,)

        def build():
            R = Rules()
            gen(R, consts.get(X))
            return R.rules

        return facts(key, build, consts, (x, expr))
    template.__name__ = tag + '_templates'
    return template


def _commutative_rules(n):
    R = Rules()
    A = range(n)
    R.rule(lits(A, 'commutative'), (n, 'commutative', True))
    for k in A:
        R.rule([(n, 'commutative', True)], (k, 'commutative', True))
    return R.rules


@registry.register(Function)
def function_commutative(expr):
    args = expr.args
    n = len(args)
    if n == 0:
        return ()
    consts = consts_of(args)
    return facts(pattern_key('function', n, consts), lambda: _commutative_rules(n),
                 consts, args + (expr,))


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


def _exp(R, c):
    _table(R, _EXP)


def _log(R, c):
    _table(R, _LOG)
    # log(x) == 0 iff x == 1.
    R.rule([(N, 'zero', True)], (X, 'odd', True))
    R.rule([(N, 'zero', True)], (X, 'positive', True))
    R.rule([(X, 'algebraic', True), (X, 'zero', False), (N, 'zero', False)],
           (N, 'transcendental', True))


registry.register(exp)(_unary('exp', _exp))
registry.register(log)(_unary('log', _log))


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


def _re(R, c):
    R.rule([], (N, 'extended_real', True))
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'imaginary', True)], (N, 'zero', True))
    R.rule([(X, 'zero', True)], (N, 'zero', True))
    R.rule([(X, 'algebraic', True)], (N, 'algebraic', True))
    _equiv(R, [(X, 'extended_real', True)], (
        'zero', 'extended_positive', 'extended_negative', 'integer', 'rational',
        'even', 'odd', 'algebraic', 'finite', 'prime', 'composite'))


def _im(R, c):
    R.rule([], (N, 'extended_real', True))
    R.rule([(X, 'finite', True)], (N, 'real', True))
    R.rule([(X, 'extended_real', True)], (N, 'zero', True))
    R.rule([(X, 'imaginary', True)], (N, 'nonzero', True))
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

_SIN = (
    (('real',), 'real'), (('complex',), 'complex'), (('zero',), 'zero'),
    (('imaginary',), 'imaginary'), _TRANSCENDENTAL,
)
_COS = (
    (('real',), 'real'), (('complex',), 'complex'), (('zero',), 'odd'),
    (('zero',), 'positive'), (('imaginary',), 'positive'), _TRANSCENDENTAL,
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


def _asin(R, c):
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    R.equiv([(N, 'real', True)], (N, 'positive', True), (X, 'positive', True))
    R.equiv([(N, 'real', True)], (N, 'negative', True), (X, 'negative', True))
    _table(R, ((('finite',), 'finite'), (('complex',), 'complex'), _TRANSCENDENTAL))


def _acos(R, c):
    R.rule([(N, 'real', True)], (N, 'nonnegative', True))
    R.rule([(N, 'real', True)], (X, 'real', True))
    # acos(x) == 0 iff x == 1.
    R.rule([(N, 'zero', True)], (X, 'odd', True))
    R.rule([(N, 'zero', True)], (X, 'positive', True))
    _table(R, ((('zero',), 'positive'), (('finite',), 'finite'), (('complex',), 'complex')))
    R.rule([(X, 'algebraic', True), (N, 'zero', False)], (N, 'transcendental', True))


def _atan(R, c):
    R.rule([(X, 'extended_real', True)], (N, 'real', True))
    R.equiv([], (N, 'zero', True), (X, 'zero', True))
    R.equiv([(X, 'extended_real', True)], (N, 'positive', True), (X, 'extended_positive', True))
    R.equiv([(X, 'extended_real', True)], (N, 'negative', True), (X, 'extended_negative', True))
    # atan(I) == oo*I, so restrict to real arguments.
    R.rule([(X, 'real', True), (X, 'algebraic', True), (X, 'zero', False)],
           (N, 'transcendental', True))


_ACOT = (
    (('extended_real',), 'real'),
    (('nonnegative',), 'positive'),           # acot(0) == pi/2
    (('negative',), 'negative'),
    (('extended_nonnegative',), 'nonnegative'),
    (('extended_negative',), 'nonpositive'),  # acot(-oo) == 0
    (('real',), ('zero', False)),
    (('infinite', 'extended_real'), 'zero'),
    (('real', 'algebraic'), 'transcendental'),
)


def _acot(R, c):
    _table(R, _ACOT)


for _cls, _tag, _gen in ((sin, 'sin', _sin), (cos, 'cos', _cos), (tan, 'tan', _tan),
                         (asin, 'asin', _asin), (acos, 'acos', _acos),
                         (atan, 'atan', _atan), (acot, 'acot', _acot)):
    registry.register(_cls)(_unary(_tag, _gen))


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
