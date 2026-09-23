"""The notation structural templates are written in.

A template is a generator of rules about one node and the objects around
it, written the way one would state them on paper::

    @template(Pow)
    def pow_rules(base, exponent, power):
        yield (base.positive & exponent.real) >> power.positive
        yield exponent.zero >> power.positive
        yield (base.zero & exponent.extended_negative) >> power.infinite

``base.positive`` is the statement "``base`` is positive".  Statements
combine with

* ``~a``       not ``a``,
* ``a & b``    ``a`` and ``b`` (premises),
* ``a | b``    ``a`` or ``b`` (conclusions),
* ``p >> c``   ``p`` implies ``c``; ``c`` may be a statement, an ``|`` of
  statements, an ``&`` of statements (one rule per conjunct) or
  ``a.iff(b)``,
* ``a.iff(b)`` ``a`` if and only if ``b``;

a statement yielded on its own is a fact.  ``&`` and ``|`` bind tighter
than ``>>`` in Python only when parenthesised, so write
``(a & b) >> (c | d)``; getting it wrong raises ``TypeError``.

The arguments of an n-ary node come as a :class:`Group`: ``terms.integer``
is "every term is an integer", ``any_of(terms).zero`` "some term is zero",
``none_of(terms).zero`` "no term is zero"; ``for t, rest in
terms.each_with_rest()`` states a rule once per argument.  A predicate
held in a variable is written ``x[pred]``.

Constants are resolved when the rules are compiled: an argument that is a
number has ``.value`` set (``None`` otherwise), and the compiler drops the
premises a constant satisfies and the rules it falsifies, so ``2*x`` and
``-x`` get specialised rules for free.  Rules are compiled once per
*pattern* (class, arity, the constants, the derived objects present and
the parameters) and cached; per node only the atoms are instantiated.
Predicate names are checked against the template vocabulary, so a typo is
an error, not a silently dead rule.

The notation lowers to the index-based specs of :mod:`._common` (a
literal ``(slot, pred, positive)``, a rule ``(premises, conclusions)``);
:func:`show_rules` prints compiled rules back in this notation.
"""
from __future__ import annotations

import inspect
from itertools import combinations
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ._common import _CACHE, VOCAB, Compiled, pattern
from .registry import registry

__all__ = [
    'Term', 'Group', 'Stmt', 'template', 'any_of', 'none_of', 'given', 'integer_at_least_2',
    'lower', 'show_rules',
]


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

class Term:
    """One object of a pattern: an argument, the node, or a derived object.
    ``term.<pred>`` (or ``term[pred]``) is the statement ``pred(term)``;
    ``term.value`` is the constant when the object is a number, else None."""
    __slots__ = ('slot', 'name', 'value')

    def __init__(self, slot: int, name: str, value=None):
        self.slot = slot
        self.name = name
        self.value = value

    @property
    def is_const(self) -> bool:
        return self.value is not None

    def __getitem__(self, pred: str) -> 'Stmt':
        if pred not in VOCAB:
            raise ValueError(f"unknown predicate {pred!r}")
        return Stmt(self.slot, pred, True)

    def __getattr__(self, pred: str) -> 'Stmt':
        if pred.startswith('_'):
            raise AttributeError(pred)
        try:
            return self[pred]
        except ValueError:
            raise AttributeError(f"{self.name}.{pred}: unknown predicate {pred!r}") from None

    def __repr__(self) -> str:
        return self.name


def _no_bool(self):
    raise TypeError("a rule statement has no truth value here; "
                    "did you mean `if x.value ...` (the constant)?")


