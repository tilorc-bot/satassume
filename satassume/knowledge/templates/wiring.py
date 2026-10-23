"""Which template each function of a family of rows gets (#249).

The family modules (the names of ``ROW_FAMILIES`` in ``templates/__init__.py``:
:mod:`.trig`, :mod:`.hyperbolic`, :mod:`.inverse`, ...)
state rows only, as ``RULES`` (see :mod:`._rows`).  :func:`load` compiles
a family's rows and registers one template per function (:func:`template`):
the unary template of its rows (:func:`.functions._unary`), with the facts
of a constant argument for a function of :data:`UNIT_INTERVAL` or
:data:`VALUE_AT_INTEGER`, and the rules about ``n/2`` for a function of
:data:`HALF_ARGUMENT`, or, for a
function of :data:`PI_MULTIPLE` or :data:`I_PI_MULTIPLE`,
:func:`.functions._pi_trig`'s, which adds the rules of ``f(pi*c*s)`` for a
rational ``c``, or, for a function of :data:`I_PI_ROOT`,
:func:`.functions._exp_ipi`'s, which adds those of ``f(I*pi*c*s)``, or
:func:`.functions.nary`'s for rows about a function of several arguments;
then the templates of :data:`AFTER_ROWS`, which are not rows.  Rows with a
star, about a function of any number of arguments (``f(factor,
*factors)``), are expanded for each node by :func:`expand`
(:func:`any_arity`'s template: ``Max``, ``Min`` and ``Piecewise``, with
:data:`ARGUMENTS` and :data:`LEAVE_OUT_WIDE`; :func:`product`'s for
``Mul``, with the factor sets and ``a/v**k`` of :mod:`.core`;
:func:`addition`'s for ``Add``, with the sums of a special shape of
:mod:`.core`).
``templates/__init__.py`` declares each family as ``"<this
module>:<family>"`` for its functions (``TemplateRegistry.lazy``), so a
family is compiled on the first use of one of its functions, and its
templates are attributed to that name.
"""
from __future__ import annotations

import importlib
from itertools import combinations

from sympy import (
    Add, Expr, Integer, Max, Min, Mul, Piecewise, Pow, S, acos, andre, asin, catalan, cos, cosh,
    exp, factorial2, genocchi, im, partition, re, sin, subfactorial,
)

from ...sat.formula import And, Implies, Not, Or, P
from ..rules import cnf_of
from ._common import MAX_EXPAND, Rules, const_key, const_value, consts_of, facts, pattern_key
# not ._rows, the language of the rows, which a query does not need (#309)
from ._rows_runtime import constant_value, generator
from .core import (
    _exp_arg, _imag_split, _imag_templates,
    _mul_factor_sets, _quotient_templates, _unit_angle, _unit_power_units, ipi_rules,
    ipi_split, irrational_root,
)
from .registry import registry

#: the functions with rules for an argument pi*c*s, each with whether it
#: shifts like cos (cos(pi*c*s) == sin(pi*(c + 1/2)*s))
PI_MULTIPLE = ((sin, False), (cos, True))

#: the functions with rules for an argument I*pi*c*s (cosh(I*pi*c*s) ==
#: cos(pi*c*s)) and r + I*pi*c*s for an integer c (functions._cosh_shift)
I_PI_MULTIPLE = (cosh,)

#: the functions with rules for an argument I*pi*c*s, a root of unity for
#: an integer s and on the unit circle for a real one (core.ipi_rules)
I_PI_ROOT = (exp,)

#: the functions with facts for a rational or float argument c: real on
#: [-1, 1], and which side of the cut outside (functions._in_unit_interval_units)
UNIT_INTERVAL = (asin, acos)

#: the functions with the facts of their value at an integer argument c,
#: |c| <= 200, which SymPy computes (functions._value_units)
VALUE_AT_INTEGER = (factorial2, subfactorial, catalan, andre, partition, genocchi)

#: the functions with rules about half the argument, n/2, in the slot after
#: the terms x + c: genocchi(n) for an even n > 0 has the sign (-1)**(n/2)
#: (functions._genocchi_half)
HALF_ARGUMENT = (genocchi,)

#: the functions whose rows have shapes and terms other than x + c, which
#: :func:`power` matches a node against: the power (``templates/power.py``)
POWER = (Pow,)

