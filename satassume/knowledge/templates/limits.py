"""Templates for ``Sum``, ``Product`` and ``Integral`` (#180, C-NOTMPL).

These nodes bind their variables, and the engine has no notion of a bound
symbol: a fact assumed about ``x`` is about the free ``x``, not about the
``x`` of ``Sum(1/x, (x, -1, 1))``.  So the function is never a slot.  Its
facts are taken from a context-free query (``registry.context_free``; the
bound symbol keeps its declared assumptions, which is SymPy's convention
too) and decide which rules the node gets; only the ends of the last limit
are slots, since they are in the scope of the node.  A node with more
limits is the last limit over the node of the others
(``Sum(f, l1, l2) == Sum(Sum(f, l1), l2)``).

With the Karr convention of SymPy, ``Sum(f, (x, a, b))`` over a reversed
range (``b < a - 1``) is ``-Sum(f, (x, b + 1, a - 1))`` and
``Product(f, (x, a, b))`` is ``1/Product(f, (x, b + 1, a - 1))``: a
product of zeros over a reversed range is not zero (it is ``zoo``), and an
empty range (``b == a - 1``) gives 0 and 1.  The rules about ``b - a + 1`` take
finite ends, where the difference is that of the values:

* ``Sum``: zero when the function is zero or a range is empty; finite when
  the function and the ends are finite; of the sign of the function over a
  range that is not reversed (strict: not empty).
* ``Product``: 1 (positive integer) when a range is empty; zero when the
  function is zero and ``b - a + 1`` is a positive integer; finite when the
  function and the ends are finite and ``b - a + 1`` is a nonnegative
  integer (a range that is not reversed), and then positive or nonnegative
  with the function.
* ``Integral``: zero when the function is zero or the ends of a definite
  limit are the same (structurally, or finite with a zero difference);
  ``Integral(c, (x, b))`` with ``c`` free of ``x`` is ``c*b`` (SymPy's
  antiderivative), zero when ``b`` is zero and ``c`` finite.  Not SymPy's
  ``Integral._eval_is_zero`` False for a nonzero function, which is no
  theorem (``Integral(sin(x), (x, 0, 2*pi))``).
"""
from __future__ import annotations

from collections import Counter

from sympy import Add, Tuple, preorder_traversal
from sympy.concrete.products import Product
from sympy.concrete.summations import Sum
from sympy.integrals.integrals import Integral

from ._common import Rules, consts_of, facts, pattern_key, units
from .registry import registry

_PREDS = ('zero', 'finite', 'positive', 'negative', 'nonnegative', 'nonpositive')


def _inner(expr):
    """What the last limit runs over and its context-free facts, or None
    when that is no scalar expression."""
    f = expr.function
    inner = f if len(expr.limits) == 1 else expr.func(f, *expr.limits[:-1])
    query = registry.context_free
    if query is None or not all(_scalar(e) for e in (inner, *expr.limits[-1][1:])):
        return None
    return inner, {p: query(inner, p) for p in _PREDS}


def _scalar(e):
    """``e`` and every part of it are commutative scalars (a node's
    ``is_commutative`` alone is not trusted: ``Integral(x, (t, 0, A))``
    claims True for the value ``x*A``)."""
    return all(isinstance(s, Tuple) or not getattr(s, 'is_Matrix', False) and s.is_commutative is True
               for s in preorder_traversal(e))


def _plain(e):
    """``e`` is no sum that rebuilds to other terms (``Add(y, -y, 1,
    evaluate=False)``, nan at ``y = oo``, #184): a difference of plain ends
    is that of their values when they are finite."""
    if e.is_Add:
        t = Add(*e.args)
        return t.is_Add and Counter(t.args) == Counter(e.args)
    return True


def _compiled(tag, gen, a, b, extra, expr):
    """The rules of ``gen`` over the slots ``a, b, *extra, expr``."""
    objs = (a, b, *extra, expr)
    consts = consts_of(objs[:-1])
    return facts(pattern_key(tag, len(objs), consts), gen, consts, objs, len(objs) - 1)


def _sum_or_product(expr, product):
    got = _inner(expr)
    if got is None:
        return None
    _, inner = got
    tag = 'Product' if product else 'Sum'
    if not product and inner['zero']:
        return units((tag, 'zero'), lambda: [('zero', True)], expr)
    _, a, b = expr.limits[-1]
    if not (_plain(a) and _plain(b)):
        return None
    held = tuple(p for p in _PREDS if inner[p])
    A, B, E, N = 0, 1, 2, 3   # a, b, b - a + 1, node
    fin = [(A, 'finite', True), (B, 'finite', True)]
    # a range that is not reversed (maybe empty), and one that is not empty
    fwd = [*fin, (E, 'integer', True), (E, 'nonnegative', True)]
    full = [*fin, (E, 'integer', True), (E, 'positive', True)]

    def gen():
        R = Rules()
        if product:
            # an empty range: the product is 1
            R.rule([*fin, (E, 'zero', True)], (N, 'positive', True))
            R.rule([*fin, (E, 'zero', True)], (N, 'integer', True))
            if 'zero' in held:
                R.rule(full, (N, 'zero', True))
            if 'finite' in held:
                R.rule(fwd, (N, 'finite', True))
            for p in ('positive', 'nonnegative'):
                if p in held:
                    R.rule(fwd, (N, p, True))
        else:
            R.rule([*fin, (E, 'zero', True)], (N, 'zero', True))
            if 'finite' in held:
                R.rule(fin, (N, 'finite', True))
            for p, pre in (('positive', full), ('negative', full),
                           ('nonnegative', fwd), ('nonpositive', fwd)):
                if p in held:
                    R.rule(pre, (N, p, True))
        return R.rules

    return _compiled((tag, held), gen, a, b, (b - a + 1,), expr)


@registry.register(Sum)
def sum_templates(expr):
    return _sum_or_product(expr, False)


@registry.register(Product)
def product_templates(expr):
    return _sum_or_product(expr, True)


@registry.register(Integral)
def integral_templates(expr):
    got = _inner(expr)
    if got is None:
        return None
    inner, f = got
    if f['zero']:
        return units(('Integral', 'zero'), lambda: [('zero', True)], expr)
    lim = expr.limits[-1]
    if len(lim) == 3:
        _, a, b = lim
        if a == b:
            return units(('Integral', 'zero'), lambda: [('zero', True)], expr)
        if not (_plain(a) and _plain(b)):
            return None
        A, B, D, N = 0, 1, 2, 3

        def gen():
            R = Rules()
            R.rule([(A, 'finite', True), (B, 'finite', True), (D, 'zero', True)], (N, 'zero', True))
            return R.rules

        return _compiled(('Integral', 3), gen, a, b, (a - b,), expr)
    if len(lim) == 2 and lim[0] not in inner.free_symbols and f['finite']:
        # the antiderivative of c is c*x: the node is c*b
        b = lim[1]
        objs = (b, expr)
        consts = consts_of(objs[:1])

        def gen2():
            R = Rules()
            R.rule([(0, 'zero', True)], (1, 'zero', True))
            return R.rules

        return facts(pattern_key(('Integral', 2), 2, consts), gen2, consts, objs, 1)
    return None
