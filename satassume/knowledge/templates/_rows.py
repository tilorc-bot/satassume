"""Template rules written as SymPy booleans (#249).

A *row* is ``premises >> conclusion`` over the plain symbol :data:`x` and
the node ``f(x)``, with :data:`f` the generic function::

    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))

The premises are a conjunction of literals; the conclusion is a literal, a
disjunction of literals, ``Equivalent`` of two literals (a rule each way),
or a conjunction of those (one rule each).  A literal is ``Q.p(t)`` or
``~Q.p(t)`` with ``p`` in ``VOCAB`` and ``t`` the argument or the node, or
an inequality between the argument and a real number, ``Q.gt(x, 1)``,
``Q.le(x, -1)``, ``Q.eq(x, 1)``, ``Q.ne(x, 1)``, ``Q.ge(x, -1/E)`` and the
like, or its negation.  Inequalities are over the extended reals
(``Q.gt(x, 1)`` holds at ``x = oo``, ``~Q.gt(x, 1)`` at ``x = I``).  A
fact about the term ``x - c`` that is not about its sign is written on
the term: ``Q.even(x - S.Half)``; one about its sign is the inequality.
A row without premises is its conclusion alone::

    Q.extended_real(x) >> Equivalent(Q.zero(f(x)), Q.zero(x))
    (Q.positive(x) & Q.lt(x, 1)) >> Q.positive(f(x))
    (Q.even(x - S.Half) & Q.negative(x) & ~Q.integer(x)) >> Q.positive(f(x))
    Equivalent(Q.zero(f(x)), Q.zero(x))
    Q.extended_nonnegative(f(x))

A row about a function of several arguments has the node ``f(x, y)`` (or
more plain symbols, in the order of the arguments), and literals about the
node and its arguments, inequalities included.  A function can have rows
of several numbers of arguments: a node gets the rows of its number::

    (Q.finite(x) & Q.positive(y)) >> Q.complex(f(x, y))
    (Q.real(x) & Q.positive(y) & Q.lt(y, 1)) >> Q.positive(f(x, y))

A family module states its rules as one tuple, ``RULES``, of
:func:`for_all` statements: the functions, and the rows that hold for each
of them, ``f`` standing for the function.  ``closed(f, P)`` is the row
``P(x) >> P(f(x))``; ``a & b`` joins rows, ``cond >> (a & b)`` adds
``cond`` to the premises of each.  The module holds rows only:
:mod:`.wiring` compiles them (:func:`rules`) into the index specs of
:mod:`._common` (the arguments from 0, then the node: argument 0 and
node 1 for one argument, then the terms ``x - c`` for the ``c`` the
inequalities compare an argument with, as facts about ``x - c``
(``Q.gt(x, c)`` is ``extended_positive(x - c)``, ``Q.eq(x, c)`` is
``zero(x - c)``), and the terms the rows write; by argument, then by
``|c|`` and ``x - c`` first: ``x - 1/2``, ``x + 1/2``, ``x - 1``,
``x + 1``, ``x - 2``, ...) and registers the templates, so the patterns, their cache
and the engine are unchanged.

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
is a conjunction is rejected, and a set with a condition refuses ``&``, so
both missing pairs of parentheses fail at import.
"""
from __future__ import annotations

from typing import NamedTuple

from sympy import (
    Add, And, Equivalent, Expr, Float, Function, I, Implies, Not, Or, S, Symbol, nan, oo, zoo,
)
from sympy.assumptions.assume import AppliedPredicate

from ._common import VOCAB, Rules

#: the argument of every row
x = Symbol('x')
#: the second argument of a row about a function of two arguments
y = Symbol('y')
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
        return _Conditioned(Implies(cond & r.args[0], r.args[1]) if isinstance(r, Implies)
                            else Implies(cond, r) for r in self.rows)

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
    # a row without premises is a literal, a disjunction of literals or
    # Equivalent; a conjunction is what a & b >> c parses to
    if not (isinstance(r, (Implies, Equivalent))
            or all(_literal(a) for a in (r.args if isinstance(r, Or) else (r,)))):
        raise TypeError(f"row {r} is not an implication "
                        "(parenthesize both sides: >> binds tighter than &)")
    return r