#: templates that are not rows, each with the functions it is for,
#: registered after the rows of those functions: re and im of floor(y) or
#: ceiling(y) are integers (functions.parts_of_round_templates); by name, as
#: :mod:`.functions` is imported only for a family that needs it (#297)
AFTER_ROWS = (((re, im), 'parts_of_round_templates'),)


def functions(family: str):
    """The functions the family's ``RULES`` state rows for, in order."""
    from ._rows import by_function
    module = importlib.import_module(f"{__package__}.{family}")
    return tuple(fn for fn, _ in by_function(module.RULES))


def template(fn, gen):
    """The template of ``fn`` whose rules ``gen`` (the compiled rows) gives.
    The objects of the terms ``x + c`` its rules use (``gen.shifts``,
    ``gen.terms``, see :func:`._rows.rules`) are built by
    :func:`.functions.shifted` (#184).  Rows about a node of several
    arguments, or about nodes of several numbers of arguments
    (``gen.arity``), get :func:`.functions.nary`'s template: the arguments
    are slots ``0 .. n-1``, the node ``n``, the terms from ``n + 1``; a
    node of another number of arguments gets no facts.  Rows with shapes
    or terms other than ``x + c`` (``gen.plain`` false) get :func:`power`'s
    template for a function of :data:`POWER`, and are refused for another:
    no other template here matches a node against shapes.  Rows with a star
    (``gen.schemas``) get :func:`product`'s template for a function of
    :data:`PRODUCT`, :func:`addition`'s for one of :data:`SUM`, and
    :func:`any_arity`'s for another, keyed by the name
    of the function, with the arguments :data:`ARGUMENTS` gives and the
    rules over too many clauses left out for a function of
    :data:`LEAVE_OUT_WIDE`.  :mod:`.functions` is imported for the templates
    of :func:`.functions` only, not for :func:`power`'s, :func:`product`'s,
    :func:`addition`'s or :func:`any_arity`'s (#297)."""
    if fn in POWER:
        return power(gen)
    if fn in PRODUCT:
        return product(gen)
    if fn in SUM:
        return addition(gen)
    if getattr(gen, 'schemas', ()):
        return any_arity(fn.__name__, gen, dict(ARGUMENTS).get(fn), fn in LEAVE_OUT_WIDE)
    if not getattr(gen, 'plain', True):
        raise ValueError(f"{fn.__name__}: its rows have shapes or terms other than x + c, "
                         "which none of these templates builds")
    from .functions import (
        _cosh_shift, _exp_ipi, _genocchi_half, _in_unit_interval_units, _pi_trig, _unary,
        _value_units, nary, shifted,
    )
    shift = dict(PI_MULTIPLE).get(fn)
    if shift is not None:
        return _pi_trig(fn.__name__, gen, shift)
    if fn in I_PI_MULTIPLE:
        return _pi_trig(fn.__name__, gen, True, ipi_split, _cosh_shift(gen))
    if fn in I_PI_ROOT:
        return _exp_ipi(gen)
    arity = getattr(gen, 'arity', 1)
    if arity != 1:
        terms = getattr(gen, 'terms', {})
        return nary(fn.__name__, gen, arity=arity,
                    slots=lambda args: tuple(shifted(args[i], S(c))
                                             for i, c in terms.get(len(args), ())))
    shifts = getattr(gen, 'shifts', ())
    units = (_in_unit_interval_units(fn.__name__) if fn in UNIT_INTERVAL
             else _value_units if fn in VALUE_AT_INTEGER else None)
    if fn in HALF_ARGUMENT:
        return _unary(fn.__name__, _genocchi_half(gen, 2 + len(shifts)),
                      lambda a: (*(shifted(a, S(c)) for c in shifts), a/2), units)
    return _unary(fn.__name__, gen, lambda a: tuple(shifted(a, S(c)) for c in shifts), units)