class Stmt:
    """``pred(slot)`` if ``positive`` else ``~pred(slot)``."""
    __slots__ = ('slot', 'pred', 'positive')

    def __init__(self, slot: int, pred: str, positive: bool):
        self.slot = slot
        self.pred = pred
        self.positive = positive

    @property
    def lit(self):
        return (self.slot, self.pred, self.positive)

    def __invert__(self) -> 'Stmt':
        return Stmt(self.slot, self.pred, not self.positive)

    def __and__(self, other) -> 'All':
        return All((self,)) & other

    def __or__(self, other) -> 'Either':
        return Either((self,)) | other

    def __rshift__(self, concl) -> 'Rule':
        return All((self,)) >> concl

    def iff(self, other: 'Stmt') -> 'Iff':
        if not isinstance(other, Stmt):
            raise TypeError("iff() takes a single statement")
        return Iff(self, other)

    __bool__ = _no_bool


class All:
    """A conjunction of statements (true when empty)."""
    __slots__ = ('stmts',)

    def __init__(self, stmts: Tuple[Stmt, ...]):
        self.stmts = stmts

    def __and__(self, other) -> 'All':
        if isinstance(other, Stmt):
            return All(self.stmts + (other,))
        if isinstance(other, All):
            return All(self.stmts + other.stmts)
        raise TypeError(f"cannot combine a premise with {type(other).__name__} using &"
                        " (parenthesise: `(a & b) >> c`)")

    def __rshift__(self, concl) -> 'Rule':
        if not isinstance(concl, (Stmt, Either, All, Iff)):
            raise TypeError(f"cannot conclude {type(concl).__name__}")
        return Rule(self.stmts, concl)

    __bool__ = _no_bool


class Either:
    """A disjunction of statements; only allowed as a conclusion."""
    __slots__ = ('stmts',)

    def __init__(self, stmts: Tuple[Stmt, ...]):
        self.stmts = stmts

    def __or__(self, other) -> 'Either':
        if isinstance(other, Stmt):
            return Either(self.stmts + (other,))
        if isinstance(other, Either):
            return Either(self.stmts + other.stmts)
        raise TypeError(f"cannot combine a conclusion with {type(other).__name__} using |"
                        " (parenthesise: `p >> (a | b)`)")

    def __and__(self, other):
        raise TypeError("`(a | b) & c` is not a rule; a disjunction is only a conclusion")

    __bool__ = _no_bool


class Iff:
    __slots__ = ('a', 'b')

    def __init__(self, a: Stmt, b: Stmt):
        self.a = a
        self.b = b

    __bool__ = _no_bool


class Rule:
    __slots__ = ('premises', 'conclusion')

    def __init__(self, premises: Tuple[Stmt, ...], conclusion):
        self.premises = premises
        self.conclusion = conclusion

    def __and__(self, other):
        raise TypeError("`a >> b & c` parses as `(a >> b) & c`; write `a >> (b & c)`")

    __rand__ = __or__ = __ror__ = __rshift__ = __and__
    __bool__ = _no_bool


def lower(item) -> List[Tuple[list, list]]:
    """The ``(premises, conclusions)`` specs of a statement, rule or fact."""
    if isinstance(item, Rule):
        prem = [s.lit for s in item.premises]
        c = item.conclusion
    else:
        prem = []
        c = item
    if isinstance(c, Stmt):
        return [(prem, [c.lit])]
    if isinstance(c, Either):
        return [(prem, [s.lit for s in c.stmts])]
    if isinstance(c, All):
        return [(list(prem), [s.lit]) for s in c.stmts]
    if isinstance(c, Iff):
        return [([*prem, c.a.lit], [c.b.lit]), ([*prem, c.b.lit], [c.a.lit])]
    raise TypeError(f"not a rule or fact: {item!r}")


# ---------------------------------------------------------------------------
# Groups of arguments
# ---------------------------------------------------------------------------

