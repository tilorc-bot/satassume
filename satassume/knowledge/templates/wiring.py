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
then the templates of :data:`AFTER_ROWS`, which are not rows.
``templates/__init__.py`` declares each family as ``"<this
module>:<family>"`` for its functions (``TemplateRegistry.lazy``), so a
family is compiled on the first use of one of its functions, and its
templates are attributed to that name.
"""
from __future__ import annotations

import importlib

from sympy import (
    Mul, Pow, S, acos, andre, asin, catalan, cos, cosh, exp, factorial2, genocchi, im, partition,
    re, sin, subfactorial,
)

from ._common import Rules, const_key, facts
from ._rows import by_function, constant_value, generator
from .core import (
    _exp_arg, _pow_bound_templates, _unit_angle, _unit_power_units, ipi_rules, ipi_split,
    irrational_root,
)
from .functions import (
    _cosh_shift, _exp_ipi, _genocchi_half, _in_unit_interval_units, _pi_trig, _unary,
    _value_units, nary, parts_of_round_templates, shifted,
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
#: ceiling(y) are integers (functions.parts_of_round_templates)
AFTER_ROWS = (((re, im), parts_of_round_templates),)


def functions(family: str):
    """The functions the family's ``RULES`` state rows for, in order."""
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
    no other template here matches a node against shapes."""
    if fn in POWER:
        return power(gen)
    if not getattr(gen, 'plain', True):
        raise ValueError(f"{fn.__name__}: its rows have shapes or terms other than x + c, "
                         "which none of these templates builds")
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
    for fn_name, arity, terms, specs in dict(FAMILIES)[family]:
        fn = by_name.get(fn_name)
        if fn is None:
            # declared by name and new in a later SymPy (owens_t)
            continue
        registry.register(fn)(template(fn, generator(fn_name, arity, terms, specs, name)))
        fns.add(fn)
    for classes, t in AFTER_ROWS:
        if fns.issuperset(classes):
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
    (:func:`.core._unit_power_units`) or the rules of a base ``c0 + c1*u``
    (:func:`.core._pow_bound_templates`)."""
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

    def matches(shape, args, consts):
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
            elif i not in consts:           # 'constant'
                return False
        return True

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
        bound = _pow_bound_templates(expr)
        if bound is not None:
            return [out, bound]
        return out
    template.__name__ = template.__qualname__ = 'pow_templates'
    template.__module__ = gen.__module__
    return template