def load(family: str) -> None:
    """Register the templates of the family's rows (``TemplateRegistry.lazy``),
    then those of :data:`AFTER_ROWS` for its functions.  The rows are read
    compiled (``_compiled_rows.py``, written by ``tools/compile_rows.py``):
    the family module, and the SymPy booleans it builds, are not imported."""
    from . import ROW_FAMILIES
    from ._compiled_rows import FAMILIES
    name = f"{__name__}:{family}"
    by_name = {fn.__name__: fn for fn in map(_declared, dict(ROW_FAMILIES)[family])
               if fn is not None}
    fns = set()
    for fn_name, arity, terms, specs, *schemas in dict(FAMILIES)[family]:
        fn = by_name.get(fn_name)
        if fn is None:
            # declared by name and new in a later SymPy (owens_t)
            continue
        registry.register(fn)(template(fn, generator(fn_name, arity, terms, specs, name,
                                                     *schemas)))
        fns.add(fn)
    for classes, t in AFTER_ROWS:
        if fns.issuperset(classes):
            t = getattr(importlib.import_module(f"{__package__}.functions"), t)
            registry.register(*classes)(_attributed(t, name))


def _declared(fn):
    """The function a family declares: a class, or ``"module:Class"`` for a
    class of a module SymPy does not import itself, or one this SymPy may
    lack (``None`` then)."""
    if not isinstance(fn, str):
        return fn
    module, _, cls = fn.partition(":")
    return getattr(importlib.import_module(module), cls, None)


def _attributed(t, module):
    """``t``, attributed to ``module`` (the registry tells a declared
    module's templates by their module)."""
    def template(expr):
        return t(expr)
    template.__name__ = template.__qualname__ = t.__name__
    template.__module__ = module
    return template


def matches(shape, args, consts):
    """Whether the arguments ``args`` of a node have the shape ``shape`` of a
    rule (:func:`power`, :func:`any_arity`); ``consts`` holds the indices of
    the arguments that are constants (atomic numbers).  A ``coefficient``
    is argument 0, a SymPy ``Number``."""
    for i, s in enumerate(shape):
        if s is None:
            continue
        a = args[i]
        kind = s[0]
        if kind == 'value':
            if not (type(a) is type(s[1]) and a == s[1]):
                return False
        elif kind == 'same':
            if a is not args[s[1]]:
                return False
        elif kind == 'head':
            if _exp_arg(a) is None:
                return False
        elif kind == 'coefficient':
            if not (i == 0 and 0 in consts and consts[0].is_Number):
                return False
        elif i not in consts:           # 'constant'
            return False
    return True