class Group:
    """The arguments of an n-ary node (or some of them).  ``group.<pred>``
    is "every member satisfies ``pred``" (true for an empty group)."""
    __slots__ = ('terms',)

    def __init__(self, terms: Sequence[Term]):
        self.terms = tuple(terms)

    def __iter__(self):
        return iter(self.terms)

    def __len__(self) -> int:
        return len(self.terms)

    def __getitem__(self, key):
        if isinstance(key, str):
            return All(tuple(t[key] for t in self.terms))
        return self.terms[key]

    def __getattr__(self, pred: str) -> All:
        if pred.startswith('_'):
            raise AttributeError(pred)
        if pred not in VOCAB:
            raise AttributeError(f"unknown predicate {pred!r}")
        return self[pred]

    def without(self, *terms: Term) -> 'Group':
        return Group([t for t in self.terms if all(t is not u for u in terms)])

    def each_with_rest(self):
        """``(t, rest)`` for each member ``t``, ``rest`` the others."""
        return [(t, self.without(t)) for t in self.terms]

    def subsets(self, m: int):
        """``(chosen, rest)`` for each ``m``-element subset."""
        return [(Group(c), self.without(*c)) for c in combinations(self.terms, m)]

    @property
    def constants(self) -> List[Term]:
        return [t for t in self.terms if t.is_const]

    def __repr__(self) -> str:
        return f"Group({', '.join(t.name for t in self.terms)})"


class _Quantified:
    __slots__ = ('terms', 'kind')

    def __init__(self, terms, kind):
        self.terms = tuple(terms)
        self.kind = kind

    def __getitem__(self, pred: str):
        stmts = tuple(t[pred] for t in self.terms)
        if self.kind == 'any':
            return Either(stmts)
        return All(tuple(~s for s in stmts))

    def __getattr__(self, pred: str):
        if pred.startswith('_'):
            raise AttributeError(pred)
        if pred not in VOCAB:
            raise AttributeError(f"unknown predicate {pred!r}")
        return self[pred]


def any_of(terms: Iterable[Term]) -> _Quantified:
    """``any_of(g).pred``: some member satisfies ``pred`` (a conclusion)."""
    return _Quantified(terms, 'any')


def none_of(terms: Iterable[Term]) -> _Quantified:
    """``none_of(g).pred``: no member satisfies ``pred`` (a premise)."""
    return _Quantified(terms, 'none')


def given(*stmts: Stmt) -> All:
    """The conjunction of ``stmts``: ``given(a, b) >> c`` is ``(a & b) >> c``."""
    return All(tuple(stmts))


def integer_at_least_2(t: Term) -> Tuple[All, ...]:
    """Premises each of which says ``t`` is an integer >= 2."""
    return (All((t.prime,)), All((t.composite,)), t.even & t.positive)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _is_const(obj) -> bool:
    return obj is not None and obj.is_Atom and obj.is_number


