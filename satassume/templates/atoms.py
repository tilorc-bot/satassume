"""Unit facts for atomic SymPy objects (symbols and numeric constants).

* ``Symbol`` (and its subclasses ``Dummy`` and ``Wild``): the user-declared
  assumptions and their closure, as stored in ``assumptions0``.
* Numbers, number symbols (``pi``, ``E``, ...), ``I``, ``oo``, ``-oo``,
  ``zoo`` and ``nan``: these objects have fixed values, so every old-system
  ``is_<pred>`` property that is not ``None`` is a trustworthy static fact
  (the "atom oracle").
* Any other expression that no template relates to its arguments' commutativity
  (``Max``, ``Integral``, ``Piecewise``, ``Trace``, ``M[0, 0]``, ...):
  ``commutative`` when SymPy's structural ``is_commutative`` says so and every
  scalar ingredient is commutative, see :func:`structural_commutative`.

Any other leaf emits nothing.
"""
from __future__ import annotations

from sympy.core.add import Add
from sympy.core.expr import Expr
from sympy.core.function import Function
from sympy.core.mul import Mul
from sympy.core.numbers import ComplexInfinity, ImaginaryUnit, Number, NumberSymbol
from sympy.core.power import Pow
from sympy.core.symbol import Symbol

from ._common import VOCAB, const_facts, const_key, units
from ..rules import PRED_INDEX
from .registry import registry
from ..memos import PROCESS as _PROCESS

_ORACLE_PREDS = tuple(sorted(VOCAB))
# Properties read on a constant.  The rest (the extended sign predicates,
# hermitian/antihermitian, the signed infinities, nonzero, noninteger,
# irrational, ...) follows from these by the rule-base closure applied in
# ``units``; ``polar`` is undecidable for numbers.
_CONST_BASIS = (
    'algebraic', 'commutative', 'complex', 'composite', 'even', 'finite',
    'imaginary', 'infinite', 'integer', 'negative', 'odd', 'positive', 'prime',
    'rational', 'real', 'transcendental', 'zero', 'extended_real',
    'extended_positive', 'extended_negative',
)


@registry.register(Symbol)
def symbol_units(expr):
    a0 = expr.assumptions0
    key = ('symbol', frozenset(a0.items()))
    return units(key, lambda: [(fact, value) for fact, value in a0.items()
                               if fact in VOCAB and value is not None], expr)


@registry.register(Number, NumberSymbol, ImaginaryUnit, ComplexInfinity)
def constant_units(expr):
    def gen():
        out = []
        facts = const_facts(expr)
        for pred in _CONST_BASIS:
            value = facts[PRED_INDEX[pred]]
            if value is not None:
                out.append((pred, value))
        return out
    return units(('const', const_key(expr)), gen, expr)


# Nodes whose commutativity other templates already decide: atoms emit it
# above; Add, Mul, Pow and functions of expressions derive it from their
# arguments (``commutative`` is closed under them).
_STRUCTURAL = (Symbol, Number, NumberSymbol, ImaginaryUnit, ComplexInfinity, Add, Mul, Pow)
_INGREDIENTS_MAX = 50_000
_INGREDIENTS = _PROCESS.table("satassume.templates.atoms._INGREDIENTS", "pure", _INGREDIENTS_MAX)


def _commutative_ingredients(expr) -> bool:
    """Every scalar subexpression of ``expr`` (``expr`` included) is
    commutative by SymPy's ``is_commutative``.  Non-expressions (tuples,
    conditions) and matrix expressions are not themselves scalars and are
    only looked into: ``M[0, 0]`` and ``Trace(M)`` are commutative scalars
    (SymPy's matrices have commutative entries; ``A*M`` for a
    non-commutative ``A`` is rejected by ``MatMul``)."""
    r = _INGREDIENTS.get(expr)
    if r is None:
        r = all(_commutative_ingredients(a) for a in expr.args) and (
            not isinstance(expr, Expr) or expr.is_Matrix or expr.is_commutative is True)
        if len(_INGREDIENTS) >= _INGREDIENTS_MAX:
            _INGREDIENTS.clear()
        _INGREDIENTS[expr] = r
    return r


@registry.register(Expr)
def structural_commutative(expr):
    """``commutative(expr)`` when SymPy's ``is_commutative`` is True and
    so is that of every scalar ingredient.

    ``is_commutative`` is structural: fixed by the class (``Trace``,
    ``MatrixElement``, ``Max``) or computed from the arguments, never from
    other assumptions.  Its value alone is not enough: some classes read
    only part of their arguments, e.g. ``Subs(x, x, A)`` and
    ``Integral(x, (t, 0, A))`` claim True from their commutative expression
    although their values ``A`` and ``x*A`` are not commutative.  With every
    ingredient commutative there is nothing non-commutative to evaluate to.
    Only the positive fact is emitted, never a negation from False."""
    if isinstance(expr, _STRUCTURAL) or expr.is_Matrix:
        return None
    if isinstance(expr, Function) and all(isinstance(a, Expr) for a in expr.args):
        return None
    if not _commutative_ingredients(expr):
        return None
    return units(('structural_commutative',), lambda: [('commutative', True)], expr)