def power(gen):
    """The template of ``Pow`` from its rows (``templates/power.py``):
    ``gen.specs[2]`` are the rules, a rule with a shape for the nodes of
    that shape only, and ``gen.terms[2]`` the terms, in slots ``3, 4, ...``
    after the base 0, the exponent 1 and the node 2; the ``s`` of
    ``E**(I*pi*c*s)`` comes last.

    A node has a shape when each argument matches it: a number when it is
    of its type and equal (``-I`` is ``Mul(-1, I)``), ``('head', 'exp')``
    when it is ``exp(u)`` or an unevaluated ``E**u`` (:func:`.core._exp_arg`),
    ``('same', j)`` when it is argument ``j``, ``('constant',)`` when it is a
    constant (an atomic number).  The terms exist as in the template that
    was before the rows: ``u`` for such a base, ``k*e`` (``Mul(k, e)``) when
    the exponent ``e`` is not a number, ``b + c`` when neither argument is
    a number, a term of the constant (``Abs(number) - 1``) when the
    argument is a SymPy ``Number``, computed there; a rule about a term that
    does not exist is left out.  The pattern is keyed as that template's
    was, by the constants, ``b is e``, the angle of a base ``I``, ``-1``,
    ``-I`` (:func:`.core._unit_angle`), the ``u``, ``E**(I*pi*c*s)``
    (:func:`.core.ipi_split`) and which terms exist: the key decides every
    shape and every term.

    The rules that are not rows are added from :mod:`.core`: those of
    ``E**(I*pi*c*s)`` (:func:`.core.ipi_rules`), the irrational ``b**(p/q)``
    (:func:`.core.irrational_root`), and next to the block the facts of
    ``b**e`` for ``b`` in ``I``, ``-1``, ``-I`` and a numeric ``e``
    (:func:`.core._unit_power_units`).  The bounds of a base ``c0 + c1*u``
    are the relation glue's (``relations.BOUND_LINKS``, #315)."""
    terms = gen.terms[2]
    first = 3
    s_slot = first + len(terms)
    nobjs = s_slot + 1
    shifts, inner, times, of_constant = [], [], [], []
    for k, t in enumerate(terms, first):
        if t[0] == 'inner':
            inner.append((k, t[1]))
        elif t[0] == 'times':
            times.append((k, t[1], t[2]))
        elif t[0] == 'of_constant':
            of_constant.append((k, t[1], t[2]))
        else:
            shifts.append((k, t[0], t[1]))
    rules = []
    for r in gen.specs[2]:
        prem, concl = list(r[0]), list(r[1])
        shape = r[2] if len(r) > 2 else None
        for s in shape or ():
            if s is not None and s[0] == 'head' and s[1] != 'exp':
                raise ValueError(f"Pow: no template matches a base {s[1]}(u)")
        terms_of = frozenset(k for k, _, _ in (*prem, *concl) if k >= first)
        rules.append((prem, concl, shape, terms_of))

    def template(expr):
        args = b, e = expr.args
        consts = {}
        if b.is_Atom and b.is_number:
            consts[0] = b
        if e.is_Atom and e.is_number:
            consts[1] = e
        objs = [b, e, expr] + [None] * (nobjs - first)
        u = None
        for k, i in inner:
            u = _exp_arg(args[i])
            if u is not None:
                objs[k] = u
                if u.is_Atom and u.is_number:
                    consts[k] = u
        ipi = None
        if b is S.Exp1 and 1 not in consts:
            split = ipi_split(e)
            if split is not None:
                c, s_ = split
                ipi = (c, s_ is not None)
                if s_ is not None:
                    objs[s_slot] = s_
                    if s_.is_Atom and s_.is_number:
                        consts[s_slot] = s_
        has_t = 1 not in consts and not e.is_number
        for k, i, c in times:
            if not args[i].is_number:
                objs[k] = Mul(c, args[i])
        has_b1 = has_t and 0 not in consts and not b.is_number
        if has_b1:
            for k, i, c in shifts:
                objs[k] = args[i] + c
        angle = _unit_angle(b)
        key = ('pow', const_key(b) if 0 in consts else None,
               const_key(e) if 1 in consts else None, b is e, angle,
               (const_key(u) if u.is_Atom and u.is_number else True) if u is not None else False,
               ipi, const_key(objs[s_slot]) if s_slot in consts else None, has_t, has_b1)

        def build():
            # the terms of the constants, computed only for a new pattern:
            # facts() resolves the rules against consts after calling this
            for k, i, t in of_constant:
                c = consts.get(i)
                if c is not None and c.is_Number:
                    consts[k] = constant_value(t, c)
            exist = {k for k in range(first, nobjs) if objs[k] is not None or k in consts}
            R = Rules()
            for prem, concl, shape, terms_of in rules:
                if terms_of <= exist and (shape is None or matches(shape, args, consts)):
                    R.rule(prem, concl)
            if ipi is not None:
                ipi_rules(R.rule, ipi[0], s_slot if ipi[1] else None, 2)
            if irrational_root(consts.get(0), consts.get(1)):
                R.rule([], (2, 'irrational', True))
            return R.rules

        out = facts(key, build, consts, tuple(objs), 2)
        if angle is not None and e.is_number:
            return [out, *_unit_power_units(angle, e, expr)]
        return out
    template.__name__ = template.__qualname__ = 'pow_templates'
    template.__module__ = gen.__module__
    return template


# ---------------------------------------------------------------------------
# Rows about a function of any number of arguments: the rows with a star
# (``f(factor, *factors)``, ``every``, ``some``, ``count``; ``_rows._schema``)
# ---------------------------------------------------------------------------

def piecewise_values(expr):
    """The values of a ``Piecewise`` (its expressions) when its last
    condition is ``True``: the node is one of them.  None without a final
    ``True`` (the node is ``nan`` where no condition holds) and for a
    ``Piecewise`` of Booleans: no facts."""
    args = expr.args
    if not args or args[-1].cond is not S.true:
        return None
    values = tuple(a.expr for a in args)
    if not all(isinstance(v, Expr) for v in values):
        return None
    return values


#: the functions whose rows with a star are about other arguments than the
#: node's ``args``, each with the function that gives them for a node (None:
#: no facts): the values of a ``Piecewise``
ARGUMENTS = ((Piecewise, piecewise_values),)