def template(*classes: type, nary: bool = False,
             shape: Optional[Callable[[Any], Tuple[Dict[str, Any], Dict[str, Any]]]] = None,
             extra: Optional[Callable[[Any], list]] = None):
    """Register a rule generator for ``classes``.

    The generator's positional parameters name the objects: one per argument
    (or, with ``nary=True``, one :class:`Group` of all arguments), then the
    node.  ``shape(expr) -> (objects, params)`` may supply *derived* objects
    (``{'x_minus_1': x - 1}``; a value of None means "absent" and the
    generator receives None) and *parameters* (hashable values, part of the
    pattern); both are passed as keyword-only arguments, always the same
    names in the same order.  ``extra(expr, params)`` may return plain
    formulas added per node (``params`` is None without ``shape``)."""
    if not classes:
        raise TypeError("template() needs at least one class")

    def deco(gen):
        params = [p.name for p in inspect.signature(gen).parameters.values()
                  if p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD]
        if nary:
            group_name, node_name = params
            arity = None
        else:
            *arg_names, node_name = params
            arity = len(arg_names)

        def compile_pattern(key, objs, n, consts, derived_names, kwargs):
            for k, d in enumerate(objs[n + 1:], n + 1):
                if _is_const(d):
                    consts[k] = d

            def slot_names():
                args = ([f"{group_name}[{k}]" for k in range(n)] if nary else arg_names)
                return [*args, node_name, *derived_names]

            def specs():
                names = slot_names()
                terms = [Term(k, names[k], consts.get(k)) for k in range(n)]
                derived = {dn: (None if objs[k] is None else Term(k, dn, consts.get(k)))
                           for k, dn in enumerate(derived_names, n + 1)}
                first = (Group(terms),) if nary else terms
                out = []
                for item in gen(*first, Term(n, node_name), **derived, **kwargs):
                    out.extend(lower(item))
                return out

            return pattern(key, specs, consts, n, slot_names)

        def tmpl(expr):
            args = expr.args
            n = len(args)
            if n != arity and (arity is not None or n == 0):
                return ()
            consts = {}
            ckey = ()
            for k, a in enumerate(args):
                if a.is_Atom and a.is_number:
                    consts[k] = a
                    ckey += ((k, type(a), a),)
            if shape is None:
                objs = args + (expr,)
                key = (gen, n, ckey)
                derived = kwargs = None
            else:
                derived, kwargs = shape(expr)
                dvals = tuple(derived.values())
                objs = args + (expr,) + dvals
                # Which derived objects are present, and their values when
                # they are constants.
                present = tuple([d is not None and ((type(d), d) if d.is_Atom and d.is_number
                                                    else True) for d in dvals])
                key = (gen, n, ckey, present, tuple(kwargs.values()))
            pat = _CACHE.get(key)
            if pat is None:
                pat = compile_pattern(key, objs, n, consts,
                                      tuple(derived or ()), kwargs or {})
            out = Compiled(objs, pat)
            if extra is not None:
                more = extra(expr, kwargs)
                if more:
                    return [out, *more]
            return out

        tmpl.__name__ = gen.__name__
        tmpl.__qualname__ = gen.__qualname__
        tmpl.__doc__ = gen.__doc__
        registry.register(*classes)(tmpl)
        return gen

    return deco


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def _show_lit(lit, names) -> str:
    k, pred, pos = lit
    s = f"{names[k]}.{pred}"
    return s if pos else '~' + s


def show_rule(rule, names) -> str:
    """One compiled rule ``(premises, conclusions)`` in template notation.
    A rule without premises is shown with its negative literals as
    premises (``~a | ~b | c`` as ``(a & b) >> c``)."""
    ps, cs = rule
    if not ps and len(cs) > 1:
        neg = [(k, p, True) for k, p, pos in cs if not pos]
        cs = [l for l in cs if l[2]] or [(*neg.pop()[:2], False)]
        ps = neg
    concl = ' | '.join(_show_lit(l, names) for l in cs)
    if not ps:
        return concl
    if len(cs) > 1:
        concl = f"({concl})"
    prem = ' & '.join(_show_lit(l, names) for l in ps)
    if len(ps) > 1:
        prem = f"({prem})"
    return f"{prem} >> {concl}"


def show_rules(expr) -> str:
    """Every rule the templates emit for ``expr``, in template notation:
    per template, what each name stands for, then the rules after
    constants are resolved and subsumed rules dropped (exactly what the
    engine asserts for the node)."""
    out = []
    for tmpl in registry.templates_for(type(expr)):
        result = tmpl(expr)
        if result is None or result == ():
            continue
        items = result if isinstance(result, list) else [result]
        compiled = [r for r in items if isinstance(r, Compiled)]
        plain = [r for r in items if not isinstance(r, Compiled)]
        for c in compiled:
            pat = c.pattern
            names = pat.names or ['y']
            shown = sorted({k for k, o in enumerate(c.objs) if o is not None and k <= pat.node}
                           | set(pat.used))
            legend = ', '.join(f"{names[k]} = {c.objs[k]}" for k in shown)
            out.append(f"# {tmpl.__name__}: {legend}")
            out.extend(show_rule(r, names) for r in pat.rules)
        if plain:
            out.append(f"# {tmpl.__name__}: per-node facts")
            out.extend(str(f) for f in plain)
        out.append('')
    return '\n'.join(out).rstrip()
