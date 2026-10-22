"""Template rules written as SymPy booleans (#249).

A *row* is ``premises >> conclusion`` over the plain symbol :data:`x` and
the node ``f(x)``::

    (Q.algebraic(x) & ~Q.zero(x)) >> Q.transcendental(sin(x))

The premises are a conjunction of literals; the conclusion is a literal, a
disjunction of literals, or a conjunction of those (one rule each).  A
literal is ``Q.p(t)`` or ``~Q.p(t)`` with ``p`` in ``VOCAB`` and ``t`` the
argument or the node.

:class:`Rows` holds rows, each labelled with where it comes from (a
property, a signature, a module); ``cond >> rows`` adds ``cond`` to the
premises of every row.  :func:`signature` states the sets a function maps
into sets: the image may be a predicate, a number or an interval
(:func:`Icc`, :func:`Ioo`, ...), and stands for the facts it implies
(:func:`facts_of`).  :func:`rules` compiles rows, at import, into the
index specs of :mod:`._common` (argument 0, node 1), so the patterns,
their cache and the engine are unchanged.

Python binds ``>>`` tighter than ``&``: ``a & b >> c`` is ``And(a,
Implies(b, c))``.  A row whose top is not an implication is rejected, which
catches the missing parentheses and a row SymPy collapsed to ``True``.
"""
from __future__ import annotations

from typing import NamedTuple

from sympy import And, Implies, Not, Or, Q, Rational, S, Symbol
from sympy.assumptions.assume import AppliedPredicate, Predicate

from ..rules import BASIS, BASIS_INDEX, DEF_LITS, RULE_INSTANTIATED, unit_propagate
from ._common import VOCAB, Rules

X, N = 0, 1

#: the argument of every row
x = Symbol('x')


class Rows:
    """Rows with their labels; ``a + b`` joins, ``cond >> rows`` adds a
    premise to each row."""
    __slots__ = ('items',)

    def __init__(self, items=()):
        self.items = tuple(items)

    def __add__(self, other: 'Rows') -> 'Rows':
        return Rows(self.items + other.items)

    def __rrshift__(self, cond) -> 'Rows':
        return Rows((label, Implies(cond & row.args[0], row.args[1]))
                    for label, row in self.items)

    def labelled(self, label: str) -> 'Rows':
        return Rows((label, row) for _, row in self.items)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


def rows(*items, label: str = '') -> Rows:
    """``Rows`` of the given rows (and ``Rows``)."""
    out = []
    for r in items:
        if isinstance(r, Rows):
            out.extend(r.items)
        elif isinstance(r, Implies):
            out.append((label, r))
        else:
            raise TypeError(f"row {r} is not an implication "
                            "(parenthesize both sides: >> binds tighter than &)")
    return Rows(out)


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


def signature(f, *pairs, label: str = 'signature') -> Rows:
    """``f`` maps each set into an image: ``(domain, image)`` pairs, the
    domain a predicate (or a boolean over :data:`x`), the image as in
    :func:`facts_of`.  ``(Q.zero, 1)`` is ``f(0) == 1``."""
    out = []
    for domain, image in pairs:
        prem = domain(x) if isinstance(domain, Predicate) else domain
        lits = [getattr(Q, p)(f(x)) if v else ~getattr(Q, p)(f(x)) for p, v in facts_of(image)]
        out.append((label, Implies(prem, And(*lits))))
    return Rows(out)


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------

def rules(head, rows: Rows, module: str):
    """The ``gen(R, c)`` of :func:`.functions._unary` for ``rows`` about
    ``head``; ``module`` (the caller's ``__name__``) is the module the
    registry attributes the template to (``TemplateRegistry.lazy``)."""
    specs = [spec for _, row in rows for spec in _specs(head, row)]

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
