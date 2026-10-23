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

An argument of the node can have a *shape*, and the row is then about the
nodes of that shape: an exact number, a function of a plain symbol (whose
argument is a term of its own), a repeated symbol, or the constant
variable :data:`number`, which stands for an argument that is a constant
(an atomic number)::

    Q.positive(base) >> Q.positive(f(base, -1))
    Q.real(exponent) >> Q.positive(f(E, exponent))
    (Q.imaginary(log_base) & Q.imaginary(exponent)) >> Q.positive(f(exp(log_base), exponent))
    Q.extended_nonnegative(base) >> Q.extended_positive(f(base, base))
    (Q.integer(number) & Q.ge(Abs(number), 2) & Q.negative(exponent)) >> ~Q.integer(
        f(number, exponent))

A literal about the constant variable is one about its argument; one
about a term of it (``k*number`` for a rational ``k``, ``1/number``,
``Abs(number)``, or the inequalities ``Q.gt(Abs(number), 1)``,
``Q.ge(number, 2)`` and the like) is decided where the row is used, from
the term computed at the constant, when the constant is a SymPy
``Number``; at another constant (``pi``, ``I``) the row is left out.  A
row has one constant variable at most.  The term ``k*x`` of an argument,
for a rational ``k``, is written like ``x - c``, for facts not about its
sign::

    (Q.extended_real(base) & Q.rational(number) & Q.integer(2*number)
     & ~Q.integer(number)) >> ~Q.extended_negative(f(base, number))
    (Q.extended_real(base) & Q.rational(exponent) & ~Q.integer(2*exponent)) >> ~Q.imaginary(
        f(base, exponent))

``Q.eq(f(base, 1), base)`` says the node has the value of the argument:
it is ``Equivalent(P(f(base, 1)), P(base))`` for each predicate ``P`` of
:data:`VALUE_PREDICATES` (all but ``commutative``, a property of the
expression and not of its value).

A family module states its rules as one tuple, ``RULES``, of
:func:`for_all` statements: the functions, and the rows that hold for each
of them, ``f`` standing for the function.  ``closed(f, P)`` is the row
``P(argument) >> P(f(argument))``; ``a & b`` joins rows, ``cond >> (a & b)``
adds ``cond`` to the premises of each.  The module holds rows only:
:mod:`.wiring` compiles them (:func:`rules`) into the index specs of
:mod:`._common` (the arguments from 0, then the node: argument 0 and
node 1 for one argument, then the terms ``x - c`` for the ``c`` the
inequalities compare an argument with, as facts about ``x - c``
(``Q.gt(x, c)`` is ``extended_positive(x - c)``, ``Q.eq(x, c)`` is
``zero(x - c)``), and the terms the rows write; by argument, then by
``|c|`` and ``x - c`` first: ``x - 1/2``, ``x + 1/2``, ``x - 1``,
``x + 1``, ``x - 2``, ...; then the other terms, :func:`compile_rows`)
and registers the templates, so the patterns, their cache and the engine
are unchanged.

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

A function of any number of arguments (:data:`ANY_ARITY`: a sum, a
product, ``Max``, ``Min`` and the values of a ``Piecewise``) has rows with
a *star*.  :data:`terms`, :data:`factors` and :data:`values` are the
arguments: ``f(*factors)`` is a node of any number of arguments, all of
them ``factors``; ``f(factor, *factors)`` picks one argument, at any
position, and ``factors`` are the others; ``f(factor, other, *factors)``
picks two.  ``every(P, factors)`` is ``P`` of each of them (true of none),
``some(P, factors)`` ``P`` of one of them (false of none), and
``count(factors)`` their number::

    (Q.extended_negative(factor) & every(Q.extended_positive, factors))
        >> Q.extended_negative(f(factor, *factors))
    (some(Q.zero, factors) & every(Q.finite, factors)) >> Q.zero(f(*factors))
    (every(Q.extended_negative, factors) & Q.even(count(factors)))
        >> Q.extended_positive(f(*factors))