#: the functions whose rules with a star are left out of a node when their
#: clauses over the basis would be more than ``MAX_EXPAND``, a limit on the
#: cost (``expand``'s ``leave_out_wide``); for the other functions such a
#: rule is encoded as a formula (``Pattern.wide``)
LEAVE_OUT_WIDE = (Max, Min, Piecewise)

#: past this many arguments, a rule with ``some`` in its premises is one
#: formula (:func:`wide_formulas`, linear in the width with Tseitin
#: variables) instead of a rule per argument (quadratic); an encoding, not
#: an answer
SOME_PER_ARGUMENT = 32


def expand(schemas, n, consts, leave_out_wide=False):
    """The rules ``(premises, conclusion)`` of the rows with a star
    (``gen.schemas``) for a node of ``n`` arguments, the slots ``0 .. n-1``,
    and the node ``n``, with the constants ``consts`` (by slot), called
    when a pattern is built.

    A row holds for ``len(picks) <= n <= at_most``.  Its picked arguments
    are placed at every set of distinct positions their kinds allow (any,
    a constant, 0 when it is a ``Number`` for ``coefficient``, a constant
    equal to the value), interchangeable ones (a group) once per set of
    positions, in order; the others are the rest.  ``every`` is the
    conjunction over the rest; ``some`` a rule per argument of the rest
    (with ``others`` on the rest but it) in the premises, a disjunction in a
    conclusion; ``count`` is decided by the number of the rest, as a
    constant's literal is (``const_value``).  Past
    :data:`SOME_PER_ARGUMENT` arguments a rule with ``some`` in its
    premises is left to :func:`wide_formulas`.  With ``leave_out_wide``
    (Max, Min, Piecewise), a rule whose clauses over the basis would be
    more than ``MAX_EXPAND`` is left out, not encoded as a formula
    (``Pattern.wide``): the product ``Pattern`` computes, before the
    constants are resolved."""
    out = []
    for at_most, picks, rules in schemas:
        if n < len(picks) or (at_most is not None and n > at_most):
            continue
        if n > SOME_PER_ARGUMENT:
            rules = [r for r in rules if not any(w == 'some' for w, _, _ in r[0])]
        for placed in _placements(picks, n, consts):
            rest = [i for i in range(n) if i not in placed]
            for prem, concl in rules:
                out += _instances(prem, concl, placed, rest, n)
    if leave_out_wide:
        out = [r for r in out if _clauses(r) <= MAX_EXPAND]
    return out


def _placements(picks, n, consts):
    """The positions of the picked arguments, one tuple per way to place
    them: each group (``(kind, group)``) at the combinations of the
    positions its kind allows and the earlier groups left."""
    groups = {}
    for i, (_, g) in enumerate(picks):
        groups.setdefault(g, []).append(i)
    groups = tuple(groups.values())
    allowed = tuple(_allowed(kind, n, consts) for kind, _ in picks)
    placed = [None] * len(picks)

    def place(gi, used):
        if gi == len(groups):
            yield tuple(placed)
            return
        members = groups[gi]
        for at in combinations([p for p in allowed[members[0]] if p not in used], len(members)):
            for i, p in zip(members, at):
                placed[i] = p
            yield from place(gi + 1, used.union(at))
    return place(0, frozenset())


def _allowed(kind, n, consts):
    """The positions a picked argument of ``kind`` can have."""
    if kind is None:
        return range(n)
    if kind[0] == 'coefficient':
        return (0,) if 0 < n and 0 in consts and consts[0].is_Number else ()
    at = sorted(k for k in consts if k < n)
    if kind[0] == 'value':
        v = kind[1]
        return [k for k in at if type(consts[k]) is type(v) and consts[k] == v]
    return at                       # 'constant'


def _instances(prem, concl, placed, rest, n):
    """The rules of one rule of a schema with its picks at ``placed``."""
    def lits(w, p, s):
        if w == 'node':
            return [(n, p, s)]
        if type(w) is int:
            return [(placed[w], p, s)]
        return [(j, p, s) for j in rest]       # every, some (a conclusion)
    ps, others, some_ = [], [], None
    for w, p, s in prem:
        if w == 'count':
            if const_value(Integer(len(rest)), p) is not s:
                return []
        elif w == 'some':
            some_ = (p, s)
        elif w == 'others':
            others.append((p, s))
        else:
            ps += lits(w, p, s)
    cs = [lit for w, p, s in concl for lit in lits(w, p, s)]
    if some_ is None:
        return [(ps, cs)]
    return [(ps + [(j, p, s) for j in rest if j != k for p, s in others] + [(k, *some_)], cs)
            for k in rest]


