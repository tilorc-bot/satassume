"""Which template each function of a family of rows gets (#249).

The family modules (:mod:`.trig`, :mod:`.hyperbolic`, :mod:`.inverse`,
:mod:`.exp_log`, :mod:`.complex_parts`, :mod:`.integer_funcs`, :mod:`.polar`)
state rows only, as ``RULES`` (see :mod:`._rows`).  :func:`load` compiles
a family's rows and registers one template per function (:func:`template`):
the unary template of its rows (:func:`.functions._unary`), with the facts
of a constant argument for a function of :data:`UNIT_INTERVAL`, or, for a
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

from sympy import S, acos, asin, cos, cosh, exp, im, re, sin

from ._rows import by_function, rules
from .core import ipi_split
from .functions import (
    _cosh_shift, _exp_ipi, _in_unit_interval_units, _pi_trig, _unary, nary,
    parts_of_round_templates, shifted,
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
    node of another number of arguments gets no facts."""
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
    units = _in_unit_interval_units(fn.__name__) if fn in UNIT_INTERVAL else None
    return _unary(fn.__name__, gen, lambda a: tuple(shifted(a, S(c)) for c in shifts), units)


def load(family: str) -> None:
    """Register the templates of the family's rows (``TemplateRegistry.lazy``),
    then those of :data:`AFTER_ROWS` for its functions."""
    name = f"{__name__}:{family}"
    fns = set()
    for fn, all_rows in by_function(importlib.import_module(f"{__package__}.{family}").RULES):
        registry.register(fn)(template(fn, rules(fn, all_rows, name)))
        fns.add(fn)
    for classes, t in AFTER_ROWS:
        if fns.issuperset(classes):
            registry.register(*classes)(_attributed(t, name))


def _attributed(t, module):
    """``t``, attributed to ``module`` (the registry tells a declared
    module's templates by their module)."""
    def template(expr):
        return t(expr)
    template.__name__ = template.__qualname__ = t.__name__
    template.__module__ = module
    return template
