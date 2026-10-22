"""Template rules written as SymPy booleans (#249).

A *row* is ``premises >> conclusion`` over the plain symbol :data:`x` and
the node ``f(x)``, with :data:`f` the generic function::

    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(f(x))

The premises are a conjunction of literals; the conclusion is a literal, a
disjunction of literals, or a conjunction of those (one rule each).  A
literal is ``Q.p(t)`` or ``~Q.p(t)`` with ``p`` in ``VOCAB`` and ``t`` the
argument or the node.

A family module states its rules as one tuple of :func:`for_all`
statements, each a tuple of functions and the rows that hold for each of
them, with ``f`` standing for the function; :func:`by_function` groups
them by function.  A row may be a :class:`Rows`, the sets of rows
:func:`closed` and :func:`signature` give: ``a & b`` joins two sets,
``cond >> rows`` adds ``cond`` to the premises of every row of a set.

Layout: a comment line above each statement names the property it states
(``tools/show_rows.py`` prints it as the label), then ``for_all((sin,
cos),`` on one line and the rows indented on the next, a longer row
continued on more lines::

    RULES = (
        # entire
        for_all((sin, cos),
            closed(f, Q.finite) & closed(f, Q.complex)),
    )

:func:`signature` states the sets a function maps into sets: the image may
be a predicate, a number or an interval (:func:`Icc`, :func:`Ioo`, ...),
and stands for the facts it implies (:func:`facts_of`).  :func:`rules`
compiles a function's rules, at import, into the index specs of
:mod:`._common` (argument 0, node 1), so the patterns, their cache and the
engine are unchanged.

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``, and ``c >> s & t`` is ``(c >> s) & t``.  A row whose top
is not an implication is rejected, and a set with a condition refuses
``&``, so both missing pairs of parentheses fail at import.
"""
from __future__ import annotations

from typing import NamedTuple

from sympy import And, Function, Implies, Not, Or, Q, Rational, S, Symbol
from sympy.assumptions.assume import AppliedPredicate, Predicate

from ..rules import BASIS, BASIS_INDEX, DEF_LITS, RULE_INSTANTIATED, unit_propagate
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
                        "or join a set with a condition in the function's tuple")

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


# --------------------------------------------------------------------------
# images: what a value in a set is
# --------------------------------------------------------------------------

class Interval(NamedTuple):
    """A real interval with Rational (or infinite, open) endpoints."""
    lo: object
    hi: object
    lo_open: bool
    hi_open: bool


def _end(v):
    v = S(v)
    if not (v.is_Rational or v in (S.Infinity, S.NegativeInfinity)):  # sympy-boundary: an author's endpoint
        raise ValueError(f"interval endpoint {v} is not a Rational or +-oo")
    return v


def _interval(lo, hi, lo_open, hi_open) -> Interval:
    lo, hi = _end(lo), _end(hi)
    if lo.is_infinite and not lo_open or hi.is_infinite and not hi_open or not lo < hi:  # sympy-boundary: endpoints
        raise ValueError(f"not an interval of reals with distinct endpoints: {lo}, {hi}")
    return Interval(lo, hi, lo_open, hi_open)


def Icc(lo, hi):
    return _interval(lo, hi, False, False)


def Ioo(lo, hi):
    return _interval(lo, hi, True, True)


def Ico(lo, hi):
    return _interval(lo, hi, False, True)


def Ioc(lo, hi):
    return _interval(lo, hi, True, False)


def _is_prime(n: int) -> bool:
    if n > 10**6:
        raise ValueError(f"no primality claim for {n} in a rule")
    return n > 1 and all(n % d for d in range(2, int(n**0.5) + 1))


