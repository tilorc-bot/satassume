"""Structural templates for combinatorial functions (#180, C-NOTMPL):
``factorial2``, ``subfactorial``, ``RisingFactorial``,
``FallingFactorial``, ``binomial``, ``catalan``, ``andre``, ``genocchi``
and ``partition`` (``factorial`` is in :mod:`.functions`).

These functions are defined on (nonnegative) integers, and SymPy leaves
them unevaluated or raises elsewhere (``factorial2(-4)``,
``partition(1/2)``); the rules state facts for the integer points and
for the real points where SymPy's extension is a theorem (``catalan(x) =
4**x*gamma(x + 1/2)/(sqrt(pi)*gamma(x + 2)) > 0`` for ``x >= 0``).  A node
with a constant integer argument (``genocchi(8, evaluate=False)``) gets
the facts of its value.

Unary templates: the argument is index 0, the node index 1, slots from 2.
"""
from __future__ import annotations

from sympy import S
from sympy.functions.combinatorial.factorials import (
    FallingFactorial,
    RisingFactorial,
    binomial,
    factorial2,
    subfactorial,
)
from sympy.functions.combinatorial.numbers import andre, catalan, genocchi, partition

from .atoms import value_units
from .functions import _table, _unary, nary, shifted
from .registry import registry

X, N = 0, 1

#: largest constant argument whose value is computed for its unit facts
MAX_VALUE_ARG = 200


def _value_units(c, expr):
    """Unit facts of ``expr``, a node with the constant argument ``c``,
    from its value (``expr.func(c)`` evaluates it)."""
    if not (c.is_Integer and abs(c) <= MAX_VALUE_ARG):
        return []
    try:
        v = expr.func(c)
    except (ValueError, TypeError, ArithmeticError):
        return []
    if not (v.is_Atom and v.is_number) or v is S.NaN:
        return []
    return [value_units(v, expr)]


def _register_unary(cls, tag, gen, slots=None):
    registry.register(cls)(_unary(tag, gen, slots=slots, units=_value_units))


# ---------------------------------------------------------------------------
# factorial2: n!! for integers n >= -1 and odd n < -1, n!! = (n + 2)!!/(n + 2)
# ---------------------------------------------------------------------------
# values: (-5)!! = 1/3, (-3)!! = -1, (-1)!! = 0!! = 1, 1, 2, 3, 8, 15, ...;
# an even n < 0 raises.  Slots 2: n + 1, 3: n + 3.

def _factorial2_slots(x):
    return (shifted(x, S.One), shifted(x, S(3)))


def _factorial2(R, c):
    R.rule([(X, 'integer', True), (2, 'nonnegative', True)], (N, 'positive', True))
    R.rule([(X, 'integer', True), (2, 'nonnegative', True)], (N, 'integer', True))
    # odd n >= -3: an odd integer; any odd n: a rational, never even
    R.rule([(X, 'odd', True), (3, 'nonnegative', True)], (N, 'odd', True))
    _table(R, (
        (('odd',), 'rational'), (('odd',), ('zero', False)), (('odd',), ('even', False)),
        (('zero',), 'odd'), (('zero',), 'positive'),
        (('even', 'positive'), 'even'), (('even', 'positive'), 'positive'),
    ))


_register_unary(factorial2, 'factorial2', _factorial2, _factorial2_slots)


# ---------------------------------------------------------------------------
# subfactorial: !0 = 1, !1 = 0, !n = n*!(n - 1) + (-1)**n, so !n is odd for
# even n and even for odd n
# ---------------------------------------------------------------------------

def _subfactorial(R, c):
    _table(R, (
        (('integer', 'nonnegative'), 'integer'), (('integer', 'nonnegative'), 'nonnegative'),
        (('odd', 'nonnegative'), 'even'), (('even', 'nonnegative'), 'odd'),
    ))


_register_unary(subfactorial, 'subfactorial', _subfactorial)


# ---------------------------------------------------------------------------
# catalan: 4**n*gamma(n + 1/2)/(sqrt(pi)*gamma(n + 2)), an integer for
# integers n >= 0, prime only for n = 2, 3 (C_n = 1, 1, 2, 5, 14, 42, ...)
# ---------------------------------------------------------------------------

def _catalan(R, c):
    _table(R, (
        (('nonnegative',), 'positive'),
        (('integer', 'nonnegative'), 'integer'),
    ))
    R.rule([(X, 'integer', True), (2, 'positive', True)], (N, 'composite', True))


_register_unary(catalan, 'catalan', _catalan, lambda x: (shifted(x, S(-3)),))


