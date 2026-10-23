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
``P(x) >> P(f(x))``; ``a & b`` joins rows, ``cond >> (a & b)`` adds
``cond`` to the premises of each.  The module holds rows only:
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

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``, and ``c >> s & t`` is ``(c >> s) & t``.  A row whose top
is a conjunction is rejected, and a set with a condition refuses ``&``, so
both missing pairs of parentheses fail at import.
"""
from __future__ import annotations

import ast
import operator
from types import MappingProxyType
from typing import NamedTuple

from sympy import (
    Abs, Add, And, Equivalent, Expr, Float, Function, I, Implies, Integer, Mul, Not, Or, S, Symbol,
    exp, nan, oo, sqrt, zoo,
)
from sympy.assumptions.assume import AppliedPredicate

from ._common import VOCAB, Rules


class Constant(Symbol):
    """A constant variable: in a row, an argument that is a constant (an
    atomic number) where the row is used.  A :class:`~sympy.Symbol`, so its
    terms (``2*number``, ``Abs(number)``) stay unevaluated, and told apart
    from a plain symbol by its class."""
    __slots__ = ()


#: the argument of every row
x = Symbol('x')
#: the second argument of a row about a function of two arguments
y = Symbol('y')
#: the base and the exponent of a power, and the ``u`` of a base ``exp(u)``
base = Symbol('base')
exponent = Symbol('exponent')
log_base = Symbol('log_base')
#: the constant variable: ``f(number, exponent)`` is a power of a constant
number = Constant('number')
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
    ``f`` of symbols, numbers and functions (the shapes, :func:`_shape`)
    is bound; ``f`` of anything else is left, and refused by :func:`rules`."""
    return row.xreplace({a: _node(fn, a.args) for a in row.atoms(f)
                         if all(isinstance(s, (Symbol, Function)) or s.is_number
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
    is a SymPy ``Number``, and leaves out the rules about it otherwise."""
    by_n = {}
    for row in rows_of(table):
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
    arities = tuple(n for n, _ in terms) or (1,)
    return (arities if len(arities) > 1 else arities[0]), tuple(terms), tuple(specs)


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
#: and of the terms of the constant variable (``'Abs(number) - 1'``)
_TEXT_NAMES = MappingProxyType({'E': S.Exp1, 'I': S.ImaginaryUnit, 'pi': S.Pi, 'number': number})
_TEXT_CALLS = MappingProxyType({'Abs': Abs, 'exp': exp, 'sqrt': sqrt})
_TEXT_OPS = MappingProxyType({ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                              ast.Div: operator.truediv, ast.Pow: operator.pow})


def from_text(text):
    """The SymPy expression of a text of :func:`compile_rows` (an int is an
    ``Integer``), read with :mod:`ast` and built with SymPy's arithmetic
    as SymPy's parser would build it, but without the parser, whose first
    use costs tens of milliseconds (the generator reads the texts when a
    function is first used); a text it does not read goes to ``S``."""
    if not isinstance(text, str):
        return S(text)
    try:
        return _read(ast.parse(text, mode='eval').body, _TEXT_NAMES)
    except (KeyError, TypeError, SyntaxError):
        return S(text)


def constant_value(text, c):
    """The term of the constant variable whose text is ``text`` at the
    constant ``c``, a SymPy ``Number``: ``constant_term(text).xreplace({number:
    c})``, computed from the text with ``c`` for ``number``, so that no term
    is built (the first sum SymPy builds in a process imports
    ``sympy.tensor``)."""
    try:
        return _read(ast.parse(text, mode='eval').body, {**_TEXT_NAMES, 'number': c})
    except (KeyError, TypeError, SyntaxError):
        return constant_term(text).xreplace({number: c})


def _read(e, names):
    if isinstance(e, ast.Constant) and type(e.value) is int:
        return Integer(e.value)
    if isinstance(e, ast.Name):
        return names[e.id]
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
        return -_read(e.operand, names)
    if isinstance(e, ast.BinOp):
        return _TEXT_OPS[type(e.op)](_read(e.left, names), _read(e.right, names))
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and not e.keywords:
        return _TEXT_CALLS[e.func.id](*(_read(a, names) for a in e.args))
    raise TypeError(ast.dump(e))


def _shape_object(shape):
    """A shape of :func:`_shape` with its numbers as SymPy numbers again."""
    return tuple(('value', from_text(s[1])) if s is not None and s[0] == 'value' else s
                 for s in shape)


def _term_object(t):
    """A term of :func:`compile_rows` with its numbers as SymPy numbers
    again; a term of the constant stays text (:func:`constant_term`,
    :func:`constant_value`)."""
    if t[0] == 'times':
        return ('times', t[1], from_text(t[2]))
    if t[0] in ('of_constant', 'inner'):
        return t
    return (t[0], from_text(t[1]))


def generator(name: str, arity, terms: tuple, specs: tuple, module: str):
    """The ``gen(R, c)`` that adds the rules ``specs`` (:func:`compile_rows`);
    ``module`` is the module the registry attributes the template to
    (``TemplateRegistry.lazy``).  ``gen.arity``, ``gen.terms`` (``{n: ((i,
    c), ...)}``, ``c`` a SymPy number again) and ``gen.shifts`` (the ``c``
    of the rows of one argument) tell :func:`.wiring.template` the slots:
    for several numbers of arguments, ``gen(R, n)`` is
    :func:`.functions.nary`'s, and gives the rules of the rows of ``n``
    arguments.

    ``gen.plain`` is false for rows with a shape or a term other than
    ``x + c``: ``gen.specs`` (``{n: rules}``, the rules of
    :func:`compile_rows` with the numbers of the shapes as SymPy numbers)
    and ``gen.terms`` (the other terms too, :func:`_term_object`) are then
    for the template that matches the node against the shapes and builds
    the terms; ``gen(R, c)`` would add every rule, shaped or not."""
    terms = {n: tuple(_term_object(t) for t in ts) for n, ts in terms}
    specs = dict(specs)
    one = tuple(spec for sp in specs.values() for spec in sp)

    def gen(R: Rules, c) -> None:
        # c: the constant argument (functions._unary) or the number of
        # arguments (functions.nary), which picks the rows for several
        for prem, concl, *_ in specs.get(c, ()) if len(specs) > 1 else one:
            R.rule(list(prem), list(concl))
    gen.__module__ = module
    gen.__name__ = gen.__qualname__ = f'{name}_rows'
    gen.arity = arity
    gen.terms = terms
    gen.shifts = tuple(t[1] for t in terms.get(1, ()) if isinstance(t[0], int))
    gen.specs = {n: tuple((*r[:2], _shape_object(r[2])) if len(r) > 2 else r for r in rs)
                 for n, rs in specs.items()}
    gen.plain = (all(isinstance(t[0], int) for ts in terms.values() for t in ts)
                 and all(len(r) == 2 for r in one))
    return gen


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
    if type(t) is head and t != 1/c:
        # 1/number is a term of the constant also for a head Pow
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
            out.append(('constant',) if s is a else ('head', type(a).__name__))
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