def _number_facts(v):
    """Basis facts of the number ``v``, from its definition (#247: not
    SymPy's ``is_*``): a Rational from ``p`` and ``q``; ``zoo`` is the
    complex infinity, neither finite nor extended real."""
    if v is S.ComplexInfinity:
        return [('finite', False), ('extended_real', False)]
    if not isinstance(v, Rational):
        raise ValueError(f"no facts for the value {v}: only Rationals and zoo")
    p, q = int(v.p), int(v.q)
    out = [('finite', True), ('extended_real', True), ('rational', True),
           ('zero', p == 0), ('extended_positive', p > 0), ('extended_negative', p < 0),
           ('integer', q == 1)]
    if q == 1:
        out += [('even', p % 2 == 0), ('prime', _is_prime(p)),
                ('composite', p > 1 and not _is_prime(p))]
    return out


def _interval_facts(iv: Interval):
    """Basis facts every point of ``iv`` has."""
    lo, hi = iv.lo, iv.hi
    out = [('extended_real', True), ('finite', True)]
    if lo > 0 or lo == 0 and iv.lo_open:  # sympy-boundary: Rational endpoints
        out.append(('extended_positive', True))
    elif lo >= 0:
        out.append(('extended_negative', False))
    if hi < 0 or hi == 0 and iv.hi_open:  # sympy-boundary: Rational endpoints
        out.append(('extended_negative', True))
    elif hi <= 0:
        out.append(('extended_positive', False))
    if lo.is_finite and hi.is_finite:  # sympy-boundary: Rational endpoints
        n = int(lo.floor())
        # inside (n, n + 1): no integer
        if (lo > n or iv.lo_open) and (hi < n + 1 or hi == n + 1 and iv.hi_open):
            out.append(('integer', False))
    return out


#: the names an image's facts are written in, most preferred first: a fact
#: is dropped when the ones before it (and the rule base) give it
_NAMES = ('zero', 'positive', 'negative', 'nonnegative', 'nonpositive', 'nonzero',
          'odd', 'even', 'noninteger', 'integer', 'real', 'infinite', 'extended_real',
          'finite', 'extended_positive', 'extended_negative', 'rational', 'prime',
          'composite')


def facts_of(image):
    """The literals ``(pred, value)`` an image stands for: a predicate is
    itself; a number or an interval gives its facts, in the fewest of the
    names of :data:`_NAMES` that give all of them under the rule base."""
    if isinstance(image, Predicate):
        return [(str(image.name), True)]
    facts = _interval_facts(image) if isinstance(image, Interval) else _number_facts(S(image))
    units = {(BASIS_INDEX[p] + 1) * (1 if v else -1) for p, v in facts}
    closure = unit_propagate(RULE_INSTANTIATED, sorted(units)) or set()
    cands = []          # (name, value, basis units)
    for name in _NAMES:
        if name in BASIS_INDEX:
            i = BASIS_INDEX[name] + 1
            cands += [(name, l > 0, {l}) for l in (i, -i) if l in units]
        elif DEF_LITS[name][0] == '&' and set(DEF_LITS[name][1]) <= closure:
            cands.append((name, True, set(DEF_LITS[name][1])))
    named = set().union(*(c[2] for c in cands))
    cands += [(BASIS[abs(l) - 1], l > 0, {l}) for l in sorted(units - named, key=abs)]
    kept = list(cands)
    for c in reversed(cands):
        rest = [d for d in kept if d is not c]
        given = unit_propagate(RULE_INSTANTIATED, sorted(set().union(*(d[2] for d in rest))))
        if c[2] <= (given or set()):
            kept = rest
    return [(name, value) for name, value, _ in kept]


class Signature(Rows):
    """The rows of :func:`signature`."""
    __slots__ = ()


def signature(f, *pairs) -> Rows:
    """``f`` maps each set into an image: ``(domain, image)`` pairs,
    the domain a predicate (or a boolean over :data:`x`), the image as in
    :func:`facts_of`.  ``(Q.zero, 1)`` is ``f(0) == 1``."""
    out = []
    for domain, image in pairs:
        prem = domain(x) if isinstance(domain, Predicate) else domain
        lits = [getattr(Q, p)(f(x)) if v else ~getattr(Q, p)(f(x)) for p, v in facts_of(image)]
        out.append(Implies(prem, And(*lits)))
    return Signature(out)


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------

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