# ---------------------------------------------------------------------------
# andre: the number of alternating permutations, a positive integer for
# integers n >= 0
# ---------------------------------------------------------------------------

def _andre(R, c):
    _table(R, ((('integer', 'nonnegative'), 'integer'), (('integer', 'nonnegative'), 'positive')))


_register_unary(andre, 'andre', _andre)


# ---------------------------------------------------------------------------
# partition: p(n) is 0 for integers n < 0, positive for n >= 0
# ---------------------------------------------------------------------------

def _partition(R, c):
    _table(R, (
        (('integer',), 'integer'), (('integer',), 'nonnegative'),
        (('integer', 'negative'), 'zero'), (('integer', 'nonnegative'), 'positive'),
    ))


_register_unary(partition, 'partition', _partition)


# ---------------------------------------------------------------------------
# genocchi(n) = 2*(1 - 2**n)*bernoulli(n): G_0 = 0, G_1 = -1, G_n = 0 for
# odd n > 1, G_2k an odd integer of sign (-1)**k (-1, 1, -3, 17, -155, ...).
# Slots 2: n - 1, 3: n/2.  The polynomials genocchi(n, x) get no rule.
# ---------------------------------------------------------------------------

def _genocchi(R, c):
    _table(R, (
        (('integer', 'nonnegative'), 'integer'),
        (('zero',), 'zero'),
        (('even', 'positive'), 'odd'),
    ))
    R.rule([(X, 'odd', True), (2, 'zero', True)], (N, 'odd', True))
    R.rule([(X, 'odd', True), (2, 'zero', True)], (N, 'negative', True))
    R.rule([(X, 'odd', True), (2, 'positive', True)], (N, 'zero', True))
    R.rule([(X, 'even', True), (X, 'positive', True), (3, 'even', True)], (N, 'positive', True))
    R.rule([(X, 'even', True), (X, 'positive', True), (3, 'odd', True)], (N, 'negative', True))


_genocchi_unary = _unary('genocchi', _genocchi, slots=lambda x: (shifted(x, S.NegativeOne), x/2),
                         units=_value_units)


# genocchi(n, x) (a polynomial in x) gets no facts (``_unary``)
registry.register(genocchi)(_genocchi_unary)


# ---------------------------------------------------------------------------
# rising and falling factorials, binomial coefficients
# ---------------------------------------------------------------------------
# rf(x, k) = x*(x + 1)*...*(x + k - 1), ff(x, k) = x*(x - 1)*...*(x - k + 1)
# for integers k >= 0 (1 for k = 0, whatever x but nan); binomial(n, k) is 0 for
# integers k < 0, 1 for k = 0, ff(n, k)/k! for integers k > 0: an integer
# for integer n, >= 0 for n >= 0 or even k.  Slots: 0 x (n), 1 k, 2 node.

_K = ((1, 'integer', True), (1, 'nonnegative', True))


def _rising_falling(R, n, positive):
    for pred in ('integer', 'rational', 'real'):
        R.rule([(0, pred, True), *_K], (2, pred, True))
    if positive:
        R.rule([(0, 'positive', True), *_K], (2, 'positive', True))
    else:
        # ff(n, k) == n!/(n - k)! for k <= n, 0 for k > n
        R.rule([(0, 'integer', True), (0, 'nonnegative', True), *_K], (2, 'nonnegative', True))
    # 1 at k = 0 for every x but nan, which SymPy propagates first
    # (rf(x + y, 0) is nan at x = oo, y = -oo); zoo is left out
    for x in ('complex', 'extended_real'):
        R.rule([(0, x, True), (1, 'zero', True)], (2, 'odd', True))
        R.rule([(0, x, True), (1, 'zero', True)], (2, 'positive', True))


def _binomial(R, n):
    R.rule([(0, 'integer', True), (1, 'integer', True)], (2, 'integer', True))
    R.rule([(1, 'integer', True), (1, 'negative', True)], (2, 'zero', True))
    R.rule([(1, 'zero', True)], (2, 'odd', True))
    R.rule([(1, 'zero', True)], (2, 'positive', True))
    R.rule([(0, 'integer', True), (0, 'nonnegative', True), (1, 'integer', True)],
           (2, 'nonnegative', True))
    # binomial(n, k) == (-1)**k*binomial(k - n - 1, k) for n < 0
    R.rule([(0, 'integer', True), (1, 'even', True)], (2, 'nonnegative', True))


registry.register(RisingFactorial)(nary('rf', lambda R, n: _rising_falling(R, n, True)))
registry.register(FallingFactorial)(nary('ff', lambda R, n: _rising_falling(R, n, False)))
registry.register(binomial)(nary('binomial', _binomial))