def _clauses(rule):
    """The number of clauses of ``rule`` over the basis (``Pattern``)."""
    k = 1
    for _, p, s in rule[0]:
        k *= len(cnf_of(p, not s))
    for _, p, s in rule[1]:
        k *= len(cnf_of(p, s))
    return k


def wide_formulas(schemas, expr, args, consts):
    """For a node of more than :data:`SOME_PER_ARGUMENT` arguments, each
    rule with ``some`` in its premises as one formula over ``args`` and the
    node ``expr``: ``every`` of each argument and ``some`` of one give the
    conclusion (the rule base gives ``others`` from ``some``).  A constant
    argument is decided here: one that is not ``every`` (or undecided)
    drops the formula, one that is ``some`` meets it."""
    n = len(args)
    if n <= SOME_PER_ARGUMENT:
        return []
    out = []
    for at_most, _, rules in schemas:
        if at_most is not None and n > at_most:
            continue
        for prem, concl in rules:
            if any(w == 'some' for w, _, _ in prem):
                f = _wide(expr, args, consts, prem, concl)
                if f is not None:
                    out.append(f)
    return out


def _wide(expr, args, consts, prem, concl):
    every = [(p, s) for w, p, s in prem if w in ('every', 'others')]
    [(sp, ss)] = [(p, s) for w, p, s in prem if w == 'some']
    if any(const_value(Integer(len(args)), p) is not s for w, p, s in prem if w == 'count'):
        return None
    weak, strong, met = [], [], False
    for k, a in enumerate(args):
        c = consts.get(k)
        if c is None:
            weak += [_atom(p, s, a) for p, s in every]
            strong.append(_atom(sp, ss, a))
        elif any(const_value(c, p) is not s for p, s in every):
            return None
        elif const_value(c, sp) is ss:
            met = True
    if not (met or strong):
        return None
    node = [_atom(p, s, expr) for w, p, s in prem if w == 'node']
    ps = node + weak + ([] if met else [Or(*strong)])
    cs = [_atom(p, s, expr) for _, p, s in concl]
    c = cs[0] if len(cs) == 1 else Or(*cs)
    return Implies(And(*ps), c) if ps else c


def _atom(pred, sign, obj):
    return P(pred, obj) if sign else Not(P(pred, obj))


def any_arity(tag, gen, arguments=None, leave_out_wide=False):
    """The template of a function of any number of arguments from its rows
    (``gen``): the block of :func:`rows_block` over the node's arguments,
    then the wide formulas (:func:`wide_formulas`).  ``arguments`` gives
    the arguments of a node (Piecewise's values), None for no facts;
    ``leave_out_wide`` is :func:`expand`'s."""
    block = rows_block(tag, gen, leave_out_wide)

    def template(expr):
        args = expr.args if arguments is None else arguments(expr)
        if args is None:
            return None
        wide = _wide_of(gen, expr, args)
        return [block(args, expr), *wide] if wide else block(args, expr)
    template.__name__ = template.__qualname__ = f'{tag}_rows_templates'
    template.__module__ = gen.__module__
    return template


def _wide_of(gen, expr, args):
    """The wide formulas of a node of the arguments ``args``."""
    if len(args) <= SOME_PER_ARGUMENT:
        return []
    return wide_formulas(gen.schemas, expr, args, consts_of(args))


def rows_block(tag, gen, leave_out_wide=False):
    """``block(args, expr)``: the block of the rows (``gen``) of a function
    of any number of arguments over the arguments ``args`` and the node
    ``expr``: the rows without a star for a node of their number of
    arguments, with a shape for the nodes that match it (a constant, a
    ``coefficient``, a number) and the terms of the constant
    (``2*coefficient``) after the node, computed when the constant is a
    SymPy ``Number``; then the rows with a star (:func:`expand`).  The
    pattern is keyed ``pattern_key(tag, n, consts)``, as the templates
    before the rows were (``'mul'``, ``'Max'``)."""
    for n, ts in gen.terms.items():
        for t in ts:
            if t[0] != 'of_constant':
                raise ValueError(f"{tag}: a row of {n} arguments has the term {t}: only terms "
                                 "of the constant are built for a function of any arity")
    for rs in gen.specs.values():
        for r in rs:
            if len(r) > 2 and any(s is not None and s[0] in ('same', 'head') for s in r[2]):
                raise ValueError(f"{tag}: a row has the shape {r[2]}, which the pattern of "
                                 "a function of any arity does not key")
    nterms = {n: len(ts) for n, ts in gen.terms.items()}

    def block(args, expr):
        n = len(args)
        consts = consts_of(args)
        objs = (*args, expr) + (None,) * nterms.get(n, 0)
        return facts(pattern_key(tag, n, consts),
                     lambda: rules_for(gen, args, consts, leave_out_wide), consts, objs, n)
    return block


