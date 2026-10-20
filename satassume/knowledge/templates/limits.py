"""Templates for ``Sum``, ``Product`` and ``Integral`` (#180, C-NOTMPL).

These nodes bind their variables, and the engine has no notion of a bound
symbol: a fact assumed about ``x`` is about the free ``x``, not about the
``x`` of ``Sum(1/x, (x, -1, 1))``.  So the function is never a slot.  Its
facts are taken from context-free queries (``registry.context_free``) with
the bound symbol replaced by a Dummy that has only what the range
guarantees about its points (``_DOMAINS``: not the declared assumptions of
the bound symbol, against SymPy) and decide which rules the node gets;
only the ends of the last limit are slots, since they are in the scope of
the node.  A node with more limits is the last limit over the node of the
others (``Sum(f, l1, l2) == Sum(Sum(f, l1), l2)``).

With the Karr convention of SymPy, ``Sum(f, (x, a, b))`` over a reversed
range (``b < a - 1``) is ``-Sum(f, (x, b + 1, a - 1))`` and
``Product(f, (x, a, b))`` is ``1/Product(f, (x, b + 1, a - 1))``: a
product of zeros over a reversed range is not zero (it is ``zoo``), and an
empty range (``b == a - 1``) gives 0 and 1.  The rules about ``b - a + 1``
take finite ends, where the difference is that of the values.

Below, "the function is P" is: P for every point of a domain of
``_DOMAINS``, under that domain's premises, and a range has finitely many
points when ``b - a + 1`` is an integer.

* ``Sum``: zero when the function is zero over finitely many points or
  the range is empty; finite when the function and the ends are finite
  over finitely many points; of the sign of the function over a range that
  is not reversed (strict: not empty).
* ``Product``: 1 (positive integer) when the range is empty; zero when the
  function is zero and ``b - a + 1`` is a positive integer; finite,
  positive or nonnegative with the function when the ends are finite and
  ``b - a + 1`` is a nonnegative integer (a range that is not reversed).
* ``Integral``: zero when the function is zero or the ends of a definite
  limit are the same (structurally, or finite with a zero difference);
  ``Integral(c, (x, b))`` with ``c`` free of ``x`` is ``c*b`` (SymPy's
  antiderivative), zero when ``b`` is zero and ``c`` finite.  Not SymPy's
  ``Integral._eval_is_zero`` False for a nonzero function, which is no
  theorem (``Integral(sin(x), (x, 0, 2*pi))``).
"""
from __future__ import annotations

from collections import Counter

from sympy import Add, Dummy, Symbol, Tuple, preorder_traversal
from sympy.concrete.products import Product
from sympy.concrete.summations import Sum
from sympy.integrals.integrals import Integral

from ._common import Rules, consts_of, facts, pattern_key, units
from .registry import registry

_PREDS = ('zero', 'finite', 'positive', 'negative', 'nonnegative', 'nonpositive')


#: the domains of the bound variable a function is queried over, as
#: ``(name, assumptions of the Dummy, premises over the slots)``: what the
#: range guarantees about its points (the slots are ``A, B, E`` = ``a, b,
#: b - a + 1``).  With an integer ``a`` every point ``a + j`` is an
#: integer, the points ``b + 1 .. a - 1`` of a reversed range too (Karr).
#: The points of a range that is not reversed (``E`` a nonnegative
#: integer) are in ``[a, b]``, so they have the sign of both ends (an
#: empty range, the only one with ends of different signs, has a rule of
#: its own).  The declared assumptions of the bound symbol are no fact
#: about the points: ``Sum(1/k, (k, 1, n))`` with ``k`` positive is ``zoo``
#: at ``n = -1``.
_FWD = ((2, 'integer', True), (2, 'nonnegative', True))
_DOMAINS = (
    ('any', {}, []),
    ('int', {'integer': True}, [(0, 'integer', True)]),
    *((p, {'integer': True, p: True}, [(0, 'integer', True), (0, p, True), (1, p, True), *_FWD])
      for p in ('positive', 'nonnegative', 'negative', 'nonpositive')),
)


def _inner(expr, domains):
    """What the last limit runs over and the predicates it holds for every
    value of its variable in each of ``domains`` (context-free; only what a
    more general domain lacks), as ``(inner, ((domain, held), ...))``, or
    None when that is no scalar expression."""
    f = expr.function
    lim = expr.limits[-1]
    v = lim[0]
    inner = f if len(expr.limits) == 1 else expr.func(f, *expr.limits[:-1])
    query = registry.context_free
    if (query is None or not isinstance(v, Symbol) or any(l[0] == v for l in expr.limits[:-1])
            or not all(_scalar(e) for e in (inner, *lim[1:]))):
        return None
    if v not in inner.free_symbols:
        domains = domains[:1]
    out, seen = [], {}
    for name, assumptions, _ in domains:
        got = query(inner.xreplace({v: Dummy(v.name, **assumptions)}), _PREDS)
        seen[name] = {p for p in _PREDS if got[p]}
        # 'any' is more general than 'int', 'int' than the signed domains
        base = set() if name == 'any' else seen['any'] | (seen['int'] if name != 'int' else set())
        held = tuple(p for p in _PREDS if p in seen[name] - base)
        if held:
            out.append((name, held))
    return inner, tuple(out)


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
    _, a, b = expr.limits[-1]
    if not (_plain(a) and _plain(b)):
        return None
    got = _inner(expr, _DOMAINS)
    if got is None:
        return None
    held = got[1]
    tag = 'Product' if product else 'Sum'
    A, B, E, N = 0, 1, 2, 3   # a, b, b - a + 1, node
    fin = [(A, 'finite', True), (B, 'finite', True)]
    # a range with finitely many points, one that is not reversed (maybe
    # empty), and one that is not empty
    some = [*fin, (E, 'integer', True)]
    fwd = [*some, (E, 'nonnegative', True)]
    full = [*some, (E, 'positive', True)]
    pre = {name: prem for name, _, prem in _DOMAINS}

    def gen():
        R = Rules()
        # an empty range: the sum is 0, the product 1
        if product:
            R.rule([*fin, (E, 'zero', True)], (N, 'positive', True))
            R.rule([*fin, (E, 'zero', True)], (N, 'integer', True))
        else:
            R.rule([*fin, (E, 'zero', True)], (N, 'zero', True))
        for name, ps in held:
            P = pre[name]
            if product:
                if 'zero' in ps:
                    R.rule([*P, *full], (N, 'zero', True))
                for p in ('finite', 'positive', 'nonnegative'):
                    if p in ps:
                        R.rule([*P, *fwd], (N, p, True))
            else:
                if 'zero' in ps:
                    R.rule([*P, *some], (N, 'zero', True))
                if 'finite' in ps:
                    R.rule([*P, *some], (N, 'finite', True))
                for p, rng in (('positive', full), ('negative', full),
                               ('nonnegative', fwd), ('nonpositive', fwd)):
                    if p in ps:
                        R.rule([*P, *rng], (N, p, True))
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
    got = _inner(expr, _DOMAINS[:1])
    if got is None:
        return None
    inner, held = got
    f = held[0][1] if held else ()
    if 'zero' in f:
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
    if len(lim) == 2 and not inner.has(lim[0]) and 'finite' in f:
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
