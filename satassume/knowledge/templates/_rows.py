"""Template rules written as SymPy booleans (#249).

A *row* is ``premises >> conclusion`` over the plain symbol :data:`x` and
the node ``f(x)``, with :data:`f` the generic function::

    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))

The premises are a conjunction of literals; the conclusion is a literal, a
disjunction of literals, or a conjunction of those (one rule each).  A
literal is ``Q.p(t)`` or ``~Q.p(t)`` with ``p`` in ``VOCAB`` and ``t`` the
argument or the node.

A family module states its rules as one tuple, ``RULES``, of
:func:`for_all` statements: the functions, and the rows that hold for each
of them, ``f`` standing for the function.  ``closed(f, P)`` is the row
``P(x) >> P(f(x))``; ``a & b`` joins rows, ``cond >> (a & b)`` adds
``cond`` to the premises of each.  The module holds rows only:
:mod:`.wiring` compiles them (:func:`rules`) into the index specs of
:mod:`._common` (argument 0, node 1) and registers the templates, so the
patterns, their cache and the engine are unchanged.

Layout: above each statement a comment line with the property's title
(``tools/show_rows.py`` prints it as the label), and under it, indented,
any explanation; then ``for_all((sin, cos),`` on one line and the rows
indented on the next, a longer row continued on more lines::

    RULES = (
        # Entire
        #     no poles: finite at every finite point
        for_all((sin, cos),
            closed(f, Q.finite) & closed(f, Q.complex)),
    )

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``, and ``c >> s & t`` is ``(c >> s) & t``.  A row whose top
is not an implication is rejected, and a set with a condition refuses
``&``, so both missing pairs of parentheses fail at import.
"""
from __future__ import annotations

from typing import NamedTuple

from sympy import And, Function, Implies, Not, Or, Symbol
from sympy.assumptions.assume import AppliedPredicate

from ._common import VOCAB, Rules

X, N = 0, 1

#: the argument of every row
x = Symbol('x')
#: the generic function: in a :func:`for_all` statement, each of its functions
f = Function('f')


class Rows:
    """A set of rows: ``a & b`` joins, ``cond >> rows`` adds a premise to
    each row."""
    __slots__ = ('rows',)

    def __init__(self, rows=()):
        self.rows = tuple(_row(r) for r in rows)

    def __and__(self, other) -> 'Rows':
        return Rows(self.rows + tuple(_flat(other)))

    def __rand__(self, other) -> 'Rows':
        return Rows(tuple(_flat(other)) + self.rows)

    def __rrshift__(self, cond) -> 'Rows':
        return _Conditioned(Implies(cond & r.args[0], r.args[1]) for r in self.rows)

    def __iter__(self):
        return iter(self.rows)


class _Conditioned(Rows):
    """``cond >> rows``: joining it with ``&`` is what ``cond >> a & b``
    parses to, so it is refused."""
    __slots__ = ()

    def __and__(self, other):
        raise TypeError("cond >> a & b is (cond >> a) & b: write cond >> (a & b), "
                        "or give the rows with a condition as their own row of the for_all")

    __rand__ = __and__


def _row(r):
    if not isinstance(r, Implies):
        raise TypeError(f"row {r} is not an implication "
                        "(parenthesize both sides: >> binds tighter than &)")
    return r


def _flat(item):
    """The rows of a row, a :class:`Rows` or a tuple of those."""
    if isinstance(item, (Rows, tuple, list)):
        for i in item:
            yield from _flat(i)
    else:
        yield _row(item)


def closed(f, pred) -> Rows:
    """``f`` maps the set ``pred`` into itself: ``pred(x) -> pred(f(x))``."""
    return Rows([pred(x) >> pred(f(x))])


def rows_of(table):
    """The rows of ``table``: a row, a :class:`Rows` or a tuple of those."""
    return list(_flat(table))


class ForAll(NamedTuple):
    """A :func:`for_all` statement."""
    functions: tuple
    rows: tuple


def for_all(functions, *rows) -> ForAll:
    """The ``rows`` hold for each of ``functions``, with :data:`f` standing
    for the function.  Each row must mention ``f``."""
    functions = tuple(functions)
    flat = tuple(_flat(rows))
    if not functions:
        raise ValueError("for_all of no function")
    for r in flat:
        if not r.has(f):
            raise ValueError(f"row {r} of for_all{functions} does not mention f")
    return ForAll(functions, flat)


def by_function(statements):
    """``((function, rows), ...)`` from :func:`for_all` statements, in the
    order the functions first appear; in each row ``f(x)`` is the function's
    node."""
    out = {}
    for st in statements:
        if not isinstance(st, ForAll):
            raise TypeError(f"{st} is not a for_all statement")
        for fn in st.functions:
            out.setdefault(fn, []).extend(r.xreplace({f(x): fn(x)}) for r in st.rows)
    return tuple((fn, tuple(rs)) for fn, rs in out.items())


def rules(head, table, module: str):
    """The ``gen(R, c)`` of :func:`.functions._unary` for the rows of
    ``table`` about ``head``; ``module`` (the caller's ``__name__``) is the
    module the registry attributes the template to (``TemplateRegistry.lazy``)."""
    specs = [spec for row in rows_of(table) for spec in _specs(head, row)]

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