def rules_for(gen, args, consts, leave_out_wide=False):
    """The rules of :func:`rows_block` for a node of the arguments
    ``args`` with the constants ``consts``, to which the values of the
    terms of the constant are added (by slot)."""
    n = len(args)
    for k, (_, i, t) in enumerate(gen.terms.get(n, ()), n + 1):
        c = consts.get(i)
        if c is not None and c.is_Number:
            consts[k] = constant_value(t, c)
    out = []
    for r in gen.specs.get(n, ()):
        if len(r) > 2 and not matches(r[2], args, consts):
            continue
        if any(k > n and k not in consts for k, _, _ in (*r[0], *r[1])):
            continue            # a term of a constant that is no Number
        out.append((list(r[0]), list(r[1])))
    return out + expand(gen.schemas, n, consts, leave_out_wide)


#: the functions whose template is :func:`product`'s: the rows over each
#: tuple of factors of the node, then ``a/v**k``
PRODUCT = (Mul,)


def product(gen):
    """The template of ``Mul`` from its rows (``templates/mul.py``): the
    block of the rows (:func:`rows_block`, keyed ``'mul'``) over each tuple
    of factors ``core._mul_factor_sets`` gives (the arguments, then
    ``I*pi*c*s`` with the product ``s`` as one factor, which the
    ``exp(I*pi*c*s)`` rules derive), then ``a/v**k`` (``core._quotient_templates``), then
    the wide formulas of the arguments (:func:`wide_formulas`: the zero
    row past :data:`SOME_PER_ARGUMENT` factors).  The sign of ``c*m``
    against ``m`` for a product ``m`` (``-x*y`` and ``x*y``) is the relation
    glue's (``relations.PRODUCTS``, #315)."""
    block = rows_block('mul', gen)

    def template(expr):
        args = expr.args
        if not args:
            return ()
        out = [block(fs, expr) for fs in _mul_factor_sets(expr)]
        quot = _quotient_templates(expr)
        if quot is not None:
            out.append(quot)
        out += _wide_of(gen, expr, args)
        return out if len(out) > 1 else out[0]
    template.__name__ = template.__qualname__ = 'mul_rows_templates'
    template.__module__ = gen.__module__
    return template


#: the functions whose template is :func:`addition`'s: the rows over the
#: terms of the node, then the sums of a special shape
SUM = (Add,)


def addition(gen):
    """The template of ``Add`` from its rows (``templates/add.py``): the
    block of the rows (:func:`rows_block`, keyed ``'add'``) over the terms,
    then the wide formulas (:func:`wide_formulas`: the strict-sign rows
    past :data:`SOME_PER_ARGUMENT` terms), then the rules of the sums of a
    special shape, which are not rows (:mod:`.core`): ``I*(c_1*x_1 + ...)``
    (``core._imag_templates``).  The sign of ``c0 + c1*u`` from integer
    bounds of ``u`` is the relation glue's (``relations.BOUND_LINKS``,
    ``relations.bound_twins``, #315), and so is the integrality of a sum
    with half-integer coefficients from the parities of its terms
    (``relations.PARITY``, the GF(2) check of LRA, #315)."""
    block = rows_block('add', gen)

    def template(expr):
        args = expr.args
        if not args:
            return ()
        out = [block(args, expr), *_wide_of(gen, expr, args)]
        terms = _imag_split(args)
        if terms is not None:
            imag = _imag_templates(expr, terms)
            if imag is not None:
                out.append(imag)
        return out if len(out) > 1 else out[0]
    template.__name__ = template.__qualname__ = 'add_rows_templates'
    template.__module__ = gen.__module__
    return template