A picked :data:`number` is a constant argument at any position, and
:data:`coefficient` is argument 0 when it is a SymPy ``Number`` (a
product's numeric coefficient: rational, float, infinite; not ``pi``).
A row without a star is about nodes of exactly its number of arguments,
in that order: ``Q.positive(coefficient) >> Q.positive(f(coefficient,
factor))``.  ``for_all((Mul,), row, at_most=6)`` leaves the row out for a
node of more than 6 arguments, a limit on the cost.  ``every`` is a
premise; ``some`` in a premise, in a row without a picked argument, is one
rule per argument (where its literal implies an ``every`` literal, that
literal is left out on the argument), and in a conclusion a disjunction.
Picked arguments of the same kind with the same literals are
interchangeable: one rule per set of positions, not per order.

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``, and ``c >> s & t`` is ``(c >> s) & t``.  A row whose top
is a conjunction is rejected, and a set with a condition refuses ``&``, so
both missing pairs of parentheses fail at import.
"""
from __future__ import annotations

import functools
from types import MappingProxyType
from typing import NamedTuple

from sympy import (
    Abs, Add, And, Equivalent, Expr, Float, Function, I, Implies, Mul, Not, Or, Symbol, nan, oo,
    zoo,
)
from sympy.assumptions.assume import AppliedPredicate

from ._common import VOCAB
# constant_value: the template's, also for the tests of the rows
from ._rows_runtime import _TEXT_NAMES as _NUMBER_NAMES, constant_value, generator  # noqa: F401
from ._rows_runtime import from_text as _from_text


class Constant(Symbol):
    """A constant variable: in a row, an argument that is a constant (an
    atomic number) where the row is used.  A :class:`~sympy.Symbol`, so its
    terms (``2*number``, ``Abs(number)``) stay unevaluated, and told apart
    from a plain symbol by its class."""
    __slots__ = ()


#: plain symbols for rows written outside the family modules (the tests):
#: ``x``, and ``y`` for a second argument
x = Symbol('x')
y = Symbol('y')
#: the arguments of the families' rows, named by their role (#299): the
#: argument of a function of one argument, and the one a function of several
#: is a function of (:func:`closed` states its rows on it)
argument = Symbol('argument')
#: the arguments of ``Mod(dividend, divisor)``
dividend = Symbol('dividend')
divisor = Symbol('divisor')
#: the period of ``principal_branch(argument, period)`` (SymPy's name)
period = Symbol('period')
#: the branch of ``LambertW(argument, branch)``
branch = Symbol('branch')
#: the order of ``besselj(order, argument)``, ``polygamma``, ``polylog``
#: and ``expint``
order = Symbol('order')
#: the parameter of Hurwitz's ``zeta(argument, parameter)`` and of
#: ``lowergamma(parameter, argument)``
parameter = Symbol('parameter')
#: the limits of an integral: ``erf2(lower, upper)``, ``betainc(first,
#: second, lower, upper)``, and the upper one of ``owens_t(argument, upper)``
lower = Symbol('lower')
upper = Symbol('upper')
#: the two arguments of ``beta(first, second)``, and the first two of
#: ``betainc(first, second, lower, upper)``
first = Symbol('first')
second = Symbol('second')
#: ``RisingFactorial(start, size)`` and ``FallingFactorial(start, size)``,
#: products of ``size`` factors from start, and ``binomial(total, size)``
start = Symbol('start')
size = Symbol('size')
total = Symbol('total')
#: the base and the exponent of a power, and the ``u`` of a base ``exp(u)``
base = Symbol('base')
exponent = Symbol('exponent')
log_base = Symbol('log_base')
#: the constant variable: ``f(number, exponent)`` is a power of a constant
number = Constant('number')
#: the generic function: in a :func:`for_all` statement, each of its functions
f = Function('f')


class Arguments(Symbol):
    """The arguments of a node of any number of arguments, or the others
    than the picked ones: ``f(factor, *factors)``.  Unpacking it gives
    itself, so that node is ``f(factor, factors)``."""
    __slots__ = ()

    def __iter__(self):
        yield self


#: the functions of any number of arguments, whose rows may have a star
ANY_ARITY = frozenset({'Add', 'Mul', 'Max', 'Min', 'Piecewise'})
#: the terms of a sum, the factors of a product, the values of Max, Min
#: and Piecewise
terms = Arguments('terms')
factors = Arguments('factors')
values = Arguments('values')
#: picked arguments of a row with a star
term = Symbol('term')
factor = Symbol('factor')
value = Symbol('value')
other = Symbol('other')
third = Symbol('third')
#: the second constant variable: argument 0 when it is a SymPy ``Number``,
#: the coefficient of a product
coefficient = Constant('coefficient')

@functools.cache
def _over():
    """What ``every``, ``some`` and ``count`` write, ``every(factors)``, by
    the name of its function: made when a row is first written (a family
    module, ``tools/compile_rows.py``), not when a query loads the compiled
    rows (a SymPy function costs a fraction of a millisecond to make)."""
    return MappingProxyType({Function(name): name for name in ('every', 'some', 'count')})


def _function(name):
    [fn] = [fn for fn, n in _over().items() if n == name]
    return fn


def every(pred, xs):
    """``pred`` (or ``~pred``) of each argument of ``xs``, a premise:
    ``every(Q.even, terms)``, ``every(~Q.zero, factors)``; true of none."""
    return _applied(pred, _function('every')(xs))


def some(pred, xs):
    """``pred`` (or ``~pred``) of one argument of ``xs``: ``some(Q.zero,
    factors)``; false of none."""
    return _applied(pred, _function('some')(xs))


def count(xs):
    """The number of arguments of ``xs``: ``Q.even(count(factors))``."""
    return _function('count')(xs)


def _applied(pred, t):
    if isinstance(pred, Not):
        return Not(pred.args[0](t))
    return pred(t)


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
    if isinstance(item, AtMost):
        yield item
    elif isinstance(item, (Rows, tuple, list)):
        for i in item:
            yield from _flat(i)
    else:
        yield _row(item)


def closed(f, pred) -> Rows:
    """``f`` maps the set ``pred`` into itself: ``pred(argument) ->
    pred(f(argument))``."""
    return Rows([pred(argument) >> pred(f(argument))])


def rows_of(table):
    """The rows of ``table``: a row, a :class:`Rows` or a tuple of those."""
    return list(_flat(table))


class ForAll(NamedTuple):
    """A :func:`for_all` statement."""
    functions: tuple
    rows: tuple


class AtMost(NamedTuple):
    """A row with a star for nodes of at most ``n`` arguments
    (``for_all(..., at_most=n)``)."""
    row: object
    n: int


def for_all(functions, *rows, at_most=None) -> ForAll:
    """The ``rows`` hold for each of ``functions``, with :data:`f` standing
    for the function.  Each row must mention ``f``.  A function this SymPy
    lacks is given as ``None`` (``owens_t`` before SymPy 1.15) and left out.
    With ``at_most``, rows with a star hold for nodes of at most that many
    arguments (:class:`AtMost`)."""
    functions = tuple(functions)
    flat = tuple(_flat(rows))
    if not functions:
        raise ValueError("for_all of no function")
    functions = tuple(fn for fn in functions if fn is not None)
    for r in flat:
        if not (r.row if isinstance(r, AtMost) else r).has(f):
            raise ValueError(f"row {r} of for_all{functions} does not mention f")
    if at_most is not None:
        if not (type(at_most) is int and at_most >= 1):
            raise ValueError(f"for_all{functions}: at_most={at_most!r} is not a positive int")
        for r in flat:
            if isinstance(r, AtMost) or not r.atoms(Arguments):
                raise ValueError(f"row {r} of for_all{functions}: at_most is for a row "
                                 "with a star, f(factor, *factors)")
        flat = tuple(AtMost(r, at_most) for r in flat)
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
    ``f`` of symbols, numbers and functions (the shapes, :func:`_shape`)
    is bound; ``f`` of anything else is left, and refused by :func:`rules`.
    A node with a star stays ``f(...)`` (``Add(terms, evaluate=False)`` is
    ``terms``): :func:`compile_rows` reads it as the node."""
    if isinstance(row, AtMost):
        return AtMost(bind(row.row, fn), row.n)
    return row.xreplace({a: _node(fn, a.args) for a in row.atoms(f)
                         if not any(isinstance(s, Arguments) for s in a.args)
                         and all(isinstance(s, (Symbol, Function)) or s.is_number
                                 for s in a.args)})


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
    several; for each number ``n``, ``(n, terms)``, the terms the rules of
    its rows use in the order of their slots ``n + 1``, ``n + 2``, ...; and
    ``(n, rules)``, the rules ``(premises, conclusion)`` of its rows, tuples
    of literals ``(slot, pred, sign)``, and ``(premises, conclusion,
    shape)`` for a row whose node has a shape (:func:`_shape`).

    A term is, in this order: ``(i, c)``, the term ``args[i] + c`` (by
    ``i``, then by ``|c|``, ``x - c`` first), ``c`` an int or the text of
    an exact real number (:func:`_number_data`); ``('inner', i)``, the
    argument ``u`` of the argument ``i == exp(u)`` of a shape ``('head',
    'exp')``; ``('times', i, k)``, the term ``k*args[i]`` for a rational
    ``k`` (an int or its text); ``('of_constant', i, text)``, a term of the
    constant variable, argument ``i``, as text (``'Abs(number) - 1'``,
    ``'2*number'``): the template computes it from the constant, when that
    is a SymPy ``Number``, and leaves out the rules about it otherwise.

    Rows with a star add a fourth element, their *schemas* (:func:`_schema`),
    in the order of the rows; the arity is then that of the rows without a
    star, ``()`` for none."""
    by_n, schemas = {}, []
    for row in rows_of(table):
        if isinstance(row, AtMost):
            schemas.append(_schema(head, row.row, row.n))
            continue
        if row.atoms(Arguments):
            schemas.append(_schema(head, row, None))
            continue
        n, s = _specs(head, row)
        by_n.setdefault(n, []).extend(s)
    specs, terms = [], []
    for n, sp in sorted(by_n.items()):
        order = sorted({k for spec in sp for k, _, _ in spec[0] + spec[1]
                        if isinstance(k, tuple)}, key=_term_order)
        slot = {k: n + 1 + i for i, k in enumerate(order)}
        specs.append((n, tuple(tuple(tuple((slot.get(k, k), pred, pos) for k, pred, pos in lits)
                                     for lits in spec[:2]) + tuple(spec[2:]) for spec in sp)))
        terms.append((n, tuple(_term_data(k) for k in order)))
    arities = tuple(n for n, _ in terms) or (() if schemas else (1,))
    return ((arities if len(arities) != 1 else arities[0]), tuple(terms), tuple(specs)
            ) + ((tuple(schemas),) if schemas else ())


#: the order of the kinds of terms in their slots
_KINDS = ('shift', 'inner', 'times', 'of_constant')


def _term_order(k):
    kind, i, *data = k
    if kind == 'shift':
        return (0, i, abs(data[0]), data[0])
    if kind == 'of_constant':
        return (3, i, str(data[0]))
    return (_KINDS.index(kind), i, *data)


def _term_data(k):
    """The slot ``k`` of :func:`_slots` as the plain data of :func:`compile_rows`."""
    kind, i, *data = k
    if kind == 'shift':
        return (i, _number_data(data[0]))
    if kind == 'inner':
        return ('inner', i)
    if kind == 'times':
        return ('times', i, _number_data(data[0]))
    return ('of_constant', i, _constant_text(data[0]))


def _number_data(c):
    """The exact real number ``c`` as plain data: an int, or its text,
    which :func:`generator` turns back into ``c`` (``1/2``, ``exp(-1)``)."""
    if c.is_Integer:
        return int(c)
    text = str(c)
    if from_text(text) != c:
        raise ValueError(f"{c} is not rebuilt from its text {text!r}")
    return text


def _constant_text(t):
    """A term of the constant variable as text, which :func:`constant_term`
    turns back into ``t``."""
    text = str(t)
    if constant_term(text) != t:
        raise ValueError(f"{t} is not rebuilt from its text {text!r}")
    return text


def constant_term(text):
    """The term of the constant variable whose text is ``text``
    (``'Abs(number) - 1'``): the template evaluates it at the constant
    ``c`` of a node as ``t.xreplace({number: c})``, for a ``c`` that is a
    SymPy ``Number`` only."""
    t = from_text(text)
    return t.xreplace({s: Constant(s.name) for s in t.free_symbols})


#: what the texts of :func:`compile_rows` name: the numbers and functions
#: of exact real numbers (``'1/2'``, ``'-1/E'``, ``'exp(-1)'``, ``'-I'``)
#: and the constant variables of the terms of a constant
#: (``'Abs(number) - 1'``)
_TEXT_NAMES = MappingProxyType({**_NUMBER_NAMES, 'number': number, 'coefficient': coefficient})


def from_text(text):
    """The SymPy expression of a text of :func:`compile_rows`
    (:func:`._rows_runtime.from_text`, which :func:`generator` reads the
    compiled rows with), its constant variables those of the rows."""
    return _from_text(text, _TEXT_NAMES)


def _specs(head, row):
    """``(n, specs)``: the number of arguments of the node, and the rules of
    ``row`` over the slots of :func:`_slots`, each with the shape of the
    node when it has one."""
    _row(row)
    constants = row.atoms(Constant)
    if len(constants) > 1:
        raise ValueError(f"{head.__name__} row {row}: more than one constant variable "
                         f"({', '.join(sorted(map(str, constants)))})")
    prem, concl = row.args if isinstance(row, Implies) else (True, row)
    premises = [_lit(head, row, t) for t in _conjuncts(prem) if t is not True]
    out = []
    for c in _conjuncts(concl):
        pairs = _value_equality(head, row, c)
        if pairs:
            for a, b in pairs:
                out += [(premises + [a], [b]), (premises + [b], [a])]
        elif isinstance(c, Equivalent):
            if len(c.args) != 2:
                raise ValueError(f"{head.__name__} row {row}: {c} is not of two literals")
            a, b = (_lit(head, row, t) for t in c.args)
            out += [(premises + [a], [b]), (premises + [b], [a])]
        else:
            out.append((premises, [_lit(head, row, t)
                                   for t in (c.args if isinstance(c, Or) else (c,))]))
    n, slot, shape = _slots(head, row, {t for p, c in out for t, _, _ in p + c})
    return n, [tuple([(slot[t], pred, pos) for t, pred, pos in lits] for lits in spec)
               + ((shape,) if shape else ()) for spec in out]


def _conjuncts(e):
    return e.args if isinstance(e, And) else (e,)


#: the predicates of a value: ``Q.eq(f(base, 1), base)`` is the
#: equivalence of each of them about the node and the argument
#: (``commutative`` is a property of the expression, not of its value)
VALUE_PREDICATES = tuple(sorted(VOCAB - {'commutative'}))


def _value_equality(head, row, c):
    """For ``Q.eq(node, a)`` (or ``Q.eq(a, node)``) with ``a`` an argument:
    the pairs of literals ``P(node)``, ``P(a)`` of :data:`VALUE_PREDICATES`;
    else ``()``."""
    if not (isinstance(c, AppliedPredicate) and str(c.function.name) == 'eq'
            and len(c.arguments) == 2):
        return ()
    nodes = [s for s in c.arguments if type(s) is head]
    if len(nodes) != 1:
        return ()
    [node] = nodes
    [a] = [s for s in c.arguments if s is not node]
    if not isinstance(a, Symbol):
        raise ValueError(f"{head.__name__} row {row}: {c} does not equate the node "
                         "with an argument")
    return [((node, p, True), (a, p, True)) for p in VALUE_PREDICATES]


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
    and so is a written term ``x - c`` (:func:`_shift`); a written term
    ``k*x`` is ``(('times', k), x)`` (:func:`_times`), and a term ``t`` of
    the constant variable ``number`` is ``(('of_constant', t), number)``
    (:func:`_of_constant`)."""
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
    if _of_constant_only(t) and not isinstance(t, Constant):
        return (_of_constant(head, row, t, pred), pred, pos)
    if type(t) is head:
        # the node of a sum or a product: not a term x + c or k*x
        return (t, pred, pos)
    if isinstance(t, Add):
        return (_shift(head, row, t, pred), pred, pos)
    if isinstance(t, Mul):
        return (_times(head, row, t, pred), pred, pos)
    return (t, pred, pos)


def _of_constant_only(t):
    fs = t.free_symbols
    return bool(fs) and all(isinstance(s, Constant) for s in fs)


def _of_constant(head, row, t, pred):
    """The slot ``(('of_constant', t), number)`` of a written term ``t`` of
    the constant variable: ``k*number`` for a rational ``k``, ``1/number`` or
    ``Abs(number)``, about which ``pred`` is not a fact about a sign.  A
    term of the constant alone is never the node: ``1/number`` is not
    ``Pow(number, -1)``, the node of a row has an argument that is a plain
    symbol or a function of one."""
    [c] = t.free_symbols
    if type(t) is head and t != 1/c and head.__name__ not in ANY_ARITY:
        # 1/number is a term of the constant also for a head Pow, and
        # 2*coefficient for a head Mul (f(2, coefficient) is the same Mul)
        raise ValueError(f"{head.__name__} row {row}: the node {t} has no argument but the "
                         "constant variable and numbers")
    k, rest = t.as_coeff_Mul()
    if not (t == 1/c or t == Abs(c) or (rest == c and k.is_Rational and k != 1)):
        raise ValueError(f"{head.__name__} row {row}: {t} is not a term of the constant "
                         f"variable: k*{c} for a rational k, 1/{c} or Abs({c})")
    if pred.removeprefix('extended_') in _SIGN:
        raise ValueError(f"{head.__name__} row {row}: {pred}({t}) is a fact about a sign: "
                         f"compare {c} or Abs({c}) with a number, Q.gt(Abs({c}), 1)")
    return (('of_constant', t), c)


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


def _times(head, row, t, pred):
    """The slot ``(('times', k), x)`` of a written term ``t == k*x`` for a
    rational ``k``, about which ``pred`` is not a fact about a sign."""
    k, s = t.as_coeff_Mul()
    if not (isinstance(s, Symbol) and k.is_Rational and k != 1):
        raise ValueError(f"{head.__name__} row {row}: {t} is neither the argument nor "
                         f"{head.__name__} of it, nor the argument times a rational")
    if pred.removeprefix('extended_') in _SIGN:
        raise ValueError(f"{head.__name__} row {row}: {pred}({t}) is a fact about the sign "
                         f"of {s}: state it on the argument")
    _plain(head, row, s)
    return (('times', k), s)


def _number(c):
    """Whether ``c`` is an exact real number: no float, I or infinity."""
    return (isinstance(c, Expr) and c.is_number
            and not c.has(Float, I, oo, -oo, zoo, nan))


def _compared(s):
    """Whether an inequality can compare ``s`` with a number: an argument,
    or ``Abs`` of the constant variable."""
    return isinstance(s, Symbol) or (isinstance(s, Abs) and isinstance(s.args[0], Constant))


def _relation(head, row, rel, args, pos):
    """``Q.gt(x, c)`` and the like, for an exact real number ``c`` (an
    integer, or a constant like ``1/2`` or ``-1/E``): a fact about the term ``x - c`` (slot
    ``('shift', -c)`` until :func:`rules` numbers the shifts; the argument
    itself for ``c == 0``).  For the constant variable, or ``Abs`` of it,
    the term is a term of the constant, ``Abs(number) - 1``."""
    of = {r[0]: r[1:] for r in _RELATIONS}
    s, c = args
    if not _compared(s):
        rel, s, c = of[rel][2], c, s
    if not (_compared(s) and _number(c)):
        raise ValueError(f"{head.__name__} row {row}: Q.{rel}{args} does not compare "
                         "an argument with a number")
    pred, sign, _ = of[rel]
    if isinstance(s, Constant) and not c:
        return (s, pred, pos is sign)
    if _of_constant_only(s):
        [k] = s.free_symbols
        return ((('of_constant', s - c), k), pred, pos is sign)
    _plain(head, row, s)
    return ((('shift', -c), s) if c else s, pred, pos is sign)


def _slots(head, row, terms):
    """``(n, slot, shape)``: the slot of each term of a row about the node
    ``head(a_0, ..., a_{n-1})``, and the shape of the node (:func:`_shape`):
    argument ``i`` is slot ``i`` (a repeated symbol its first), the node
    ``n``, and a term ``a_i - c`` is ``('shift', i, -c)``, ``k*a_i``
    ``('times', i, k)``, the ``u`` of an argument ``exp(u)`` ``('inner',
    i)`` and a term ``t`` of the constant variable ``('of_constant', i,
    t)`` until :func:`compile_rows` numbers them."""
    kinds = {t: _term(head, row, t) for t in terms}
    nodes = [t for t, k in kinds.items() if k == 'node']
    if not nodes:
        raise ValueError(f"{head.__name__} row {row} does not mention the node")
    if len(nodes) > 1:
        raise ValueError(f"{head.__name__} row {row} mentions more than one node")
    [node] = nodes
    args = node.args
    shape = _shape(head, row, node)
    slot = {}
    for i, a in enumerate(args):
        slot.setdefault(a, i)
    slot[node] = len(args)
    inner = {a.args[0]: i for i, (a, s) in enumerate(zip(args, shape or ()))
             if s is not None and s[0] == 'head'}
    for t, k in kinds.items():
        if k == 'node' or t in slot:
            continue
        if k == 'argument':
            if t in inner:
                slot[t] = ('inner', inner[t])
                continue
            if isinstance(t, Symbol):
                _not_an_argument(head, row, node, t)
            raise ValueError(f"{head.__name__} row {row}: {t} is neither the argument nor "
                             f"{head.__name__} of it")
        (kind, data), s = t
        if s not in args:
            _not_an_argument(head, row, node, s)
        slot[t] = (kind, args.index(s), data)
    return len(args), slot, shape


def _not_an_argument(head, row, node, s):
    if isinstance(s, Constant):
        raise ValueError(f"{head.__name__} row {row}: the constant variable {s} is not an "
                         f"argument of {node}")
    raise ValueError(f"{head.__name__} row {row} mentions more than one argument: "
                     f"{s} is not an argument of {node}")


def _shape(head, row, node):
    """The shape of ``node``: for each argument ``None`` (a plain symbol),
    ``('same', j)`` (the plain symbol of argument ``j``), ``('value', v)``
    (the exact number ``v``, an int or its text: ``-1``, ``'E'``,
    ``'-I'``), ``('head', name)`` (the function ``name`` of a plain
    symbol, ``exp(log_base)``) or ``('constant',)`` (the constant variable,
    for a constant argument); ``None`` when every argument is a distinct
    plain symbol."""
    # seen: the argument of each plain symbol, None for the constant
    # variable and the symbol of a function, which are not repeated
    out, seen = [], {}
    for i, a in enumerate(node.args):
        if isinstance(a, Constant) or isinstance(a, Function):
            s = a if isinstance(a, Constant) else _inner(head, row, node, a)
            if s in seen:
                _not_distinct(head, row, node)
            seen[s] = None
            out.append(_constant_shape(head, row, node, i, a) if s is a
                       else ('head', type(a).__name__))
        elif isinstance(a, Symbol):
            _plain(head, row, a)
            if a in seen and seen[a] is None:
                _not_distinct(head, row, node)
            out.append(('same', seen[a]) if a in seen else None)
            seen.setdefault(a, i)
        elif a.is_number:
            out.append(('value', _value_data(head, row, node, a)))
        else:
            raise ValueError(f"{head.__name__} row {row}: the argument {a} of {node} is not "
                             "a plain Symbol, an exact number, a function of a plain Symbol "
                             "or the constant variable")
    return tuple(out) if any(s is not None for s in out) else None


def _constant_shape(head, row, node, i, a):
    """The shape of the constant variable ``a``, argument ``i`` of ``node``:
    ``('constant',)``, or ``('coefficient',)`` for :data:`coefficient`,
    which is argument 0 of a function of any number of arguments."""
    if a != coefficient:
        return ('constant',)
    if head.__name__ not in ANY_ARITY or i != 0:
        raise ValueError(f"{head.__name__} row {row}: coefficient is argument 0 of a function "
                         f"of any number of arguments, not argument {i} of {node}")
    return ('coefficient',)


def _not_distinct(head, row, node):
    raise ValueError(f"{head.__name__} row {row}: the arguments of {node} are not distinct "
                     "(only a plain symbol can be repeated)")


def _inner(head, row, node, a):
    """The plain symbol ``u`` of an argument ``a == g(u)`` of ``node``."""
    if not (len(a.args) == 1 and isinstance(a.args[0], Symbol)
            and not isinstance(a.args[0], Constant)):
        raise ValueError(f"{head.__name__} row {row}: the argument {a} of {node} is not "
                         "a function of a plain Symbol")
    return _plain(head, row, a.args[0])


def _value_data(head, row, node, v):
    """The exact number ``v``, an argument of ``node``, as plain data: an
    int, or its text (``'E'``, ``'-I'``, ``'1/2'``), which :func:`generator`
    turns back into ``v``."""
    if v.has(Float, zoo, nan):
        raise ValueError(f"{head.__name__} row {row}: the argument {v} of {node} is not "
                         "an exact number")
    if v.is_Integer:
        return int(v)
    text = str(v)
    if from_text(text) != v:
        raise ValueError(f"{head.__name__} row {row}: the argument {v} of {node} is not "
                         f"rebuilt from its text {text!r}")
    return text


def _term(head, row, t):
    """``'node'``, ``'argument'`` (a symbol, or a function of one: an
    argument ``exp(u)`` of the node), or the kind of a term from
    :func:`_lit` (``'shift'``, ``'times'``, ``'of_constant'``)."""
    if isinstance(t, tuple):
        return t[0][0]
    if type(t) is head:
        return 'node'
    if isinstance(t, Constant):
        return 'argument'
    if isinstance(t, Symbol):
        _plain(head, row, t)
        return 'argument'
    if isinstance(t, Function) and len(t.args) == 1 and isinstance(t.args[0], Symbol):
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


# ---------------------------------------------------------------------------
# rows with a star: f(factor, *factors), every, some, count
# ---------------------------------------------------------------------------

def _schema(head, row, at_most):
    """The schema of a row with a star, plain data: ``(at_most, picks,
    rules)``.  ``picks`` has, for each picked argument in the order of the
    node, ``(kind, group)``: the kind is ``None`` (any argument),
    ``('constant',)`` (a constant one, :data:`number`), ``('coefficient',)``
    (argument 0 when it is a SymPy ``Number``) or ``('value', v)`` (the
    atomic number ``v``, an int or its text); picks of one group (the index
    of its first) are interchangeable: the row is the same for any order of
    them.  ``rules`` are ``(premises, conclusion)`` of literals ``(where,
    pred, sign)``, ``where`` the index of a picked argument, ``'node'``,
    ``'every'`` (each argument of the others), ``'some'`` (one of them),
    ``'count'`` (their number), or ``'others'``: an ``every`` literal that
    the ``some`` literal of the rule implies by the rule base, which the
    argument of ``some`` leaves out.  A rule with ``some`` in its premises
    has no picked argument; ``every`` and ``count`` are premises."""
    name = head.__name__
    _row(row)
    if name not in ANY_ARITY:
        raise ValueError(f"{name} row {row}: a row with a star is about a function of any "
                         f"number of arguments ({', '.join(sorted(ANY_ARITY))})")
    if len(row.atoms(Constant)) > 1:
        raise ValueError(f"{name} row {row}: more than one constant variable")
    nodes = row.atoms(f)
    starred = [a for a in nodes if any(isinstance(s, Arguments) for s in a.args)]
    if not starred:
        raise ValueError(f"{name} row {row}: every, some and count are about the arguments of "
                         "a node with a star, f(*factors)")
    if len(nodes) > 1:
        raise ValueError(f"{name} row {row} mentions more than one node")
    [node] = starred
    *picked, xs = node.args
    if not isinstance(xs, Arguments) or any(isinstance(a, Arguments) for a in picked):
        raise ValueError(f"{name} row {row}: the star is the last argument of {node}, "
                         "and the only one")
    if len(set(picked)) != len(picked):
        raise ValueError(f"{name} row {row}: the picked arguments of {node} are not distinct")
    kinds = tuple(_pick(head, row, node, a) for a in picked)
    where = {a: i for i, a in enumerate(picked)}
    where[node] = 'node'
    prem, concl = row.args if isinstance(row, Implies) else (True, row)
    premises = [_star_lit(head, row, t, where, xs) for t in _conjuncts(prem) if t is not True]
    out = []
    for c in _conjuncts(concl):
        if isinstance(c, Equivalent):
            if len(c.args) != 2:
                raise ValueError(f"{name} row {row}: {c} is not of two literals")
            a, b = (_star_lit(head, row, t, where, xs) for t in c.args)
            out += [(premises + [a], [b]), (premises + [b], [a])]
        else:
            out.append((premises, [_star_lit(head, row, t, where, xs)
                                   for t in (c.args if isinstance(c, Or) else (c,))]))
    out = [_star_rule(head, row, p, c, bool(picked)) for p, c in out]
    return (at_most, tuple(zip(kinds, _groups(kinds, out))), tuple(out))


def _pick(head, row, node, a):
    """The kind of the picked argument ``a`` of ``node`` (:func:`_schema`)."""
    if isinstance(a, Constant):
        return ('coefficient',) if a == coefficient else ('constant',)
    if isinstance(a, Symbol):
        _plain(head, row, a)
        return None
    if isinstance(a, Expr) and a.is_number:
        if not a.is_Atom:
            raise ValueError(f"{head.__name__} row {row}: the argument {a} of {node} is no "
                             "atomic number, which a picked argument of a row with a star is")
        return ('value', _value_data(head, row, node, a))
    raise ValueError(f"{head.__name__} row {row}: the picked argument {a} of {node} is not a "
                     "plain Symbol, an atomic number or a constant variable")


def _star_lit(head, row, e, where, xs):
    """``(where, pred, sign)`` of the literal ``e`` of a row with a star."""
    pos = not isinstance(e, Not)
    a = e if pos else e.args[0]
    if not (isinstance(a, AppliedPredicate) and len(a.arguments) == 1):
        raise ValueError(f"{head.__name__} row {row}: {e} is not a literal of one argument "
                         "(a row with a star has no inequalities)")
    pred = str(a.function.name)
    if pred not in VOCAB:
        raise ValueError(f"{head.__name__} row {row}: {pred} is not a template predicate")
    t = a.arguments[0]
    if t in where:
        return (where[t], pred, pos)
    over = _over().get(type(t))
    if over is not None:
        if t.args != (xs,):
            raise ValueError(f"{head.__name__} row {row}: {t} is not about {xs}, the arguments "
                             "of the node")
        return (over, pred, pos)
    if isinstance(t, Arguments):
        raise ValueError(f"{head.__name__} row {row}: {e} is about {t}: write "
                         f"every(Q.{pred}, {t}) or some(Q.{pred}, {t})")
    raise ValueError(f"{head.__name__} row {row}: {t} is neither the node nor one of its "
                     "picked arguments, nor every, some or count of the others")


def _star_rule(head, row, prem, concl, picked):
    """The rule ``(premises, conclusion)`` of a row with a star, checked;
    an ``every`` premise that the ``some`` premise implies is
    ``'others'``."""
    if any(w in ('every', 'count') for w, _, _ in concl):
        raise ValueError(f"{head.__name__} row {row}: every and count are premises; for a "
                         "conclusion about each argument, pick it: f(factor, *factors)")
    some_ = [(p, s) for w, p, s in prem if w == 'some']
    if some_:
        if len(some_) > 1 or picked or any(w == 'some' for w, _, _ in concl):
            raise ValueError(f"{head.__name__} row {row}: a row with some in its premises has "
                             "one some, no picked argument and no some in its conclusion")
        [s] = some_
        prem = [('others', p, sign) if w == 'every' and _implies(s, (p, sign)) else (w, p, sign)
                for w, p, sign in prem]
    return (tuple(prem), tuple(concl))


def _implies(a, b):
    """Whether the literal ``a`` (``(pred, sign)``) implies ``b`` by the
    rule base (in each of its models over the basis)."""
    from ..rules import _basis_models, cnf_of

    def holds(m, pred, sign):
        return all(any(m[abs(l) - 1] is (l > 0) for l in c) for c in cnf_of(pred, sign))
    return all(holds(m, *b) for m in _basis_models() if holds(m, *a))


def _groups(kinds, rules):
    """For each picked argument, the first of those it is interchangeable
    with: of the same kind, and the rules are the same after swapping
    them."""
    def swapped(i, j):
        sw = {i: j, j: i}
        return frozenset((frozenset((sw.get(w, w), p, s) for w, p, s in ps),
                          frozenset((sw.get(w, w), p, s) for w, p, s in cs)) for ps, cs in rules)
    same = swapped(0, 0)
    group = list(range(len(kinds)))
    for j in range(len(kinds)):
        for i in range(j):
            if group[i] == i and kinds[i] == kinds[j] and swapped(i, j) == same:
                group[j] = i
                break
    return group