def _literal(e):
    return isinstance(e.args[0] if isinstance(e, Not) else e, AppliedPredicate)


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
    for the function.  Each row must mention ``f``.  A function this SymPy
    lacks is given as ``None`` (``owens_t`` before SymPy 1.15) and left out."""
    functions = tuple(functions)
    flat = tuple(_flat(rows))
    if not functions:
        raise ValueError("for_all of no function")
    functions = tuple(fn for fn in functions if fn is not None)
    for r in flat:
        if not r.has(f):
            raise ValueError(f"row {r} of for_all{functions} does not mention f")
    return ForAll(functions, flat)


def by_function(statements):
    """``((function, rows), ...)`` from :func:`for_all` statements, in the
    order the functions first appear; in each row ``f(x)`` is the function's
    node (:func:`bind`)."""
    out = {}
    for st in statements:
        if not isinstance(st, ForAll):
            raise TypeError(f"{st} is not a for_all statement")
        for fn in st.functions:
            out.setdefault(fn, []).extend(bind(r, fn) for r in st.rows)
    return tuple((fn, tuple(rs)) for fn, rs in out.items())


def bind(row, fn):
    """``row`` with :data:`f` standing for ``fn``: ``f(x)`` is ``fn(x)``,
    unevaluated (a base class has no value: ``RoundFunction(x)`` raises).
    ``f`` of anything but symbols is left, and refused by :func:`rules`."""
    return row.xreplace({a: _node(fn, a.args) for a in row.atoms(f)
                         if all(isinstance(s, Symbol) for s in a.args)})


def _node(fn, args):
    try:
        return fn(*args, evaluate=False)
    except TypeError:
        # betainc_regularized.__new__ takes no keyword: of plain symbols it
        # is not evaluated (and :func:`_term` refuses a rewritten node)
        return fn(*args)


def rules(head, table, module: str):
    """The ``gen(R, c)`` of :func:`.functions._unary` for the rows of
    ``table`` about ``head``: :func:`generator` of :func:`compile_rows`;
    ``module`` (the caller's ``__name__``) is the module the registry
    attributes the template to (``TemplateRegistry.lazy``)."""
    return generator(head.__name__, *compile_rows(head, table), module)


def compile_rows(head, table):
    """``(arity, terms, specs)``, plain data (``tools/compile_rows.py``
    writes it to ``_compiled_rows.py``): the number of arguments of the
    nodes the rows mention, or the tuple of the numbers for rows of
    several; for each number ``n``, ``(n, ((i, c), ...))``, the terms
    ``args[i] + c`` the rules of its rows use in the order of their slots
    ``n + 1``, ``n + 2``, ... (by ``i``, then by ``|c|``, ``x - c`` first),
    ``c`` an int or the text of an exact real number (:func:`_number_data`); and
    ``(n, rules)``, the rules ``(premises, conclusion)`` of its rows, tuples
    of literals ``(slot, pred, sign)``."""
    by_n = {}
    for row in rows_of(table):
        n, s = _specs(head, row)
        by_n.setdefault(n, []).extend(s)
    specs, terms = [], []
    for n, sp in sorted(by_n.items()):
        shifts = sorted({k for p, c in sp for k, _, _ in p + c if isinstance(k, tuple)},
                        key=lambda k: (k[1], abs(k[2]), k[2]))
        slot = {k: n + 1 + i for i, k in enumerate(shifts)}
        specs.append((n, tuple(tuple(tuple((slot.get(k, k), pred, pos) for k, pred, pos in lits)
                                     for lits in spec) for spec in sp)))
        terms.append((n, tuple((i, _number_data(c)) for _, i, c in shifts)))
    arities = tuple(n for n, _ in terms) or (1,)
    return (arities if len(arities) > 1 else arities[0]), tuple(terms), tuple(specs)


def _number_data(c):
    """The exact real number ``c`` as plain data: an int, or its text,
    which :func:`generator` turns back into ``c`` (``1/2``, ``exp(-1)``)."""
    if c.is_Integer:
        return int(c)
    text = str(c)
    if S(text) != c:
        raise ValueError(f"{c} is not rebuilt from its text {text!r}")
    return text


def generator(name: str, arity, terms: tuple, specs: tuple, module: str):
    """The ``gen(R, c)`` that adds the rules ``specs`` (:func:`compile_rows`);
    ``module`` is the module the registry attributes the template to
    (``TemplateRegistry.lazy``).  ``gen.arity``, ``gen.terms`` (``{n: ((i,
    c), ...)}``, ``c`` a SymPy number again) and ``gen.shifts`` (the ``c``
    of the rows of one argument) tell :func:`.wiring.template` the slots:
    for several numbers of arguments, ``gen(R, n)`` is
    :func:`.functions.nary`'s, and gives the rules of the rows of ``n``
    arguments."""
    terms = {n: tuple((i, S(c)) for i, c in ts) for n, ts in terms}
    specs = dict(specs)
    one = tuple(spec for sp in specs.values() for spec in sp)

    def gen(R: Rules, c) -> None:
        # c: the constant argument (functions._unary) or the number of
        # arguments (functions.nary), which picks the rows for several
        for prem, concl in specs.get(c, ()) if len(specs) > 1 else one:
            R.rule(list(prem), list(concl))
    gen.__module__ = module
    gen.__name__ = gen.__qualname__ = f'{name}_rows'
    gen.arity = arity
    gen.terms = terms
    gen.shifts = tuple(c for _, c in terms.get(1, ()))
    return gen


def _specs(head, row):
    """``(n, specs)``: the number of arguments of the node, and the rules of
    ``row`` over the slots of :func:`_slots`."""
    _row(row)
    prem, concl = row.args if isinstance(row, Implies) else (True, row)
    premises = [_lit(head, row, t) for t in _conjuncts(prem) if t is not True]
    out = []
    for c in _conjuncts(concl):
        if isinstance(c, Equivalent):
            if len(c.args) != 2:
                raise ValueError(f"{head.__name__} row {row}: {c} is not of two literals")
            a, b = (_lit(head, row, t) for t in c.args)
            out += [(premises + [a], [b]), (premises + [b], [a])]
        else:
            out.append((premises, [_lit(head, row, t)
                                   for t in (c.args if isinstance(c, Or) else (c,))]))
    n, slot = _slots(head, row, {t for p, c in out for t, _, _ in p + c})
    return n, [tuple([(slot[t], pred, pos) for t, pred, pos in lits] for lits in spec)
               for spec in out]


def _conjuncts(e):
    return e.args if isinstance(e, And) else (e,)


#: an inequality between the argument and a real number ``c``: the fact
#: about ``x - c`` it is (order relations are over the extended reals), and the
#: relation with its sides swapped
_RELATIONS = (('gt', 'extended_positive', True, 'lt'), ('lt', 'extended_negative', True, 'gt'),
              ('ge', 'extended_nonnegative', True, 'le'),
              ('le', 'extended_nonpositive', True, 'ge'),
              ('eq', 'zero', True, 'eq'), ('ne', 'zero', False, 'ne'))

#: the facts about a term ``x - c`` that an inequality states: written on
#: the term they are refused (``extended_`` of them too)
_SIGN = ('positive', 'negative', 'nonnegative', 'nonpositive', 'nonzero', 'zero')


def _lit(head, row, e):
    """``(term, pred, positive)`` of the literal ``e``; the term of an
    inequality is ``(('shift', -c), x)`` for ``x - c`` (:func:`_relation`),
    and so is a written term ``x - c`` (:func:`_shift`)."""
    pos = not isinstance(e, Not)
    a = e if pos else e.args[0]
    if not isinstance(a, AppliedPredicate):
        raise ValueError(f"{head.__name__} row {row}: {e} is not a literal")
    pred = str(a.function.name)
    if any(pred == r[0] for r in _RELATIONS) and len(a.arguments) == 2:
        return _relation(head, row, pred, a.arguments, pos)
    if len(a.arguments) != 1:
        raise ValueError(f"{head.__name__} row {row}: {e} is not a literal")
    if pred not in VOCAB:
        raise ValueError(f"{head.__name__} row {row}: {pred} is not a template predicate")
    t = a.arguments[0]
    if isinstance(t, Add):
        return (_shift(head, row, t, pred), pred, pos)
    return (t, pred, pos)


def _shift(head, row, t, pred):
    """The slot ``(('shift', k), x)`` of a written term ``t == x + k`` for an
    exact real ``k``, about which ``pred`` is not a fact an inequality states."""
    k, s = t.as_independent(*t.free_symbols, as_Add=True)
    if not (isinstance(s, Symbol) and k != 0 and _number(k)):
        raise ValueError(f"{head.__name__} row {row}: {t} is neither the argument nor "
                         f"{head.__name__} of it, nor the argument plus a number")
    if pred.removeprefix('extended_') in _SIGN:
        raise ValueError(f"{head.__name__} row {row}: {pred}({t}) is an inequality: "
                         "compare the argument with Q.gt(x, 1) and the like")
    _plain(head, row, s)
    return (('shift', k), s)


def _number(c):
    """Whether ``c`` is an exact real number: no float, I or infinity."""
    return (isinstance(c, Expr) and c.is_number
            and not c.has(Float, I, oo, -oo, zoo, nan))


def _relation(head, row, rel, args, pos):
    """``Q.gt(x, c)`` and the like, for an exact real number ``c`` (an
    integer, or a constant like ``1/2`` or ``-1/E``): a fact about the term ``x - c`` (slot
    ``('shift', -c)`` until :func:`rules` numbers the shifts; the argument
    itself for ``c == 0``)."""
    of = {r[0]: r[1:] for r in _RELATIONS}
    s, c = args
    if not isinstance(s, Symbol):
        rel, s, c = of[rel][2], c, s
    if not (isinstance(s, Symbol) and _number(c)):
        raise ValueError(f"{head.__name__} row {row}: Q.{rel}{args} does not compare "
                         "an argument with a number")
    pred, sign, _ = of[rel]
    _plain(head, row, s)
    return ((('shift', -c), s) if c else s, pred, pos is sign)


def _slots(head, row, terms):
    """``(n, slot)``: the slot of each term of a row about the node ``head(x0,
    ..., x_{n-1})``: argument ``i`` is slot ``i``, the node ``n``, and a
    term ``x_i - c`` is ``('shift', i, -c)`` until :func:`rules` numbers
    it."""
    kinds = {t: _term(head, row, t) for t in terms}
    nodes = [t for t, k in kinds.items() if k == 'node']
    if not nodes:
        raise ValueError(f"{head.__name__} row {row} does not mention the node")
    if len(nodes) > 1:
        raise ValueError(f"{head.__name__} row {row} mentions more than one node")
    [node] = nodes
    args = node.args
    if len(set(args)) != len(args):
        raise ValueError(f"{head.__name__} row {row}: the arguments of {node} are not distinct")
    slot = {a: i for i, a in enumerate(args)}
    slot[node] = len(args)
    for t, k in kinds.items():
        if k == 'node':
            continue
        s = t if k == 'argument' else t[1]
        if s not in args:
            raise ValueError(f"{head.__name__} row {row} mentions more than one argument: "
                             f"{s} is not an argument of {node}")
        if k == 'shift':
            slot[t] = ('shift', args.index(s), t[0][1])
    return len(args), slot


def _term(head, row, t):
    """``'node'``, ``'argument'`` or ``'shift'`` (``x - c``, from an
    inequality or written)."""
    if isinstance(t, tuple):
        return 'shift'
    if type(t) is head:
        for a in t.args:
            _plain(head, row, a)
        return 'node'
    if isinstance(t, Symbol):
        _plain(head, row, t)
        return 'argument'
    # a constructor that rewrote the written term (cos(x + pi/2) is -sin(x)),
    # or a term of the argument other than x + c
    raise ValueError(f"{head.__name__} row {row}: {t} is neither the argument nor "
                     f"{head.__name__} of it")


def _plain(head, row, s):
    # a symbol with assumptions would make SymPy rewrite the terms built
    # from it (sin(n*pi) with n integer is 0), and a row's facts are stated
    if not (isinstance(s, Symbol) and s == Symbol(s.name)):
        raise ValueError(f"{head.__name__} row {row}: the argument {s} "
                         "must be a plain Symbol")
    return s
