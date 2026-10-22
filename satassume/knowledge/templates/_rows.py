"""Template rules written as SymPy booleans (#249).

A *row* is ``premises >> conclusion`` over a plain symbol ``x`` and the
node ``f(x)``::

    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(sin(x))

The premises are a conjunction of literals; the conclusion is a literal, a
disjunction of literals, or a conjunction of those (one rule each).  A
literal is ``Q.p(t)`` or ``~Q.p(t)`` with ``p`` in ``VOCAB`` and ``t`` the
argument or the node.  :func:`rules` compiles the rows of a unary head, at
import, into the index specs of :mod:`._common` (argument 0, node 1), so
the patterns, their cache and the engine are unchanged.

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``.  A row whose top is not an implication is rejected, which
catches the missing parentheses and a row SymPy collapsed to ``True``.
"""
from __future__ import annotations

from sympy import And, Implies, Not, Or, Symbol
from sympy.assumptions.assume import AppliedPredicate

from ._common import VOCAB, Rules

X, N = 0, 1


def rules(head, rows, module: str):
    """The ``gen(R, c)`` of :func:`.functions._unary` for ``rows`` about
    ``head``; ``module`` (the caller's ``__name__``) is the module the
    registry attributes the template to (``TemplateRegistry.lazy``)."""
    specs = [spec for row in rows for spec in _specs(head, row)]

    def gen(R: Rules, c) -> None:
        for prem, concl in specs:
            R.rule(prem, list(concl))
    gen.__module__ = module
    gen.__name__ = gen.__qualname__ = f'{head.__name__}_rows'
    return gen


def _specs(head, row):
    if not isinstance(row, Implies):
        raise TypeError(f"{head.__name__} row {row} is not an implication "
                        "(parenthesize both sides: >> binds tighter than &)")
    prem, concl = row.args
    slots = {}
    premises = [_lit(head, row, t, slots) for t in _conjuncts(prem)]
    out = []
    for c in _conjuncts(concl):
        out.append((premises, [_lit(head, row, t, slots)
                               for t in (c.args if isinstance(c, Or) else (c,))]))
    nodes = [t for t, k in slots.items() if k == N]
    if not nodes:
        raise ValueError(f"{head.__name__} row {row} does not mention the node")
    if len(nodes) > 1 or any(k == X and t != nodes[0].args[0] for t, k in slots.items()):
        raise ValueError(f"{head.__name__} row {row} mentions more than one argument")
    return out


def _conjuncts(e):
    return e.args if isinstance(e, And) else (e,)


def _lit(head, row, e, slots):
    pos = not isinstance(e, Not)
    a = e if pos else e.args[0]
    if not (isinstance(a, AppliedPredicate) and len(a.arguments) == 1):
        raise ValueError(f"{head.__name__} row {row}: {e} is not a literal")
    pred = str(a.function.name)
    if pred not in VOCAB:
        raise ValueError(f"{head.__name__} row {row}: {pred} is not a template predicate")
    t = a.arguments[0]
    if t not in slots:
        slots[t] = _slot(head, row, t)
    return (slots[t], pred, pos)


def _slot(head, row, t):
    if type(t) is head and len(t.args) == 1:
        _plain(head, row, t.args[0])
        return N
    if isinstance(t, Symbol):
        _plain(head, row, t)
        return X
    # a constructor that rewrote the written term: cos(x + pi/2) is -sin(x)
    raise ValueError(f"{head.__name__} row {row}: {t} is neither the argument "
                     f"nor {head.__name__} of it")


def _plain(head, row, s):
    # a symbol with assumptions would make SymPy rewrite the terms built
    # from it (sin(n*pi) with n integer is 0), and a row's facts are stated
    if not (isinstance(s, Symbol) and s == Symbol(s.name)):
        raise ValueError(f"{head.__name__} row {row}: the argument {s} "
                         "must be a plain Symbol")
